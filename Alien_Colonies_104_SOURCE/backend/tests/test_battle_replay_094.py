"""Replay telemetry must match combat, survive saves, and remain participant-only."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from server.main import World, blank_ships, GameError, build_server, CLIENT_VERSION_CODE
from server.i18n import language_scope
from tests.fixtures.combat_093 import Combat093

NOW = 1900000000
class LegacyWorld(Combat093, World):
    pass


def fixture(world, attacker_race='zetans', defender_race='symbionts', full=False):
    accounts=[]
    for name, race in [('Orion',attacker_race),('Verdant',defender_race),('Observer','automatons')]:
        account=world.register(name,'test-replay-password')
        player=account['state']['player']['id']
        world.action(player,{'type':'choose_race','race_id':race})
        accounts.append((player,account['token']))
    a,b,_=accounts; origin=world._owned(a[0]);target=world._owned(b[0])
    origin['ships']={**blank_ships(),'scout':4,'frigate':14,'cruiser':4}
    target['ships']={**blank_ships(),'frigate':8,'cruiser':6}
    target['defenses']={k:2 for k in world._specs(b[0],'defenses')}
    if full:
        origin['ships']={k:i+1 for i,k in enumerate(blank_ships())}
        target['ships']={k:i+2 for i,k in enumerate(blank_ships())}
    world._player(a[0])['protected_until']=0;world._player(b[0])['protected_until']=0
    f={'id':'replay-fixture','owner_id':a[0],'origin_id':origin['id'],'target_id':target['id'],
       'mission':'attack','status':'outbound','ships':dict(origin['ships']),
       'cargo':dict.fromkeys(('metal','crystal','fuel'),0),'seconds':300,
       'started_at':NOW,'arrives_at':NOW+300,'building_effects':world._building_effects(origin)}
    world.data['fleets'][f['id']]=f
    return accounts,f,target


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.w=World(':memory:',now=NOW)
        self.addCleanup(self.w.close)
        self.accounts,self.f,self.target=fixture(self.w)
        self.a,self.b,self.other=[p[0] for p in self.accounts]

    def record(self):
        self.w._battle(self.f,self.target)
        return self.w._player(self.a)['reports'][0]['battle_replay']

    def test_each_damage_healing_and_final_state_reconcile(self):
        record=self.record(); previous={s:record[s]['initial'] for s in ('attacker','defender')}
        self.assertTrue(record['rounds'])
        seen_heal=seen_loss=False
        for r in record['rounds']:
            self.assertEqual(r['before'],previous)
            for side in ('attacker','defender'):
                actual=copy.deepcopy(r['before'][side]);units={u['key']:u for u in record[side]['units']}
                last=(-1,'')
                for hit in r['hits'][side]:
                    key=hit['key'];unit=units[key]
                    self.assertLessEqual(last,(unit['hull'],key));last=(unit['hull'],key)
                    self.assertEqual(actual[key],hit['before'])
                    self.assertEqual(hit['before']['count']-hit['after']['count'],hit['destroyed'])
                    before=hit['before']['count']*unit['hull']-hit['before']['wounds']
                    after=hit['after']['count']*unit['hull']-hit['after']['wounds']
                    self.assertAlmostEqual(before-after,hit['damage'])
                    self.assertGreaterEqual(hit['blocked'],0)
                    actual[key]=hit['after'];seen_loss|=hit['destroyed']>0
                self.assertEqual(actual,r['after_damage'][side])
                for heal in r['heals'][side]:
                    key=heal['key'];self.assertEqual(actual[key],heal['before'])
                    self.assertEqual(heal['before']['count'],heal['after']['count'])
                    self.assertGreater(heal['after']['count'],0)
                    self.assertAlmostEqual(heal['before']['wounds']-heal['after']['wounds'],heal['healed'])
                    actual[key]=heal['after'];seen_heal=True
                self.assertEqual(actual,r['after'][side])
            previous=r['after']
        self.assertTrue(seen_heal);self.assertTrue(seen_loss)
        self.assertEqual(previous,record['final'])
        for side,counts in [('attacker',self.f['ships']),('defender',{**self.target['ships'],**self.target['defenses']})]:
            for key,state in record['final'][side].items():
                self.assertEqual(state['count'],counts[key])
                self.assertEqual(record[side]['initial'][key]['count']-state['count'],record[side]['losses'][key])
        self.assertEqual(record['cargo'],self.f['cargo'])
        json.dumps(record,allow_nan=False)

    def test_old_combat_outcomes_and_loot_match_all_factions_and_swarm(self):
        # All race pairings, static defenses, skill/research buffs and NPC rewards.
        base=copy.deepcopy(self.w.data)
        for ar in ('zetans','automatons','symbionts'):
            for dr in ('zetans','automatons','symbionts','swarm'):
                with self.subTest(attacker=ar,defender=dr):
                    self.w.data=copy.deepcopy(base)
                    for player,race in ((self.a,ar),(self.b,dr if dr!='swarm' else 'zetans')):
                        p=self.w._player(player);p['race_id']=race;p['skill_nodes']=[]
                        p['research']['weapons']=2
                    f=self.w.data['fleets']['replay-fixture']
                    target=self.w._owned(self.b) if dr!='swarm' else next(p for p in self.w.data['planets'].values() if p['owner_id']=='khar')
                    f['target_id']=target['id']
                    target['defenses']={k:2 for k in self.w._specs(target['owner_id'],'defenses')}
                    old=LegacyWorld(':memory:',now=NOW);old.data=copy.deepcopy(self.w.data)
                    try:
                        old._battle(old.data['fleets'][f['id']],old.data['planets'][target['id']])
                        self.w._battle(f,target)
                        if dr == 'swarm':
                            # Eradication deliberately changes ownership, queues,
                            # reports and attacker intel after combat. The frozen
                            # oracle still verifies identical casualties and loot.
                            current_fleets = copy.deepcopy(self.w.data['fleets'])
                            for flight in current_fleets.values():
                                self.assertEqual(flight.pop('swarm_destruction_bonus', 0), 0)
                            self.assertEqual(current_fleets, old.data['fleets'])
                            record = self.w._player(self.a)['reports'][0]['battle_replay']
                            old_target = old.data['planets'][target['id']]
                            survivors = {**old_target['ships'], **old_target['defenses']}
                            for key, unit in record['final']['defender'].items():
                                self.assertEqual(unit['count'], survivors.get(key, 0))
                            self.assertEqual(old_target['swarm_kind'], 'hive')
                            self.assertFalse(record['swarm_eradicated'])
                            self.assertEqual(target['owner_type'], 'alien')
                            self.assertEqual(target['buildings'], old_target['buildings'])
                            self.assertEqual(target['queue'], old_target['queue'])
                            self.assertEqual(record['cargo'], f['cargo'])
                            self.assertEqual(record['swarm_crystals'], f['swarm_crystals'])
                            continue
                        current=copy.deepcopy(self.w.data);legacy=copy.deepcopy(old.data)
                        for flight in current['fleets'].values():
                            self.assertEqual(flight.pop('swarm_destruction_bonus', 0), 0)
                        for data in (current,legacy):
                            for p in data['players'].values():
                                for report in p['reports']:
                                    report.pop('id',None);report.pop('battle_replay',None)
                        self.assertEqual(current,legacy)
                    finally:old.close()

    def test_simultaneous_salvos_allow_mutual_destruction(self):
        for pid in (self.a,self.b):
            p=self.w._player(pid);p['race_id']='';p['skill_nodes']=[];p['research']['weapons']=100
        self.f['ships']={**blank_ships(),'scout':1}
        self.target['ships']={**blank_ships(),'scout':1};self.target['defenses']={}
        record=self.record()
        self.assertEqual(len(record['rounds']),1)
        self.assertEqual(record['rounds'][0]['salvos'],{'attacker':32.0,'defender':32.0})
        self.assertEqual(record['final']['attacker']['scout']['count'],0)
        self.assertEqual(record['final']['defender']['scout']['count'],0)

    def test_zero_rounds_empty_target_and_six_round_retreat(self):
        self.target['ships']=blank_ships();self.target['defenses']={}
        record=self.record();self.assertEqual(record['rounds'],[]);self.assertEqual(record['outcome'],'attacker_wins')
        self.f['ships']={**blank_ships(),'cargo':1};self.target['ships']={**blank_ships(),'cargo':1}
        record=self.record();self.assertEqual(len(record['rounds']),6);self.assertEqual(record['outcome'],'retreat')

    def test_immutable_persisted_localized_private_and_small_state(self):
        record=self.record();report=self.w._player(self.a)['reports'][0];rid=report['id']
        original=copy.deepcopy(record)
        with language_scope('en'):english=self.w.battle_report(self.a,rid)['replay']
        with language_scope('pl'):polish=self.w.battle_report(self.a,rid)['replay']
        self.assertEqual(english['attacker']['name'],'Orion')
        self.assertNotIn('name_i18n',english['attacker']['units'][0])
        self.assertNotEqual(english['attacker']['units'][0]['name'],polish['attacker']['units'][0]['name'])
        for pid in (self.other,self.b):
            with self.assertRaises(GameError): self.w.battle_report(pid,rid)
        state=self.w.state(self.a);public=next(r for r in state['reports'] if r['id']==rid)
        self.assertTrue(public['battle_replay_available']);self.assertNotIn('battle_replay',public)
        english['rounds'].clear();self.f['ships']['cruiser']=999;self.target['name']='Changed'
        self.assertEqual(record,original)
        self.assertLess(len(json.dumps(original)),100000)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'world.sqlite3'
            saved=World(path,now=NOW);saved.data=copy.deepcopy(self.w.data);saved.close()
            loaded=World(path,now=NOW)
            try:self.assertEqual(loaded._player(self.a)['reports'][0]['battle_replay'],original)
            finally:loaded.close()
        for i in range(85):self.w._report(self.a,'test','text')
        self.assertEqual(len(self.w._player(self.a)['reports']),80)
        with self.assertRaises(GameError):self.w.battle_report(self.a,rid)

    def test_npc_attack_is_recorded_for_the_defender(self):
        hive=next(p for p in self.w.data['planets'].values() if p['owner_id']=='khar')
        self.f.update(owner_id='khar',origin_id=hive['id'],swarm_weapon_level=2)
        self.f['ships']={k:3 for k in self.w._specs('khar','ships')}
        self.w._battle(self.f,self.target)
        report=self.w._player(self.b)['reports'][0]
        record=self.w.battle_report(self.b,report['id'])['replay']
        self.assertEqual(record['attacker']['race'],'swarm')
        self.assertTrue(record['rounds'])
        self.assertTrue(all(u['art_key'].startswith('swarm/') for u in record['attacker']['units']))
        self.assertFalse(any(r.get('battle_replay') for r in self.w._player(self.other)['reports']))

    def test_http_requires_owner_and_preserves_old_reports(self):
        self.record();rid=self.w._player(self.a)['reports'][0]['id']
        self.w._report(self.a,'Old report','Historical result')
        state=self.w.state(self.a);self.assertNotIn('battle_replay_available',state['reports'][0])
        # Prevent a real-clock jump from completing fixture fleet a second time.
        self.w.advance=lambda *a,**k:None
        server=build_server(self.w,'127.0.0.1',0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_address[1]}/api/battle-replay?report_id={rid}'
            for token,expected in [(self.accounts[0][1],200),(self.accounts[1][1],404),(self.accounts[2][1],404),('',401)]:
                req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'X-PGR-Client-Version':str(CLIENT_VERSION_CODE),'Accept-Language':'en'})
                try:
                    with urllib.request.urlopen(req) as response:
                        self.assertEqual(response.status,expected)
                        self.assertTrue(json.load(response)['replay']['rounds'])
                except urllib.error.HTTPError as error:self.assertEqual(error.code,expected)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
