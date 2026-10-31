"""Fortress progression: starters lose; prepared veterans earn real rare loot."""
from pathlib import Path
import tempfile
import unittest

from tests.world_fixture import LocalTestWorld as World
from server import swarm
from tests.make_progression_fixture import RACES, START, advance_live, first_hunt


class ProgressionPlaythroughTests(unittest.TestCase):
    def assert_playthrough(self, age):
        for race in RACES:
            with self.subTest(race=race, aged_seconds=age), tempfile.TemporaryDirectory() as directory:
                world = World(str(Path(directory) / "playthrough.sqlite3"), speed=10, now=START)
                try:
                    snapshots = first_hunt(world, race, age)
                    m = snapshots["measurements"]
                    self.assertEqual(snapshots["chosen"]["ships"]["frigate"], 2500)
                    self.assertTrue(m["qa_prepared_veteran_fleet"])
                    self.assertEqual(snapshots["chosen"]["player"]["swarm_crystals"], 0)
                    self.assertGreater(sum(m["defenders_before"].values()), 0)
                    self.assertGreater(m["rare_stock_before"], 0)
                    self.assertLessEqual(m["fuel_cost"], m["starting_fuel"])
                    self.assertGreater(m["returning_reward"], 0)
                    self.assertEqual(m["wallet_before_return"], 0)
                    self.assertEqual(m["wallet_after_return"], m["returning_reward"])
                    self.assertGreaterEqual(m["wallet_after_return"], m["first_node_cost"])
                    self.assertEqual(m["wallet_after_purchase"], m["wallet_after_return"] - m["first_node_cost"])
                    self.assertGreater(m["surviving_frigates"], 0)
                    self.assertEqual(m["whole_mission_seconds"], 2 * m["outbound_seconds"])
                    node_id = m["first_node_id"]
                    self.assertIn(node_id, snapshots["purchased"]["skill_tree"]["unlocked"])
                    production_resource = next(iter(m["first_node_effects"])).removeprefix("production_")
                    self.assertAlmostEqual(m["production_after"][production_resource],
                                           m["production_before"][production_resource] * 1.08)
                    if age:
                        self.assertGreater(m["age_simulation_steps"], 100)
                        self.assertEqual(m["swarm_colonies_at_registration"], swarm.INITIAL_HIVES)
                    # Replayed purchase and repeated time settlement cannot duplicate
                    # either the raid reward or an already-applied skill's bonus.
                    replayed = world.action(snapshots["player_id"], snapshots["purchase_payload"])["state"]
                    self.assertEqual(replayed["player"]["swarm_crystals"], m["wallet_after_purchase"])
                    self.assertEqual(replayed["production"], snapshots["purchased"]["production"])
                    world.advance(world.now)
                    advance_live(world, world.now + 30)
                    later = world.state(snapshots["player_id"])
                    self.assertEqual(later["player"]["swarm_crystals"], m["wallet_after_purchase"])
                finally:
                    world.close()

    def test_every_race_can_earn_and_buy_a_skill_with_a_prepared_veteran_fleet(self):
        self.assert_playthrough(0)

    def test_live_swarm_growth_does_not_break_prepared_veteran_raid_accounting(self):
        self.assert_playthrough(3600)

    def test_starter_fleets_cannot_farm_the_initial_fortresses(self):
        for race in RACES:
            with self.subTest(race=race):
                world = World(":memory:", speed=1, now=START)
                try:
                    player = world.register("Starter " + race, "starter-raid-password")["state"]["player"]["id"]
                    world.action(player, {"type": "choose_race", "race_id": race})
                    target = next(p for p in world.data["planets"].values() if p["owner_id"] == "khar")
                    stock = target["swarm_crystals"]
                    response = world.action(player, {"type": "fleet", "mission": "attack",
                        "target_id": target["id"], "ships": {"frigate": 3}})
                    fleet = world.data["fleets"][response["state"]["fleets"][0]["id"]]
                    world._complete_fleet(fleet)
                    self.assertEqual(fleet["swarm_crystals"], 0)
                    self.assertEqual(world.data["players"][player]["swarm_crystals"], 0)
                    self.assertEqual(target["swarm_crystals"], stock)
                    self.assertEqual(sum(fleet["ships"].values()), 0)
                    self.assertGreater(sum(target["ships"].values()), 0)
                finally:
                    world.close()


if __name__ == "__main__":
    unittest.main()
