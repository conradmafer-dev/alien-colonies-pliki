"""Launch policy: inactive galaxies, paid expansion and one-time bootstrap."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app
import swarm

NOW = 2_000_000.0


class SwarmLaunchTests(unittest.TestCase):
    def setUp(self):
        self.clock = patch.object(app.time, "time", return_value=NOW)
        self.clock.start()
        self.world = app.World(":memory:", now=NOW)

    def tearDown(self):
        self.world.close()
        self.clock.stop()

    def nests(self, galaxy=None):
        return [p for p in self.world.data["planets"].values()
                if p["owner_id"] == swarm.OWNER_ID
                and (galaxy is None or p["galaxy_id"] == galaxy)]

    def empty(self, galaxy):
        return [p for p in self.world.data["planets"].values()
                if p["owner_type"] == "empty" and p["galaxy_id"] == galaxy]

    def player(self):
        self.world.register("Launch Settler", "test-password-123")
        return next(iter(self.world.data["players"].values()))

    def settle_fixture(self, player, galaxy):
        planet = self.empty(galaxy)[0]
        planet.update(owner_id=player["id"], owner_type="player")
        return planet

    def flight(self, player, target, mission="colonize"):
        f = dict(id="launch-test-flight", owner_id=player["id"],
                 origin_id=player["home_id"], target_id=target["id"], mission=mission,
                 status="outbound", ships={**app.blank_ships(), "colonizer": 1},
                 cargo=dict.fromkeys(app.RESOURCES, 0), swarm_crystals=0,
                 started_at=NOW, seconds=600, arrives_at=NOW + 600)
        self.world.data["fleets"][f["id"]] = f
        return f

    def test_fresh_world_has_only_one_hive_and_three_rare_crystals(self):
        self.assertEqual(swarm.INITIAL_HIVES, 1)
        self.assertEqual(len(self.nests()), 1)
        hive = self.nests()[0]
        self.assertEqual(hive["galaxy_id"], "g1")
        self.assertEqual(hive["swarm_crystals"], 3)
        self.assertEqual(sum(hive["ships"].values()), 0)
        self.assertEqual(sum(hive["resources"].values()), 0)
        self.assertEqual(sum(hive["defenses"].values()), 0)
        self.assertTrue(all(n == 1 for n in hive["buildings"].values()))
        self.assertIn("seeded_at", self.world.data["alien"]["swarm_activated_galaxies"]["g1"])

    def test_paid_outpost_still_has_zero_rare_crystals(self):
        target = self.empty("g1")[0]
        swarm.seed(target, self.world.now)
        self.assertEqual(target["swarm_kind"], "outpost")
        self.assertEqual(target["swarm_crystals"], 0)
        self.assertEqual(sum(target["resources"].values()) + sum(target["ships"].values()), 0)

    def test_world_topology_and_map_reads_do_not_activate_other_galaxies(self):
        player = self.player()
        for _ in range(3):
            self.world._ensure_universe()
            self.world.state(player["id"])
            self.world._ensure_swarm_activation()
        self.assertEqual({p["galaxy_id"] for p in self.nests()}, {"g1"})
        self.assertEqual(set(self.world.data["alien"]["swarm_activated_galaxies"]), {"g1"})

    def test_unowned_or_unknown_player_planet_is_not_settlement(self):
        target = self.empty("g2")[0]
        target.update(owner_type="player", owner_id="missing-account")
        self.world._ensure_swarm_activation()
        self.assertEqual(self.nests("g2"), [])
        self.assertNotIn("g2", self.world.data["alien"]["swarm_activated_galaxies"])

    def test_scouting_and_outbound_colonizer_do_not_activate(self):
        player = self.player()
        target = self.empty("g2")[0]
        self.world._capture_planetary_intel(player["id"], target)
        self.flight(player, target)
        self.world._ensure_swarm_activation()
        self.assertEqual(self.nests("g2"), [])
        self.assertNotIn("g2", self.world.data["alien"]["swarm_activated_galaxies"])

    def test_first_settlement_activates_one_hive_with_current_clock(self):
        player = self.player()
        home = self.settle_fixture(player, "g2")
        before = copy.deepcopy(home)
        self.world.now += 20 * 86400
        seeded = self.world._ensure_swarm_activation()
        hive, = self.nests("g2")
        self.assertEqual(seeded, [hive["id"]])
        self.assertEqual(home, before)
        self.assertEqual(hive["swarm_established_at"], self.world.now)
        self.assertEqual(hive["swarm_crystals"], 3)
        self.assertEqual(sum(hive["resources"].values()), 0)
        self.assertEqual(self.world.data["alien"]["swarm_next_colonization_by_galaxy"]["g2"],
                         self.world.now + swarm.COLONY_MATURITY_SECONDS)
        self.assertFalse(self.world._swarm_expansion_due(hive))
        self.assertEqual(self.nests("g3"), [])
        self.assertEqual(self.world._ensure_swarm_activation(), [])

    def test_player_colony_arrival_activates_immediately(self):
        player = self.player()
        target = self.empty("g3")[0]
        f = self.flight(player, target)
        self.world.now = f["arrives_at"]
        self.world._complete_fleet(f)
        self.assertEqual(target["owner_id"], player["id"])
        self.assertEqual(len(self.nests("g3")), 1)
        self.assertEqual(self.nests("g2"), [])
        self.assertEqual(self.nests("g3")[0]["swarm_established_at"], self.world.now)

    def test_bootstrap_does_not_take_player_or_reserved_colonizer_planet(self):
        player = self.player()
        self.settle_fixture(player, "g2")
        preferred = self.world.data["planets"]["s45p2"]
        self.flight(player, preferred)
        before = copy.deepcopy(preferred)
        self.world._ensure_swarm_activation()
        self.assertEqual(preferred, before)
        self.assertNotEqual(self.nests("g2")[0]["id"], preferred["id"])

    def test_full_galaxy_waits_for_safe_space_and_never_takes_a_player_world(self):
        player = self.player()
        candidates = self.empty("g2")
        for p in candidates:
            p.update(owner_type="player", owner_id=player["id"])
        before = copy.deepcopy(candidates)
        self.assertEqual(self.world._ensure_swarm_activation(), [])
        self.assertEqual(candidates, before)
        self.assertNotIn("seeded_at", self.world.data["alien"]["swarm_activated_galaxies"]["g2"])
        candidate = candidates[-1]
        candidate.update(owner_type="empty", owner_id="")
        self.flight(player, candidate)
        self.assertEqual(self.world._ensure_swarm_activation(), [])
        self.world.data["fleets"].clear()
        self.assertEqual(self.world._ensure_swarm_activation(), [candidate["id"]])

    def test_existing_nest_is_adopted_without_free_refill_or_new_clock(self):
        player = self.player()
        self.settle_fixture(player, "g2")
        old = self.empty("g2")[0]
        swarm.seed(old, NOW - 500, hive=False)
        old["swarm_crystals"] = 1
        before = copy.deepcopy(old)
        self.assertEqual(self.world._ensure_swarm_activation(), [])
        self.assertEqual(old, before)
        self.assertEqual(self.nests("g2"), [old])

    def test_erased_last_nest_does_not_respawn_after_turn_or_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.world.close()
            db = Path(tmp) / "world.sqlite3"
            self.world = app.World(db, now=NOW)
            player = self.player()
            self.settle_fixture(player, "g2")
            self.world._ensure_swarm_activation()
            hive, = self.nests("g2")
            hive.update(owner_type="empty", owner_id="")
            marker = copy.deepcopy(self.world.data["alien"]["swarm_activated_galaxies"]["g2"])
            self.world._alien_turn()
            self.assertEqual(self.nests("g2"), [])
            self.world.close()
            self.world = app.World(db, now=NOW + 600)
            self.world._alien_turn()
            self.assertEqual(self.nests("g2"), [])
            self.assertEqual(self.world.data["alien"]["swarm_activated_galaxies"]["g2"], marker)
            self.world.close()
            self.world = app.World(":memory:", now=NOW)

    def test_npc_reset_only_seeds_eligible_galaxies(self):
        player = self.player()
        self.settle_fixture(player, "g3")
        self.world.data.pop("swarm_reset_id")
        with self.world._atomic():
            self.world._apply_swarm_reset()
        self.assertEqual({p["galaxy_id"] for p in self.nests()}, {"g1", "g3"})
        self.assertTrue(all(p["swarm_crystals"] == 3 for p in self.nests()))
        self.assertEqual(set(self.world.data["alien"]["swarm_activated_galaxies"]), {"g1", "g3"})

    def test_slow_expansion_limits_remain(self):
        self.assertEqual(swarm.EXPANSION_SECONDS, 24 * 3600)
        self.assertEqual(swarm.ORIGIN_EXPANSION_SECONDS, 48 * 3600)
        self.assertEqual(swarm.COLONY_MATURITY_SECONDS, 24 * 3600)
        self.assertEqual(swarm.MAX_COLONIES_PER_GALAXY, 40)


if __name__ == "__main__":
    unittest.main()
