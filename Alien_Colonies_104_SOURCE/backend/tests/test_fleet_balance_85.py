"""Runtime coverage for release-85 unit economics; never uses a live database."""
from __future__ import annotations

import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import defenses
import fleet_balance85
import ogame_economy
import races
import swarm


# Reference HP is actual hull points, not OGame structural integrity.
REFERENCE = {
    'scout': (1, 100, 5, 1), 'cargo': (5, 400, 5000, 10),
    'colonizer': (50, 3000, 7500, 1000), 'frigate': (50, 400, 50, 20),
    'cruiser': (400, 2700, 800, 300), 'interceptor': (150, 1000, 100, 75),
    'freighter': (5, 1200, 25000, 50), 'siege': (1000, 7500, 500, 700),
    'battleship': (1000, 6000, 1500, 500), 'dreadnought': (2000, 11000, 2000, 1000),
    'flagship': (2800, 14000, 10000, 1100), 'titan': (200000, 900000, 1000000, 1),
}
FACTORS = {'zetans': (1, .9, 1, .9), 'automatons': (1, 1.1, 1, 1.1),
           'symbionts': (.9, 1.05, 1.1, .9)}


class FleetBalance85Tests(unittest.TestCase):
    def setUp(self):
        self.w = app.World(':memory:', now=1900000000)
        self.addCleanup(self.w.close)
        self.people = {}
        self.seq = 0
        for race in FACTORS:
            state = self.w.register('Fleet85_' + race, 'LocalAudit-94751')['state']
            owner = state['player']['id']
            self.w.action(owner, {'type': 'choose_race', 'race_id': race})
            planet = self.w._owned(owner)
            planet['resources'] = dict.fromkeys(app.RESOURCES, 0.0)
            planet['ships'] = app.blank_ships()
            planet['queue'] = []
            self.people[race] = (owner, planet)
        self.w.data['alien']['next_expansion_at'] = self.w.now + 10**9

    def catalog(self, race):
        owner, planet = self.people[race]
        return self.w._catalog(owner, planet)

    def fleet(self, race, target, ships=None):
        owner, origin = self.people[race]
        self.seq += 1
        f = {'id': 'audit85_' + str(self.seq), 'owner_id': owner,
             'origin_id': origin['id'], 'target_id': target['id'],
             'ships': {**app.blank_ships(), **(ships or {'titan': 100})},
             'seconds': 1, 'return_seconds': 1, 'started_at': self.w.now,
             'arrives_at': self.w.now + 1, 'mission': 'attack', 'status': 'outbound',
             'building_effects': self.w._building_effects(origin)}
        self.w.data['fleets'][f['id']] = f
        return f

    def replay(self, owner):
        return next(r['battle_replay'] for r in self.w._player(owner)['reports'] if r.get('battle_replay'))

    def test_all_36_catalog_units_have_new_stats_original_speeds_and_prices(self):
        seen = 0
        for race, factors in FACTORS.items():
            original = copy.deepcopy(races.RACES[race]['ships'])
            owner, _ = self.people[race]
            specs = self.w._specs(owner, 'ships')
            catalog = self.catalog(race)['ships']
            self.assertEqual(len(catalog), 12)
            for item in catalog:
                key = item['key']
                with self.subTest(race=race, key=key):
                    expected = [round(x * factor, 6) for x, factor in zip(REFERENCE[key], factors)]
                    if key == 'scout':
                        expected[0] = 1
                    for field, value in zip(('attack', 'hull', 'capacity', 'fuel'), expected):
                        self.assertAlmostEqual(item[field], value)
                    self.assertEqual(item['speed'], original[key][8])
                    self.assertEqual(item['cost'], dict(zip(app.RESOURCES, ogame_economy.SHIP_BASES[key])))
                    self.assertEqual(tuple(specs[key][4:8]), tuple(expected))
                    seen += 1
            self.assertEqual(races.RACES[race]['ships'], original)
        self.assertEqual(seen, 36)

    def test_player_defenses_prices_stats_and_traits_are_consistent(self):
        expected = {'zetans': ('phase_sentinel', 250, 800, (6000, 2000, 0)),
                    'automatons': ('iron_bastion', 1100, 3500, (20000, 15000, 2000)),
                    'symbionts': ('rooted_spore', 150, 800, (2000, 6000, 0))}
        for race, (key, attack, hull, price) in expected.items():
            with self.subTest(race=race):
                entry = self.catalog(race)['defenses'][0]
                self.assertEqual(entry['key'], key)
                self.assertEqual((entry['attack'], entry['hull']), (attack, hull))
                self.assertEqual(entry['cost'], dict(zip(app.RESOURCES, price)))
                self.assertTrue(entry['stationary'])
        self.assertEqual(defenses.TRAITS['phase_sentinel']['first_volley'], 1.5)
        self.assertEqual(defenses.TRAITS['iron_bastion']['damage_reduction'], .25)
        self.assertEqual(defenses.TRAITS['rooted_spore']['regeneration_fraction'], .50)

    def test_weapons_ten_percent_in_catalog_research_details_and_coalitions(self):
        for race in FACTORS:
            owner, planet = self.people[race]
            self.w._player(owner)['research']['weapons'] = 5
            self.w._player(owner)['research']['propulsion'] = 5
            catalog = self.catalog(race)
            for item in catalog['ships'] + catalog['defenses']:
                self.assertAlmostEqual(item['effective_attack'], item['attack'] * 1.5)
            weapons = next(x for x in catalog['research'] if x['key'] == 'weapons')
            propulsion = next(x for x in catalog['research'] if x['key'] == 'propulsion')
            metric = next(x for x in weapons['details']['metrics'] if x['key'] == 'fleet_attack_bonus')
            self.assertEqual((metric['current'], metric['next']), (50, 60))
            self.assertIn('+50%', str(weapons['effect_current']))
            self.assertIn('+75%', str(propulsion['effect_current']))
            form = self.w._coalition_formation(owner, {'cruiser': 2}, 'test_' + race)
            self.assertAlmostEqual(self.w._coalition_power(form, 2),
                                   self.w._specs(owner, 'ships')['cruiser'][4] * 2 * 1.5)

    def test_historical_combat_preserves_84_until_migration_timestamp(self):
        epoch = self.w.now + 100
        self.w.data['economy85_from'] = epoch
        self.w.now = epoch - 1
        for race in FACTORS:
            owner, _ = self.people[race]
            self.w._player(owner)['research']['weapons'] = 4
            specs = self.w._specs(owner, 'ships')
            for key, spec in specs.items():
                self.assertEqual(spec[4:9], races.RACES[race]['ships'][key][4:9])
            for key, spec in self.w._specs(owner, 'defenses').items():
                self.assertEqual(spec[4:6], defenses.specs_for(race)[key][4:6])
            form = self.w._coalition_formation(owner, {'cruiser': 2}, 'legacy_' + race)
            self.assertAlmostEqual(self.w._coalition_power(form, 2), specs['cruiser'][4] * 2 * 1.6)
            self.assertEqual(self.w._unit_construction_cost(owner, 'cruiser', specs['cruiser'])['metal'],
                             specs['cruiser'][2][0])
        owner, _ = self.people['zetans']
        legacy = self.w._specs(owner, 'ships')['cruiser']
        self.assertEqual((legacy[4], legacy[5], legacy[6]), (100, 250, 190))
        self.assertEqual(self.w._unit_construction_cost(owner, 'cruiser', legacy)['metal'], 1050)
        # At the exact release instant all three authorities switch together.
        self.w.now = epoch
        current = self.w._specs(owner, 'ships')['cruiser']
        self.assertEqual((current[4], current[5], current[6]), (400, 2430, 800))
        self.assertEqual(self.w._unit_construction_cost(owner, 'cruiser', current)['metal'], 20000)
        self.assertAlmostEqual(self.w._power({'cruiser': 1}, 4, {'cruiser': current}), 560)

    def test_replay_units_salvos_and_survivors_match_catalog_and_state(self):
        defender, target = self.people['zetans']
        for race in FACTORS:
            owner, _ = self.people[race]
            self.w._player(owner)['research']['weapons'] = 3
            target['ships'] = {**app.blank_ships(), 'cruiser': 1}
            target['defenses'] = {}
            f = self.fleet(race, target)
            before = next(x for x in self.catalog(race)['ships'] if x['key'] == 'titan')
            self.w._battle(f, target)
            record = self.replay(owner)
            self.assertEqual(record['outcome'], 'attacker_wins')
            unit = next(x for x in record['attacker']['units'] if x['key'] == 'titan')
            self.assertEqual((unit['attack'], unit['hull']), (before['attack'], before['hull']))
            self.assertAlmostEqual(record['rounds'][0]['salvos']['attacker'],
                                   before['effective_first_volley_attack'] * 100)
            self.assertEqual(record['final']['attacker']['titan']['count'], f['ships']['titan'])
            self.assertEqual(record['final']['defender']['cruiser']['count'], target['ships']['cruiser'])

    def test_solo_wrecks_use_actual_player_ship_and_defense_prices(self):
        owner, origin = self.people['automatons']
        origin['buildings']['wreck_recycler'] = 5
        _, target = self.people['zetans']
        for key, stationary, expected in (('cruiser', False, 5000), ('titan', False, 1250000),
                                          ('phase_sentinel', True, 1500)):
            with self.subTest(key=key):
                target['ships'] = {**app.blank_ships(), **({key: 1} if not stationary else {})}
                target['defenses'] = {key: 1} if stationary else {}
                f = self.fleet('automatons', target)
                self.w._battle(f, target)
                self.assertEqual(f['cargo']['metal'], expected)
                self.assertEqual(self.replay(owner)['cargo']['metal'], expected)

    def test_alliance_wrecks_use_actual_prices_and_share_once(self):
        owner, origin = self.people['automatons']
        origin['buildings']['wreck_recycler'] = 5
        _, target = self.people['zetans']
        for key, stationary, expected in (('cruiser', False, 5000), ('titan', False, 1250000),
                                          ('phase_sentinel', True, 1500)):
            with self.subTest(key=key):
                target['ships'] = {**app.blank_ships(), **({key: 1} if not stationary else {})}
                target['defenses'] = {key: 1} if stationary else {}
                fleets = [self.fleet('automatons', target), self.fleet('automatons', target)]
                result = self.w._alliance_battle(fleets, target)
                self.assertEqual(result['cargo']['metal'], expected)
                self.assertEqual([f['cargo']['metal'] for f in fleets], [expected // 2] * 2)
                record = self.replay(owner)
                recovered = [p['recovered_metal'] for p in record['participant_results'] if p['side'] == 'attacker']
                self.assertEqual(sum(recovered), expected)

    def test_skill_research_and_unique_combat_traits_stack_on_new_base(self):
        owner, planet = self.people['zetans']
        research = self.w._player(owner)['research']
        research.update(weapons=5, phase_hulls=2, coherent_plasma=3, folding_cargo=2, capital_weapons=2)
        items = {x['key']: x for x in self.catalog('zetans')['ships']}
        self.assertAlmostEqual(items['flagship']['attack'], 2800 * 1.24 * 1.08)
        self.assertAlmostEqual(items['flagship']['hull'], 14000 * .9 * 1.16)
        self.assertAlmostEqual(items['flagship']['capacity'], 10000 * 1.24)
        self.assertAlmostEqual(items['flagship']['effective_first_volley_attack'], 2800 * 1.24 * 1.08 * 1.5 * 1.35 * 1.6)
        self.assertEqual(items['flagship']['first_volley_multiplier'], 1.35 * 1.6)
        auto = next(x for x in self.catalog('automatons')['ships'] if x['key'] == 'flagship')
        sym = next(x for x in self.catalog('symbionts')['ships'] if x['key'] == 'flagship')
        self.assertAlmostEqual(auto['damage_reduction'], .296)
        self.assertEqual(sym['regeneration_fraction'], .6)

    def test_fuel_coefficients_receive_existing_discounts_exactly_once(self):
        owner, _ = self.people['symbionts']
        self.w._player(owner)['research'].update(metabolic_drive=3, graviton_control=2)
        spec = self.w._specs(owner, 'ships')['cruiser']
        self.assertAlmostEqual(spec[7], 300 * .9 * (1 - .18 - .04))

    def test_alliance_holding_uses_one_tenth_coefficient_and_launch_discount(self):
        owner, origin = self.people['zetans']
        ally, target = self.people['symbionts']
        origin['ships']['cruiser'] = 1
        self.w._player(ally)['protected_until'] = 0
        self.w.alliance_action(owner, {'action': 'create', 'name': 'Fleet85 Alliance',
                                      'tag': 'F85', 'request_id': 'fleet85-alliance-create'})
        self.w._alliance_join(ally, self.w._alliance_for(owner), 'member')
        payload = {'action': 'defend', 'planet_id': origin['id'], 'target_id': target['id'],
                   'ships': {'cruiser': 1}, 'hold_hours': 1}
        quote = self.w._operation_quote(owner, payload)
        self.assertEqual(quote['upkeep'], 27)
        payload['hold_hours'] = 8
        self.assertEqual(self.w._operation_quote(owner, payload)['upkeep'], 216)
        # 8% research discount and 20% launch-building discount, each once.
        self.w._player(owner)['research']['graviton_control'] = 4
        origin['buildings']['gravitic_logistics'] = 5
        self.assertEqual(self.w._building_effects(origin)['fleet_fuel_reduction'], .2)
        self.assertEqual(self.w._operation_quote(owner, payload)['upkeep'], 159)
        payload['hold_hours'] = 1
        self.assertEqual(self.w._operation_quote(owner, payload)['upkeep'], 20)

    def test_swarm_stats_prices_and_fifteen_percent_weapons_are_unchanged(self):
        specs = self.w._specs('khar', 'ships')
        static = self.w._specs('khar', 'defenses')
        for key, raw in swarm.SHIPS.items():
            self.assertEqual(specs[key][2:], raw[2:])
            self.assertEqual(self.w._unit_construction_cost('khar', key, specs[key]), dict(zip(app.RESOURCES, raw[2])))
        for key, raw in defenses.specs_for('swarm').items():
            self.assertEqual(static[key][2:], raw[2:])
            self.assertEqual(self.w._unit_construction_cost('khar', key, static[key], stationary=True), dict(zip(app.RESOURCES, raw[2])))
        self.assertAlmostEqual(self.w._power({'cruiser': 1}, 4, specs, owner_id='khar'), swarm.SHIPS['cruiser'][4] * 1.6)
        # SwarmAI's existing raw-catalog call keeps its original forecast too.
        self.assertAlmostEqual(self.w._power({'cruiser': 1}, 4, swarm.SHIPS), swarm.SHIPS['cruiser'][4] * 1.6)
        hive = next(p for p in self.w.data['planets'].values() if p['owner_id'] == 'khar')
        form = self.w._coalition_formation('khar', {'cruiser': 1}, 'khar85', target=hive)
        form['weapons'] = 4
        self.assertAlmostEqual(self.w._coalition_power(form, 2), swarm.SHIPS['cruiser'][4] * 1.6)

    def test_actual_solo_swarm_salvo_keeps_npc_weapon_scaling(self):
        owner, target = self.people['zetans']
        target['ships'] = {**app.blank_ships(), 'titan': 1}
        hive = next(p for p in self.w.data['planets'].values() if p['owner_id'] == 'khar')
        f = {'id': 'swarm85', 'owner_id': 'khar', 'origin_id': hive['id'], 'target_id': target['id'],
             'ships': {'cruiser': 1}, 'seconds': 1, 'swarm_weapon_level': 4,
             'building_effects': {}, 'mission': 'attack', 'status': 'outbound'}
        self.w._battle(f, target)
        record = self.replay(owner)
        expected = swarm.SHIPS['cruiser'][4] * 1.6 * self.w._rules('khar')['first_volley_multiplier']
        self.assertAlmostEqual(record['rounds'][0]['salvos']['attacker'], expected)


if __name__ == '__main__':
    unittest.main()
