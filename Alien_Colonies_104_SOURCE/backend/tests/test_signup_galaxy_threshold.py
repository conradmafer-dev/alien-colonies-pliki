"""New empires start in empty systems and move galaxy at 50% occupied systems.

Run against the real production World, using the persistent world snapshot,
registration transaction and pending colonizer reservations.
"""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app
import swarm

NOW = 2_000_000.0
PASSWORD = "signup-system-threshold"


def systems_in(world, galaxy):
    return [s for s in world.data["systems"] if s["galaxy_id"] == galaxy]


def planets_in_system(world, system):
    return [world.data["planets"][pid] for pid in system["planet_ids"]]


def occupied_system_ids(world, galaxy):
    ids = {s["id"] for s in systems_in(world, galaxy)}
    return {p["system_id"] for p in world.data["planets"].values()
            if p["system_id"] in ids and p["owner_type"] != "empty"}


def occupy_systems_to(world, galaxy, target, owner="fixture-owner"):
    settled = occupied_system_ids(world, galaxy)
    if target < len(settled) or target > len(systems_in(world, galaxy)):
        raise AssertionError("Invalid fixture occupancy")
    for system in systems_in(world, galaxy):
        if len(settled) >= target:
            break
        if system["id"] in settled:
            continue
        planet = planets_in_system(world, system)[0]
        planet.update(owner_type="player", owner_id=owner)
        settled.add(system["id"])


def half_ceil(world, galaxy):
    return (len(systems_in(world, galaxy)) + 1) // 2


def home(world, result):
    player_id = result["state"]["player"]["id"]
    return world.data["planets"][world._player(player_id)["home_id"]]


