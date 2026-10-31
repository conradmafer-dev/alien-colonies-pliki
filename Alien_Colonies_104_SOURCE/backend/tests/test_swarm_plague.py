"""Real World/SQLite tests of the NPC-only 0.11.3 migration and AI policy."""
import copy
from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app
import swarm
import swarm_reset
import defenses
import planetary
from i18n import language_scope, render_text, store_text, t

NOW = 2_000_000.0


def npc(world, galaxy='g1'):
    return next(p for p in world.data['planets'].values() if p['owner_id']=='khar' and p['galaxy_id']==galaxy)


def activate_galaxy(world, galaxy, established_at=NOW):
    """Give a real account a settled colony before exercising another galaxy's AI."""
    existing = next((p for p in world.data['planets'].values()
                     if p['owner_id'] == 'khar' and p['galaxy_id'] == galaxy), None)
    if existing is not None:
        return existing
    current = world.now
    try:
        world.now = established_at
        result = world.register('FixtureSettler' + galaxy, 'fixture-password-123')
        owner = result['state']['player']['id']
        colony = next(p for p in world.data['planets'].values()
                      if p['owner_type'] == 'empty' and p['galaxy_id'] == galaxy)
        colony.update(owner_type='player', owner_id=owner)
        world._ensure_swarm_activation()
    finally:
        world.now = current
    return npc(world, galaxy)


