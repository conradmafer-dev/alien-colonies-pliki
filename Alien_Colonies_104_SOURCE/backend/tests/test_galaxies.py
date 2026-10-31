"""0.6.0 topology, migrations, navigation, pricing and asset integrity regression.
Run: python -m unittest discover -s tests -p test_galaxies.py -v
"""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from server.main import GameError, MAX_COLONIES, MAX_RESOURCE, CLIENT_VERSION_CODE
from tests.world_fixture import LocalTestWorld as World
from server.galaxies import CATALOG, separation, JUMP_BASE_FUEL, JUMP_FUEL_PER_MASS
from server.i18n import language_scope

ROOT = Path(__file__).resolve().parents[1]
NOW = 1_900_000_000.0
PASSWORD = 'galaxy-test-password'


class GalaxyTests(unittest.TestCase):
    def setUp(self):
        self.w = World(':memory:', now=NOW)
        result = self.w.register('GalacticTester', PASSWORD)
        self.pid = result['state']['player']['id']
        self.token = result['token']
        self.home = self.w._owned(self.pid)

    def tearDown(self):
        self.w.close()

    def payload(self, target='s31p1', mission='scout', ships=None):
        return {'type':'fleet','planet_id':self.home['id'], 'target_id':target,
                'mission':mission, 'ships':ships or {'scout':1}, 'cargo':{}}

    def fund(self):
        self.home['resources'] = {k: 250_000_000.0 for k in ('metal','crystal','fuel')}

    def test_six_distinct_galaxies_and_540_unique_planets(self):
        state = self.w.state(self.pid)
        self.assertEqual([g['id'] for g in state['galaxies']], [f'g{i}' for i in range(1,7)])
        self.assertEqual(len(state['galaxy']),180)
        self.assertEqual(len(self.w.data['planets']),540)
        self.assertEqual(len({g['art_key'] for g in state['galaxies']}),6)
        self.assertEqual(state['limits']['colonies'],12)
        self.assertEqual(state['limits']['resource_cap'],1_000_000_000)
        for g in state['galaxies']:
            self.assertEqual((g['systems_count'], g['planets_count']),(30,90))
        self.assertEqual([g['hives_count'] for g in state['galaxies']],[1,1,1,1,1,1])

    def test_local_route_fixture_keeps_accounts_at_home(self):
        for i in range(3):
            state = self.w.register(f'Tester_{i}', PASSWORD)['state']
            self.assertEqual(state['planet_galaxy_id'], 'g1')

    def test_local_flight_cost_is_unchanged(self):
        a=self.home;b=self.w.data['planets']['s1p2']
        seconds, fuel = self.w._flight_numbers(a,b,{'scout':1})
        dist=self.w._local_distance(a,b)
        self.assertEqual(fuel, math.ceil(1*(1+dist)*2))
        self.assertEqual(seconds, max(8,math.ceil((100+dist*130)/1.8)))

    def test_intergalactic_floor_and_mass_cost(self):
        for name,mass in [('scout',1),('colonizer',8),('cruiser',9)]:
            with self.subTest(name=name):
                _,fuel=self.w._flight_numbers(self.home,self.w.data['planets']['s31p1'],{name:1})
                self.assertEqual(fuel, JUMP_BASE_FUEL+JUMP_FUEL_PER_MASS*mass)

    def test_larger_fleet_and_more_distant_galaxy_cost_more(self):
        target=self.w.data['planets']['s31p1']
        _,small=self.w._flight_numbers(self.home,target,{'frigate':1})
        _,large=self.w._flight_numbers(self.home,target,{'frigate':100})
        time_far,far=self.w._flight_numbers(self.home,self.w.data['planets']['s151p1'],{'frigate':1})
        self.assertGreater(large,10_000_000)
        self.assertGreater(far,small*4)
        self.assertGreater(time_far,6*3600)

    def test_cross_galaxy_cost_even_for_identical_local_coordinates(self):
        a=self.w.data['planets']['s1p1'];b=self.w.data['planets']['s31p1']
        self.assertEqual(self.w._local_distance(a,b),0.1)
        self.assertGreater(self.w._distance(a,b),1_000_000)
        self.assertGreaterEqual(self.w._flight_numbers(a,b,{'scout':1})[1],1_000_000)

    def test_quote_can_show_unaffordable_trip_without_mutation(self):
        payload=self.payload();payload['allow_unaffordable']=True
        before=copy.deepcopy(self.w.data)
        quote=self.w.preview(self.pid,payload)
        self.assertFalse(quote['affordable'])
        self.assertEqual(quote['fuel_cost'],1_040_000)
        self.assertEqual(quote['shortfall']['fuel'],1_038_600)
        self.assertEqual(quote['route']['target_galaxy_name'],'Eclipse')
        self.assertTrue(quote['route']['round_trip_fuel'])
        self.assertEqual(self.w.data,before)

    def test_cannot_bypass_payment_by_faking_preview_fields(self):
        payload=self.payload();payload.update(allow_unaffordable=True,fuel_cost=0,seconds=1,affordable=True)
        before=copy.deepcopy(self.w.data)
        with self.assertRaises(GameError):self.w.action(self.pid,payload)
        self.assertEqual(before,self.w.data)

    def test_server_charges_exact_price_once_for_idempotent_command(self):
        self.fund();payload=self.payload();payload['request_id']='galaxy-idempotency-123'
        quote=self.w.preview(self.pid,payload)
        before=self.home['resources']['fuel'];ships=self.home['ships']['scout']
        first=self.w.action(self.pid,payload)
        self.w.action(self.pid,payload)
        self.assertEqual(self.home['resources']['fuel'],before-quote['fuel_cost'])
        self.assertEqual(self.home['ships']['scout'],ships-1)
        self.assertEqual(len(first['state']['fleets']),1)

    def test_roundtrip_never_takes_another_jump_payment(self):
        self.fund();payload=self.payload()
        self.w.action(self.pid,payload)
        f=next(f for f in self.w.data['fleets'].values() if f['owner_id']==self.pid)
        fuel=self.home['resources']['fuel'];flight_seconds=f['seconds']
        self.w.now=f['arrives_at'];self.w._complete_fleet(f)
        self.assertEqual(f['status'],'returning')
        self.assertEqual(f['arrives_at'],self.w.now+flight_seconds)
        self.assertEqual(self.home['resources']['fuel'],fuel)
        self.w.now=f['arrives_at'];self.w._complete_fleet(f)
        self.assertEqual(self.home['resources']['fuel'],fuel)
        self.assertEqual(self.home['ships']['scout'],2)

    def test_cross_galaxy_colony_and_transport(self):
        self.fund();target='s31p1'
        self.w.action(self.pid,self.payload(target,'colonize',{'colonizer':1}))
        f=next(f for f in self.w.data['fleets'].values() if f['owner_id']==self.pid)
        self.w.now=f['arrives_at'];self.w._complete_fleet(f)
        colony=self.w.data['planets'][target]
        self.assertEqual(colony['owner_id'],self.pid)
        self.assertEqual(colony['galaxy_id'],'g2')
        mission=self.payload(target,'transport',{'cargo':1});mission['cargo']={'metal':1000}
        self.w.action(self.pid,mission)
        f=next(f for f in self.w.data['fleets'].values() if f['owner_id']==self.pid and f['mission']=='transport')
        before=colony['resources']['metal']
        self.w.now=f['arrives_at'];self.w._complete_fleet(f)
        self.assertEqual(colony['resources']['metal'],before+1000)
        self.assertEqual(f['status'],'returning')

    def test_remote_hive_has_real_attack_quote(self):
        self.fund();target='s45p2'
        quote=self.w.preview(self.pid,self.payload(target,'attack',{'frigate':1}))
        self.assertEqual(quote['fuel_cost'],1_120_000)
        self.assertTrue(quote['route']['intergalactic'])

    def test_navigation_uses_ids_not_array_position(self):
        target=self.w.data['planets']['s31p1']
        expected=self.w._flight_numbers(self.home,target,{'scout':1})
        self.w.data['systems'].reverse()
        self.assertEqual(self.w._flight_numbers(self.home,target,{'scout':1}),expected)

    def test_npc_does_not_raid_across_the_universe(self):
        self.home['resources']={k:100000.0 for k in ('metal','crystal','fuel')}
        self.w.data['players'][self.pid]['protected_until']=0
        origin=self.w.data['planets']['s45p2']
        from server import swarm
        self.assertEqual(self.w._swarm_raid_score(origin,self.home,swarm.RAID_PARTY),0)

    def test_all_five_localizations_have_galaxy_descriptions(self):
        for locale in ('en','pl','de','es','fr'):
            with self.subTest(locale=locale), language_scope(locale):
                view=self.w.state(self.pid)
                self.assertTrue(all(g['description'] for g in view['galaxies']))
                if locale!='pl':
                    for g,entry in zip(view['galaxies'],CATALOG):
                        self.assertNotEqual(g['description'],entry['description'])


