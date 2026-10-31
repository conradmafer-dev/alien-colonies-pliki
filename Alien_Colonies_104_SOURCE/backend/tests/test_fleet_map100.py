"""Flights are observed from the actual flat runtime; presentation cannot change orders."""
import copy, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World
from i18n import language_scope
import report_kinds

NOW=1900000000.0
class FleetMap100Tests(unittest.TestCase):
 def setUp(self):
  self.w=World(':memory:',now=NOW)
  s=self.w.register('Motion100','fixture-password-123',_google_verified=True)['state']
  self.pid=s['player']['id'];self.w.action(self.pid,{'type':'choose_race','race_id':'zetans'})
  self.p=self.w._owned(self.pid);self.p['ships']['scout']=8
  self.p['resources']=dict.fromkeys(('metal','crystal','fuel'),1000000.)
  system=next(s for s in self.w.data['systems'] if s['galaxy_id']==self.p['galaxy_id'] and s['ring_index']==2)
  self.target=self.w.data['planets'][system['planet_ids'][0]]
  if self.target['system_id']==self.p['system_id']:
   self.target=next(p for p in self.w.data['planets'].values() if p['galaxy_id']==self.p['galaxy_id'] and p['system_id']!=self.p['system_id'])
 def tearDown(self):self.w.close()
 def dispatch(self):
  payload={'type':'fleet','mission':'scout','planet_id':self.p['id'],'target_id':self.target['id'],'ships':{'scout':1}}
  quote=self.w.preview(self.pid,payload);self.w.action(self.pid,payload)
  f=next(f for f in self.w.data['fleets'].values() if f['owner_id']==self.pid)
  return f,quote
 def test_dispatched_snapshot_includes_real_endpoints_timing_and_paid_route(self):
  f,q=self.dispatch();before=copy.deepcopy(f);fuel=self.p['resources']['fuel']
  public=next(f for f in self.w.state(self.pid)['fleets'] if f['id']==before['id'])
  self.assertEqual(public['started_at'],NOW);self.assertEqual(public['arrives_at'],NOW+q['seconds'])
  self.assertEqual(public['origin_system_id'],self.p['system_id']);self.assertEqual(public['target_system_id'],self.target['system_id'])
  self.assertEqual(public['route'],q['route']);self.assertEqual(f,before);self.assertEqual(self.p['resources']['fuel'],fuel)
  public['route']['system_ids'].clear();self.assertEqual(f,before)
 def test_return_clock_and_original_route_survive_public_read(self):
  f,_=self.dispatch();route=copy.deepcopy(f['route']);self.w.now+=f['seconds'];self.w._return(f)
  view=next(x for x in self.w.state(self.pid)['fleets'] if x['id']==f['id'])
  self.assertEqual(view['status'],'returning');self.assertEqual(view['started_at'],self.w.now)
  self.assertEqual(view['arrives_at']-view['started_at'],f['seconds']);self.assertEqual(view['route'],route)
 def test_early_recall_preserves_turnaround_fraction_without_changing_existing_return_rule(self):
  f,q=self.dispatch();route=copy.deepcopy(f['route']);f['return_seconds']=f['seconds']
  elapsed=f['seconds']/4;self.w.now+=elapsed
  self.w._operation_return(f,early=True)
  self.assertEqual(f['status'],'returning');self.assertAlmostEqual(f['map_return_fraction'],.25)
  self.assertEqual(f['seconds'],max(1,elapsed));self.assertEqual(f['route'],route)
  view=next(x for x in self.w.state(self.pid)['fleets'] if x['id']==f['id'])
  self.assertAlmostEqual(view['map_return_fraction'],.25)
 def test_legacy_flight_does_not_claim_new_corridor_route_or_timing(self):
  f,_=self.dispatch();f.pop('route');f.pop('started_at');timing=f['arrives_at'],f['seconds']
  view=next(x for x in self.w.state(self.pid)['fleets'] if x['id']==f['id'])
  self.assertNotIn('segments',view['route']);self.assertNotIn('system_ids',view['route'])
  self.assertEqual(view['started_at'],timing[0]-timing[1]);self.assertEqual((view['arrives_at'],view['seconds']),timing)
 def test_unrelated_empire_cannot_observe_another_players_flight(self):
  f,_=self.dispatch()
  other=self.w.register('Other100','fixture-password-123',_google_verified=True)['state']['player']['id']
  state=self.w.state(other)
  self.assertNotIn(f['id'],[x['id'] for x in state['fleets']])
  self.assertNotIn(f['id'],[x['id'] for x in state['incoming_attacks']])
 def test_localized_legacy_reports_have_stable_kinds_and_remain_immutable(self):
  for title,expected in [('Raport zwiadu','scout'),('Raport bitwy','battle'),('Nadciąga wroga flota','warning'),('Dostarczono transport','transport'),('Flota wróciła','return'),('Nowa kolonia','colonization')]:
   report={'id':'rtest','at':NOW,'title':title,'text':'User Empire 123','art_key':''};before=copy.deepcopy(report)
   for lang in ['en','pl','de','es','fr']:
    with language_scope(lang):view=self.w._public_intel_report(report)
    self.assertEqual(view['kind'],expected);self.assertEqual(report,before);self.assertEqual(view['text'],'User Empire 123')
 def test_each_project_lane_gets_its_own_category(self):
  for lane,kind in report_kinds.PROJECT_KINDS.items():
   self.w._report(self.pid,'Ukończono projekt','Fixture',report_kind=kind)
   self.assertEqual(self.w.state(self.pid)['reports'][0]['kind'],kind)
 def test_battle_and_scout_snapshots_classify_old_custom_titles(self):
  self.assertEqual(report_kinds.kind({'title':'User colony name','battle_replay':{'seed':1}}),'battle')
  self.assertEqual(report_kinds.kind({'title':'User colony name','system_snapshot':{'system_id':'s1'}}),'scout')
if __name__=='__main__':unittest.main()

