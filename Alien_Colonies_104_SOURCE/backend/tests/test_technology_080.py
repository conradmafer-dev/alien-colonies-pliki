"""Reachability, authoritative unlocks, real effects and additive migration."""
import copy
import tempfile
import unittest
from pathlib import Path

from server import technology
from server.main import GameError
from tests.world_fixture import LocalTestWorld as World


class TechnologyTests(unittest.TestCase):
    def setUp(self):
        self.world = World(":memory:", speed=1000, now=1900000000)
        account = self.world.register("Tech080", "test-password-123")
        self.pid = account["state"]["player"]["id"]
        self.world.action(self.pid, {"type": "choose_race", "race_id": "zetans"})
        self.player = self.world.data["players"][self.pid]
        self.planet = self.world.data["planets"][self.player["home_id"]]
        self.planet["resources"] = dict.fromkeys(("metal", "crystal", "fuel"), 1000000000)
        self.planet["buildings"]["lab"] = 12

    def tearDown(self):
        self.world.db.close()

    def entry(self, key):
        return next(e for e in self.world.state(self.pid)["catalog"]["research"] if e["key"] == key)

    def test_graph_has_three_lanes_no_cycles_and_reachable_levels_for_all_races(self):
        for race in ("zetans", "symbionts", "automatons"):
            self.player["race_id"] = race
            self.world._ensure_racial_research(self.player)
            entries = {e["key"]: e for e in self.world.state(self.pid)["catalog"]["research"]}
            self.assertEqual(len(entries), 21)
            placements = [(e["tree"]["row"], e["tree"]["column"]) for e in entries.values()]
            self.assertEqual(len(placements), len(set(placements)))
            self.assertTrue(all(0 <= column < 3 for _, column in placements))
            for key, entry in entries.items():
                for req in entry["requirements"]:
                    if req["group"] == "research":
                        parent = entries[req["key"]]
                        self.assertLess(parent["tree"]["row"], entry["tree"]["row"])
                        self.assertLessEqual(req["level"], parent["max_level"])
            self.assertEqual(entries["dyson_design"]["max_level"], 1)
            self.assertEqual(entries["wormhole_theory"]["max_level"], 1)

    def test_all_parent_levels_must_be_completed_not_merely_in_progress(self):
        self.player["research"].update(hyperspace=5, energy_technology=5)
        before = copy.deepcopy(self.planet["resources"])
        with self.assertRaises(GameError):
            self.world.action(self.pid, {"type": "research", "key": "graviton_control"})
        self.assertEqual(before, self.planet["resources"])
        self.world.action(self.pid, {"type": "research", "key": "energy_technology"})
        self.assertFalse(self.entry("graviton_control")["requirements_met"])
        self.world.advance(self.planet["queue"][0]["ends_at"])
        self.assertTrue(self.entry("graviton_control")["requirements_met"])
        self.world.action(self.pid, {"type": "research", "key": "graviton_control"})
        self.assertEqual(self.planet["queue"][0]["key"], "graviton_control")

    def test_energy_production_and_timers_apply_actual_research_effects(self):
        self.world.speed = 1
        self.planet["buildings"]["power_plant"] = 12
        power = self.world.energy(self.planet)["supply"]
        rate = self.world.production(self.planet)["metal"]
        duration = self.world._project_seconds(self.pid, self.planet, "research", "energy_technology", 5)
        self.player["research"].update(energy_technology=5, nanotechnology=5, computing=5)
        self.assertAlmostEqual(self.world.energy(self.planet)["supply"], power * 1.3)
        self.assertAlmostEqual(self.world.production(self.planet)["metal"], rate * 1.15)
        self.assertLess(self.world._project_seconds(self.pid, self.planet, "research", "energy_technology", 5), duration)

    def test_capstone_requires_both_branches_and_maximum_local_lab(self):
        self.player["research"].update(megastructures=10, spacetime_stability=8, dyson_design=1)
        self.planet["buildings"]["lab"] = 11
        self.assertFalse(self.entry("wormhole_theory")["requirements_met"])
        self.planet["buildings"]["lab"] = 12
        self.assertTrue(self.entry("wormhole_theory")["enabled"])
        self.player["research"]["dyson_design"] = 0
        self.assertFalse(self.entry("wormhole_theory")["requirements_met"])

    def test_legacy_world_keeps_accounts_levels_stock_and_ships(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "legacy.sqlite3")
            self.world.data.pop("technology_schema", None)
            self.player.pop("megastructure", None)
            for key in technology.RESEARCH:
                self.player["research"].pop(key, None)
            self.player["research"].update(propulsion=7, weapons=5, antigravity=3)
            self.planet["ships"]["cruiser"] = 17
            before = copy.deepcopy(self.world.data)
            # Keep account/session tables as well as the world snapshot.
            self.world._save()
            import sqlite3
            dest = sqlite3.connect(path)
            self.world.db.backup(dest)
            dest.close()
            restored = World(path, speed=1000, now=self.world.now)
            try:
                new = restored.data["players"][self.pid]
                self.assertEqual(new["research"]["antigravity"], 3)
                self.assertEqual(new["research"]["propulsion"], 7)
                self.assertTrue(all(new["research"][k] == 0 for k in technology.RESEARCH))
                self.assertEqual(new["megastructure"]["dyson_stage"], 0)
                self.assertEqual(restored.data["planets"][self.planet["id"]]["ships"], before["planets"][self.planet["id"]]["ships"])
                self.assertEqual(restored.data["planets"][self.planet["id"]]["resources"], before["planets"][self.planet["id"]]["resources"])
                self.assertTrue(list(Path(folder).rglob("*.sqlite3")))
            finally:
                restored.db.close()


if __name__ == "__main__":
    unittest.main()
