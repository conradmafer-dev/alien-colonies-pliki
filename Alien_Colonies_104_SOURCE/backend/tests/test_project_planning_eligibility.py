"""Free UI offers use hard eligibility without granting paid queue access."""
import copy
import unittest

from app import World, GameError, RESOURCES


class ProjectPlanningEligibility(unittest.TestCase):
    def setUp(self):
        self.world = World(":memory:", now=1900000000.0)
        self.addCleanup(self.world.close)
        self.player_id = self.world.register("Project UI Test", "queue-ui-password-123")["state"]["player"]["id"]
        self.world.action(self.player_id, {"type": "choose_race", "race_id": "zetans"})
        self.planet = self.world._owned(self.player_id)
        self.planet["resources"] = dict.fromkeys(RESOURCES, 10000000.0)
        self.planet["buildings"].update(lab=2, shipyard=2)

    def entry(self, group, key):
        return next(item for item in self.world.state(self.player_id)["catalog"][group] if item["key"] == key)

    def test_free_busy_project_offers_planning_without_granting_mutation(self):
        self.world.action(self.player_id, {"type": "build", "key": "metal_mine"})
        self.planet["resources"] = dict.fromkeys(RESOURCES, 0.0)
        item = self.entry("buildings", "crystal_mine")
        self.assertFalse(item["enabled"])
        self.assertTrue(item["planning_eligible"])
        self.assertEqual(item["planning_eligibility_reason"], "")
        self.assertFalse(item["planning_enabled"])
        before = copy.deepcopy(self.world.data)
        with self.assertRaises(GameError) as caught:
            self.world.action(self.player_id, {"type": "plan_project", "kind": "build", "key": "crystal_mine"})
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(before, self.world.data)

    def test_hard_requirements_are_visible_to_free_and_paid_players(self):
        self.planet["buildings"]["shipyard"] = 0
        free = self.entry("ships", "scout")
        self.assertFalse(free["planning_eligible"])
        self.assertTrue(free["planning_eligibility_reason"])
        self.world._player(self.player_id)["subscription"] = {"enable_queue_planning": True, "starts_at": self.world.now - 1, "expires_at": self.world.now + 1000}
        paid = self.entry("ships", "scout")
        self.assertFalse(paid["planning_enabled"])
        self.assertEqual(paid["planning_reason"], paid["planning_eligibility_reason"])

    def test_paid_catalog_and_mutation_share_the_same_hard_checks(self):
        self.world._player(self.player_id)["subscription"] = {"enable_queue_planning": True, "starts_at": self.world.now - 1, "expires_at": self.world.now + 1000}
        self.world.action(self.player_id, {"type": "build", "key": "metal_mine"})
        item = self.entry("buildings", "crystal_mine")
        self.assertTrue(item["planning_eligible"])
        self.assertTrue(item["planning_enabled"])
        self.world.action(self.player_id, {"type": "plan_project", "kind": "build", "key": "crystal_mine"})
        self.assertEqual(self.world._player(self.player_id)["planned_orders"][0]["key"], "crystal_mine")


if __name__ == "__main__":
    unittest.main()
