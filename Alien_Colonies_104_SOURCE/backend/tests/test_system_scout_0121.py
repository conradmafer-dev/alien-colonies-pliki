"""Whole-system occupancy scans are one paid, arrival-time mission."""
import copy
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World, GameError

NOW = 1_900_000_000.


class SystemScoutTests(unittest.TestCase):
    def setUp(self):
        self.world = World(':memory:', now=NOW)
        self.player, self.home = self.register('Scanner0121')
        self.system = next(s for s in self.world.data['systems'] if s['galaxy_id'] == 'g1'
                           and len(s['planet_ids']) >= 3 and s['id'] != self.home['system_id']
                           and all(self.world.data['planets'][pid]['owner_type'] == 'empty' for pid in s['planet_ids']))
        self.target = self.world.data['planets'][self.system['planet_ids'][0]]

    def tearDown(self):
        self.world.close()

    def register(self, name):
        choose = self.world._choose_start_planet
        def outside_scan_system(available):
            return choose([planet for planet in available
                           if not hasattr(self, 'system') or planet['system_id'] != self.system['id']])
        with patch.object(self.world, '_choose_start_planet', side_effect=outside_scan_system):
            state = self.world.register(name, 'fixture-password-123', _google_verified=True)['state']
        player = state['player']['id']
        self.world.action(player, {'type': 'choose_race', 'race_id': 'zetans'})
        home = self.world._owned(player)
        home['resources'] = dict.fromkeys(('metal', 'crystal', 'fuel'), 1_000_000.)
        home['ships']['scout'] = 10
        home['ships']['colonizer'] = 1
        return player, home

    def payload(self, target=None, scope='system'):
        target = target or self.target
        result = {'type': 'fleet', 'mission': 'scout', 'planet_id': self.home['id'],
                  'target_id': target['id'], 'ships': {'scout': 1}, 'scout_scope': scope}
        if scope == 'system':
            result['target_system_id'] = target['system_id']
        return result

    def launch(self, payload=None, player=None):
        previous = set(self.world.data['fleets'])
        self.world.action(player or self.player, payload or self.payload())
        return self.world.data['fleets'][(set(self.world.data['fleets']) - previous).pop()]

    def scan(self, payload=None):
        fleet = self.launch(payload)
        self.world.advance(fleet['arrives_at'])
        report = next(r for r in self.world._player(self.player)['reports'] if 'system_snapshot' in r)
        return fleet, report

    def map_system(self):
        return next(s for s in self.world.state(self.player)['galaxy'] if s['id'] == self.system['id'])

    def test_preview_never_reveals_occupancy_and_dispatch_charges_one_real_flight(self):
        unknown = self.map_system()
        self.assertEqual(unknown['planets'], [])
        self.assertEqual(unknown['system_scout_target_id'], self.target['id'])
        before_intel = copy.deepcopy(self.world._player(self.player)['system_intel'])
        before = copy.deepcopy(self.home)
        preview = self.world.preview(self.player, self.payload())
        self.assertEqual(preview['scout_scope'], 'system')
        self.assertEqual(preview['target_system_id'], self.system['id'])
        self.assertNotIn('planets', preview)
        self.assertEqual(self.home, before)
        self.assertEqual(self.world._player(self.player)['system_intel'], before_intel)
        fleet = self.launch()
        self.assertEqual(fleet['scout_scope'], 'system')
        self.assertEqual(fleet['target_system_id'], self.system['id'])
        self.assertEqual(self.home['resources']['fuel'], before['resources']['fuel'] - preview['fuel_cost'])
        self.assertEqual(self.home['ships']['scout'], before['ships']['scout'] - 1)
        self.assertEqual(self.map_system()['planets'], [])
        self.world.advance(fleet['arrives_at'])
        self.assertEqual(len(self.map_system()['planets']), len(self.system['planet_ids']))
        self.assertEqual(fleet['status'], 'returning')

    def test_one_rescout_refreshes_every_owner_after_real_colonization_and_keeps_old_report(self):
        _, old_report = self.scan()
        frozen = copy.deepcopy(old_report)
        player_b, home_b = self.register('Colonist0121')
        target_b = self.world.data['planets'][self.system['planet_ids'][1]]
        scout_b = self.launch({'type': 'fleet', 'mission': 'scout', 'planet_id': home_b['id'],
                              'target_id': target_b['id'], 'ships': {'scout': 1}}, player_b)
        self.world.advance(scout_b['arrives_at'])
        colonizer = self.launch({'type': 'fleet', 'mission': 'colonize', 'planet_id': home_b['id'],
                                'target_id': target_b['id'], 'ships': {'colonizer': 1}}, player_b)
        self.world.advance(colonizer['arrives_at'])
        self.assertEqual(target_b['owner_id'], player_b)
        # No map refresh, preview or report read silently grants fresh intel.
        self.assertEqual(next(p for p in self.map_system()['planets'] if p['id'] == target_b['id'])['owner_type'], 'empty')
        self.world.preview(self.player, self.payload())
        self.assertEqual(old_report, frozen)
        _, latest = self.scan()
        current = self.map_system()
        owner = next(p for p in current['planets'] if p['id'] == target_b['id'])
        self.assertEqual(owner['owner_id'], player_b)
        self.assertEqual(owner['owner_name'], 'Colonist0121')
        self.assertGreater(latest['system_snapshot']['scouted_at'], frozen['system_snapshot']['scouted_at'])
        self.assertEqual(latest['system_snapshot']['counts']['player'], 1)
        self.assertEqual(latest['system_snapshot']['counts']['empty'], len(self.system['planet_ids']) - 1)
        self.assertEqual(old_report, frozen)
        self.assertNotIn('scout_target_id', current)
        self.assertEqual(current['system_scout_target_id'], self.target['id'])

    def test_system_scan_has_no_individual_resources_fleet_defense_or_building_details(self):
        self.target['resources']['metal'] = 123456
        self.target['ships']['frigate'] = 17
        self.target['buildings']['metal_mine'] = 9
        _, report = self.scan()
        public = self.world._public_intel_report(report)
        self.assertNotIn('planet_scout', public)
        self.assertNotIn('scout', public)
        scan = public['system_scout']
        self.assertEqual(scan['system_id'], self.system['id'])
        self.assertEqual(scan['planets_count'], len(self.system['planet_ids']))
        self.assertEqual(sum(scan['counts'].values()), scan['planets_count'])
        for planet in scan['planets']:
            self.assertEqual(planet['scouted_at'], scan['scouted_at'])
            for private in ('resources', 'ships', 'defenses', 'buildings', 'observed_buildings', 'planet_scout'):
                self.assertNotIn(private, planet)
        self.assertNotIn(self.target['id'], self.world._player(self.player)['planet_intel'])

    def test_individual_scout_details_stay_dated_when_later_system_scan_updates_occupancy(self):
        fleet = self.launch(self.payload(scope='planet'))
        self.world.advance(fleet['arrives_at'])
        old_details = copy.deepcopy(self.world._player(self.player)['planet_intel'][self.target['id']])
        individual = next(r for r in self.world._player(self.player)['reports'] if 'planet_snapshot' in r)
        self.assertIn('planet_scout', self.world._public_intel_report(individual))
        self.target['resources']['metal'] += 12345
        self.scan()
        self.assertEqual(self.world._player(self.player)['planet_intel'][self.target['id']], old_details)
        self.assertEqual(individual['planet_snapshot'], old_details)

    def test_invalid_scope_or_mismatched_system_cannot_spend_or_reveal_anything(self):
        for change in ({'scout_scope': 'all'}, {'target_system_id': 's-does-not-exist'},
                       {'target_system_id': self.home['system_id']}, {'mission': 'attack'},
                       {'scout_scope': None}, {'scout_scope': ['system']}):
            before = copy.deepcopy(self.world.data)
            with self.assertRaises(GameError):
                self.world.action(self.player, {**self.payload(), **change})
            self.assertEqual(self.world.data, before)

    def test_own_planet_is_valid_only_for_a_paid_whole_system_scan(self):
        with self.assertRaises(GameError):
            self.world.preview(self.player, self.payload(target=self.home, scope='planet'))
        before = self.home['ships']['scout']
        payload = self.payload(target=self.home)
        quote = self.world.preview(self.player, payload)
        self.assertGreater(quote['fuel_cost'], 0)
        self.assertGreater(quote['seconds'], 0)
        fleet, report = self.scan(payload)
        self.assertEqual(report['system_snapshot']['system_id'], self.home['system_id'])
        self.assertGreaterEqual(report['system_snapshot']['counts']['own'], 1)
        self.world.advance(fleet['arrives_at'])
        self.assertEqual(self.home['ships']['scout'], before)

    def test_pending_system_scan_survives_restart_and_generates_one_immutable_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'scan.sqlite3')
            original = self.world
            # Copy the complete transactional fixture, including its real account
            # credentials and session rows, with SQLite's backup API.
            original._save()
            with sqlite3.connect(path) as disk:
                original.db.backup(disk)
            original.close()
            self.world = World(path, now=NOW)
            self.home = self.world._owned(self.player)
            self.target = self.world.data['planets'][self.target['id']]
            fleet = self.launch()
            arrival = fleet['arrives_at']
            self.world.close()
            self.world = World(path, now=arrival)
            reports = [r for r in self.world._player(self.player)['reports'] if 'system_snapshot' in r]
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0]['system_snapshot']['scouted_at'], arrival)
            self.assertEqual(self.world.data['fleets'][fleet['id']]['scout_scope'], 'system')
            self.world.advance(arrival)
            self.assertEqual(len([r for r in self.world._player(self.player)['reports'] if 'system_snapshot' in r]), 1)


if __name__ == '__main__':
    unittest.main()
