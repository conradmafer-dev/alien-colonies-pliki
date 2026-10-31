"""Version-85 construction and storage-aware queue checks on the live server."""
import copy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
import ogame_economy
import technology


NOW = 1_900_000_000.0


class TimingRules85(unittest.TestCase):
    def test_early_mine_and_late_automation_examples(self):
        first = ogame_economy.cost("buildings", "metal_mine", (60, 15, 0), 0)
        self.assertEqual(ogame_economy.project_seconds("buildings", first, {}, target_level=1), 31)
        cost30 = ogame_economy.cost("buildings", "metal_mine", (60, 15, 0), 29)
        self.assertEqual(cost30, {"metal": 7670042, "crystal": 1917510, "fuel": 0})
        self.assertEqual(ogame_economy.project_seconds("buildings", cost30, {}, target_level=30,
                         research_levels={"robotics": 5, "nanotechnology": 6}), 575254)
        self.assertEqual(ogame_economy.project_seconds("buildings", cost30, {}, target_level=30,
                         research_levels={"robotics": 12, "nanotechnology": 12}), 66376)

    def test_early_bonus_ends_at_target_level_six(self):
        cost = {"metal": 1000, "crystal": 0, "fuel": 999999}
        for target, bonus in ((1, 3.5), (2, 3.0), (3, 2.5), (4, 2.0), (5, 1.5), (6, 1), (30, 1)):
            with self.subTest(target=target):
                result = ogame_economy.project_timing("buildings", cost, {}, target_level=target)
                self.assertEqual(result["early_bonus"], bonus)
                self.assertEqual(result["seconds"], math.ceil(1440 / bonus))

    def test_nano_stages_only_apply_to_construction(self):
        cost = {"metal": 1000, "crystal": 0, "fuel": 0}
        for nano, multiplier in ((0, 1), (2, 1), (3, 2), (5, 2), (6, 4), (8, 4), (9, 8), (11, 8), (12, 16)):
            for group in ("buildings", "ships", "defenses", "research"):
                with self.subTest(nano=nano, group=group):
                    timing = ogame_economy.project_timing(group, cost, {"lab": 5, "shipyard": 5},
                                      research_levels={"robotics": 5, "nanotechnology": nano}, target_level=10)
                    expected = 1 if group == "research" else multiplier
                    self.assertEqual(timing["nanotechnology_multiplier"], expected)
                    self.assertEqual(timing["robotics_multiplier"], 6 if group == "buildings" else 1)
                    self.assertEqual(timing["facility_multiplier"], 1 if group == "buildings" else 6)
                    self.assertEqual(timing["seconds"], math.ceil((3600 if group == "research" else 1440)
                                     / (6 * expected)))

    def test_nano_keeps_production_and_robotics_does_not_stack_generic_bonus(self):
        effects = technology.effects({"robotics": 12, "nanotechnology": 12})
        self.assertEqual(effects["production_all"], .36)
        self.assertEqual(effects["robotics_speed"], 12)
        self.assertEqual(effects.get("build_speed", 0), 0)

    def test_minimum_one_second_with_all_modifiers(self):
        self.assertEqual(ogame_economy.project_seconds("buildings", {"metal": 0, "crystal": 1}, {},
                         100, .5, .4, research_levels={"robotics": 12, "nanotechnology": 12}, target_level=1), 1)


