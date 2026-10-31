"""Real local facility bonuses: timers, previews, persistence and Khar parity."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from server import production_timing, swarm
from server.main import World, RESOURCES, ECONOMY_MULTIPLIER, GameError
from server.races import RACES, UNIQUE_RESEARCH

ROOT = Path(__file__).resolve().parents[1]


class FacilityTimingRules(unittest.TestCase):
    def test_level_one_preserves_old_starting_pace(self):
        for level in (0, 1):
            for group in ('ships', 'defenses', 'research'):
                p = production_timing.facility_profile({'shipyard': level, 'lab': level}, group)
                self.assertEqual(p['speed_multiplier'], 1)
                self.assertEqual(p['speed_bonus_percent'], 0)
                self.assertEqual(p['time_reduction_percent'], 0)

    def test_bonus_adds_ten_points_per_extra_level_not_exponential(self):
        for level, bonus, factor in [(1, 0, 1), (2, 10, 1.1), (5, 40, 1.4), (12, 110, 2.1), (20, 190, 2.9)]:
            for group in ('ships','defenses','research'):
                p = production_timing.facility_profile({'shipyard': level, 'lab': level}, group)
                self.assertEqual(p['speed_bonus_percent'], bonus)
                self.assertAlmostEqual(p['speed_multiplier'], factor)
                self.assertAlmostEqual(p['time_reduction_percent'], (1 - 1/factor)*100, places=5)
                seconds = production_timing.project_seconds(3600, 0, group, {'shipyard':level,'lab':level}, 1)
                self.assertEqual(seconds, math.ceil(3600/factor))

    def test_facility_levels_never_speed_up_buildings(self):
        for level in (1,5,12,20):
            self.assertEqual(production_timing.project_seconds(240, 3, 'buildings', {'shipyard':level,'lab':level}, 1), math.ceil(240*1.3**3))

    def test_extreme_bad_or_legacy_level_data_cannot_create_unbounded_bonus(self):
        for value in (True, None, '12', 3.5, -2):
            self.assertEqual(production_timing.facility_profile({'shipyard':value},'ships')['speed_multiplier'],1)
        self.assertAlmostEqual(production_timing.facility_profile({'shipyard':1000000},'ships')['speed_multiplier'],2.9)
        for speed in (0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                production_timing.project_seconds(240,0,'ships',{'shipyard':5},speed)

    def test_seconds_never_drop_below_one_and_are_whole(self):
        for group in ('ships','defenses','research','buildings'):
            seconds=production_timing.project_seconds(.01,0,group,{'shipyard':20,'lab':20},100)
            self.assertEqual(seconds,1)
            self.assertIsInstance(seconds,int)


class RealFacilityOrders(unittest.TestCase):
    def setUp(self):
        self.w=World(':memory:',now=2_000_000_000,speed=1)
        self.addCleanup(self.w.close)
        self.owner=self.w.register('Speed076','Test-password-076!')['state']['player']['id']
        self.w.action(self.owner,{'type':'choose_race','race_id':'zetans'})
        self.p=self.w._owned(self.owner)
        self.p['rare_trait'] = ''  # Isolate pre-0.9.5 rules; rarity has its own tests.
        self.fund()

    def fund(self):
        self.p['resources']={k:100000000 for k in RESOURCES}

    def race(self,race):
        player=self.w._player(self.owner)
        player['race_id']=race
        player['skill_nodes']=[]
        self.w._ensure_race_buildings(self.p)
        self.w._ensure_racial_research(player)
        self.p['queue']=[]
        self.p['buildings'].update(shipyard=1,lab=1)
        self.fund()

    def entry(self,group,key,p=None):
        return next(x for x in self.w._catalog(self.owner,p or self.p)[group] if x['key']==key)

    def test_shipyard_changes_actual_ship_and_defense_orders_for_every_race(self):
        for race in RACES:
            self.race(race)
            defense=next(iter(self.w._specs(self.owner,'defenses')))
            for group,key,kind in [('ships','scout','ship'),('defenses',defense,'defense')]:
                self.p['queue']=[];self.p['buildings']['shipyard']=1
                before=self.entry(group,key)
                self.p['buildings']['shipyard']=5
                entry=self.entry(group,key)
                self.assertLess(entry['seconds'],before['seconds'])
                self.assertEqual(entry['cost'],before['cost'])
                self.assertEqual(entry['seconds'],math.ceil(self.w._specs(self.owner,group)[key][3]/1.4))
                # Spoofed client durations/levels never override server rules.
                self.w.action(self.owner,{'type':kind,'key':key,'amount':1,'seconds':1,'facility_level':20})
                task=self.p['queue'][0]
                self.assertEqual(task['seconds'],entry['seconds'])
                self.assertEqual(task['ends_at']-self.w.now,entry['seconds'])
                self.assertEqual(task['facility_timing']['level'],5)

    def test_laboratory_speeds_all_basic_and_racial_research_quotes(self):
        for race in RACES:
            self.race(race)
            for key in self.w._specs(self.owner,'research'):
                with self.subTest(race=race,key=key):
                    self.p['buildings']['lab']=1
                    before=self.entry('research',key)
                    self.p['buildings']['lab']=8
                    after=self.entry('research',key)
                    self.assertLess(after['seconds'],before['seconds'])
                    self.assertEqual(before['cost'],after['cost'])
                    self.assertEqual(after['seconds'],math.ceil(self.w._specs(self.owner,'research')[key][3]/1.7))

    def test_real_racial_research_order_uses_local_laboratory(self):
        for race in RACES:
            self.race(race)
            self.p['buildings'].update({k:5 for k in self.p['buildings']})
            self.p['buildings']['lab']=8
            for key in self.w._player(self.owner)['research']:
                self.w._player(self.owner)['research'][key]=0
            key=next(iter(UNIQUE_RESEARCH[race]))
            row=self.entry('research',key)
            self.assertTrue(row['enabled'],row['reason'])
            self.w.action(self.owner,{'type':'research','key':key})
            self.assertEqual(self.p['queue'][0]['seconds'],row['seconds'])
            self.assertEqual(self.p['queue'][0]['facility_timing']['building_key'],'lab')

    def test_lab_uses_selected_start_planet_not_best_lab_in_empire(self):
        other=deepcopy(self.p);other['id']='local076';other['queue']=[]
        other['buildings'].update(lab=1,shipyard=1)
        self.w.data['planets'][other['id']]=other
        self.p['buildings'].update(lab=12,shipyard=12)
        low=self.entry('research','propulsion',other)
        high=self.entry('research','propulsion',self.p)
        self.assertGreater(low['seconds'],high['seconds'])
        self.w.action(self.owner,{'type':'research','key':'propulsion','planet_id':other['id']})
        self.assertEqual(other['queue'][0]['seconds'],low['seconds'])
        self.assertEqual(other['queue'][0]['facility_timing']['level'],1)
        self.assertFalse(self.p['queue'])

    def test_skill_and_factory_stack_once_with_level_bonus(self):
        factories={'zetans':'quantum_foundry','symbionts':'brood_chamber','automatons':'assembly_hub'}
        for race,factory in factories.items():
            self.race(race)
            self.p['buildings'].update(shipyard=5,lab=5)
            self.p['buildings'][factory]=5
            with patch.object(self.w,'_bonuses',return_value={'build_speed':.5,'research_speed':.5}):
                for group,key in [('ships','scout'),('research','propulsion')]:
                    row=self.entry(group,key)
                    base=self.w._specs(self.owner,group)[key][3]
                    expected=math.ceil(base/1.5*(.75 if group=='ships' else 1)/1.4)
                    self.assertEqual(row['seconds'],expected)

    def test_automaton_batch_still_applies_existing_serial_discount_once(self):
        self.race('automatons')
        self.p['buildings'].update(shipyard=5,serial_forge=5,assembly_hub=5)
        row=self.entry('ships','scout')
        reduction=min(row['batch_time_reduction_cap'],row['batch_time_reduction_per_extra']*4)
        self.w.action(self.owner,{'type':'ship','key':'scout','amount':5})
        self.assertEqual(self.p['queue'][0]['seconds'],math.ceil(row['seconds']*5*(1-reduction)))
        self.assertEqual(self.p['queue'][0]['paid_cost'],{k:v*5 for k,v in row['cost'].items()})

    def test_no_changes_to_mining_prices_energy_flights_or_building_timers(self):
        before=self.w._catalog(self.owner,self.p)
        rates=self.w.production(self.p);energy=self.w.energy(self.p)
        target=next(p for p in self.w.data['planets'].values() if p['owner_type']=='empty' and p['id']!=self.p['id'])
        flight=self.w._flight_numbers(self.p,target,{'scout':1})
        self.p['buildings'].update(shipyard=12,lab=12)
        after=self.w._catalog(self.owner,self.p)
        for a,b in zip(before['buildings'],after['buildings']):
            if a['key'] not in ('shipyard','lab'):
                self.assertEqual(a['seconds'],b['seconds'])
                self.assertEqual(a['cost'],b['cost'])
        self.assertEqual(self.w.production(self.p),rates)
        self.assertEqual(self.w.energy(self.p),energy)
        self.assertEqual(self.w._flight_numbers(self.p,target,{'scout':1}),flight)
        self.assertEqual(ECONOMY_MULTIPLIER,.1)

    def test_running_timers_and_paid_cost_stay_fixed_after_facility_change(self):
        self.w.action(self.owner,{'type':'ship','key':'scout','amount':2})
        task=deepcopy(self.p['queue'][0])
        self.p['buildings']['shipyard']=12
        self.w._catalog(self.owner,self.p)
        self.w.state(self.owner,self.p['id'])
        self.assertEqual(self.p['queue'][0],task)
        self.w.action(self.owner,{'type':'cancel_project','queue_id':task['id']})
        self.assertFalse(self.p['queue'])

    def test_reload_keeps_legacy_deadline_and_does_not_add_reset(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'world.sqlite3')
            a=World(path,now=2_000_000_000)
            response=a.register('Persist076','Test-password-076!')
            owner=response['state']['player']['id'];p=a._owned(owner)
            p['resources']={k:10000000 for k in RESOURCES}
            a.action(owner,{'type':'ship','key':'scout','amount':2})
            # Legacy task predating the new facility metadata.
            p['queue'][0].pop('facility_timing',None)
            task=deepcopy(p['queue'][0]);pid=p['id'];a.close()
            b=World(path,now=2_000_000_000)
            try:
                self.assertEqual(b.data['planets'][pid]['queue'][0],task)
                self.assertEqual(len([p for p in b.data['planets'].values() if p['owner_id']==owner]),1)
            finally:b.close()

    def test_zero_facility_still_blocks_paid_orders(self):
        for group,key,kind,facility in [('ships','scout','ship','shipyard'),('research','propulsion','research','lab')]:
            self.p['buildings'][facility]=0
            entry=self.entry(group,key)
            self.assertFalse(entry['enabled'])
            with self.assertRaises(GameError):self.w.action(self.owner,{'type':kind,'key':key})

    def test_current_and_next_example_timers_match_authoritative_catalog(self):
        for race in RACES:
            self.race(race)
            for key in ('shipyard','lab'):
                for level in (0,1,4,11,12):
                    self.p['buildings'][key]=level
                    before=deepcopy(self.w.data)
                    d=self.entry('buildings',key)['details']
                    self.assertEqual(self.w.data,before)
                    future=deepcopy(self.p);future['buildings'][key]=min(12,level+1)
                    for ex in d['time_examples']:
                        nowrow=self.entry(ex['group'],ex['key'],self.p)
                        nextrow=self.entry(ex['group'],ex['key'],future)
                        if ex['current_seconds'] is not None:self.assertEqual(ex['current_seconds'],nowrow['seconds'])
                        if ex['next_seconds'] is not None:self.assertEqual(ex['next_seconds'],nextrow['seconds'])
                        if level==0:self.assertIsNone(ex['current_seconds'])
                        if level==12:self.assertIsNone(ex['next_seconds'])
                    for metric in d['metrics']:
                        if level==12:self.assertIsNone(metric['next'])
                    self.assertNotIn('shipyard_unlocks_only',d['notes'])
                    self.assertNotIn('lab_unlocks_only',d['notes'])

    def test_upgrading_dock_then_new_order_really_shortens_production(self):
        old=self.entry('ships','scout')['seconds']
        self.w.action(self.owner,{'type':'build','key':'shipyard'})
        self.w.now=self.p['queue'][0]['ends_at']
        self.w._complete_queue(self.p)
        self.assertEqual(self.p['buildings']['shipyard'],2)
        row=self.entry('ships','scout')
        self.assertLess(row['seconds'],old)
        count=self.p['ships']['scout']
        self.w.action(self.owner,{'type':'ship','key':'scout','amount':1})
        end=self.p['queue'][0]['ends_at']
        self.w.advance(end-1)
        self.assertEqual(self.p['ships']['scout'],count)
        self.w.advance(end)
        self.assertEqual(self.p['ships']['scout'],count+1)

    def test_khar_hatchery_applies_same_rule_to_paid_ship_and_defense_batches(self):
        hive=next(p for p in self.w.data['planets'].values() if p['owner_id']==swarm.OWNER_ID)
        for kind,key,group,amount in [('ship','frigate','ships',3),('defense','acid_spire','defenses',2)]:
            durations=[]
            for level in (1,5,20):
                hive['queue']=[];hive['resources']={k:10000000 for k in RESOURCES};hive['buildings']['shipyard']=level
                before=dict(hive['resources'])
                self.assertTrue(self.w._swarm_queue(hive,kind,key,amount))
                task=hive['queue'][0];spec=self.w._specs('khar',group)[key]
                self.assertEqual(task['seconds'],math.ceil(spec[3]*amount/(1+.1*(level-1))))
                self.assertEqual(task['facility_timing']['level'],level)
                for resource,cost in zip(RESOURCES,spec[2]):self.assertEqual(before[resource]-hive['resources'][resource],cost*amount)
                durations.append(task['seconds'])
            self.assertGreater(durations[0],durations[1]);self.assertGreater(durations[1],durations[2])

    def test_khar_building_upgrades_do_not_gain_hatchery_speed(self):
        hive=next(p for p in self.w.data['planets'].values() if p['owner_id']=='khar')
        hive['queue']=[];hive['resources']={k:10000000 for k in RESOURCES}
        hive['buildings'].update(shipyard=20,lab=1)
        self.assertTrue(self.w._swarm_queue(hive,'build','lab'))
        self.assertEqual(hive['queue'][0]['seconds'],math.ceil(swarm.BUILDINGS['lab'][3]*1.3))


class FacilityReleaseContracts(unittest.TestCase):
    def test_flat_modules_and_docker_are_complete(self):
        for source,flat in [('main.py','app.py'),('swarm_ai.py','swarm_ai.py'),('production_timing.py','production_timing.py')]:
            self.assertEqual((ROOT/'server'/source).read_bytes(),(ROOT/'railway'/flat).read_bytes())
        self.assertIn('production_timing.py',(ROOT/'railway/Dockerfile').read_text())
        self.assertIn('slow-economy-072',(ROOT/'server/balance_reset.py').read_text())

    def test_speed_notes_and_project_time_labels_translated_for_all_locales(self):
        sources=json.loads((ROOT/'localization/widgets_source.json').read_text())
        notes=[s for s in sources if s.startswith(('Każdy poziom stoczni','Każdy poziom laboratorium','Premie do tempa'))]
        self.assertEqual(len(notes),3)
        for lang in ('en','pl','de','es','fr'):
            data=json.loads((ROOT/'localization'/f'{lang}.json').read_text())
            for key in notes+['Czas projektu: %s','Premia stoczni do tempa produkcji','Premia laboratorium do tempa badań']:
                self.assertTrue(data[key])
                if lang!='pl':self.assertNotEqual(data[key],key)
            self.assertEqual((ROOT/'localization'/f'{lang}.json').read_bytes(),(ROOT/'railway'/f'{lang}.json').read_bytes())

    def test_ui_displays_real_server_examples_without_recomputing_timers(self):
        text=(ROOT/'client/scripts/catalog_details.gd').read_text()
        self.assertIn('detail.get("time_examples", [])',text)
        self.assertIn('host._duration(float(example["current_seconds"]))',text)
        self.assertIn('host._duration(float(example["next_seconds"]))',text)
        self.assertIn('"shipyard_speed_rule"',text)
        self.assertIn('"lab_speed_rule"',text)
        self.assertNotIn('pow(1.1',text)

if __name__=='__main__':unittest.main(verbosity=2)
