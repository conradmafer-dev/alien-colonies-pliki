"""Targeted regression tests for the actual root production server.

Unlike older historical test fixtures, these assert the current one-hive,
zero-starter-fleet and finite-planet-field rules. No production database is used.
"""
from __future__ import annotations
import copy
from pathlib import Path
import tempfile
import unittest

import app
import ogame_economy


NOW = 1_900_000_000.0
PASSWORD = "economy-migration-strong-password"


class OGameRootProduction(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = str(Path(self.temp.name) / "world.sqlite3")
        self.world = app.World(self.database, now=NOW)
        state = self.world.register("EconomyPilot", PASSWORD)["state"]
        self.owner = state["player"]["id"]
        self.home_id = state["planet_id"]
        self.p = self.world.data["planets"][self.home_id]
        self.world.data["alien"]["next_expansion_at"] = NOW + 365 * 86400

    def tearDown(self):
        self.world.close()

    def test_root_starter_costs_levels_and_player_only_economy(self):
        self.assertEqual(self.p["resources"],
                         {"metal": 500.0, "crystal": 500.0, "fuel": 0.0})
        self.assertTrue(all(self.p["buildings"][key] == 0 for key in
                            ("metal_mine","crystal_mine","refinery","power_plant","shipyard","lab")))
        self.assertTrue(all(count == 0 for count in self.p["ships"].values()))
        mine = next(item for item in self.world._catalog(self.owner, self.p)["buildings"]
                    if item["key"]=="metal_mine")
        self.assertEqual(mine["cost"], {"metal": 60, "crystal": 15, "fuel": 0})
        self.assertEqual(mine["seconds"], 31)
        self.assertEqual(mine["max_level"], self.p["environment"]["fields"])
        self.assertEqual(ogame_economy.cost("ships","colonizer",(1,1,1),0),
                         {"metal": 10000, "crystal": 20000, "fuel": 10000})


    def test_passive_colony_income_and_productive_level_one(self):
        starter = dict(self.p["resources"])
        passive = {"metal": 30.0, "crystal": 15.0, "fuel": 0.0}
        self.assertEqual(self.world.production(self.p), passive)
        self.assertEqual(self.world.state(self.owner)["production"], self.world.production(self.p))
        # Passive colony production is independent of the starter power supply.
        self.assertEqual(self.world.energy(self.p)["supply"], app.STARTER_ENERGY_SUPPLY)
        self.world._produce(3600)
        self.assertEqual(self.p["resources"], {key: starter[key] + passive[key] for key in app.RESOURCES})

        for mine, resource in (("metal_mine", "metal"), ("crystal_mine", "crystal"),
                               ("refinery", "fuel")):
            with self.subTest(mine=mine):
                entry = next(item for item in self.world._catalog(self.owner, self.p)["buildings"]
                             if item["key"] == mine)
                self.assertEqual(entry["base_production"], passive[resource])
                self.assertIn("production_actual", entry["details"]["notes"])
                metric = next(m for m in entry["details"]["metrics"] if m["key"] == "mine_" + resource)
                colony = next(m for m in entry["details"]["metrics"] if m["key"] == "colony_" + resource)
                self.assertEqual(metric["current"], 0)
                self.assertEqual(colony["current"], passive[resource])
                self.assertGreater(metric["next"], 0)

                self.p["buildings"][mine] = 1
                self.assertEqual(self.world.energy(self.p)["factor"], 1.0)
                rate = self.world.production(self.p)
                self.assertGreater(rate[resource], 0)
                self.assertAlmostEqual(metric["next"] + passive[resource], rate[resource], places=5)
                self.assertAlmostEqual(colony["next"], rate[resource], places=5)
                for other in app.RESOURCES:
                    if other != resource:
                        self.assertEqual(rate[other], passive[other])
                self.p["buildings"][mine] = 0

        # Existing OGame progression for a powered mine is preserved.
        self.p["buildings"]["metal_mine"] = 1
        first = self.world.production(self.p)["metal"]
        self.p["buildings"]["metal_mine"] = 2
        second = self.world.production(self.p)["metal"]
        self.assertGreater(second, first)
        self.p["buildings"]["power_plant"] = 1
        self.assertGreaterEqual(self.world.production(self.p)["metal"], second)

    def test_first_mine_is_productive_for_automaton_without_power_plant(self):
        self.world.action(self.owner, {"type": "choose_race", "race_id": "automatons"})
        self.p["buildings"]["metal_mine"] = 1
        self.assertEqual(self.p["buildings"]["power_plant"], 0)
        self.assertGreater(self.world.production(self.p)["metal"], 0)
        catalog = self.world._catalog(self.owner, self.p)["buildings"]
        mine = next(item for item in catalog if item["key"] == "metal_mine")
        self.assertAlmostEqual(next(m for m in mine["details"]["metrics"]
                                    if m["key"] == "mine_metal")["current"],
                               self.world.production(self.p)["metal"] - 30.0, places=5)

    def test_unmodified_swarm_production_and_fleets(self):
        swarm = next(p for p in self.world.data["planets"].values() if p["owner_id"]=="khar")
        self.assertEqual(self.world.production(swarm, ogame_enabled=False),
                         self.world.production(swarm, ogame_enabled=True))

    def test_migration_uses_old_rates_before_epoch_and_new_after(self):
        self.p["buildings"].update(metal_mine=5, crystal_mine=5,
                                   refinery=5, power_plant=5)
        old = self.world.production(self.p, ogame_enabled=False)
        new = self.world.production(self.p, ogame_enabled=True)
        baseline = dict(self.p["resources"])
        self.world.data["ogame_economy_from"] = NOW + 1800
        self.world.advance(NOW + 3600)
        for key in app.RESOURCES:
            expected = baseline[key] + 0.5 * old[key] + 0.5 * new[key]
            self.assertAlmostEqual(self.p["resources"][key], expected, places=5)

    def test_migration_preserves_existing_paid_queue_and_accounts(self):
        self.p["resources"] = {"metal": 100000.0, "crystal": 100000.0,
                               "fuel": 100000.0}
        self.world.action(self.owner, {"type": "choose_race", "race_id": "zetans"})
        self.world.action(self.owner, {"type": "build", "key": "metal_mine"})
        task = copy.deepcopy(self.p["queue"][0])
        before_resources = copy.deepcopy(self.p["resources"])
        before_ships = copy.deepcopy(self.p["ships"])
        account_id = self.owner
        self.world.data.pop("ogame_economy_from", None)
        self.world._save()
        self.world.close()
        self.world = app.World(self.database, now=NOW)
        owner = self.world.login("EconomyPilot", PASSWORD)["state"]["player"]["id"]
        self.assertEqual(owner, account_id)
        p = self.world.data["planets"][self.home_id]
        self.assertEqual(p["resources"], before_resources)
        self.assertEqual(p["ships"], before_ships)
        self.assertEqual(p["queue"][0], task)
        self.assertIn("ogame_economy_from", self.world.data)
        backups = list(Path(self.temp.name).rglob("galaxy-*.sqlite3"))
        self.assertTrue(backups, "A database backup is required before migration")

    def test_fields_not_level_120_are_only_building_limit(self):
        for key in self.p["buildings"]:
            self.p["buildings"][key] = 3
        catalog = self.world._catalog(self.owner, self.p)["buildings"]
        self.assertTrue(all(item["max_level"] == self.p["environment"]["fields"]
                            for item in catalog))
        self.p["environment"]["fields"] = sum(self.p["buildings"].values())
        self.assertTrue(all(not item["enabled"] for item in
                            self.world._catalog(self.owner, self.p)["buildings"]))


if __name__=="__main__":
    unittest.main()
