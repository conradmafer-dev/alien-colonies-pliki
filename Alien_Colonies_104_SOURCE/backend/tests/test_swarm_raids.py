"""Raid strategy and actual cargo settlement for the rare Khar resource raids."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from server import swarm, defenses
from server.main import RESOURCES, blank_ships
from tests.world_fixture import LocalTestWorld as World


START = 1_900_000_000
DAY = 86400


class SwarmRaidTests(unittest.TestCase):
    def setUp(self):
        self.world = World(':memory:', now=START)
        self.pid = self.world.register('Raid Pilot', 'testing-password')['state']['player']['id']
        self.player = self.world.data['players'][self.pid]
        self.player['protected_until'] = 0
        self.player['swarm_crystals'] = 17
        self.home = self.world._owned(self.pid)
        self.home['resources'] = dict.fromkeys(RESOURCES, 1_000_000.0)
        self.home['ships'] = blank_ships()
        self.hive = next(p for p in self.world.data['planets'].values()
                         if p['owner_id'] == swarm.OWNER_ID)

    def tearDown(self):
        self.world.close()

    def arriving_raid(self):
        """An existing, paid expedition; completion must recheck current ownership/protection."""
        fleet = {'id': 'arriving-raid', 'owner_id': swarm.OWNER_ID, 'race_id': 'swarm',
                 'origin_id': self.hive['id'], 'target_id': self.home['id'],
                 'mission': 'attack', 'swarm_raid': True, 'status': 'outbound',
                 'ships': {**dict.fromkeys(swarm.SHIPS, 0), 'frigate': 180, 'cruiser': 30, 'cargo': 20},
                 'cargo': dict.fromkeys(RESOURCES, 0), 'swarm_crystals': 0,
                 'swarm_weapon_level': self.world._swarm_weapon_level(self.hive),
                 'seconds': 60, 'started_at': self.world.now - 60,
                 'arrives_at': self.world.now}
        self.world.data['fleets'][fleet['id']] = fleet
        return fleet

    def party(self):
        return {**dict.fromkeys(swarm.SHIPS, 0), **swarm.RAID_PARTY}

    def prepared_origin(self, origin=None):
        origin = origin or self.hive
        origin['queue'] = []
        origin['ships'] = {**dict.fromkeys(swarm.SHIPS, 0), 'frigate': 3000, 'cruiser': 500, 'cargo': 200}
        origin['resources'] = dict.fromkeys(RESOURCES, 100_000_000.0)
        origin['swarm_next_attack_at'] = 0
        return origin

    def ready_clock(self):
        self.world.now = START + swarm.RAID_INTERVAL_SECONDS

    def launch(self, target=None, origin=None, ships=None):
        return self.world._swarm_launch(origin or self.hive, target or self.home,
                                        'attack', ships or self.party(), raid=True)

    def another_player(self):
        pid = self.world.register('Second Raid Pilot', 'testing-password')['state']['player']['id']
        player = self.world.data['players'][pid]
        player['protected_until'] = 0
        home = self.world._owned(pid)
        home['resources'] = dict.fromkeys(RESOURCES, 1_000_000.0)
        home['ships'] = blank_ships()
        return player, home

    def test_real_time_startup_grace_is_48_hours_including_accelerated_world(self):
        self.prepared_origin()
        for speed in (1, 10, 1000):
            with self.subTest(speed=speed):
                self.world.speed = speed
                self.world.now = START + 48 * 3600 - 1
                before = copy.deepcopy(self.hive)
                self.assertIsNone(self.launch())
                self.assertEqual(self.hive, before)
        self.world.now += 1
        self.assertIsNotNone(self.launch())

    def test_paid_raid_departs_with_free_planets_and_keeps_a_home_garrison(self):
        self.prepared_origin()
        self.ready_clock()
        before = copy.deepcopy(self.hive)
        _, fuel = self.world._flight_numbers(self.hive, self.home, self.party())
        fleet = self.launch()
        self.assertIsNotNone(fleet)
        self.assertTrue(fleet['swarm_raid'])
        self.assertEqual(fleet['mission'], 'attack')
        self.assertEqual(fleet['ships'], self.party())
        for key, count in self.party().items():
            self.assertEqual(self.hive['ships'][key], before['ships'][key] - count)
        for key, count in swarm.defense_minimum(self.hive).items():
            self.assertGreaterEqual(self.hive['ships'][key], count)
        self.assertEqual(self.hive['resources']['fuel'], before['resources']['fuel'] - fuel)
        self.assertEqual(self.world.data['alien']['swarm_next_raid_at'], self.world.now + 48 * 3600)
        self.assertEqual(self.player['swarm_raid_protected_until'], self.world.now + 96 * 3600)

    def test_failed_raid_still_consumes_global_gate_shared_by_all_hives(self):
        self.prepared_origin()
        other = next(p for p in self.world.data['planets'].values()
                     if p['owner_id'] == swarm.OWNER_ID and p['id'] != self.hive['id'])
        self.prepared_origin(other)
        second_player, _ = self.another_player()
        # One initial hive per galaxy: its target must be local, while the raid
        # cooldown is deliberately shared by hives in different galaxies.
        second_home = next(p for p in self.world.data['planets'].values()
                           if p['owner_type'] == 'empty' and p['galaxy_id'] == other['galaxy_id'])
        second_home.update(owner_type='player', owner_id=second_player['id'],
                           resources=dict.fromkeys(RESOURCES, 1_000_000.0), ships=blank_ships())
        self.ready_clock()
        fleet = self.launch()
        self.assertIsNotNone(fleet)
        self.world.data['fleets'].pop(fleet['id'])  # Lost before arrival still counts.
        self.world.now += 48 * 3600 - 1
        self.assertIsNone(self.launch(target=second_home, origin=other))
        self.world.now += 1
        self.assertIsNotNone(self.launch(target=second_home, origin=other))

    def test_victim_96_hour_gate_covers_all_of_that_players_planets(self):
        self.prepared_origin()
        other_home = next(p for p in self.world.data['planets'].values() if p['owner_type'] == 'empty')
        other_home.update(owner_type='player', owner_id=self.pid,
                          resources=dict.fromkeys(RESOURCES, 1_000_000.0))
        self.ready_clock()
        fleet = self.launch()
        self.assertIsNotNone(fleet)
        self.world.data['fleets'].pop(fleet['id'])
        self.world.now += 48 * 3600
        before = copy.deepcopy(self.hive)
        self.assertIsNone(self.launch(target=other_home))
        self.assertEqual(self.hive, before)
        self.world.now += 48 * 3600
        self.assertIsNotNone(self.launch(target=other_home))

    def test_protected_and_poor_targets_do_not_consume_a_raid(self):
        self.prepared_origin()
        self.ready_clock()
        self.player['protected_until'] = self.world.now + DAY
        before = copy.deepcopy(self.world.data)
        self.assertIsNone(self.launch())
        self.assertEqual(self.world.data, before)
        self.player['protected_until'] = 0
        self.home['resources'] = dict.fromkeys(RESOURCES, 100.0)
        before = copy.deepcopy(self.world.data)
        self.assertIsNone(self.launch())
        self.assertEqual(self.world.data, before)

    def test_fuel_cost_and_strong_defenders_can_make_a_rich_target_unprofitable(self):
        self.prepared_origin()
        self.ready_clock()
        before = copy.deepcopy(self.world.data)
        with patch.object(self.world, '_flight_numbers', return_value=(60, 2000)):
            self.assertIsNone(self.launch())
        self.assertEqual(self.world.data, before)
        self.home['ships']['cruiser'] = 1000
        self.assertIsNone(self.launch())

    def test_departure_cannot_empty_home_defense_or_invent_cargo_ships(self):
        self.prepared_origin()
        self.ready_clock()
        self.hive['ships']['cargo'] = 0
        before = copy.deepcopy(self.world.data)
        self.assertIsNone(self.launch())
        self.assertEqual(self.world.data, before)
        self.hive['ships']['cargo'] = 4
        self.hive['ships'].update(swarm.defense_minimum(self.hive))
        before = copy.deepcopy(self.world.data)
        self.assertIsNone(self.launch())
        self.assertEqual(self.world.data, before)

    def test_ai_buys_raid_carriers_then_launches_after_the_paid_queue_completes(self):
        self.ready_clock()
        for hive in (p for p in self.world.data['planets'].values() if p['owner_id'] == swarm.OWNER_ID):
            hive['queue'] = [{'kind': 'test-pending'}]  # Keep this test about a single hive.
        self.prepared_origin()
        self.hive['buildings'] = dict.fromkeys(swarm.BUILDINGS, swarm.MAX_BUILDING_LEVEL)
        self.hive['defenses']['acid_spire'] = defenses.swarm_target(self.hive)
        targets = swarm.defense_targets(self.hive, self.world.now)
        self.hive['ships'] = dict.fromkeys(swarm.SHIPS, 0)
        for key, count in targets.items():
            self.hive['ships'][key] = count + swarm.RAID_PARTY.get(key, 0)
        resources = dict(self.hive['resources'])
        self.world._alien_turn()
        self.assertEqual(self.hive['queue'][0]['kind'], 'ship')
        self.assertEqual(self.hive['queue'][0]['key'], 'cargo')
        self.assertEqual(self.hive['ships']['cargo'], 0)
        self.assertLess(self.hive['resources']['metal'], resources['metal'])
        self.assertFalse(self.world.data['fleets'])
        self.world.now = self.hive['queue'][0]['ends_at']
        self.world._complete_queue(self.hive)
        self.world._alien_turn()
        raids = [f for f in self.world.data['fleets'].values() if f.get('swarm_raid')]
        self.assertEqual(len(raids), 1)
        self.assertEqual(raids[0]['target_id'], self.home['id'])
        self.assertEqual(self.hive['ships']['cargo'], 0)
        self.assertTrue(swarm.ready(self.hive))

    def test_upgrade_grace_is_persisted_once_and_restart_preserves_victim_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'raid-upgrade.sqlite3'
            old = World(path, now=START)
            try:
                pid = old.register('Saved Raid Pilot', 'testing-password')['state']['player']['id']
                old.data['alien'].pop('swarm_next_raid_at')  # Genuine 0.4.0 shape.
                old.data['alien']['next_expansion_at'] = START + 30 * DAY
                hive = next(p for p in old.data['planets'].values() if p['owner_id'] == swarm.OWNER_ID)
                hive['swarm_crystals'] = 0
                hive['ships'] = dict.fromkeys(swarm.SHIPS, 0)  # No generation while undefended.
                marked_id = hive['id']
            finally:
                old.close()
            upgraded_at = START + DAY
            upgraded = World(path, now=upgraded_at)
            try:
                self.assertEqual(upgraded.data['alien']['swarm_next_raid_at'], upgraded_at + 48 * 3600)
                self.assertEqual(upgraded.data['planets'][marked_id]['swarm_crystals'], 0)
                self.assertEqual(sum(upgraded.data['planets'][marked_id]['ships'].values()), 0)
                upgraded.data['players'][pid]['swarm_raid_protected_until'] = upgraded_at + 96 * 3600
            finally:
                upgraded.close()
            reopened = World(path, now=upgraded_at + 3600)
            try:
                self.assertEqual(reopened.data['alien']['swarm_next_raid_at'], upgraded_at + 48 * 3600)
                self.assertEqual(reopened.data['players'][pid]['swarm_raid_protected_until'],
                                 upgraded_at + 96 * 3600)
                self.assertEqual(reopened.data['planets'][marked_id]['swarm_crystals'], 0)
                self.assertEqual(sum(reopened.data['planets'][marked_id]['ships'].values()), 0)
            finally:
                reopened.close()

    def test_raid_takes_normal_resources_home_once_but_never_rare_crystals(self):
        self.assertTrue(any(p['owner_type'] == 'empty'
                            for p in self.world.data['planets'].values()))
        fleet = self.arriving_raid()
        home_before = copy.deepcopy(self.home)
        hive_before = copy.deepcopy(self.hive)
        self.world._complete_fleet(fleet)
        self.assertEqual(fleet['status'], 'returning')
        self.assertGreater(sum(fleet['cargo'].values()), 0)
        for resource in RESOURCES:
            self.assertGreater(fleet['cargo'][resource], 0)
            self.assertEqual(self.home['resources'][resource],
                             home_before['resources'][resource] - fleet['cargo'][resource])
        self.assertEqual(self.hive, hive_before, 'Loot is not remotely credited before return.')
        self.assertEqual(fleet['swarm_crystals'], 0)
        self.assertEqual(self.player['swarm_crystals'], 17)
        self.assertEqual(self.home['buildings'], home_before['buildings'])
        self.assertEqual(self.home['owner_id'], self.pid)
        cargo = dict(fleet['cargo'])
        returning_ships = dict(fleet['ships'])
        self.world.now = fleet['arrives_at']
        self.world._complete_fleet(fleet)
        for resource in RESOURCES:
            self.assertEqual(self.hive['resources'][resource],
                             hive_before['resources'][resource] + cargo[resource])
        for key in returning_ships:
            self.assertEqual(self.hive['ships'][key], hive_before['ships'][key] + returning_ships[key])
        after = copy.deepcopy(self.hive)
        self.world._complete_fleet(fleet)
        self.assertEqual(self.hive, after)
        self.assertNotIn(fleet['id'], self.world.data['fleets'])

    def test_protection_gained_during_travel_cancels_even_a_marked_raid(self):
        fleet = self.arriving_raid()
        self.player['protected_until'] = self.world.now + DAY
        before = copy.deepcopy(self.home)
        self.world._complete_fleet(fleet)
        self.assertEqual(self.home, before)
        self.assertEqual(fleet['status'], 'returning')
        self.assertEqual(sum(fleet['cargo'].values()), 0)

    def test_incoming_resource_raid_is_visible_without_its_cargo_or_ship_counts(self):
        fleet = self.arriving_raid()
        fleet['arrives_at'] = self.world.now + 120
        state = self.world.state(self.pid)
        self.assertIn(fleet['id'], [f['id'] for f in state['incoming_attacks']])
        view = next(f for f in state['alien']['fleets'] if f['id'] == fleet['id'])
        self.assertFalse({'ships', 'cargo', 'swarm_crystals'} & set(view))


if __name__ == '__main__':
    unittest.main()
