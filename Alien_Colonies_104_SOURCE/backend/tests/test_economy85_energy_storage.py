"""Version 85: energy, bounded mining and additive migration; private fixtures only."""
from __future__ import annotations

import copy
import math
import ogame_economy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
import economy85
import planetary
import races

NOW = 1_900_000_000.0


class EnergyStorage85(unittest.TestCase):
    def setUp(self):
        self.world = app.World(":memory:", now=NOW)
        state = self.world.register("StoragePilot", "private-audit-password-85")["state"]
        self.owner = state["player"]["id"]
        self.player = self.world.data["players"][self.owner]
        self.planet = self.world.data["planets"][state["planet_id"]]
        self.planet["rare_trait"] = ""
        self.world.data["alien"]["next_expansion_at"] = NOW + 365 * 86400
        self.addCleanup(lambda: self.world.close())

    def race(self, race):
        self.player["race_id"] = race
        self.player["research"] = {"propulsion": 0, "weapons": 0}
        self.player["skill_nodes"] = []
        self.world._ensure_race_buildings(self.planet)

    def powered_mines(self, level=10):
        self.planet["buildings"].update(metal_mine=level, crystal_mine=level,
                                         refinery=level, power_plant=40)

    def test_exact_energy_curve_and_faction_ratios(self):
        for race in ("", "zetans", "automatons", "symbionts"):
            self.race(race)
            rules = races.RACES[race]["rules"] if race else races.NEUTRAL_RULES
            for level in (0, 1, 10, 20, 30):
                with self.subTest(race=race, level=level):
                    self.planet["buildings"].update(metal_mine=level, crystal_mine=level,
                                                     refinery=level, power_plant=level)
                    energy = self.world.energy(self.planet)
                    curve = level * 1.1 ** level
                    expected_supply = 40 + 20 * curve * rules["energy_supply_per_level"] / 100
                    expected_used = curve * (rules["energy_use_per_level"]["metal_mine"] / 2
                                             + rules["energy_use_per_level"]["crystal_mine"] * .4
                                             + rules["energy_use_per_level"]["refinery"] * .8)
                    self.assertAlmostEqual(energy["supply"], expected_supply)
                    self.assertAlmostEqual(energy["used"], round(expected_used, 6))
                    self.assertAlmostEqual(energy["factor"], min(1, expected_supply / round(expected_used, 6)) if expected_used else 1)

    def test_zero_mines_and_first_mine_starter_energy(self):
        for race in races.RACES:
            self.race(race)
            self.planet["buildings"].update(metal_mine=0, crystal_mine=0, refinery=0, power_plant=0)
            self.assertEqual(self.world.production(self.planet), {"metal": 30.0, "crystal": 15.0, "fuel": 0.0})
            self.planet["buildings"]["metal_mine"] = 1
            self.assertEqual(self.world.energy(self.planet)["factor"], 1)
            self.assertGreater(self.world.production(self.planet)["metal"], 30)

    def test_passive_income_ignores_all_mining_bonuses_and_zero_energy(self):
        for race in races.RACES:
            self.race(race)
            self.player["research"]["nanotechnology"] = 12
            self.planet["rare_trait"] = "metal_veins"
            self.planet["buildings"].update(metal_mine=0, crystal_mine=0, refinery=0, power_plant=0)
            for biome in planetary.TYPES:
                self.planet["environment"]["type"] = biome
                with self.subTest(race=race, biome=biome), \
                     patch.object(self.world, "_bonuses", return_value={"production_metal": .6, "production_crystal": .6}), \
                     patch.object(self.world, "_building_effects", return_value={"production_all": .75}), \
                     patch.object(self.world, "energy", return_value={"factor": 0.0}):
                    self.assertEqual(self.world.production(self.planet), {"metal": 30.0, "crystal": 15.0, "fuel": 0.0})

    def test_passive_income_adds_fixed_amount_to_mines_and_only_scales_with_speed(self):
        for race in races.RACES:
            self.race(race)
            self.planet["buildings"].update(metal_mine=10, crystal_mine=10, refinery=10, power_plant=0)
            self.assertLess(self.world.energy(self.planet)["factor"], 1)
            for speed in (1, 3, 7):
                self.world.speed = speed
                # Isolate legacy and current production from the energy-curve
                # migration: this comparison changes only passive income.
                energy = self.world.energy(self.planet)
                with patch.object(self.world, "energy", return_value=energy):
                    mine_only = self.world.production(self.planet, economy85_enabled=False)
                    total = self.world.production(self.planet)
                for resource, base in (("metal", 30), ("crystal", 15), ("fuel", 0)):
                    self.assertAlmostEqual(total[resource] - mine_only[resource], base * speed)

    def test_passive_income_stops_at_storage_and_inactivity(self):
        self.race("automatons")
        self.planet["resources"] = {"metal": 9999.0, "crystal": 25000.0, "fuel": 0.0}
        self.world._produce(3600)
        self.assertEqual(self.planet["resources"], {"metal": 10000, "crystal": 25000.0, "fuel": 0.0})
        self.planet["resources"]["metal"] = 0
        self.player["last_active_at"] = NOW - 7 * 86400
        self.assertEqual(self.world.production(self.planet), dict.fromkeys(app.RESOURCES, 0.0))
        before = dict(self.planet["resources"])
        self.world._produce(3600)
        self.assertEqual(self.planet["resources"], before)

    def test_passive_income_is_not_backdated_before_version85(self):
        self.race("zetans")
        self.planet["resources"] = dict.fromkeys(app.RESOURCES, 0.0)
        self.world.data["economy85_from"] = NOW + 1800
        self.assertEqual(self.world.production(self.planet, economy85_enabled=False), dict.fromkeys(app.RESOURCES, 0.0))
        self.world._produce(3600, start_at=NOW)
        self.assertEqual(self.planet["resources"], {"metal": 15.0, "crystal": 7.5, "fuel": 0.0})

    def test_passive_income_can_start_waiting_build_without_a_mine(self):
        self.race("symbionts")
        self.player["subscription"] = {"enable_queue_planning": True, "starts_at": NOW,
                                       "expires_at": NOW + 86400}
        self.planet["resources"] = dict.fromkeys(app.RESOURCES, 0.0)
        self.world.action(self.owner, {"type": "plan_project", "kind": "build", "key": "metal_mine"})
        deadline = min(self.world._planned_queue_deadlines(NOW, NOW + 10000))
        self.assertAlmostEqual(deadline, NOW + 7200, places=5)
        self.world.advance(deadline)
        task = self.planet["queue"][0]
        self.assertAlmostEqual(task["started_at"], NOW + 7200, places=5)
        self.assertEqual(task["paid_cost"], {"metal": 60, "crystal": 15, "fuel": 0})
        for resource, expected in (("metal", 0), ("crystal", 15), ("fuel", 0)):
            self.assertAlmostEqual(self.planet["resources"][resource], expected, places=5)

    def test_catalog_separates_passive_income_from_mine_bonuses(self):
        for race in races.RACES:
            self.race(race)
            self.player["research"]["nanotechnology"] = 6
            self.planet["buildings"].update(metal_mine=3, crystal_mine=3, refinery=3, power_plant=0)
            for speed in (1, 3):
                self.world.speed = speed
                total = self.world.production(self.planet)
                catalog = self.world._catalog(self.owner, self.planet)["buildings"]
                for key, resource, passive in (("metal_mine", "metal", 30), ("crystal_mine", "crystal", 15), ("refinery", "fuel", 0)):
                    item = next(row for row in catalog if row["key"] == key)
                    metrics = {row["key"]: row for row in item["details"]["metrics"]}
                    self.assertEqual(item["base_production"], passive * speed)
                    self.assertAlmostEqual(metrics["mine_" + resource]["current"] + passive * speed,
                                           total[resource], places=5)
                    self.assertAlmostEqual(metrics["colony_" + resource]["current"], total[resource], places=5)
                    self.assertIn("production_actual", item["details"]["notes"])

    def test_energy_research_traits_and_dyson_preserved(self):
        self.race("zetans")
        self.planet["buildings"].update(metal_mine=10, crystal_mine=10, refinery=10,
                                         power_plant=10, phase_matrix=2)
        self.player["research"].update(energy_technology=3, superconductors=4)
        self.planet["rare_trait"] = "geothermal_sources"
        self.player["megastructure"].update(origin_id=self.planet["id"], dyson_stage=1)
        energy = self.world.energy(self.planet)
        expected_supply = 40 + 20 * 10 * 1.1 ** 10 * 1.18 * 1.25 + self.world._dyson_power(self.planet)
        expected_used = 10 * 1.1 ** 10 * (11.5 + 11.6 + 23.2) * .88 * .92
        self.assertAlmostEqual(energy["supply"], expected_supply)
        self.assertAlmostEqual(energy["used"], round(expected_used, 6))

    def test_storage_curve_race_vaults_and_no_free_levels(self):
        expected = [10000, 20000, 40000, 75000, 140000, 255000, 470000,
                    865000, 1590000, 2920000, 5355000]
        for race, key in economy85.VAULTS.items():
            self.race(race)
            for level, capacity in enumerate(expected):
                self.planet["buildings"][key] = level
                actual = self.world.storage(self.planet)
                self.assertEqual(actual["level"], level)
                self.assertEqual(actual["capacity"], dict.fromkeys(app.RESOURCES, capacity))
        self.assertEqual(economy85.storage_capacity(360, app.MAX_RESOURCE), app.MAX_RESOURCE)

    def test_caps_each_resource_without_deleting_overflow_and_resumes(self):
        self.race("symbionts")
        self.powered_mines()
        self.planet["resources"] = {"metal": 9999.0, "crystal": 25000.0, "fuel": 100.0}
        rates = self.world.production(self.planet)
        self.assertEqual(rates["crystal"], 0)
        self.world._produce(3600)
        self.assertEqual(self.planet["resources"]["metal"], 10000)
        self.assertEqual(self.planet["resources"]["crystal"], 25000)
        self.assertAlmostEqual(self.planet["resources"]["fuel"], 100 + rates["fuel"])
        self.assertEqual(self.world.production(self.planet)["metal"], 0)
        self.planet["resources"]["metal"] -= 100
        self.assertGreater(self.world.production(self.planet)["metal"], 0)
        self.planet["buildings"]["living_vault"] = 2
        self.assertGreater(self.world.production(self.planet)["crystal"], 0)
        self.assertEqual(self.planet["resources"]["crystal"], 25000)

    def test_late_vault_capacity_can_pay_next_upgrade_for_all_races(self):
        first_floor = {"automatons": 22, "zetans": 24, "symbionts": 29}
        for race, level in first_floor.items():
            self.race(race)
            key = economy85.VAULTS[race]
            base = races.UNIQUE_BUILDINGS[race][key]["spec"][2]
            previous_cost = ogame_economy.cost("buildings", key, base, level - 1)
            self.assertLessEqual(max(previous_cost.values()), economy85.storage_capacity(level - 1, app.MAX_RESOURCE))
            self.planet["buildings"][key] = level
            self.planet["buildings"]["lab"] = 2
            next_cost = ogame_economy.cost("buildings", key, base, level)
            base_capacity = economy85.storage_capacity(level, app.MAX_RESOURCE)
            self.assertGreater(max(next_cost.values()), base_capacity)
            snapshot = copy.deepcopy(self.planet)
            storage = self.world.storage(self.planet)
            self.assertEqual(storage["capacity"], dict.fromkeys(app.RESOURCES, max(next_cost.values())))
            self.assertEqual(self.planet, snapshot, "Capacity calculation must grant no stocks or levels")
            self.planet["resources"] = dict(storage["capacity"])
            item = self.world._catalog(self.owner, self.planet, project_only=("buildings", key))["buildings"][0]
            self.assertTrue(item["enabled"])
            self.assertEqual(item["storage_capacity_current"], storage["capacity"]["metal"])
            metric = next(m for m in item["details"]["metrics"] if m["key"] == "storage_capacity")
            self.assertEqual(metric["current"], storage["capacity"]["metal"])
            self.assertTrue(app.affordable(self.planet, next_cost))
            self.planet["queue"] = []

    def test_catalog_storage_upgrade_energy_details_and_overflow_spending(self):
        self.race("symbionts")
        self.powered_mines(3)
        self.planet["buildings"].update(lab=2, living_vault=0, crystal_mine=15)
        self.planet["resources"] = dict.fromkeys(app.RESOURCES, 500.0)
        catalog = self.world._catalog(self.owner, self.planet)["buildings"]
        vault = next(row for row in catalog if row["key"] == "living_vault")
        metric = next(row for row in vault["details"]["metrics"] if row["key"] == "storage_capacity")
        self.assertEqual((metric["current"], metric["next"]), (10000, 20000))
        crystal = next(row for row in catalog if row["key"] == "crystal_mine")
        self.assertIn("skarbiec", crystal["reason"])
        self.planet["resources"] = dict.fromkeys(app.RESOURCES, 1000000.0)
        catalog = self.world._catalog(self.owner, self.planet)["buildings"]
        crystal = next(row for row in catalog if row["key"] == "crystal_mine")
        self.assertTrue(crystal["enabled"])
        energy_metric = next(row for row in crystal["details"]["metrics"] if row["key"] == "energy_use")
        self.assertAlmostEqual(energy_metric["current"], crystal["energy_use_current"], places=5)
        self.assertAlmostEqual(energy_metric["next"], crystal["energy_use_next"], places=5)
        state = self.world.state(self.owner)
        self.assertEqual(state["storage"]["capacity"], dict.fromkeys(app.RESOURCES, 10000))
        own = next(p for p in state["own_planets"] if p["id"] == self.planet["id"])
        self.assertEqual(own["storage"], state["storage"])
        self.world.action(self.owner, {"type": "build", "key": "crystal_mine"})
        self.assertTrue(any(q["key"] == "crystal_mine" for q in self.planet["queue"]))

    def test_split_offline_epoch_uses_old_energy_and_no_old_storage_cap(self):
        self.race("zetans")
        self.planet["buildings"].update(metal_mine=10, crystal_mine=10, refinery=10, power_plant=8)
        self.planet["resources"] = {"metal": 20000.0, "crystal": 100.0, "fuel": 100.0}
        self.world.data["economy85_from"] = NOW + 1800
        old_rates = self.world.production(self.planet, economy85_enabled=False)
        before = dict(self.planet["resources"])
        self.world._produce(1800, start_at=NOW)
        for resource in app.RESOURCES:
            self.assertAlmostEqual(self.planet["resources"][resource], before[resource] + .5 * old_rates[resource])
        at_epoch = dict(self.planet["resources"])
        new_rates = self.world.production(self.planet)
        self.assertEqual(new_rates["metal"], 0)
        self.world._produce(1800, start_at=NOW + 1800)
        for resource in app.RESOURCES:
            expected = at_epoch[resource] if at_epoch[resource] >= 10000 else min(10000, at_epoch[resource] + .5 * new_rates[resource])
            self.assertAlmostEqual(self.planet["resources"][resource], expected)
        # The same interval split internally must produce byte-identical balances.
        self.planet["resources"] = before
        self.world._produce(3600, start_at=NOW)
        for resource in app.RESOURCES:
            expected = at_epoch[resource] if at_epoch[resource] >= 10000 else min(10000, at_epoch[resource] + .5 * new_rates[resource])
            self.assertAlmostEqual(self.planet["resources"][resource], expected)

    def test_khar_energy_and_production_not_changed(self):
        hive = next(p for p in self.world.data["planets"].values() if p["owner_id"] == "khar")
        self.assertEqual(self.world.energy(hive), self.world.energy(hive, economy85_enabled=False))
        self.assertEqual(self.world.production(hive), self.world.production(hive, economy85_enabled=False))


