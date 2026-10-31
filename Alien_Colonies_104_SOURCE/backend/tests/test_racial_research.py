"""Racial research uses real orders, travel, settlement and saved fleet stocks."""
import copy
from fractions import Fraction
import math
from pathlib import Path
import tempfile
import unittest

from server.main import BUILDINGS, MAX_RESOURCE, RESEARCH, RESOURCES, SHIPS, GameError, blank_ships
from tests.world_fixture import LocalTestWorld as World
from server.races import RACES, UNIQUE_RESEARCH
from server import skill_tree

START = 1_900_000_000.0


class RacialResearchScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'research.sqlite3')
        self.world = World(self.path, speed=1, now=START)
        self.player = self.world.register('Researcher', 'password-123')['state']['player']['id']
        self.world.data['alien']['next_expansion_at'] = START + 10_000_000

    def tearDown(self):
        self.world.close()
        self.tmp.cleanup()

    @property
    def owner(self):
        return self.world.data['players'][self.player]

    @property
    def home(self):
        return self.world._owned(self.player)

    def choose(self, race):
        self.world.action(self.player, {'type': 'choose_race', 'race_id': race})
        self.home['resources'] = dict.fromkeys(RESOURCES, 1_000_000.0)
        return self.home

    def unlock_requirements(self, key, planet=None):
        p = planet or self.home
        for required, level in UNIQUE_RESEARCH[self.owner['race_id']][key]['requirements']:
            p['buildings'][required] = level

    def entry(self, key, group='research', planet=None):
        return next(e for e in self.world._catalog(self.player, planet or self.home)[group] if e['key'] == key)

    def extra_colony(self):
        p = next(p for p in self.world.data['planets'].values() if p['owner_type'] == 'empty')
        p.update(owner_id=self.player, owner_type='player')
        p['buildings'] = dict.fromkeys(BUILDINGS, 1)
        p['resources'] = dict.fromkeys(RESOURCES, 1_000_000.0)
        self.world._ensure_race_buildings(p)
        return p

    def start(self, kind, key, amount=1, planet=None, request_id=None):
        p = planet or self.home
        payload = {'type': kind, 'key': key, 'amount': amount, 'planet_id': p['id']}
        if request_id:
            payload['request_id'] = request_id
        self.world.action(self.player, payload)
        return payload

    def complete(self, kind, key, amount=1, planet=None):
        p = planet or self.home
        self.start(kind, key, amount, p)
        self.world._complete_queue(p)

    def research_to(self, key, level):
        self.unlock_requirements(key)
        while self.owner['research'][key] < level:
            self.complete('research', key)

    def flight(self, status='outbound', counts=None, owner=None):
        f = {'id': 'flight-' + str(len(self.world.data['fleets'])), 'owner_id': owner or self.player,
             'origin_id': self.home['id'], 'target_id': 's30p1', 'status': status, 'mission': 'scout',
             'ships': {**blank_ships(), **(counts or {'scout': 10})}, 'seconds': 123,
             'arrives_at': START + 123, 'cargo': {'metal': 8, 'crystal': 0, 'fuel': 0}, 'swarm_crystals': 3}
        self.world.data['fleets'][f['id']] = f
        return f

    def test_each_race_gets_four_locked_unique_research_before_unchanged_basics(self):
        for race, meta in UNIQUE_RESEARCH.items():
            player = self.world.register('Research ' + race, 'password-123')['state']['player']['id']
            state = self.world.action(player, {'type': 'choose_race', 'race_id': race})['state']
            entries = state['catalog']['research']
            from server import technology
            self.assertEqual([e['key'] for e in entries], list(meta) + list(RESEARCH) + list(technology.RESEARCH))
            row = entries[0]
            self.assertTrue(row['unique'])
            self.assertEqual(row['max_level'], 5)
            self.assertEqual(row['level'], 0)
            self.assertFalse(row['enabled'])
            self.assertEqual(row['art_key'], f"races/{race}/{row['key']}")
            self.assertEqual([r['level'] for r in row['requirements']], [3, 2])
            self.assertEqual(len(meta), 4)
            for unique in entries[:len(meta)]:
                self.assertTrue(unique['unique'])
                self.assertEqual(unique['level'], 0)
                self.assertEqual(unique['max_level'], 5)
                self.assertFalse(unique['enabled'])
                self.assertEqual(unique['name'], meta[unique['key']]['spec'][0])
            for basic in entries[len(meta):len(meta) + len(RESEARCH)]:
                self.assertFalse(basic.get('unique', False))
                self.assertEqual(basic['name'], RACES[race]['research'][basic['key']][0])

    def test_both_local_requirements_are_enforced_and_global_research_serialized(self):
        self.choose('zetans')
        key = 'antigravity'
        other = self.extra_colony()
        self.unlock_requirements(key, other)
        self.home['buildings']['lab'] = 3
        before = copy.deepcopy(self.world.data)
        with self.assertRaises(GameError):
            self.start('research', key)
        self.assertEqual(before, self.world.data)
        self.home['buildings']['echo_observatory'] = 2
        row = self.entry(key)
        self.assertTrue(row['enabled'])
        initial = dict(self.home['resources'])
        payload = self.start('research', key, request_id='once-research')
        for resource in RESOURCES:
            self.assertEqual(self.home['resources'][resource], initial[resource] - row['cost'][resource])
        after = copy.deepcopy(self.world.data)
        self.world.action(self.player, payload)
        self.assertEqual(after, self.world.data)
        with self.assertRaises(GameError):
            self.start('research', key, planet=other)
        self.world._complete_queue(self.home)
        self.assertEqual(self.entry(key, planet=other)['level'], 1)
        self.owner['research'][key] = 5
        self.assertFalse(self.entry(key)['enabled'])
        with self.assertRaises(GameError):
            self.start('research', key)

    def test_foreign_roots_and_forged_research_keys_never_grant_racial_effects(self):
        self.choose('zetans')
        self.owner['skill_nodes'] = [n['id'] for n in skill_tree.graph()['nodes']]
        self.owner['research'].update(recycling=5, multiplication=5)
        for key in ('recycling', 'multiplication'):
            with self.assertRaises(GameError):
                self.start('research', key)
        self.assertEqual(self.entry('scout', 'ships')['production_multiplier'], 1)
        self.assertEqual(self.entry('metal_mine', 'buildings')['construction_refund_rate'], 0)

    def test_antigravity_stacks_speed_globally_with_propulsion_and_wheel_not_fuel(self):
        self.choose('zetans')
        other = self.extra_colony()
        self.owner['research']['propulsion'] = 3
        self.owner['skill_nodes'] = [n['id'] for n in skill_tree.graph()['nodes']]
        target = self.world.data['planets']['s30p3']
        fleet = {'scout': 2}
        old_seconds, old_fuel = self.world._flight_numbers(other, target, fleet, 3)
        spec = self.world._specs(self.player, 'ships')['scout']
        self.owner['research']['antigravity'] = 3
        seconds, fuel = self.world._flight_numbers(other, target, fleet, 3)
        expected = max(8, math.ceil((100 + self.world._distance(other, target) * 130) / spec[8] / 1.45 / 1.6))
        self.assertEqual(seconds, expected)
        self.assertLess(seconds, old_seconds)
        self.assertEqual(fuel, old_fuel)
        self.assertAlmostEqual(self.entry('scout', 'ships', other)['effective_speed'], spec[8] * 1.45 * 1.6)

    def test_antigravity_launch_preview_matches_and_existing_flight_deadlines_stay(self):
        self.choose('zetans')
        target = self.world.data['planets']['s30p1']
        payload = {'type': 'fleet', 'mission': 'scout', 'target_id': target['id'], 'ships': {'scout': 1}}
        quote = self.world.preview(self.player, payload)
        self.world.action(self.player, payload)
        f = next(f for f in self.world.data['fleets'].values() if f['owner_id'] == self.player)
        self.assertEqual(f['seconds'], quote['seconds'])
        before = copy.deepcopy(f)
        self.research_to('antigravity', 5)
        self.assertEqual(f, before)
        self.world._return(f)
        self.assertEqual(f['arrives_at'], self.world.now + before['seconds'])
        self.world.speed = 1000
        self.home['buildings']['echo_observatory'] = 5
        self.assertEqual(self.world.preview(self.player, payload)['seconds'], 8)

    def test_multiplication_grows_all_owned_stocks_including_both_flight_directions_only_once(self):
        self.choose('symbionts')
        self.home['ships'] = {**blank_ships(), 'scout': 10}
        other = self.extra_colony()
        other['ships']['scout'] = 20
        outbound = self.flight(counts={'scout': 10})
        returning = self.flight('returning', {'scout': 15})
        npc = self.flight(owner='khar')
        npc_before = copy.deepcopy(npc)
        flight_fixed = [{k: copy.deepcopy(v) for k, v in f.items() if k != 'ships'} for f in (outbound, returning)]
        self.research_to('multiplication', 1)
        self.assertEqual([self.home['ships']['scout'], other['ships']['scout'], outbound['ships']['scout'], returning['ships']['scout']], [12, 24, 12, 18])
        self.assertEqual(npc, npc_before)
        self.research_to('multiplication', 5)
        self.assertEqual([self.home['ships']['scout'], other['ships']['scout'], outbound['ships']['scout'], returning['ships']['scout']], [20, 40, 20, 30])
        for f, expected in zip((outbound, returning), flight_fixed):
            self.assertEqual({k: v for k, v in f.items() if k != 'ships'}, expected)
        before = copy.deepcopy(self.world.data)
        self.world._complete_queue(self.home)
        self.assertEqual(before, self.world.data)
        self.assertIn('całym imperium', self.owner['reports'][0]['text'])

    def test_multiplication_exact_fraction_survives_every_upgrade_and_restart(self):
        self.choose('symbionts')
        self.home['ships'] = {**blank_ships(), 'scout': 1}
        for level in range(1, 6):
            self.research_to('multiplication', level)
            exact = Fraction(5 + level, 5)
            self.assertEqual(self.home['ships']['scout'], math.floor(exact))
            self.assertEqual(self.world._growth_credit(self.owner, 'scout'), exact - math.floor(exact))
            self.world.close()
            self.world = World(self.path, speed=1, now=START)
        self.assertEqual(self.home['ships']['scout'], 2)

    def test_production_twenty_single_orders_equals_one_batch_and_other_colony_shares_credit(self):
        self.choose('symbionts')
        self.home['ships'] = blank_ships()
        self.owner['research']['multiplication'] = 2
        self.home['buildings']['shipyard'] = 1
        other = self.extra_colony()
        for i in range(20):
            self.complete('ship', 'scout', planet=other if i % 2 else self.home)
        self.assertEqual(self.home['ships']['scout'] + other['ships']['scout'], 28)
        self.assertEqual(self.world._growth_credit(self.owner, 'scout'), 0)
        self.complete('ship', 'cargo', 20)
        self.assertEqual(self.home['ships']['cargo'], 28)
        self.assertEqual(self.entry('scout', 'ships')['production_multiplier'], 1.4)

    def test_losses_are_not_restored_and_zero_stock_is_not_resurrected_by_fraction(self):
        self.choose('symbionts')
        self.home['ships'] = {**blank_ships(), 'scout': 10, 'frigate': 1}
        self.research_to('multiplication', 1)
        self.home['ships']['scout'] = 6
        self.home['ships']['frigate'] = 0
        self.research_to('multiplication', 2)
        self.assertEqual(self.home['ships']['scout'], 7)
        self.assertEqual(self.home['ships']['frigate'], 0)
        self.assertEqual(self.home['ships']['cruiser'], 0)

    def test_future_ship_queue_is_not_multiplied_until_completion_and_uses_current_level(self):
        self.choose('symbionts')
        self.home['ships'] = blank_ships()
        other = self.extra_colony()
        self.start('ship', 'scout', 10, other)
        queued_before = copy.deepcopy(other['queue'])
        self.research_to('multiplication', 2)
        self.assertEqual(other['ships']['scout'], 0)
        self.assertEqual(other['queue'], queued_before)
        self.world._complete_queue(other)
        self.assertEqual(other['ships']['scout'], 14)
        self.world._complete_queue(other)
        self.assertEqual(other['ships']['scout'], 14)

    def test_growth_allocation_is_proportional_and_ties_are_independent_of_dict_order(self):
        self.choose('symbionts')
        self.home['ships'] = {**blank_ships(), 'scout': 2}
        other = self.extra_colony()
        other['ships']['scout'] = 2
        outbound = self.flight(counts={'scout': 2})
        before = copy.deepcopy(self.world.data)
        self.world._multiply_existing_fleet(self.player, 0, 1)
        result = (self.home['ships']['scout'], other['ships']['scout'], outbound['ships']['scout'])
        self.assertEqual(sum(result), 7)
        self.world.data = before
        self.world.data['planets'] = dict(reversed(list(self.world.data['planets'].items())))
        self.world._multiply_existing_fleet(self.player, 0, 1)
        result2 = (self.home['ships']['scout'], self.world.data['planets'][other['id']]['ships']['scout'], self.world.data['fleets'][outbound['id']]['ships']['scout'])
        self.assertEqual(result, result2)

    def test_recycling_snapshots_actual_paid_batch_cost_and_pays_once_on_completion(self):
        self.choose('automatons')
        self.home['buildings']['shipyard'] = 1
        self.owner['research']['recycling'] = 1
        entry = self.entry('scout', 'ships')
        self.assertEqual(entry['construction_refund_rate'], .05)
        initial = dict(self.home['resources'])
        payload = self.start('ship', 'scout', 3, request_id='recycle-once')
        task = self.home['queue'][0]
        paid = {k: v * 3 for k, v in entry['cost'].items()}
        refund = {k: v // 20 for k, v in paid.items()}
        self.assertEqual(task['construction_refund'], refund)
        for resource in RESOURCES:
            self.assertEqual(self.home['resources'][resource], initial[resource] - paid[resource])
        self.owner['research']['recycling'] = 5
        self.world._complete_queue(self.home)
        for resource in RESOURCES:
            self.assertEqual(self.home['resources'][resource], initial[resource] - paid[resource] + refund[resource])
        before = copy.deepcopy(self.world.data)
        self.world.action(self.player, payload)
        self.world._complete_queue(self.home)
        self.assertEqual(before, self.world.data)

    def test_recycling_covers_basic_and_unique_upgrades_globally_but_not_research(self):
        self.choose('automatons')
        self.research_to('recycling', 5)
        other = self.extra_colony()
        for key, p in (('metal_mine', self.home), ('serial_forge', other)):
            entry = self.entry(key, 'buildings', p)
            self.assertEqual(entry['construction_refund_rate'], .25)
            initial = dict(p['resources'])
            self.complete('build', key, planet=p)
            for resource in RESOURCES:
                paid = entry['cost'][resource]
                self.assertEqual(p['resources'][resource], initial[resource] - paid + paid // 4)
        initial = dict(self.home['resources'])
        cost = self.entry('propulsion')['cost']
        self.complete('research', 'propulsion')
        for resource in RESOURCES:
            self.assertEqual(self.home['resources'][resource], initial[resource] - cost[resource])

    def test_recycling_pending_refund_persists_restart_resource_cap_and_old_queue_default(self):
        self.choose('automatons')
        self.owner['research']['recycling'] = 5
        self.start('build', 'metal_mine')
        expected = copy.deepcopy(self.home['queue'][0])
        self.world.close()
        self.world = World(self.path, speed=1, now=START)
        self.assertEqual(self.home['queue'][0], expected)
        self.home['resources'] = dict.fromkeys(RESOURCES, MAX_RESOURCE)
        self.world._complete_queue(self.home)
        self.assertEqual(self.home['resources'], dict.fromkeys(RESOURCES, MAX_RESOURCE))
        self.start('build', 'metal_mine')
        self.home['queue'][0].pop('construction_refund')
        paid_balance = dict(self.home['resources'])
        self.world._complete_queue(self.home)
        self.assertEqual(self.home['resources'], paid_balance)

    def test_old_snapshot_adds_zero_research_without_free_ship_growth(self):
        self.choose('symbionts')
        self.home['ships'] = {**blank_ships(), 'scout': 19}
        self.owner['research'].pop('multiplication')
        self.owner.pop('fleet_growth_credits')
        self.world.close()
        self.world = World(self.path, speed=1, now=START)
        self.assertEqual(self.home['ships']['scout'], 19)
        self.assertEqual(self.owner['research']['multiplication'], 0)
        self.assertEqual(self.owner['fleet_growth_credits'], {})


if __name__ == '__main__':
    unittest.main()