def fleet(world, owner, origin, target, fid='test-flight', mission='attack', status='outbound'):
    ships = dict.fromkeys(world._specs(owner, 'ships'), 0)
    ships['frigate'] = 3
    f = dict(id=fid, owner_id=owner, origin_id=origin['id'], target_id=target['id'],
             race_id='swarm' if owner=='khar' else world._race_id(owner), mission=mission,
             status=status, ships=ships, cargo={'metal':17,'crystal':23,'fuel':9},
             swarm_crystals=2, started_at=world.now-60, seconds=600,
             arrives_at=world.now+3600)
    world.data['fleets'][fid]=f
    return f


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.w=app.World(':memory:', now=NOW)
        self.p=npc(self.w)
        self.w.now=NOW+7*86400
        self.w.data['alien']['swarm_next_colonization_by_galaxy']={g:0 for g in app.GALAXIES_BY_ID}
        # Ongoing policy fixtures are already migrated; separate tests cover the
        # one-time cooldown applied to an existing fast-tempo world.
        self.w.data['swarm_expansion_tempo']='slow-20261009'

    def tearDown(self):self.w.close()

    def equipped(self, p=None):
        p=self.p if p is None else p
        p['resources']=dict.fromkeys(app.RESOURCES,1_000_000.)
        p['ships'].update(colonizer=1,frigate=4)
        return p

    def target(self, p=None):return self.w._swarm_expansion_target(self.p if p is None else p)

    def test_fresh_world_is_one_level_one_hive_with_three_rare_crystals_and_no_stock_or_ships(self):
        h=[p for p in self.w.data['planets'].values() if p['owner_id']=='khar']
        self.assertEqual(len(h),1)
        self.assertEqual(h[0]['galaxy_id'], 'g1')
        for p in h:
            self.assertTrue(all(x==1 for x in p['buildings'].values()))
            self.assertEqual(sum(p['resources'].values())+sum(p['ships'].values())+sum(p['defenses'].values()),0)
            self.assertEqual(p['swarm_crystals'],3)

    def test_swarm_only_production_is_sixty_percent_of_previous_rates(self):
        for p in (activate_galaxy(self.w,g) for g in app.GALAXIES_BY_ID):
            new=self.w.production(p)
            old=copy.deepcopy(swarm.RULES);old['production_multipliers']={'metal':1.5,'crystal':1.1,'fuel':1.4}
            with patch.object(swarm,'RULES',old):previous=self.w.production(p)
            for r in app.RESOURCES:self.assertAlmostEqual(new[r],previous[r]*.6)

    def test_npc_costs_and_stats_use_requested_multipliers(self):
        old={'scout':((25,20,5),1,5),'cargo':((75,35,15),2,30),
             'colonizer':((260,120,70),1,45),'frigate':((60,25,10),8,20),
             'cruiser':((500,250,100),65,200)}
        for k,(cost,attack,hull) in old.items():
            self.assertEqual(swarm.SHIPS[k][2],tuple(math.ceil(n*(1 if k=='colonizer' else 1.5)) for n in cost))
            self.assertAlmostEqual(swarm.SHIPS[k][4],attack*.8)
            self.assertAlmostEqual(swarm.SHIPS[k][5],hull*.8)
        self.assertEqual(defenses.DEFENSES['swarm']['acid_spire'][4:6],(72,336))

    def test_colonizer_is_bought_before_any_economic_or_military_upgrade(self):
        self.p['resources']=dict.fromkeys(app.RESOURCES,10000.)
        self.w._alien_turn()
        self.assertEqual((self.p['queue'][0]['kind'],self.p['queue'][0]['key']),('ship','colonizer'))
        for r,cost in zip(app.RESOURCES,swarm.SHIPS['colonizer'][2]):
            self.assertEqual(self.p['resources'][r],10000-cost)
        self.assertEqual(sum(self.p['ships'].values()),0)

    def test_repeated_turns_do_not_finish_queue_or_charge_twice(self):
        self.p['resources']=dict.fromkeys(app.RESOURCES,10000.)
        self.w._alien_turn();before=copy.deepcopy(self.p)
        for _ in range(12):self.w._alien_turn()
        self.assertEqual(self.p,before)

    def test_poor_nest_does_not_spawn_a_free_colonizer(self):
        for _ in range(5):self.w._alien_turn()
        self.assertEqual(sum(self.p['ships'].values()),0)
        self.assertFalse(self.p['queue']);self.assertFalse(self.w.data['fleets'])

    def test_completed_colonizer_needs_only_small_real_escort(self):
        p=self.equipped();target=self.target();before=dict(p['resources'])
        seconds,fuel=self.w._flight_numbers(p,target,{'colonizer':1,'frigate':2})
        f=self.w._swarm_launch(p,target,'colonize',{'colonizer':1,'frigate':2})
        self.assertIsNotNone(f)
        self.assertEqual(p['ships']['frigate'],2);self.assertEqual(p['ships']['colonizer'],0)
        self.assertEqual(p['resources']['fuel'],before['fuel']-fuel)
        self.assertEqual(f['arrives_at'],self.w.now+seconds)
        self.assertEqual(f['ships']['cruiser'],0)

    def test_launch_requires_paid_ships_and_retains_home_defenders(self):
        p=self.equipped();p['ships']['frigate']=3
        before=copy.deepcopy(p)
        self.assertIsNone(self.w._swarm_launch(p,self.target(),'colonize',{'colonizer':1,'frigate':2}))
        self.assertEqual(p,before)

    def test_launch_requires_fuel_and_cannot_overdraw_stock(self):
        p=self.equipped();p['resources']['fuel']=0
        before=copy.deepcopy(p)
        self.assertIsNone(self.w._swarm_launch(p,self.target(),'colonize',{'colonizer':1,'frigate':2}))
        self.assertEqual(p,before)

    def test_colonization_clocks_are_independent_between_galaxies(self):
        for g in ('g1','g2'):
            p=self.equipped(activate_galaxy(self.w,g))
            self.assertIsNotNone(self.w._swarm_launch(p,self.target(p),'colonize',{'colonizer':1,'frigate':2}))
        self.assertEqual(len(self.w._swarm_pending_colonies()),2)

    def test_new_nest_matures_at_twenty_four_hours_and_galaxy_waits_another_day(self):
        second = next(p for p in self.w.data['planets'].values()
                      if p['galaxy_id'] == 'g1' and p['owner_type'] == 'empty')
        swarm.seed(second, self.w.now, hive=False)
        self.equipped(second)
        target = self.target(second)
        self.w.now += 24 * 3600 - 1
        self.assertIsNone(self.w._swarm_launch(second, target, 'colonize', {'colonizer':1,'frigate':2}))
        self.w.now += 1
        launched = self.w._swarm_launch(second, target, 'colonize', {'colonizer':1,'frigate':2})
        self.assertIsNotNone(launched)
        self.assertEqual(second['ships']['colonizer'], 0)
        self.equipped(self.p)
        other_target = self.target(self.p)
        self.w.now += 24 * 3600 - 1
        self.assertIsNone(self.w._swarm_launch(self.p, other_target, 'colonize', {'colonizer':1,'frigate':2}))
        self.w.now += 1
        self.assertIsNotNone(self.w._swarm_launch(self.p, other_target, 'colonize', {'colonizer':1,'frigate':2}))

    def test_fast_waits_extend_once_without_changing_paid_work_or_player_progress(self):
        result = self.w.register('TempoKeeper', 'tempo-keeper-password')
        owner = result['state']['player']['id']
        player = self.w._player(owner)
        home = self.w.data['planets'][player['home_id']]
        player['research']['weapons'] = 6
        home['resources']['metal'] = 12345
        home['queue'] = [dict(id='player-tempo-project', kind='build',
                              key='metal_mine', amount=1, level=2,
                              started_at=self.w.now, seconds=4*86400,
                              ends_at=self.w.now+4*86400)]
        self.w.data['swarm_expansion_tempo'] = 'fast-20261005'
        self.p['swarm_next_colonization_at'] = self.w.now + 2 * 3600
        self.w.data['alien']['swarm_next_colonization_by_galaxy']['g1'] = self.w.now + 30 * 60
        self.p['resources'] = dict.fromkeys(app.RESOURCES, 10000.)
        self.assertTrue(self.w._swarm_queue(self.p, 'ship', 'colonizer'))
        flight = fleet(self.w, 'khar', self.p, self.target(),
                       fid='paid-tempo-flight', mission='colonize')
        queue, resources = copy.deepcopy(self.p['queue']), dict(self.p['resources'])
        players, player_home = copy.deepcopy(self.w.data['players']), copy.deepcopy(home)
        flight_before = copy.deepcopy(flight)
        marker = self.w.data['swarm_reset_id']
        self.w._ensure_swarm_expansion_tempo()
        self.assertEqual(self.p['swarm_next_colonization_at'], self.w.now + 48 * 3600)
        self.assertEqual(self.w.data['alien']['swarm_next_colonization_by_galaxy']['g1'], self.w.now + 24 * 3600)
        self.assertEqual(self.p['queue'], queue)
        self.assertEqual(self.p['resources'], resources)
        self.assertEqual(self.w.data['players'], players)
        self.assertEqual(home, player_home)
        self.assertEqual(flight, flight_before)
        self.assertEqual(self.w.data['swarm_reset_id'], marker)
        self.assertEqual(self.w.data['swarm_expansion_tempo'], 'slow-20261009')
        deadlines = {p['id']: p['swarm_next_colonization_at']
                     for p in self.w.data['planets'].values() if p['owner_id']=='khar'}
        gates = dict(self.w.data['alien']['swarm_next_colonization_by_galaxy'])
        self.w.now += 3600
        self.w._ensure_swarm_expansion_tempo()
        self.assertEqual({p['id']: p['swarm_next_colonization_at']
                          for p in self.w.data['planets'].values() if p['owner_id']=='khar'}, deadlines)
        self.assertEqual(self.w.data['alien']['swarm_next_colonization_by_galaxy'], gates)

    def test_tempo_migration_handles_overdue_missing_and_long_future_deadlines(self):
        activate_galaxy(self.w, 'g2')
        activate_galaxy(self.w, 'g3')
        self.w.data.pop('swarm_expansion_tempo')
        gates = self.w.data['alien']['swarm_next_colonization_by_galaxy']
        gates['g1'] = self.w.now - 86400
        gates.pop('g2')
        gates['g3'] = self.w.now + 7 * 86400
        self.p['swarm_next_colonization_at'] = self.w.now - 86400
        npc(self.w, 'g2').pop('swarm_next_colonization_at')
        npc(self.w, 'g3')['swarm_next_colonization_at'] = self.w.now + 7 * 86400
        self.w._ensure_swarm_expansion_tempo()
        self.assertEqual(gates['g1'], self.w.now + 86400)
        self.assertEqual(gates['g2'], self.w.now + 86400)
        self.assertEqual(gates['g3'], self.w.now + 7 * 86400)
        self.assertEqual(self.p['swarm_next_colonization_at'], self.w.now + 2 * 86400)
        self.assertEqual(npc(self.w, 'g2')['swarm_next_colonization_at'], self.w.now + 2 * 86400)
        self.assertEqual(npc(self.w, 'g3')['swarm_next_colonization_at'], self.w.now + 7 * 86400)

    def test_same_source_waits_forty_eight_hours_despite_an_open_galaxy_gate(self):
        self.equipped()
        first = self.w._swarm_launch(self.p, self.target(), 'colonize',
                                    {'colonizer':1,'frigate':2})
        self.assertIsNotNone(first)
        launched_at = self.w.now
        self.w.now = first['arrives_at']
        self.w._complete_fleet(first)
        self.equipped()
        target = self.target()
        self.w.now = launched_at + 24 * 3600
        self.assertIsNone(self.w._swarm_launch(self.p, target, 'colonize',
                                             {'colonizer':1,'frigate':2}))
        self.w.now = launched_at + 48 * 3600 - 1
        self.assertIsNone(self.w._swarm_launch(self.p, target, 'colonize',
                                             {'colonizer':1,'frigate':2}))
        self.w.now += 1
        self.assertIsNotNone(self.w._swarm_launch(self.p, target, 'colonize',
                                                {'colonizer':1,'frigate':2}))

    def test_repeated_turns_cannot_burst_from_overdue_sources_in_one_galaxy(self):
        second = next(p for p in self.w.data['planets'].values()
                      if p['galaxy_id']=='g1' and p['owner_type']=='empty')
        swarm.seed(second, NOW, hive=False)
        for p in (self.p, second):
            self.equipped(p)
            p['swarm_next_colonization_at'] = NOW
        self.w.data['alien']['swarm_next_colonization_by_galaxy']['g1'] = NOW
        started_at = self.w.now
        self.w._alien_turn()
        self.assertEqual(len(self.w._swarm_pending_colonies()), 1)
        for _ in range(10):
            self.w._alien_turn()
        self.assertEqual(len(self.w._swarm_pending_colonies()), 1)
        self.w.now = started_at + 24 * 3600 - 1
        self.w._alien_turn()
        self.assertEqual(len(self.w._swarm_pending_colonies()), 1)
        self.w.now += 1
        self.w._alien_turn()
        self.assertEqual(len(self.w._swarm_pending_colonies()), 2)

    def test_long_offline_advance_does_not_replay_daily_colonization_slots(self):
        second = next(p for p in self.w.data['planets'].values()
                      if p['galaxy_id']=='g1' and p['owner_type']=='empty')
        swarm.seed(second, NOW, hive=False)
        for p in (self.p, second):
            self.equipped(p)
            p['swarm_next_colonization_at'] = NOW
        self.w.data['alien']['swarm_next_colonization_by_galaxy']['g1'] = NOW
        initial_colonies = sum(p['owner_id']=='khar' for p in self.w.data['planets'].values())
        resumed_at = NOW + 30 * 86400
        self.w.advance(resumed_at)
        self.assertEqual(sum(p['owner_id']=='khar' for p in self.w.data['planets'].values()), initial_colonies)
        self.assertEqual(len(self.w._swarm_pending_colonies()), 1)
        self.assertEqual(self.w.data['alien']['swarm_next_colonization_by_galaxy']['g1'], resumed_at + 86400)

    def test_tempo_marker_and_absolute_deadlines_survive_database_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / 'tempo-restart.sqlite3')
            world = app.World(db, now=NOW)
            try:
                world.data['swarm_expansion_tempo'] = 'fast-20261005'
                npc(world)['swarm_next_colonization_at'] = NOW + 2 * 3600
                world.data['alien']['swarm_next_colonization_by_galaxy']['g1'] = NOW + 30 * 60
                world._ensure_swarm_expansion_tempo()
                deadlines = {p['id']: p['swarm_next_colonization_at']
                             for p in world.data['planets'].values() if p['owner_id']=='khar'}
                gates = dict(world.data['alien']['swarm_next_colonization_by_galaxy'])
            finally:
                world.close()
            reopened = app.World(db, now=NOW + 3600)
            try:
                self.assertEqual(reopened.data['swarm_expansion_tempo'], 'slow-20261009')
                self.assertEqual({p['id']: p['swarm_next_colonization_at']
                                  for p in reopened.data['planets'].values() if p['owner_id']=='khar'}, deadlines)
                self.assertEqual(reopened.data['alien']['swarm_next_colonization_by_galaxy'], gates)
                reopened._ensure_swarm_expansion_tempo()
                self.assertEqual(npc(reopened)['swarm_next_colonization_at'], NOW + 48 * 3600)
                self.assertEqual(reopened.data['alien']['swarm_next_colonization_by_galaxy']['g1'], NOW + 24 * 3600)
            finally:
                reopened.close()

    def test_per_galaxy_gate_blocks_second_origin_but_not_first(self):
        first=self.equipped();self.assertIsNotNone(self.w._swarm_launch(first,self.target(),'colonize',{'colonizer':1,'frigate':2}))
        second=next(p for p in self.w.data['planets'].values() if p['galaxy_id']=='g1' and p['owner_type']=='empty' and p['id']!=next(iter(self.w.data['fleets'].values()))['target_id'])
        swarm.seed(second,NOW,hive=False);self.equipped(second)
        self.assertIsNone(self.w._swarm_launch(second,self.target(second),'colonize',{'colonizer':1,'frigate':2}))

    def test_origin_clock_and_maturity_use_real_seconds_even_at_speed_1000(self):
        p=self.equipped();self.w.speed=1000
        p['swarm_established_at']=self.w.now-3600
        p['swarm_next_colonization_at']=0
        self.assertIsNone(self.w._swarm_launch(p,self.target(),'colonize',{'colonizer':1,'frigate':2}))
        p['swarm_established_at']=NOW;p['swarm_next_colonization_at']=self.w.now+1
        self.assertIsNone(self.w._swarm_launch(p,self.target(),'colonize',{'colonizer':1,'frigate':2}))

    def test_does_not_target_player_or_swarm_colony_reservations(self):
        p=self.equipped();target=self.target()
        f=fleet(self.w,'dummy-owner',p,target,mission='colonize')
        f['ships']['colonizer']=1
        self.assertNotEqual(self.target()['id'],target['id'])
        self.assertIsNone(self.w._swarm_launch(p,target,'colonize',{'colonizer':1,'frigate':2}))

    def test_galaxy_and_global_caps_include_already_travelling_colonies(self):
        activate_galaxy(self.w, 'g2')
        p=self.equipped();tgt=self.target()
        with patch.object(swarm,'MAX_COLONIES_PER_GALAXY',1):
            self.assertIsNone(self.w._swarm_launch(p,tgt,'colonize',{'colonizer':1,'frigate':2}))
        with patch.object(swarm,'MAX_COLONIES',2):
            self.assertIsNone(self.w._swarm_launch(p,tgt,'colonize',{'colonizer':1,'frigate':2}))
        f=self.w._swarm_launch(p,tgt,'colonize',{'colonizer':1,'frigate':2});self.assertIsNotNone(f)
        p2=self.equipped(npc(self.w,'g2'))
        with patch.object(swarm,'MAX_COLONIES',3):
            self.assertFalse(self.w._swarm_colony_room(p2))

    def test_paid_and_queued_colony_hulls_reserve_planning_capacity(self):
        first = self.p
        second = next(p for p in self.w.data['planets'].values()
                      if p['galaxy_id'] == 'g1' and p['owner_type'] == 'empty')
        swarm.seed(second, NOW)
        first['ships']['colonizer'] = 1
        # Two occupied plus one paid hull completely reserve a three-nest cap.
        with patch.object(swarm, 'MAX_COLONIES_PER_GALAXY', 3):
            self.assertIsNone(self.w._swarm_expansion_target(second))
            self.assertIsNotNone(self.w._swarm_expansion_target(first))
            first['ships']['colonizer'] = 0
            first['resources'] = dict.fromkeys(app.RESOURCES, 10000.)
            self.assertTrue(self.w._swarm_queue(first, 'ship', 'colonizer'))
            self.assertIsNone(self.w._swarm_expansion_target(second))
            self.assertIsNotNone(self.w._swarm_expansion_target(first))

    def test_planned_hulls_reserve_global_capacity_not_other_galaxy_slots(self):
        self.p['ships']['colonizer'] = 1
        other = activate_galaxy(self.w, 'g2')
        with patch.object(swarm, 'MAX_COLONIES', 3):
            self.assertFalse(self.w._swarm_has_colony_commitment_room(other))
        with patch.object(swarm, 'MAX_COLONIES_PER_GALAXY', 2):
            self.assertTrue(self.w._swarm_has_colony_commitment_room(other))

    def test_surplus_saves_for_a_cruiser_instead_of_spending_its_fuel(self):
        self.p['buildings']['shipyard'] = 2
        self.p['ships']['frigate'] = 32
        cost = dict(zip(app.RESOURCES, swarm.SHIPS['cruiser'][2]))
        self.p['resources'] = dict(cost)
        self.p['resources']['fuel'] -= 1
        before = copy.deepcopy(self.p)
        self.assertFalse(self.w._swarm_surplus_fleet(self.p))
        self.assertEqual(self.p, before)
        self.p['resources']['fuel'] += 1
        self.assertTrue(self.w._swarm_surplus_fleet(self.p))
        self.assertEqual(self.p['queue'][0]['key'], 'cruiser')
        self.assertEqual(sum(self.p['resources'].values()), 0)

    def test_new_colony_consumes_colonizer_and_only_lands_real_escort(self):
        p=self.equipped();tgt=self.target()
        f=self.w._swarm_launch(p,tgt,'colonize',{'colonizer':1,'frigate':2})
        self.w.now=f['arrives_at'];self.w._complete_fleet(f)
        self.assertEqual(tgt['owner_id'],'khar')
        self.assertEqual(tgt['ships']['colonizer'],0);self.assertEqual(tgt['ships']['frigate'],2)
        self.assertEqual(tgt['ships']['cruiser'],0);self.assertEqual(sum(tgt['resources'].values()),0)
        self.assertEqual(tgt['swarm_crystals'],0)
        before=copy.deepcopy(tgt);self.w._complete_fleet(f);self.assertEqual(tgt,before)

    def test_arrival_rechecks_galaxy_capacity_without_losing_colony_ship(self):
        p=self.equipped();tgt=self.target()
        f=self.w._swarm_launch(p,tgt,'colonize',{'colonizer':1,'frigate':2})
        with patch.object(swarm,'MAX_COLONIES_PER_GALAXY',1):self.w._complete_fleet(f)
        self.assertEqual(tgt['owner_type'],'empty');self.assertEqual(f['status'],'returning')
        self.assertEqual(f['ships']['colonizer'],1)

    def test_ready_expedition_launches_while_facility_queue_is_busy(self):
        self.equipped();self.w._swarm_queue(self.p,'build','power_plant')
        self.w._alien_turn()
        self.assertTrue(self.w._swarm_pending_colonies());self.assertTrue(self.p['queue'])

    def test_surplus_fleet_is_not_blocked_at_garrison_target(self):
        p=self.equipped();p['ships'].update(swarm.defense_targets(p,self.w.now))
        p['buildings']={k:10 for k in swarm.BUILDINGS};p['buildings']['shipyard']=6;p['buildings']['lab']=6
        p['defenses']['acid_spire']=defenses.swarm_target(p)
        self.w.data['alien']['swarm_next_raid_at']=self.w.now+86400
        with patch.object(self.w,'_swarm_expansion_target',return_value=None):self.w._alien_turn()
        self.assertTrue(p['queue']);self.assertEqual(p['queue'][0]['kind'],'ship')
        self.assertIn(p['queue'][0]['key'],('frigate','cruiser'))

    def test_reserve_prevents_spending_the_next_colony_budget(self):
        reserve=self.w._swarm_colony_reserve(self.p,self.target())
        self.p['resources']=dict(reserve)
        self.assertFalse(self.w._swarm_queue(self.p,'ship','frigate',reserve=reserve))
        for r,cost in zip(app.RESOURCES,swarm.SHIPS['frigate'][2]):self.p['resources'][r]+=cost
        self.assertTrue(self.w._swarm_queue(self.p,'ship','frigate',reserve=reserve))
        self.assertEqual(self.p['resources'],reserve)

    def test_empty_galaxy_does_not_trigger_invasion_of_protected_player(self):
        reg=self.w.register('Protected','long-password-123')
        owner=reg['state']['player']['id'];target=self.w.data['planets'][self.w._player(owner)['home_id']]
        self.w._player(owner)['protected_until']=self.w.now+86400
        target['resources']=dict.fromkeys(app.RESOURCES,1_000_000)
        self.assertEqual(self.w._swarm_raid_score(self.p,target,swarm.RAID_PARTY),0)

    def test_growth_ceiling_advances_slowly_and_never_grants_levels(self):
        p=self.equipped();p['swarm_established_at']=self.w.now
        self.assertFalse(self.w._swarm_grow_economy(p))
        self.w.now+=36*3600
        self.assertTrue(self.w._swarm_grow_economy(p))
        self.assertTrue(all(n==1 for n in p['buildings'].values()))
        self.assertEqual(p['queue'][0]['level'],2)
        self.assertNotIn(p['queue'][0]['key'],('lab','shipyard'))

    def test_low_threat_is_not_mislabelled_extreme(self):
        self.p['ships']['frigate']=2
        self.assertEqual(swarm.public_planet(self.p,self.w.now)['swarm_threat'],'Niska')
        self.assertFalse(swarm.public_planet(self.p,self.w.now)['swarm_threat_high'])


