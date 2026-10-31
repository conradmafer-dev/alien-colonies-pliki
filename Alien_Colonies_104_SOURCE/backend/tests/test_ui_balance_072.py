"""Regression tests for 0.7.2. Tests use local disposable databases only."""
from __future__ import annotations
import copy
import concurrent.futures
import json
import sys
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import main, balance_reset, skill_tree
from server.main import World, GameError, MAX_RESOURCE, RESOURCES

PASSWORD = 'Local-Test-Password-072!'
NOW = 2_000_000.0

class CancelProjectTests(unittest.TestCase):
    def setUp(self):
        self.w = World(':memory:', now=NOW)
        self.login = self.w.register('CancelTester', PASSWORD)
        self.pid = self.login['state']['player']['id']
        self.p = self.w._owned(self.pid)
        self.w.action(self.pid, {'type':'choose_race','race_id':'automatons'})
        self.p['resources'] = dict.fromkeys(RESOURCES, 100000.0)
        self.request_counter = 0
        self.addCleanup(self.w.close)

    def order(self, kind='build', key='metal_mine', amount=1):
        self.request_counter += 1
        self.w.action(self.pid, {'type':kind,'key':key,'amount':amount,'planet_id':self.p['id'],
                                'request_id':'build-'+str(self.request_counter)})
        return self.p['queue'][0]

    def cancel(self, task=None, **extra):
        task = task or self.p['queue'][0]
        payload = {'type':'cancel_project','queue_id':task['id'],'planet_id':self.p['id'],
                   'request_id':'cancel-'+task['id'], **extra}
        return self.w.action(self.pid,payload)

    def test_refunds_all_four_job_types_without_completing_them(self):
        for kind,key in [('build','metal_mine'),('research','weapons'),('ship','frigate'),('defense','iron_bastion')]:
            with self.subTest(kind=kind):
                before=copy.deepcopy(self.p)
                research=copy.deepcopy(self.w._player(self.pid)['research'])
                task=copy.deepcopy(self.order(kind,key,2 if kind in ('ship','defense') else 1))
                self.assertIn('paid_cost',task)
                for resource in RESOURCES:
                    self.assertEqual(before['resources'][resource]-self.p['resources'][resource],task['paid_cost'][resource])
                self.cancel(task)
                self.assertEqual(self.p['resources'],before['resources'])
                self.assertEqual(self.p['buildings'],before['buildings'])
                self.assertEqual(self.p['ships'],before['ships'])
                self.assertEqual(self.p['defenses'],before['defenses'])
                self.assertEqual(self.w._player(self.pid)['research'],research)
                self.assertEqual(self.p['queue'],[])

    def test_replay_has_no_second_refund(self):
        task=copy.deepcopy(self.order())
        self.cancel(task)
        before=copy.deepcopy(self.p)
        self.cancel(task)
        self.assertEqual(before,self.p)

    def test_replay_never_cancels_a_new_project(self):
        old=copy.deepcopy(self.order()); self.cancel(old)
        new=copy.deepcopy(self.order('build','power_plant'))
        self.cancel(old)
        self.assertEqual(self.p['queue'],[new])

    def test_stale_id_with_new_request_is_rejected(self):
        old=copy.deepcopy(self.order()); self.cancel(old)
        self.order('ship','cargo')
        before=copy.deepcopy(self.p)
        with self.assertRaises(GameError): self.cancel(old,request_id='different')
        self.assertEqual(self.p,before)

    def test_at_completion_time_it_cannot_be_cancelled(self):
        task=self.order(); self.w.now=task['ends_at']
        before=copy.deepcopy(self.p)
        with self.assertRaises(GameError): self.cancel()
        self.assertEqual(before,self.p)

    def test_finished_job_is_not_refunded(self):
        task=copy.deepcopy(self.order())
        self.w._complete_queue(self.p)
        resources=copy.deepcopy(self.p['resources'])
        with self.assertRaises(GameError): self.cancel(task)
        self.assertEqual(resources,self.p['resources'])

    def test_other_accounts_cannot_cancel(self):
        task=copy.deepcopy(self.order())
        pid=self.w.register('OtherCancel',PASSWORD)['state']['player']['id']
        before=copy.deepcopy(self.p)
        with self.assertRaises(GameError):
            self.w.action(pid,{'type':'cancel_project','planet_id':self.p['id'],'queue_id':task['id']})
        self.assertEqual(before,self.p)

    def test_client_cannot_choose_a_refund(self):
        before=copy.deepcopy(self.p['resources'])
        self.order(); self.cancel(paid_cost={'metal':999999999},refund=999999999)
        self.assertEqual(before,self.p['resources'])

    def test_malformed_receipt_fails_without_losing_the_project(self):
        task=self.order(); task['paid_cost']['metal']=-99
        before=copy.deepcopy(self.p)
        with self.assertRaises(GameError): self.cancel()
        self.assertEqual(before,self.p)

    def test_missing_legacy_receipt_cancels_without_refund(self):
        task=self.order(); task.pop('paid_cost')
        before=copy.deepcopy(self.p['resources'])
        response=self.cancel()
        self.assertIn('Bez zwrotu',response['message'])
        self.assertEqual(before,self.p['resources']); self.assertEqual([],self.p['queue'])

    def test_no_recycling_or_other_completion_bonuses(self):
        self.w._player(self.pid)['research']['recycling']=10
        before=copy.deepcopy(self.p['resources'])
        task=self.order('ship','frigate',3)
        self.assertTrue(any(task['construction_refund'].values()))
        self.cancel()
        self.assertEqual(before,self.p['resources'])

    def test_refund_uses_original_cost_after_balance_or_research_changes(self):
        before=copy.deepcopy(self.p['resources']); task=copy.deepcopy(self.order())
        self.w._player(self.pid)['research']['recycling']=20
        self.p['buildings']['metal_mine']=12
        self.cancel(task)
        self.assertEqual(before,self.p['resources'])

    def test_storage_cap_applies(self):
        self.order(); self.p['resources']['metal']=MAX_RESOURCE-1
        self.cancel(); self.assertEqual(MAX_RESOURCE,self.p['resources']['metal'])

    def test_concurrent_requests_refund_once(self):
        before=copy.deepcopy(self.p['resources']); task=copy.deepcopy(self.order())
        def attempt(index):
            try: self.cancel(task,request_id=f'parallel-{index}'); return True
            except GameError: return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            result=list(pool.map(attempt,range(8)))
        self.assertEqual(1,sum(result)); self.assertEqual(before,self.p['resources'])

    def test_failed_commit_restores_project_wallet_and_request_cache(self):
        self.order(); before=copy.deepcopy(self.w.data)
        with patch.object(self.w,'_save',side_effect=sqlite3.OperationalError('forced disk failure')):
            with self.assertRaises(GameError): self.cancel()
        self.assertEqual(before,self.w.data)

    def test_receipts_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'world.sqlite3'
            world=World(file,now=NOW)
            pid=world.register('PersistCancel',PASSWORD)['state']['player']['id']
            planet=world._owned(pid); before=copy.deepcopy(planet['resources'])
            world.action(pid,{'type':'build','key':'metal_mine'})
            task=copy.deepcopy(planet['queue'][0]); world.close()
            world=World(file,now=NOW)
            try:
                self.assertEqual(task,world._owned(pid)['queue'][0])
                world.action(pid,{'type':'cancel_project','queue_id':task['id']})
                self.assertEqual(before,world._owned(pid)['resources'])
            finally: world.close()

class BalanceResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'private_test.sqlite3'
        self.w=World(self.path,now=NOW)
        self.users=[]
        for i,race in enumerate(('zetans','automatons','symbionts','')):
            response=self.w.register(f'OldEmpire{i}',PASSWORD)
            pid=response['state']['player']['id']
            if race: self.w.action(pid,{'type':'choose_race','race_id':race})
            planet=self.w._owned(pid)
            planet['resources']=dict.fromkeys(RESOURCES,999999.0)
            planet['buildings']['metal_mine']=12
            self.w._player(pid)['swarm_crystals']=999
            self.w._player(pid)['research']['weapons']=9
            self.users.append((pid,race,response['token']))
        self.code=self.w.account_recovery_code(self.users[0][2],PASSWORD)['recovery_code']
        self.original_accounts=self.w.db.execute('SELECT * FROM accounts ORDER BY id').fetchall()
        self.original_recovery=self.w.db.execute('SELECT * FROM account_recovery ORDER BY player_id').fetchall()
        self.w.data.pop('balance_reset_id',None) # Simulate a pre-0.7.2 DB.
        self.w._save(); self.old=copy.deepcopy(self.w.data)
        self.w.close(); self.w=None
        self.addCleanup(self.close_world)

    def close_world(self):
        if self.w: self.w.close(); self.w=None

    def reset(self):
        self.w=World(self.path,now=NOW+86400,apply_balance_reset=True)
        return self.w

    def test_accounts_passwords_recovery_and_races_survive(self):
        self.reset()
        self.assertEqual(self.original_accounts,self.w.db.execute('SELECT * FROM accounts ORDER BY id').fetchall())
        self.assertEqual(self.original_recovery,self.w.db.execute('SELECT * FROM account_recovery ORDER BY player_id').fetchall())
        self.assertEqual(0,self.w.db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0])
        for pid,race,token in self.users:
            self.assertEqual(race,self.w._player(pid)['race_id'])
            with self.assertRaises(GameError): self.w.authenticate(token)
            name=self.w._player(pid)['name']
            self.assertEqual(pid,self.w.login(name,PASSWORD)['state']['player']['id'])

    def test_only_one_colony_and_default_balance_per_player(self):
        self.reset()
        for pid,race,_ in self.users:
            own=[p for p in self.w.data['planets'].values() if p['owner_id']==pid]
            self.assertEqual(1,len(own)); planet=own[0]
            self.assertEqual({'metal':4000.0,'crystal':2600.0,'fuel':1400.0},planet['resources'])
            self.assertTrue(all(planet['buildings'][k]==(0 if k=='observatory' else 1) for k in main.BUILDINGS))
            self.assertEqual({},planet['defenses']); self.assertEqual([],planet['queue'])
            player=self.w._player(pid)
            self.assertEqual(0,player['swarm_crystals']); self.assertEqual({},player['scout_intel'])
            self.assertTrue(all(level==0 for level in player['research'].values()))
            self.assertEqual(skill_tree.unlocked_for(race,[]),player['skill_nodes'])
            self.assertEqual({},player['requests']); self.assertEqual(NOW+2*86400,player['protected_until'])
        self.assertEqual({},self.w.data['fleets'])

    def test_six_starting_hives_and_slow_economy(self):
        self.reset()
        for galaxy in ('g1','g2','g3','g4','g5','g6'):
            hives=[p for p in self.w.data['planets'].values() if p['owner_id']=='khar' and p['galaxy_id']==galaxy]
            self.assertEqual(1,len(hives))
        self.assertEqual(0.1,main.ECONOMY_MULTIPLIER)

    def test_backup_is_full_standalone_old_database(self):
        self.reset()
        files=list((self.path.parent/'reset-backups').glob('*.sqlite3'))
        self.assertEqual(1,len(files))
        db=sqlite3.connect(files[0])
        try:
            self.assertEqual([('ok',)],db.execute('PRAGMA integrity_check').fetchall())
            self.assertEqual(self.old,json.loads(db.execute('SELECT body FROM snapshot').fetchone()[0]))
            self.assertEqual(self.original_accounts,db.execute('SELECT * FROM accounts ORDER BY id').fetchall())
            self.assertEqual(self.original_recovery,db.execute('SELECT * FROM account_recovery ORDER BY player_id').fetchall())
            self.assertGreater(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],0)
        finally: db.close()
        self.assertFalse(list(files[0].parent.glob('*.part*')))

    def test_restart_never_resets_twice(self):
        self.reset(); self.w._owned(self.users[0][0])['resources']['metal']=1234
        stamp=self.w.data['balance_reset_at']; self.close_world()
        self.w=World(self.path,now=NOW+86400,apply_balance_reset=True)
        self.assertEqual(1234,self.w._owned(self.users[0][0])['resources']['metal'])
        self.assertEqual(stamp,self.w.data['balance_reset_at'])
        self.assertEqual(1,len(list((self.path.parent/'reset-backups').glob('*.sqlite3'))))

    def test_backup_failure_prevents_reset(self):
        with patch('server.balance_reset.verified_reset_backup',side_effect=OSError('no space')):
            with self.assertRaises(OSError): self.reset()
        db=sqlite3.connect(self.path)
        try: self.assertEqual(self.old,json.loads(db.execute('SELECT body FROM snapshot').fetchone()[0]))
        finally: db.close()

    def test_failed_write_rolls_back_and_keeps_old_sessions(self):
        self.w=World(self.path,now=NOW)
        before=copy.deepcopy(self.w.data)
        sessions=self.w.db.execute('SELECT * FROM sessions ORDER BY token_hash').fetchall()
        with patch.object(self.w,'_save',side_effect=sqlite3.OperationalError('forced')):
            with self.assertRaises(GameError): self.w._apply_balance_reset()
        self.assertEqual(before,self.w.data)
        self.assertEqual(sessions,self.w.db.execute('SELECT * FROM sessions ORDER BY token_hash').fetchall())

    def test_inconsistent_accounts_fail_closed(self):
        db=sqlite3.connect(self.path)
        data=copy.deepcopy(self.old); data['players'].pop(self.users[0][0])
        db.execute('UPDATE snapshot SET body=?',(json.dumps(data),));db.commit();db.close()
        with self.assertRaises(RuntimeError): self.reset()
        db=sqlite3.connect(self.path)
        try: self.assertEqual(data,json.loads(db.execute('SELECT body FROM snapshot').fetchone()[0]))
        finally: db.close()

    def test_recovery_code_works_after_reset(self):
        self.reset(); pid=self.users[0][0]; name=self.w._player(pid)['name']
        response=self.w.recover_account(name,self.code,'ReplacementPassword072!')
        self.assertEqual(pid,response['state']['player']['id'])

    def test_new_world_marked_without_destructive_reset(self):
        another=Path(self.tmp.name)/'new.sqlite3'
        w=World(another,now=NOW,apply_balance_reset=True)
        try:
            self.assertEqual(balance_reset.BALANCE_RESET_ID,w.data['balance_reset_id'])
            self.assertNotIn('balance_reset_at',w.data)
            w.register('FreshPlayer',PASSWORD)
        finally: w.close()
        w=World(another,now=NOW,apply_balance_reset=True)
        try: self.assertEqual(1,len(w.data['players'])); self.assertNotIn('balance_reset_at',w.data)
        finally: w.close()

