"""Persistent first steps and live mission recommendations for the public build."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from server import onboarding, skill_tree, swarm
from tests.world_fixture import LocalTestWorld as World
from tests.make_progression_fixture import START, advance_live


def completed(state):
    return {step["id"] for step in state["steps"] if step["done"]}


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.world = World(":memory:", speed=10, now=START)
        account = self.world.register("Guide unit", "guide-test-password")
        self.player_id = account["state"]["player"]["id"]
        self.player = self.world.data["players"][self.player_id]
        self.home = self.world.data["planets"][self.player["home_id"]]

    def tearDown(self):
        self.world.close()

    def choose(self, race="zetans"):
        self.world.action(self.player_id, {"type": "choose_race", "race_id": race})

    def view(self, **kwargs):
        return onboarding.public_state(self.world.data, self.player, **kwargs)

    def step(self, ident, **kwargs):
        return next(s for s in self.view(**kwargs)["steps"] if s["id"] == ident)

    def test_no_progress_before_race_even_with_existing_economy(self):
        self.home["buildings"]["metal_mine"] = 3
        for event in onboarding.STEP_IDS:
            self.assertFalse(onboarding.record(self.player, event))
        before = deepcopy(self.player)
        state = self.view()
        self.assertEqual(state["completed_count"], 0)
        self.assertEqual(state["total"], 5)
        self.assertFalse(state["finished"])
        self.assertIsNone(state["current"])
        self.assertEqual(self.player, before)

    def test_first_selected_race_starts_at_zero_and_own_root_is_free(self):
        self.choose()
        state = self.view()
        self.assertEqual(completed(state), set())
        self.assertEqual(state["current"]["id"], "first_building")
        self.assertEqual(state["current"]["target_id"], "metal_mine")
        self.assertEqual(state["current"]["action"], "building")
        self.assertEqual(self.player["skill_nodes"], [skill_tree.ROOTS["zetans"]])

    def test_markers_are_idempotent_and_do_not_reward_or_reset_any_inventory(self):
        self.choose()
        before = deepcopy(self.world.data)
        self.assertFalse(onboarding.record(self.player, "unknown_event"))
        for event in onboarding.STEP_IDS:
            self.assertTrue(onboarding.record(self.player, event))
            self.assertFalse(onboarding.record(self.player, event))
        state = self.view()
        self.assertEqual(state["completed_count"], 5)
        self.assertTrue(state["finished"])
        self.assertIsNone(state["current"])
        after = deepcopy(self.world.data)
        before["players"][self.player_id].pop("onboarding", None)
        after["players"][self.player_id].pop("onboarding", None)
        self.assertEqual(before, after)

    def test_infers_only_verifiable_legacy_facts(self):
        self.choose()
        self.player.pop("onboarding", None)
        self.home["buildings"]["metal_mine"] = 2
        node = next(n for n in skill_tree.public_state("zetans", [], 50)["nodes"] if n["affordable"])
        self.player["skill_nodes"].append(node["id"])
        second = next(p for p in self.world.data["planets"].values() if p["owner_type"] == "empty")
        second.update(owner_id=self.player_id, owner_type="player")
        self.player["swarm_crystals"] = 200
        self.player["reports"] = [{"title": "Raport zwiadu", "text": "Rój Khar"}]
        self.assertEqual(completed(self.view()), {"first_building", "first_skill", "second_colony"})
        # Loss of the underlying current state must not clear historical markers.
        self.home["buildings"]["metal_mine"] = 1
        self.player["skill_nodes"] = [skill_tree.ROOTS["zetans"]]
        second.update(owner_id="", owner_type="empty")
        self.player["swarm_crystals"] = 0
        self.assertEqual(completed(self.view()), {"first_building", "first_skill", "second_colony"})

    def test_unique_building_and_disconnected_skills_do_not_forge_first_steps(self):
        self.choose()
        self.home["buildings"]["echo_observatory"] = 3
        self.player["skill_nodes"] = ["automatons_root", "automatons_core_3", "imaginary_skill"]
        self.assertEqual(completed(self.view()), set())

    def test_recommendation_never_targets_a_player_after_npc_ownership_changes(self):
        self.choose()
        first = self.step("swarm_crystals")["target_id"]
        self.assertTrue(first)
        former = self.world.data["planets"][first]
        former.update(owner_type="player", owner_id=self.player_id)
        state = self.view(recommended_target_id=first)
        for step in state["steps"]:
            if step["action"] in ("scout", "hunt"):
                self.assertNotEqual(step["target_id"], first)
                if step["target_id"]:
                    self.assertEqual(self.world.data["planets"][step["target_id"]]["owner_id"], "khar")
        self.assertNotIn("swarm_scout", completed(state))

    def test_hunt_recommends_stocked_fortress_without_claiming_it_is_weak(self):
        self.choose()
        step = self.step("swarm_crystals")
        self.assertTrue(step["target_id"])
        target = self.world.data["planets"][step["target_id"]]
        self.assertEqual(swarm.kind(target), "hive")
        self.assertTrue(swarm.ready(target))
        self.assertNotIn("słaby", step["description"].lower())
        for planet in self.world.data["planets"].values():
            if planet["owner_id"] == "khar":
                planet["swarm_crystals"] = 0
        self.assertEqual(self.step("swarm_crystals")["target_id"], "")

    def test_live_recommendation_prefers_valid_stocked_fortress(self):
        self.choose()
        candidates = [p for p in self.world.data["planets"].values()
                      if p["owner_id"] == "khar" and p["swarm_crystals"] >= 1]
        requested = candidates[-1]["id"]
        self.assertEqual(self.step("swarm_crystals", recommended_target_id=requested)["target_id"], requested)
        self.world.data["planets"][requested]["owner_type"] = "empty"
        self.assertNotEqual(self.step("swarm_crystals", recommended_target_id=requested)["target_id"], requested)

    def test_crystals_in_returning_fleet_do_not_count_before_delivery(self):
        self.choose()
        self.world.data["fleets"]["guide-return"] = {"id": "guide-return", "owner_id": self.player_id,
            "status": "returning", "mission": "attack", "swarm_crystals": 12}
        step = self.step("swarm_crystals")
        self.assertFalse(step["done"])
        self.assertEqual(step["target_id"], "")
        self.assertIn("po rozładunku", step["description"])

    def test_scout_in_progress_waits_but_changed_target_does_not_complete_it(self):
        self.choose()
        target_id = self.step("swarm_scout")["target_id"]
        self.world.data["fleets"]["guide-scout"] = {"id": "guide-scout", "owner_id": self.player_id,
            "status": "outbound", "mission": "scout", "target_id": target_id}
        self.assertEqual(self.step("swarm_scout")["target_id"], "")
        self.world.data["planets"][target_id].update(owner_type="empty", owner_id="")
        step = self.step("swarm_scout")
        self.assertFalse(step["done"])
        self.assertTrue(step["target_id"])
        self.assertNotEqual(step["target_id"], target_id)

    def test_no_npc_or_free_planet_returns_an_honest_wait_state(self):
        self.choose()
        for p in self.world.data["planets"].values():
            if p["owner_id"] != self.player_id:
                p.update(owner_type="player", owner_id="unrelated-player")
        for ident in ("swarm_scout", "swarm_crystals", "second_colony"):
            step = self.step(ident)
            self.assertEqual(step["target_id"], "")
            self.assertIn("teraz", step["description"])
        self.assertEqual(completed(self.view()), set())

    def test_returned_copy_cannot_edit_authoritative_markers(self):
        self.choose()
        state = self.view()
        state["current"]["done"] = True
        for step in state["steps"]:
            step["done"] = True
        self.assertEqual(completed(self.view()), set())


class OnboardingIntegrationTests(unittest.TestCase):
    def test_five_step_event_flow_with_prepared_veteran_fleet_and_restart(self):
        for race in skill_tree.ROOTS:
            with self.subTest(race=race), tempfile.TemporaryDirectory() as directory:
                path = str(Path(directory) / "guide.sqlite3")
                world = World(path, speed=10, now=START)
                try:
                    player_id = world.register("Guide " + race, "guide-integration-password")["state"]["player"]["id"]
                    world.action(player_id, {"type": "choose_race", "race_id": race})
                    state = world.state(player_id)
                    self.assertEqual(state["onboarding"]["completed_count"], 0)
                    world.action(player_id, {"type": "build", "key": "metal_mine"})
                    self.assertFalse(world.state(player_id)["onboarding"]["steps"][0]["done"])
                    advance_live(world, world.data["planets"][state["home_id"]]["queue"][0]["ends_at"])
                    self.assertTrue(world.state(player_id)["onboarding"]["steps"][0]["done"])
                    # Since 0.9.0 targets must have been discovered. This scenario
                    # tests later goal events, so give the veteran its prior scouts.
                    for discovered in world.data["planets"].values():
                        if discovered["owner_type"] in ("empty", "alien"):
                            world._capture_planetary_intel(player_id, discovered)
                            if discovered["owner_type"] == "alien":
                                world._capture_swarm_intel(player_id, discovered)
                    # The ordinary colony comes before the difficult raid now.
                    current = world.state(player_id)["onboarding"]["current"]
                    self.assertEqual(current["id"], "second_colony")
                    world.action(player_id, {"type": "fleet", "mission": "colonize", "target_id": current["target_id"], "ships": {"colonizer": 1}})
                    flight = next(f for f in world.data["fleets"].values() if f["owner_id"] == player_id)
                    advance_live(world, flight["arrives_at"])
                    self.assertEqual(world.state(player_id)["onboarding"]["current"]["id"], "swarm_scout")
                    target = world.state(player_id)["onboarding"]["current"]["target_id"]
                    world.action(player_id, {"type": "fleet", "mission": "scout", "target_id": target, "ships": {"scout": 1}})
                    flight = next(f for f in world.data["fleets"].values() if f["owner_id"] == player_id)
                    advance_live(world, flight["arrives_at"])
                    self.assertIn("swarm_scout", completed(world.state(player_id)["onboarding"]))
                    advance_live(world, flight["arrives_at"])
                    target = world.state(player_id)["onboarding"]["current"]["target_id"]
                    # This verifies durable event markers, not starter balance.
                    # Prepare an experienced force without granting rare currency
                    # or altering the real fortress's stock and defenders.
                    home = world._owned(player_id)
                    home["ships"]["frigate"] = 2500
                    home["resources"]["fuel"] = 10_000_000.0
                    world.action(player_id, {"type": "fleet", "mission": "attack", "target_id": target, "ships": {"frigate": 2500}})
                    flight = next(f for f in world.data["fleets"].values() if f["owner_id"] == player_id)
                    advance_live(world, flight["arrives_at"])
                    self.assertGreater(flight["swarm_crystals"], 0)
                    self.assertNotIn("swarm_crystals", completed(world.state(player_id)["onboarding"]))
                    advance_live(world, flight["arrives_at"])
                    state = world.state(player_id)
                    self.assertIn("swarm_crystals", completed(state["onboarding"]))
                    node = next(n for n in state["skill_tree"]["nodes"] if n["available"] and n["affordable"])
                    world.action(player_id, {"type": "unlock_skill", "node_id": node["id"]})
                    finished = world.state(player_id)["onboarding"]
                    self.assertTrue(finished["finished"])
                    self.assertEqual(finished["completed_count"], 5)
                    self.assertIsNone(finished["current"])
                    markers = json.dumps(world.data["players"][player_id]["onboarding"], sort_keys=True)
                    now = world.now
                finally:
                    world.close()
                restored = World(path, speed=10, now=now)
                try:
                    self.assertTrue(restored.state(player_id)["onboarding"]["finished"])
                    self.assertEqual(json.dumps(restored.data["players"][player_id]["onboarding"], sort_keys=True), markers)
                finally:
                    restored.close()

    def test_scout_of_former_swarm_never_completes_swarm_goal(self):
        world = World(":memory:", speed=10, now=START)
        try:
            player_id = world.register("Guide changed target", "guide-integration-password")["state"]["player"]["id"]
            world.action(player_id, {"type": "choose_race", "race_id": "zetans"})
            target_id = next(step["target_id"] for step in world.state(player_id)["onboarding"]["steps"] if step["id"] == "swarm_scout")
            world.action(player_id, {"type": "fleet", "mission": "scout", "target_id": target_id, "ships": {"scout": 1}})
            target = world.data["planets"][target_id]
            target.update(owner_id="", owner_type="empty")
            flight = next(f for f in world.data["fleets"].values() if f["owner_id"] == player_id)
            # Resolve the genuine arrival against changed ownership, without a
            # fabricated claim that the former colony is still an NPC target.
            world._complete_fleet(flight)
            self.assertNotIn("swarm_scout", completed(world.state(player_id)["onboarding"]))
        finally:
            world.close()


if __name__ == "__main__":
    unittest.main()
