"""0.11 regressions: server gates, real queues, combat traits and additive saves.
Run with python -m unittest discover -s tests -p 'test*.py'. No third-party deps.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import fleet_expansion as fleet
import technology
from i18n import language_scope


class CapitalFleetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / 'capital.sqlite3')
        self.world = app.World(self.db, 1, now=1800000000)
        self.seq = 0

    def tearDown(self):
        self.world.close()
        self.temp.cleanup()

    def colony(self, race='zetans', endgame=False):
        self.seq += 1
        account = self.world.register('fleet_test_' + str(self.seq), 'LocalTest-94751')
        owner, pid = account['state']['player']['id'], account['state']['planet_id']
        if race:
            self.world.action(owner, {'type':'choose_race', 'race_id':race, 'planet_id':pid})
        p = self.world.data['planets'][pid]
        p['resources'] = dict.fromkeys(app.RESOURCES, 100000000)
        if endgame:
            for item in self.world._catalog(owner, p)['research']:
                self.world._player(owner)['research'][item['key']] = item['max_level']
            for key in p['buildings']:
                p['buildings'][key] = 5 if key in app.UNIQUE_BUILDINGS.get(race, {}) else 12
            project = self.world._player(owner)['megastructure']
            project.update(origin_id=pid, dyson_stage=4, gate_level=1)
        return owner, pid, account['token']

    def planet(self, pid):
        return self.world.data['planets'][pid]

    def item(self, owner, pid, group, key):
        return next(item for item in self.world._catalog(owner, self.planet(pid))[group] if item['key']==key)

    def command(self, owner, pid, kind, **values):
        return self.world.action(owner, {'planet_id':pid, 'type':kind, **values})

    def finish(self, pid):
        # Move a real pending deadline to the next second; advance uses normal completion code.
        self.planet(pid)['queue'][0]['ends_at'] = self.world.now + 1
        self.world.advance(self.world.now + 1)

    def test_initial_fleet_unchanged_and_new_hulls_start_at_zero(self):
        for race in app.RACES:
            owner, pid, _ = self.colony(race)
            ships = self.planet(pid)['ships']
            self.assertEqual({k: ships[k] for k in ('scout','cargo','colonizer','frigate')},
                             {'scout':2,'cargo':1,'colonizer':1,'frigate':3})
            self.assertTrue(all(ships[k]==0 for k in fleet.CAPITAL_ROLES))
            self.assertTrue(self.item(owner,pid,'ships','scout')['enabled'])

    def test_rich_shipyard_alone_cannot_build_any_new_hull(self):
        for race in app.RACES:
            owner,pid,_=self.colony(race)
            self.planet(pid)['buildings']['shipyard']=12
            for key in fleet.CAPITAL_ROLES:
                with self.subTest(race=race, key=key):
                    before=copy.deepcopy(self.planet(pid))
                    self.assertFalse(self.item(owner,pid,'ships',key)['enabled'])
                    with self.assertRaises(app.GameError):self.command(owner,pid,'ship',key=key)
                    self.assertEqual(self.planet(pid),before)

    def test_raceless_accounts_do_not_gain_new_hulls(self):
        owner,pid,_=self.colony(None,True)
        for key in fleet.CAPITAL_ROLES:
            self.assertFalse(self.item(owner,pid,'ships',key)['enabled'])
            with self.assertRaises(app.GameError):self.command(owner,pid,'ship',key=key)

    def test_each_research_requirement_is_enforced_on_server(self):
        for race in app.RACES:
            owner,pid,_=self.colony(race,True)
            for key in fleet.CAPITAL_ROLES:
                self.assertTrue(self.item(owner,pid,'ships',key)['enabled'])
                for req in self.item(owner,pid,'ships',key)['requirements']:
                    if req['group']!='research':continue
                    old=self.world._player(owner)['research'][req['key']]
                    self.world._player(owner)['research'][req['key']]=req['level']-1
                    self.assertFalse(self.item(owner,pid,'ships',key)['enabled'],(race,key,req))
                    with self.assertRaises(app.GameError):self.command(owner,pid,'ship',key=key)
                    self.world._player(owner)['research'][req['key']]=old

    def test_research_queue_does_not_unlock_until_completion_and_caps_at_one(self):
        owner,pid,_=self.colony('zetans',True)
        signature=fleet.SIGNATURES['zetans'][0]
        self.world._player(owner)['research'][signature]=0
        self.command(owner,pid,'research',key=signature)
        self.assertFalse(self.item(owner,pid,'ships','flagship')['enabled'])
        self.assertEqual(self.world._player(owner)['research'][signature],0)
        self.finish(pid)
        self.assertTrue(self.item(owner,pid,'ships','flagship')['enabled'])
        entry=self.item(owner,pid,'research',signature)
        self.assertEqual(entry['level'],1);self.assertEqual(entry['max_level'],1)
        self.assertIsNone(entry['effect_next']);self.assertFalse(entry['enabled'])
        with self.assertRaises(app.GameError):self.command(owner,pid,'research',key=signature)

    def test_production_completion_and_exact_cancel_refund_for_all_races(self):
        for race in app.RACES:
            owner,pid,_=self.colony(race,True)
            for key in fleet.CAPITAL_ROLES:
                before=copy.deepcopy(self.planet(pid)['resources'])
                entry=self.item(owner,pid,'ships',key)
                result=self.command(owner,pid,'ship',key=key,amount=2)
                task=self.planet(pid)['queue'][0]
                for resource in app.RESOURCES:
                    self.assertEqual(before[resource]-self.planet(pid)['resources'][resource],2*entry['cost'][resource])
                self.command(owner,pid,'cancel_project',queue_id=task['id'])
                self.assertEqual(self.planet(pid)['resources'],before)
                self.assertEqual(self.planet(pid)['ships'][key],0)
                self.command(owner,pid,'ship',key=key,amount=2)
                expected=self.world._produced_ships(owner,key,2)
                self.finish(pid)
                self.assertEqual(self.planet(pid)['ships'][key],expected)

    def test_batch_limits_and_idempotent_commands_prevent_duplicate_charges(self):
        owner,pid,_=self.colony('zetans',True)
        for n in (0,21,True,-1,1.5):
            with self.assertRaises(app.GameError):self.command(owner,pid,'ship',key='titan',amount=n)
        self.command(owner,pid,'ship',key='titan',request_id='capital-order-1')
        before=copy.deepcopy(self.planet(pid))
        self.command(owner,pid,'ship',key='titan',request_id='capital-order-1')
        self.assertEqual(self.planet(pid),before)

    def test_titan_requires_stage_four_at_this_colony_not_elsewhere(self):
        owner,pid,_=self.colony('automatons',True)
        project=self.world._player(owner)['megastructure']
        project['dyson_stage']=3
        self.assertFalse(self.item(owner,pid,'ships','titan')['enabled'])
        project['dyson_stage']=4
        self.assertTrue(self.item(owner,pid,'ships','titan')['enabled'])
        other=next(p for p in self.world.data['planets'].values() if p['owner_type']=='empty')
        other.update(owner_id=owner,owner_type='player',buildings=copy.deepcopy(self.planet(pid)['buildings']),
                     ships=dict.fromkeys(self.planet(pid)['ships'],0),resources=dict.fromkeys(app.RESOURCES,100000000))
        self.assertFalse(self.item(owner,other['id'],'ships','titan')['enabled'])

    def test_capital_attack_bonus_changes_only_new_heavy_hulls(self):
        owner,pid,_=self.colony('zetans')
        before=self.world._specs(owner,'ships')
        self.world._player(owner)['research']['capital_weapons']=5
        after=self.world._specs(owner,'ships')
        for key in before:
            self.assertAlmostEqual(after[key][4],before[key][4]*(1.2 if key in fleet.CAPITAL_ROLES else 1))
            self.assertEqual(after[key][5],before[key][5])

    def test_zetan_first_salvo_is_per_hull_and_shared_by_normal_and_coalition(self):
        owner,pid,_=self.colony('zetans')
        ships={'flagship':2,'battleship':1}
        specs=self.world._specs(owner,'ships');race=self.world._rules(owner)
        expected=(2*specs['flagship'][4]*1.6+specs['battleship'][4])*race['first_volley_multiplier']
        form=self.world._coalition_formation(owner,dict(ships),'formation')
        normal=self.world._power(ships,0,specs,race['first_volley_multiplier'],type_multipliers=self.world._ship_round_factors(owner,1))
        self.assertAlmostEqual(normal,expected)
        self.assertAlmostEqual(self.world._coalition_power(form,1),expected)
        self.assertAlmostEqual(self.world._coalition_power(form,2),2*specs['flagship'][4]+specs['battleship'][4])

    def test_symbiont_signature_heals_only_own_surviving_wounds_in_both_paths(self):
        owner,pid,_=self.colony('symbionts')
        form=self.world._coalition_formation(owner,{'flagship':1,'battleship':1,'dreadnought':0},'form')
        form['wounds']={'flagship':1000.,'battleship':1000.,'dreadnought':500.}
        wounds=copy.deepcopy(form['wounds']);normal=dict(form['ships'])
        fractions={k:v.get('regeneration_fraction',0) for k,v in self.world._ship_traits(owner).items()}
        self.world._regenerate(normal,wounds,form['regeneration'],fractions)
        self.world._coalition_regenerate([form],[])
        self.assertEqual(form['wounds'],wounds)
        self.assertEqual(wounds['flagship'],400.)
        self.assertEqual(wounds['battleship'],1000*(1-form['regeneration']))
        self.assertEqual(form['ships']['dreadnought'],0);self.assertEqual(wounds['dreadnought'],0)

    def test_automaton_signature_armor_multiplies_racial_reduction_only_for_itself(self):
        owner,pid,_=self.colony('automatons')
        for key in ('flagship','battleship'):
            form=self.world._coalition_formation(owner,{key:1},'form')
            wounds={};ships={key:1};traits=self.world._ship_traits(owner)
            self.world._damage(ships,1000,wounds,form['specs'],form['rules']['damage_reduction'],
                               {k:v.get('damage_reduction',0) for k,v in traits.items()})
            expected=1000*(1-form['rules']['damage_reduction'])*(.8 if key=='flagship' else 1)
            self.assertAlmostEqual(wounds[key],expected)
            self.world._coalition_damage([form],1000,[])
            self.assertAlmostEqual(form['wounds'][key],expected)

    def test_capital_only_fleets_can_attack_and_have_battle_replays(self):
        for race in app.RACES:
            owner,pid,_=self.colony(race,True)
            defender,target_id,_=self.colony('automatons')
            target=self.planet(target_id)
            target['system_id']=self.planet(pid)['system_id']  # Local combat fixture, not an intergalactic fuel test.
            target['galaxy_id']=self.world._galaxy_id(self.planet(pid))
            self.world._player(defender)['protected_until']=0
            target['ships']={k:0 for k in target['ships']};target['ships']['battleship']=1
            target['defenses']={k:0 for k in target['defenses']}
            for role in fleet.CAPITAL_ROLES:
                self.planet(pid)['ships'][role]=1
                with patch.object(self.world,'_known_planet',return_value=True):
                    q=self.world._fleet_quote(owner,{'planet_id':pid,'target_id':target_id,'mission':'attack','ships':{role:1}})
                self.assertGreater(q[5],0);self.assertGreater(q[6],0)
            # One real battle exercises damage, healing, reports, loot, return and new hull serialization.
            with patch.object(self.world,'_known_planet',return_value=True):
                self.command(owner,pid,'fleet',target_id=target_id,mission='attack',ships={'flagship':1,'titan':1})
            f=next(f for f in self.world.data['fleets'].values() if f['owner_id']==owner)
            self.world._battle(f,target)
            replay=next(r['battle_replay'] for r in self.world._player(owner)['reports'] if 'battle_replay' in r)
            self.assertTrue(replay['rounds']);json.dumps(replay,allow_nan=False)

    def test_mixed_race_coalition_resolves_new_hulls_and_records_all_participants(self):
        defender,target_id,_=self.colony('automatons',True)
        target=self.planet(target_id)
        target['ships']={k:0 for k in target['ships']};target['ships']['titan']=2
        target['defenses']={k:0 for k in target['defenses']}
        formations=[]
        for race in app.RACES:
            owner,pid,_=self.colony(race,True)
            f={'id':'test_coalition_'+race,'owner_id':owner,'origin_id':pid,'target_id':target_id,
               'mission':'alliance_attack','status':'outbound','seconds':120,'arrives_at':self.world.now+120,
               'started_at':self.world.now,'ships':dict.fromkeys(fleet.CAPITAL_ROLES,2),
               'cargo':dict.fromkeys(app.RESOURCES,0),'building_effects':self.world._building_effects(self.planet(pid))}
            self.world.data['fleets'][f['id']]=f;formations.append(f)
        expected=sum(self.world._coalition_power(self.world._coalition_formation(f['owner_id'],f['ships'],f['id'],fleet=f),1) for f in formations)
        result=self.world._alliance_battle(formations,target)
        self.assertGreater(result['rounds'],0)
        report=next(r['battle_replay'] for r in self.world._player(defender)['reports'] if 'battle_replay' in r)
        self.assertEqual(len(report['attacker']['participants']),3)
        self.assertAlmostEqual(report['rounds'][0]['salvos']['attacker'],expected)
        self.assertEqual(report['attacker']['race'],'mixed')
        self.assertTrue(all('/siege' in u['art_key'] or '/cruiser' in u['art_key'] for u in report['attacker']['units']))
        json.dumps(report,allow_nan=False)

    def test_real_megastructure_queue_cancel_and_four_stages(self):
        owner,pid,_=self.colony('zetans',True)
        project=self.world._player(owner)['megastructure']
        project.update(origin_id='',dyson_stage=0,gate_level=0,energy=0)
        before=copy.deepcopy(self.planet(pid)['resources'])
        self.command(owner,pid,'megabuild',key='dyson')
        q=project['queue'];self.assertFalse(self.item(owner,pid,'ships','titan')['enabled'])
        self.command(owner,pid,'megacancel',queue_id=q['id'])
        self.assertEqual(self.planet(pid)['resources'],before);self.assertEqual(project['origin_id'],'')
        for stage in range(1,5):
            self.command(owner,pid,'megabuild',key='dyson')
            project['queue']['ends_at']=self.world.now+1
            self.world.advance(self.world.now+1)
            self.assertEqual(project['dyson_stage'],stage)
        self.assertTrue(self.item(owner,pid,'ships','titan')['enabled'])
        self.command(owner,pid,'megabuild',key='wormhole')
        project['queue']['ends_at']=self.world.now+1;self.world.advance(self.world.now+1)
        self.assertEqual(project['gate_level'],1)

    def test_titan_core_expands_capacitor_without_creating_energy(self):
        owner,pid,_=self.colony('zetans',True)
        player=self.world._player(owner);player['research']['titan_core']=0
        player['megastructure']['energy']=10000
        before=self.world._mega_profile(player)
        self.command(owner,pid,'research',key='titan_core');self.finish(pid)
        after=self.world._mega_profile(player)
        self.assertEqual(after['capacity'],before['capacity']*8)
        self.assertEqual(after['charge_per_second'],before['charge_per_second'])
        self.assertAlmostEqual(player['megastructure']['energy'],10000+before['charge_per_second'])

    def test_titan_tunnel_roundtrip_is_affordable_at_endgame_and_paid_once(self):
        for race in app.RACES:
            owner,pid,_=self.colony(race,True)
            p=self.planet(pid);p['ships']['titan']=1
            player=self.world._player(owner);project=player['megastructure']
            target=next(v for v in self.world.data['planets'].values() if v['owner_type']=='empty')
            project['energy']=self.world._mega_profile(player)['capacity']
            self.command(owner,pid,'tunnel_open',target_id=target['id'])
            with self.assertRaises(app.GameError):
                self.world._tunnel_quote(owner,p,target,{'titan':1},{})
            # Shift the ready_at boundary, without changing available energy or pricing.
            project['window']['ready_at']=self.world.now
            quote=self.world._tunnel_quote(owner,p,target,{'titan':1,'scout':1},{})
            self.assertTrue(quote['affordable']);self.assertGreater(quote['return_reserved'],0)
            before=project['energy'];fuel=p['resources']['fuel']
            self.command(owner,pid,'fleet',target_id=target['id'],mission='scout',ships={'scout':1,'titan':1},travel_mode='tunnel')
            self.assertEqual(project['energy'],before-quote['energy_cost'])
            self.assertEqual(p['resources']['fuel'],fuel)
            f=next(f for f in self.world.data['fleets'].values() if f['owner_id']==owner)
            self.command(owner,pid,'tunnel_close')
            self.assertIsNone(project['window']);self.assertEqual(f['tunnel']['return_reserved'],quote['return_reserved'])
            self.world._return(f);self.assertEqual(f['seconds'],120)
            self.world._land(p,f);self.assertEqual(p['ships']['titan'],1)
            self.assertEqual(project['energy'],before-quote['energy_cost'])

    def test_catalog_is_read_only_and_all_graph_requirements_are_reachable(self):
        for race in app.RACES:
            owner,pid,_=self.colony(race)
            before=copy.deepcopy(self.world.data)
            catalog=self.world._catalog(owner,self.planet(pid))
            self.assertEqual(self.world.data,before)
            self.assertEqual(len(catalog['ships']),12);self.assertEqual(len(catalog['research']),25)
            by_key={r['key']:r for r in catalog['research']}
            coords=set()
            for item in catalog['research']:
                pos=(item['tree']['row'],item['tree']['column'])
                self.assertNotIn(pos,coords);coords.add(pos)
                self.assertLess(pos[1],3)
                for req in item['requirements']:
                    if req['group']!='research':continue
                    self.assertIn(req['key'],by_key)
                    parent=by_key[req['key']]
                    self.assertLessEqual(req['level'],parent['max_level'])
                    self.assertLess(parent['tree']['row'],item['tree']['row'])
                    self.assertTrue(any(u['key']==item['key'] and u['group']=='research' and u['level']==req['level'] for u in parent['unlocks']))
            json.dumps(catalog,allow_nan=False)

    def test_old_save_migrates_additively_with_backup_accounts_and_queues_intact(self):
        owner,pid,token=self.colony('symbionts')
        self.planet(pid)['buildings']['lab']=4
        self.world._player(owner)['research']['computing']=3
        self.command(owner,pid,'research',key='computing')
        self.world.data['technology_schema']=1
        new_research={'capital_shipbuilding','capital_weapons','titan_core',fleet.SIGNATURES['symbionts'][0]}
        for key in new_research:self.world._player(owner)['research'].pop(key,None)
        for p in self.world.data['planets'].values():
            for key in fleet.CAPITAL_ROLES:p['ships'].pop(key,None)
        before=copy.deepcopy(self.planet(pid));now=self.world.now
        self.world._save();backups_before=set(Path(self.temp.name,'backups').glob('*.sqlite3'))
        self.world.close();self.world=app.World(self.db,1,now=now)
        self.assertEqual(self.world.authenticate(token),owner)
        self.assertEqual(self.world.data['technology_schema'],2)
        after=self.planet(pid)
        for key in ('resources','buildings','queue'):self.assertEqual(after[key],before[key])
        for key,count in before['ships'].items():self.assertEqual(after['ships'][key],count)
        for key in fleet.CAPITAL_ROLES:self.assertEqual(after['ships'][key],0)
        for key in new_research:self.assertEqual(self.world._player(owner)['research'][key],0)
        self.assertEqual(self.world._player(owner)['research']['computing'],3)
        self.assertTrue(set(Path(self.temp.name,'backups').glob('*.sqlite3'))-backups_before)


if __name__=='__main__':unittest.main()
