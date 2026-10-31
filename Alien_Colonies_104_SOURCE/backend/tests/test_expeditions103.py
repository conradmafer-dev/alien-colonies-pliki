"""Real World dispatch, combat, landing, recall and SQLite restart regression."""
import copy,json,sys,tempfile,unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import World,GameError
import expeditions
from i18n import language_scope
NOW=1900000000.
class ExpeditionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=str(Path(self.tmp.name)/'world.sqlite3')
  self.w=World(self.path,now=NOW);s=self.w.register('Exp103','fixture-password-103',_google_verified=True)['state']
  self.pid=s['player']['id'];self.w.action(self.pid,{'type':'choose_race','race_id':'zetans'})
  self.p=self.w._owned(self.pid);self.p['buildings'].update(expedition_base=1,shipyard=3,lab=4)
  self.p['ships'].update(scout=20,cargo=20,frigate=100,cruiser=100)
  self.p['resources']=dict.fromkeys(expeditions.RESOURCES,1000000.)
  self.player=self.w._player(self.pid);self.w.data['alien']['next_action']=NOW+1000000
 def tearDown(self):self.w.close();self.tmp.cleanup()
 def payload(self,**extra):return {'type':'fleet','mission':'expedition','planet_id':self.p['id'],'target_id':'expedition:'+self.p['system_id'],'ships':{'scout':1,'cargo':1},'expedition_hours':1,**extra}
 def send(self,event='resources',**extra):
  self.w.action(self.pid,self.payload(**extra));f=[f for f in self.w.data['fleets'].values() if f['owner_id']==self.pid][-1];f['expedition']['outcome']=event;return f
 def step(self,f):self.w.now=f['arrives_at'];self.w._complete_fleet(f)
 def recall(self,f,rid='recall103'):return self.w.action(self.pid,{'type':'recall_expedition','planet_id':self.p['id'],'fleet_id':f['id'],'request_id':rid})
 def test_profiles_and_outcomes(self):
  self.assertEqual([expeditions.profile(x)['slots'] for x in [0,1,5,6,10,11]],[0,1,1,2,2,3])
  self.assertEqual([expeditions.profile(x)['reward_bonus_percent'] for x in [1,5,6,10,11]],[0,20,25,45,50])
  self.assertEqual(Counter(expeditions.outcome(i) for i in range(100)),dict(resources=50,ships=10,empty=20,patrol=10,delay=10))
 def test_quote_formula_read_only_real_hours(self):
  self.p['buildings']['expedition_base']=5;before=copy.deepcopy(self.w.data)
  with patch.object(self.w,'production',return_value=dict(metal=1000,crystal=600,fuel=300)):q=self.w.preview(self.pid,self.payload(expedition_hours=3))
  self.assertEqual(self.w.data,before);self.assertEqual(q['expedition']['reward_budget'],dict(metal=1800,crystal=1080,fuel=540))
  self.assertEqual(q['round_trip_seconds'],q['seconds']*2+10800);self.assertEqual(q['return_at'],NOW+q['round_trip_seconds'])
  self.w.speed=100;self.assertEqual(self.w.preview(self.pid,self.payload(expedition_hours=6))['expedition']['search_seconds'],21600)
 def test_catalog_all_races_and_requirements(self):
  for race in ['zetans','automatons','symbionts']:
   self.player['race_id']=race;self.w._ensure_race_buildings(self.p)
   item=next(x for x in self.w._catalog(self.pid,self.p)['buildings'] if x['key']==expeditions.KEY)
   self.assertEqual({r['key']:r['level'] for r in item['requirements']},{'shipyard':3,'lab':4})
   self.assertEqual(item['art_key'],expeditions.ART)
  self.assertNotIn(expeditions.KEY,self.w._specs('khar','buildings'))
 def test_rejects_bad_duration_target_cargo_ships_without_mutation(self):
  for bad in [{'expedition_hours':2},{'expedition_hours':True},{'expedition_hours':'3'},{'expedition_hours':1.5},{'target_id':self.p['id']},{'travel_mode':'tunnel'},{'scout_scope':'system'},{'ships':{'cargo':1}},{'ships':{'scout':1000}},{'cargo':{'metal':1}}]:
   before=copy.deepcopy(self.w.data)
   with self.assertRaises(GameError):self.w.action(self.pid,self.payload(**bad))
   self.assertEqual(self.w.data,before)
  self.p['buildings'][expeditions.KEY]=0
  with self.assertRaises(GameError):self.w.preview(self.pid,self.payload())
  self.p['buildings'][expeditions.KEY]=1;self.p['resources']['fuel']=0
  self.assertFalse(self.w.preview(self.pid,self.payload(allow_unaffordable=True))['affordable'])
  with self.assertRaises(GameError):self.w.action(self.pid,self.payload())
 def test_highest_base_sets_global_slots_and_return_keeps_slot(self):
  q=copy.deepcopy(self.p);q['id']='test-colony';q['buildings'][expeditions.KEY]=6;self.w.data['planets'][q['id']]=q
  self.assertEqual(self.w._expedition_state(self.pid,self.p)['max_active'],2)
  f=self.send();self.send('empty')
  with self.assertRaises(GameError):self.w.preview(self.pid,self.payload())
  self.recall(f)
  with self.assertRaises(GameError):self.w.preview(self.pid,self.payload())
  self.step(f);self.w.preview(self.pid,self.payload())
 def test_regular_eight_missions_are_separate(self):
  for i in range(8):self.w.data['fleets']['old'+str(i)]={'id':'old'+str(i),'owner_id':self.pid,'mission':'scout','status':'outbound','origin_id':self.p['id'],'target_id':self.p['id'],'ships':{'scout':1},'cargo':dict.fromkeys(expeditions.RESOURCES,0),'arrives_at':NOW+9999,'seconds':9999}
  self.w.preview(self.pid,self.payload())
 def test_hidden_roll_and_other_empire_cannot_recall(self):
  f=self.send();view=next(x for x in self.w.state(self.pid)['fleets'] if x['id']==f['id'])
  self.assertEqual(view['target_id'],self.payload()['target_id']);self.assertTrue(view['can_recall'])
  for k in ['seed','outcome','allowed_ships','reward_budget','production_snapshot']:self.assertNotIn(k,json.dumps(view))
  other=self.w.register('OtherExp103','fixture-password-103',_google_verified=True)['state']['player']['id']
  self.assertNotIn(f['id'],[x['id'] for x in self.w.state(other)['fleets']])
  with self.assertRaises(GameError):self.w.action(other,{'type':'recall_expedition','fleet_id':f['id']})
 def test_phases_frozen_reward_and_landing_exactly_once(self):
  with patch.object(self.w,'production',return_value=dict(metal=1000,crystal=600,fuel=300)):f=self.send(expedition_hours=3)
  before=copy.deepcopy(self.p);self.step(f);self.assertEqual(f['status'],'exploring');self.assertEqual(f['seconds'],10800)
  self.p['buildings'][expeditions.KEY]=11;self.step(f)
  self.assertEqual(f['cargo'],dict(metal=1500,crystal=900,fuel=450));self.assertEqual(f['status'],'returning');self.assertEqual(self.p['resources'],before['resources'])
  cargo=dict(f['cargo']);self.step(f)
  for k,v in cargo.items():self.assertEqual(self.p['resources'][k],before['resources'][k]+v)
  before=copy.deepcopy(self.p);self.w._complete_fleet(f);self.assertEqual(self.p,before)
 def test_capacity_truncates_proportionally(self):
  self.assertEqual(expeditions.load_resources(dict(metal=1800,crystal=1080,fuel=540),19),dict(metal=10,crystal=6,fuel=3))
  for cap in [0,1,2,7,10000]:self.assertEqual(sum(expeditions.load_resources(dict(metal=9,crystal=3,fuel=1),cap).values()),min(cap,13))
  f=self.send(ships={'scout':1});f['expedition']['reward_budget']=dict.fromkeys(expeditions.RESOURCES,999999)
  self.step(f);self.step(f);self.assertLessEqual(sum(f['cargo'].values()),self.w.expedition_capacity(self.w._specs(self.pid,'ships'),f['ships']))
 def test_delay_is_one_half_search_then_empty(self):
  f=self.send('delay');leg=f['seconds'];self.step(f);self.step(f)
  self.assertTrue(f['expedition']['delayed']);self.assertEqual(f['seconds'],1800)
  self.step(f);self.assertEqual(f['status'],'returning');self.assertEqual(f['seconds'],leg);self.assertEqual(sum(f['cargo'].values()),0)
 def test_recall_outbound_or_search_no_loot_no_fuel_refund_idempotent(self):
  for searching in [False,True]:
   f=self.send('patrol');leg=f['seconds']
   if searching:self.step(f)
   self.w.now+=leg/4;fuel=self.p['resources']['fuel'];rid='recall'+str(searching)
   self.recall(f,rid);deadline=f['arrives_at'];self.assertEqual(f['seconds'],leg if searching else leg/4)
   self.assertEqual(sum(f['cargo'].values()),0);self.assertEqual(self.p['resources']['fuel'],fuel)
   self.recall(f,rid);self.assertEqual(f['arrives_at'],deadline)
   with self.assertRaises(GameError):self.recall(f,'new'+rid)
   self.step(f)
 def test_ship_finds_respect_unlocks_race_and_budget(self):
  f=self.send('ships');f['expedition']['reward_budget']=dict(metal=5000,crystal=3000,fuel=0);initial=dict(f['ships']);allowed=set(f['expedition']['allowed_ships'])
  self.step(f);self.step(f);found={k:v-initial.get(k,0) for k,v in f['ships'].items() if v>initial.get(k,0)}
  self.assertTrue(found);self.assertLessEqual(set(found),allowed);self.assertNotIn('titan',found);self.assertLessEqual(sum(found.values()),10)
  specs=self.w._specs(self.pid,'ships');value=sum(sum(self.w._unit_construction_cost(self.pid,k,specs[k]).values())*n for k,n in found.items());self.assertLessEqual(value,8000)
 def test_patrol_crystal_is_a_chance_only_on_victory_and_landing(self):
  for win_crystal in [True,False]:
   f=self.send('patrol',ships={'scout':1,'cargo':1,'cruiser':100})
   f['expedition']['seed']=next(str(n) for n in range(100) if (expeditions.roll(str(n),'crystal',100)<25)==win_crystal)
   wallet=self.player.get('swarm_crystals',0);self.step(f);self.step(f)
   self.assertEqual(f['status'],'returning');self.assertEqual(f.get('swarm_crystals',0),int(win_crystal));self.assertEqual(self.player.get('swarm_crystals',0),wallet)
   report=next(x for x in self.player['reports'] if x.get('kind')=='expedition');self.assertEqual(report['battle_replay']['outcome'],'attacker_wins');self.assertTrue(report['battle_replay']['rounds'])
   self.step(f);self.assertEqual(self.player.get('swarm_crystals',0),wallet+int(win_crystal));self.w._complete_fleet(f);self.assertEqual(self.player.get('swarm_crystals',0),wallet+int(win_crystal))
 def test_patrol_loss_grants_no_loot_or_nest_bonus(self):
  nests={k:p.get('swarm_crystals') for k,p in self.w.data['planets'].items() if p['owner_id']=='khar'}
  f=self.send('patrol',ships={'scout':1});self.step(f);self.step(f)
  self.assertNotIn(f['id'],self.w.data['fleets']);self.assertEqual(f.get('swarm_crystals',0),0)
  self.assertEqual(nests,{k:p.get('swarm_crystals') for k,p in self.w.data['planets'].items() if p['owner_id']=='khar'})
 def test_sqlite_restart_offline_completion_does_not_reroll(self):
  f=self.send(expedition_hours=3);data=copy.deepcopy(f['expedition']);target=NOW+data['round_trip_seconds']+1
  self.w.close();self.w=World(self.path,now=NOW);self.assertEqual(self.w.data['fleets'][f['id']]['expedition'],data)
  self.w.advance(target);self.assertNotIn(f['id'],self.w.data['fleets'])
  self.assertEqual(len([x for x in self.w._player(self.pid)['reports'] if x.get('kind')=='expedition']),1)
  self.w.advance(target+100);self.assertEqual(len([x for x in self.w._player(self.pid)['reports'] if x.get('kind')=='expedition']),1)
 def test_recalled_state_persists(self):
  f=self.send('ships');self.w.now+=10;self.recall(f);self.w.close();self.w=World(self.path,now=NOW+10)
  self.assertEqual(self.w.data['fleets'][f['id']]['status'],'returning');self.w.advance(NOW+25);self.assertNotIn(f['id'],self.w.data['fleets'])
 def test_five_languages(self):
  for lang in ['pl','en','de','es','fr']:
   with language_scope(lang):
    item=next(x for x in self.w._catalog(self.pid,self.p)['buildings'] if x['key']==expeditions.KEY)
    self.assertTrue(item['name']);self.assertTrue(item['description'])
    if lang!='pl':self.assertNotEqual(item['name'],'Baza ekspedycyjna')

if __name__=='__main__':unittest.main()