class SignupSystemThresholdTests(unittest.TestCase):
    def setUp(self):
        self.world = app.World(":memory:", now=NOW)

    def tearDown(self):
        self.world.close()

    def selected_galaxy(self, candidates=None):
        candidates = (self.world._available_start_planets()
                      if candidates is None else candidates)
        planet = self.world._choose_start_planet(candidates)
        return self.world._galaxy_id(planet)

    def test_new_players_start_in_different_empty_systems(self):
        first = self.world.register("FirstNew", PASSWORD)
        first_home = home(self.world, first)
        self.assertEqual(self.world._galaxy_id(first_home), "g1")
        first_system = first_home["system_id"]
        self.assertTrue(all(p["system_id"] != first_system
                            for p in self.world._available_start_planets()))
        second = self.world.register("SecondNew", PASSWORD)
        second_home = home(self.world, second)
        self.assertEqual(self.world._galaxy_id(second_home), "g1")
        self.assertNotEqual(second_home["system_id"], first_system)

    def test_khar_occupied_system_is_never_a_start(self):
        khar_systems = {p["system_id"] for p in self.world.data["planets"].values()
                        if p["owner_type"] not in ("empty", "player")}
        self.assertTrue(khar_systems)
        self.assertTrue(all(p["system_id"] not in khar_systems
                            for p in self.world._available_start_planets()))

    def test_below_half_uses_first_galaxy(self):
        occupy_systems_to(self.world, "g1", half_ceil(self.world, "g1") - 1)
        self.assertEqual(self.selected_galaxy(), "g1")

    def test_exactly_half_moves_to_next_galaxy(self):
        occupy_systems_to(self.world, "g1", half_ceil(self.world, "g1"))
        self.assertEqual(self.selected_galaxy(), "g2")
        occupy_systems_to(self.world, "g2", half_ceil(self.world, "g2"))
        self.assertEqual(self.selected_galaxy(), "g3")

    def test_skips_multiple_half_filled_galaxies(self):
        for galaxy in ("g1", "g2", "g3"):
            occupy_systems_to(self.world, galaxy, half_ceil(self.world, galaxy))
        self.assertEqual(self.selected_galaxy(), "g4")

    def test_multiple_colonies_in_one_system_only_count_once(self):
        occupy_systems_to(self.world, "g1", half_ceil(self.world, "g1") - 1)
        populated = next(s for s in systems_in(self.world, "g1")
                         if s["id"] in occupied_system_ids(self.world, "g1")
                         and any(p["owner_type"] == "empty" for p in planets_in_system(self.world, s)))
        another = next(p for p in planets_in_system(self.world, populated)
                       if p["owner_type"] == "empty")
        another.update(owner_type="player", owner_id="fixture-owner")
        self.assertEqual(self.selected_galaxy(), "g1")
        self.assertNotIn(another, self.world._available_start_planets())

    def test_another_khar_system_advances_to_next_galaxy(self):
        occupy_systems_to(self.world, "g1", half_ceil(self.world, "g1") - 1)
        vacant = next(s for s in systems_in(self.world, "g1")
                      if s["id"] not in occupied_system_ids(self.world, "g1"))
        nest = planets_in_system(self.world, vacant)[0]
        swarm.seed(nest, NOW)
        self.assertEqual(self.selected_galaxy(), "g2")

    def test_pending_colonization_blocks_entire_system_but_not_threshold(self):
        vacant = next(s for s in systems_in(self.world, "g1")
                      if s["id"] not in occupied_system_ids(self.world, "g1"))
        reserved = planets_in_system(self.world, vacant)[0]
        self.world.data["fleets"]["test-reservation"] = {
            "target_id": reserved["id"], "mission": "colonize", "status": "outbound"}
        self.assertTrue(all(p["system_id"] != vacant["id"]
                            for p in self.world._available_start_planets()))
        with self.assertRaises(app.GameError):
            self.world._choose_start_planet(planets_in_system(self.world, vacant))
        self.assertEqual(self.selected_galaxy(), "g1")

    def test_no_available_first_galaxy_skips_it_even_when_below_half(self):
        reserved_count = 0
        settled = occupied_system_ids(self.world, "g1")
        for system in systems_in(self.world, "g1"):
            if system["id"] in settled:
                continue
            self.world.data["fleets"][f"reserved-{reserved_count}"] = {
                "target_id": planets_in_system(self.world, system)[0]["id"],
                "mission": "colonize", "status": "outbound"}
            reserved_count += 1
        self.assertEqual(self.selected_galaxy(), "g2")
        self.assertEqual(len(occupied_system_ids(self.world, "g1")), 1)

    def test_real_registration_moves_at_threshold_and_preserves_older_home(self):
        established = self.world.register("Established", PASSWORD)
        old_owner = established["state"]["player"]["id"]
        old_home = home(self.world, established)
        snapshot = copy.deepcopy(old_home)
        occupy_systems_to(self.world, "g1", half_ceil(self.world, "g1") - 1, old_owner)
        crossing = self.world.register("Crossing", PASSWORD)
        self.assertEqual(self.world._galaxy_id(home(self.world, crossing)), "g1")
        later = self.world.register("NextGalaxy", PASSWORD)
        self.assertEqual(self.world._galaxy_id(home(self.world, later)), "g2")
        self.assertEqual(self.world._player(old_owner)["home_id"], snapshot["id"])
        self.assertEqual(old_home, snapshot)

    def test_no_vacant_system_blocks_signup_even_if_planets_remain_empty(self):
        established = self.world.register("Original", PASSWORD)
        first_player = established["state"]["player"]["id"]
        for galaxy in app.GALAXIES_BY_ID:
            occupy_systems_to(self.world, galaxy, len(systems_in(self.world, galaxy)),
                              first_player)
        self.assertTrue(any(p["owner_type"] == "empty" for p in self.world.data["planets"].values()))
        self.assertFalse(self.world._available_start_planets())
        with self.assertRaises(app.GameError) as caught:
            self.world.register("NoSystem", PASSWORD)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(len(self.world.data["players"]), 1)
        self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 1)
        self.assertFalse(self.world.state(first_player)["sector"]["registration_open"])

    def test_freeing_a_settled_system_reopens_earlier_galaxy(self):
        occupy_systems_to(self.world, "g1", half_ceil(self.world, "g1"))
        self.assertEqual(self.selected_galaxy(), "g2")
        to_clear = next(s for s in systems_in(self.world, "g1")
                        if any(p["owner_type"] == "player" for p in planets_in_system(self.world, s)))
        for planet in planets_in_system(self.world, to_clear):
            planet.update(owner_type="empty", owner_id="")
        self.assertEqual(self.selected_galaxy(), "g1")

    def test_fallback_uses_least_occupied_ratio_after_all_cross_half(self):
        for galaxy in app.GALAXIES_BY_ID:
            occupy_systems_to(self.world, galaxy, half_ceil(self.world, galaxy)
                              + (0 if galaxy == "g2" else 1))
        self.assertEqual(self.selected_galaxy(), "g2")


class SignupPersistenceTests(unittest.TestCase):
    def test_restart_keeps_old_home_and_new_signup_uses_correct_galaxy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "signup.sqlite3")
            world = app.World(path, now=NOW)
            try:
                previous = world.register("Persistent", PASSWORD)
                owner = previous["state"]["player"]["id"]
                home_id = world._player(owner)["home_id"]
                occupy_systems_to(world, "g1", half_ceil(world, "g1"), owner)
                world._save()
            finally:
                world.close()
            restarted = app.World(path, now=NOW)
            try:
                next_player = restarted.register("AfterRestart", PASSWORD)
                self.assertEqual(restarted._galaxy_id(home(restarted, next_player)), "g2")
                self.assertEqual(restarted._player(owner)["home_id"], home_id)
            finally:
                restarted.close()


if __name__ == "__main__":
    unittest.main()
