"""Deterministic account inactivity, settlement and authenticated-return tests."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World, GameError, RESOURCES, UpdatePolicy, build_server
from inactivity import INACTIVE_AFTER_SECONDS, ACTIVITY_HEADER

NOW = 1_900_000_000.0
DAY = 86400
PASSWORD = "inactivity-local-test-password"


class InactivityProduction(unittest.TestCase):
    def setUp(self):
        self.w = World(":memory:", now=NOW)
        self.addCleanup(self.w.close)
        result = self.w.register("ActivePlayer", PASSWORD)
        self.pid, self.token = result["state"]["player"]["id"], result["token"]
        self.player = self.w._player(self.pid)
        self.p = self.w._owned(self.pid)
        self.w.data["alien"]["next_expansion_at"] = NOW + 365 * DAY
        self.before = dict(self.p["resources"])
        self.rates = self.w.production(self.p)

    def assert_resources(self, expected, planet=None):
        for key in RESOURCES:
            self.assertAlmostEqual((planet or self.p)["resources"][key], expected[key], places=6)

    def expected(self, seconds, initial=None, rates=None):
        return {key: (initial or self.before)[key] + (rates or self.rates)[key] * seconds / 3600
                for key in RESOURCES}

    def test_exact_seven_day_boundary_and_long_offline_jump(self):
        self.w.advance(NOW + INACTIVE_AFTER_SECONDS - 1)
        self.assertFalse(self.w._production_status(self.pid)["paused"])
        self.assert_resources(self.expected(INACTIVE_AFTER_SECONDS - 1))
        self.w.advance(NOW + INACTIVE_AFTER_SECONDS)
        self.assertTrue(self.w._production_status(self.pid)["paused"])
        self.assertEqual(self.w.production(self.p), dict.fromkeys(RESOURCES, 0.0))
        self.assert_resources(self.expected(INACTIVE_AFTER_SECONDS))
        self.w.advance(NOW + 30 * DAY)
        self.assert_resources(self.expected(INACTIVE_AFTER_SECONDS))

    def test_single_30_day_settlement_grants_only_first_seven_days(self):
        self.w.advance(NOW + 30 * DAY)
        self.assert_resources(self.expected(INACTIVE_AFTER_SECONDS))
        self.assertEqual(self.player["last_active_at"], NOW)

    def test_all_colonies_share_account_cutoff(self):
        other = next(p for p in self.w.data["planets"].values() if p["owner_type"] == "empty")
        other.update(owner_type="player", owner_id=self.pid,
                     buildings=copy.deepcopy(self.p["buildings"]), resources=dict.fromkeys(RESOURCES, 0.0))
        other_rates = self.w.production(other)
        self.w.advance(NOW + 9 * DAY)
        self.assert_resources(self.expected(INACTIVE_AFTER_SECONDS))
        self.assert_resources(self.expected(INACTIVE_AFTER_SECONDS, dict.fromkeys(RESOURCES, 0.0), other_rates), other)
        self.assertEqual(self.w.production(other), dict.fromkeys(RESOURCES, 0.0))

    def test_return_resumes_without_paused_interval_backpay(self):
        self.w.advance(NOW + 20 * DAY)
        paused = dict(self.p["resources"])
        self.w.login("ActivePlayer", PASSWORD)
        self.assert_resources(paused)
        self.assertEqual(self.player["last_active_at"], NOW + 20 * DAY)
        self.assertFalse(self.w._production_status(self.pid)["paused"])
        self.w.advance(NOW + 20 * DAY + 3600)
        self.assert_resources(self.expected(3600, paused))

    def test_reading_authenticating_and_observing_never_revive_account(self):
        other = self.w.register("ObserverPlayer", PASSWORD)["state"]["player"]["id"]
        self.w.advance(NOW + 8 * DAY)
        stock = dict(self.p["resources"])
        self.assertEqual(self.w.authenticate(self.token), self.pid)
        self.w.state(self.pid)
        self.w.state(other)
        self.w._capture_planetary_intel(other, self.p)
        self.w._report(self.pid, "Passive event", "An automatic report is not user activity.")
        self.assertEqual(self.player["last_active_at"], NOW)
        self.w.advance(NOW + 9 * DAY)
        self.assert_resources(stock)

    def test_successful_new_action_counts_failed_or_replayed_action_does_not(self):
        request = {"type": "build", "key": "metal_mine", "request_id": "local-new-command"}
        self.w.advance(NOW + 30)
        self.w.action(self.pid, request)
        self.assertEqual(self.player["last_active_at"], NOW + 30)
        self.w.advance(NOW + 60)
        self.w.action(self.pid, request)
        self.assertEqual(self.player["last_active_at"], NOW + 30)
        with self.assertRaises(GameError):
            self.w.action(self.pid, {"type": "invalid"})
        self.assertEqual(self.player["last_active_at"], NOW + 30)

    def test_prepaid_project_and_returning_fleet_finish_after_cutoff(self):
        self.w.action(self.pid, {"type": "build", "key": "metal_mine"})
        task = self.p["queue"][0]
        task["ends_at"] = NOW + 8 * DAY
        current = dict(self.p["resources"])
        target = next(p for p in self.w.data["planets"].values() if p["owner_type"] == "empty")
        ships_before = self.p["ships"]["scout"]
        self.w.data["fleets"]["freturn"] = {
            "id": "freturn", "owner_id": self.pid, "origin_id": self.p["id"],
            "target_id": target["id"], "mission": "scout", "status": "returning",
            "ships": {"scout": 1}, "cargo": {"metal": 17, "crystal": 11, "fuel": 5},
            "started_at": NOW, "arrives_at": NOW + 9 * DAY, "seconds": 9 * DAY}
        self.w.advance(NOW + 10 * DAY)
        expected = self.expected(INACTIVE_AFTER_SECONDS, current)
        for key, cargo in (("metal", 17), ("crystal", 11), ("fuel", 5)):
            expected[key] += cargo
        self.assert_resources(expected)
        self.assertEqual(self.p["buildings"]["metal_mine"], 2)
        self.assertFalse(self.p["queue"])
        self.assertNotIn("freturn", self.w.data["fleets"])
        self.assertEqual(self.p["ships"]["scout"], ships_before + 1)
        self.assertEqual(self.player["last_active_at"], NOW)

    def test_khar_and_dyson_are_not_farmable_player_resource_production(self):
        npc = next(p for p in self.w.data["planets"].values() if p["owner_id"] == "khar")
        npc["resources"] = dict.fromkeys(RESOURCES, 0.0)
        npc["swarm_established_at"] = NOW
        rates = self.w.production(npc)
        self.player["megastructure"] = {"origin_id": self.p["id"], "dyson_stage": 1,
                                         "gate_level": 0, "energy": 0.0, "queue": None, "window": None}
        self.w.advance(NOW + 8 * DAY)
        for key in RESOURCES:
            self.assertAlmostEqual(npc["resources"][key], min(self.w.MAX_RESOURCE, rates[key] * 8 * DAY / 3600), places=6)
        self.assertGreater(self.player["megastructure"]["energy"], 0)
        self.assertEqual(self.w._production_cutoff("khar"), float("inf"))
        self.assertEqual(self.w.production(self.p), dict.fromkeys(RESOURCES, 0.0))

    def test_cutoff_is_real_time_independent_of_server_speed(self):
        self.w.speed = 1000
        self.rates = self.w.production(self.p)
        self.w.advance(NOW + INACTIVE_AFTER_SECONDS - 1)
        self.assertFalse(self.w._production_status(self.pid)["paused"])
        self.w.advance(NOW + INACTIVE_AFTER_SECONDS)
        self.assertTrue(self.w._production_status(self.pid)["paused"])

    def test_planning_never_forecasts_resources_after_cutoff(self):
        self.player["subscription"] = {"enable_queue_planning": True, "starts_at": NOW,
                                       "expires_at": NOW + 60 * DAY}
        self.player["planned_orders"] = [{"id": "planned", "kind": "build", "key": "metal_mine",
                                            "planet_id": self.p["id"], "created_at": NOW, "amount": 1}]
        entry = {"cost": {"metal": 100000000, "crystal": 0, "fuel": 0}}
        with patch.object(self.w, "_planned_readiness", return_value=(self.p, entry, "waiting_resources", "")):
            deadlines = self.w._planned_queue_deadlines(NOW, NOW + 60 * DAY)
        self.assertEqual(deadlines, [NOW + INACTIVE_AFTER_SECONDS])

    def test_planned_project_affordable_exactly_at_cutoff_can_start(self):
        self.player["subscription"] = {"enable_queue_planning": True, "starts_at": NOW,
                                       "expires_at": NOW + 60 * DAY}
        entry = next(item for item in self.w._catalog(self.pid, self.p)["buildings"]
                     if item["key"] == "metal_mine")
        self.p["resources"] = {key: max(0.0, entry["cost"][key] - self.rates[key] * 60 / 3600)
                               for key in RESOURCES}
        self.player["last_active_at"] = NOW + 60 - INACTIVE_AFTER_SECONDS
        self.player["planned_orders"] = [{"id": "at-cutoff", "kind": "build", "key": "metal_mine",
                                            "planet_id": self.p["id"], "created_at": NOW, "amount": 1}]
        self.w.advance(NOW + 61)
        self.assertFalse(self.player["planned_orders"])
        task = next(task for task in self.p["queue"] if task.get("planned_order_id") == "at-cutoff")
        self.assertEqual(task["started_at"], NOW + 60)
        self.assertTrue(self.w._production_status(self.pid)["paused"])

    def test_new_chat_message_counts_but_replay_and_read_ack_do_not(self):
        self.w.advance(NOW + 8 * DAY)
        payload = {"text": "Local test message", "request_id": "local-chat-command"}
        response = self.w.chat_send(self.pid, payload)
        self.assertEqual(self.player["last_active_at"], NOW + 8 * DAY)
        self.w.advance(NOW + 9 * DAY)
        self.w.chat_send(self.pid, payload)
        self.w.chat_read(self.pid, {"last_id": response["sent"]["id"]})
        self.w.chat_inbox(self.pid)
        self.w.chat_feed(self.pid)
        self.assertEqual(self.player["last_active_at"], NOW + 8 * DAY)

    def test_activity_change_rolls_back_on_save_failure(self):
        self.w.advance(NOW + 8 * DAY)
        before = copy.deepcopy(self.w.data)
        with patch.object(self.w, "_save", side_effect=OSError("local synthetic write failure")):
            with self.assertRaises(GameError):
                self.w.mark_player_activity(self.pid)
        self.assertEqual(self.w.data, before)


class InactivityMigration(unittest.TestCase):
    def test_one_time_grace_and_restart_preserve_activity_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "inactivity.sqlite3")
            w = World(path, now=NOW)
            pid = w.register("LegacyPlayer", PASSWORD)["state"]["player"]["id"]
            w.data["alien"]["next_expansion_at"] = NOW + 365 * DAY
            w.data.pop("activity_schema_version")
            w.data.pop("activity_policy_started_at")
            w._player(pid).pop("last_active_at")
            w.close()
            migrated = World(path, now=NOW + DAY)
            self.assertEqual(migrated._player(pid)["last_active_at"], NOW + DAY)
            self.assertEqual(migrated.data["activity_policy_started_at"], NOW + DAY)
            migrated.close()
            restarted = World(path, now=NOW + 10 * DAY)
            self.assertEqual(restarted._player(pid)["last_active_at"], NOW + DAY)
            self.assertTrue(restarted._production_status(pid)["paused"])
            stock = dict(restarted._owned(pid)["resources"])
            restarted.close()
            again = World(path, now=NOW + 11 * DAY)
            self.assertEqual(again._owned(pid)["resources"], stock)
            self.assertEqual(again.data["activity_policy_started_at"], NOW + DAY)
            again.close()


class InactivityHTTP(unittest.TestCase):
    def setUp(self):
        self.w = World(":memory:", now=NOW)
        response = self.w.register("HttpActive", PASSWORD)
        self.pid, self.token = response["state"]["player"]["id"], response["token"]
        self.w.data["alien"]["next_expansion_at"] = NOW + 365 * DAY
        self.server = build_server(self.w, port=0, update_policy=UpdatePolicy(min_version_code=1))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(3)
        self.w.close()

    def request(self, headers=(), path="/api/state", token=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        try:
            connection.putrequest("GET", path)
            connection.putheader("Authorization", "Bearer " + (self.token if token is None else token))
            connection.putheader("X-PGR-Client-Version", "68")
            for key, value in headers:
                connection.putheader(key, value)
            connection.endheaders()
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_foreground_signal_resumes_but_poll_does_not_and_no_backpay(self):
        with patch("app.time.time", return_value=NOW + 8 * DAY):
            status, poll = self.request()
            self.assertEqual(status, 200)
            self.assertTrue(poll["state"]["production_status"]["paused"])
            self.assertEqual(poll["state"]["production"], dict.fromkeys(RESOURCES, 0))
            stocks = dict(self.w._owned(self.pid)["resources"])
            status, active = self.request([(ACTIVITY_HEADER, "1")])
            self.assertEqual(status, 200)
            self.assertFalse(active["state"]["production_status"]["paused"])
            self.assertEqual(self.w._owned(self.pid)["resources"], stocks)
            self.assertEqual(self.w._player(self.pid)["last_active_at"], NOW + 8 * DAY)

    def test_invalid_signal_unauthorized_or_wrong_planet_do_not_resume(self):
        with patch("app.time.time", return_value=NOW + 8 * DAY):
            for headers in ([(ACTIVITY_HEADER, "0")], [(ACTIVITY_HEADER, "1"), (ACTIVITY_HEADER, "1")]):
                self.assertEqual(self.request(headers)[0], 200)
                self.assertEqual(self.w._player(self.pid)["last_active_at"], NOW)
            self.assertEqual(self.request([(ACTIVITY_HEADER, "1")], token="not-a-session-token-123456")[0], 401)
            self.assertEqual(self.request([(ACTIVITY_HEADER, "1")], path="/api/state?planet_id=not-owned")[0], 403)
            self.assertEqual(self.w._player(self.pid)["last_active_at"], NOW)


if __name__ == "__main__":
    unittest.main()
