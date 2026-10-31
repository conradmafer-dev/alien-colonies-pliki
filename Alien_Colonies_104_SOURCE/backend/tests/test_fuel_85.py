"""Reference examples, map adaptation and actual payment tests for fuel85."""
import copy
import math
from unittest.mock import patch
import unittest

import app
import flight_balance85 as fuel85
from galaxies import JUMP_BASE_FUEL, JUMP_FUEL_PER_MASS, separation
import swarm


class FuelFormula85(unittest.TestCase):
    def test_official_mixed_fleet_example(self):
        # Gameforge Formula Thread v3: cruiser, battleship, recycler, one system.
        specs = {k: (None,) * 7 + (fuel, speed) for k, fuel, speed in
                 [('cruiser', 300, 27000), ('battleship', 500, 22000), ('recycler', 300, 3200)]}
        self.assertEqual(fuel85.fuel_cost(specs, dict.fromkeys(specs, 1), 2795), 216)

    def test_aggregate_rounding_and_full_speed_reference(self):
        specs = {'large_cargo': (None,) * 7 + (50, 7500)}
        self.assertEqual(fuel85.fuel_cost(specs, {'large_cargo': 100}, 1005), 575)
        self.assertEqual(fuel85.fuel_cost(specs, {'large_cargo': 100}, 20000), 11430)
        # Floor of one is charged once, including a complete discount.
        self.assertEqual(fuel85.fuel_cost(specs, {'large_cargo': 100}, 20000, 0), 1)

    def test_map_distance_and_mixed_speed_effect(self):
        self.assertEqual(fuel85.distance(galaxy_gap=0, same_system=True, slot_delta=-3), 1015)
        self.assertEqual(fuel85.distance(galaxy_gap=0, same_system=False, slot_delta=3, lane_distance=.6), 2757)
        self.assertEqual(fuel85.distance(galaxy_gap=2.5, same_system=False, slot_delta=3), 50000)
        specs = {'fast': (None,) * 7 + (500, 4), 'slow': (None,) * 7 + (1, .1)}
        self.assertLess(fuel85.fuel_cost(specs, {'fast': 100, 'slow': 1}, 20000),
                        fuel85.fuel_cost(specs, {'fast': 100}, 20000))
        with self.assertRaises(ValueError):
            fuel85.fuel_cost(specs, {}, 20000)