class LiveTimingAndQueues85(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = str(Path(self.temp.name) / "timing.sqlite3")
        self.w = app.World(self.database, now=NOW)
        state = self.w.register("TimingPilot", "timing-tests-strong-password")["state"]
        self.owner = state["player"]["id"]
        self.w.action(self.owner, {"type": "choose_race", "race_id": "symbionts"})
        self.p = self.w._owned(self.owner)
        self.player = self.w._player(self.owner)
        self.p["resources"] = dict.fromkeys(app.RESOURCES, 100000000.0)
        self.w.data["alien"]["next_expansion_at"] = NOW + 365 * 86400

    def tearDown(self):
        self.w.close()

    def entry(self, group, key):
        return self.w._catalog(self.owner, self.p, project_only=(group, key))[group][0]

    def grant(self):
        self.player["subscription"] = {"enable_queue_planning": True, "starts_at": NOW,
                                       "expires_at": NOW + 365 * 86400}

    def test_live_catalog_uses_robotics_once_and_keeps_racial_and_skill_reductions(self):
        self.p["buildings"].update(metal_mine=29, world_root=5)
        self.player["research"].update(robotics=5, nanotechnology=6)
        with patch.object(self.w, "_bonuses", return_value={"build_speed": .25}):
            entry = self.entry("buildings", "metal_mine")
        profile = entry["construction_timing"]
        self.assertEqual(profile["robotics_multiplier"], 6)
        self.assertEqual(profile["nanotechnology_multiplier"], 4)
        self.assertEqual(profile["skill_multiplier"], 1.25)
        self.assertEqual(profile["time_reduction"], .4)
        self.assertEqual(profile["speed_multiplier"], 50)
        self.assertEqual(entry["seconds"], 276122)
        self.assertEqual(entry["seconds"], profile["seconds"])

    def test_live_ships_and_research_have_no_duplicate_facility_or_robotics_factor(self):
        self.p["buildings"].update(shipyard=5, lab=5)
        self.player["research"].update(robotics=12, nanotechnology=6)
        ship = self.entry("ships", "scout")
        self.assertEqual(ship["seconds"], 60)
        self.assertEqual(ship["construction_timing"]["speed_multiplier"], 24)
        before = self.entry("research", "computing")
        self.player["research"].update(robotics=0, nanotechnology=0)
        after = self.entry("research", "computing")
        self.assertEqual(before["seconds"], after["seconds"])
        self.assertEqual(before["construction_timing"]["facility_multiplier"], 6)
        self.assertEqual(before["construction_timing"]["nanotechnology_multiplier"], 1)

    def test_historical_pending_uses_exact_old_robotics_until_migration(self):
        self.player["research"].update(robotics=5, nanotechnology=6)
        self.w.data["economy85_from"] = NOW + 20
        old = self.entry("buildings", "metal_mine")
        self.assertEqual(old["seconds"], 90)
        self.assertEqual(old["construction_timing"]["rules_version"], 84)
        self.assertEqual(old["construction_timing"]["skill_multiplier"], 1.2)
        self.assertEqual(old["construction_timing"]["early_bonus"], 1)
        self.assertEqual(old["construction_timing"]["nanotechnology_multiplier"], 1)
        self.w.now = NOW + 20
        new = self.entry("buildings", "metal_mine")
        self.assertEqual(new["seconds"], 2)
        self.assertEqual(new["construction_timing"]["rules_version"], 85)
        self.assertEqual(new["construction_timing"]["speed_multiplier"], 84)

    def test_paid_legacy_task_survives_migration_and_pending_uses_new_factors(self):
        self.grant()
        self.w.action(self.owner, {"type": "build", "key": "metal_mine"})
        # Simulate the durable queue record written by version 84.
        task = self.p["queue"][0]
        task.update(seconds=108, ends_at=NOW + 108)
        task.pop("construction_timing", None)
        self.w.action(self.owner, {"type": "plan_project", "kind": "build", "key": "metal_mine"})
        frozen = copy.deepcopy(task)
        resources = dict(self.p["resources"])
        self.player["research"].update(robotics=5, nanotechnology=6)
        self.w.data.pop("economy85_from")
        self.w._save()
        self.w.close()
        self.w = app.World(self.database, now=NOW)
        self.p = self.w._owned(self.owner)
        self.player = self.w._player(self.owner)
        self.assertEqual(self.p["queue"][0], frozen)
        self.assertEqual(self.p["resources"], resources)
        self.w.advance(NOW + 108)
        started = self.p["queue"][0]
        self.assertEqual(started["level"], 2)
        self.assertEqual(started["started_at"], NOW + 108)
        self.assertEqual(started["paid_cost"], {"metal": 90, "crystal": 22, "fuel": 0})
        self.assertEqual(started["seconds"], 3)
        self.assertEqual(started["construction_timing"]["speed_multiplier"], 72)
        self.assertIn("planned_order_id", started)

    def test_storage_wait_unreachable_and_overcapacity_stock_spendable(self):
        self.p["resources"] = dict.fromkeys(app.RESOURCES, 0.0)
        cost = {"metal": 12000, "crystal": 0, "fuel": 0}
        rates = dict.fromkeys(app.RESOURCES, 3600.0)
        self.assertIsNone(self.w._planning_wait_seconds(self.p, cost, rates))
        self.p["resources"]["metal"] = 12000
        self.assertEqual(self.w._planning_wait_seconds(self.p, cost, rates), 0)
        self.p["resources"]["metal"] = 0
        self.w.data["economy85_from"] = NOW + 20
        self.assertEqual(self.w._planning_wait_seconds(self.p, cost, rates), 12000)

    def test_batch_storage_block_has_no_impossible_deadline_then_delivery_starts_it(self):
        self.grant()
        self.p["buildings"]["shipyard"] = 1
        self.p["resources"] = dict.fromkeys(app.RESOURCES, 0.0)
        self.w.production = lambda planet, **kwargs: dict.fromkeys(app.RESOURCES, 3600.0)
        self.w.action(self.owner, {"type": "plan_project", "kind": "ship", "key": "scout", "amount": 20})
        self.assertEqual(self.w._public_planned_orders(self.owner)[0]["status"], "blocked")
        self.assertEqual(self.w._planned_queue_deadlines(NOW, NOW + 30000), [])
        self.w.advance(NOW + 30000)
        self.assertFalse(self.p["queue"])
        self.assertEqual(self.p["resources"]["crystal"], 10000)
        # Trade/transport income can legitimately exceed the mining capacity.
        self.p["resources"]["crystal"] += 10000
        self.w._start_planned_projects()
        self.assertEqual(self.p["queue"][0]["paid_cost"]["crystal"], 20000)
        self.assertFalse(self.player["planned_orders"])

    def test_forecast_replays_historical_energy_until_migration_epoch(self):
        self.grant()
        self.p["buildings"]["shipyard"] = 1
        self.p["resources"] = dict.fromkeys(app.RESOURCES, 0.0)
        self.w.data["economy85_from"] = NOW + 20
        self.w.action(self.owner, {"type": "plan_project", "kind": "ship", "key": "scout"})
        with patch.object(self.w, "production", return_value=dict.fromkeys(app.RESOURCES, 3600.0)) as production:
            deadlines = self.w._planned_queue_deadlines(NOW, NOW + 2000)
        self.assertFalse(production.call_args.kwargs["economy85_enabled"])
        self.assertEqual(production.call_args.kwargs["at"], NOW)
        self.assertIn(NOW + 20, deadlines)


if __name__ == "__main__":
    unittest.main()
