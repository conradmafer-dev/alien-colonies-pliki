"""0.5 content must unlock, affect real orders, and survive actual fleet events."""
import copy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from server.main import BUILDINGS, MAX_RESOURCE, RESOURCES, SHIPS, GameError, blank_ships
from tests.world_fixture import LocalTestWorld as World
from server.races import RACES, UNIQUE_BUILDINGS, UNIQUE_RESEARCH
from server import swarm

START = 1_900_000_000
OLD_BUILDINGS = {
    'zetans': {'phase_matrix', 'echo_observatory', 'synapse_archive'},
    'automatons': {'serial_forge', 'magnetic_citadel', 'wreck_recycler'},
    'symbionts': {'world_root', 'pioneer_nursery', 'renewal_grove'},
}
OLD_RESEARCH = {'zetans': {'antigravity'}, 'automatons': {'recycling'}, 'symbionts': {'multiplication'}}
OLD_SHIPS = {'scout', 'cargo', 'colonizer', 'frigate', 'cruiser'}
KINDS = {'buildings': 'build', 'research': 'research', 'ships': 'ship'}


class ContentExpansionScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'expansion.sqlite3')
        self.world = World(self.path, speed=1, now=START)
        self.player = self.new_player('Expansion Pilot')
        # We drive queue/flight events explicitly: random AI is unrelated here.
        self.world.data['alien']['next_expansion_at'] = START + 100 * 86400

    def tearDown(self):
        self.world.close()
        self.tmp.cleanup()

    def new_player(self, name, race=None):
        pid = self.world.register(name, 'password-123')['state']['player']['id']
        if race:
            self.world.action(pid, {'type': 'choose_race', 'race_id': race})
        return pid

    @property
    def owner(self):
        return self.world._player(self.player)

    @property
    def home(self):
        return self.world._owned(self.player)

    def choose(self, race):
        self.world.action(self.player, {'type': 'choose_race', 'race_id': race})
        return self.home

    def rich(self, planet=None):
        (planet or self.home)['resources'] = dict.fromkeys(RESOURCES, float(MAX_RESOURCE))

    def row(self, group, key, planet=None, pid=None):
        return next(r for r in self.world._catalog(pid or self.player, planet or self.home)[group] if r['key'] == key)

    def new_keys(self, group, race=None):
        race = race or self.owner['race_id']
        if group == 'buildings':
            return set(UNIQUE_BUILDINGS[race]) - OLD_BUILDINGS[race]
        if group == 'research':
            return set(UNIQUE_RESEARCH[race]) - OLD_RESEARCH[race]
        return set(RACES[race]['ships']) - OLD_SHIPS

    def extra_colony(self):
        p = next(p for p in self.world.data['planets'].values() if p['owner_type'] == 'empty')
        p.update(owner_type='player', owner_id=self.player)
        p['buildings'] = dict.fromkeys(BUILDINGS, 1)
        self.world._ensure_race_buildings(p)
        p['ships'] = blank_ships()
        self.rich(p)
        return p

    def order(self, group, key, amount=1, planet=None, complete=True):
        p = planet or self.home
        self.world.action(self.player, {'type': KINDS[group], 'key': key, 'amount': amount, 'planet_id': p['id']})
        if complete:
            self.world._complete_queue(p)

    def acquire(self, group, key, minimum=1, chain=()):
        """Reach prerequisites only through the public catalog and paid orders."""
        marker = (group, key)
        self.assertNotIn(marker, chain, f'Unreachable circular prerequisite: {chain + (marker,)}')
        while self.row(group, key)['level'] < minimum:
            for req in self.row(group, key).get('requirements', []):
                self.acquire(req.get('group', 'buildings'), req['key'], req['level'], chain + (marker,))
            self.rich()
            row = self.row(group, key)
            self.assertTrue(row['enabled'], f'{group}/{key} is unreachable: {row["reason"]}')
            self.order(group, key)

    def launch(self, mission, target, counts, cargo=None):
        payload = {'type': 'fleet', 'mission': mission, 'target_id': target['id'], 'ships': counts}
        if cargo:
            payload['cargo'] = cargo
        ids = set(self.world.data['fleets'])
        self.world.action(self.player, payload)
        return self.world.data['fleets'][(set(self.world.data['fleets']) - ids).pop()]

    def test_three_additions_per_category_are_own_race_content_without_free_stocks(self):
        for race in RACES:
            pid = self.new_player('Catalog ' + race, race)
            p = self.world._owned(pid)
            for group in KINDS:
                new = self.new_keys(group, race)
                self.assertEqual(len(new), 3)
                rows = {r['key']: r for r in self.world._catalog(pid, p)[group]}
                for key in new:
                    self.assertEqual(rows[key]['level'], 0)
                    self.assertTrue(rows[key].get('requirements'))
                    self.assertFalse(rows[key]['enabled'])
                    self.assertEqual(rows[key]['art_key'], f'races/{race}/{key}')
            self.assertEqual(len(self.world._catalog(pid, p)['ships']), 8)
            self.assertEqual(self.world._player(pid)['swarm_crystals'], 0)
            self.assertEqual({k: n for k, n in p['ships'].items() if n},
                             {'scout': 2, 'cargo': 1, 'colonizer': 1, 'frigate': 3})

    def test_all_new_content_reachable_by_real_purchases_without_circular_requirements(self):
        for race in RACES:
            self.player = self.new_player('Unlock ' + race, race)
            for group in ('buildings', 'research', 'ships'):
                for key in sorted(self.new_keys(group)):
                    with self.subTest(race=race, group=group, key=key):
                        self.acquire(group, key)
                        self.assertGreaterEqual(self.row(group, key)['level'], 1)

    def test_ship_research_gate_cannot_be_bypassed_with_resources_and_buildings(self):
        for race in RACES:
            self.player = self.new_player('Gate ' + race, race)
            self.rich()
            for key in self.home['buildings']:
                self.home['buildings'][key] = 5 if key in UNIQUE_BUILDINGS[race] else 12
            for key in sorted(self.new_keys('ships')):
                row = self.row('ships', key)
                research = [r for r in row['requirements'] if r.get('group') == 'research']
                self.assertTrue(research, f'{race}/{key} needs a genuine research gate')
                self.assertFalse(row['enabled'])
                before = copy.deepcopy(self.world.data)
                with self.assertRaises(GameError):
                    self.order('ships', key)
                self.assertEqual(self.world.data, before)
            for key in self.owner['research']:
                self.owner['research'][key] = 5 if key in UNIQUE_RESEARCH[race] else 12
            for key in self.new_keys('ships'):
                self.assertTrue(self.row('ships', key)['enabled'])

    def test_foreign_new_building_and_research_projects_are_rejected_atomically(self):
        self.choose('zetans')
        self.rich()
        before = copy.deepcopy(self.world.data)
        for race in ('symbionts', 'automatons'):
            for group in ('buildings', 'research'):
                for key in self.new_keys(group, race):
                    with self.assertRaises(GameError):
                        self.order(group, key)
                    self.assertEqual(self.world.data, before)

    def test_neutral_account_cannot_build_advanced_hulls_before_choosing_a_race(self):
        self.rich()
        self.home['buildings']['shipyard'] = 12
        self.home['buildings']['lab'] = 12
        before = copy.deepcopy(self.world.data)
        for key in ('interceptor', 'siege', 'freighter'):
            with self.assertRaises(GameError):
                self.order('ships', key)
            self.assertEqual(self.world.data, before)

    def test_new_ship_types_can_escort_colonization_and_land_once(self):
        self.choose('symbionts')
        self.rich()
        target = next(p for p in self.world.data['planets'].values() if p['owner_type'] == 'empty')
        escorts = {key: 2 for key in self.new_keys('ships')}
        self.home['ships'].update(escorts)
        fleet = self.launch('colonize', target, {'colonizer': 1, **escorts}, {'metal': 100})
        self.world._complete_fleet(fleet)
        self.assertEqual(target['owner_id'], self.player)
        self.assertEqual(target['ships']['colonizer'], 0)
        for key, number in escorts.items():
            self.assertEqual(target['ships'][key], number)
        self.assertEqual(target['resources']['metal'], 550)
        before = copy.deepcopy(self.world.data)
        self.world._complete_fleet(fleet)
        self.assertEqual(self.world.data, before)

    def test_new_mixed_fleet_can_attack_hive_and_deliver_survivors_and_loot_once(self):
        self.choose('automatons')
        self.rich()
        hive = next(p for p in self.world.data['planets'].values() if p['owner_id'] == 'khar')
        # Tiny controlled defenders isolate event handling, not fortress balance.
        hive['ships'] = {**dict.fromkeys(swarm.SHIPS, 0), 'frigate': 1}
        counts = {key: 10 for key in self.new_keys('ships')}
        self.home['ships'].update(counts)
        fleet = self.launch('attack', hive, counts)
        self.world._complete_fleet(fleet)
        self.assertEqual(fleet['status'], 'returning')
        self.assertGreater(sum(fleet['cargo'].values()), 0)
        survivors = dict(fleet['ships'])
        loot = dict(fleet['cargo'])
        balance = dict(self.home['resources'])
        self.assertEqual(self.owner['swarm_crystals'], 0)
        self.assertEqual(fleet['swarm_crystals'], 3)
        self.world._complete_fleet(fleet)
        for key in counts:
            self.assertEqual(self.home['ships'][key], survivors[key])
        for key in RESOURCES:
            self.assertEqual(self.home['resources'][key], min(MAX_RESOURCE, balance[key] + loot[key]))
        self.assertEqual(self.owner['swarm_crystals'], 3)
        before = copy.deepcopy(self.world.data)
        self.world._complete_fleet(fleet)
        self.assertEqual(self.world.data, before)

    def test_ship_factories_reduce_real_local_orders_and_stack_with_serial_batches(self):
        factories = {'zetans': 'quantum_foundry', 'symbionts': 'brood_chamber', 'automatons': 'assembly_hub'}
        for race, factory in factories.items():
            self.player = self.new_player('Factory ' + race, race)
            other = self.extra_colony()
            self.rich()
            baseline = self.row('ships', 'scout')['seconds']
            other_baseline = self.row('ships', 'scout', other)['seconds']
            building_before = self.row('buildings', 'metal_mine')['seconds']
            research_before = self.row('research', 'weapons')['seconds']
            self.home['buildings'][factory] = 5
            row = self.row('ships', 'scout')
            self.assertEqual(row['seconds'], math.ceil(baseline * .75))
            self.assertEqual(self.row('ships', 'scout', other)['seconds'], other_baseline)
            self.assertEqual(self.row('buildings', 'metal_mine')['seconds'], building_before)
            self.assertEqual(self.row('research', 'weapons')['seconds'], research_before)
            if race == 'automatons':
                self.home['buildings']['serial_forge'] = 5
            self.order('ships', 'scout', amount=5, complete=False)
            reduction = .30 if race == 'automatons' else 0
            self.assertEqual(self.home['queue'][0]['seconds'], math.ceil(row['seconds'] * 5 * (1 - reduction)))
            self.world._complete_queue(self.home)
            self.assertEqual(self.home['ships']['scout'], 7)

    def test_new_economy_buildings_affect_local_real_production_only(self):
        for race, building in (('symbionts', 'nutrient_reservoir'), ('automatons', 'ore_processor')):
            self.player = self.new_player('Economy ' + race, race)
            other = self.extra_colony()
            baseline = self.world.production(self.home)
            other_baseline = self.world.production(other)
            self.home['buildings'][building] = 5
            actual = self.world.production(self.home)
            for resource in RESOURCES:
                factor = 1.2 if race == 'symbionts' else 1.3 if resource == 'metal' else 1
                self.assertAlmostEqual(actual[resource], baseline[resource] * factor)
            self.assertEqual(self.world.production(other), other_baseline)
            self.home['resources'] = dict.fromkeys(RESOURCES, 0.)
            self.world._produce(3600)
            for resource in RESOURCES:
                self.assertAlmostEqual(self.home['resources'][resource], actual[resource])
            self.assertEqual(self.owner['swarm_crystals'], 0)

    def test_local_fuel_bonus_changes_quote_and_charge_without_retiming_flights(self):
        self.choose('zetans')
        self.rich()
        other = self.extra_colony()
        target = next(p for p in self.world.data['planets'].values() if p['owner_type'] == 'empty')
        counts = {'interceptor': 20, 'freighter': 10}
        self.home['ships'].update(counts)
        base_seconds, base_fuel = self.world._flight_numbers(self.home, target, counts)
        other_before = self.world._flight_numbers(other, target, counts)
        self.home['buildings']['gravitic_logistics'] = 5
        seconds, fuel = self.world._flight_numbers(self.home, target, counts)
        self.assertEqual(seconds, base_seconds)
        self.assertLess(fuel, base_fuel)
        self.assertAlmostEqual(fuel / base_fuel, .8, delta=.002)
        self.assertEqual(self.world._flight_numbers(other, target, counts), other_before)
        # Colonization allows a neutral destination without starting a battle.
        self.home['ships']['colonizer'] = 1
        payload = {'mission': 'colonize', 'target_id': target['id'], 'ships': {**counts, 'colonizer': 1}}
        quote = self.world.preview(self.player, payload)
        balance = self.home['resources']['fuel']
        fleet = self.launch('colonize', target, payload['ships'])
        self.assertEqual(balance - self.home['resources']['fuel'], quote['fuel_cost'])
        before = copy.deepcopy(fleet)
        self.home['buildings']['gravitic_logistics'] = 0
        self.assertEqual(fleet, before)

    def test_global_research_changes_all_owned_ship_specs_but_not_other_races_or_npcs(self):
        for race in RACES:
            self.player = self.new_player('Global ' + race, race)
            other = self.extra_colony()
            untouched_pid = self.new_player('Observer ' + race, race)
            for research in sorted(self.new_keys('research')):
                meta = UNIQUE_RESEARCH[race][research]
                effect = meta['effect']
                index = {'attack': 4, 'hull': 5, 'capacity': 6, 'fuel_efficiency': 7}[effect]
                self.owner['research'][research] = 0
                before = self.world._specs(self.player, 'ships')
                untouched = self.world._specs(untouched_pid, 'ships')
                npc = self.world._specs('khar', 'ships')
                self.owner['research'][research] = 5
                after = self.world._specs(self.player, 'ships')
                factor = 1 - meta['cap'] if effect == 'fuel_efficiency' else 1 + meta['cap']
                for key in after:
                    with self.subTest(race=race, research=research, ship=key):
                        self.assertAlmostEqual(after[key][index], before[key][index] * factor, places=5)
                        self.assertEqual(self.row('ships', key, other)[{'attack': 'attack', 'hull': 'hull', 'capacity': 'capacity', 'fuel_efficiency': 'fuel'}[effect]], after[key][index])
                self.assertEqual(self.world._specs(untouched_pid, 'ships'), untouched)
                self.assertEqual(self.world._specs('khar', 'ships'), npc)

    def test_cargo_research_unlocks_actual_transport_capacity_at_boundary(self):
        self.choose('zetans')
        self.rich()
        other = self.extra_colony()
        self.home['ships']['freighter'] = 1
        self.owner['research']['folding_cargo'] = 5
        payload = {'mission': 'transport', 'target_id': other['id'], 'ships': {'freighter': 1}}
        capacity = self.world.preview(self.player, payload)['capacity']
        self.assertEqual(capacity, 11200)
        with self.assertRaises(GameError):
            self.world.preview(self.player, {**payload, 'cargo': {'metal': capacity + 1}})
        quote = self.world.preview(self.player, {**payload, 'cargo': {'metal': capacity}})
        self.assertEqual(quote['capacity'], capacity)
        other['resources'] = dict.fromkeys(RESOURCES, 0.)
        fleet = self.launch('transport', other, {'freighter': 1}, {'metal': capacity})
        self.world._complete_fleet(fleet)
        self.assertEqual(other['resources']['metal'], capacity)

    def test_new_hull_research_prevents_a_real_combat_casualty(self):
        self.choose('symbionts')
        no_armor = self.world._specs(self.player, 'ships')
        self.owner['research']['chitin_layers'] = 5
        armor = self.world._specs(self.player, 'ships')
        before = {**blank_ships(), 'interceptor': 2}
        after = copy.deepcopy(before)
        hit = no_armor['interceptor'][5] + 1
        self.world._damage(before, hit, {}, no_armor)
        self.world._damage(after, hit, {}, armor)
        self.assertEqual(before['interceptor'], 1)
        self.assertEqual(after['interceptor'], 2)

    def test_vault_protects_each_resource_and_only_surplus_is_actually_looted(self):
        self.choose('zetans')
        defender = self.new_player('Vault Defender', 'automatons')
        target = self.world._owned(defender)
        self.world._player(defender)['protected_until'] = 0
        self.world._player(defender)['swarm_crystals'] = 23
        target['buildings']['armored_vault'] = 5
        target['ships'] = blank_ships()
        target['resources'] = {'metal': 7499., 'crystal': 7500., 'fuel': 17500.}
        self.assertEqual(self.world._lootable_resources(target), {'metal': 0, 'crystal': 0, 'fuel': 3500})
        self.rich()
        self.home['ships'].update(interceptor=1, freighter=1)
        fleet = self.launch('attack', target, {'interceptor': 1, 'freighter': 1})
        self.world._complete_fleet(fleet)
        self.assertEqual(fleet['cargo'], {'metal': 0, 'crystal': 0, 'fuel': 3500})
        self.assertEqual(target['resources'], {'metal': 7499., 'crystal': 7500., 'fuel': 14000.})
        self.assertEqual(self.world._player(defender)['swarm_crystals'], 23)
        self.assertEqual(fleet['swarm_crystals'], 0)

    def test_swarm_raid_target_selection_accounts_for_protected_stock(self):
        self.choose('automatons')
        self.owner['protected_until'] = 0
        self.home['resources'] = dict.fromkeys(RESOURCES, 7500.)
        self.home['ships'] = blank_ships()
        hive = min((p for p in self.world.data['planets'].values() if p['owner_id'] == 'khar'),
                   key=lambda p: self.world._distance(p, self.home))
        self.assertGreater(self.world._swarm_raid_score(hive, self.home, swarm.RAID_PARTY), 0)
        self.home['buildings']['armored_vault'] = 5
        self.assertEqual(self.world._swarm_raid_score(hive, self.home, swarm.RAID_PARTY), 0)

    def battle_first_damage(self, attacker, target, counts):
        f = {'id': 'controlled-battle', 'owner_id': attacker, 'origin_id': self.world._owned(attacker)['id'],
             'target_id': target['id'], 'mission': 'attack', 'status': 'outbound',
             'ships': {**blank_ships(), **counts}, 'cargo': dict.fromkeys(RESOURCES, 0),
             'seconds': 60, 'arrives_at': START + 60, 'swarm_crystals': 0}
        self.world.data['fleets'][f['id']] = f
        with patch.object(self.world, '_damage', wraps=self.world._damage) as damage:
            self.world._battle(f, target)
        return damage.call_args_list[0].args[1]

    def test_siege_extra_damage_applies_only_to_siege_attacking_a_hive_not_pvp(self):
        self.choose('zetans')
        defender = self.new_player('Siege Defender', 'automatons')
        pvp = self.world._owned(defender)
        pvp['ships'] = {**blank_ships(), 'cruiser': 100}
        hive = next(p for p in self.world.data['planets'].values() if p['owner_id'] == 'khar')
        hive['ships'] = {**dict.fromkeys(swarm.SHIPS, 0), 'cruiser': 100}
        counts = {'siege': 2, 'interceptor': 3}
        spec = self.world._specs(self.player, 'ships')
        first_volley = self.world._rules(self.player)['first_volley_multiplier']
        normal = self.battle_first_damage(self.player, pvp, counts)
        enhanced = self.battle_first_damage(self.player, hive, counts)
        self.assertAlmostEqual(normal, (2 * spec['siege'][4] + 3 * spec['interceptor'][4]) * first_volley)
        self.assertAlmostEqual(enhanced - normal, 2 * spec['siege'][4] * .5 * first_volley)
        # The bonus belongs to the attack on a hive, not the defending role.
        self.home['ships'] = {**blank_ships(), **counts}
        npc_fleet = {'id': 'incoming-raid', 'owner_id': 'khar', 'origin_id': hive['id'],
                     'target_id': self.home['id'], 'mission': 'attack', 'status': 'outbound',
                     'ships': {**dict.fromkeys(swarm.SHIPS, 0), 'cruiser': 50},
                     'cargo': dict.fromkeys(RESOURCES, 0), 'seconds': 60,
                     'arrives_at': START + 60, 'swarm_crystals': 0}
        self.world.data['fleets'][npc_fleet['id']] = npc_fleet
        with patch.object(self.world, '_damage', wraps=self.world._damage) as damage:
            self.world._battle(npc_fleet, self.home)
        self.assertAlmostEqual(damage.call_args_list[1].args[1], normal)

    def test_multiplication_grows_new_hulls_in_both_flight_directions_and_future_orders_once(self):
        self.choose('symbionts')
        self.acquire('research', 'multiplication')
        # Existing level one is the baseline; next upgrade must use 1.4 / 1.2.
        new = self.new_keys('ships')
        self.home['ships'].update(dict.fromkeys(new, 12))
        flights = []
        for index, status in enumerate(('outbound', 'returning')):
            fleet = {'id': 'growth-' + str(index), 'owner_id': self.player,
                     'origin_id': self.home['id'], 'target_id': 's30p1',
                     'mission': 'scout', 'status': status,
                     'ships': {**blank_ships(), **dict.fromkeys(new, 12)},
                     'cargo': {'metal': 8, 'crystal': 0, 'fuel': 0}, 'swarm_crystals': 2,
                     'seconds': 123, 'arrives_at': START + 123}
            self.world.data['fleets'][fleet['id']] = fleet
            flights.append(fleet)
        fixed = [{k: copy.deepcopy(v) for k, v in f.items() if k != 'ships'} for f in flights]
        self.acquire('research', 'multiplication', 2)
        for stock in [self.home['ships']] + [f['ships'] for f in flights]:
            for key in new:
                self.assertEqual(stock[key], 14)
        for f, unchanged in zip(flights, fixed):
            self.assertEqual({k: v for k, v in f.items() if k != 'ships'}, unchanged)
        for req in self.row('ships', 'interceptor')['requirements']:
            self.acquire(req['group'], req['key'], req['level'])
        self.rich()
        count = self.home['ships']['interceptor']
        self.order('ships', 'interceptor', amount=5)
        self.assertEqual(self.home['ships']['interceptor'], count + 7)
        before = copy.deepcopy(self.world.data)
        self.world._complete_queue(self.home)
        self.assertEqual(self.world.data, before)

    def test_041_save_migrates_new_fields_at_zero_without_reset_or_growing_old_fleets(self):
        self.choose('symbionts')
        self.owner['research']['multiplication'] = 3
        self.owner['swarm_crystals'] = 17
        self.home['buildings']['metal_mine'] = 7
        self.home['ships']['frigate'] = 41
        self.home['resources']['metal'] = 7654
        hive = next(p for p in self.world.data['planets'].values() if p['owner_id'] == 'khar')
        hive['swarm_crystals'] = .5
        hive['ships']['frigate'] = 7
        hive_before = copy.deepcopy(hive)
        fleet = {'id': 'old-scout', 'owner_id': self.player,
                 'origin_id': self.home['id'], 'target_id': hive['id'],
                 'mission': 'scout', 'status': 'outbound',
                 'ships': dict.fromkeys(OLD_SHIPS, 0), 'cargo': dict.fromkeys(RESOURCES, 0),
                 'swarm_crystals': 0, 'seconds': 100, 'arrives_at': START + 100}
        fleet['ships']['scout'] = 2
        self.world.data['fleets'][fleet['id']] = fleet
        for key in self.new_keys('buildings'):
            self.home['buildings'].pop(key)
        for key in self.new_keys('research'):
            self.owner['research'].pop(key)
        for key in self.new_keys('ships'):
            self.home['ships'].pop(key)
        self.world.close()
        self.world = World(self.path, speed=1, now=START)
        for group in ('buildings', 'research', 'ships'):
            for key in self.new_keys(group):
                self.assertEqual(self.row(group, key)['level'], 0)
        self.assertEqual(self.home['buildings']['metal_mine'], 7)
        self.assertEqual(self.home['ships']['frigate'], 41)
        self.assertEqual(self.home['resources']['metal'], 7654)
        self.assertEqual(self.owner['swarm_crystals'], 17)
        self.assertEqual(self.owner['research']['multiplication'], 3)
        self.assertEqual(self.world.data['planets'][hive['id']], hive_before)
        migrated = self.world.data['fleets'][fleet['id']]
        self.assertEqual(migrated['ships']['scout'], 2)
        self.assertTrue(all(migrated['ships'][key] == 0 for key in self.new_keys('ships')))
        self.world._complete_fleet(migrated)
        self.assertEqual(migrated['status'], 'returning')
        self.world._complete_fleet(migrated)
        self.assertEqual(self.home['ships']['scout'], 4)


if __name__ == '__main__':
    unittest.main()