class FuelRuntime85(unittest.TestCase):
    def setUp(self):
        self.w = app.World(':memory:', now=1900000000)
        self.addCleanup(self.w.close)
        state = self.w.register('Fuel85Pilot', 'private-fuel-tests-85')['state']
        self.owner = state['player']['id']
        self.w.action(self.owner, {'type': 'choose_race', 'race_id': 'zetans'})
        self.p = self.w._owned(self.owner)
        self.p['resources'] = dict.fromkeys(app.RESOURCES, 1000000.0)
        self.p['ships'] = {**app.blank_ships(), 'scout': 100, 'freighter': 100}
        self.target = self.w.data['planets']['s31p1']
        self.payload = {'type': 'fleet', 'planet_id': self.p['id'], 'target_id': self.target['id'],
                        'mission': 'scout', 'ships': {'scout': 1, 'freighter': 100}, 'cargo': {}}

    def test_all_races_and_all_hulls_near_system_and_galaxy_routes(self):
        same = next(p for p in self.w.data['planets'].values()
                    if p['system_id'] == self.p['system_id'] and p['id'] != self.p['id'])
        neighbor_id = next(iter(self.w._galaxy_navigation().edges[self.p['system_id']]))
        neighbor = next(p for p in self.w.data['planets'].values() if p['system_id'] == neighbor_id)
        for race, factor in [('zetans', .9), ('automatons', 1.1), ('symbionts', .9)]:
            self.w._player(self.owner)['race_id'] = race
            specs = self.w._specs(self.owner, 'ships')
            for key in specs:
                for target in [same, neighbor, self.target]:
                    with self.subTest(race=race, hull=key, target=target['id']):
                        dist = self.w._fuel_distance(self.p, target)
                        expected = 1 + math.floor(100 * specs[key][7] * dist / 35000 * 4 + .5)
                        seconds, fuel = self.w._flight_numbers(self.p, target, {key: 100})
                        self.assertEqual(fuel, expected)
                        self.assertGreaterEqual(seconds, 8)
        self.assertEqual(self.w._route_details(self.p, self.target)['fuel_model'], 'ogame_lanes_v85')

    def test_tech_and_building_discounts_once_and_speed_does_not_tax_fuel(self):
        fleet = {'freighter': 100}
        baseline = self.w._flight_numbers(self.p, self.target, fleet)
        # Propulsion and universe speed alter travel time, not the fuel bill.
        self.w.speed *= 5
        faster = self.w._flight_numbers(self.p, self.target, fleet, 10)
        self.assertEqual(faster[1], baseline[1])
        self.assertLess(faster[0], baseline[0])
        with patch.object(self.w, '_building_effects', return_value={'fleet_fuel_reduction': .2}):
            discounted = self.w._flight_numbers(self.p, self.target, fleet)[1]
        raw = 100 * 45 * 20000 / 35000 * 4
        self.assertEqual(discounted, 1 + math.floor(raw * .8 + .5))

    def test_preview_authoritative_charge_idempotency_and_free_return(self):
        payload = {**self.payload, 'request_id': 'fuel85-charge-once', 'fuel_cost': 0, 'seconds': 1}
        before = copy.deepcopy(self.w.data)
        quote = self.w.preview(self.owner, payload)
        self.assertEqual(self.w.data, before)
        self.assertLess(quote['fuel_cost'], 20000)
        self.assertGreater(quote['fuel_cost'], 1)
        start_fuel = self.p['resources']['fuel']
        self.w.action(self.owner, payload)
        self.w.action(self.owner, payload)
        self.assertEqual(self.p['resources']['fuel'], start_fuel - quote['fuel_cost'])
        fleet = next(f for f in self.w.data['fleets'].values() if f['owner_id'] == self.owner)
        self.assertEqual(fleet['fuel_paid'], quote['fuel_cost'])
        self.assertEqual(fleet['seconds'], quote['seconds'])
        for _ in range(2):
            self.w.now = fleet['arrives_at']
            self.w._complete_fleet(fleet)
            self.assertEqual(self.p['resources']['fuel'], start_fuel - quote['fuel_cost'])
        self.assertNotIn(fleet['id'], self.w.data['fleets'])

    def test_insufficient_fuel_cannot_be_bypassed(self):
        self.p['resources']['fuel'] = 0
        payload = {**self.payload, 'allow_unaffordable': True, 'fuel_cost': 0, 'affordable': True}
        quote = self.w.preview(self.owner, payload)
        self.assertFalse(quote['affordable'])
        before = copy.deepcopy(self.w.data)
        with self.assertRaises(app.GameError):
            self.w.action(self.owner, payload)
        self.assertEqual(self.w.data, before)

    def test_swarm_keeps_original_flight_fuel(self):
        origin = next(p for p in self.w.data['planets'].values() if p['owner_id'] == swarm.OWNER_ID)
        specs = self.w._specs(swarm.OWNER_ID, 'ships')
        target = self.target
        key = next(iter(specs))
        mass = specs[key][7] * 3
        gap = separation(self.w._galaxy_id(origin), self.w._galaxy_id(target))
        factor = 1 - self.w._building_effects(origin).get('fleet_fuel_reduction', 0)
        expected = math.ceil(gap * (JUMP_BASE_FUEL + JUMP_FUEL_PER_MASS * mass * factor))
        self.assertEqual(self.w._flight_numbers(origin, target, {key: 3})[1], expected)


if __name__ == '__main__':
    unittest.main()
