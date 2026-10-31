"""Production-launch wipe: durable backup, rollback and exactly-once behavior."""
import copy
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from app import GameError, World, blank_ships, build_server
from balance_reset import verified_reset_backup
from launch_reset import ACCOUNT_TABLES, LAUNCH_RESET_ID


START = 1_900_000_000.0
PASSWORD = "launch-test-password"


class LaunchResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "world.sqlite3"
        self.world = World(str(self.path), now=START)

    def tearDown(self):
        if self.world is not None:
            self.world.close()
        self.tmp.cleanup()

    def sql_snapshot(self, connection=None):
        connection = self.world.db if connection is None else connection
        result = {}
        for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            quoted = '"' + name.replace('"', '""') + '"'
            width = len(connection.execute(f"PRAGMA table_info({quoted})").fetchall())
            order = ",".join(str(i + 1) for i in range(width))
            result[name] = connection.execute(f"SELECT * FROM {quoted} ORDER BY {order}").fetchall()
        return result

    def snapshot(self):
        return copy.deepcopy(self.world.data), self.sql_snapshot()

    def make_legacy_world(self):
        self.legacy = self.world.register("Previous Empire", PASSWORD)
        self.google = self.world.google_complete("verified-google-subject", "Previous Google")
        self.legacy_id = self.legacy["state"]["player"]["id"]
        self.google_id = self.google["state"]["player"]["id"]
        self.recovery = self.world.account_recovery_code(self.legacy["token"], PASSWORD)["recovery_code"]
        public = self.world.db.execute("INSERT INTO chat_messages(sender,body,created,request_id) VALUES(?,?,?,?)",
            (self.legacy_id, "Previous global message", START, "previous-global")).lastrowid
        self.world.db.execute("INSERT INTO chat_messages(sender,recipient,body,created,request_id) VALUES(?,?,?,?,?)",
            (self.legacy_id, self.google_id, "Previous private message", START, "previous-private"))
        self.world.db.execute("INSERT INTO chat_blocks VALUES(?,?)", (self.google_id, self.legacy_id))
        self.world.db.execute("INSERT INTO chat_reports VALUES(?,?,?)", (self.google_id, public, START))
        self.world.db.execute("INSERT INTO chat_mutes VALUES(?,?)", (self.legacy_id, START + 50))
        self.world.data["players"][self.legacy_id]["subscription"] = {
            "enable_queue_planning": True, "starts_at": START - 1, "expires_at": START + 1000}
        self.world._owned(self.legacy_id)["ships"]["frigate"] = 99
        self.world.data["fleets"]["old-fleet"] = {
            "id": "old-fleet", "owner_id": self.legacy_id,
            "origin_id": self.world._owned(self.legacy_id)["id"],
            "target_id": self.world._owned(self.google_id)["id"],
            "mission": "scout", "status": "outbound", "ships": {**blank_ships(), "scout": 2},
            "cargo": {"metal": 0, "crystal": 0, "fuel": 0}, "swarm_crystals": 0,
            "seconds": 50, "arrives_at": START + 50}
        self.world.data.pop("launch_reset_id")
        self.world._save()

    def reopen(self):
        self.world.close()
        self.world = None
        self.world = World(str(self.path), now=START)

    def test_fresh_world_marker_preserves_new_account_on_restart(self):
        result = self.world.register("Fresh Empire", PASSWORD)
        player_id = result["state"]["player"]["id"]
        self.assertEqual(self.world.data["launch_reset_id"], LAUNCH_RESET_ID)
        home = self.world._owned(player_id)
        self.assertEqual(home["ships"], blank_ships())
        self.assertEqual(self.world._galaxy_id(home), "g1")
        self.assertEqual(home["resources"], {"metal": 500.0, "crystal": 500.0, "fuel": 0.0})
        self.assertEqual(self.world._player(player_id)["protected_until"], START + 3 * 86400)
        self.reopen()
        self.assertEqual(self.world.authenticate(result["token"]), player_id)
        self.assertEqual(self.world._owned(player_id)["ships"], blank_ships())
        self.assertEqual(self.world._player(player_id)["protected_until"], START + 3 * 86400)
        self.assertFalse((self.path.parent / "reset-backups").exists())

    def test_legacy_reset_backs_up_all_data_cascades_once_and_allows_same_google_to_start_again(self):
        self.make_legacy_world()
        before = self.sql_snapshot()
        self.reopen()
        self.assertEqual(self.world.data["launch_reset_id"], LAUNCH_RESET_ID)
        self.assertEqual(self.world.data["players"], {})
        self.assertEqual(self.world.data["fleets"], {})
        self.assertEqual(self.world.data["launch_reset_summary"]["removed_accounts"], 2)
        self.assertEqual(self.world.data["launch_reset_summary"]["removed_chat_messages"], 2)
        self.assertEqual(self.world.data["launch_reset_summary"]["removed_active_queue_entitlements"], 1)
        for table in ACCOUNT_TABLES:
            self.assertEqual(self.world.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)
        self.assertEqual(self.world.db.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(self.world.db.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
        backups = list((self.path.parent / "reset-backups").glob("*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(backups[0]) as connection:
            self.assertEqual(self.sql_snapshot(connection), before)
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        for token in (self.legacy["token"], self.google["token"]):
            with self.assertRaises(GameError):
                self.world.authenticate(token)
        with self.assertRaises(GameError):
            self.world.login("Previous Empire", PASSWORD)
        with self.assertRaises(GameError):
            self.world.recover_account("Previous Empire", self.recovery, "next-password-test")
        result = self.world.google_complete("verified-google-subject", "Previous Google")
        new_id = result["state"]["player"]["id"]
        self.assertNotEqual(new_id, self.google_id)
        self.assertEqual(self.world._owned(new_id)["ships"], blank_ships())
        self.assertEqual(self.world._galaxy_id(self.world._owned(new_id)), "g1")
        self.assertFalse(self.world._queue_entitlement(self.world._player(new_id))["queue_planning_active"])
        self.reopen()
        self.assertEqual(self.world.authenticate(result["token"]), new_id)
        self.assertEqual(len(list((self.path.parent / "reset-backups").glob("*.sqlite3"))), 1)


    def test_new_beginning_preserves_latest_administrator_announcement(self):
        self.make_legacy_world()
        announcement = {
            "published": {"category": "update",
                          "title": "New world. New beginning.",
                          "body": "Your colonies can be captured by other players if have no defense"},
            "draft": {"category": "", "title": "New world. New beginning.", "body": ""},
            "revision": 7,
            "updated_at": START + 100,
        }
        self.world.data["login_announcement"] = copy.deepcopy(announcement)
        self.world._save()
        self.reopen()
        self.assertEqual(self.world.data["launch_reset_id"], LAUNCH_RESET_ID)
        self.assertEqual(self.world.data["login_announcement"], announcement)
        self.assertFalse(self.world.data["players"])
        self.assertFalse(self.world.data["fleets"])
        self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 0)
        backups = list((self.path.parent / "reset-backups").glob("*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(backups[0]) as pre_reset:
            snapshot = json.loads(pre_reset.execute("SELECT body FROM snapshot WHERE id=1").fetchone()[0])
            self.assertEqual(snapshot["login_announcement"], announcement)
            self.assertEqual(len(snapshot["players"]), 2)
        # A subsequent restart must not reset accounts created in the fresh world.
        new_account = self.world.register("Next Empire", PASSWORD)
        player_id = new_account["state"]["player"]["id"]
        self.reopen()
        self.assertEqual(self.world.authenticate(new_account["token"]), player_id)

    def test_backup_failure_never_changes_accounts_or_snapshot(self):
        self.make_legacy_world()
        before = self.snapshot()
        with patch("launch_reset.verified_reset_backup", side_effect=OSError("backup unavailable")):
            with self.assertRaises(OSError):
                self.world._apply_launch_reset()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.world.authenticate(self.legacy["token"]), self.legacy_id)

    def test_failed_snapshot_write_rolls_back_sql_and_memory_and_can_retry(self):
        self.make_legacy_world()
        before = self.snapshot()
        with patch.object(self.world, "_save", side_effect=sqlite3.OperationalError("disk full")):
            with self.assertRaises(GameError) as raised:
                self.world._apply_launch_reset()
        self.assertEqual(raised.exception.status, 503)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.world.authenticate(self.google["token"]), self.google_id)
        self.assertTrue(self.world._apply_launch_reset())
        self.assertFalse(self.world._apply_launch_reset())
        self.assertEqual(self.world.data["players"], {})

    def test_failed_sql_delete_rolls_back_sessions_and_preserves_world(self):
        self.make_legacy_world()
        self.world.db.execute("CREATE TRIGGER prevent_account_delete BEFORE DELETE ON accounts BEGIN SELECT RAISE(ABORT, 'blocked'); END")
        self.world.db.commit()
        before = self.snapshot()
        with self.assertRaises(GameError):
            self.world._apply_launch_reset()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.world.authenticate(self.google["token"]), self.google_id)

    def test_backup_checks_future_tables_and_rejects_invalid_foreign_keys(self):
        self.world.db.executescript("""CREATE TABLE future_account_data(
            player_id TEXT REFERENCES accounts(id), payload BLOB, counter INTEGER);
            INSERT INTO future_account_data VALUES(NULL, X'0012FF', 17);""")
        self.world.db.commit()
        path = verified_reset_backup(self.world.db, self.path, reset_id="future-table-test")
        with sqlite3.connect(path) as backup:
            self.assertEqual(self.sql_snapshot(backup), self.sql_snapshot())
        self.world.db.execute("PRAGMA foreign_keys=OFF")
        self.world.db.execute("INSERT INTO future_account_data VALUES('missing-player', X'AA', 18)")
        self.world.db.commit()
        self.world.db.execute("PRAGMA foreign_keys=ON")
        with self.assertRaises(sqlite3.DatabaseError):
            verified_reset_backup(self.world.db, self.path, reset_id="invalid-fk-test")
        self.assertEqual(list((self.path.parent / "reset-backups").glob("before-invalid-fk-test-*")), [])

    def test_health_exposes_only_fixed_epoch_and_no_reset_details(self):
        server = build_server(self.world, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            connection.request("GET", "/health")
            response = connection.getresponse()
            result = json.loads(response.read())
            connection.close()
            self.assertEqual(response.status, 200)
            self.assertEqual(set(result), {"ok", "version", "world_epoch"})
            self.assertEqual(result["world_epoch"], LAUNCH_RESET_ID)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