class UISource072Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.source=(ROOT/'client/scripts/main.gd').read_text()
    def method(self,name): return self.source.split(f'func {name}(',1)[1].split('\n\nfunc ',1)[0]
    def test_nav_is_bound_to_full_map(self):
        self.assertIn('_open_galaxy_map if index == 1',self.source)
        self.assertIn('_show_full_galaxy_map()',self.method('_open_galaxy_map'))
        self.assertIn('"reset_view"',self.method('_show_full_galaxy_map'))
        self.assertIn('set_deferred("scroll_vertical", 0)',self.method('_show_full_galaxy_map'))
    def test_no_redundant_swarm_overview(self): self.assertNotIn('SwarmOverview',self.source)
    def test_galaxy_arrows_cycle_without_sending_missions(self):
        for key in ('PreviousGalaxy','NextGalaxy'): self.assertIn(key,self.source)
        self.assertIn('posmod(',self.method('_step_galaxy'));self.assertNotIn('_request',self.method('_step_galaxy'))
    def test_dock_is_outside_scroll_before_navigation(self):
        app=self.method('_make_app')
        self.assertLess(app.index('shell.add_child(fleet_action_bar)'),app.index('var navigation:'))
        fleet=self.method('_make_fleet_tab')
        self.assertIn('dock_buttons.add_child(preview_button)',fleet);self.assertIn('dock_buttons.add_child(send_button)',fleet)
        self.assertNotIn('form.add_child(send_button)',fleet)
    def test_dock_only_in_missions(self):
        self.assertIn('current_tab == 2 and fleet_mode == 0',self.source)
        self.assertIn('index == 2 and fleet_mode == 0',self.method('_open_tab'))
    def test_defense_is_after_all_ships(self):
        fleet=self.method('_make_fleet_tab')
        self.assertLess(fleet.index('fleet_build_view.add_child(ship_list)'),fleet.index('fleet_build_view.add_child(defense_section)'))
    def test_cancellation_confirmation_uses_captured_task_and_planet(self):
        self.assertIn('ConfirmationDialog.new()',self.source)
        self.assertIn('project_ui.find_task(str(payload.get("queue_id"',self.method('_confirm_cancel_project'))
        self.assertIn('payload.get("planet_id"',self.method('_confirm_cancel_project'))
    def test_launchers_opt_into_reset_but_http_has_no_reset_route(self):
        source=(ROOT/'server/main.py').read_text()
        self.assertIn('max_players=args.max_players, apply_balance_reset=True',source)
        self.assertNotIn('"/api/reset"',source)
    def test_server_and_railway_identical(self):
        for path in (ROOT/'server').glob('*.py'):
            target=ROOT/'railway'/('app.py' if path.name=='main.py' else path.name)
            self.assertEqual(path.read_bytes(),target.read_bytes(),path.name)

if __name__=='__main__': unittest.main()
