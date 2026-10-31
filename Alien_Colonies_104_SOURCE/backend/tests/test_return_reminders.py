"""Return campaigns use synthetic accounts and fake senders, never real recipients."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World, GameError, UpdatePolicy, build_server
from inactivity import ACTIVITY_HEADER
import push_notifications as push

NOW = 1_900_000_000.0
DAY = 86400
PASSWORD = "reminder-local-test-password"


class Sender:
    def __init__(self, result="sent"):
        self.result = result
        self.calls = []

    def send(self, token, data):
        self.calls.append((token, data))
        return self.result


class ReturnReminderTests(unittest.TestCase):
    def setUp(self):
        self.world = World(":memory:", now=NOW)
        self.addCleanup(lambda: self.world.close())
        self.first = self.world.register("Reminder first", PASSWORD)
        self.pid = self.first["state"]["player"]["id"]
        self.world.data["alien"]["next_expansion_at"] = NOW + 365 * DAY
        self.configured = patch.object(push, "configuration", return_value={"configured": True})
        self.configured.start()
        self.addCleanup(self.configured.stop)

    def subscribe(self, suffix="a", language="en", player=None, session=None):
        return push.register(self.world, player or self.pid, session or self.first["token"],
                             {"token": "device_" + suffix * 150, "language": language})

    def outbox(self):
        return self.world.db.execute("SELECT report_id,player_id,payload,attempts,next_at FROM push_outbox").fetchall()

    def queue(self):
        return push.enqueue_return_reminders(self.world)

    def due(self):
        self.world.now = NOW + DAY

    def test_exact_24_real_hours_and_no_daily_repetition(self):
        self.subscribe()
        self.world.speed = 1000
        self.world.now = NOW + DAY - .001
        self.assertEqual(self.queue(), 0)
        self.due()
        self.assertEqual(self.queue(), 1)
        self.assertEqual(self.queue(), 0)
        sender = Sender()
        self.assertEqual(push.deliver_due(self.world, sender), 1)
        for days in (2, 3, 7, 20):
            self.world.now = NOW + days * DAY
            self.assertEqual(self.queue(), 0)
            self.assertEqual(push.deliver_due(self.world, sender), 0)
        self.assertEqual(len(sender.calls), 1)

    def test_languages_and_devices_share_one_absence_episode(self):
        for index, language in enumerate(("en", "pl", "de", "es", "fr")):
            self.subscribe(chr(97 + index), language)
        self.due()
        before = copy.deepcopy(self.world.data)
        self.assertEqual(self.queue(), 1)
        sender = Sender()
        self.assertEqual(push.deliver_due(self.world, sender), 5)
        self.assertEqual({(d["title"], d["body"]) for _, d in sender.calls}, set(push.RETURN_COPY.values()))
        self.assertEqual(len({d["report_id"] for _, d in sender.calls}), 1)
        self.assertTrue(all(d["kind"] == "return_reminder" and d["player_id"] == self.pid for _, d in sender.calls))
        self.assertTrue(all(isinstance(value, str) for _, d in sender.calls for value in d.values()))
        self.assertEqual(self.world.data, before)  # No new gameplay report or activity.

    def test_unconfigured_or_unsubscribed_players_never_receive_a_reminder(self):
        self.due()
        self.assertEqual(self.queue(), 0)
        self.subscribe()
        with patch.object(push, "configuration", return_value={"configured": False}):
            self.assertEqual(self.queue(), 0)
        self.assertFalse(self.outbox())

    def test_language_fallback_and_account_isolation(self):
        self.subscribe(language="unsupported")
        second = self.world.register("Other reminder", PASSWORD)
        other = second["state"]["player"]["id"]
        self.subscribe("z", player=other, session=second["token"])
        self.due()
        self.world.mark_player_activity(other)
        self.assertEqual(self.queue(), 1)
        row = self.outbox()[0]
        self.assertEqual(row[1], self.pid)
        payload = json.loads(row[2])
        self.assertEqual((payload["title"], payload["body"]), push.RETURN_COPY["en"])

    def test_return_cancels_retries_then_next_24_hours_creates_new_id(self):
        self.subscribe()
        self.due()
        self.queue()
        old_id = self.outbox()[0][0]
        sender = Sender("retry")
        self.assertEqual(push.deliver_due(self.world, sender), 0)
        self.assertEqual(self.outbox()[0][3:], (1, NOW + DAY + 30))
        self.world.now += 10
        self.world.mark_player_activity(self.pid)
        self.assertFalse(self.outbox())
        self.world.now += DAY - .001
        self.assertEqual(self.queue(), 0)
        self.world.now += .001
        self.assertEqual(self.queue(), 1)
        self.assertNotEqual(self.outbox()[0][0], old_id)

    def test_login_return_cancels_queued_reminder(self):
        self.subscribe()
        self.due()
        self.queue()
        self.world.login("Reminder first", PASSWORD)
        self.assertFalse(self.outbox())
        self.assertEqual(self.queue(), 0)

    def test_failed_activity_commit_preserves_reminder_and_activity(self):
        self.subscribe()
        self.due()
        self.queue()
        before = self.outbox()
        with patch.object(self.world, "_save", side_effect=OSError("synthetic save failure")):
            with self.assertRaises(GameError):
                self.world.mark_player_activity(self.pid)
        self.assertEqual(self.outbox(), before)
        self.assertEqual(self.world._player(self.pid)["last_active_at"], NOW)
        self.assertEqual(self.queue(), 0)

    def test_background_reports_and_reads_do_not_reset_the_clock(self):
        self.subscribe()
        self.due()
        with self.world._atomic():
            self.world._report(self.pid, "Fixture report", "Synthetic background completion")
        self.world.state(self.pid)
        self.assertEqual(self.world._player(self.pid)["last_active_at"], NOW)
        self.assertEqual(self.queue(), 1)
        self.assertEqual(len(self.outbox()), 2)

    def test_recent_open_game_suppresses_enqueue_without_touching_production_activity(self):
        self.subscribe()
        self.due()
        with patch.object(push.time, "monotonic", return_value=500):
            self.world._state_poll_presence[self.pid] = 499
            self.assertEqual(self.queue(), 0)
            self.world._state_poll_presence[self.pid] = 500 - push.RETURN_PRESENCE_SECONDS
            self.assertEqual(self.queue(), 1)
        self.assertEqual(self.world._player(self.pid)["last_active_at"], NOW)

    def test_open_game_after_enqueue_prevents_send(self):
        self.subscribe()
        self.due()
        self.queue()
        with patch.object(push.time, "monotonic", return_value=500):
            self.world._state_poll_presence[self.pid] = 499
            sender = Sender()
            self.assertEqual(push.deliver_due(self.world, sender), 0)
        self.assertFalse(sender.calls)
        self.assertFalse(self.outbox())

    def test_expired_and_invalid_sessions_logout_and_unsubscribe_never_send(self):
        for mode in ("expires", "logout", "unsubscribe"):
            with self.subTest(mode=mode):
                self.world.now = NOW
                login = self.world.login("Reminder first", PASSWORD)
                self.subscribe(session=login["token"])
                self.due()
                if mode == "expires":
                    self.world.db.execute("UPDATE sessions SET expires=?", (self.world.now,))
                    self.world.db.commit()
                elif mode == "logout":
                    self.world.logout(login["token"])
                else:
                    push.unregister(self.world, self.pid, login["token"])
                self.assertEqual(self.queue(), 0)
                self.assertEqual(push.deliver_due(self.world, Sender()), 0)

    def test_queued_notification_does_not_follow_installation_to_another_account(self):
        self.subscribe()
        self.due()
        self.queue()
        other = self.world.register("New device owner", PASSWORD)
        other_id = other["state"]["player"]["id"]
        self.subscribe(player=other_id, session=other["token"])
        self.assertFalse(self.outbox())
        self.assertEqual(self.queue(), 0)

    def test_dead_tokens_are_removed_and_ignored_afterwards(self):
        self.subscribe()
        self.due()
        self.queue()
        sender = Sender("unregistered")
        self.assertEqual(push.deliver_due(self.world, sender), 0)
        self.assertFalse(self.outbox())
        self.assertEqual(self.queue(), 0)
        self.assertEqual(len(sender.calls), 1)

    def test_retry_exhaustion_never_starts_another_campaign(self):
        self.subscribe()
        self.due()
        self.queue()
        self.world.db.execute("UPDATE push_outbox SET attempts=7")
        self.world.db.commit()
        sender = Sender("retry")
        push.deliver_due(self.world, sender)
        self.assertFalse(self.outbox())
        self.assertEqual(self.queue(), 0)

    def test_one_hour_expiry_does_not_requeue_but_reports_keep_their_existing_ttl(self):
        self.subscribe()
        self.due()
        self.queue()
        with self.world._atomic():
            self.world._report(self.pid, "Report stays", "Synthetic mission")
        self.world.now += push.RETURN_TTL_SECONDS
        sender = Sender()
        self.assertEqual(push.deliver_due(self.world, sender), 1)
        self.assertEqual(sender.calls[0][1]["kind"], "report")
        self.assertEqual(self.queue(), 0)

    def test_delivery_uses_committed_rows_without_holding_world_lock(self):
        self.subscribe()
        self.due()
        self.queue()
        world = self.world
        outer = self
        class CheckingSender(Sender):
            def send(self, token, data):
                outer.assertFalse(world.lock._is_owned())
                outer.assertFalse(world.db.in_transaction)
                return super().send(token, data)
        sender = CheckingSender()
        self.assertEqual(push.deliver_due(world, sender), 1)

    def test_uncommitted_work_never_enqueues_or_sends(self):
        self.subscribe()
        self.due()
        with self.world._atomic():
            self.assertEqual(self.queue(), 0)
            self.assertEqual(push.deliver_due(self.world, Sender()), 0)
        self.assertFalse(self.outbox())

    def test_failed_enqueue_rolls_back_episode_so_it_can_be_retried(self):
        self.subscribe()
        self.due()
        self.world.db.executescript("""CREATE TRIGGER reject_fixture_push BEFORE INSERT ON push_outbox
          BEGIN SELECT RAISE(ABORT, 'synthetic enqueue failure'); END;""")
        with self.assertRaises(Exception):
            self.queue()
        self.assertFalse(self.outbox())
        self.assertEqual(self.world.db.execute("SELECT count(*) FROM push_return_reminders").fetchone()[0], 0)
        self.world.db.execute("DROP TRIGGER reject_fixture_push")
        self.world.db.commit()
        self.assertEqual(self.queue(), 1)

    def test_missing_invalid_or_future_activity_is_not_a_target(self):
        self.subscribe()
        self.due()
        for invalid in (None, -1, "yesterday", float("nan"), float("inf"), NOW + 3 * DAY):
            self.world._player(self.pid)["last_active_at"] = invalid
            self.assertEqual(self.queue(), 0)
        self.world._player(self.pid)["last_active_at"] = NOW

    def test_account_deletion_cascades_the_episode_and_outbox(self):
        self.subscribe()
        self.due()
        self.queue()
        self.world.account_delete(self.first["token"], PASSWORD, "DELETE ACCOUNT")
        self.assertFalse(self.outbox())
        self.assertEqual(self.world.db.execute("SELECT count(*) FROM push_return_reminders").fetchone()[0], 0)

    def test_restart_preserves_pending_retry_and_consumed_episode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "reminders.sqlite3")
            self.world.close()
            self.world = World(path, now=NOW)
            self.first = self.world.register("Persisted reminder", PASSWORD)
            self.pid = self.first["state"]["player"]["id"]
            self.world.data["alien"]["next_expansion_at"] = NOW + 365 * DAY
            self.subscribe()
            self.due()
            self.queue()
            notification_id = self.outbox()[0][0]
            push.deliver_due(self.world, Sender("retry"))
            self.world.close()
            self.world = World(path, now=NOW + DAY + 31)
            self.assertEqual(self.queue(), 0)
            self.assertEqual(self.outbox()[0][0], notification_id)
            sender = Sender()
            self.assertEqual(push.deliver_due(self.world, sender), 1)
            self.world.close()
            self.world = World(path, now=NOW + 2 * DAY)
            self.assertEqual(self.queue(), 0)
            self.assertFalse(self.outbox())


class ReturnReminderWorkerTests(unittest.TestCase):
    def test_existing_worker_sweeps_once_a_minute_and_delivers_each_iteration(self):
        stop = SimpleNamespace(wait=unittest.mock.Mock(side_effect=[False, False, True]))
        with patch.object(push, "FcmSender"), patch.object(push.time, "monotonic", return_value=500), \
                patch.object(push, "enqueue_return_reminders", return_value=0) as enqueue, \
                patch.object(push, "deliver_due") as deliver:
            push.run_sender(object(), stop)
        self.assertEqual(enqueue.call_count, 1)
        self.assertEqual(deliver.call_count, 2)

    def test_fcm_http_payload_preserves_reports_and_uses_normal_priority_for_reminders(self):
        sender = push.FcmSender()
        sender.credentials = SimpleNamespace(valid=True, token="synthetic-access-token")
        for kind in ("return_reminder", "attack", "report"):
            data = {"kind": kind, "report_id": "synthetic", "player_id": "fixture"}
            with patch.object(push, "configuration", return_value={"configured": True, "project_id": "fixture"}), \
                    patch.object(push.urllib.request, "urlopen") as send:
                self.assertEqual(sender.send("synthetic-device", data), "sent")
            message = json.loads(send.call_args.args[0].data)["message"]
            self.assertEqual(message["data"], data)
            self.assertNotIn("notification", message)
            self.assertEqual(send.call_args.kwargs["timeout"], 10)
            if kind == "return_reminder":
                self.assertEqual(message["android"], {"priority": "NORMAL", "ttl": "3600s", "collapse_key": "alien-return-24h"})
            else:
                self.assertEqual(message["android"], {"priority": "HIGH", "ttl": "86400s"})


class ReturnReminderHTTPTests(unittest.TestCase):
    def test_authenticated_foreground_return_from_web_cancels_android_reminder(self):
        world = World(":memory:", now=NOW)
        account = world.register("Http reminder", PASSWORD)
        player_id = account["state"]["player"]["id"]
        world.data["alien"]["next_expansion_at"] = NOW + 365 * DAY
        push.register(world, player_id, account["token"], {"token": "http_" + "x" * 150})
        server = build_server(world, port=0, update_policy=UpdatePolicy(min_version_code=1))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch.object(push, "configuration", return_value={"configured": True}):
                world.now = NOW + DAY
                self.assertEqual(push.enqueue_return_reminders(world), 1)
                with patch("app.time.time", return_value=NOW + DAY + 1):
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
                    connection.request("GET", "/api/state", headers={"Authorization": "Bearer " + account["token"],
                        "X-PGR-Client-Version": "92", ACTIVITY_HEADER: "1", "Accept-Language": "en"})
                    response = connection.getresponse()
                    response.read()
                    self.assertEqual(response.status, 200)
                    connection.close()
                self.assertEqual(world._player(player_id)["last_active_at"], NOW + DAY + 1)
                self.assertEqual(world.db.execute("SELECT count(*) FROM push_outbox").fetchone()[0], 0)
                self.assertEqual(push.deliver_due(world, Sender()), 0)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(3)
            world.close()


if __name__ == "__main__":
    unittest.main()
