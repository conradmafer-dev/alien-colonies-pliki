"""Playable faction regression tests: real economy, selection and combat paths."""
import copy
import math
from pathlib import Path
import tempfile
import unittest

from server.main import BUILDINGS, RESEARCH, SHIPS, GameError, blank_ships, load_update_policy, VERSION, CLIENT_VERSION_CODE
from tests.world_fixture import LocalTestWorld as World
from server.races import RACES, UNIQUE_BUILDINGS, UNIQUE_RESEARCH
from server import swarm, technology

START = 1_900_000_000.0


class RaceScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'race.sqlite3')
        self.world = World(self.path, speed=10, now=START)
        self.a = self.world.register('Race Alpha', 'test-password-123')['state']['player']['id']
        self.b = self.world.register('Race Beta', 'test-password-123')['state']['player']['id']
        self.world.data['alien']['next_expansion_at'] = START + 10_000_000

    def tearDown(self):
        self.world.close()
        self.tmp.cleanup()

    def choose(self, race, player=None, request='race-choice'):
        return self.world.action(player or self.a, {'type': 'choose_race', 'race_id': race, 'request_id': request})['state']

    def home(self, player=None):
        return self.world._owned(player or self.a)

    def fleet(self, key, count=1):
        result = blank_ships()
        result[key] = count
        return result

    def battle(self, attacker_ship, defender_ship, count_a=1, count_d=1):
        origin, target = self.home(), self.home(self.b)
        target['ships'] = self.fleet(defender_ship, count_d)
        f = {'id': 'battle-fixture', 'owner_id': self.a, 'origin_id': origin['id'],
             'target_id': target['id'], 'mission': 'attack', 'status': 'outbound',
             'ships': self.fleet(attacker_ship, count_a), 'cargo': dict.fromkeys(('metal', 'crystal', 'fuel'), 0),
             'seconds': 15, 'arrives_at': self.world.now}
        self.world.data['fleets'][f['id']] = f
        self.world._battle(f, target)
        return f, target

    def test_new_and_legacy_players_have_three_choices_and_neutral_until_selection(self):
        for player in (self.a, self.b):
            if player == self.b:
                self.world.data['players'][player].pop('race_id')  # Previous snapshot shape.
            state = self.world.state(player)
            self.assertEqual(state['player']['race_id'], '')
            self.assertTrue(state['race_choice_allowed'])
            self.assertEqual(state['race_choice_reason'], '')
            self.assertEqual([r['id'] for r in state['races']], ['zetans', 'symbionts', 'automatons'])
            self.assertEqual(state['catalog']['ships'][0]['name'], 'Zwiadowca')
        self.assertEqual(load_update_policy({}).manifest()['latest_version'], VERSION)
        self.assertEqual(load_update_policy({}).manifest()['latest_version_code'], CLIENT_VERSION_CODE)

    def test_each_race_has_complete_unique_catalog_and_matching_art_roles(self):
        names = set()
        for race_id, race in RACES.items():
            for group, reference in (('buildings', BUILDINGS), ('ships', SHIPS), ('research', RESEARCH)):
                self.assertEqual(set(race[group]), set(reference))
                for spec in race[group].values():
                    self.assertNotIn(spec[0], names)
                    names.add(spec[0])
                    self.assertTrue(all(v >= 0 for v in spec[2]))
                    self.assertGreater(spec[3], 0)
            player = self.world.register('Race ' + race_id, 'test-password-123')['state']['player']['id']
            state = self.choose(race_id, player)
            for group in ('buildings', 'research', 'ships'):
                for entry in state['catalog'][group]:
                    key = entry['key']
                    role = 'scout' if key == 'propulsion' else 'weapon' if key == 'weapons' else key
                    if group == 'research' and key in technology.RESEARCH:
                        role = technology.RESEARCH[key]['art']
                    self.assertEqual(entry['art_key'], f'races/{race_id}/{role}')
                    unique = UNIQUE_BUILDINGS if group == 'buildings' else UNIQUE_RESEARCH
                    source = technology.RESEARCH[key]['spec'] if group == 'research' and key in technology.RESEARCH else unique[race_id][key]['spec'] if entry.get('unique') else race[group][key]
                    self.assertEqual(entry['name'], source[0])
            self.assertEqual(state['colony_art'], f'races/{race_id}/colony')
            self.assertEqual(state['race']['portrait_art'], f'races/{race_id}/portrait')

    def test_selection_is_atomic_permanent_idempotent_and_persists_without_freebies(self):
        original = copy.deepcopy(self.home())
        payload = {'type': 'choose_race', 'race_id': 'zetans', 'request_id': 'once'}
        first = self.world.action(self.a, payload)
        after = copy.deepcopy(self.world.data)
        original['buildings'].update(dict.fromkeys(UNIQUE_BUILDINGS['zetans'], 0))
        self.assertEqual(self.home(), original)
        replay = self.world.action(self.a, payload)
        self.assertEqual(first['message'], replay['message'])
        self.assertEqual(self.world.data, after)
        self.assertFalse(first['state']['race_choice_allowed'])
        with self.assertRaises(GameError):
            self.choose('symbionts', request='another')
        with self.assertRaises(GameError):
            self.world.action(self.a, {**payload, 'race_id': 'automatons'})
        self.assertEqual(self.world.data, after)
        self.world.close()
        self.world = World(self.path, speed=10, now=START)
        self.assertEqual(self.world.login('Race Alpha', 'test-password-123')['state']['player']['race_id'], 'zetans')
        self.assertEqual(self.home()['resources'], original['resources'])
        self.assertEqual(self.world.action(self.a, payload)['state']['player']['race_id'], 'zetans')

    def test_unknown_race_types_and_cross_player_selection_do_not_mutate_state(self):
        for bad in (None, '', 'human', 'ZETANS', True, 2, [], {}, ['zetans']):
            before = copy.deepcopy(self.world.data)
            with self.subTest(bad=bad), self.assertRaises(GameError):
                self.choose(bad)
            self.assertEqual(self.world.data, before)
        before = copy.deepcopy(self.world.data)
        with self.assertRaises(GameError):
            self.world.action(self.a, {'type': 'choose_race', 'race_id': 'zetans', 'planet_id': self.home(self.b)['id']})
        self.assertEqual(self.world.data, before)

    def test_selection_waits_for_queue_and_existing_flights_including_incoming(self):
        self.world.action(self.a, {'type': 'build', 'key': 'metal_mine'})
        self.assertFalse(self.world.state(self.a)['race_choice_allowed'])
        with self.assertRaises(GameError):
            self.choose('zetans')
        self.world.advance(self.home()['queue'][0]['ends_at'])
        self.assertTrue(self.world.state(self.a)['race_choice_allowed'])
        self.world.action(self.b, {'type': 'fleet', 'mission': 'scout', 'target_id': self.home()['id'], 'ships': {'scout': 1}})
        self.assertFalse(self.world.state(self.a)['race_choice_allowed'])
        with self.assertRaises(GameError):
            self.choose('symbionts')
        self.assertFalse(self.world.state(self.b)['race_choice_allowed'])
        while self.world.data['fleets']:
            self.world.advance(min(f['arrives_at'] for f in self.world.data['fleets'].values()))
        self.assertEqual(self.choose('symbionts')['player']['race_id'], 'symbionts')

    def test_economy_and_energy_match_published_values_and_actual_production(self):
        expected = {
            'zetans': ({'metal': 4860, 'crystal': 4875, 'fuel': 2100}, 100, 81),
            'symbionts': ({'metal': 5400, 'crystal': 3315, 'fuel': 2520}, 85, 59),
            'automatons': ({'metal': 6750, 'crystal': 3900, 'fuel': 1680}, 120, 87),
        }
        for race_id, (rates, supply, used) in expected.items():
            rates = {key: value / 10 for key, value in rates.items()}
            player = self.world.register('Economy ' + race_id, 'test-password-123')['state']['player']['id']
            state = self.choose(race_id, player)
            for key, rate in rates.items(): self.assertAlmostEqual(state['production'][key], rate)
            self.assertEqual(state['energy'], {'supply': supply, 'used': used, 'factor': 1.0})
            for entry in state['catalog']['buildings']:
                if 'production_resource' in entry:
                    resource = entry['production_resource']
                    self.assertEqual(entry['base_production'] + entry['production_per_level'], rates[resource])
            planet = self.home(player)
            before = dict(planet['resources'])
            self.world._produce(3600)
            for resource, rate in rates.items():
                self.assertAlmostEqual(planet['resources'][resource] - before[resource], rate)
            planet['buildings']['power_plant'] = 0
            self.assertEqual(self.world.production(planet), dict.fromkeys(rates, 0))

    def test_catalog_cost_and_time_are_used_by_build_ship_and_research_actions(self):
        for race_id in RACES:
            player = self.world.register('Build ' + race_id, 'test-password-123')['state']['player']['id']
            self.choose(race_id, player)
            for kind, group, key in (('build', 'buildings', 'metal_mine'), ('ship', 'ships', 'scout'), ('research', 'research', 'weapons')):
                planet = self.home(player)
                entry = next(x for x in self.world.state(player)['catalog'][group] if x['key'] == key)
                before = dict(planet['resources'])
                response = self.world.action(player, {'type': kind, 'key': key, 'amount': 2 if kind == 'ship' else 1})
                amount = 2 if kind == 'ship' else 1
                for resource, cost in entry['cost'].items():
                    self.assertEqual(planet['resources'][resource], before[resource] - cost * amount)
                self.assertEqual(response['state']['queue'][0]['ends_at'] - self.world.now, entry['seconds'] * amount)
                self.world.advance(planet['queue'][0]['ends_at'])
                self.assertIn(entry['name'], self.world.state(player)['reports'][0]['text'])

    def test_mission_quote_uses_race_capacity_fuel_speed_and_matches_launch(self):
        state = self.choose('zetans')
        home = self.home()
        target = next(p for p in self.world.data['planets'].values() if p['system_id'] == home['system_id'] and p['id'] != home['id'] and p['owner_type'] == 'empty')
        payload = {'type': 'fleet', 'mission': 'colonize', 'target_id': target['id'], 'ships': {'colonizer': 1, 'cargo': 1}, 'cargo': {'metal': 100}}
        quote = self.world.preview(self.a, payload)
        self.assertEqual(quote['capacity'], 1850)  # Zetan 550 + 1300; not neutral 600 + 1500.
        distance = abs(home['slot'] - target['slot']) * .08 + .1
        self.assertEqual(quote['fuel_cost'], math.ceil(9 * (1 + distance) * 2))
        self.assertEqual(quote['seconds'], max(8, math.ceil((100 + distance * 130) / 1.05 / 10)))
        before_fuel = home['resources']['fuel']
        result = self.world.action(self.a, payload)['state']
        self.assertEqual(before_fuel - home['resources']['fuel'], quote['fuel_cost'])
        self.assertEqual(result['fleets'][0]['arrives_at'] - self.world.now, quote['seconds'])
        self.assertEqual(result['fleets'][0]['race_id'], 'zetans')
        self.world.advance(result['fleets'][0]['arrives_at'])
        colony = self.world.state(self.a, target['id'])
        self.assertEqual(colony['player']['race_id'], 'zetans')
        self.assertEqual(colony['colony_art'], 'races/zetans/colony')
        self.assertEqual(next(p for p in colony['own_planets'] if p['id'] == target['id'])['race_id'], 'zetans')

    def test_scout_report_uses_defenders_race_names(self):
        self.choose('zetans')
        self.choose('automatons', self.b)
        state = self.world.action(self.a, {'type': 'fleet', 'mission': 'scout', 'target_id': self.home(self.b)['id'], 'ships': {'scout': 1}})['state']
        self.world.advance(state['fleets'][0]['arrives_at'])
        text = self.world.state(self.a)['reports'][0]['text']
        self.assertIn('Młot ×3', text)
        self.assertIn('Sonda 01 ×2', text)
        self.assertNotIn('Promień', text)

    def test_first_volley_works_for_attacker_and_defender(self):
        self.choose('zetans')
        self.choose('zetans', self.b)
        # Promień's opening 43.2 damage kills a 40-hull Arka in one volley;
        # its normal 32-damage volley would take two rounds.
        f, target = self.battle('frigate', 'cargo')
        self.assertEqual(target['ships']['cargo'], 0)
        self.assertIn('Rundy: 1.', self.world.state(self.a)['reports'][0]['text'])
        # Reverse the roles: the defender receives the same first-volley effect.
        f, target = self.battle('cargo', 'frigate')
        self.assertEqual(f['ships']['cargo'], 0)
        self.assertEqual(target['ships']['frigate'], 1)
        self.assertIn('Rundy: 1.', self.world.state(self.a)['reports'][0]['text'])

    def test_symbiont_regeneration_changes_battle_without_resurrecting(self):
        self.choose('zetans')
        self.choose('symbionts', self.b)
        # Four simultaneous volleys: Symbiont survives by healing partial hull damage;
        # without healing 43.2 + 32 + 32 + 32 would destroy its 120 hull.
        f, target = self.battle('frigate', 'frigate')
        self.assertEqual(f['ships']['frigate'], 0)
        self.assertEqual(target['ships']['frigate'], 1)
        text = self.world.state(self.a)['reports'][0]['text']
        self.assertIn('Rundy: 4.', text)
        self.assertIn('Promień ×1', text)
        self.assertIn('regeneracja 35%', text)
        ships = self.fleet('scout', 2)
        wounds = {}
        self.world._damage(ships, 25, wounds, RACES['symbionts']['ships'])
        self.assertEqual(ships['scout'], 1)
        self.world._regenerate(ships, wounds, .35)
        self.assertEqual(ships['scout'], 1)
        self.assertAlmostEqual(wounds['scout'], 3.9)

    def test_automaton_armor_prevents_first_round_destruction(self):
        self.choose('zetans')
        self.choose('automatons', self.b)
        self.world.data['players'][self.a]['research']['weapons'] = 1
        # Archont's 155.25 opening hit exceeds Młot's 140 hull, but its 12%
        # armor reduces it to 136.62 so this takes two rounds, not one.
        f, target = self.battle('cruiser', 'frigate')
        self.assertEqual(target['ships']['frigate'], 0)
        self.assertEqual(f['ships']['cruiser'], 1)
        text = self.world.state(self.a)['reports'][0]['text']
        self.assertIn('Rundy: 2.', text)
        self.assertIn('Młot ×1', text)
        self.assertIn('redukcja obrażeń 12%', text)
        self.assertLessEqual(sum(f['cargo'].values()), 190)  # Actual Zetan Archont hold.

    def test_requirements_name_the_actual_racial_buildings_and_units(self):
        self.choose('automatons')
        home = self.home()
        home['buildings']['lab'] = 0
        home['buildings']['shipyard'] = 0
        state = self.world.state(self.a)
        self.assertTrue(all('Rdzeń obliczeniowy' in row['reason'] for row in state['catalog']['research']))
        self.assertTrue(all('Kuźnia orbitalna' in row['reason'] for row in state['catalog']['ships']))
        target = self.home(self.b)['id']
        with self.assertRaisesRegex(GameError, 'Sonda 01'):
            self.world.preview(self.a, {'mission': 'scout', 'target_id': target, 'ships': {'cargo': 1}})
        with self.assertRaisesRegex(GameError, 'Młot lub Bastion'):
            self.world.preview(self.a, {'mission': 'attack', 'target_id': target, 'ships': {'cargo': 1}})
        with self.assertRaisesRegex(GameError, 'Konstruktor'):
            self.world.preview(self.a, {'mission': 'colonize', 'target_id': target, 'ships': {'cargo': 1}})

    def test_swarm_uses_own_catalog_and_public_data_cannot_mutate_racial_rules(self):
        self.choose('symbionts')
        khar = next(p for p in self.world.data['planets'].values() if p['owner_id'] == 'khar')
        self.assertEqual(self.world._specs('khar', 'ships'), swarm.SHIPS)
        self.assertNotEqual(self.world._specs('khar', 'ships'), SHIPS)
        # Isolate racial production multipliers from the stronger starting levels.
        production_fixture = copy.deepcopy(khar)
        production_fixture['buildings'] = dict.fromkeys(swarm.BUILDINGS, 1)
        for key, value in {'metal': 810, 'crystal': 429, 'fuel': 294}.items():
            self.assertAlmostEqual(self.world.production(production_fixture)[key], value)
        state = self.world.state(self.a)
        state['race']['rules']['regeneration_fraction'] = 100
        state['races'][0]['rules']['production_multipliers']['metal'] = 100
        self.assertEqual(RACES['symbionts']['rules']['regeneration_fraction'], .35)
        self.assertEqual(RACES['zetans']['rules']['production_multipliers']['metal'], .9)
        seen = next(p for system in self.world.state(self.b)['galaxy'] for p in system['planets'] if p['id'] == self.home()['id'])
        self.assertEqual(seen['race_id'], 'symbionts')
        self.assertEqual(seen['race_name'], 'Symbionci')


if __name__ == '__main__':
    unittest.main()