class SignupTests(unittest.TestCase):
    def setUp(self):self.w=app.World(':memory:',now=NOW)
    def tearDown(self):self.w.close()
    def available(self):return [p for p in self.w.data['planets'].values() if p['owner_type']=='empty']

    def test_many_new_accounts_begin_in_first_galaxy(self):
        for i in range(8):
            result=self.w.register('Colonist'+str(i),'signup-password-123')
            player=result['state']['player'];home=self.w.data['planets'][self.w._player(player['id'])['home_id']]
            self.assertEqual(home['galaxy_id'],'g1')

    def test_small_available_world_below_half_wins_over_large_second_galaxy(self):
        g1=next(p for p in self.available() if p['galaxy_id']=='g1');g1['environment']['fields']=64
        g2=next(p for p in self.available() if p['galaxy_id']=='g2');g2['environment']['fields']=160
        self.assertIs(self.w._choose_start_planet([g2,g1]),g1)

    def test_full_first_then_second_moves_to_third_in_order(self):
        for blocked,expected in [({'g1'},'g2'),({'g1','g2'},'g3')]:
            available=[p for p in self.available() if p['galaxy_id'] not in blocked]
            for _ in range(15):self.assertEqual(self.w._choose_start_planet(available)['galaxy_id'],expected)

    def test_registration_respects_last_planet_colonization_reservation(self):
        reg=self.w.register('FirstOwner','signup-password-123');owner=reg['state']['player']['id']
        home=self.w.data['planets'][self.w._player(owner)['home_id']]
        empty_g1=[p for p in self.available() if p['galaxy_id']=='g1']
        last=empty_g1.pop()
        for p in empty_g1:p.update(owner_id=owner,owner_type='player')
        f=fleet(self.w,owner,home,last,mission='colonize');f['ships']['colonizer']=1
        result=self.w.register('SecondOwner','signup-password-123');new=result['state']['player']['id']
        self.assertEqual(self.w.data['planets'][self.w._player(new)['home_id']]['galaxy_id'],'g2')
        self.assertEqual(last['owner_type'],'empty');self.assertEqual(home['owner_id'],owner)

    def test_default_hosted_cap_no_longer_stops_at_fifteen_accounts(self):
        import run
        with tempfile.TemporaryDirectory() as d:
            _,argv,_=run.configuration(None,None,{'RAILWAY_SERVICE_ID':'fixture','RAILWAY_VOLUME_MOUNT_PATH':d})
            self.assertEqual(argv[argv.index('--max-players')+1],'0')
            _,argv,_=run.configuration(None,None,{'RAILWAY_SERVICE_ID':'fixture','RAILWAY_VOLUME_MOUNT_PATH':d,'PGR_MAX_PLAYERS':'19'})
            self.assertEqual(argv[argv.index('--max-players')+1],'19')


class ResetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=Path(self.temp.name)/'private_test.sqlite3'
        w=app.World(str(self.db),now=NOW)
        r=w.register('Keeper','keeper-password-123');self.owner=r['state']['player']['id'];self.token=r['token']
        player=w._player(self.owner);player['race_id']='zetans';w._ensure_racial_research(player)
        player['skill_nodes']=app.skill_tree.unlocked_for('zetans', player['skill_nodes'])
        player['research']['weapons']=4;player['swarm_crystals']=27
        self.home_id=player['home_id'];home=w.data['planets'][self.home_id]
        w._ensure_race_buildings(home);home['ships']['frigate']=51
        home['buildings']['metal_mine']=5
        home['queue']=[dict(id='player-project',kind='build',key='refinery',level=2,amount=1,started_at=NOW,seconds=3600,ends_at=NOW+3600)]
        h=npc(w);self.hive_id=h['id'];self.env=copy.deepcopy(h['environment']);self.trait=h['rare_trait']
        for p in w.data['planets'].values():
            if p['owner_id']=='khar':
                p['buildings']={k:8 if k!='lab' else 6 for k in swarm.BUILDINGS}
                p['resources']=dict.fromkeys(app.RESOURCES,50000.)
                p['ships'].update(frigate=360,cruiser=60,colonizer=2)
                p['defenses']={'acid_spire':12};p['swarm_crystals']=6
        extra=next(p for p in w.data['planets'].values() if p['owner_type']=='empty' and p['galaxy_id']=='g1')
        self.extra_id=extra['id'];swarm.seed(extra,NOW-86400);extra['ships']['frigate']=120
        w._capture_swarm_intel(self.owner,h);w._capture_planetary_intel(self.owner,h)
        fleet(w,'khar',h,home,'npc-raid');fleet(w,self.owner,home,h,'player-attack')
        fleet(w,self.owner,home,h,'already-returning',status='returning')
        w.data['alien']['swarm_next_colonization_at']=NOW+999999
        w.data.pop('swarm_reset_id',None)
        w.data['alien']['next_expansion_at']=NOW+120
        w.data['last_update']=NOW
        w.close()
        self.original=self.read_snapshot()
        self.tables=self.read_tables()
        self.world=None

    def tearDown(self):
        if self.world:self.world.close()
        self.temp.cleanup()

    def read_snapshot(self,path=None):
        with closing(sqlite3.connect(str(path or self.db))) as db:return json.loads(db.execute('SELECT body FROM snapshot').fetchone()[0])

    def read_tables(self):
        with closing(sqlite3.connect(str(self.db))) as db:return {table:db.execute('SELECT * FROM '+table+' ORDER BY 1').fetchall() for table in ('accounts','sessions','account_recovery')}

    def start(self,now=NOW):
        self.world=app.World(str(self.db),now=now)
        return self.world

    def test_migration_erases_old_npc_progress_and_seeds_only_eligible_galaxies(self):
        w=self.start();h=[p for p in w.data['planets'].values() if p['owner_id']=='khar']
        self.assertEqual(len(h),1);self.assertEqual({p['galaxy_id'] for p in h},{'g1'})
        for p in h:
            self.assertTrue(all(x==1 for x in p['buildings'].values()))
            self.assertEqual(sum(p['ships'].values())+sum(p['resources'].values())+sum(p['defenses'].values()),0)
            self.assertEqual(p['swarm_crystals'],3)
        self.assertEqual(w.data['planets'][self.extra_id]['owner_type'],'empty')
        self.assertNotIn('npc-raid',w.data['fleets'])
        self.assertNotIn('swarm_next_colonization_at',w.data['alien'])

    def test_migration_keeps_accounts_sessions_player_wallets_ships_research_and_queues(self):
        w=self.start();before=self.original['players'][self.owner];after=w._player(self.owner)
        for k in ('research','skill_nodes','swarm_crystals','home_id','race_id','protected_until'):
            self.assertEqual(after[k],before[k],k)
        self.assertEqual(w.data['planets'][self.home_id],self.original['planets'][self.home_id])
        self.assertEqual(self.read_tables(),self.tables)
        self.assertEqual(w.login('Keeper','keeper-password-123')['ok'],True)

    def test_missing_legacy_balance_marker_does_not_reset_players(self):
        data = copy.deepcopy(self.original)
        data.pop('balance_reset_id', None)
        with closing(sqlite3.connect(str(self.db))) as db:
            db.execute('UPDATE snapshot SET body=?', (json.dumps(data),))
            db.commit()
        w = self.start()
        self.assertEqual(w.data['planets'][self.home_id], data['planets'][self.home_id])
        self.assertEqual(w._player(self.owner)['research'], data['players'][self.owner]['research'])
        self.assertEqual(w._player(self.owner)['swarm_crystals'], 27)
        self.assertEqual(w.data['swarm_reset_id'], swarm.RESET_ID)

    def test_verified_permanent_backup_matches_entire_original_snapshot(self):
        w=self.start();path=self.db.parent/'reset-backups'/w.data['swarm_reset_backup']
        self.assertTrue(path.is_file());self.assertIn(swarm.RESET_ID,path.name)
        self.assertEqual(self.read_snapshot(path),self.original)
        with closing(sqlite3.connect(str(path))) as db:self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_attack_returns_without_losses_and_existing_return_trip_is_unchanged(self):
        w=self.start();f=w.data['fleets']['player-attack'];before=self.original['fleets']['player-attack']
        self.assertEqual(f['status'],'returning')
        for k in ('ships','cargo','swarm_crystals'):self.assertEqual(f[k],before[k])
        self.assertEqual(f['arrives_at'],NOW+60)
        self.assertEqual(w.data['fleets']['already-returning'],self.original['fleets']['already-returning'])

    def test_planet_environment_traits_and_historical_reports_survive(self):
        w=self.start();p=w.data['planets'][self.hive_id]
        self.assertEqual(p['environment'],self.env);self.assertEqual(p['rare_trait'],self.trait)
        self.assertNotIn(self.hive_id,w._player(self.owner)['scout_intel'])
        self.assertNotIn(self.hive_id,w._player(self.owner)['planet_intel'])
        oldids={r['id'] for r in self.original['players'][self.owner]['reports']}
        self.assertTrue(oldids <= {r['id'] for r in w._player(self.owner)['reports']})

    def test_reset_runs_once_and_never_respawns_nests_on_next_restart(self):
        w=self.start();p=w.data['planets'][self.hive_id]
        p['resources']['metal']=731;p['ships']['frigate']=29
        marker=w.data['swarm_reset_at'];backups=list((self.db.parent/'reset-backups').glob('*.sqlite3'))
        w.close();self.world=None;w=self.start()
        self.assertEqual(w.data['planets'][self.hive_id]['ships']['frigate'],29)
        self.assertEqual(w.data['planets'][self.hive_id]['resources']['metal'],731)
        self.assertEqual(w.data['swarm_reset_at'],marker)
        self.assertEqual(list((self.db.parent/'reset-backups').glob('*.sqlite3')),backups)

    def test_offline_interval_does_not_grant_income_to_newly_seeded_nests(self):
        w=self.start(NOW+86400)
        for p in w.data['planets'].values():
            if p['owner_id']=='khar':self.assertEqual(sum(p['resources'].values()),0)
        self.assertEqual(w.data['planets'][self.home_id]['buildings']['refinery'],2)
        self.assertGreater(w.data['planets'][self.home_id]['resources']['metal'],self.original['planets'][self.home_id]['resources']['metal'])

    def test_failed_backup_aborts_without_any_reset(self):
        with patch.object(app,'verified_reset_backup',side_effect=OSError('fixture disk full')):
            with self.assertRaises(OSError):self.start()
        self.assertEqual(self.read_snapshot(),self.original);self.assertEqual(self.read_tables(),self.tables)

    def test_transaction_failure_rolls_back_partial_reset_and_marker(self):
        original=app.World._apply_swarm_reset
        def broken(world,backup=None):
            original(world,backup)
            raise RuntimeError('fixture failure after NPC reset')
        with patch.object(app.World,'_apply_swarm_reset',broken):
            with self.assertRaises(RuntimeError):self.start()
        self.assertEqual(self.read_snapshot(),self.original);self.assertEqual(self.read_tables(),self.tables)

    def test_no_http_or_accidental_outside_transaction_reset_path(self):
        w=self.start();w.data.pop('swarm_reset_id')
        with self.assertRaises(RuntimeError):w._apply_swarm_reset()
        w.data['swarm_reset_id']=swarm.RESET_ID
        self.assertIn('apply_balance_reset=False',(ROOT/'app.py').read_text().split('def main(argv=None')[1])

    def test_reset_never_takes_a_player_planet_even_when_first_galaxy_is_full(self):
        data=self.original
        for p in data['planets'].values():
            if p['galaxy_id']=='g1':
                p.update(owner_id=self.owner,owner_type='player')
                p['ships']={k:0 for k in app.SHIPS};p['defenses']={};p['queue']=[]
        # Existing test attack is now player-owned, therefore not a reset target.
        with closing(sqlite3.connect(str(self.db))) as db:
            db.execute('UPDATE snapshot SET body=?',(json.dumps(data),));db.commit()
        w=self.start()
        self.assertFalse(any(p['owner_id']=='khar' and p['galaxy_id']=='g1' for p in w.data['planets'].values()))
        self.assertTrue(all(p['owner_id']==self.owner for p in w.data['planets'].values() if p['galaxy_id']=='g1'))

    def test_coalition_operation_is_cancelled_and_all_contributed_ships_return(self):
        data=self.original;f=copy.deepcopy(data['fleets']['player-attack'])
        f.update(id='coalition-flight',mission='alliance_attack',operation_id='fixture-op')
        data['fleets'][f['id']]=f
        data['alliance_operations']['fixture-op']=dict(id='fixture-op',alliance_id='fixture-alliance',
          creator_id=self.owner,created_at=NOW-60,impact_at=NOW+600,status='forming',
          target={'id':self.hive_id,'name':'Old hive'},target_owner_id='khar',known_swarm=True,
          participants={self.owner:{'fleet_id':f['id'],'status':'outbound'}})
        with closing(sqlite3.connect(str(self.db))) as db:
            db.execute('UPDATE snapshot SET body=?',(json.dumps(data),));db.commit()
        w=self.start();op=w.data['alliance_operations']['fixture-op']
        self.assertEqual(op['status'],'cancelled');self.assertEqual(op['cancel_reason'],'swarm_reset')
        returning=w.data['fleets'][f['id']]
        self.assertEqual(returning['status'],'returning');self.assertEqual(returning['ships'],f['ships'])
        self.assertEqual(returning['cargo'],f['cargo'])

    def test_new_reset_reports_are_localized_in_all_existing_languages(self):
        w=self.start();report=next(r for r in w._player(self.owner)['reports'] if r['title']==swarm_reset.RESET_TITLE)
        for lang in ('en','de','es','fr'):
            rendered=render_text(report['i18n']['text'],lang)
            self.assertNotIn('zostały',rendered);self.assertNotEqual(rendered,swarm_reset.RESET_TEXT)
            with language_scope(lang):self.assertNotEqual(str(t(swarm.DESCRIPTION)),swarm.DESCRIPTION)


if __name__=='__main__':unittest.main()

