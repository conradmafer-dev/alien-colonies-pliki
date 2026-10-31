"""Parallel paid orders, exact cancellation, event chronology and durable guide state."""
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from server.main import World, GameError, RESOURCES
from server import onboarding, planetary

NOW = 1900000000
PASSWORD = 'local-parallel-test-password'

class ParallelProjects(unittest.TestCase):
    def setUp(self):
        self.w = World(':memory:', speed=1, now=NOW)
        self.addCleanup(self.w.close)
        self.pid = self.w.register('Parallel092', PASSWORD)['state']['player']['id']
        self.w.action(self.pid, {'type':'choose_race','race_id':'zetans'})
        self.p = self.w._owned(self.pid)
        self.p['resources'] = dict.fromkeys(RESOURCES, 10000000.0)
        self.p['buildings'].update(lab=2, shipyard=2)
        self.w.data['alien']['next_expansion_at'] = NOW + 1000000

    def order(self, kind, key, **extra):
        result = self.w.action(self.pid, {'type':kind, 'key':key, **extra})
        return next(q for q in result['state']['queue'] if q['kind']==kind and q['key']==key)

    def three(self):
        # The longest task is deliberately purchased first.
        return [self.order('ship','frigate',amount=20), self.order('research','weapons'), self.order('build','metal_mine')]

    def second_colony(self):
        p=next(p for p in self.w.data['planets'].values() if p['owner_type']=='empty')
        p.update(owner_id=self.pid, owner_type='player')
        p['buildings'].update(lab=2,shipyard=2)
        p['resources']=dict.fromkeys(RESOURCES,10000000.0)
        return p

    def test_three_orders_paid_once_and_only_building_reserves_slot(self):
        before=copy.deepcopy(self.p['resources']);fields=planetary.fields(self.p)
        tasks=self.three()
        self.assertEqual(len(self.p['queue']),3)
        self.assertEqual({q['started_at'] for q in tasks},{NOW})
        for r in RESOURCES:
            self.assertEqual(self.p['resources'][r], before[r]-sum(q['paid_cost'][r] for q in tasks))
        self.assertEqual(planetary.fields(self.p)['reserved'],1)
        self.assertEqual(planetary.fields(self.p)['free'],fields['free']-1)

    def test_each_lane_blocks_only_its_own_next_order(self):
        self.order('build','metal_mine')
        cat=self.w.state(self.pid)['catalog']
        self.assertFalse(next(x for x in cat['buildings'] if x['key']=='crystal_mine')['enabled'])
        self.assertTrue(next(x for x in cat['research'] if x['key']=='weapons')['enabled'])
        self.assertTrue(next(x for x in cat['ships'] if x['key']=='scout')['enabled'])
        self.order('research','weapons');self.order('ship','scout')
        before=copy.deepcopy(self.w.data)
        for kind,key in [('build','power_plant'),('ship','frigate'),('defense','phase_sentinel'),('research','computing')]:
            with self.subTest(kind=kind), self.assertRaises(GameError):self.order(kind,key)
        self.assertEqual(self.w.data,before)

    def test_defense_shares_shipyard_but_allows_building_and_research(self):
        self.order('defense','phase_sentinel')
        self.order('build','metal_mine');self.order('research','weapons')
        with self.assertRaises(GameError):self.order('ship','scout')
        self.assertEqual(len(self.p['queue']),3)

    def test_other_colony_can_build_and_produce_but_not_duplicate_research(self):
        self.three();second=self.second_colony()
        self.order('build','metal_mine',planet_id=second['id'])
        self.order('ship','scout',planet_id=second['id'])
        with self.assertRaises(GameError):self.order('research','weapons',planet_id=second['id'])
        state=self.w.state(self.pid,second['id'])
        self.assertEqual(state['research_queue']['planet_id'],self.p['id'])
        self.assertEqual(state['research_queue']['kind'],'research')
        other=self.w.register('Other092',PASSWORD)['state']['player']['id']
        self.assertIsNone(self.w.state(other)['research_queue'])

    def test_shorter_jobs_finish_before_first_purchased_ship_batch(self):
        tasks=self.three();before=copy.deepcopy(self.p)
        research_before=self.w._player(self.pid)['research']['weapons']
        first=min(q['ends_at'] for q in tasks)
        self.assertLess(first,tasks[0]['ends_at'])
        self.w.advance(first)
        for task in tasks:
            self.assertEqual(any(q['id']==task['id'] for q in self.p['queue']),task['ends_at']>first)
        self.w.advance(max(q['ends_at'] for q in tasks))
        self.assertFalse(self.p['queue'])
        self.assertEqual(self.p['ships']['frigate'],before['ships']['frigate']+20)
        self.assertEqual(self.p['buildings']['metal_mine'],before['buildings']['metal_mine']+1)
        self.assertEqual(self.w._player(self.pid)['research']['weapons'],research_before+1)
        after=(copy.deepcopy(self.p['buildings']),copy.deepcopy(self.p['ships']))
        self.w.advance(self.w.now)
        self.assertEqual((self.p['buildings'],self.p['ships']),after)

    def test_same_deadline_and_offline_production_use_each_completion_once(self):
        self.three()
        old_rate=self.w.production(self.p)['metal'];stock=self.p['resources']['metal']
        for q in self.p['queue']:q.update(ends_at=NOW+10,seconds=10)
        self.w.advance(NOW+30)
        new_rate=self.w.production(self.p)['metal']
        self.assertAlmostEqual(self.p['resources']['metal'],stock+old_rate*10/3600+new_rate*20/3600,places=6)
        self.assertEqual(len(self.p['queue']),0)
        self.assertEqual(planetary.fields(self.p)['reserved'],0)

    def test_cancel_middle_refunds_exact_cost_without_touching_other_lanes(self):
        tasks=self.three();remaining=[copy.deepcopy(tasks[0]),copy.deepcopy(tasks[2])]
        stock=copy.deepcopy(self.p['resources'])
        payload={'type':'cancel_project','queue_id':tasks[1]['id'],'request_id':'cancel-middle'}
        self.w.action(self.pid,payload)
        self.assertEqual(self.p['queue'],remaining)
        self.assertEqual(self.p['resources'],{r:stock[r]+tasks[1]['paid_cost'][r] for r in RESOURCES})
        after=copy.deepcopy(self.w.data)
        self.w.action(self.pid,payload)
        self.assertEqual(self.w.data,after)
        self.assertEqual(planetary.fields(self.p)['reserved'],1)
        self.assertIsNone(self.w.state(self.pid)['research_queue'])

    def test_cancel_build_releases_field_keeps_research_and_fleet(self):
        tasks=self.three()
        self.w.action(self.pid,{'type':'cancel_project','queue_id':tasks[2]['id']})
        self.assertEqual(self.p['queue'],tasks[:2]);self.assertEqual(planetary.fields(self.p)['reserved'],0)
        self.order('build','crystal_mine')
        self.assertEqual(len(self.p['queue']),3)

    def test_wrong_colony_or_foreign_queue_id_cannot_cancel_or_refund(self):
        tasks=self.three();second=self.second_colony();before=copy.deepcopy(self.w.data)
        with self.assertRaises(GameError):self.w.action(self.pid,{'type':'cancel_project','planet_id':second['id'],'queue_id':tasks[1]['id']})
        self.assertEqual(self.w.data,before)
        other=self.w.register('Unauthorized092',PASSWORD)['state']['player']['id']
        with self.assertRaises(GameError):self.w.action(other,{'type':'cancel_project','planet_id':self.p['id'],'queue_id':tasks[0]['id']})

    def test_parallel_duplicate_requests_cannot_buy_two_orders_in_same_lane(self):
        def submit(i):
            try:return self.order('ship','scout',request_id='racing-'+str(i))
            except GameError:return None
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(submit,range(4)))
        self.assertEqual(sum(x is not None for x in results),1)
        self.assertEqual(len(self.p['queue']),1)
        self.order('build','metal_mine');self.order('research','weapons')
        self.assertEqual(len(self.p['queue']),3)

    def test_unaffordable_other_lane_does_not_change_paid_queue(self):
        self.order('build','metal_mine');self.p['resources']=dict.fromkeys(RESOURCES,0.0)
        before=copy.deepcopy(self.w.data)
        with self.assertRaises(GameError):self.order('ship','scout')
        self.assertEqual(self.w.data,before)

    def test_single_legacy_queue_and_parallel_tasks_survive_restart(self):
        for legacy in (True,False):
            with self.subTest(legacy=legacy),tempfile.TemporaryDirectory() as d:
                data=copy.deepcopy(self.w.data)
                tasks=self.three()
                if legacy:
                    self.p['queue']=self.p['queue'][:1]
                    for k in ('seconds','started_at','paid_cost'):self.p['queue'][0].pop(k,None)
                queued=copy.deepcopy(self.p['queue'])
                path=Path(d)/'world.sqlite3'
                other=World(path,now=NOW)
                other.data=copy.deepcopy(self.w.data);other._save();other.close()
                restored=World(path,now=NOW)
                try:
                    self.assertEqual(restored._owned(self.pid)['queue'],queued)
                    restored.advance(max(q['ends_at'] for q in queued))
                    self.assertEqual(restored._owned(self.pid)['queue'],[])
                finally:restored.close()
                self.w.data=data;self.p=self.w._owned(self.pid)

