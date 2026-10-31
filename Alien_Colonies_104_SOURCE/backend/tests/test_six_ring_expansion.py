"""Release99: append outer systems to the live five-ring world without reset."""
import copy
import json
from collections import Counter
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World
from galaxy_topology import Navigation, RING_RADII, RING_SIZES, SCHEMA

NOW = 1_900_000_000.0


def five_ring_world(data):
    previous = copy.deepcopy(data)
    previous['systems'] = [system for system in previous['systems'] if system['ring_index'] < 5]
    keep = {pid for system in previous['systems'] for pid in system['planet_ids']}
    previous['planets'] = {pid: planet for pid, planet in previous['planets'].items() if pid in keep}
    for system in previous['systems']:
        system['ring_radius'] = (1.0, .67, .34, 4 / 3, .17)[system['ring_index']] / (4 / 3)
    previous['galaxy_schema_version'] = 3
    return previous


class SixRingExpansionTests(unittest.TestCase):
    def setUp(self):
        self.world = World(':memory:', now=NOW)

    def tearDown(self):
        self.world.close()

    def test_new_outer_ring_counts_identities_and_unsettled_galaxies(self):
        self.assertEqual(SCHEMA, 4)
        self.assertEqual(RING_SIZES, (30, 20, 10, 40, 5, 50))
        self.assertEqual(len(self.world.data['systems']), 930)
        for index in range(1, 7):
            local = [system for system in self.world.data['systems'] if system['galaxy_id'] == f'g{index}']
            self.assertEqual(Counter(s['ring_index'] for s in local), dict(enumerate(RING_SIZES)))
            self.assertEqual(len({system['name'] for system in local}), 155)
            self.assertTrue(all(0 < system['ring_radius'] <= 1 for system in local))
            outer = [system for system in local if system['ring_index'] == 5]
            self.assertTrue(all(system['ring_radius'] == 1 for system in outer))
            self.assertTrue(all(int(system['id'][1:]) > 630 for system in outer))
        self.assertGreater(RING_RADII[5], RING_RADII[3])
        self.assertEqual({p['galaxy_id'] for p in self.world.data['planets'].values() if p['owner_id'] == 'khar'}, {'g1'})

    def test_live_migration_keeps_every_old_record_and_is_idempotent(self):
        data = five_ring_world(self.world.data)
        data['players']['kept'] = {'id':'kept','research':{'propulsion':7},'reports':[{'id':'kept-report'}]}
        data['fleets']['kept'] = {'id':'kept','status':'outbound','arrives_at':NOW+900,'route':{'system_ids':['s1','s2']}}
        data['planets']['s1p1'].update(owner_type='player', owner_id='kept', queue=[{'kind':'build','ends_at':NOW+500}])
        before = copy.deepcopy(data)
        self.world._ensure_universe(data)
        for key in ('players','fleets','alien'):
            self.assertEqual(data[key], before[key])
        for pid, planet in before['planets'].items():
            self.assertEqual(data['planets'][pid], planet)
        systems = {system['id']:system for system in data['systems']}
        for system in before['systems']:
            self.assertEqual({k:v for k,v in systems[system['id']].items() if k != 'ring_radius'},
                             {k:v for k,v in system.items() if k != 'ring_radius'})
        self.assertEqual(len(data['systems']) - len(before['systems']), 300)
        migrated = copy.deepcopy(data)
        self.world._ensure_universe(data)
        self.assertEqual(data, migrated)
        self.assertEqual(data['systems'], self.world.data['systems'])

    def test_all_existing_routes_and_distances_stay_identical(self):
        old = five_ring_world(self.world.data)
        before, after = Navigation(old['systems']), self.world._galaxy_navigation()
        for first in old['systems']:
            for second in old['systems']:
                if first['galaxy_id'] == second['galaxy_id']:
                    self.assertEqual(before.route(first['id'], second['id']), after.route(first['id'], second['id']))

    def test_new_ring_is_reachable_with_five_bridges_and_no_cross_galaxy_edges(self):
        navigation = self.world._galaxy_navigation()
        for index in range(1, 7):
            local = [system for system in self.world.data['systems'] if system['galaxy_id'] == f'g{index}']
            outer = [system for system in local if system['ring_index'] == 5]
            self.assertEqual(len(navigation.hop_distances(local[0]['id'])), 155)
            bridges = []
            for system in outer:
                for target, (distance, kind) in navigation.edges[system['id']].items():
                    peer = navigation.systems[target]
                    self.assertEqual(peer['galaxy_id'], system['galaxy_id'])
                    self.assertEqual(navigation.edges[target][system['id']], (distance, kind))
                    if kind == 'bridge':
                        bridges.append((system['id'], target))
                        self.assertEqual(peer['ring_index'], 3)
            self.assertEqual(len(bridges), 5)

    def test_actual_preview_and_dispatch_to_new_ring(self):
        state = self.world.register('Outer99', 'fixture-password-123', _google_verified=True)['state']
        player_id = state['player']['id']
        self.world.action(player_id, {'type':'choose_race','race_id':'zetans'})
        home = self.world._owned(player_id)
        home['ships']['scout'] = 1
        home['resources'] = dict.fromkeys(('metal','crystal','fuel'),1_000_000.)
        target = next(system for system in self.world.data['systems'] if system['galaxy_id'] == home['galaxy_id'] and system['ring_index'] == 5)
        payload = {'type':'fleet','mission':'scout','planet_id':home['id'],'target_id':target['planet_ids'][0],'ships':{'scout':1}}
        quote = self.world.preview(player_id, payload)
        self.assertEqual(quote['route']['system_ids'][-1], target['id'])
        fuel = home['resources']['fuel']
        self.world.action(player_id, payload)
        fleet = next(f for f in self.world.data['fleets'].values() if f['owner_id'] == player_id)
        self.assertEqual(fleet['seconds'], quote['seconds'])
        self.assertEqual(home['resources']['fuel'], fuel - quote['fuel_cost'])

    def test_sqlite_migrates_once_with_verified_permanent_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory)/'world.sqlite3')
            old = World(database, now=NOW)
            old.data = five_ring_world(old.data)
            original = copy.deepcopy(old.data)
            old._save();old.close()
            for _ in range(2):
                restored = World(database, now=NOW)
                try:
                    self.assertEqual(len(restored.data['systems']),930)
                    self.assertEqual(restored.data['galaxy_schema_version'],4)
                    for pid, planet in original['planets'].items():
                        self.assertEqual(restored.data['planets'][pid],planet)
                finally:
                    restored.close()
            copies = list((Path(directory)/'reset-backups').glob('before-galaxy-rings-01232-*.sqlite3'))
            self.assertEqual(len(copies),1)
            with sqlite3.connect(f'file:{copies[0]}?mode=ro',uri=True) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                snapshot = json.loads(db.execute('SELECT body FROM snapshot WHERE id=1').fetchone()[0])
                self.assertEqual(snapshot, original)

    def test_failed_permanent_backup_leaves_committed_world_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory)/'world.sqlite3')
            old = World(database,now=NOW)
            old.data = five_ring_world(old.data);old._save();old.close()
            with sqlite3.connect(database) as db:
                before = db.execute('SELECT body FROM snapshot WHERE id=1').fetchone()[0]
            with patch('app.verified_reset_backup',side_effect=OSError('fixture disk failure')):
                with self.assertRaises(OSError):World(database,now=NOW)
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute('SELECT body FROM snapshot WHERE id=1').fetchone()[0],before)


if __name__ == '__main__':
    unittest.main()
