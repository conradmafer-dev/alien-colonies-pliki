"""Coalition battles preserve ownership, economics, real flights and telemetry."""
import copy
import json
import unittest
from unittest.mock import patch
from server.main import World, GameError, blank_ships
from server.alliance_operations import apportion, capacity
from server import swarm
from server.i18n import language_scope

NOW = 1900000000


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.w = World(':memory:', now=NOW, speed=1000)
        self.addCleanup(self.w.close)
        self.owners = []
        for name, race in [('Coalition', 'zetans'), ('MetalAlly', 'automatons'), ('GreenAlly', 'symbionts'), ('Enemy', 'symbionts')]:
            pid = self.w.register(name, 'alliance-operation-password')['state']['player']['id']
            self.w.action(pid, {'type': 'choose_race', 'race_id': race})
            self.owners.append(pid)
            planet = self.w._owned(pid)
            planet['ships'] = {**blank_ships(), 'frigate': 300, 'cruiser': 60, 'cargo': 20, 'siege': 20}
            planet['resources'] = dict.fromkeys(('metal', 'crystal', 'fuel'), 1_000_000_000.)
            planet['queue'] = []
            self.w._player(pid)['protected_until'] = 0
        self.a, self.b, self.c, self.enemy = self.owners
        self.w.alliance_action(self.a, {'action': 'create', 'name': 'Coalition Test', 'tag': 'CLT', 'request_id': 'alliance-create'})
        self.alliance = self.w._alliance_for(self.a)
        self.w._alliance_join(self.b, self.alliance, 'member')
        self.w._alliance_join(self.c, self.alliance, 'member')
        self.target = self.w._owned(self.enemy)
        self.w._capture_planetary_intel(self.a, self.target)
        self.w.data['alien']['next_expansion_at'] = NOW + 1000000
        self.serial = 0

    def action(self, owner, action, **kw):
        self.serial += 1
        return self.w.alliance_operation(owner, dict(action=action, request_id='operation-%d' % self.serial, **kw))

    def create(self, target=None, delay=600):
        target = target or self.target
        self.w._capture_planetary_intel(self.a, target)
        result = self.action(self.a, 'create', target_id=target['id'], delay_seconds=delay)
        return self.w.data['alliance_operations'][result['operation_id']]

    def join(self, owner, op, ships=None):
        result = self.action(owner, 'join', operation_id=op['id'], planet_id=self.w._owned(owner)['id'], ships=ships or {'frigate': 30, 'cruiser': 5, 'cargo': 2})
        return self.w.data['fleets'][result['fleet_id']]

    def support(self, owner, target, ships=None, hold=1):
        result = self.action(owner, 'defend', target_id=target['id'], planet_id=self.w._owned(owner)['id'], ships=ships or {'frigate': 30, 'cruiser': 5}, hold_hours=hold)
        return self.w.data['fleets'][result['fleet_id']]

    def battle(self, target=None, ships=None):
        op = self.create(target)
        fleets = [self.join(owner, op, ships) for owner in (self.a, self.b, self.c)]
        self.w.advance(op['impact_at'])
        report = next(r for r in self.w._player(self.a)['reports'] if r.get('battle_replay'))
        return op, fleets, report['battle_replay']

    def test_integer_allocation_conserves_quota_and_respects_caps(self):
        for total in (0, 1, 3, 17, 400):
            result = apportion(total, {'a': 1, 'b': 3, 'c': 0}, {'a': 2, 'b': 100, 'c': 100})
            self.assertEqual(sum(result.values()), min(total, 102))
            self.assertLessEqual(result['a'], 2)
            self.assertEqual(result['c'], 0)

    def test_three_owners_one_impact_and_exact_once_return(self):
        self.target['ships'] = {**blank_ships(), 'frigate': 3}
        before = {owner: dict(self.w._owned(owner)['ships']) for owner in (self.a, self.b, self.c)}
        op, fleets, replay = self.battle()
        self.assertEqual(op['status'], 'completed')
        self.assertEqual(len(replay['attacker']['participants']), 3)
        self.assertEqual(len({u['key'] for u in replay['attacker']['units']}), len(replay['attacker']['units']))
        self.assertEqual(replay['outcome'], 'attacker_wins')
        snapshots = copy.deepcopy(self.w.data)
        self.w.advance(self.w.now)
        self.assertEqual(self.w.data, snapshots)
        for f in fleets:
            self.assertEqual(f['status'], 'returning')
            self.assertEqual(f['arrives_at'] - self.w.now, f['return_seconds'])
        self.w.advance(max(f['arrives_at'] for f in fleets))
        for f in fleets:
            self.assertNotIn(f['id'], self.w.data['fleets'])
            result = next(x for x in replay['participant_results'] if x['owner_id'] == f['owner_id'])
            self.assertEqual(self.w._owned(f['owner_id'])['ships']['frigate'], before[f['owner_id']]['frigate'] - result['losses']['frigate'])
        after = copy.deepcopy(self.w.data)
        for f in fleets:
            self.w._complete_fleet(f)
        self.assertEqual(self.w.data, after)

    def test_each_round_salvos_events_heals_and_owner_stats_reconcile(self):
        op, fleets, replay = self.battle()
        previous = {side: replay[side]['initial'] for side in ('attacker', 'defender')}
        for round_ in replay['rounds']:
            self.assertEqual(round_['before'], previous)
            for side in ('attacker', 'defender'):
                actual = copy.deepcopy(round_['before'][side])
                units = {u['key']: u for u in replay[side]['units']}
                expected = sum(u['attack'] * actual[k]['count'] * (self.w._rules(u['owner_id'])['first_volley_multiplier'] if round_['number'] == 1 else 1)
                               for k, u in units.items())
                self.assertAlmostEqual(round_['salvos'][side], expected)
                for hit in round_['hits'][side]:
                    self.assertEqual(actual[hit['key']], hit['before'])
                    u = units[hit['key']]
                    self.assertEqual(hit['destroyed'], hit['before']['count'] - hit['after']['count'])
                    hp_before = hit['before']['count'] * u['hull'] - hit['before']['wounds']
                    hp_after = hit['after']['count'] * u['hull'] - hit['after']['wounds']
                    self.assertAlmostEqual(hp_before - hp_after, hit['damage'])
                    actual[hit['key']] = hit['after']
                self.assertEqual(actual, round_['after_damage'][side])
                for heal in round_['heals'][side]:
                    self.assertEqual(actual[heal['key']], heal['before'])
                    self.assertEqual(heal['before']['count'], heal['after']['count'])
                    actual[heal['key']] = heal['after']
                self.assertEqual(actual, round_['after'][side])
            previous = round_['after']
        self.assertEqual(previous, replay['final'])
        for owner in (self.a, self.b, self.c, self.enemy):
            saved = next(r['battle_replay'] for r in self.w._player(owner)['reports'] if r.get('battle_replay'))
            self.assertEqual(saved, replay)
            self.assertIsNot(saved, replay) if owner != self.a else None
        json.dumps(replay, allow_nan=False)

    def test_siege_bonus_only_when_attacking_swarm_defense(self):
        form = self.w._coalition_formation(self.a, {'siege': 3}, 'siege-test')
        defending = self.w._coalition_power(form, 1, enemy_swarm=True)
        attacking = self.w._coalition_power(form, 1, enemy_swarm=True, assault=True)
        self.assertAlmostEqual(attacking, defending * 1.5)
        self.assertAlmostEqual(defending, self.w._power(form['ships'], form['weapons'], form['specs'], form['rules']['first_volley_multiplier'] * (1 + self.w._bonuses(self.a).get('swarm_damage', 0))))

    def test_proportional_damage_uses_current_hull_not_owner_order(self):
        formations = []
        for owner, count in ((self.a, 5), (self.b, 7), (self.c, 3)):
            formations.append(self.w._coalition_formation(owner, {'cruiser': count}, owner))
        before = {f['id']: f['ships']['cruiser'] * f['specs']['cruiser'][5] / (1 - f['rules']['damage_reduction']) for f in formations}
        events = []
        self.w._coalition_damage(formations, 100, events)
        for event in events:
            f = next(f for f in formations if event['key'].startswith(f['id']))
            self.assertAlmostEqual(event['damage'] + event['blocked'], 100 * before[f['id']] / sum(before.values()))

    def test_outpost_eradication_one_pooled_bonus_and_one_return_settlement(self):
        target = next(p for p in self.w.data['planets'].values() if p['owner_id'] == 'khar')
        target['swarm_kind'] = 'outpost'
        target['ships'] = {**target['ships'], 'frigate': 10, 'cruiser': 0}
        target['defenses'] = dict.fromkeys(target.get('defenses', {}), 0)
        target['swarm_crystals'] = 6
        target['swarm_loot_sealed'] = False
        target['queue'] = [{'id': 'future-swarm-ships', 'kind': 'ship', 'key': 'frigate',
                            'amount': 8, 'ends_at': self.w.now + 100000}]
        identity = {k: copy.deepcopy(target[k]) for k in
                    ('id', 'name', 'system_id', 'slot', 'galaxy_id', 'environment', 'rare_trait') if k in target}
        wallets = {owner: self.w._player(owner)['swarm_crystals'] for owner in (self.a, self.b, self.c)}
        op, fleets, replay = self.battle(target, {'frigate': 100, 'cruiser': 20, 'cargo': 2})
        self.assertEqual(replay['outcome'], 'attacker_wins')
        self.assertTrue(replay['swarm_eradicated'])
        self.assertTrue(op['result']['swarm_eradicated'])
        self.assertEqual(replay['swarm_crystals'], swarm.RAID_CRYSTALS['outpost'] + swarm.DESTRUCTION_CRYSTALS)
        self.assertEqual(replay['swarm_destruction_bonus'], swarm.DESTRUCTION_CRYSTALS)
        self.assertEqual(op['result']['swarm_destruction_bonus'], swarm.DESTRUCTION_CRYSTALS)
        self.assertEqual(sum(f['swarm_crystals'] for f in fleets), replay['swarm_crystals'])
        self.assertEqual(sum(f['swarm_destruction_bonus'] for f in fleets), swarm.DESTRUCTION_CRYSTALS)
        self.assertEqual((target['owner_type'], target['owner_id']), ('empty', ''))
        self.assertEqual({k: target[k] for k in identity}, identity)
        self.assertEqual(target['queue'], [])
        self.assertFalse(any(target['buildings'].values()))
        self.assertFalse(any(target['ships'].values()))
        self.assertFalse(any(target['defenses'].values()))
        self.assertFalse(any(k.startswith('swarm_') for k in target))
        for f in fleets:
            self.assertLessEqual(sum(f['cargo'].values()) + f['swarm_crystals'], capacity(self.w._specs(f['owner_id'], 'ships'), f['ships']))
            self.assertEqual(self.w._player(f['owner_id'])['swarm_crystals'], wallets[f['owner_id']])
            report = next(r for r in self.w._player(f['owner_id'])['reports'] if r.get('battle_replay'))
            self.assertIn('Planeta jest wolna', report['text'])
            self.assertIn('Premia za zniszczenie gniazda', report['text'])
            participant = next(p for p in replay['participant_results'] if p['owner_id'] == f['owner_id'])
            self.assertEqual(participant['swarm_destruction_bonus'], f['swarm_destruction_bonus'])
            known = self.w._operation_known_targets(f['owner_id'])[target['id']]
            self.assertEqual(known['owner_type'], 'empty')
        self.w.advance(max(f['arrives_at'] for f in fleets))
        for f in fleets:
            self.assertEqual(self.w._player(f['owner_id'])['swarm_crystals'], wallets[f['owner_id']] + f['swarm_crystals'])
            self.assertNotIn(f['id'], self.w.data['fleets'])
        settled = copy.deepcopy(self.w.data)
        for f in fleets:
            self.w._complete_fleet(f)
        self.assertEqual(self.w.data, settled)
        with self.assertRaises(GameError) as denied:
            self.create(target)
        self.assertEqual(denied.exception.status, 403)

    def test_main_hive_survives_without_bonus_or_empty_repeat_crystals_and_rebuilds(self):
        target = next(p for p in self.w.data['planets'].values() if p['owner_id'] == 'khar')
        target['swarm_kind'] = 'hive'
        target['ships'] = {**dict.fromkeys(target['ships'], 0), 'frigate': 10}
        target['defenses'] = dict.fromkeys(target.get('defenses', {}), 0)
        target['swarm_crystals'] = 6
        target['swarm_loot_sealed'] = False
        target['resources'] = dict.fromkeys(('metal', 'crystal', 'fuel'), 100000.)
        target['queue'] = []
        stock = dict(target['resources'])
        self.assertTrue(self.w._swarm_queue(target, 'ship', 'frigate', 8))
        self.assertTrue(all(target['resources'][k] < stock[k] for k in stock))
        target['queue'][0]['ends_at'] = NOW + 2400
        paid_queue = copy.deepcopy(target['queue'])
        buildings = dict(target['buildings'])
        op, fleets, replay = self.battle(target, {'frigate': 100, 'cruiser': 20, 'cargo': 2})
        self.assertFalse(replay['swarm_eradicated'])
        self.assertFalse(op['result']['swarm_eradicated'])
        self.assertEqual(replay['swarm_destruction_bonus'], 0)
        self.assertEqual(replay['swarm_crystals'], swarm.RAID_CRYSTALS['hive'])
        self.assertEqual((target['owner_type'], target['owner_id']), ('alien', 'khar'))
        self.assertEqual(target['buildings'], buildings)
        self.assertEqual(target['queue'], paid_queue)
        self.assertTrue(target['swarm_loot_sealed'])
        self.assertEqual(target['swarm_suppressed_until'], 0)
        self.assertFalse(any(target['ships'].values()))
        for f in fleets:
            self.assertEqual(f['swarm_destruction_bonus'], 0)
            self.assertLessEqual(sum(f['cargo'].values()) + f['swarm_crystals'], capacity(self.w._specs(f['owner_id'], 'ships'), f['ships']))
            report = next(r for r in self.w._player(f['owner_id'])['reports'] if r.get('battle_replay'))
            self.assertIn('Główny ul przetrwał', report['text'])
            self.assertNotIn('Planeta jest wolna', report['text'])
        _, _, repeat = self.battle(target, {'frigate': 10})
        self.assertEqual(repeat['rounds'], [])
        self.assertEqual(repeat['swarm_crystals'], 0)
        self.assertEqual(repeat['swarm_destruction_bonus'], 0)
        self.assertEqual(target['queue'], paid_queue)
        self.w.advance(NOW + 2400)
        self.assertEqual(target['ships']['frigate'], 8)
        self.assertEqual(target['queue'], [])

    def test_empty_outpost_has_one_bonus_independent_of_stock_and_loot_skill(self):
        target = next(p for p in self.w.data['planets'].values() if p['owner_id'] == 'khar')
        target['swarm_kind'] = 'outpost'
        target['ships'] = dict.fromkeys(target['ships'], 0)
        target['defenses'] = {}
        target['swarm_crystals'] = 0
        target['queue'] = []
        bonuses = self.w._bonuses
        with patch.object(self.w, '_bonuses', side_effect=lambda owner: {**bonuses(owner), 'swarm_loot': 5}):
            _, fleets, replay = self.battle(target, {'frigate': 10})
        self.assertEqual(replay['rounds'], [])
        self.assertEqual(replay['swarm_crystals'], swarm.DESTRUCTION_CRYSTALS)
        self.assertEqual(replay['swarm_destruction_bonus'], swarm.DESTRUCTION_CRYSTALS)
        self.assertEqual(sum(f['swarm_destruction_bonus'] for f in fleets), swarm.DESTRUCTION_CRYSTALS)
        self.assertEqual(target['owner_type'], 'empty')

    def test_stock_crystals_take_priority_when_no_capacity_remains_for_bonus(self):
        target = next(p for p in self.w.data['planets'].values() if p['owner_id'] == 'khar')
        target['swarm_kind'] = 'outpost'
        target['ships'] = {**dict.fromkeys(target['ships'], 0), 'frigate': 1}
        target['defenses'] = {}
        target['swarm_crystals'] = 6
        target['queue'] = []
        with patch('server.alliance_operations.capacity', return_value=1):
            _, fleets, replay = self.battle(target, {'frigate': 10})
        self.assertEqual(replay['swarm_crystals'], 3)
        self.assertEqual(replay['swarm_destruction_bonus'], 0)
        for f in fleets:
            self.assertEqual(f['swarm_crystals'], 1)
            self.assertEqual(sum(f['cargo'].values()), 0)

    def test_swarm_retreat_and_defeat_do_not_eradicate_nest(self):
        for outcome, target_count, attack_count in (('attacker_destroyed', 10000, 1), ('retreat', 162, 100)):
            with self.subTest(outcome=outcome):
                target = next(p for p in self.w.data['planets'].values() if p['owner_id'] == 'khar')
                target['swarm_kind'] = 'outpost'
                target['ships'] = dict.fromkeys(target['ships'], 0)
                target['ships']['cruiser'] = target_count
                target['defenses'] = dict.fromkeys(target.get('defenses', {}), 0)
                target['queue'] = []
                self.w._owned(self.a)['ships']['cruiser'] = attack_count
                buildings = dict(target['buildings'])
                op = self.create(target)
                self.join(self.a, op, {'cruiser': attack_count})
                self.w.advance(op['impact_at'])
                self.assertEqual(op['result']['outcome'], outcome)
                self.assertFalse(op['result']['swarm_eradicated'])
                self.assertEqual((target['owner_type'], target['owner_id']), ('alien', 'khar'))
                self.assertEqual(target['buildings'], buildings)

    def test_later_operation_returns_without_second_battle_after_nest_eradication(self):
        target = next(p for p in self.w.data['planets'].values() if p['owner_id'] == 'khar')
        target['swarm_kind'] = 'outpost'
        target['ships'] = {**dict.fromkeys(target['ships'], 0), 'frigate': 1}
        target['defenses'] = dict.fromkeys(target.get('defenses', {}), 0)
        target['queue'] = []
        first = self.create(target, delay=600)
        self.join(self.a, first, {'cruiser': 20})
        later = self.create(target, delay=1200)
        fleet = self.join(self.b, later, {'frigate': 10})
        ships = dict(fleet['ships'])
        self.w.advance(first['impact_at'])
        self.assertTrue(first['result']['swarm_eradicated'])
        self.w.advance(later['impact_at'])
        self.assertEqual(later['status'], 'cancelled')
        self.assertEqual(fleet['status'], 'returning')
        self.assertEqual(fleet['ships'], ships)
        self.assertFalse(any(fleet['cargo'].values()))
        self.assertFalse(any(r.get('battle_replay') for r in self.w._player(self.b)['reports']))

    def test_single_resource_pool_and_recycler_fraction_not_duplicated(self):
        self.target['ships'] = {**blank_ships(), 'frigate': 3}
        op = self.create()
        fleets = [self.join(owner, op) for owner in (self.a, self.b, self.c)]
        for f in fleets:
            f['building_effects']['wreck_recovery_fraction'] = .5
        available = self.w._lootable_resources(self.target)
        stocks = dict(self.target['resources'])
        self.w.now = op['impact_at']
        self.w._advance_alliance_operations()
        results = op['result']['participants']
        metal_cost = self.w._specs(self.enemy, 'ships')['frigate'][2][0] * 3
        recovered = sum(x['recovered_metal'] for x in results)
        self.assertLessEqual(recovered, metal_cost * .5)
        for resource in ('metal', 'crystal', 'fuel'):
            cargo = sum(f['cargo'][resource] for f in fleets)
            self.assertEqual(stocks[resource] - self.target['resources'][resource], cargo - (recovered if resource == 'metal' else 0))
            self.assertLessEqual(stocks[resource] - self.target['resources'][resource], available[resource])

    def test_defense_real_arrival_native_grove_only_and_return_ownership(self):
        host = self.w._owned(self.c)
        host['buildings']['renewal_grove'] = 5
        support = self.support(self.b, host)
        arrival = support['arrives_at']
        self.assertFalse(self.w._alliance_has_support(host))
        host_before = dict(host['ships'])
        self.w.advance(arrival)
        self.assertTrue(self.w._alliance_has_support(host))
        self.assertEqual(support['status'], 'holding')
        self.assertEqual(host['ships'], host_before)
        native = self.w._coalition_formation(self.c, dict(host['ships']), 'host', target=host)
        guest = self.w._coalition_formation(self.b, support['ships'], 'guest', fleet=support)
        self.assertEqual(guest['regeneration'], self.w._rules(self.b)['regeneration_fraction'])
        self.assertGreater(native['regeneration'], self.w._rules(self.c)['regeneration_fraction'])
        until = support['hold_until']
        self.w.advance(until)
        self.assertFalse(self.w._alliance_has_support(host))
        self.assertEqual(support['status'], 'returning')
        self.assertEqual(support['arrives_at'] - until, support['return_seconds'])
        self.w.advance(support['arrives_at'])
        self.assertEqual(host['ships'], host_before)
        self.assertEqual(self.w._owned(self.b)['ships']['frigate'], 300)

    def test_single_attack_fights_allied_support_without_merging_ships(self):
        host = self.w._owned(self.c)
        host['ships'] = {**blank_ships(), 'frigate': 3}
        support = self.support(self.b, host, {'frigate': 30})
        self.w.advance(support['arrives_at'])
        f = {'id': 'ordinary-attack', 'owner_id': self.enemy, 'origin_id': self.target['id'], 'target_id': host['id'],
             'mission': 'attack', 'status': 'outbound', 'ships': {**blank_ships(), 'frigate': 20}, 'cargo': dict.fromkeys(('metal', 'crystal', 'fuel'), 0),
             'seconds': 100, 'started_at': self.w.now - 100, 'arrives_at': self.w.now}
        self.w.data['fleets'][f['id']] = f
        self.w._complete_fleet(f)
        replay = next(r['battle_replay'] for r in self.w._player(self.enemy)['reports'] if r.get('battle_replay'))
        self.assertEqual({p['owner_id'] for p in replay['defender']['participants']}, {self.b, self.c})
        self.assertLessEqual(host['ships']['frigate'], 3)
        guest = next(p for p in replay['participant_results'] if p['owner_id'] == self.b)
        self.assertEqual(guest['survivors']['frigate'], support['ships']['frigate'])

    def test_departure_recalls_own_operations_and_defense_without_theft(self):
        op = self.create()
        f = self.join(self.b, op)
        support = self.support(self.c, self.w._owned(self.b))
        self.w._alliance_member_departed(self.b, self.alliance['id'])
        self.assertEqual(f['status'], 'returning')
        self.assertEqual(support['status'], 'returning')
        self.assertNotIn(self.b, op['participants'])
        self.assertEqual(op['status'], 'cancelled')

    def test_operation_ship_names_and_retry_messages_localize_after_serialization(self):
        op = self.create()
        self.join(self.a, op)
        self.w.data = json.loads(json.dumps(self.w.data))
        with language_scope('en'):
            view = self.w.alliance_operations_view(self.b)
            participant = next(x for x in view['operations'] if x['id'] == op['id'])['participants'][0]
            expected = self.w._specs(self.a, 'ships')['frigate'][0]
            self.assertEqual(next(s['name'] for s in participant['ship_specs'] if s['key'] == 'frigate'), expected)
            response = self.w.alliance_operation(self.a, {'action': 'create', 'target_id': self.target['id'], 'delay_seconds': 600, 'request_id': 'operation-1'})
            self.assertIn('Operation created', response['message'])

    def test_protected_host_cannot_shelter_allied_warships(self):
        host = self.w._owned(self.c)
        self.w._player(self.c)['protected_until'] = NOW + 3600
        before = copy.deepcopy(self.w.data)
        with self.assertRaises(GameError) as denied:
            self.support(self.b, host)
        self.assertEqual(denied.exception.status, 403)
        self.assertEqual(self.w.data, before)
        self.w._player(self.c)['protected_until'] = NOW
        self.w._player(self.b)['protected_until'] = NOW + 3600
        f = self.support(self.b, host)
        self.assertEqual(self.w._player(self.b)['protected_until'], NOW)
        self.assertEqual(f['status'], 'outbound')

    def test_support_arrival_and_expiry_order_at_exact_attack_timestamp(self):
        host = self.w._owned(self.c)
        support = self.support(self.b, host)
        self.w.now = support['arrives_at']
        self.w._advance_alliance_operations()
        self.assertTrue(self.w._alliance_has_support(host))
        self.assertEqual(support['status'], 'holding')
        self.w.now = support['hold_until']
        self.w._advance_alliance_operations()
        self.assertFalse(self.w._alliance_has_support(host))
        self.assertEqual(support['status'], 'returning')

    def test_scouts_alone_cannot_receive_crystal_share(self):
        op = self.create()
        before = copy.deepcopy(self.w.data)
        with self.assertRaises(GameError):
            self.join(self.a, op, {'scout': 1})
        self.assertEqual(self.w.data, before)
        self.assertEqual(apportion(3, {'real': 100, 'scout': 0}, {'real': 100, 'scout': 10}), {'real': 3, 'scout': 0})

    def test_fixed_impact_no_time_or_tunnel_override_and_join_lock(self):
        op = self.create()
        with self.assertRaises(GameError):
            self.action(self.a, 'join', operation_id=op['id'], planet_id=self.w._owned(self.a)['id'], ships={'frigate': 3}, travel_mode='tunnel')
        f = self.join(self.a, op, {'frigate': 3})
        self.assertEqual(f['arrives_at'], op['impact_at'])
        self.w.now = op['impact_at'] - 30
        with self.assertRaises(GameError):
            self.join(self.b, op)
        self.w.now = NOW
        with patch.object(self.w, '_flight_numbers', return_value=(1000, 5)):
            with self.assertRaises(GameError):
                self.join(self.b, op)
        self.assertEqual(op['impact_at'], NOW + 600)

    def test_target_joining_alliance_recalls_instead_of_friendly_fire(self):
        op = self.create()
        f = self.join(self.a, op)
        self.w._alliance_join(self.enemy, self.alliance, 'member')
        self.assertEqual(f['status'], 'returning')
        self.assertEqual(op['status'], 'cancelled')
        self.assertFalse(any(r.get('battle_replay') for r in self.w._player(self.a)['reports']))

    def test_creation_only_shares_frozen_known_target_not_live_intel(self):
        self.w._capture_planetary_intel(self.a, self.target)
        self.target['name'] = 'Secret new name'
        op = self.create()
        # create helper captured the current name; change it after planning.
        self.target['name'] = 'Later secret name'
        self.target['resources']['metal'] = 1234567
        view = self.w.alliance_operations_view(self.b)
        shared = next(x for x in view['operations'] if x['id'] == op['id'])
        self.assertNotIn('Later secret name', json.dumps(shared))
        self.assertNotIn('1234567', json.dumps(shared))
        self.assertNotIn(self.target['id'], self._known_ids(self.b))

    def _known_ids(self, owner):
        return set(self.w._operation_known_targets(owner))


if __name__ == '__main__':
    unittest.main()