class FieldsMigration85(unittest.TestCase):
    def test_fields_tripled_once_and_occupied_overflow_preserved(self):
        p = {"environment": {"fields": 60}, "buildings": {"metal_mine": 10}, "queue": []}
        self.assertTrue(planetary.expand_fields85(p))
        self.assertEqual(p["environment"]["fields"], 180)
        saved = copy.deepcopy(p)
        self.assertFalse(planetary.expand_fields85(p))
        self.assertEqual(p, saved)
        p = {"environment": {"fields": 20}, "buildings": {"metal_mine": 90},
             "queue": [{"kind": "build", "key": "metal_mine", "level": 110}]}
        original_levels, original_queue = copy.deepcopy(p["buildings"]), copy.deepcopy(p["queue"])
        planetary.expand_fields85(p)
        self.assertEqual(p["environment"]["fields"], 110)
        self.assertEqual(p["buildings"], original_levels)
        self.assertEqual(p["queue"], original_queue)
        for i in range(1, 100):
            env = planetary.profile(f"s{i}p1", 0, 1)
            self.assertTrue(144 <= env["fields"] <= 360)
            self.assertEqual(env["fields_expansion85"], 1)

    def test_disk_migration_preserves_queue_balances_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            database = str(Path(temp) / "world.sqlite3")
            world = app.World(database, now=NOW)
            state = world.register("MigrationPilot", "private-migration-password-85")["state"]
            owner, pid = state["player"]["id"], state["planet_id"]
            p = world.data["planets"][pid]
            p["rare_trait"] = ""
            p["buildings"].update(metal_mine=10, crystal_mine=10, refinery=10, power_plant=8)
            p["resources"] = dict.fromkeys(app.RESOURCES, 50000.0)
            p["queue"] = [{"kind": "build", "key": "shipyard", "level": 1,
                            "ends_at": NOW + 7200, "seconds": 7200,
                            "cost": {"metal": 400, "crystal": 200, "fuel": 100}}]
            world.data["alien"]["next_expansion_at"] = NOW + 365 * 86400
            for planet in world.data["planets"].values():
                planet["environment"]["fields"] //= 3
                planet["environment"].pop("fields_expansion85", None)
            world.data.pop("economy85_from", None)
            world.data.pop("economy85_schema", None)
            original = copy.deepcopy(p)
            rates = world.production(p, economy85_enabled=False)
            world.close()
            world = app.World(database, now=NOW + 3600)
            try:
                migrated = world.data["planets"][pid]
                self.assertEqual(world.data["economy85_from"], NOW + 3600)
                self.assertEqual(migrated["buildings"], original["buildings"])
                self.assertEqual(migrated["queue"], original["queue"])
                self.assertEqual(migrated["environment"]["fields"], max(original["environment"]["fields"] * 3,
                                      sum(original["buildings"].values()) + 1))
                for resource in app.RESOURCES:
                    self.assertAlmostEqual(migrated["resources"][resource], original["resources"][resource] + rates[resource])
                saved = copy.deepcopy(migrated)
            finally:
                world.close()
            world = app.World(database, now=NOW + 3600)
            try:
                again = world.data["planets"][pid]
                self.assertEqual(again["environment"]["fields"], saved["environment"]["fields"])
                self.assertEqual(again["resources"], saved["resources"])
                self.assertEqual(again["queue"], saved["queue"])
                self.assertEqual(world.data["economy85_from"], NOW + 3600)
                world.advance(NOW + 3601)
                self.assertEqual(again["resources"], saved["resources"])
            finally:
                world.close()


if __name__ == "__main__":
    unittest.main()
