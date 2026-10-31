"""0.7.0 integration tests use the REAL random-spawn World, not the legacy fixture."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from server.main import World, RESOURCES, GameError, blank_ships, ECONOMY_MULTIPLIER
from server import defenses, swarm
from server.i18n import language_scope

NOW = 1_900_000_000.0
PASSWORD = 'integration-strong-password'


class ReconDefenseTests(unittest.TestCase):
    def setUp(self):
        self.w = World(':memory:', now=NOW)
        self.pid = self.w.register('Integration Pilot', PASSWORD)['state']['player']['id']
        self.home = self.w._owned(self.pid)
        self.hive = next(p for p in self.w.data['planets'].values()
                         if p['owner_id'] == 'khar' and p['galaxy_id'] == self.home['galaxy_id'])
        self.w.data['alien']['next_expansion_at'] = NOW + 10**8

    def tearDown(self):
        self.w.close()

    def choose(self, race='zetans'):
        self.w.action(self.pid, {'type': 'choose_race', 'race_id': race})
        self.home['buildings']['shipyard'] = 1
        self.home['resources'] = dict.fromkeys(RESOURCES, 100_000_000.0)
        return next(iter(defenses.DEFENSES[race]))

    def view(self, pid=None):
        return next(p for s in self.w.state(pid or self.pid)['galaxy'] for p in s['planets'] if p['id'] == self.hive['id'])

    def scout(self, arrive=True):
        self.home['resources']['fuel'] = 100_000_000.0
        self.home['ships']['scout'] = max(1, self.home['ships']['scout'])
        before = set(self.w.data['fleets'])
        self.w.action(self.pid, {'type':'fleet', 'mission':'scout', 'target_id':self.hive['id'], 'ships':{'scout':1}})
        fleet = self.w.data['fleets'][next(iter(set(self.w.data['fleets']) - before))]
        if arrive:
            self.w.now = fleet['arrives_at']
            self.w._complete_fleet(fleet)
        return fleet

    def test_real_world_has_exactly_one_seed_per_galaxy(self):
        hives=[p for p in self.w.data['planets'].values() if p['owner_id']=='khar']
        self.assertEqual(len(hives),6)
        self.assertEqual(sorted(p['galaxy_id'] for p in hives),['g1','g2','g3','g4','g5','g6'])
        self.assertTrue(all(p['defenses']=={'acid_spire':12} for p in hives))

    def test_real_registration_can_select_each_galaxy(self):
        real_choice=__import__('secrets').choice
        for i in range(1,7):
            gid=f'g{i}'
            def choose(items):
                return gid if items and isinstance(items[0],str) and gid in items else real_choice(items)
            with patch('server.main.secrets.choice',side_effect=choose):
                pid=self.w.register('Spawn'+gid,PASSWORD)['state']['player']['id']
            self.assertEqual(self.w._owned(pid)['galaxy_id'],gid)

    def test_spawn_excludes_reserved_colonization_targets(self):
        target=next(p for p in self.w.data['planets'].values() if p['owner_type']=='empty')
        self.w.data['fleets']['reserve']={'owner_id':'khar','id':'reserve','origin_id':self.hive['id'],
            'target_id':target['id'],'mission':'colonize','status':'outbound','ships':{'colonizer':1},'arrives_at':NOW+100}
        seen=[]
        original=self.w._choose_start_planet
        def observe(candidates):
            seen.extend(p['id'] for p in candidates)
            return original(candidates)
        self.w._choose_start_planet=observe
        self.w.register('NoReservedSpawn',PASSWORD)
        self.assertNotIn(target['id'],seen)

    def test_full_galaxy_is_not_used_for_registration(self):
        for p in self.w.data['planets'].values():
            if p['galaxy_id']=='g1' and p['owner_type']=='empty':
                p.update(owner_type='player',owner_id=self.pid)
        seen=[]
        original=self.w._choose_start_planet
        def observe(candidates):
            seen.extend(p['galaxy_id'] for p in candidates); return original(candidates)
        self.w._choose_start_planet=observe
        other=self.w.register('OtherGalaxy',PASSWORD)['state']['player']['id']
        self.assertNotIn('g1',seen)
        self.assertNotEqual(self.w._owned(other)['galaxy_id'],'g1')

    def test_unscouted_planet_never_sends_private_telemetry(self):
        visible=self.view()
        self.assertFalse(visible['has_scout'])
        for key in ('swarm_buildings','swarm_power','swarm_crystals_stock','swarm_crystals_next_at',
                    'resources','swarm_units','swarm_defenses','scouted_at','swarm_activity'):
            self.assertNotIn(key,visible)
        self.hive['buildings']['metal_mine']=20
        self.hive['resources']['metal']=123456789
        self.assertEqual(visible,self.view())

    def test_departure_does_not_reveal_intel_before_arrival(self):
        self.scout(False)
        self.assertFalse(self.view()['has_scout'])
        self.assertFalse(self.w.data['players'][self.pid]['scout_intel'])

    def test_arrival_observes_actual_not_departure_values(self):
        fleet=self.scout(False)
        self.hive['buildings']['metal_mine']=13
        self.hive['swarm_activity']='preparing_raid'
        self.w.now=fleet['arrives_at']; self.w._complete_fleet(fleet)
        visible=self.view()
        self.assertTrue(visible['has_scout'])
        self.assertEqual(visible['scouted_at'],self.w.now)
        self.assertEqual(visible['swarm_activity_key'],'preparing_raid')
        self.assertEqual(next(b['level'] for b in visible['swarm_buildings'] if b['key']=='metal_mine'),13)

    def test_map_is_an_immutable_snapshot_despite_ai_changes(self):
        self.scout(); before=copy.deepcopy(self.view())
        self.hive['resources']['metal']=99999
        self.hive['buildings']['metal_mine']=20
        self.hive['ships']['frigate']=1
        self.hive['defenses']['acid_spire']=55
        self.hive['swarm_activity']='fortifying'
        self.w.now+=3600
        self.assertEqual(before,self.view())
        self.assertNotIn('swarm_crystals_next_at',self.view())

    def test_intelligence_is_private_to_the_observer(self):
        self.scout()
        other=self.w.register('AnotherObserver',PASSWORD)['state']['player']['id']
        self.assertTrue(self.view()['has_scout']); self.assertFalse(self.view(other)['has_scout'])
        self.w._capture_swarm_intel(other,self.hive)
        original=copy.deepcopy(self.view())
        self.hive['resources']['metal']+=1000
        self.w._capture_swarm_intel(other,self.hive)
        self.assertEqual(original,self.view())

    def test_new_scout_updates_map_but_not_historical_report(self):
        self.scout(); report=next(r for r in self.w.state(self.pid)['reports'] if 'scout' in r)
        self.hive['buildings']['metal_mine']=17
        self.w.now+=100
        self.scout()
        latest=self.view()
        self.assertGreater(latest['scouted_at'],report['scout']['scouted_at'])
        history=next(r for r in self.w.state(self.pid)['reports'] if r['id']==report['id'])
        self.assertEqual(report,history)
        self.assertEqual(next(b['level'] for b in latest['swarm_buildings'] if b['key']=='metal_mine'),17)

    def test_language_switch_translates_same_observation(self):
        self.hive['swarm_activity']='preparing_raid'; self.scout()
        with language_scope('en'):
            english=self.view()
            self.assertEqual(english['swarm_activity'],'Preparing a raid')
        with language_scope('pl'):
            polish=self.view()
            self.assertEqual(polish['swarm_activity'],'Przygotowuje najazd')
        self.assertEqual(english['scouted_at'],polish['scouted_at'])
        self.assertEqual(english['swarm_crystals_stock'],polish['swarm_crystals_stock'])

    def test_preview_does_not_reveal_fresh_crystal_stock(self):
        payload={'mission':'attack','target_id':self.hive['id'],'ships':{'frigate':1},'allow_unaffordable':True}
        before=self.w.preview(self.pid,payload)
        self.hive['swarm_crystals']=0
        self.assertEqual(before,self.w.preview(self.pid,payload))
        self.scout(); first=self.w.preview(self.pid,payload)
        self.hive['swarm_crystals']=6
        self.assertEqual(first,self.w.preview(self.pid,payload))

    def test_ai_queue_has_simple_activity_not_building_narrative(self):
        self.hive['queue']=[{'kind':'build','key':'metal_mine','level':9,'amount':1,'ends_at':NOW+500}]
        self.hive['swarm_activity']='developing'; self.scout()
        with language_scope('en'):
            visible=self.view()
        self.assertEqual(visible['swarm_activity'],'Developing the colony')
        self.assertNotIn('9',visible['swarm_activity'])

    def test_outgoing_swarm_mission_is_actual_plan_but_not_global_feed(self):
        target=next(p for p in self.w.data['planets'].values() if p['owner_type']=='empty')
        self.w.data['fleets']['secret']={'id':'secret','owner_id':'khar','origin_id':self.hive['id'],
            'target_id':target['id'],'mission':'colonize','status':'outbound','ships':{'colonizer':1},'arrives_at':NOW+999}
        self.assertEqual(self.w._swarm_activity_at(self.hive),'expanding')
        self.assertEqual(self.w.state(self.pid)['alien']['fleets'],[])

    def test_recommended_target_does_not_follow_secret_defense_changes(self):
        before=self.w.state(self.pid)['alien']['recommended_target_id']
        for p in self.w.data['planets'].values():
            if p['owner_id']=='khar':
                p['ships']['frigate']=999999 if p['id']==before else 1
                p['swarm_crystals']=0 if p['id']==before else 6
        self.assertEqual(self.w.state(self.pid)['alien']['recommended_target_id'],before)

    def test_no_chosen_race_means_no_defense_purchase(self):
        self.assertEqual(self.w.state(self.pid)['catalog']['defenses'],[])
        with self.assertRaises(GameError): self.w.action(self.pid,{'type':'defense','key':'phase_sentinel'})

    def test_each_player_race_has_one_distinct_static_catalog_entry(self):
        for race in ('zetans','automatons','symbionts'):
            pid=self.w.register('Defender'+race,PASSWORD)['state']['player']['id']
            self.w.action(pid,{'type':'choose_race','race_id':race})
            entries=self.w.state(pid)['catalog']['defenses']
            self.assertEqual(len(entries),1)
            entry=entries[0]
            self.assertIn(entry['key'],defenses.DEFENSES[race])
            self.assertTrue(entry['stationary']); self.assertGreater(entry['hull'],0)
            self.assertNotIn('speed',entry); self.assertNotIn(entry['key'],[s['key'] for s in self.w.state(pid)['catalog']['ships']])

    def test_build_requires_local_shipyard(self):
        key=self.choose(); self.home['buildings']['shipyard']=0
        with self.assertRaises(GameError):self.w.action(self.pid,{'type':'defense','key':key})
        self.home['buildings']['shipyard']=1
        self.w.action(self.pid,{'type':'defense','key':key})
        self.assertEqual(self.home['queue'][0]['kind'],'defense')

    def test_static_batch_has_exact_payment_count_and_idempotence(self):
        key=self.choose(); cost=self.w._catalog(self.pid,self.home)['defenses'][0]['cost']
        stocks=copy.deepcopy(self.home['resources'])
        payload={'type':'defense','key':key,'amount':3,'request_id':'static-once'}
        self.w.action(self.pid,payload); self.w.action(self.pid,payload)
        self.assertEqual(len(self.home['queue']),1)
        for k in RESOURCES: self.assertEqual(self.home['resources'][k],stocks[k]-3*cost[k])
        self.w._complete_queue(self.home); self.w._complete_queue(self.home)
        self.assertEqual(self.home['defenses'][key],3)
        self.assertNotIn(key,self.home['ships'])

    def test_cannot_build_another_races_or_khar_static(self):
        self.choose()
        for key in ('iron_bastion','rooted_spore','acid_spire'):
            before=copy.deepcopy(self.w.data)
            with self.assertRaises(GameError):self.w.action(self.pid,{'type':'defense','key':key})
            self.assertEqual(before,self.w.data)

    def test_stationary_units_rejected_in_every_fleet_mission(self):
        key=self.choose(); self.home['defenses'][key]=30
        for mission in ('scout','attack','transport','colonize'):
            before=copy.deepcopy(self.w.data)
            with self.assertRaises(GameError):self.w.action(self.pid,{'type':'fleet','mission':mission,'target_id':self.hive['id'],'ships':{key:1}})
            self.assertEqual(before,self.w.data)
        with self.assertRaises(GameError):self.w.action(self.pid,{'type':'fleet','mission':'scout','target_id':self.hive['id'],'ships':{'scout':1,key:0}})

    def test_stationary_units_cannot_be_sent_as_cargo(self):
        key=self.choose()
        with self.assertRaises(GameError):self.w.action(self.pid,{'type':'fleet','mission':'scout','target_id':self.hive['id'],'ships':{'scout':1},'cargo':{key:1}})

    def test_symbiont_multiplication_does_not_multiply_defenses(self):
        key=self.choose('symbionts')
        self.w.data['players'][self.pid]['research']['multiplication']=5
        self.w.action(self.pid,{'type':'defense','key':key,'amount':3}); self.w._complete_queue(self.home)
        self.assertEqual(self.home['defenses'][key],3)
        before=copy.deepcopy(self.home['defenses']); self.w._multiply_existing_fleet(self.pid,0,5)
        self.assertEqual(before,self.home['defenses'])

    def test_automaton_defense_construction_refund_is_paid_once(self):
        key=self.choose('automatons'); self.w.data['players'][self.pid]['research']['recycling']=2
        initial=self.home['resources']['metal']
        self.w.action(self.pid,{'type':'defense','key':key,'amount':2})
        task=self.home['queue'][0]; refund=task['construction_refund']['metal']
        paid=initial-self.home['resources']['metal']
        self.w._complete_queue(self.home); self.w._complete_queue(self.home)
        self.assertEqual(self.home['resources']['metal'],initial-paid+refund)
        self.assertGreater(refund,0)

    def test_swarm_builds_acid_spires_for_real_resources(self):
        self.hive['defenses']['acid_spire']=0
        before=copy.deepcopy(self.hive['resources'])
        self.assertTrue(self.w._swarm_train_defenses(self.hive))
        task=copy.deepcopy(self.hive['queue'][0]); spec=defenses.DEFENSES['swarm']['acid_spire']
        self.assertEqual(task['kind'],'defense')
        for k,c in zip(RESOURCES,spec[2]):self.assertEqual(self.hive['resources'][k],before[k]-task['amount']*c)
        self.w._complete_queue(self.hive)
        self.assertEqual(self.hive['defenses']['acid_spire'],task['amount'])

    def test_unfunded_swarm_cannot_create_static_defense(self):
        self.hive['defenses']['acid_spire']=0; self.hive['resources']=dict.fromkeys(RESOURCES,0)
        self.assertFalse(self.w._swarm_train_defenses(self.hive)); self.assertEqual(self.hive['queue'],[])

    def test_new_expansion_outpost_gets_no_free_static_units(self):
        p=next(p for p in self.w.data['planets'].values() if p['owner_type']=='empty')
        swarm.seed(p,self.w.now,hive=False)
        self.assertEqual(sum(p['defenses'].values()),0)

    def test_static_only_defender_participates_in_battle(self):
        key=self.choose('automatons'); self.home['ships']=blank_ships(); self.home['defenses'][key]=20
        self.w.data['players'][self.pid]['protected_until']=0
        raid={'id':'static-battle','owner_id':'khar','origin_id':self.hive['id'],'target_id':self.home['id'],
              'mission':'attack','status':'outbound','ships':{**dict.fromkeys(swarm.SHIPS,0),'frigate':1},
              'seconds':30,'cargo':dict.fromkeys(RESOURCES,0),'swarm_crystals':0,'swarm_raid':True}
        self.w.data['fleets'][raid['id']]=raid
        self.w._complete_fleet(raid)
        self.assertEqual(sum(raid['ships'].values()),0)
        self.assertGreater(self.home['defenses'][key],0)
        self.assertNotIn(key,self.home['ships'])
        self.assertNotIn(key,raid['ships'])

    def test_phase_first_volley_and_acid_ramp(self):
        self.assertEqual(defenses.round_factors(1)['phase_sentinel'],1.5)
        self.assertEqual(defenses.round_factors(2)['phase_sentinel'],1)
        self.assertEqual(defenses.round_factors(1)['acid_spire'],1)
        self.assertEqual(defenses.round_factors(6)['acid_spire'],1.25)
        self.assertEqual(defenses.round_factors(100)['acid_spire'],1.25)

    def test_bastion_extra_armor_is_multiplicative_and_spillover_safe(self):
        spec=defenses.DEFENSES['automatons']; fleet={'iron_bastion':2}; wounds={}
        self.w._damage(fleet,100,wounds,spec,.12,{'iron_bastion':.25})
        self.assertAlmostEqual(wounds['iron_bastion'],66)
        self.assertEqual(fleet['iron_bastion'],2)
        fleet={'iron_bastion':2}; wounds={}
        self.w._damage(fleet,10000,wounds,spec,.12,{'iron_bastion':.25})
        self.assertEqual(fleet['iron_bastion'],0)

    def test_spore_regeneration_does_not_resurrect_dead_batteries(self):
        fleet={'rooted_spore':1}; wounds={'rooted_spore':100}
        self.w._regenerate(fleet,wounds,.35,{'rooted_spore':.5})
        self.assertEqual(wounds['rooted_spore'],50)
        fleet['rooted_spore']=0
        self.w._regenerate(fleet,wounds,.35,{'rooted_spore':.5})
        self.assertEqual(wounds['rooted_spore'],0); self.assertEqual(fleet['rooted_spore'],0)

    def test_all_ordinary_income_is_one_tenth_without_reducing_energy(self):
        for p in (self.home,self.hive):
            energy=self.w.energy(p)
            for speed in (1,10):
                self.w.speed=speed
                rules=self.w._rules(p['owner_id'])
                for resource,key,base,per in (('metal','metal_mine',90,450),('crystal','crystal_mine',60,330),('fuel','refinery',30,180)):
                    old=(base+p['buildings'][key]*per)*energy['factor']*speed*rules['production_multipliers'][resource]
                    self.assertAlmostEqual(self.w.production(p)[resource],old/10)
                self.assertEqual(energy,self.w.energy(p))

    def test_catalog_income_matches_global_slow_multiplier(self):
        self.choose()
        rates=self.w.production(self.home); factor=self.w.energy(self.home)['factor']
        for entry in self.w._catalog(self.pid,self.home)['buildings']:
            if 'production_resource' in entry:
                expected=(entry['base_production']+entry['level']*entry['production_per_level'])*factor
                self.assertAlmostEqual(rates[entry['production_resource']],expected)

    def test_swarm_crystal_regeneration_is_180_real_hours_not_speed_scaled(self):
        for speed in (1,10,1000):
            self.w.speed=speed; self.hive['swarm_crystals']=0
            self.w._produce(180*3600)
            self.assertEqual(self.hive['swarm_crystals'],1)
        self.assertEqual(swarm.CRYSTAL_REGEN_SECONDS,180*3600)

    def test_existing_stocks_not_divided_and_post_update_income_correct(self):
        self.home['resources']=dict.fromkeys(RESOURCES,12345.0)
        rates=self.w.production(self.home)
        self.w._produce(3600)
        for key in RESOURCES:self.assertAlmostEqual(self.home['resources'][key],12345+rates[key])

    def test_production_straddling_cutover_preserves_old_time_then_new(self):
        self.w.data['economy_slow_from']=NOW+1800
        self.home['resources']=dict.fromkeys(RESOURCES,0.0)
        self.hive['swarm_crystals']=0
        rates=self.w.production(self.home)
        self.w._produce(3600,start_at=NOW)
        for key in RESOURCES:self.assertAlmostEqual(self.home['resources'][key],rates[key]*5.5)
        self.assertAlmostEqual(self.hive['swarm_crystals'],.5/18+.5/180)

    def test_saved_observations_statics_and_colonies_survive_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/'persist.sqlite3')
            w=World(path,now=NOW); pid=w.register('SavedPilot',PASSWORD)['state']['player']['id']
            home=w._owned(pid); home['defenses']={'phase_sentinel':7}
            hive=next(p for p in w.data['planets'].values() if p['owner_id']=='khar')
            w._capture_swarm_intel(pid,hive)
            snapshot=copy.deepcopy(w.data['players'][pid]['scout_intel'])
            outpost=next(p for p in w.data['planets'].values() if p['owner_type']=='empty')
            swarm.seed(outpost,NOW,hive=False)
            w.data['alien']['next_expansion_at']=NOW+10**8
            w._save(); w.close()
            w=World(path,now=NOW)
            try:
                self.assertEqual(w._owned(pid)['defenses'],{'phase_sentinel':7})
                self.assertEqual(w.data['players'][pid]['scout_intel'],snapshot)
                self.assertEqual(sum(p['owner_id']=='khar' for p in w.data['planets'].values()),7)
            finally:w.close()

    def test_existing_061_world_uses_backup_and_no_reseed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/'upgrade.sqlite3')
            w=World(path,now=NOW); pid=w.register('LegacyPilot',PASSWORD)['state']['player']['id']
            home=w._owned(pid); home['resources']=dict.fromkeys(RESOURCES,54321.0)
            home.pop('defenses',None)
            w.data.pop('recon_defense_schema'); w.data.pop('economy_slow_from')
            w.data['players'][pid].pop('scout_intel')
            for p in w.data['planets'].values():p.pop('defenses',None)
            w.data['alien']['next_expansion_at']=NOW+10**8
            w._save(); w.close()
            w=World(path,now=NOW)
            try:
                self.assertEqual(w._owned(pid)['resources'],dict.fromkeys(RESOURCES,54321.0))
                self.assertEqual(w.data['players'][pid]['scout_intel'],{})
                self.assertFalse(any(sum(p.get('defenses',{}).values()) for p in w.data['planets'].values()))
                self.assertEqual(w.data['economy_slow_from'],NOW)
            finally:w.close()


if __name__=='__main__':unittest.main()
