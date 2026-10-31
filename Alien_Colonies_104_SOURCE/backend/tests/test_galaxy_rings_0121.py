"""Actual flat Railway backend: additive world migration and real lane travel."""
import copy
import json
import math
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

# The repository also retains an older server/ source snapshot. Exercise the
# runtime app copied by the root Dockerfile, never that historical snapshot.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World
from galaxies import SYSTEMS_PER_GALAXY, inferred_id
from galaxy_topology import Navigation, system_key

NOW = 1_900_000_000.0


class GalaxyRingsTests(unittest.TestCase):
    def setUp(self):
        self.world = World(':memory:', now=NOW)

    def tearDown(self):
        self.world.close()

    def register(self):
        state = self.world.register('Rings0121', 'fixture-password-123', _google_verified=True)['state']
        player_id = state['player']['id']
        self.world.action(player_id, {'type': 'choose_race', 'race_id': 'zetans'})
        return player_id, self.world._owned(player_id)

    def system(self, galaxy='g1', ring=0, order=0):
        return next(s for s in self.world.data['systems']
                    if (s['galaxy_id'], s['ring_index'], s['ring_order']) == (galaxy, ring, order))

    def planet(self, system):
        return self.world.data['planets'][system['planet_ids'][0]]

    def legacy_snapshot(self):
        snapshot = copy.deepcopy(self.world.data)
        snapshot['systems'] = [s for s in snapshot['systems'] if s['ring_index'] == 0]
        remaining = {pid for system in snapshot['systems'] for pid in system['planet_ids']}
        snapshot['planets'] = {pid: p for pid, p in snapshot['planets'].items() if pid in remaining}
        for system in snapshot['systems']:
            for field in ('ring_index', 'ring_order', 'ring_size', 'ring_radius'):
                system.pop(field)
        snapshot['galaxy_schema_version'] = 1
        return snapshot

    def test_new_world_has_six_rings_without_activating_unsettled_galaxies(self):
        self.assertEqual(len(self.world.data['systems']), 930)
        self.assertEqual(SYSTEMS_PER_GALAXY, 30)
        self.assertEqual(inferred_id('s31'), 'g2')
        for index in range(1, 7):
            local = [s for s in self.world.data['systems'] if s['galaxy_id'] == f'g{index}']
            self.assertEqual(Counter(s['ring_index'] for s in local), {0: 30, 1: 20, 2: 10, 3: 40, 4: 5, 5: 50})
            for system in local:
                self.assertTrue(1 <= len(system['planet_ids']) <= 5)
                for pid in system['planet_ids']:
                    self.assertEqual(self.world.data['planets'][pid]['galaxy_id'], f'g{index}')
        self.assertEqual({p['galaxy_id'] for p in self.world.data['planets'].values()
                          if p['owner_id'] == 'khar'}, {'g1'})

    def test_additive_migration_preserves_every_existing_record_and_is_idempotent(self):
        snapshot = self.legacy_snapshot()
        snapshot['players']['fixture'] = {'id': 'fixture', 'reports': [{'id': 'kept'}], 'research': {'propulsion': 7}}
        snapshot['fleets']['f1'] = {'id': 'f1', 'origin_id': 's1p1', 'target_id': 's30p1',
                                   'started_at': NOW - 5, 'arrives_at': NOW + 800, 'seconds': 805,
                                   'status': 'outbound', 'owner_id': 'fixture', 'mission': 'scout'}
        snapshot['planets']['s1p1'].update(owner_type='player', owner_id='fixture',
                                         queue=[{'ends_at': NOW + 700, 'kind': 'build', 'key': 'metal_mine'}])
        original = copy.deepcopy(snapshot)
        self.world._ensure_universe(snapshot)
        self.assertEqual(snapshot['players'], original['players'])
        self.assertEqual(snapshot['fleets'], original['fleets'])
        self.assertEqual(snapshot['alien'], original['alien'])
        for pid, planet in original['planets'].items():
            self.assertEqual(snapshot['planets'][pid], planet)
        for old in original['systems']:
            updated = next(s for s in snapshot['systems'] if s['id'] == old['id'])
            self.assertEqual({key: updated[key] for key in old}, old)
        migrated = copy.deepcopy(snapshot)
        self.world._ensure_universe(snapshot)
        self.assertEqual(snapshot, migrated)

    def test_allocator_starts_after_actual_ids_and_does_not_reassign_legacy_galaxies(self):
        snapshot = self.legacy_snapshot()
        old = snapshot['systems'][-1]
        previous_id = old['id']
        old['id'] = 's901'
        for pid in old['planet_ids']:
            snapshot['planets'][pid]['system_id'] = old['id']
        self.world._ensure_universe(snapshot)
        new = [s for s in snapshot['systems'] if s['ring_index'] != 0]
        self.assertGreaterEqual(min(int(s['id'][1:]) for s in new), 902)
        self.assertEqual(old['galaxy_id'], 'g6')
        self.assertNotIn(previous_id, {s['id'] for s in snapshot['systems']})

    def test_legacy_missing_galaxy_fields_use_the_original_thirty_system_blocks(self):
        snapshot = self.legacy_snapshot()
        for system in snapshot['systems']:
            system.pop('galaxy_id')
            for pid in system['planet_ids']:
                snapshot['planets'][pid].pop('galaxy_id')
        self.world._ensure_universe(snapshot)
        self.assertEqual(len(snapshot['systems']), 930)
        self.assertEqual(next(s['galaxy_id'] for s in snapshot['systems'] if s['id'] == 's31'), 'g2')

    def test_lanes_are_symmetric_connected_and_have_five_bridges_per_ring_pair(self):
        navigation = self.world._galaxy_navigation()
        for galaxy in ('g1', 'g2', 'g3', 'g4', 'g5', 'g6'):
            local = [s for s in self.world.data['systems'] if s['galaxy_id'] == galaxy]
            edges = set()
            bridges = Counter()
            for system in local:
                for target, (distance, kind) in navigation.edges[system['id']].items():
                    self.assertEqual(navigation.systems[target]['galaxy_id'], galaxy)
                    self.assertEqual(navigation.edges[target][system['id']], (distance, kind))
                    edge = tuple(sorted((system['id'], target), key=system_key))
                    if edge not in edges and kind == 'bridge':
                        bridges[tuple(sorted((system['ring_index'], navigation.systems[target]['ring_index'])))] += 1
                    edges.add(edge)
            self.assertEqual(len(edges), 180)
            self.assertEqual(bridges, {(0, 1): 5, (1, 2): 5, (0, 3): 5, (2, 4): 5, (3, 5): 5})
            self.assertEqual(len(navigation.hop_distances(local[0]['id'])), 155)
        self.assertEqual(navigation.edges['s1']['s30'], (.6, 'orbit'))

    def test_weighted_paths_match_spokes_and_stay_bounded_after_reordered_state(self):
        navigation = self.world._galaxy_navigation()
        a, b, c = (self.system(ring=ring) for ring in range(3))
        route = navigation.route(a['id'], c['id'])
        self.assertEqual(route['system_ids'], [a['id'], b['id'], c['id']])
        self.assertEqual(route['distance'], 2.0)
        self.assertEqual(navigation.route('s1', 's2')['distance'], .6)
        local = [s for s in self.world.data['systems'] if s['galaxy_id'] == 'g1']
        reversed_navigation = Navigation(list(reversed(self.world.data['systems'])))
        maximum = 0
        for first in local:
            for second in local:
                expected = navigation.route(first['id'], second['id'])
                self.assertEqual(expected, reversed_navigation.route(first['id'], second['id']))
                maximum = max(maximum, expected['distance'])
        self.assertEqual(maximum, 14.0)

    def test_preview_actual_dispatch_and_paid_return_use_the_same_authoritative_route(self):
        player_id, origin = self.register()
        target = self.planet(self.system(ring=2 if self.world._galaxy_navigation().systems[origin['system_id']]['ring_index'] != 2 else 0))
        origin['ships']['scout'] = 1
        origin['resources'] = dict.fromkeys(('metal', 'crystal', 'fuel'), 1_000_000.)
        payload = {'type': 'fleet', 'planet_id': origin['id'], 'target_id': target['id'],
                   'mission': 'scout', 'ships': {'scout': 1}}
        preview = self.world.preview(player_id, payload)
        route = self.world._galaxy_navigation().route(origin['system_id'], target['system_id'])
        self.assertEqual(preview['route']['system_ids'], route['system_ids'])
        distance = route['distance'] + abs(origin['slot'] - target['slot']) * .08 + .1
        self.assertAlmostEqual(self.world._local_distance(origin, target), distance)
        mass = self.world._specs(player_id, 'ships')['scout'][7]
        reduction = self.world._building_effects(origin).get('fleet_fuel_reduction', 0)
        self.assertEqual(preview['fuel_cost'], 1 + math.floor(mass * (2700 + 95 * route['distance']) / 35000 * 4 * (1 - reduction) + .5))
        before = origin['resources']['fuel']
        self.world.action(player_id, payload)
        fleet = next(f for f in self.world.data['fleets'].values() if f['owner_id'] == player_id)
        self.assertEqual(fleet['seconds'], preview['seconds'])
        self.assertEqual(fleet['arrives_at'], NOW + preview['seconds'])
        self.assertEqual(origin['resources']['fuel'], before - preview['fuel_cost'])
        self.world.advance(fleet['arrives_at'])
        self.assertEqual(fleet['status'], 'returning')
        self.assertEqual(fleet['arrives_at'], NOW + preview['seconds'] * 2)

    def test_observation_follows_real_connections_and_never_crosses_galaxies(self):
        player_id, home = self.register()
        home['buildings']['observatory'] = 1
        navigation = self.world._galaxy_navigation()
        coverage = self.world._observation_coverage(player_id)
        expected = {home['system_id'], *navigation.edges[home['system_id']]}
        self.assertEqual({sid for sid, tier in coverage.items() if tier}, expected)
        self.assertTrue(all(navigation.systems[sid]['galaxy_id'] == home['galaxy_id'] for sid in expected))
        # The original outer wrap is retained and the nearby middle bridge is
        # visible, but the second bridge beyond a level-one sensor is not.
        home['buildings']['observatory'] = 0
        out = self.planet(self.system(ring=0))
        out.update(owner_id=player_id, owner_type='player')
        out['buildings']['observatory'] = 1
        coverage = self.world._observation_coverage(player_id)
        self.assertEqual(coverage['s30'], 1)
        self.assertEqual(coverage[self.system(ring=1)['id']], 1)
        self.assertEqual(coverage[self.system(ring=2)['id']], 0)

    def test_public_structure_reveals_no_unknown_planets_and_jump_costs_are_unchanged(self):
        player_id, home = self.register()
        state = self.world.state(player_id)
        self.assertEqual(len(state['galaxy']), 930)
        self.assertEqual(sum(len(s['planets']) for s in state['galaxy']), 1)
        for system in state['galaxy']:
            self.assertIn('connections', system)
            self.assertIn('ring_index', system)
            if system['visibility'] == 'unknown':
                self.assertEqual(system['planets'], [])
                self.assertNotIn('planet_ids', system)
        target = self.planet(self.system(galaxy='g2'))
        route = self.world._route_details(home, target)
        self.assertTrue(route['intergalactic'])
        self.assertEqual(route['system_ids'], [])
        self.assertEqual(route['segments'], [])
        self.assertEqual(next(g['minimum_jump_fuel'] for g in state['galaxies'] if g['id'] == 'g2'), 0)

    def test_account_deletion_preserves_an_inner_planets_explicit_galaxy(self):
        player_id, _ = self.register()
        inner = self.planet(self.system(galaxy='g4', ring=2))
        inner.update(owner_id=player_id, owner_type='player')
        before = {key: copy.deepcopy(inner[key]) for key in ('id', 'system_id', 'galaxy_id', 'environment', 'rare_trait')}
        token = self.world.login('Rings0121', 'fixture-password-123')['token']
        self.world.account_delete(token, 'fixture-password-123', 'DELETE ACCOUNT')
        freed = self.world.data['planets'][inner['id']]
        self.assertEqual({key: freed[key] for key in before}, before)
        self.assertEqual(freed['owner_type'], 'empty')
        self.assertEqual(self.world._galaxy_id(freed), 'g4')

    def test_planetary_legacy_repair_keeps_new_numeric_ids_in_their_actual_galaxy(self):
        system = self.system(galaxy='g3', ring=1)
        pid = system['planet_ids'].pop()
        self.world.data['planets'].pop(pid)
        self.world.data['planetary_schema'] = 0
        self.world._ensure_planetary()
        self.assertEqual(self.world.data['planets'][pid]['galaxy_id'], 'g3')

    def test_persisted_migration_keeps_active_flight_accounts_and_world_on_second_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / 'world.sqlite3')
            original = World(database, now=NOW)
            # Recreate a genuine legacy topology before creating the account,
            # so a starter cannot be located in a not-yet-existing inner ring.
            original.data = self.legacy_snapshot()
            original._navigation_cache = None
            state = original.register('Persistent0121', 'fixture-password-123', _google_verified=True)['state']
            player_id = state['player']['id']
            original.action(player_id, {'type': 'choose_race', 'race_id': 'zetans'})
            home = original._owned(player_id)
            home['ships']['scout'] = 1
            home['resources'] = dict.fromkeys(('metal', 'crystal', 'fuel'), 1_000_000.)
            target = next(p for p in original.data['planets'].values()
                          if p['galaxy_id'] == home['galaxy_id'] and p['system_id'] != home['system_id'])
            original.action(player_id, {'type': 'fleet', 'mission': 'scout', 'target_id': target['id'], 'ships': {'scout': 1}})
            # A real pre-update flight carried galaxy metadata, not lane data.
            active = next(iter(original.data['fleets'].values()))
            for key in ('navigation_schema', 'system_ids', 'segments', 'local_distance'):
                active['route'].pop(key, None)
            fleets = copy.deepcopy(original.data['fleets'])
            colonies = {pid: copy.deepcopy(p) for pid, p in original.data['planets'].items() if p['owner_id'] == player_id}
            account = original.db.execute('SELECT id,name_key,password_hash,salt FROM accounts WHERE id=?', (player_id,)).fetchone()
            original._save()
            original.close()
            restored = World(database, now=NOW)
            try:
                self.assertEqual(len(restored.data['systems']), 930)
                self.assertEqual(restored.data['fleets'], fleets)
                public_fleet = next(f for f in restored.state(player_id)['fleets'] if f['id'] == active['id'])
                self.assertEqual(public_fleet['route'], active['route'])
                self.assertNotIn('system_ids', public_fleet['route'])
                self.assertEqual({pid: restored.data['planets'][pid] for pid in colonies}, colonies)
                self.assertEqual(restored.db.execute('SELECT id,name_key,password_hash,salt FROM accounts WHERE id=?', (player_id,)).fetchone(), account)
                expanded = copy.deepcopy(restored.data['systems'])
            finally:
                restored.close()
            again = World(database, now=NOW)
            try:
                self.assertEqual(again.data['systems'], expanded)
                self.assertEqual(again.data['fleets'], fleets)
            finally:
                again.close()


if __name__ == '__main__':
    unittest.main()