class SkippableGuide(unittest.TestCase):
    def test_skip_survives_events_restart_and_resume_without_forging_progress(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'world.sqlite3';w=World(path,now=NOW)
            pid=w.register('Guide092',PASSWORD)['state']['player']['id']
            w.action(pid,{'type':'choose_race','race_id':'symbionts'})
            before=copy.deepcopy(w.data)
            payload={'type':'skip_onboarding','request_id':'skip-1'}
            state=w.action(pid,payload)['state']
            self.assertTrue(state['onboarding']['skipped']);self.assertIsNone(state['onboarding']['current'])
            self.assertFalse(state['onboarding']['finished']);self.assertEqual(state['onboarding']['completed_count'],0)
            w.action(pid,payload)
            self.assertEqual(before['planets'],w.data['planets'])
            onboarding.record(w._player(pid),'first_building')
            w._save();w.close();w=World(path,now=NOW)
            try:
                guide=w.state(pid)['onboarding']
                self.assertTrue(guide['skipped']);self.assertIsNone(guide['current'])
                state=w.action(pid,{'type':'resume_onboarding'})['state']
                self.assertFalse(state['onboarding']['skipped'])
                self.assertEqual(state['onboarding']['completed_count'],1)
                self.assertEqual(state['onboarding']['current']['id'],'second_colony')
            finally:w.close()

if __name__=='__main__':unittest.main()
