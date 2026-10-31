"""Migration from the live three-ring world, including persistence and routes."""
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World
from galaxy_topology import Navigation, RING_RADII

NOW = 1_900_000_000.0


def previous_world(data):
    result = copy.deepcopy(data)
    result['systems'] = [s for s in result['systems'] if s['ring_index'] < 3]
    keep = {pid for s in result['systems'] for pid in s['planet_ids']}
    result['planets'] = {pid: p for pid, p in result['planets'].items() if pid in keep}
    for system in result['systems']:
        system['ring_radius'] = (1.0, .67, .34)[system['ring_index']]
    result['galaxy_schema_version'] = 2
    return result


class FiveRingExpansionTests(unittest.TestCase):
    def setUp(self):
        self.world = World(':memory:', now=NOW)

    def tearDown(self):
        self.world.close()

    def test_live_migration_preserves_all_physical_records_and_is_idempotent(self):
        snapshot = previous_world(self.world.data)
        snapshot['players']['retained'] = {'id': 'retained', 'research': {'propulsion': 7},
                                          'reports': [{'id': 'old-report', 'at': NOW - 100}]}
        snapshot['fleets']['retained'] = {'id': 'retained', 'status': 'outbound',
                                         'arrives_at': NOW + 600, 'route': {'system_ids': ['s1', 's2']}}
        snapshot['planets']['s1p1'].update(owner_type='player', owner_id='retained',
                                         queue=[{'kind': 'build', 'ends_at': NOW + 500}])
        before = copy.deepcopy(snapshot)
        self.world._ensure_universe(snapshot)
        self.assertEqual(snapshot['players'], before['players'])
        self.assertEqual(snapshot['fleets'], before['fleets'])
        self.assertEqual(snapshot['alien'], before['alien'])
        for pid, planet in before['planets'].items():
            self.assertEqual(snapshot['planets'][pid], planet)
        by_id = {s['id']: s for s in snapshot['systems']}
        for system in before['systems']:
            self.assertEqual({k: v for k, v in by_id[system['id']].items() if k != 'ring_radius'},
                             {k: v for k, v in system.items() if k != 'ring_radius'})
        self.assertEqual(len(snapshot['systems']), 930)
        self.assertEqual(snapshot['galaxy_schema_version'], 4)
        migrated = copy.deepcopy(snapshot)
        self.world._ensure_universe(snapshot)
        self.assertEqual(snapshot, migrated)

    def test_all_old_routes_and_cost_distances_are_identical(self):
        old = previous_world(self.world.data)
        before, after = Navigation(old['systems']), self.world._galaxy_navigation()
        for first in old['systems']:
            for second in old['systems']:
                if first['galaxy_id'] == second['galaxy_id']:
                    self.assertEqual(before.route(first['id'], second['id']),
                                     after.route(first['id'], second['id']))

    def test_existing_inner_ids_and_normalized_android_protocol_are_preserved(self):
        systems = self.world.data['systems']
        self.assertEqual(next(s['id'] for s in systems if
                             (s['galaxy_id'], s['ring_index'], s['ring_order']) == ('g2', 1, 0)), 's211')
        self.assertEqual(next(s['id'] for s in systems if
                             (s['galaxy_id'], s['ring_index'], s['ring_order']) == ('g6', 2, 9)), 's360')
        self.assertEqual(len({s['id'] for s in systems}), 930)
        for galaxy in ('g1', 'g2', 'g3', 'g4', 'g5', 'g6'):
            local = [s for s in systems if s['galaxy_id'] == galaxy]
            self.assertEqual(Counter(s['ring_index'] for s in local), {0: 30, 1: 20, 2: 10, 3: 40, 4: 5, 5: 50})
            self.assertEqual(len({s['name'] for s in local}), 155)
            self.assertTrue(all(0 < s['ring_radius'] <= 1 for s in local))
            self.assertTrue(all(s['ring_radius'] == RING_RADII[s['ring_index']] for s in local))
        self.assertGreater(RING_RADII[3], RING_RADII[0])
        self.assertLess(RING_RADII[4], RING_RADII[2])

    def test_schema_two_sqlite_world_expands_once_and_keeps_active_flight(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / 'world.sqlite3')
            old = World(database, now=NOW)
            old.data = previous_world(old.data)
            old._navigation_cache = None
            state = old.register('Five ring migration', 'fixture-password-123', _google_verified=True)['state']
            player_id = state['player']['id']
            old.action(player_id, {'type': 'choose_race', 'race_id': 'zetans'})
            home = old._owned(player_id)
            home['ships']['scout'] = 1
            home['resources'] = dict.fromkeys(('metal', 'crystal', 'fuel'), 1_000_000.)
            target = next(p for p in old.data['planets'].values()
                          if p['galaxy_id'] == home['galaxy_id'] and p['system_id'] != home['system_id'])
            old.action(player_id, {'type': 'fleet', 'mission': 'scout',
                                  'target_id': target['id'], 'ships': {'scout': 1}})
            flights = copy.deepcopy(old.data['fleets'])
            colony = copy.deepcopy(home)
            old._save()
            old.close()
            for _ in range(2):
                restored = World(database, now=NOW)
                try:
                    self.assertEqual(len(restored.data['systems']), 930)
                    self.assertEqual(restored.data['fleets'], flights)
                    self.assertEqual(restored.data['planets'][colony['id']], colony)
                    self.assertEqual(restored.data['galaxy_schema_version'], 4)
                finally:
                    restored.close()

            backups = list((Path(directory) / 'reset-backups').glob('before-galaxy-rings-01232-*.sqlite3'))
            self.assertEqual(len(backups), 1)
            with sqlite3.connect(f'file:{backups[0]}?mode=ro', uri=True) as backup:
                preserved = json.loads(backup.execute('SELECT body FROM snapshot WHERE id=1').fetchone()[0])
                self.assertEqual(len(preserved['systems']), 360)
                self.assertEqual(preserved['fleets'], flights)
                self.assertEqual(backup.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_failed_permanent_backup_keeps_the_live_schema_two_database_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / 'world.sqlite3')
            old = World(database, now=NOW)
            old.data = previous_world(old.data)
            old._save()
            old.close()
            with sqlite3.connect(database) as connection:
                before = connection.execute('SELECT body FROM snapshot WHERE id=1').fetchone()[0]
            with patch('app.verified_reset_backup', side_effect=OSError('fixture disk unavailable')):
                with self.assertRaises(OSError):
                    World(database, now=NOW)
            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute('SELECT body FROM snapshot WHERE id=1').fetchone()[0], before)


if __name__ == '__main__':
    unittest.main()
