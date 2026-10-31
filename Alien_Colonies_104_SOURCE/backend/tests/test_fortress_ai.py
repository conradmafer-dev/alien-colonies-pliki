"""Strategic invariants for slow, budgeted fortress AI (0.4.0)."""
import copy
import unittest

from server import swarm
from server.main import scaled_cost
from tests.world_fixture import LocalTestWorld as World

START = 1_900_000_000.0


class FortressAI(unittest.TestCase):
    def setUp(self):
        self.world = World(':memory:', now=START)

    def tearDown(self):
        self.world.close()

    def hives(self):
        return [p for p in self.world.data['planets'].values() if p['owner_id'] == swarm.OWNER_ID]

    def empty(self):
        return next(p for p in self.world.data['planets'].values() if p['owner_type'] == 'empty')

    def prepared_origin(self, planet=None):
        planet = planet or self.hives()[0]
        planet['queue'] = []
        planet['ships'].update(frigate=1800, cruiser=300, colonizer=2)
        planet['resources'] = dict.fromkeys(('metal', 'crystal', 'fuel'), 100_000_000.0)
        return planet

    def escort(self):
        ships = dict.fromkeys(swarm.SHIPS, 0)
        ships.update(swarm.EXPANSION_ESCORT)
        ships['colonizer'] = 1
        return ships

    def player(self):
        pid = self.world.register('Fortress Tester', 'password-123')['state']['player']['id']
        self.world.data['players'][pid]['protected_until'] = 0
        return pid, self.world._owned(pid)

    def test_six_strong_initial_fortresses_have_one_time_stock(self):
        self.assertEqual(len(self.hives()), swarm.INITIAL_HIVES)
        for planet in self.hives():
            self.assertEqual(swarm.kind(planet), 'hive')
            self.assertTrue(swarm.ready(planet))
            self.assertEqual(planet['swarm_crystals'], 3)
            self.assertEqual(planet['ships']['frigate'], 360)
            self.assertEqual(planet['ships']['cruiser'], 60)
            self.assertEqual(self.world._swarm_weapon_level(planet), 6)
        self.assertEqual(self.world.data['alien']['swarm_next_colonization_at'], START + 7 * 86400)

    def test_global_expansion_gate_includes_first_and_failed_colonization(self):
        origin, other = [self.prepared_origin(p) for p in self.hives()[:2]]
        target = self.empty()
        before = copy.deepcopy(origin)
        self.world.now = START + swarm.EXPANSION_SECONDS - 1
        self.assertIsNone(self.world._swarm_launch(origin, target, 'colonize', self.escort()))
        self.assertEqual(origin, before)
        self.world.now += 1
        fleet = self.world._swarm_launch(origin, target, 'colonize', self.escort())
        self.assertIsNotNone(fleet)
        self.assertEqual(self.world.data['alien']['swarm_next_colonization_at'], self.world.now + swarm.EXPANSION_SECONDS)
        self.world.data['fleets'].pop(fleet['id'])  # Intercepted/failed mission still consumes the gate.
        self.assertIsNone(self.world._swarm_launch(other, target, 'colonize', self.escort()))
        self.world.now += swarm.EXPANSION_SECONDS
        self.assertIsNotNone(self.world._swarm_launch(other, target, 'colonize', self.escort()))

    def test_expansion_moves_paid_escort_and_new_colony_gets_no_free_stock(self):
        origin = self.prepared_origin()
        target = self.empty()
        self.world.now = START + swarm.EXPANSION_SECONDS
        ships_before = dict(origin['ships'])
        fuel_before = origin['resources']['fuel']
        fleet = self.world._swarm_launch(origin, target, 'colonize', self.escort())
        self.assertLess(origin['resources']['fuel'], fuel_before)
        for key, count in self.escort().items():
            self.assertEqual(origin['ships'][key], ships_before[key] - count)
        self.world._complete_fleet(fleet)
        self.assertEqual(target['owner_id'], swarm.OWNER_ID)
        self.assertEqual(target['swarm_crystals'], 0)
        self.assertEqual(target['ships']['frigate'], 180)
        self.assertEqual(target['ships']['cruiser'], 30)
        self.assertEqual(target['ships']['colonizer'], 0)
        self.assertTrue(swarm.ready(target))

    def test_no_weak_or_home_depleting_colony_expeditions(self):
        origin = self.hives()[0]
        origin['ships']['colonizer'] = 1
        self.world.now = START + swarm.EXPANSION_SECONDS
        # New player ship roles never become NPC units, even at zero count.
        original = copy.deepcopy(origin)
        for extra in ({'interceptor': 0}, {'siege': 1}, {'unknown_ship': 0}):
            self.assertIsNone(self.world._swarm_launch(origin, self.empty(), 'colonize', {**self.escort(), **extra}))
            self.assertEqual(origin, original)
        ships = self.escort()
        ships['frigate'] = 2
        before = copy.deepcopy(origin)
        self.assertIsNone(self.world._swarm_launch(origin, self.empty(), 'colonize', ships))
        self.assertEqual(origin, before)
        origin['ships']['frigate'] = 180
        self.assertIsNone(self.world._swarm_launch(origin, self.empty(), 'colonize', self.escort()))

    def test_colony_count_cap_applies_even_after_gate(self):
        origin = self.prepared_origin()
        for _ in range(swarm.MAX_COLONIES - len(self.hives())):
            swarm.seed(self.empty(), START, hive=True)
        self.world.now = START + swarm.EXPANSION_SECONDS
        self.assertIsNone(self.world._swarm_launch(origin, self.empty(), 'colonize', self.escort()))
        self.assertEqual(len(self.hives()), swarm.MAX_COLONIES)

    def test_any_empty_world_forbids_player_attacks_even_at_colony_cap(self):
        pid, target = self.player()
        origin = self.prepared_origin()
        for _ in range(swarm.MAX_COLONIES - len(self.hives())):
            swarm.seed(self.empty(), START, hive=True)
        self.world.now = START + 20 * 86400
        origin['swarm_next_attack_at'] = 0
        fleet = self.escort()
        fleet['colonizer'] = 0
        before = copy.deepcopy(origin)
        self.assertIsNone(self.world._swarm_launch(origin, target, 'attack', fleet))
        self.assertEqual(origin, before)
        # Occupied galaxy permits an attack, preserving the original daily clock.
        for planet in self.world.data['planets'].values():
            if planet['owner_type'] == 'empty':
                planet.update(owner_type='player', owner_id=pid)
        launched = self.world._swarm_launch(origin, target, 'attack', fleet)
        self.assertIsNotNone(launched)
        self.assertEqual(launched['swarm_weapon_level'], 6)
        self.assertEqual(origin['swarm_next_attack_at'], self.world.now + 86400)
        self.assertIsNone(self.world._swarm_launch(origin, target, 'attack', fleet))

    def test_training_requires_resources_and_completion_not_ai_visits(self):
        planet = self.hives()[0]
        before = dict(planet['ships'])
        resources = dict(planet['resources'])
        self.assertTrue(self.world._swarm_queue(planet, 'ship', 'cruiser', 4))
        cost = scaled_cost(swarm.SHIPS['cruiser'][2], 0)
        for key in cost:
            self.assertEqual(planet['resources'][key], resources[key] - 4 * cost[key])
        self.assertEqual(planet['ships'], before)
        self.assertGreater(planet['queue'][0]['ends_at'], self.world.now)
        for _ in range(30):
            self.world._alien_turn()
        self.assertEqual(planet['ships'], before)
        self.world._complete_queue(planet)
        self.assertEqual(planet['ships']['cruiser'], before['cruiser'] + 4)
        planet['resources'] = dict.fromkeys(('metal', 'crystal', 'fuel'), 0)
        state = copy.deepcopy(planet)
        self.assertFalse(self.world._swarm_queue(planet, 'ship', 'cruiser'))
        self.assertEqual(planet, state)

    def test_defense_repair_is_prioritized_over_economy_and_research(self):
        planet = self.prepared_origin()
        planet['ships'].update(frigate=0, cruiser=0)
        self.world.now += 10 * 86400
        self.world._alien_turn()
        self.assertEqual(planet['queue'][0]['kind'], 'ship')
        self.assertIn(planet['queue'][0]['key'], ('frigate', 'cruiser'))
        self.assertFalse(self.world._swarm_ready(planet))

    def test_weapons_are_paid_building_research(self):
        planet = self.hives()[0]
        resources = dict(planet['resources'])
        self.assertTrue(self.world._swarm_queue(planet, 'build', 'lab'))
        self.assertEqual(self.world._swarm_weapon_level(planet), 6)
        self.assertLess(planet['resources']['metal'], resources['metal'])
        self.world._complete_queue(planet)
        self.assertEqual(self.world._swarm_weapon_level(planet), 7)

    def test_three_days_grow_facilities_defense_and_weapons_without_new_colonies(self):
        originals = {p['id']: copy.deepcopy(p) for p in self.hives()}
        for dt in range(900, 3 * 86400 + 1, 900):
            self.world.advance(START + dt)
        self.assertEqual(len(self.hives()), swarm.INITIAL_HIVES)
        self.assertFalse(any(f['mission'] == 'colonize' for f in self.world.data['fleets'].values()))
        for planet in self.hives():
            original = originals[planet['id']]
            self.assertGreater(planet['buildings']['metal_mine'], original['buildings']['metal_mine'])
            self.assertGreater(planet['buildings']['lab'], original['buildings']['lab'])
            self.assertGreater(planet['ships']['frigate'], original['ships']['frigate'])
            self.assertGreater(planet['ships']['cruiser'], original['ships']['cruiser'])

    def test_public_stock_timing_is_precise_and_pauses_when_defenseless(self):
        planet = self.hives()[0]
        planet['swarm_crystals'] = 2.5
        view = swarm.public_planet(planet, START)
        self.assertEqual(view['swarm_crystals_stock'], 2)
        self.assertEqual(view['swarm_crystals_capacity'], 6)
        self.assertEqual(view['swarm_crystals_next_at'], START + 90 * 3600)
        self.assertTrue(view['swarm_crystals_regenerating'])
        planet['ships']['cruiser'] = 0
        view = swarm.public_planet(planet, START)
        self.assertEqual(view['swarm_crystals_stock'], 2)
        self.assertEqual(view['swarm_crystals_next_at'], 0)
        self.assertFalse(view['swarm_crystals_ready'])
        self.assertIn('wstrzymana', view['swarm_crystals_hint'])

    def test_age_only_increases_purchase_targets_and_never_spawns_ships(self):
        planet = self.hives()[0]
        original = copy.deepcopy(planet)
        young = swarm.defense_targets(planet, START)
        old = swarm.defense_targets(planet, START + 100 * 86400)
        self.assertGreater(old['frigate'], young['frigate'])
        self.assertGreater(old['cruiser'], young['cruiser'])
        self.assertEqual(planet, original)
        self.assertTrue(swarm.ready(planet))


if __name__ == '__main__':
    unittest.main()
