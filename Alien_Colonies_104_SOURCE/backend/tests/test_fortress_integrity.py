"""Persistent scarcity and safe migration across the actual World event loop."""
import copy
from pathlib import Path
import tempfile
import unittest

from server.main import blank_ships, RESOURCES
from tests.world_fixture import LocalTestWorld as World
from server import swarm

START = 1_900_000_000


class FortressIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.world = World(':memory:', now=START)
        self.player = self.world.register('Integrity Pilot', 'testing-password')['state']['player']['id']
        self.home = self.world._owned(self.player)
        self.hive = next(p for p in self.world.data['planets'].values() if p['owner_id'] == 'khar')

    def tearDown(self):
        self.world.close()

    def raid(self, fid, ships=3000):
        fleet = {'id': fid, 'owner_id': self.player, 'origin_id': self.home['id'],
                 'target_id': self.hive['id'], 'mission': 'attack', 'status': 'outbound',
                 'ships': {**blank_ships(), 'cruiser': ships},
                 'cargo': dict.fromkeys(RESOURCES, 0), 'swarm_crystals': 0,
                 'started_at': self.world.now, 'seconds': 60, 'arrives_at': self.world.now}
        self.world.data['fleets'][fid] = fleet
        self.world._complete_fleet(fleet)
        return fleet

    def test_repeated_empty_raids_never_stop_paid_rebuild_or_mint_crystals(self):
        self.assertTrue(self.world._swarm_queue(self.hive, 'ship', 'frigate', 24))
        queue = copy.deepcopy(self.hive['queue'])
        first = self.raid('first')
        self.assertEqual(first['swarm_crystals'], 3)
        self.assertEqual(sum(self.hive['ships'].values()), 0)
        self.assertEqual(self.hive['queue'], queue)
        self.assertEqual(self.hive['buildings']['shipyard'], 8)
        for i in range(20):
            self.world._produce(swarm.CRYSTAL_REGEN_SECONDS)
            repeat = self.raid('repeat-' + str(i))
            self.assertEqual(repeat['swarm_crystals'], 0)
            self.assertEqual(self.hive['queue'], queue)
            self.assertEqual(self.hive.get('swarm_suppressed_until', 0), 0)
        self.world._complete_fleet(first)
        self.world._complete_fleet(first)
        self.assertEqual(self.world.data['players'][self.player]['swarm_crystals'], 3)

    def test_generation_is_one_per_18_real_hours_at_every_test_speed(self):
        for speed in (1, 10, 1000):
            self.world.speed = speed
            self.hive['swarm_crystals'] = 0
            self.world._produce(swarm.CRYSTAL_REGEN_SECONDS - 1)
            self.assertEqual(int(self.hive['swarm_crystals']), 0)
            self.world._produce(1)
            self.assertEqual(self.hive['swarm_crystals'], 1)

    def test_remaining_stock_is_sealed_until_full_defense_is_rebuilt(self):
        self.hive['swarm_crystals'] = 6
        first = self.raid('sealed-first')
        self.assertEqual(first['swarm_crystals'], 3)
        self.assertEqual(self.hive['swarm_crystals'], 3)
        self.assertFalse(swarm.public_planet(self.hive, self.world.now)['swarm_crystals_loot_available'])
        second = self.raid('sealed-empty')
        self.assertEqual(second['swarm_crystals'], 0)
        self.hive['ships']['frigate'] = 1
        third = self.raid('sealed-one-defender')
        self.assertEqual(third['swarm_crystals'], 0)
        self.hive['ships'].update(swarm.defense_minimum(self.hive))
        # Rebuilt at the same instant: no extra production tick is needed.
        self.assertTrue(swarm.public_planet(self.hive, self.world.now)['swarm_crystals_loot_available'])
        fourth = self.raid('rebuilt-defenders')
        self.assertEqual(fourth['swarm_crystals'], 3)

    def test_generation_pauses_for_defense_and_resumes_existing_fraction(self):
        self.hive['swarm_crystals'] = .5
        ships = dict(self.hive['ships'])
        self.hive['ships'] = dict.fromkeys(swarm.SHIPS, 0)
        self.world._produce(7 * 86400)
        self.assertEqual(self.hive['swarm_crystals'], .5)
        self.hive['ships'] = ships
        self.world._produce(swarm.CRYSTAL_REGEN_SECONDS / 2)
        self.assertEqual(self.hive['swarm_crystals'], 1)

    def test_single_offline_interval_matches_many_live_intervals(self):
        other = World(':memory:', now=START)
        try:
            self.hive['swarm_crystals'] = 0
            reference = other.data['planets'][self.hive['id']]
            reference['swarm_crystals'] = 0
            # Stop decisions only: production and event persistence remain real.
            self.world.data['alien']['next_expansion_at'] = START + 30 * 86400
            other.data['alien']['next_expansion_at'] = START + 30 * 86400
            self.world.advance(START + swarm.CRYSTAL_REGEN_SECONDS)
            for elapsed in range(120, swarm.CRYSTAL_REGEN_SECONDS + 1, 120):
                other.advance(START + elapsed)
            self.assertEqual(self.hive['swarm_crystals'], 1)
            self.assertEqual(reference['swarm_crystals'], 1)
            other.advance(other.now)
            self.assertEqual(reference['swarm_crystals'], 1)
        finally:
            other.close()

    def test_old_frontier_migrates_once_without_touching_players_or_old_raid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'world.sqlite3'
            old = World(path, now=START)
            pid = old.register('Saved Pilot', 'testing-password')['state']['player']['id']
            old.action(pid, {'type': 'choose_race', 'race_id': 'zetans'})
            player = old.data['players'][pid]
            player['swarm_crystals'] = 17
            old.action(pid, {'type': 'unlock_skill', 'node_id': 'zetans_0_0'})
            player_before = copy.deepcopy(player)
            home_id = player['home_id']
            for p in list(old.data['planets'].values())[:40]:
                if p['owner_type'] == 'empty':
                    swarm.seed(p, START, hive=False)
            target = next(p for p in old.data['planets'].values() if p['owner_id'] == 'khar')
            old.data['fleets']['old-raid'] = {
                'id': 'old-raid', 'owner_id': pid, 'origin_id': home_id, 'target_id': target['id'],
                'mission': 'attack', 'status': 'outbound', 'ships': {**blank_ships(), 'frigate': 3},
                'cargo': dict.fromkeys(RESOURCES, 0), 'swarm_crystals': 0,
                'seconds': 60, 'started_at': START, 'arrives_at': START + 60}
            old.data['progression_version'] = 1
            old.close()
            migrated = World(path, now=START + 7 * 86400)
            try:
                hives = [p for p in migrated.data['planets'].values() if p['owner_id'] == 'khar']
                self.assertEqual(len(hives), swarm.INITIAL_HIVES)
                self.assertEqual(sum(p['swarm_crystals'] for p in hives), 3 * swarm.INITIAL_HIVES)
                self.assertTrue(all(p['resources']['metal'] == 18000 for p in hives))
                self.assertEqual(migrated.data['planets'][home_id]['owner_id'], pid)
                for key in ('race_id', 'swarm_crystals', 'skill_nodes'):
                    self.assertEqual(migrated.data['players'][pid][key], player_before[key])
                self.assertEqual(migrated.data['fleets']['old-raid']['status'], 'returning')
                self.assertEqual(migrated.data['fleets']['old-raid']['ships']['frigate'], 3)
                self.assertEqual(migrated.data['alien']['swarm_next_colonization_at'], START + 14 * 86400)
                hives[0]['swarm_crystals'] = 0
                hives[0]['ships'] = dict.fromkeys(swarm.SHIPS, 0)
                marked_id = hives[0]['id']
            finally:
                migrated.close()
            reopened = World(path, now=START + 7 * 86400)
            try:
                self.assertEqual(reopened.data['planets'][marked_id]['swarm_crystals'], 0)
                self.assertEqual(sum(reopened.data['planets'][marked_id]['ships'].values()), 0)
                self.assertEqual(reopened.data['progression_version'], 2)
            finally:
                reopened.close()

    def test_incoming_swarm_attack_returns_when_empty_planet_becomes_available(self):
        self.world.data['players'][self.player]['protected_until'] = 0
        # Existing mission from a previously full galaxy; current world has space.
        f = {'id': 'npc-attack', 'owner_id': 'khar', 'origin_id': self.hive['id'],
             'target_id': self.home['id'], 'mission': 'attack', 'status': 'outbound',
             'ships': {**dict.fromkeys(swarm.SHIPS, 0), 'frigate': 180, 'cruiser': 30},
             'cargo': dict.fromkeys(RESOURCES, 0), 'swarm_crystals': 0,
             'seconds': 60, 'started_at': START, 'arrives_at': START}
        self.world.data['fleets'][f['id']] = f
        before = copy.deepcopy(self.home)
        self.world._complete_fleet(f)
        self.assertEqual(f['status'], 'returning')
        self.assertEqual(self.home, before)


if __name__ == '__main__':
    unittest.main()
