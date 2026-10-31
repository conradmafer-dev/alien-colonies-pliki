"""Confirmed one-use launcher: local databases only, including replay and expiry."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
import authorized_unused_cleanup as cleanup

START = 1_900_000_000.0


class AuthorizedCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "world.sqlite3"
        self.world = app.World(self.path, now=START)
        result = self.world.register("One use fixture", "local-test-password")
        self.pid = result["state"]["player"]["id"]

    def tearDown(self):
        self.world.close()
        self.temp.cleanup()

    def perform(self, clock=START):
        return cleanup.perform(self.world, as_of=START, operation_id="test-one-use", clock=clock)

    def test_success_is_persisted_and_never_deletes_another_eligible_account_on_restart(self):
        self.world.data["players"][self.pid]["last_active_at"] = START - 172800
        self.world._save()
        result = self.perform()
        self.assertEqual(result["deleted"], 1)
        self.assertTrue((self.path.parent / "reset-backups" / result["backup"]).is_file())
        self.world.close()
        self.world = app.World(self.path, now=START)
        new = self.world.register("Later fixture", "local-test-password")
        new_id = new["state"]["player"]["id"]
        self.world.data["players"][new_id]["last_active_at"] = START - 172800
        again = self.perform(clock=START + 86400)
        self.assertEqual(again["status"], "already_completed")
        self.assertIn(new_id, self.world.data["players"])

    def test_zero_selection_is_also_persisted_and_cannot_widen_later(self):
        result = self.perform()
        self.assertEqual(result["deleted"], 0)
        self.world.close()
        self.world = app.World(self.path, now=START)
        self.world.data["players"][self.pid]["last_active_at"] = START - 172800
        again = self.perform(clock=START + 86400)
        self.assertEqual(again["status"], "already_completed")
        self.assertIn(self.pid, self.world.data["players"])

    def test_fixed_activity_cohort_excludes_players_returning_after_authorization(self):
        self.world.data["players"][self.pid]["last_active_at"] = START + 1
        self.assertEqual(self.perform(clock=START + 2)["deleted"], 0)

    def test_expired_job_refuses_changes_and_missing_epoch_refuses_reset(self):
        before = copy.deepcopy(self.world.data)
        with self.assertRaises(RuntimeError):
            self.perform(clock=START + 3601)
        self.assertEqual(self.world.data, before)
        self.world.data["launch_reset_id"] = "some-other-world"
        before = copy.deepcopy(self.world.data)
        with self.assertRaises(RuntimeError):
            self.perform()
        self.assertEqual(self.world.data, before)

    def test_backup_failure_does_not_mark_operation_complete_or_remove_accounts(self):
        self.world.data["players"][self.pid]["last_active_at"] = START - 172800
        self.world._save()
        with patch("balance_reset.verified_reset_backup", side_effect=OSError("test backup failure")):
            with self.assertRaises(OSError):
                self.perform()
        self.assertIn(self.pid, self.world.data["players"])
        self.assertFalse(self.world.data.get("unused_account_cleanups"))

    def test_new_confirmed_operation_rechecks_a_later_cohort_and_replays_once(self):
        self.world.data["players"][self.pid]["last_active_at"] = START - 172800 + 60
        self.world._save()
        self.assertEqual(self.perform()["deleted"], 0)
        self.world.close()
        self.world = app.World(self.path, now=START + 120)
        result = cleanup.perform(self.world, as_of=START + 120,
                                 operation_id="test-second-confirmed", clock=START + 120)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["remaining_players"], 0)
        self.assertTrue((self.path.parent / "reset-backups" / result["backup"]).is_file())
        self.assertEqual([row["at"] for row in self.world.data["unused_account_cleanups"]],
                         [START, START + 120])
        replay = cleanup.perform(self.world, as_of=START + 120,
                                 operation_id="test-second-confirmed", clock=START + 86400)
        self.assertEqual(replay["status"], "already_completed")
        self.assertEqual(len(self.world.data["unused_account_cleanups"]), 2)


if __name__ == "__main__":
    unittest.main()
