"""Actual generation, field reservations, production and in-place world migration."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from server.main import World, GameError
from server import planetary


class PlanetaryTests(unittest.TestCase):
    def setUp(self):
        self.w = World(':memory:', now=1900000000, speed=1000)
        state = self.w.register('Planet090', 'test-password-123')['state']
        self.pid = state['player']['id']
        self.p = self.w.data['planets'][state['home_id']]
        self.p['rare_trait'] = ''  # Isolate pre-0.9.5 rules; rarity has its own tests.
        self.w.action(self.pid, {'type': 'choose_race', 'race_id': 'zetans'})
        self.p['resources'] = dict.fromkeys(('metal','crystal','fuel'), 100000000)

    def tearDown(self):
        self.w.close()

    def test_generation_has_all_counts_and_physical_orbits_and_stable_profiles(self):
        self.assertEqual({len(s['planet_ids']) for s in self.w.data['systems']}, {1,2,3,4,5})
        seen = set()
        for system in self.w.data['systems']:
            planets = [self.w.data['planets'][pid] for pid in system['planet_ids']]
            orbits = [p['environment']['orbit_au'] for p in planets]
            temperatures = [p['environment']['temperature_c'] for p in planets]
            self.assertEqual(orbits, sorted(orbits))
            self.assertEqual(temperatures, sorted(temperatures, reverse=True))
            for p in planets:
                e = p['environment']; seen.add(e['type'])
                self.assertTrue(48 <= e['fields'] <= 120)
                if e['type'] in ('volcanic','obsidian'): self.assertLess(e['orbit_au'], .5)
                if e['type'] == 'ice': self.assertGreater(e['orbit_au'], 4)
        self.assertEqual(seen, set(planetary.TYPES))
        other = World(':memory:', now=self.w.now)
        try:
            for pid,p in self.w.data['planets'].items():
                self.assertEqual(p['environment'], other.data['planets'][pid]['environment'])
        finally: other.close()

    def test_first_build_and_each_upgrade_reserve_one_field_then_commit_or_refund(self):
        self.p['buildings']['lab'] = 2
        before = planetary.fields(self.p)
        self.w.action(self.pid, {'type':'build', 'key':'observatory', 'request_id':'obs-1'})
        during = planetary.fields(self.p)
        self.assertEqual(during['used'], before['used'])
        self.assertEqual(during['reserved'], 1)
        self.assertEqual(during['free'], before['free']-1)
        self.w.advance(self.p['queue'][0]['ends_at'])
        self.assertEqual(planetary.fields(self.p)['used'], before['used']+1)
        self.w.action(self.pid, {'type':'build', 'key':'observatory'})
        qid=self.p['queue'][0]['id']
        payload={'type':'cancel_project','queue_id':qid,'request_id':'refund-once'}
        self.w.action(self.pid,payload)
        stock=copy.deepcopy(self.p['resources'])
        self.w.action(self.pid,payload)
        self.assertEqual(stock,self.p['resources'])
        self.assertEqual(planetary.fields(self.p)['reserved'],0)
        self.assertEqual(self.p['buildings']['observatory'],1)

    def test_full_planet_blocks_all_buildings_but_not_research_units_or_defenses(self):
        self.p['buildings']['lab']=2
        self.p['environment']['fields']=planetary.fields(self.p)['used']
        before=copy.deepcopy(self.p)
        for key in ('metal_mine','observatory','phase_matrix'):
            with self.assertRaises(GameError): self.w.action(self.pid,{'type':'build','key':key})
        self.assertEqual(before,self.p)
        for payload in ({'type':'research','key':'computing'},{'type':'ship','key':'scout'},{'type':'defense','key':'phase_sentinel'}):
            self.w.action(self.pid,payload)
            self.assertEqual(planetary.fields(self.p)['reserved'],0)
            self.w.advance(self.p['queue'][0]['ends_at'])
        self.assertEqual(planetary.fields(self.p)['used'],before['environment']['fields'])

    def test_racial_buildings_and_free_starting_levels_count(self):
        base=planetary.fields(self.p)['used']
        self.p['buildings']['phase_matrix']=4
        self.assertEqual(planetary.fields(self.p)['used'],base+4)
        self.w.action(self.pid,{'type':'build','key':'phase_matrix'})
        self.w.advance(self.p['queue'][0]['ends_at'])
        self.assertEqual(planetary.fields(self.p)['used'],base+5)

    def test_real_production_and_catalog_include_planet_ratios_once(self):
        self.p['buildings']['power_plant']=12
        self.p['environment']['type']='ocean'
        old=self.w.production(self.p)
        self.p['environment']['type']='rust'
        new=self.w.production(self.p)
        for key in old:
            i=planetary.RESOURCES.index(key)
            self.assertAlmostEqual(new[key]/old[key],planetary.TYPES['rust'][1][i]/planetary.TYPES['ocean'][1][i])
        entry=next(e for e in self.w._catalog(self.pid,self.p)['buildings'] if e['key']=='metal_mine')
        next_rate=next(m for m in entry['details']['metrics'] if m['key']=='colony_metal')['next']
        self.p['buildings']['metal_mine']+=1
        self.assertAlmostEqual(next_rate,self.w.production(self.p)['metal'],places=5)

    def test_colonization_keeps_physics_and_accounts_for_starting_buildings(self):
        target=next(q for q in self.w.data['planets'].values() if q['owner_type']=='empty' and q['galaxy_id']==self.p['galaxy_id'])
        env=copy.deepcopy(target['environment'])
        self.w._capture_planetary_intel(self.pid,target)
        self.w.action(self.pid,{'type':'fleet','mission':'colonize','target_id':target['id'],'ships':{'colonizer':1}})
        fleet=next(f for f in self.w.data['fleets'].values() if f['owner_id']==self.pid)
        self.w.advance(fleet['arrives_at'])
        self.assertEqual(target['environment'],env)
        self.assertEqual(planetary.fields(target)['used'],4)
        self.assertEqual(target['buildings']['observatory'],0)

    def test_account_deletion_does_not_change_planet_physics(self):
        env=copy.deepcopy(self.p['environment'])
        token=self.w.login('Planet090','test-password-123')['token']
        self.w.account_delete(token,'test-password-123','DELETE ACCOUNT')
        self.assertEqual(self.w.data['planets'][self.p['id']]['environment'],env)
        self.assertEqual(planetary.fields(self.w.data['planets'][self.p['id']])['used'],0)

    def test_migration_preserves_owned_planets_orders_and_reserves_without_offline_retroactivity(self):
        self.p['buildings']['metal_mine']=7
        self.p['environment']['fields']=120
        self.w.action(self.pid,{'type':'build','key':'power_plant'})
        before=copy.deepcopy(self.p)
        self.w.data.pop('planetary_schema')
        self.w.data.pop('observation_schema')
        self.w.data.pop('planetary_from')
        for planet in self.w.data['planets'].values(): planet.pop('environment',None)
        self.w._save()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'migration.sqlite3'
            db=sqlite3.connect(path);self.w.db.backup(db);db.close()
            restored=World(path,speed=1000,now=self.w.now)
            try:
                p=restored.data['planets'][self.p['id']]
                for key in ('id','owner_id','buildings','ships','resources','queue'):
                    self.assertEqual(p[key],before[key])
                self.assertGreaterEqual(planetary.fields(p)['total'],planetary.fields(p)['used']+1)
                self.assertTrue(list((Path(folder)/'backups').glob('*.sqlite3')))
                profiles={pid:copy.deepcopy(q['environment']) for pid,q in restored.data['planets'].items()}
                restored._ensure_planetary()
                self.assertEqual(profiles,{pid:q['environment'] for pid,q in restored.data['planets'].items()})
            finally:restored.close()

    def test_legacy_three_planet_system_preserves_colony_and_fleet_target_when_shrinking(self):
        system=next(s for s in self.w.data['systems'] if planetary.system_count(s['id'])==1 and s['id']!=self.p['system_id'] and all(self.w.data['planets'][pid]['owner_type']=='empty' for pid in s['planet_ids']))
        for slot in (2,3):
            pid=f"{system['id']}p{slot}"
            if pid not in self.w.data['planets']:
                self.w.data['planets'][pid]=self.w._planet(pid,f"Test {slot}",system['id'],slot)
                system['planet_ids'].append(pid)
        colony=self.w.data['planets'][f"{system['id']}p2"]
        colony.update(owner_id=self.pid,owner_type='player')
        target=self.w.data['planets'][f"{system['id']}p3"]
        self.w.action(self.pid,{'type':'fleet','mission':'scout','target_id':target['id'],'ships':{'scout':1}})
        deadlines=copy.deepcopy(self.w.data['fleets'])
        self.w.data.pop('planetary_schema')
        self.w._ensure_planetary()
        self.assertIn(colony['id'],system['planet_ids'])
        self.assertIn(target['id'],system['planet_ids'])
        self.assertEqual(len(system['planet_ids']),2)
        self.assertEqual(deadlines,self.w.data['fleets'])
        self.assertTrue(all(f['target_id'] in self.w.data['planets'] for f in self.w.data['fleets'].values()))

    def test_old_offline_period_uses_old_rates_before_new_environment_applies(self):
        self.p['environment']['type']='rust'
        self.p['buildings']['power_plant']=12
        self.w.data['planetary_from']=self.w.now+100
        self.w.data['alien']['next_expansion_at']=self.w.now+10000
        before=copy.deepcopy(self.p['resources'])
        rates=self.w.production(self.p)
        self.w.advance(self.w.now+200)
        for key in rates:
            expected=rates[key]*(100/planetary.multipliers(self.p)[key]+100)/3600
            self.assertAlmostEqual(self.p['resources'][key]-before[key],expected,places=5)

if __name__=='__main__':unittest.main()
