"""Milestone, durable display claims, and unchanged subscription entitlements."""
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import review_invite
import subscription_invite

NOW = 1_920_000_000.0
PASSWORD = "subscription-invite-test-password"


class SubscriptionInvitationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = str(Path(self.tmp.name) / "world.sqlite3")
        self.world = app.World(self.db_path, now=NOW)
        self.addCleanup(lambda: self.world.close())
        registered = self.world.register("TrialPilot", PASSWORD)
        self.owner = registered["state"]["player"]["id"]
        self.player = self.world._player(self.owner)
        self.planet = self.world._owned(self.owner)
        self.world.data["alien"]["next_expansion_at"] = NOW + 365 * 86400

    def qualify(self):
        """Seed authoritative event history for tests of claims, not counting."""
        for _ in range(subscription_invite.MILESTONE):
            review_invite.record_completed_build(self.player)

    def prompt(self, owner=None):
        return self.world.state(owner or self.owner)["subscription_prompt"]

    def claim(self, nonce="trial-request-device-a", **extra):
        return self.world.action(self.owner, {
            "type": "subscription_prompt", "choice": "show",
            "planet_id": self.planet["id"], "request_id": nonce, **extra})

    def buy_and_finish(self, planet=None, key="metal_mine"):
        planet = self.planet if planet is None else planet
        planet["resources"] = dict.fromkeys(app.RESOURCES, 1_000_000.0)
        self.world.action(self.owner, {
            "type": "build", "key": key, "planet_id": planet["id"]})
        task = next(task for task in planet["queue"] if task["kind"] == "build")
        self.world.advance(task["ends_at"] + 1)

    def grant_subscription(self):
        self.player["subscription"] = {
            "enable_queue_planning": True,
            "starts_at": self.world.now - 1, "expires_at": self.world.now + 3600}

    def test_ten_completions_include_repeated_upgrades_but_not_start_or_cancel(self):
        self.planet["resources"] = dict.fromkeys(app.RESOURCES, 1_000_000.0)
        self.world.action(self.owner, {"type": "build", "key": "metal_mine"})
        self.assertEqual(self.prompt()["completed_builds"], 0)
        self.world.action(self.owner, {
            "type": "cancel_project", "queue_id": self.planet["queue"][0]["id"]})
        self.assertEqual(self.prompt()["completed_builds"], 0)
        for expected in range(1, 11):
            self.buy_and_finish()
            row = self.prompt()
            self.assertEqual(row["completed_builds"], expected)
            self.assertEqual(row["eligible"], expected >= 10)
        self.assertEqual(self.planet["buildings"]["metal_mine"], 10)
        self.assertEqual(self.prompt()["milestone"], 10)

    def test_progress_is_empire_wide_and_independent_of_dismissed_review(self):
        for _ in range(9):
            self.buy_and_finish()
        self.assertFalse(self.prompt()["eligible"])
        self.world.action(self.owner, {"type": "review_prompt", "choice": "dismiss"})
        second = next(p for p in self.world.data["planets"].values()
                      if p["owner_type"] == "empty")
        second.update(owner_type="player", owner_id=self.owner)
        self.buy_and_finish(second, key="crystal_mine")
        self.assertTrue(self.prompt()["eligible"])
        self.assertTrue(self.world.state(self.owner)["review_prompt"]["disabled"])

    def test_research_and_ship_completions_do_not_count(self):
        self.world.action(self.owner, {"type": "choose_race", "race_id": "zetans"})
        self.planet["buildings"].update(lab=2, shipyard=2)
        self.planet["resources"] = dict.fromkeys(app.RESOURCES, 1_000_000.0)
        self.world.action(self.owner, {"type": "research", "key": "weapons"})
        self.world.action(self.owner, {"type": "ship", "key": "scout"})
        self.world.advance(max(task["ends_at"] for task in self.planet["queue"]) + 1)
        self.assertEqual(self.player["research"]["weapons"], 1)
        self.assertEqual(self.planet["ships"]["scout"], 1)
        self.assertEqual(self.prompt()["completed_builds"], 0)

    def test_public_state_is_read_only_and_does_not_guess_old_builds(self):
        self.player.pop("review_invitation")
        self.planet["buildings"]["metal_mine"] = 20
        before = copy.deepcopy(self.player)
        self.assertEqual(subscription_invite.public(self.player), {
            "eligible": False, "completed_builds": 0, "milestone": 10,
            "shown": False, "claim_request_id": ""})
        self.assertEqual(self.player, before)
        self.assertNotIn("subscription_invitation", self.player)

    def test_claim_before_threshold_or_without_valid_nonce_does_not_consume_offer(self):
        for completed in (0, 6, 9):
            while self.prompt()["completed_builds"] < completed:
                review_invite.record_completed_build(self.player)
            with self.subTest(completed=completed):
                self.assertFalse(self.prompt()["eligible"])
                with self.assertRaises(app.GameError):
                    self.claim()
                self.assertNotIn("subscription_invitation", self.player)
        review_invite.record_completed_build(self.player)
        self.assertEqual(self.prompt()["completed_builds"], 10)
        self.assertTrue(self.prompt()["eligible"])
        for invalid in (None, "", True, "x" * 101):
            with self.subTest(nonce=invalid), self.assertRaises(app.GameError):
                self.claim(nonce=invalid)
        with self.assertRaises(app.GameError):
            self.claim(choice="later")
        self.assertTrue(self.prompt()["eligible"])

    def test_competing_devices_have_only_one_claim_and_same_nonce_is_idempotent(self):
        self.qualify()
        barrier = threading.Barrier(2)
        def request(nonce):
            barrier.wait(timeout=3)
            return nonce, self.claim(nonce)["state"]["subscription_prompt"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(request, ["trial-device-a", "trial-device-b"]))
        self.assertEqual(sum(row["claim_request_id"] == nonce
                             for nonce, row in results), 1)
        winner = self.prompt()["claim_request_id"]
        saved = copy.deepcopy(self.player["subscription_invitation"])
        replay = self.claim(winner)["state"]["subscription_prompt"]
        self.assertEqual(replay["claim_request_id"], winner)
        self.assertFalse(replay["eligible"])
        self.assertTrue(replay["shown"])
        self.assertEqual(self.player["subscription_invitation"], saved)

    def test_claim_survives_restart_new_device_and_action_cache_eviction(self):
        self.qualify()
        self.claim("original-device")
        self.player["requests"].clear()
        self.world.close()
        self.world = app.World(self.db_path, now=self.world.now)
        self.player = self.world._player(self.owner)
        self.planet = self.world._owned(self.owner)
        self.assertFalse(self.prompt()["eligible"])
        replay = self.claim("original-device")["state"]["subscription_prompt"]
        self.assertEqual(replay["claim_request_id"], "original-device")
        new_device = self.claim("after-reinstall")["state"]["subscription_prompt"]
        self.assertNotEqual(new_device["claim_request_id"], "after-reinstall")
        self.buy_and_finish()
        self.assertFalse(self.prompt()["eligible"])

    def test_active_subscribers_cannot_claim_or_reuse_pre_purchase_response(self):
        self.qualify()
        self.grant_subscription()
        self.assertFalse(self.prompt()["eligible"])
        with self.assertRaises(app.GameError):
            self.claim()
        self.assertNotIn("subscription_invitation", self.player)
        self.player.pop("subscription")
        self.claim()
        self.grant_subscription()
        replay = self.claim()["state"]
        self.assertTrue(replay["premium"]["queue_planning_active"])
        self.assertEqual(replay["subscription_prompt"]["claim_request_id"], "")
        self.player.pop("subscription")
        self.assertFalse(self.prompt()["eligible"])

    def test_claim_does_not_grant_benefits_spend_resources_or_count_as_play(self):
        self.qualify()
        self.player["last_active_at"] = self.world.now - 300
        activity = self.player["last_active_at"]
        resources = copy.deepcopy(self.planet["resources"])
        before = copy.deepcopy(self.player["review_invitation"])
        response = self.claim()
        self.assertEqual(response["message"], "")
        self.assertEqual(self.player["last_active_at"], activity)
        self.assertEqual(self.planet["resources"], resources)
        self.assertEqual(self.player["review_invitation"], before)
        self.assertNotIn("subscription", self.player)
        self.assertFalse(response["state"]["premium"]["queue_planning_active"])

    def test_claim_and_progress_are_isolated_to_authenticated_player(self):
        self.qualify()
        other = self.world.register("OtherTrialPilot", PASSWORD)["state"]["player"]["id"]
        self.assertFalse(self.prompt(other)["eligible"])
        with self.assertRaises(app.GameError):
            self.world.action(other, {
                "type": "subscription_prompt", "choice": "show",
                "planet_id": self.planet["id"], "request_id": "foreign-device"})
        self.assertTrue(self.prompt()["eligible"])
        self.claim()
        self.assertFalse(self.prompt(other)["shown"])

    def test_failed_database_write_rolls_back_display_claim(self):
        self.qualify()
        with patch.object(self.world, "_save", side_effect=OSError("local test disk failure")):
            with self.assertRaises(app.GameError) as error:
                self.claim()
        self.assertEqual(error.exception.status, 503)
        self.assertNotIn("subscription_invitation", self.player)
        self.assertNotIn("trial-request-device-a", self.player["requests"])
        self.assertTrue(self.prompt()["eligible"])
        self.assertTrue(self.claim()["state"]["subscription_prompt"]["shown"])


if __name__ == "__main__":
    unittest.main()
