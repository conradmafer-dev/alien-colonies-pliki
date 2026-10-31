import copy
import json
from pathlib import Path
import sqlite3
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from server.main import GameError, build_server
from tests.world_fixture import LocalTestWorld as World
from server.backups import SQLiteBackups


class StorageAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "galaxy.sqlite3"
        self.world = World(self.path, now=1000)
        self.registration = self.world.register("Testowy", "test-pass-123")
        self.token = self.registration["token"]
        self.player = self.world.authenticate(self.token)

    def tearDown(self):
        self.world.db.execute("PRAGMA query_only=OFF")
        self.world.close()
        self.temp.cleanup()

    def snapshot(self):
        return json.loads(self.world.db.execute("SELECT body FROM snapshot").fetchone()[0])

    def readonly(self):
        self.world.db.execute("PRAGMA query_only=ON")

    def writable(self):
        self.world.db.execute("PRAGMA query_only=OFF")

    def assert_unavailable(self, operation):
        with self.assertRaises(GameError) as error:
            operation()
        self.assertEqual(error.exception.status, 503)
        self.assertFalse(self.world.write_healthy)
        self.assertNotIn(str(self.path), str(error.exception))

    def test_failed_action_restores_resources_queue_and_replay_then_retries_once(self):
        before = copy.deepcopy(self.world.data)
        payload = {"type": "build", "key": "metal_mine", "request_id": "same-id"}
        self.readonly()
        self.assert_unavailable(lambda: self.world.action(self.player, payload))
        self.assertEqual(self.world.data, before)
        self.assertEqual(self.snapshot(), before)
        self.writable()
        first = self.world.action(self.player, payload)
        resources = first["state"]["resources"]
        replay = self.world.action(self.player, payload)
        self.assertEqual(len(replay["state"]["queue"]), 1)
        self.assertEqual(replay["state"]["resources"], resources)
        self.assertTrue(self.world.write_healthy)

    def test_failed_register_restores_planet_and_account(self):
        before = copy.deepcopy(self.world.data)
        self.readonly()
        self.assert_unavailable(lambda: self.world.register("NowyGracz", "test-pass-123"))
        self.assertEqual(self.world.data, before)
        self.assertIsNone(self.world.db.execute("SELECT id FROM accounts WHERE name_key='nowygracz'").fetchone())
        self.writable()
        self.assertTrue(self.world.register("NowyGracz", "test-pass-123")["ok"])

    def test_login_and_logout_rollback_sql_sessions(self):
        before = self.world.db.execute("SELECT * FROM sessions").fetchall()
        self.readonly()
        self.assert_unavailable(lambda: self.world.login("Testowy", "test-pass-123"))
        self.assertEqual(self.world.db.execute("SELECT * FROM sessions").fetchall(), before)
        self.assert_unavailable(lambda: self.world.logout(self.token))
        self.assertEqual(self.world.authenticate(self.token), self.player)
        self.writable()
        self.world.logout(self.token)
        with self.assertRaises(GameError):
            self.world.authenticate(self.token)

    def test_sql_deletes_roll_back_when_snapshot_write_fails_after_success(self):
        # Covers failure after a successful SQL mutation, not only the first SQL statement.
        before = copy.deepcopy(self.world.data)
        with patch.object(self.world, "_save", side_effect=sqlite3.OperationalError("private disk path")):
            self.assert_unavailable(lambda: self.world.logout(self.token))
        self.assertEqual(self.world.authenticate(self.token), self.player)
        self.assertEqual(self.world.data, before)
        self.assertEqual(self.snapshot(), before)

    def test_failed_race_selection_rolls_back_racial_catalog_and_guide(self):
        before = copy.deepcopy(self.world.data)
        payload = {"type": "choose_race", "race_id": "symbionts", "request_id": "race-id"}
        self.readonly()
        self.assert_unavailable(lambda: self.world.action(self.player, payload))
        self.assertEqual(self.world.data, before)
        self.writable()
        self.assertEqual(self.world.action(self.player, payload)["state"]["player"]["race_id"], "symbionts")

    def test_failed_advance_replays_elapsed_time_and_completion_without_duplicate_rewards(self):
        self.world.action(self.player, {"type": "build", "key": "metal_mine"})
        before = copy.deepcopy(self.world.data)
        end = self.world.state(self.player)["queue"][0]["ends_at"]
        old_now = self.world.now
        self.readonly()
        self.assert_unavailable(lambda: self.world.advance(end + 60))
        self.assertEqual(self.world.data, before)
        self.assertEqual(self.world.now, old_now)
        self.writable()
        self.world.advance(end + 60)
        state = self.world.state(self.player)
        self.assertEqual(state["buildings"]["metal_mine"], 2)
        self.assertFalse(state["queue"])
        self.world.advance(end + 60)
        replay = self.world.state(self.player)
        self.assertEqual(replay["resources"], state["resources"])
        self.assertEqual(replay["reports"], state["reports"])
        self.assertTrue(self.world.write_healthy)

    def test_health_503_after_write_error_and_200_after_recovery(self):
        server = build_server(self.world, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/health"
        try:
            self.readonly()
            self.assert_unavailable(lambda: self.world.advance(1100))
            with self.assertRaises(HTTPError) as failure:
                urlopen(url)
            self.assertEqual(failure.exception.code, 503)
            self.assertNotIn(str(self.path), failure.exception.read().decode())
            self.writable()
            self.world.advance(1100)
            with urlopen(url) as response:
                self.assertEqual(response.status, 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_backup_rotation_interval_and_real_restore_accounts_and_world(self):
        manager = SQLiteBackups(self.path, interval=3600, retention=2)
        for old in manager.directory.glob("galaxy-*.sqlite3"):
            old.unlink()
        first = manager.maybe_create(self.world.db, clock=0)
        self.assertIsNotNone(first)
        self.assertIsNone(manager.maybe_create(self.world.db, clock=3599))
        self.world.action(self.player, {"type": "choose_race", "race_id": "zetans"})
        second = manager.maybe_create(self.world.db, clock=3600)
        third = manager.maybe_create(self.world.db, clock=7200)
        self.assertEqual(len(list(manager.directory.glob("galaxy-*.sqlite3"))), 2)
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())
        # Restore from the actual SQLite backup, not a hand-built snapshot.
        restored = World(third, now=self.world.now)
        try:
            self.assertEqual(restored.authenticate(self.token), self.player)
            self.assertEqual(restored.state(self.player)["player"]["race_id"], "zetans")
            self.assertTrue(restored.login("Testowy", "test-pass-123")["ok"])
        finally:
            restored.close()

    def test_backup_failure_keeps_live_save_and_retries_later(self):
        manager = SQLiteBackups(self.path)
        before = self.snapshot()
        with patch("server.backups.Path.mkdir", side_effect=OSError("private path")):
            self.assertIsNone(manager.maybe_create(self.world.db, clock=0))
        self.assertFalse(manager.healthy)
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(manager.maybe_create(self.world.db, clock=59))
        self.assertIsNotNone(manager.maybe_create(self.world.db, clock=60))
        self.assertTrue(manager.healthy)

    def test_wal_backups_close_every_handle_and_restore_without_sidecars(self):
        manager = SQLiteBackups(self.path, retention=2)
        self.world.db.execute("PRAGMA wal_autocheckpoint=0")
        self.world.db.execute("CREATE TABLE backup_marker (n INTEGER)")
        self.world.db.commit()
        retained_connections = []
        connect = sqlite3.connect

        def track_connection(*args, **kwargs):
            connection = connect(*args, **kwargs)
            # Keep a strong reference: garbage collection cannot hide missing close.
            retained_connections.append(connection)
            return connection

        with patch("server.backups.sqlite3.connect", side_effect=track_connection):
            for number in range(8):
                self.world.db.execute("INSERT INTO backup_marker VALUES(?)", (number,))
                self.world.db.commit()
                self.assertGreater(Path(str(self.path) + "-wal").stat().st_size, 0)
                final_copy = manager.maybe_create(self.world.db, force=True)
                self.assertIsNotNone(final_copy)
        self.assertEqual(len(retained_connections), 8)
        for connection in retained_connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")
        files = list(manager.directory.iterdir())
        self.assertEqual(len(files), 2)
        self.assertTrue(all(path.suffix == ".sqlite3" for path in files))
        # Copy only the main file, so an unnoticed dependency on a WAL cannot pass.
        standalone = Path(self.temp.name) / "restored-alone.sqlite3"
        shutil.copyfile(final_copy, standalone)
        restored = sqlite3.connect(f"file:{standalone}?mode=ro&immutable=1", uri=True)
        try:
            self.assertEqual(restored.execute("SELECT n FROM backup_marker ORDER BY n").fetchall(), [(n,) for n in range(8)])
            self.assertEqual(restored.execute("PRAGMA journal_mode").fetchone(), ("delete",))
            self.assertEqual(restored.execute("PRAGMA quick_check").fetchone(), ("ok",))
        finally:
            restored.close()
        self.assertEqual(self.world.db.execute("PRAGMA journal_mode").fetchone(), ("wal",))

    def test_backup_rename_failure_closes_handle_and_removes_all_temporary_files(self):
        manager = SQLiteBackups(self.path)
        connect = sqlite3.connect
        retained_connections = []

        def track_connection(*args, **kwargs):
            connection = connect(*args, **kwargs)
            retained_connections.append(connection)
            return connection

        before = self.snapshot()
        with patch("server.backups.sqlite3.connect", side_effect=track_connection), patch("server.backups.os.replace", side_effect=OSError("simulated rename failure")):
            self.assertIsNone(manager.maybe_create(self.world.db, force=True))
        self.assertEqual(len(retained_connections), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            retained_connections[0].execute("SELECT 1")
        self.assertFalse(list(manager.directory.glob("*.part*")))
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
