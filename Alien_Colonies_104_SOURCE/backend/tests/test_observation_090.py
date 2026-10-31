"""Privacy at the serialized boundary, sensor range, and actual scout arrivals."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from server.main import World, GameError
from server.observation import ranges

class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.w=World(':memory:',now=1900000000,speed=1000)
        s=self.w.register('Observer090','test-password-123')['state']
        self.pid=s['player']['id'];self.p=self.w.data['planets'][s['home_id']]
        self.w.action(self.pid,{'type':'choose_race','race_id':'zetans'})
        self.p['resources']=dict.fromkeys(('metal','crystal','fuel'),100000000)
        self.p['ships']['scout']=20
        self.systems=sorted([s for s in self.w.data['systems'] if s['galaxy_id']==self.p['galaxy_id']],key=lambda s:int(s['id'][1:]))
        self.index=next(i for i,s in enumerate(self.systems) if s['id']==self.p['system_id'])
    def tearDown(self):self.w.close()
    def neighbour(self,distance=1):
        return self.w.data['planets'][self.systems[(self.index+distance)%len(self.systems)]['planet_ids'][0]]
    def view(self,planet):
        return next(q for s in self.w.state(self.pid)['galaxy'] for q in s['planets'] if q['id']==planet['id'])
    def scout(self,target):
        self.w.action(self.pid,{'type':'fleet','mission':'scout','target_id':target['id'],'ships':{'scout':1}})
        f=next(f for f in self.w.data['fleets'].values() if f['owner_id']==self.pid and f['status']=='outbound')
        self.w.advance(f['arrives_at'])

    def test_http_responses_enforce_fog_and_refresh_observed_buildings(self):
        import http.client
        import threading
        from server.main import build_server
        server=build_server(self.w,'127.0.0.1',0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        token=self.w.login('Observer090','test-password-123')['token']
        def get():
            conn=http.client.HTTPConnection('127.0.0.1',server.server_address[1],timeout=5)
            try:
                conn.request('GET','/api/state',headers={'Authorization':'Bearer '+token,'Accept-Language':'en'})
                response=conn.getresponse();self.assertEqual(response.status,200)
                return json.loads(response.read())['state']
            finally:conn.close()
        try:
            first=get()
            self.assertEqual(len([q for s in first['galaxy'] for q in s['planets']]),1)
            target=self.neighbour();target['buildings']['metal_mine']=9
            self.p['buildings']['observatory']=8
            observed=next(q for s in get()['galaxy'] for q in s['planets'] if q['id']==target['id'])
            self.assertEqual(next(b['level'] for b in observed['observed_buildings'] if b['key']=='metal_mine'),9)
            self.assertNotIn('resources',observed)
            self.assertNotIn('ships',observed)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3)

    def test_start_is_unknown_except_own_colony_and_does_not_leak_hidden_counters_or_targets(self):
        state=self.w.state(self.pid)
        known=[q for s in state['galaxy'] for q in s['planets']]
        self.assertEqual([q['id'] for q in known],[self.p['id']])
        self.assertEqual(sum(s['visibility']=='unknown' for s in state['galaxy']),179)
        self.assertEqual(state['alien']['colonies_count'],0)
        self.assertEqual(state['alien']['recommended_target_id'],'')
        self.assertTrue(all(g['hives_count']==0 for g in state['galaxies']))
        for s in state['galaxy']:
            if s['visibility']=='unknown':
                self.assertFalse(s['planets'])
                self.assertIn('scout_target_id',s)
                self.assertNotIn('planet_ids',s)
        guide=state['onboarding']
        for step in guide['steps']:
            if step['action'] in ('hunt','colonize'):self.assertFalse(step['target_id'])

    def test_undiscovered_target_accepts_scout_but_rejects_other_missions_before_owner_checks(self):
        target=self.neighbour()
        before=copy.deepcopy(self.p)
        for mission,ships in [('colonize',{'colonizer':1}),('attack',{'frigate':1}),('transport',{'cargo':1})]:
            with self.assertRaisesRegex(GameError,'Najpierw'):
                self.w.action(self.pid,{'type':'fleet','mission':mission,'target_id':target['id'],'ships':ships})
        self.assertEqual(before,self.p)
        preview=self.w.preview(self.pid,{'mission':'scout','target_id':target['id'],'ships':{'scout':1}})
        self.assertNotIn('buildings',json.dumps(preview))
        self.scout(target)
        self.assertTrue(self.w._known_planet(self.pid,target))

    def test_range_grows_every_other_level_and_follows_map_ring(self):
        for level in range(1,13):
            self.p['buildings']['observatory']=level
            coverage=self.w._observation_coverage(self.pid)
            self.assertEqual(sum(t>0 for t in coverage.values()),1+2*((level+1)//2))
            self.assertTrue(all(s['galaxy_id']==self.p['galaxy_id'] for s in self.w.data['systems'] if coverage.get(s['id'],0)))
        self.assertEqual(ranges(1)['range'],ranges(2)['range'])
        self.assertEqual(ranges(12)['building_range'],3)

    def test_basic_observation_updates_occupancy_but_hides_buildings_resources_and_size(self):
        target=self.neighbour();self.p['buildings']['observatory']=1
        self.assertEqual(self.view(target)['owner_type'],target['owner_type'])
        bob=self.w.register('Foreign090','test-password-123')['state']['player']['id']
        target.update(owner_id=bob,owner_type='player')
        target['buildings']['metal_mine']=9;target['resources']['metal']=7654321
        view=self.view(target)
        self.assertEqual(view['owner_id'],bob)
        self.assertEqual(view['owner_name'],'Foreign090')
        for key in ('observed_buildings','buildings','resources','ships','defenses','fields'):
            self.assertNotIn(key,view)
        self.assertNotIn('fields',view['environment'])
        self.assertIn('type',view['environment'])
        target.update(owner_id='',owner_type='empty')
        self.assertEqual(self.view(target)['owner_type'],'empty')

    def test_late_observation_shows_only_buildings_in_nearer_radius(self):
        near=self.neighbour(1);far=self.neighbour(3)
        near['buildings']['metal_mine']=7
        self.p['buildings']['observatory']=6
        self.assertNotIn('observed_buildings',self.view(near))
        self.p['buildings']['observatory']=8
        self.assertEqual(next(x['level'] for x in self.view(near)['observed_buildings'] if x['key']=='metal_mine'),7)
        near['buildings']['metal_mine']=8
        self.assertEqual(next(x['level'] for x in self.view(near)['observed_buildings'] if x['key']=='metal_mine'),8)
        self.assertNotIn('observed_buildings',self.view(far))
        self.assertNotIn('resources',self.view(near))
        self.assertNotIn('ships',self.view(near))

    def test_other_galaxy_stays_unknown_until_local_station_or_scout(self):
        self.p['buildings']['observatory']=12
        foreign=next(q for q in self.w.data['planets'].values() if q['galaxy_id']!=self.p['galaxy_id'] and q['owner_type']=='empty')
        self.assertFalse(self.w._known_planet(self.pid,foreign))
        foreign.update(owner_id=self.pid,owner_type='player')
        foreign['buildings']['observatory']=1
        state=self.w.state(self.pid)
        observed=[s for s in state['galaxy'] if s['galaxy_id']==foreign['galaxy_id'] and s['visibility']=='observed']
        self.assertEqual(len(observed),3)
        untouched=[s for s in state['galaxy'] if s['galaxy_id'] not in (foreign['galaxy_id'],self.p['galaxy_id'])]
        self.assertTrue(all(s['visibility']=='unknown' for s in untouched))

    def test_scout_reveals_system_and_freezes_detail_without_live_updates(self):
        target=self.neighbour();target['buildings']['metal_mine']=3
        self.scout(target)
        before=self.view(target)
        snapshot=copy.deepcopy(before['planet_scout'])
        system=next(s for s in self.w.state(self.pid)['galaxy'] if s['id']==target['system_id'])
        self.assertEqual(len(system['planets']),len(self.systems[(self.index+1)%30]['planet_ids']))
        target.update(owner_id='khar',owner_type='alien')
        target['buildings']['metal_mine']=10;target['resources']['metal']=9999999
        after=self.view(target)
        self.assertEqual(after['owner_id'],before['owner_id'])
        self.assertEqual(after['planet_scout'],snapshot)
        self.assertNotIn('observed_buildings',after)
        self.assertIn('fields',after['environment'])

    def test_live_building_update_does_not_rewrite_old_report(self):
        target=self.neighbour();target['buildings']['metal_mine']=2
        self.scout(target)
        reports=copy.deepcopy(self.w.state(self.pid)['reports'])
        self.p['buildings']['observatory']=8
        target['buildings']['metal_mine']=11
        self.assertEqual(self.view(target)['building_visibility'],'live')
        self.assertEqual(self.w.state(self.pid)['reports'],reports)
        self.assertEqual(next(b['level'] for b in self.view(target)['planet_scout']['observed_buildings'] if b['key']=='metal_mine'),2)

    def test_building_completion_not_queue_start_enables_live_observation(self):
        self.p['buildings']['lab']=2
        self.w.action(self.pid,{'type':'build','key':'observatory'})
        self.assertFalse(any(self.w._observation_coverage(self.pid).values()))
        self.w.advance(self.p['queue'][0]['ends_at'])
        self.assertEqual(sum(x>0 for x in self.w._observation_coverage(self.pid).values()),3)

    def test_restart_preserves_scout_snapshot_and_live_coverage(self):
        target=self.neighbour(8);self.scout(target)
        before=copy.deepcopy(self.view(target))
        self.p['buildings']['observatory']=3
        self.w._save()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'restart.sqlite3'
            db=sqlite3.connect(path);self.w.db.backup(db);db.close()
            restored=World(path,speed=1000,now=self.w.now)
            try:
                q=next(q for s in restored.state(self.pid)['galaxy'] for q in s['planets'] if q['id']==target['id'])
                self.assertEqual(q,before)
                self.assertEqual(sum(x>0 for x in restored._observation_coverage(self.pid).values()),5)
            finally:restored.close()

if __name__=='__main__':unittest.main()
