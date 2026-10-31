"""Real SQLite fixtures for the operator's 72-hour, one-time cleanup."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import accounts
import maintenance_unused_accounts as maintenance
import test_unused_accounts as fixtures


IDLE = 72 * 3600
START = fixtures.START


class StricterUnusedAccountsTests(unittest.TestCase):
    setUp = fixtures.UnusedAccountsTests.setUp
    tearDown = fixtures.UnusedAccountsTests.tearDown
    snapshot = fixtures.UnusedAccountsTests.snapshot

    def preview(self):
        return self.world.unused_accounts_preview(at=START, idle_seconds=IDLE)

    def request(self, preview):
        return {"preview_id": preview["preview_id"], "count": preview["count"],
                "confirmation": accounts.UNUSED_CONFIRMATION}

    def test_exact_72_hour_boundary_and_default_policy_unchanged(self):
        for age, eligible in ((IDLE, True), (IDLE - .001, False), (IDLE + 1, True),
                              (60 * 3600, False)):
            with self.subTest(age=age):
                self.player["last_active_at"] = START - age
                self.assertEqual(self.preview()["count"], int(eligible))
        self.assertEqual(self.world.unused_accounts_preview(at=START)["count"], 1)
        for invalid in (0, 47 * 3600, True, "259200", 259200.0):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.world.unused_accounts_preview(at=START, idle_seconds=invalid)

    def test_deletes_72_hour_account_but_preserves_60_hour_account(self):
        self.player["last_active_at"] = START - IDLE
        self.world.data["players"][self.other]["last_active_at"] = START - 60 * 3600
        self.world._save()
        preview = self.preview()
        self.assertEqual(preview["idle_seconds"], IDLE)
        self.assertEqual([p["id"] for p in preview["candidates"]], [self.pid])
        result = self.world.unused_accounts_delete(self.request(preview), at=START)
        self.assertEqual(result["deleted"], 1)
        self.assertTrue(result["backup"].startswith("before-unused-72h-"))
        self.assertIn(self.other, self.world.data["players"])

    def test_recorded_72_hour_requirement_is_revalidated_before_delete(self):
        self.player["last_active_at"] = START - IDLE
        preview = self.preview()
        self.player["last_active_at"] = START - 60 * 3600
        self.world._save()
        before = self.snapshot()
        with self.assertRaises(app.GameError):
            self.world.unused_accounts_delete(self.request(preview), at=START,
                                              operation_id="must-not-commit")
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn("must-not-commit", self.world.data.get("unused_account_operations", {}))

    def test_operator_operation_is_durable_and_cannot_delete_a_new_batch_on_restart(self):
        self.player["last_active_at"] = START - IDLE
        result = maintenance.cleanup(self.world, idle_seconds=IDLE,
            operation_id="local-72h-once", apply=True, at=START)
        self.assertTrue(result["verified"])
        self.assertEqual((result["accounts_before"], result["accounts_after"]), (2, 1))
        self.world.close()
        self.world = app.World(self.path, now=START)
        self.world.data["players"][self.other]["last_active_at"] = START - IDLE
        self.world._save()
        before = self.snapshot()
        repeated = maintenance.cleanup(self.world, idle_seconds=IDLE,
            operation_id="local-72h-once", apply=True, at=START)
        self.assertTrue(repeated["already_completed"])
        self.assertEqual(self.snapshot(), before)
        self.assertIn(self.other, self.world.data["players"])

    def test_failed_batch_rolls_back_operation_marker_with_deletion(self):
        self.player["last_active_at"] = START - IDLE
        self.world._save()
        before = self.snapshot()
        original = self.world._delete_account_data
        def fail(pid):
            original(pid)
            raise RuntimeError("fixture failure after account deletion")
        with patch.object(self.world, "_delete_account_data", side_effect=fail):
            with self.assertRaises(RuntimeError):
                maintenance.cleanup(self.world, idle_seconds=IDLE,
                    operation_id="local-rollback", apply=True, at=START)
        self.assertEqual(self.snapshot(), before)

    def test_empty_operation_also_remains_one_time(self):
        result = maintenance.cleanup(self.world, idle_seconds=IDLE,
            operation_id="local-empty", apply=True, at=START)
        self.assertEqual(result["deleted"], 0)
        self.player["last_active_at"] = START - IDLE
        self.world._save()
        repeated = maintenance.cleanup(self.world, idle_seconds=IDLE,
            operation_id="local-empty", apply=True, at=START)
        self.assertTrue(repeated["already_completed"])
        self.assertEqual(repeated["deleted"], 0)
        self.assertIn(self.pid, self.world.data["players"])

    def test_preview_and_missing_operation_id_cannot_delete_accounts(self):
        self.player["last_active_at"] = START - IDLE
        self.world._save()
        before = self.snapshot()
        preview = maintenance.cleanup(self.world, idle_seconds=IDLE, at=START)
        self.assertTrue(preview["dry_run"])
        self.assertEqual(preview["eligible"], 1)
        with self.assertRaises(ValueError):
            maintenance.cleanup(self.world, idle_seconds=IDLE, apply=True, at=START)
        self.assertEqual(self.snapshot(), before)

    def test_offline_cli_commits_verifies_and_retries_without_another_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "private_test.sqlite3"
            now = time.time()
            world = app.World(db, now=now)
            old = world.register("Old CLI fixture", fixtures.PASSWORD)["state"]["player"]["id"]
            recent = world.register("Recent CLI fixture", fixtures.PASSWORD)["state"]["player"]["id"]
            world.data["players"][old]["last_active_at"] = now - IDLE - 1
            world.data["players"][recent]["last_active_at"] = now - 60 * 3600
            world.close()
            command = [sys.executable, str(Path(maintenance.__file__).resolve()),
                       "--local-data", directory, "--apply", "--operation-id", "cli-once"]
            first = subprocess.run(command, capture_output=True, text=True, check=True)
            result = json.loads(next(line.split(" ", 1)[1] for line in first.stdout.splitlines()
                                     if line.startswith("UNUSED_ACCOUNT_CLEANUP_RESULT ")))
            self.assertEqual(result["deleted"], 1)
            self.assertTrue(result["persisted"])
            subprocess.run(command, capture_output=True, text=True, check=True)
            with sqlite3.connect(db) as connection:
                self.assertEqual(connection.execute("SELECT id FROM accounts").fetchall(), [(recent,)])


if __name__ == "__main__":
    unittest.main()

