"""Unused-account selection and deletion against the CURRENT root app.py.

All accounts/databases are local fixtures. Never uses production credentials.
"""
import copy
import http.client
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import accounts


START = 1_900_000_000.0
PASSWORD = "unused-account-test-password"


class UnusedAccountsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "world.sqlite3"
        self.world = app.World(self.path, now=START)
        old = self.world.register("Dormant fixture", PASSWORD)
        self.old_token = old["token"]
        self.pid = old["state"]["player"]["id"]
        active = self.world.register("Active fixture", PASSWORD)
        self.active_token = active["token"]
        self.other = active["state"]["player"]["id"]
        self.player = self.world.data["players"][self.pid]
        self.player["last_active_at"] = START - accounts.UNUSED_IDLE_SECONDS
        self.home = self.player["home_id"]
        self.world._save()

    def tearDown(self):
        self.world.close()
        self.temp.cleanup()

    def preview(self):
        return self.world.unused_accounts_preview(at=START)

    def request(self, preview=None):
        preview = self.preview() if preview is None else preview
        return {"preview_id": preview["preview_id"], "count": preview["count"],
                "confirmation": accounts.UNUSED_CONFIRMATION}

    def snapshot(self):
        return copy.deepcopy(self.world.data), "\n".join(self.world.db.iterdump())

    def test_exact_48_hour_boundary_and_invalid_timestamps(self):
        for value, eligible in ((START - 172800, True), (START - 172799.9, False),
                                (START + 1, False), (None, False), ("0", False),
                                (True, False), (float("nan"), False)):
            with self.subTest(value=value):
                data = copy.deepcopy(self.world.data)
                data["players"][self.pid]["last_active_at"] = value
                self.assertEqual(accounts.unused_account_reason(data, self.pid, START) is None, eligible)

    def test_zero_points_does_not_mean_no_development(self):
        self.world.data["planets"][self.home]["buildings"]["metal_mine"] = 1
        self.assertEqual(self.preview()["count"], 0)

    def test_all_recorded_progress_queues_purchases_and_uncertain_data_are_excluded(self):
        changes = [
            ("completed then lost building", lambda p, h: p["review_invitation"].update(completed_builds=1)),
            ("missing lifetime counter", lambda p, h: p.pop("review_invitation")),
            ("invalid lifetime counter", lambda p, h: p["review_invitation"].update(completed_builds=False)),
            ("research", lambda p, h: p["research"].update(propulsion=1)),
            ("missing research", lambda p, h: p.pop("research")),
            ("level 1 building", lambda p, h: h["buildings"].update(metal_mine=1)),
            ("ship", lambda p, h: h["ships"].update(scout=1)),
            ("defense", lambda p, h: h["defenses"].update(turret=1)),
            ("live queue", lambda p, h: h["queue"].append({"kind": "build"})),
            ("planned queue", lambda p, h: p["planned_orders"].append({"kind": "build"})),
            ("first building history", lambda p, h: p.update(onboarding={"completed": {"first_building": True}})),
            ("extra skill", lambda p, h: p.update(race_id="zetans", skill_nodes=["zetans_root", "paid_skill"])),
            ("rare currency", lambda p, h: p.update(swarm_crystals=1)),
            ("subscription history", lambda p, h: p.update(subscription={"status": "expired"})),
            ("alliance", lambda p, h: p.update(alliance_id="alliance-fixture")),
            ("scouting", lambda p, h: p.update(scout_intel={"old-planet": {}})),
            ("megastructure", lambda p, h: p["megastructure"].update(dyson_stage=1)),
            ("cancelled build command", lambda p, h: p["requests"].update(old={"fingerprint": '{"type":"build"}'})),
            ("unknown command history", lambda p, h: p["requests"].update(old={"fingerprint": "broken"})),
        ]
        for name, mutate in changes:
            with self.subTest(name=name):
                data = copy.deepcopy(self.world.data)
                mutate(data["players"][self.pid], data["planets"][self.home])
                self.assertIsNotNone(accounts.unused_account_reason(data, self.pid, START))

    def test_race_choice_free_root_and_passive_resource_growth_are_not_upgrades(self):
        self.player.update(race_id="zetans", skill_nodes=["zetans_root"])
        self.player["requests"]["choice"] = {"fingerprint": '{"type":"choose_race"}'}
        self.world.data["planets"][self.home]["resources"]["metal"] = 10000
        self.assertEqual(self.preview()["count"], 1)

    def test_owned_second_planet_or_flying_fleet_excludes_account(self):
        for kind in ("planet", "fleet"):
            with self.subTest(kind=kind):
                data = copy.deepcopy(self.world.data)
                if kind == "planet":
                    data["planets"]["extra"] = {"id": "extra", "owner_id": self.pid, "owner_type": "player"}
                else:
                    data["fleets"]["flight"] = {"owner_id": self.pid}
                self.assertIsNotNone(accounts.unused_account_reason(data, self.pid, START))

    def test_preview_is_read_only_and_contains_no_authentication_material(self):
        before = self.snapshot()
        preview = self.preview()
        self.assertEqual(preview["count"], 1)
        self.assertEqual(preview["candidates"][0]["id"], self.pid)
        self.assertEqual(self.snapshot(), before)
        for secret in (PASSWORD, self.old_token, self.active_token):
            self.assertNotIn(secret, json.dumps(preview))
        preview["candidates"][0]["id"] = self.other
        self.assertEqual(self.world._unused_previews[preview["preview_id"]]["candidates"][0]["id"], self.pid)

    def test_current_online_presence_and_sent_chat_protect_player(self):
        self.world._state_poll_presence[self.pid] = time.monotonic()
        self.assertEqual(self.preview()["count"], 0)
        self.world._state_poll_presence.clear()
        self.world.db.execute("INSERT INTO chat_messages(sender,recipient,body,created,request_id) VALUES(?,NULL,?,?,?)",
                              (self.pid, "I am a player", START - 200000, "local-chat-fixture"))
        self.world.db.commit()
        self.assertEqual(self.preview()["count"], 0)

    def test_requires_confirmation_fresh_exact_preview_and_matching_count(self):
        request = self.request()
        invalid = ({}, {**request, "confirmation": ""}, {**request, "preview_id": "wrong"},
                   {**request, "count": 2}, {**request, "count": True},
                   {**request, "preview_id": []})
        before = self.snapshot()
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(app.GameError):
                self.world.unused_accounts_delete(payload, at=START)
            self.assertEqual(self.snapshot(), before)
        with self.assertRaises(app.GameError):
            self.world.unused_accounts_delete(request, at=START + accounts.UNUSED_PREVIEW_SECONDS)
        self.assertEqual(self.snapshot(), before)

    def test_player_return_or_new_progress_aborts_entire_selection(self):
        for change in ("login", "build"):
            with self.subTest(change=change):
                request = self.request()
                if change == "login":
                    self.player["last_active_at"] = START
                else:
                    self.world.data["planets"][self.home]["queue"] = [{"kind": "build"}]
                self.world._save()
                before = self.snapshot()
                with self.assertRaises(app.GameError):
                    self.world.unused_accounts_delete(request, at=START)
                self.assertEqual(self.snapshot(), before)
                self.player["last_active_at"] = START - 172800
                self.world.data["planets"][self.home]["queue"] = []

    def test_verified_backup_cleanup_and_restart_preserve_other_empire_and_world(self):
        request = self.request()
        before = copy.deepcopy(self.world.data)
        report = self.world.unused_accounts_delete(request, at=START)
        self.assertEqual(report["deleted"], 1)
        backup_path = self.path.parent / "reset-backups" / report["backup"]
        with sqlite3.connect(backup_path) as backup:
            self.assertEqual(backup.execute("PRAGMA integrity_check").fetchone(), ("ok",))
            self.assertEqual(backup.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 2)
            self.assertEqual(json.loads(backup.execute("SELECT body FROM snapshot").fetchone()[0]), before)
        self.assertNotIn(self.pid, self.world.data["players"])
        self.assertEqual(self.world.data["players"][self.other], before["players"][self.other])
        self.assertEqual(self.world.data["alien"], before["alien"])
        self.assertEqual(self.world.data["systems"], before["systems"])
        self.assertEqual({key: value for key, value in self.world.data["planets"].items() if key != self.home},
                         {key: value for key, value in before["planets"].items() if key != self.home})
        home = self.world.data["planets"][self.home]
        self.assertEqual(home["owner_type"], "empty")
        self.assertEqual(home["environment"], before["planets"][self.home]["environment"])
        self.assertEqual(home["rare_trait"], before["planets"][self.home]["rare_trait"])
        self.assertEqual(self.world.db.execute("PRAGMA foreign_key_check").fetchall(), [])
        with self.assertRaises(app.GameError):
            self.world.authenticate(self.old_token)
        self.assertEqual(self.world.authenticate(self.active_token), self.other)
        self.world.close()
        self.world = app.World(self.path, now=START)
        self.assertNotIn(self.pid, self.world.data["players"])
        self.assertEqual(self.world.authenticate(self.active_token), self.other)
        with self.assertRaises(app.GameError):
            self.world.unused_accounts_delete(request, at=START)

    def test_backup_failure_or_transaction_failure_leaves_all_accounts_intact(self):
        request = self.request()
        before = self.snapshot()
        with patch("balance_reset.verified_reset_backup", side_effect=OSError("test disk full")):
            with self.assertRaises(OSError):
                self.world.unused_accounts_delete(request, at=START)
        self.assertEqual(self.snapshot(), before)
        original = self.world._delete_account_data
        def fail_after_deleting(pid):
            original(pid)
            raise RuntimeError("test transaction failure")
        with patch.object(self.world, "_delete_account_data", side_effect=fail_after_deleting):
            with self.assertRaises(RuntimeError):
                self.world.unused_accounts_delete(request, at=START)
        self.assertEqual(self.snapshot(), before)

    def test_normal_player_account_deletion_still_uses_existing_path(self):
        result = self.world.account_delete(self.old_token, PASSWORD, "DELETE ACCOUNT")
        self.assertTrue(result["deleted"])
        self.assertEqual(self.world.authenticate(self.active_token), self.other)

    def test_failure_on_second_selected_account_rolls_back_whole_batch(self):
        self.world.data["players"][self.other]["last_active_at"] = START - 172800
        self.world._save()
        preview = self.preview()
        self.assertEqual(preview["count"], 2)
        before = self.snapshot()
        original = self.world._delete_account_data
        calls = []
        def fail_second(pid):
            original(pid)
            calls.append(pid)
            if len(calls) == 2:
                raise RuntimeError("second account failure")
        with patch.object(self.world, "_delete_account_data", side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.world.unused_accounts_delete(self.request(preview), at=START)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.world.authenticate(self.old_token), self.pid)
        self.assertEqual(self.world.authenticate(self.active_token), self.other)

    def test_credentials_recovery_google_email_and_push_cascade_with_deleted_account(self):
        self.world.db.execute("INSERT INTO google_accounts(subject,player_id) VALUES(?,?)", ("local-google-subject", self.pid))
        self.world.db.execute("INSERT INTO email_accounts(email_key,player_id) VALUES(?,?)", ("local-email-hash", self.pid))
        self.world.db.execute("INSERT INTO account_recovery(player_id,code_hash) VALUES(?,?)", (self.pid, "local-code-hash"))
        session_hash = self.world.db.execute("SELECT token_hash FROM sessions WHERE player_id=?", (self.pid,)).fetchone()[0]
        self.world.db.execute("INSERT INTO google_sessions(token_hash,authenticated_at) VALUES(?,?)", (session_hash, START))
        self.world.db.execute("INSERT INTO email_sessions(token_hash,authenticated_at) VALUES(?,?)", (session_hash, START))
        self.world.db.execute("INSERT INTO push_devices VALUES(?,?,?,?,?,?)", ("local-device", self.pid, session_hash, "local-token", "en", START))
        self.world.db.execute("INSERT INTO push_outbox(device_hash,report_id,player_id,payload,queued_at,next_at) VALUES(?,?,?,?,?,?)",
                              ("local-device", "local-report", self.pid, "{}", START, START))
        self.world.db.execute("INSERT INTO push_return_reminders VALUES(?,?,?,?)", (self.pid, START, "local-notification", START))
        self.world.db.commit()
        self.world.unused_accounts_delete(self.request(), at=START)
        for table in ("google_accounts", "email_accounts", "account_recovery", "sessions", "push_devices", "push_return_reminders"):
            with self.subTest(table=table):
                self.assertIsNone(self.world.db.execute("SELECT 1 FROM " + table + " WHERE player_id=?", (self.pid,)).fetchone())
        self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM push_outbox").fetchone()[0], 0)
        for table in ("google_sessions", "email_sessions"):
            self.assertIsNone(self.world.db.execute("SELECT 1 FROM " + table + " WHERE token_hash=?", (session_hash,)).fetchone())
        self.assertEqual(self.world.db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_api_requires_existing_admin_key_before_both_preview_and_delete(self):
        with patch.dict("os.environ", {"ALIEN_ANNOUNCEMENT_ADMIN_KEY": "test-admin-key-only-for-local-fixtures-123"}):
            server = app.build_server(self.world, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for method in ("GET", "POST"):
                    conn = http.client.HTTPConnection(*server.server_address, timeout=3)
                    conn.request(method, "/api/admin/unused-accounts", body="{}")
                    response = conn.getresponse()
                    self.assertEqual(response.status, 403)
                    response.read()
                    conn.close()
                conn = http.client.HTTPConnection(*server.server_address, timeout=3)
                with patch("accounts.time.time", return_value=START):
                    conn.request("GET", "/api/admin/unused-accounts", headers={
                        "X-AC-Announcement-Key": "test-admin-key-only-for-local-fixtures-123"})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["count"], 1)
                    self.assertEqual(response.getheader("Cache-Control"), "no-store")
                conn.close()
                self.assertEqual(len(self.world.data["players"]), 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
