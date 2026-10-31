"""Authoritative skill purchases and the budgeted, destructible Swarm economy."""
import copy
import math
from pathlib import Path
import tempfile
import unittest

from server.main import GameError, RESOURCES, blank_ships, scaled_cost
from tests.world_fixture import LocalTestWorld as World
from server import skill_tree, swarm

START = 1_900_000_000.0


class SwarmProgression(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'progression.sqlite3')
        self.world = World(self.path, speed=10, now=START)
        result = self.world.register('First Colony', 'password-123')
        self.player = result['state']['player']['id']
        self.world.action(self.player, {'type': 'choose_race', 'race_id': 'zetans'})
        self.world.data['alien']['next_expansion_at'] = START + 10_000_000

    def tearDown(self):
        self.world.close()
        self.tmp.cleanup()

    def home(self):
        return self.world._owned(self.player)

    def outpost(self):
        """Controlled low-defense legacy colony for isolated accounting tests.

        New worlds deliberately have no weak starter outposts. This helper is
        only for testing old-save colony clearing and reward settlement.
        """
        target = next(p for p in self.world.data['planets'].values() if p['owner_type'] == 'empty')
        swarm.seed(target, self.world.now, hive=False)
        target['ships'] = dict.fromkeys(swarm.SHIPS, 0)
        target['ships']['frigate'] = 1
        return target

    def hive(self):
        return next(p for p in self.world.data['planets'].values() if p.get('swarm_kind') == 'hive')

    def launch(self, target, ships=None):
        result = self.world.action(self.player, {'type': 'fleet', 'mission': 'attack',
                                  'target_id': target['id'], 'ships': ships or {'frigate': 3}})
        return self.world.data['fleets'][result['state']['fleets'][0]['id']]

    def purchase(self, node, request=None):
        payload = {'type': 'unlock_skill', 'node_id': node}
        if request:
            payload['request_id'] = request
        return self.world.action(self.player, payload)

    def unlock_all(self):
        self.world.data['players'][self.player]['swarm_crystals'] = 10**12
        while True:
            tree = self.world.state(self.player)['skill_tree']
            node = next((node for node in tree['nodes'] if node['available']), None)
            if node is None:
                break
            self.purchase(node['id'])

    def test_purchase_is_adjacent_atomic_idempotent_and_persistent(self):
        before = copy.deepcopy(self.world.data)
        for node in ('zetans_0_0', 'automatons_root', 'wrong', ['zetans_0_0'], None):
            with self.subTest(node=node), self.assertRaises(GameError):
                self.purchase(node)
            self.assertEqual(before, self.world.data)
        player = self.world.data['players'][self.player]
        player['swarm_crystals'] = 10
        first = self.purchase('zetans_0_0', 'buy-once')
        self.assertEqual(first['state']['player']['swarm_crystals'], 9)
        after = copy.deepcopy(self.world.data)
        replay = self.purchase('zetans_0_0', 'buy-once')
        self.assertEqual(first['message'], replay['message'])
        self.assertEqual(self.world.data, after)
        with self.assertRaises(GameError):
            self.purchase('zetans_1_0', 'buy-once')
        self.world.close()
        self.world = World(self.path, speed=10, now=START)
        state = self.world.login('First Colony', 'password-123')['state']
        self.assertIn('zetans_0_0', state['skill_tree']['unlocked'])
        self.assertEqual(state['player']['swarm_crystals'], 9)
        self.assertEqual(self.purchase('zetans_0_0', 'buy-once')['state']['player']['swarm_crystals'], 9)

    def test_only_actual_swarm_stock_can_be_looted_and_settled_once(self):
        target = self.outpost()
        target['swarm_crystals'] = 3.9
        self.world._capture_planetary_intel(self.player, target)
        fleet = self.launch(target)
        # Settle directly at the existing timestamp to isolate stock accounting.
        self.world._complete_fleet(fleet)
        self.assertEqual(fleet['swarm_crystals'], 6)  # Three from stock, three for destroying the outpost.
        self.assertEqual(fleet['swarm_destruction_bonus'], 3)
        self.assertEqual(self.world.state(self.player)['player']['swarm_crystals'], 0)
        self.assertEqual(target['owner_type'], 'empty')
        self.assertEqual(target['owner_id'], '')
        self.assertFalse(any(target['buildings'].values()))
        self.assertNotIn('swarm_crystals', target)
        self.world._complete_fleet(fleet)
        self.assertEqual(self.world.state(self.player)['player']['swarm_crystals'], 6)
        self.world._complete_fleet(fleet)  # Stale event cannot pay a second time.
        self.assertEqual(self.world.state(self.player)['player']['swarm_crystals'], 6)
        self.world.advance(START + 1000)
        self.assertNotIn('swarm_crystals', target)
        self.assertEqual(self.world.state(self.player)['player']['swarm_crystals'], 6)

    def test_pvp_and_cargo_cannot_create_or_steal_skill_currency(self):
        enemy = self.world.register('Other Colony', 'password-123')['state']['player']['id']
        player = self.world.data['players'][enemy]
        player.update(protected_until=0, swarm_crystals=50)
        target = self.world._owned(enemy)
        target['ships'] = blank_ships()
        target['swarm_crystals'] = 80  # A stale non-NPC field must not become a source.
        fleet = self.launch(target)
        self.world._complete_fleet(fleet)
        self.world._complete_fleet(fleet)
        self.assertEqual(self.world.data['players'][enemy]['swarm_crystals'], 50)
        self.assertEqual(self.world.data['players'][self.player]['swarm_crystals'], 0)
        with self.assertRaises(GameError):
            self.world.action(self.player, {'type': 'fleet', 'mission': 'colonize',
                'target_id': self.outpost()['id'], 'ships': {'colonizer': 1},
                'cargo': {'swarm_crystals': 10}})
        old = target['swarm_crystals']
        self.world._produce(3600)
        self.assertEqual(target['swarm_crystals'], old)

    def test_actual_fuel_capacity_production_and_task_duration_use_purchased_skills(self):
        home = self.home()
        target = self.outpost()
        payload = {'mission': 'attack', 'target_id': target['id'], 'ships': {'frigate': 3}}
        initial_quote = self.world.preview(self.player, payload)
        initial_state = self.world.state(self.player)
        self.unlock_all()
        state = self.world.state(self.player)
        quote = self.world.preview(self.player, payload)
        self.assertLess(quote['seconds'], initial_quote['seconds'])
        self.assertLess(quote['fuel_cost'], initial_quote['fuel_cost'])
        self.assertGreater(quote['capacity'], initial_quote['capacity'])
        for resource in RESOURCES:
            self.assertGreater(state['production'][resource], initial_state['production'][resource])
        self.assertGreater(state['energy']['supply'], initial_state['energy']['supply'])
        before = dict(home['resources'])
        self.world._produce(3600)
        for resource in RESOURCES:
            self.assertAlmostEqual(home['resources'][resource] - before[resource], state['production'][resource])
        for group, kind, key in (('buildings', 'build', 'metal_mine'), ('research', 'research', 'weapons'), ('ships', 'ship', 'scout')):
            base = next(e for e in initial_state['catalog'][group] if e['key'] == key)
            entry = next(e for e in self.world.state(self.player)['catalog'][group] if e['key'] == key)
            self.assertLess(entry['seconds'], base['seconds'])
            self.world.action(self.player, {'type': kind, 'key': key})
            self.assertEqual(home['queue'][0]['ends_at'] - self.world.now, entry['seconds'])
            self.world.advance(home['queue'][0]['ends_at'])
        frigate = next(e for e in state['catalog']['ships'] if e['key'] == 'frigate')
        initial_frigate = next(e for e in initial_state['catalog']['ships'] if e['key'] == 'frigate')
        self.assertGreater(frigate['effective_attack'], initial_frigate['effective_attack'])
        self.assertGreater(frigate['hull'], initial_frigate['hull'])
        self.assertEqual(frigate['first_volley_multiplier'], 1.35)  # No legacy double count.
        self.assertEqual(frigate['regeneration_fraction'], .35)  # Foreign root was earned.
        self.assertEqual(frigate['damage_reduction'], .12)

    def test_rare_loot_bonus_is_capped_by_real_stock_and_capacity(self):
        self.unlock_all()
        target = self.outpost()
        stage = swarm.kind(target)
        stock = swarm.CRYSTAL_CAPS[stage]
        target['swarm_crystals'] = stock
        self.world._capture_planetary_intel(self.player, target)
        fleet = self.launch(target)
        self.world._complete_fleet(fleet)
        self.assertEqual(fleet['swarm_destruction_bonus'], 3)
        ordinary = fleet['swarm_crystals'] - fleet['swarm_destruction_bonus']
        self.assertGreater(ordinary, swarm.RAID_CRYSTALS[stage])
        self.assertLessEqual(ordinary, stock)
        capacity = int(sum(self.world._specs(self.player, 'ships')[key][6] * n for key, n in fleet['ships'].items()))
        self.assertLessEqual(sum(fleet['cargo'].values()) + fleet['swarm_crystals'], capacity)

    def test_ai_queues_and_flights_spend_real_resources_and_real_escorts(self):
        hive = self.hive()
        hive['ships']['colonizer'] = 1  # Isolated paid-flight fixture.
        self.world.data['alien']['swarm_next_colonization_at'] = self.world.now
        target = next(p for p in self.world.data['planets'].values() if p['owner_type'] == 'empty')
        sent = dict.fromkeys(swarm.SHIPS, 0)
        sent.update(swarm.EXPANSION_ESCORT, colonizer=1)
        old_ships = dict(hive['ships'])
        old_fuel = hive['resources']['fuel']
        fleet = self.world._swarm_launch(hive, target, 'colonize', sent)
        self.assertIsNotNone(fleet)
        self.assertEqual(old_ships['colonizer'] - hive['ships']['colonizer'], 1)
        for key, count in swarm.EXPANSION_ESCORT.items():
            self.assertEqual(old_ships[key] - hive['ships'][key], count)
        _, fuel = self.world._flight_numbers(hive, target, fleet['ships'])
        self.assertEqual(old_fuel - hive['resources']['fuel'], fuel)
        self.world._complete_fleet(fleet)
        colony = self.world.data['planets'][fleet['target_id']]
        for key, count in swarm.EXPANSION_ESCORT.items():
            self.assertEqual(colony['ships'][key], count)  # Actual escort, no free garrison.
        self.assertEqual(colony['ships']['colonizer'], 0)
        self.assertEqual(colony['swarm_crystals'], 0)
        self.assertEqual(colony['owner_id'], 'khar')
        self.assertTrue(swarm.ready(colony))
        hive['queue'] = []
        hive['ships']['colonizer'] = 0
        before = dict(hive['resources'])
        self.assertTrue(self.world._swarm_queue(hive, 'ship', 'colonizer'))
        expected = scaled_cost(swarm.SHIPS['colonizer'][2], 0)
        for resource in RESOURCES:
            self.assertEqual(before[resource] - hive['resources'][resource], expected[resource])
        self.assertEqual(hive['queue'][0]['ends_at'] - self.world.now, math.ceil(swarm.SHIPS['colonizer'][3] / self.world.speed / (1 + .1 * max(0, hive['buildings']['shipyard'] - 1))))

    def test_offline_interval_never_replays_ai_or_exceeds_stock_caps(self):
        self.world.data['alien']['next_expansion_at'] = START
        original = sum(p['owner_id'] == 'khar' for p in self.world.data['planets'].values())
        self.world.advance(START + 365 * 86400)
        self.assertEqual(sum(p['owner_id'] == 'khar' for p in self.world.data['planets'].values()), original)
        self.assertLessEqual(len(self.world.data['fleets']), original)
        for p in self.world.data['planets'].values():
            if p['owner_id'] == 'khar':
                self.assertLessEqual(p['swarm_crystals'], swarm.CRYSTAL_CAPS[swarm.kind(p)])
        self.assertEqual(self.world.data['players'][self.player]['swarm_crystals'], 0)

    def test_invasions_respect_empty_worlds_protection_and_real_day_pacing(self):
        hive = self.hive()
        sent = dict.fromkeys(swarm.SHIPS, 0); sent.update(swarm.EXPANSION_ESCORT)
        hive['swarm_next_attack_at'] = 0
        before = copy.deepcopy(self.world.data)
        self.assertIsNone(self.world._swarm_launch(hive, self.home(), 'attack', sent))
        self.assertEqual(before, self.world.data)
        # Fill otherwise empty worlds to exercise the last-resort invasion rule.
        for planet in self.world.data['planets'].values():
            if planet['owner_type'] == 'empty':
                planet.update(owner_type='player', owner_id=self.player)
        self.assertIsNone(self.world._swarm_launch(hive, self.home(), 'attack', sent))
        self.world.data['players'][self.player]['protected_until'] = 0
        raid = self.world._swarm_launch(hive, self.home(), 'attack', sent)
        self.assertIsNotNone(raid)
        self.assertEqual(hive['swarm_next_attack_at'], self.world.now + swarm.ATTACK_SECONDS)
        self.assertTrue(swarm.ready(hive))
        self.assertIsNone(self.world._swarm_launch(hive, self.home(), 'attack', sent))

    def test_eradicating_origin_redirects_swarm_return_to_an_owned_hive(self):
        origin = self.outpost()
        hive = next(p for p in self.world.data['planets'].values() if p.get('swarm_kind') == 'hive')
        ships = dict.fromkeys(swarm.SHIPS, 0); ships['frigate'] = 2
        # Legacy returning mission: strategic launch policy is tested separately.
        fleet = {'id': 'legacy-npc-return', 'owner_id': 'khar', 'origin_id': origin['id'],
                 'target_id': hive['id'], 'mission': 'scout', 'status': 'returning',
                 'ships': ships, 'cargo': dict.fromkeys(RESOURCES, 0), 'swarm_crystals': 0,
                 'seconds': 10, 'arrives_at': self.world.now}
        self.world.data['fleets'][fleet['id']] = fleet
        origin.update(owner_id=self.player, owner_type='player')
        original_player_ships = dict(origin['ships'])
        fleet['status'] = 'returning'
        self.world._complete_fleet(fleet)
        self.assertEqual(origin['ships'], original_player_ships)
        self.assertNotEqual(fleet['origin_id'], origin['id'])
        self.assertEqual(self.world.data['planets'][fleet['origin_id']]['owner_id'], 'khar')

    def test_upgrade_rebuilds_npc_frontier_once_without_touching_player_wallet(self):
        self.world.data.pop('progression_version')
        self.world.data['players'][self.player]['swarm_crystals'] = 9
        original_home = copy.deepcopy(self.home())
        self.world.close()
        self.world = World(self.path, speed=10, now=START)
        planets = self.world.data['planets'].values()
        self.assertEqual(sum(p.get('swarm_kind') == 'hive' for p in planets), swarm.INITIAL_HIVES)
        self.assertEqual(sum(p.get('swarm_kind') == 'outpost' for p in planets), 0)
        self.assertEqual(self.home(), original_home)
        self.assertEqual(self.world.data['players'][self.player]['swarm_crystals'], 9)
        target = self.hive(); target['swarm_crystals'] = 1
        target_id = target['id']
        self.world.close()
        self.world = World(self.path, speed=10, now=START)
        self.assertEqual(self.world.data['planets'][target_id]['swarm_crystals'], 1)
        self.assertEqual(self.world.data['players'][self.player]['swarm_crystals'], 9)


    def test_exact_capacity_at_sixteen_percent_accepts_the_entire_hold(self):
        other = self.world.register('Cargo Robots', 'password-123')['state']['player']['id']
        self.world.action(other, {'type': 'choose_race', 'race_id': 'automatons'})
        self.world.data['players'][other]['swarm_crystals'] = 100
        for step in range(4):
            self.world.action(other, {'type': 'unlock_skill', 'node_id': f'automatons_1_{step}'})
        home = self.world._owned(other)
        target = next(p for p in self.world.data['planets'].values() if p['owner_type'] == 'empty')
        target.update(owner_id=other, owner_type='player')
        payload = {'type': 'fleet', 'mission': 'transport', 'target_id': target['id'],
                   'ships': {'cargo': 1}, 'cargo': {'metal': 1856}}
        preview = self.world.preview(other, payload)
        self.assertEqual(preview['capacity'], 1856)
        response = self.world.action(other, payload)
        self.assertEqual(response['state']['fleets'][0]['cargo']['metal'], 1856)

    def test_running_task_keeps_immutable_duration_when_speed_skill_is_bought(self):
        self.world.data['players'][self.player]['swarm_crystals'] = 10**12
        self.world.action(self.player, {'type': 'ship', 'key': 'frigate', 'amount': 2})
        task_before = copy.deepcopy(self.home()['queue'][0])
        self.assertEqual(task_before['started_at'], START)
        self.assertEqual(task_before['seconds'], task_before['ends_at'] - START)
        self.unlock_all()
        task_after = self.world.state(self.player)['queue'][0]
        self.assertEqual(task_after, task_before)
        current = next(e for e in self.world.state(self.player)['catalog']['ships'] if e['key'] == 'frigate')
        self.assertLess(current['seconds'] * 2, task_after['seconds'])
        energy = next(e for e in self.world.state(self.player)['catalog']['buildings'] if e['key'] == 'power_plant')
        self.assertIn(f"{energy['energy_supply_per_level']:g}".replace('.', ','), energy['description'])

    def test_hive_victory_preserves_hatchery_and_paid_rebuilding(self):
        target = self.hive()
        target['resources'] = dict.fromkeys(RESOURCES, 1000000.)
        target['ships']['frigate'] = 1
        target['swarm_crystals'] = 3
        self.world._capture_planetary_intel(self.player, target)
        self.assertTrue(self.world._swarm_queue(target, 'ship', 'frigate', 2))
        task = copy.deepcopy(target['queue'][0])
        buildings = dict(target['buildings'])
        self.home()['ships']['frigate'] = 2500
        self.home()['resources']['fuel'] = 10_000_000.0
        fleet = self.launch(target, {'frigate': 2500})
        self.world._complete_fleet(fleet)
        self.assertEqual(target['owner_id'], 'khar')
        self.assertEqual(target['buildings'], buildings)
        self.assertEqual(target['queue'], [task])
        self.assertEqual(target['swarm_suppressed_until'], 0)
        self.assertTrue(target['swarm_loot_sealed'])
        self.assertEqual(fleet['swarm_crystals'], 3)
        self.assertEqual(fleet['swarm_destruction_bonus'], 0)
        self.world._alien_turn()
        self.assertEqual(target['queue'], [task])
        self.world.advance(task['ends_at'])
        self.assertEqual(target['ships']['frigate'], task['amount'])
        # Main hives retain their already paid reconstruction after defeat.
        self.assertFalse(target['queue'])
        remaining_metal = target['resources']['metal']
        self.world._alien_turn()
        self.assertTrue(target['queue'])
        self.assertLess(target['resources']['metal'], remaining_metal)
        self.assertEqual(target['swarm_crystals'], 0)

    def test_two_players_can_use_real_sequential_attrition_without_duplicate_loot(self):
        """Separate assaults retain real losses until the surviving attack wins."""
        target = self.hive()
        # A grown nest fixture; freshly seeded nests deliberately start empty.
        target['ships']['frigate'] = 1250
        target['swarm_crystals'] = 3
        initial_defense = sum(target['ships'].values())
        initial_stock = int(target['swarm_crystals'])
        other = self.world.register('Second Assault', 'password-123')['state']['player']['id']
        self.world.action(other, {'type': 'choose_race', 'race_id': 'zetans'})
        for player in (self.player, other):
            home = self.world._owned(player)
            # Equal prepared forces: the first cannot defeat an intact fortress.
            home['ships']['frigate'] = 230
            home['resources']['fuel'] = 1_000_000.0
            self.world._capture_planetary_intel(player, target)
        first = self.launch(target, {'frigate': 230})
        response = self.world.action(other, {'type': 'fleet', 'mission': 'attack',
            'target_id': target['id'], 'ships': {'frigate': 230}})
        second = self.world.data['fleets'][response['state']['fleets'][0]['id']]
        self.world._complete_fleet(first)
        self.assertEqual(sum(first['ships'].values()), 0)
        self.assertEqual(first['swarm_crystals'], 0)
        self.assertGreater(sum(target['ships'].values()), 0)
        self.assertLess(sum(target['ships'].values()), initial_defense)
        self.assertEqual(target['swarm_crystals'], initial_stock)
        self.world._complete_fleet(second)
        self.assertEqual(sum(target['ships'].values()), 0)
        self.assertGreater(sum(second['ships'].values()), 0)
        self.assertEqual(second['swarm_crystals'], initial_stock)
        self.assertEqual(self.world.data['players'][other]['swarm_crystals'], 0)
        self.assertEqual(target['swarm_crystals'], 0)
        self.world._complete_fleet(second)
        self.world._complete_fleet(second)
        self.assertEqual(self.world.data['players'][other]['swarm_crystals'], initial_stock)
        self.assertEqual(self.world.data['players'][self.player]['swarm_crystals'], 0)
        self.assertEqual(target['owner_id'], 'khar')
        self.assertEqual(target['swarm_suppressed_until'], 0)
        self.assertTrue(target['swarm_loot_sealed'])
        self.assertEqual(second['swarm_destruction_bonus'], 0)

    def test_purchased_anti_swarm_damage_applies_in_battle_but_not_to_pvp(self):
        self.world.data['players'][self.player]['swarm_crystals'] = 100
        self.purchase('zetans_2_0')
        hive_id = next(p['id'] for p in self.world.data['planets'].values() if p.get('swarm_kind') == 'hive')
        other = self.world.register('Combat Robots', 'password-123')['state']['player']['id']
        other_id = self.world._owned(other)['id']
        self.world.data['players'][other]['protected_until'] = 0
        before = copy.deepcopy(self.world.data)
        damage = []
        original_damage = self.world._damage
        def record_damage(ships, hit, wounds, specs=None, damage_reduction=0.0, type_reductions=None):
            damage.append(hit)
            return original_damage(ships, hit, wounds, specs, damage_reduction, type_reductions)
        self.world._damage = record_damage
        def first_hit(target_id, upgraded):
            self.world.data = copy.deepcopy(before)
            if upgraded:
                self.purchase('zetans_2_1')
            target = self.world.data['planets'][target_id]
            target['ships']['frigate'] = 24
            fleet = self.launch(target)
            damage.clear()
            self.world._battle(fleet, target)
            return damage[0]
        base_npc, upgraded_npc = first_hit(hive_id, False), first_hit(hive_id, True)
        base_player, upgraded_player = first_hit(other_id, False), first_hit(other_id, True)
        self.assertAlmostEqual(upgraded_npc, base_npc * 1.08)
        self.assertAlmostEqual(upgraded_player, base_player)


if __name__ == '__main__':
    unittest.main()