class GalaxyMigrationTests(unittest.TestCase):
    def test_old_save_accounts_session_queues_and_flights_survive_without_reseeding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'old.sqlite3'
            w=World(path,now=NOW)
            reg=w.register('OldPlayer',PASSWORD);pid=reg['state']['player']['id'];token=reg['token']
            p=w._owned(pid);p['resources']={k:5_000_000.0 for k in ('metal','crystal','fuel')}
            w.action(pid,{'type':'build','planet_id':p['id'],'key':'metal_mine'})
            w.action(pid,{'type':'fleet','planet_id':p['id'],'target_id':'s1p2','mission':'scout','ships':{'scout':1}})
            # Emulate a genuine 0.5.1 snapshot (no new systems or galaxy metadata).
            w.data['systems']=[s for s in w.data['systems'] if s['galaxy_id']=='g1']
            w.data['planets']={k:p for k,p in w.data['planets'].items() if p['galaxy_id']=='g1'}
            w.data.pop('galaxy_schema_version',None);w.data.pop('galaxies',None)
            for s in w.data['systems']:s.pop('galaxy_id',None)
            for p in w.data['planets'].values():p.pop('galaxy_id',None)
            old=copy.deepcopy(w.data)
            accounts=w.db.execute('SELECT * FROM accounts').fetchall()
            sessions=w.db.execute('SELECT * FROM sessions').fetchall()
            w._save();w.close()
            upgraded=World(path,now=NOW)
            self.assertEqual(upgraded.authenticate(token),pid)
            self.assertEqual(upgraded.db.execute('SELECT * FROM accounts').fetchall(),accounts)
            self.assertEqual(upgraded.db.execute('SELECT * FROM sessions').fetchall(),sessions)
            self.assertEqual(upgraded.data['fleets'],old['fleets'])
            for key,p in old['planets'].items():
                self.assertEqual({k:v for k,v in upgraded.data['planets'][key].items() if k!='galaxy_id'},p)
            self.assertEqual(upgraded.data['players'][pid]['home_id'],old['players'][pid]['home_id'])
            self.assertEqual(len(upgraded.data['systems']),180)
            remote=upgraded.data['planets']['s45p2']
            remote['ships']['frigate']=7;remote['swarm_crystals']=0
            upgraded._save();upgraded.close()
            again=World(path,now=NOW)
            self.assertEqual(len(again.data['systems']),180)
            self.assertEqual(again.data['planets']['s45p2']['ships']['frigate'],7)
            self.assertEqual(again.data['planets']['s45p2']['swarm_crystals'],0)
            again.close()

    def test_client_and_flat_server_use_same_version_and_catalogues(self):
        self.assertEqual((ROOT/'server/main.py').read_bytes(),(ROOT/'railway/app.py').read_bytes())
        self.assertEqual((ROOT/'server/galaxies.py').read_bytes(),(ROOT/'railway/galaxies.py').read_bytes())
        for lang in ('en','pl','de','es','fr'):
            self.assertEqual((ROOT/'localization'/f'{lang}.json').read_bytes(),(ROOT/'railway'/f'{lang}.json').read_bytes())
        self.assertIn(f'version/code={CLIENT_VERSION_CODE}',(ROOT/'export_presets.cfg').read_text())
        self.assertIn(f'const CLIENT_VERSION_CODE: int = {CLIENT_VERSION_CODE}',(ROOT/'client/scripts/main.gd').read_text())
        self.assertIn('galaxies.py',(ROOT/'railway/Dockerfile').read_text())

    def test_six_unique_graphics_present(self):
        digests=set()
        for g in CATALOG:
            path=ROOT/'client/assets/art'/(g['art_key']+'.webp')
            self.assertTrue(path.is_file(),path)
            self.assertGreater(path.stat().st_size,10000)
            digests.add(hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(len(digests),6)


if __name__=='__main__':unittest.main()
