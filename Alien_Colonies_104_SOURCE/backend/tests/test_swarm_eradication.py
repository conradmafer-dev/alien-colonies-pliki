"""Destroy expansion nests for a bounded reward while main hives survive."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from server import swarm
from server.main import GALAXIES_BY_ID, GameError, RESOURCES, blank_ships, fleet_capacity
from tests.world_fixture import LocalTestWorld as World


START = 1_900_000_000.0


class SwarmEradicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'eradication.sqlite3')
        self.world = World(self.path, now=START)
        result = self.world.register('Liberator', 'fixture-password-123')
        self.player = result['state']['player']['id']
        self.world.action(self.player, {'type': 'choose_race', 'race_id': 'zetans'})
        self.home = self.world._owned(self.player)
        self.home['resources'] = dict.fromkeys(RESOURCES, 1_000_000_000.)
        self.home['ships'] = {**blank_ships(), 'frigate': 1000, 'colonizer': 4}
        self.home['buildings']['observatory'] = 0
        self.world.data['alien']['next_expansion_at'] = START + 1_000_000_000

    def tearDown(self):
        self.world.close()
        self.tmp.cleanup()

    def nest(self, *, hive=False):
        target = next(p for p in self.world.data['planets'].values()
                      if p['owner_type'] == 'empty' and p['galaxy_id'] == 'g1'
                      and p['system_id'] != self.home['system_id'])
        swarm.seed(target, self.world.now, hive=hive)
        target['ships']['frigate'] = 2
        target['defenses']['acid_spire'] = 1
        target['resources'] = dict.fromkeys(RESOURCES, 10_000.)
        target['swarm_crystals'] = 3.9
        self.world._capture_planetary_intel(self.player, target)
        self.world._capture_swarm_intel(self.player, target)
        return target

    def launch(self, target, *, mission='attack', ships=None):
        previous = set(self.world.data['fleets'])
        self.world.action(self.player, {'type': 'fleet', 'mission': mission,
                                       'target_id': target['id'],
                                       'ships': ships or {'frigate': 100}})
        return self.world.data['fleets'][(set(self.world.data['fleets']) - previous).pop()]

    def assert_empty(self, target):
        self.assertEqual((target['owner_type'], target['owner_id']), ('empty', ''))
        for field in ('ships', 'defenses', 'buildings', 'resources'):
            self.assertFalse(any(target[field].values()), field)
        self.assertEqual(target['queue'], [])
        self.assertFalse(any(key.startswith('swarm_') for key in target))

    def battle_report(self):
        return next(r for r in self.world._player(self.player)['reports']
                    if r.get('battle_replay'))

    def test_outpost_is_liberated_after_real_combat(self):
        target = self.nest()
        identity = {k: copy.deepcopy(target[k]) for k in
                    ('id', 'name', 'galaxy_id', 'system_id', 'slot', 'environment', 'rare_trait')}
        fleet = self.launch(target)
        self.world._complete_fleet(fleet)
        self.assert_empty(target)
        self.assertEqual(identity, {k: target[k] for k in identity})
        self.assertEqual(fleet['status'], 'returning')
        replay = self.battle_report()['battle_replay']
        self.assertEqual(replay['outcome'], 'attacker_wins')
        self.assertGreater(len(replay['rounds']), 0)
        self.assertEqual(replay['swarm_destruction_bonus'], 3)
        self.assertIn('Planeta jest wolna', self.battle_report()['text'])

    def test_hive_survives_preserves_paid_rebuilding_and_requires_defense_for_next_loot(self):
        target = self.nest(hive=True)
        target['swarm_crystals'] = 6
        self.assertTrue(self.world._swarm_queue(target, 'ship', 'frigate', 2))
        buildings, queue = copy.deepcopy(target['buildings']), copy.deepcopy(target['queue'])
        first = self.launch(target)
        self.world._complete_fleet(first)
        self.assertEqual((target['owner_type'], target['owner_id']), ('alien', 'khar'))
        self.assertEqual(target['buildings'], buildings)
        self.assertEqual(target['queue'], queue)
        self.assertTrue(target['swarm_loot_sealed'])
        self.assertEqual(target['swarm_crystals'], 3)
        self.assertEqual(first['swarm_crystals'], 3)
        self.assertEqual(first.get('swarm_destruction_bonus', 0), 0)
        with self.assertRaises(GameError):
            self.world.preview(self.player, {'mission': 'colonize', 'target_id': target['id'], 'ships': {'colonizer': 1}})
        self.world._complete_fleet(first)
        second = self.launch(target)
        self.world._complete_fleet(second)
        self.assertEqual(self.battle_report()['battle_replay']['rounds'], [])
        self.assertEqual(second['swarm_crystals'], 0)
        self.assertEqual(second.get('swarm_destruction_bonus', 0), 0)
        self.assertEqual(target['swarm_crystals'], 3)
        self.assertEqual(target['queue'], queue)
        self.world._complete_fleet(second)
        self.world.advance(queue[0]['ends_at'])
        self.assertEqual(target['ships']['frigate'], 2)
        self.assertTrue(swarm.ready(target))
        third = self.launch(target)
        self.world._complete_fleet(third)
        self.assertEqual(third['swarm_crystals'], 3)
        self.assertEqual(third.get('swarm_destruction_bonus', 0), 0)
        self.assertEqual(target['owner_id'], 'khar')

    def test_attack_then_colonize_cancels_rebuild_and_survives_reload(self):
        target = self.nest()
        self.assertTrue(self.world._swarm_queue(target, 'ship', 'frigate', 2))
        fleet = self.launch(target)
        # The already paid work is due after the assault arrives.
        rebuild_at = fleet['arrives_at'] + 86400
        target['queue'][0]['ends_at'] = rebuild_at
        self.world.advance(fleet['arrives_at'])
        self.assert_empty(target)
        colony = self.launch(target, mission='colonize', ships={'colonizer': 1, 'frigate': 2})
        self.world.advance(colony['arrives_at'])
        self.assertEqual(target['owner_id'], self.player)
        self.assertEqual(target['ships']['colonizer'], 0)
        self.assertEqual(target['ships']['frigate'], 2)
        self.world.advance(rebuild_at + 1)
        self.assertEqual(target['ships']['frigate'], 2)
        self.assertFalse(target['defenses'])
        identity = target['id']
        reset_marker = self.world.data['swarm_reset_at']
        self.world.close()
        self.world = World(self.path, now=rebuild_at + 1)
        target = self.world.data['planets'][identity]
        self.assertEqual(target['owner_id'], self.player)
        self.assertEqual(target['ships']['frigate'], 2)
        self.assertFalse(any(k.startswith('swarm_') for k in target))
        self.assertEqual(self.world.data['swarm_reset_at'], reset_marker)

    def test_stock_capacity_and_return_are_settled_once_before_erasure(self):
        target = self.nest()
        stock = dict(target['resources'])
        fleet = self.launch(target)
        self.world._complete_fleet(fleet)
        self.assert_empty(target)
        self.assertEqual(fleet['swarm_crystals'], 6)
        self.assertEqual(fleet['swarm_destruction_bonus'], 3)
        self.assertEqual(self.world._player(self.player)['swarm_crystals'], 0)
        capacity = fleet_capacity(self.world._specs(self.player, 'ships'), fleet['ships'])
        self.assertLessEqual(sum(fleet['cargo'].values()) + fleet['swarm_crystals'], capacity)
        self.assertGreater(sum(fleet['cargo'].values()), 0)
        for resource, count in fleet['cargo'].items():
            self.assertLessEqual(count, stock[resource])
        before = copy.deepcopy(self.home)
        cargo, ships = dict(fleet['cargo']), dict(fleet['ships'])
        self.world._complete_fleet(fleet)
        self.assertEqual(self.world._player(self.player)['swarm_crystals'], 6)
        for resource, count in cargo.items():
            self.assertEqual(self.home['resources'][resource], min(1_000_000_000, before['resources'][resource] + count))
        for key, count in ships.items():
            self.assertEqual(self.home['ships'][key], before['ships'].get(key, 0) + count)
        settled = copy.deepcopy(self.home)
        self.world._complete_fleet(fleet)
        self.assertEqual(self.home, settled)
        self.assertEqual(self.world._player(self.player)['swarm_crystals'], 6)

    def test_undefended_outpost_pays_only_the_destruction_bonus(self):
        target = self.nest()
        target['ships'] = dict.fromkeys(swarm.SHIPS, 0)
        target['defenses'] = {}
        fleet = self.launch(target)
        self.world._complete_fleet(fleet)
        self.assert_empty(target)
        self.assertEqual(fleet['swarm_crystals'], 3)
        self.assertEqual(fleet['swarm_destruction_bonus'], 3)
        self.assertEqual(self.battle_report()['battle_replay']['rounds'], [])

    def test_outpost_bonus_is_limited_by_capacity_left_after_normal_loot(self):
        for capacity, ordinary, bonus in ((0, 0, 0), (2, 2, 0), (5, 3, 2), (6, 3, 3)):
            with self.subTest(capacity=capacity):
                target = self.nest()
                fleet = self.launch(target)
                # Exercise hold boundaries independently of combat survivorship.
                with patch('server.main.fleet_capacity', return_value=capacity):
                    self.world._complete_fleet(fleet)
                self.assert_empty(target)
                self.assertEqual(fleet['swarm_destruction_bonus'], bonus)
                self.assertEqual(fleet['swarm_crystals'], ordinary + bonus)
                self.assertLessEqual(sum(fleet['cargo'].values()) + fleet['swarm_crystals'], capacity)
                self.world._complete_fleet(fleet)

    def test_zero_stock_bonus_survives_reload_and_is_credited_only_once_on_return(self):
        target = self.nest()
        target['swarm_crystals'] = 0
        fleet = self.launch(target)
        self.world._complete_fleet(fleet)
        self.assertEqual(fleet['swarm_crystals'], 3)
        self.assertEqual(fleet['swarm_destruction_bonus'], 3)
        self.assertEqual(self.world._player(self.player)['swarm_crystals'], 0)
        fleet_id, target_id = fleet['id'], target['id']
        self.world.close()
        self.world = World(self.path, now=START)
        fleet = self.world.data['fleets'][fleet_id]
        self.assert_empty(self.world.data['planets'][target_id])
        self.assertEqual(fleet['swarm_destruction_bonus'], 3)
        self.assertEqual(self.world._player(self.player)['swarm_crystals'], 0)
        self.world._complete_fleet(fleet)
        self.world._complete_fleet(fleet)
        self.assertEqual(self.world._player(self.player)['swarm_crystals'], 3)

    def test_loot_skill_increases_stock_loot_without_multiplying_destruction_bonus(self):
        target = self.nest()
        target['swarm_crystals'] = 6
        fleet = self.launch(target)
        original_bonuses = self.world._bonuses
        def upgraded(owner):
            result = dict(original_bonuses(owner))
            if owner == self.player:
                result['swarm_loot'] = 1.0
            return result
        with patch.object(self.world, '_bonuses', side_effect=upgraded):
            self.world._complete_fleet(fleet)
        self.assert_empty(target)
        self.assertEqual(fleet['swarm_crystals'], 9)
        self.assertEqual(fleet['swarm_destruction_bonus'], 3)

    def test_failed_attack_retreat_and_mutual_destruction_do_not_liberate(self):
        for outcome in ('defeat', 'retreat', 'mutual'):
            with self.subTest(outcome=outcome):
                target = self.nest()
                target['ships']['cruiser'] = 500 if outcome == 'defeat' else 0
                buildings = dict(target['buildings'])
                fleet = self.launch(target, ships={'frigate': 1})
                if outcome == 'defeat':
                    self.world._complete_fleet(fleet)
                else:
                    with patch.object(self.world, '_power', return_value=0 if outcome == 'retreat' else 10**12):
                        self.world._complete_fleet(fleet)
                self.assertEqual((target['owner_type'], target['owner_id']), ('alien', 'khar'))
                self.assertEqual(target['buildings'], buildings)
                self.assertEqual(target['swarm_crystals'], 3.9)
                self.assertEqual(fleet['swarm_crystals'], 0)
                self.assertEqual(fleet.get('swarm_destruction_bonus', 0), 0)
                if outcome == 'mutual':
                    self.assertEqual(sum(target['ships'].values()) + sum(target['defenses'].values()), 0)
                    self.assertEqual(sum(fleet['ships'].values()), 0)
                if outcome == 'retreat':
                    self.assertEqual(self.battle_report()['battle_replay']['outcome'], 'retreat')
                    self.assertEqual(len(self.battle_report()['battle_replay']['rounds']), 6)

    def test_player_victory_does_not_destroy_another_players_colony(self):
        other = self.world.register('Other Empire', 'fixture-password-123')['state']['player']['id']
        self.world._player(other)['protected_until'] = 0
        target = self.world._owned(other)
        target['ships'] = blank_ships()
        self.world._capture_planetary_intel(self.player, target)
        buildings = dict(target['buildings'])
        fleet = self.launch(target)
        self.world._complete_fleet(fleet)
        self.assertEqual(target['owner_id'], other)
        self.assertEqual(target['owner_type'], 'player')
        self.assertEqual(target['buildings'], buildings)
        self.assertEqual(fleet.get('swarm_destruction_bonus', 0), 0)

    def test_only_attackers_target_intel_changes_without_revealing_neighbors(self):
        target = self.nest()
        spectator = self.world.register('Observer', 'fixture-password-123')['state']['player']['id']
        self.world._capture_planetary_intel(spectator, target)
        self.world._capture_swarm_intel(spectator, target)
        spectator_intel = {key: copy.deepcopy(self.world._player(spectator).get(key, {}))
                           for key in ('system_intel', 'planet_intel', 'scout_intel', 'trait_intel')}
        player = self.world._player(self.player)
        system_record = player['system_intel'][target['system_id']]
        neighbor = next(p for p in system_record['planets'] if p['id'] != target['id'])
        system_record['planets'] = [p for p in system_record['planets'] if p['id'] in (target['id'], neighbor['id'])]
        neighbor_before = copy.deepcopy(neighbor)
        self.world.data['planets'][neighbor['id']]['name'] = 'Unobserved change'
        fleet = self.launch(target)
        known_before = {p['id'] for s in self.world.state(self.player)['galaxy'] for p in s['planets']}
        self.world._complete_fleet(fleet)
        state = self.world.state(self.player)
        known_after = {p['id']: p for s in state['galaxy'] for p in s['planets']}
        self.assertEqual(set(known_after), known_before)
        self.assertEqual(known_after[target['id']]['owner_type'], 'empty')
        self.assertEqual(known_after[target['id']]['planet_scout']['owner_type'], 'empty')
        self.assertNotIn(target['id'], player['scout_intel'])
        self.assertEqual(next(p for p in system_record['planets'] if p['id'] == neighbor['id']), neighbor_before)
        for key, previous in spectator_intel.items():
            self.assertEqual(self.world._player(spectator).get(key, {}), previous)
        self.world.preview(self.player, {'mission': 'colonize', 'target_id': target['id'], 'ships': {'colonizer': 1}})

    def returning_swarm_fleet(self, origin):
        fleet = {'id': 'old-swarm-return', 'owner_id': 'khar', 'origin_id': origin['id'],
                 'target_id': self.home['id'], 'mission': 'scout', 'status': 'returning',
                 'ships': {**dict.fromkeys(swarm.SHIPS, 0), 'frigate': 2},
                 'cargo': dict.fromkeys(RESOURCES, 17), 'swarm_crystals': 0,
                 'seconds': 60, 'started_at': self.world.now, 'arrives_at': self.world.now + 60}
        self.world.data['fleets'][fleet['id']] = fleet
        return fleet

    def test_returning_swarm_fleet_cannot_donate_to_recolonized_planet(self):
        target = self.nest()
        returning = self.returning_swarm_fleet(target)
        self.world._complete_fleet(self.launch(target))
        self.world._complete_fleet(self.launch(target, mission='colonize', ships={'colonizer': 1}))
        colony = copy.deepcopy(target)
        self.world._complete_fleet(returning)
        self.assertEqual(target, colony)
        self.assertNotEqual(returning['origin_id'], target['id'])
        new_home = self.world.data['planets'][returning['origin_id']]
        self.assertEqual(new_home['owner_id'], 'khar')
        before = copy.deepcopy(new_home)
        self.world._complete_fleet(returning)
        self.assertEqual(new_home['ships']['frigate'], before['ships']['frigate'] + 2)
        self.assertNotIn(returning['id'], self.world.data['fleets'])

    def test_each_galaxy_retains_its_original_main_hive_after_attacks_and_reload(self):
        # Later galaxies now sleep until a real account settles there. Activate
        # all six explicitly so the original survival assertions still apply.
        for galaxy in GALAXIES_BY_ID:
            if galaxy == 'g1':
                continue
            result = self.world.register('HiveSettler' + galaxy, 'fixture-password-123')
            owner = result['state']['player']['id']
            colony = next(p for p in self.world.data['planets'].values()
                          if p['owner_type'] == 'empty' and p['galaxy_id'] == galaxy)
            colony.update(owner_type='player', owner_id=owner)
            self.world._ensure_swarm_activation()
        nests = [p for p in self.world.data['planets'].values() if p['owner_id'] == 'khar']
        original = {p['galaxy_id']: p['id'] for p in nests}
        self.assertEqual(len(nests), len(GALAXIES_BY_ID))
        self.assertEqual(set(original), set(GALAXIES_BY_ID))
        self.assertTrue(all(swarm.kind(p) == 'hive' for p in nests))
        for target in nests:
            buildings = dict(target['buildings'])
            self.world._capture_planetary_intel(self.player, target)
            fleet = self.launch(target, ships={'frigate': 1})
            self.world._complete_fleet(fleet)
            self.world._complete_fleet(fleet)
            self.assertEqual(target['owner_id'], 'khar')
            self.assertEqual(target['buildings'], buildings)
            self.assertEqual(fleet.get('swarm_destruction_bonus', 0), 0)
        marker = self.world.data['swarm_reset_at']
        self.world._alien_turn()
        self.world.close()
        self.world = World(self.path, now=START + 86400)
        self.world._alien_turn()
        remaining = [p for p in self.world.data['planets'].values() if p['owner_id'] == 'khar']
        self.assertEqual(len(remaining), len(original))
        self.assertEqual({p['galaxy_id']: p['id'] for p in remaining}, original)
        self.assertEqual(self.world.data['swarm_reset_at'], marker)

    def test_paid_colonizer_already_in_flight_can_found_a_new_nest(self):
        origin = self.nest()
        origin['ships'].update(colonizer=1, frigate=10)
        origin['swarm_next_colonization_at'] = 0
        origin['swarm_established_at'] = self.world.now - 7 * 86400
        self.world.data['alien']['swarm_next_colonization_by_galaxy']['g1'] = 0
        destination = next(p for p in self.world.data['planets'].values()
                           if p['owner_type'] == 'empty' and p['galaxy_id'] == 'g1')
        paid = self.world._swarm_launch(origin, destination, 'colonize', {'colonizer': 1, 'frigate': 2})
        self.assertIsNotNone(paid)
        self.world._complete_fleet(self.launch(origin))
        self.assert_empty(origin)
        self.world._complete_fleet(paid)
        self.assertEqual(destination['owner_id'], 'khar')
        self.assertEqual(destination['ships']['colonizer'], 0)
        self.assertEqual(destination['ships']['frigate'], 2)
        self.assertEqual(destination['swarm_crystals'], 0)
        self.assertNotIn(paid['id'], self.world.data['fleets'])
        before = copy.deepcopy(destination)
        self.world._complete_fleet(paid)
        self.assertEqual(destination, before)


if __name__ == '__main__':
    unittest.main()
