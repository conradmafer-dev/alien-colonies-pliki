import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World
import push_notifications as push

NOW=1_900_000_000.0

class PushTests(unittest.TestCase):
    def setUp(self):
        self.world=World(':memory:',now=NOW)
        self.first=self.world.register('Push first','fixture-password-123',_google_verified=True)
        self.second=self.world.register('Push second','fixture-password-123',_google_verified=True)
        self.pid=self.first['state']['player']['id']
        self.other=self.second['state']['player']['id']
    def tearDown(self):
        self.world.close()
    def subscribe(self,token='device_'+('a'*150),player=None,session=None):
        return push.register(self.world,player or self.pid,session or self.first['token'],{'token':token,'language':'en'})
    def count(self):
        return self.world.db.execute('SELECT count(*) FROM push_outbox').fetchone()[0]
    def report(self):
        with self.world._atomic():
            self.world._report(self.pid,'Atak na kolonię','Raport '+('x'*1000))
    def test_no_historical_reports_and_only_the_correct_empire_receives_new_reports(self):
        self.subscribe()
        self.assertEqual(self.count(),0)
        with self.world._atomic():
            self.world._report(self.other,'Other report','Other empire')
        self.assertEqual(self.count(),0)
        self.report()
        row=self.world.db.execute('SELECT player_id,payload FROM push_outbox').fetchone()
        data=json.loads(row[1])
        self.assertEqual(row[0],self.pid)
        self.assertEqual(data['player_id'],self.pid)
        self.assertEqual(data['kind'],'attack')
        self.assertLessEqual(len(data['body']),300)
    def test_public_configuration_never_exposes_server_credentials(self):
        public={'project_id':'test-project','sender_id':'12345','app_id':'1:12345:android:example','api_key':'public-key'}
        account={'project_id':'test-project','private_key':'server-only-private-fixture'}
        with patch.dict('os.environ',{'ALIEN_FIREBASE_ANDROID_CONFIG_JSON':json.dumps(public),
                                    'ALIEN_FIREBASE_SERVICE_ACCOUNT_JSON':json.dumps(account)}):
            self.assertEqual(push.configuration(),{'configured':True,**public})
            self.assertNotIn('private_key',push.configuration())
    def test_malformed_or_mismatched_firebase_configuration_stays_inactive(self):
        for raw,account in [('[]','{}'),('{}','[]'),('{','{}'),
             (json.dumps({'project_id':'one','sender_id':'123','app_id':'a','api_key':'b'}),
              json.dumps({'project_id':'two','private_key':'fixture'}))]:
            with patch.dict('os.environ',{'ALIEN_FIREBASE_ANDROID_CONFIG_JSON':raw,'ALIEN_FIREBASE_SERVICE_ACCOUNT_JSON':account}):
                self.assertEqual(push.configuration(),{'configured':False})
    def test_failed_game_action_never_commits_a_push(self):
        self.subscribe()
        with self.assertRaises(RuntimeError):
            with self.world._atomic():
                self.world._report(self.pid,'Rollback','Must not send')
                raise RuntimeError('fixture action failure')
        self.assertEqual(self.count(),0)
    def test_logout_cascades_device_and_queued_reports(self):
        self.subscribe();self.report()
        self.world.logout(self.first['token'])
        self.assertEqual(self.count(),0)
        self.assertEqual(self.world.db.execute('SELECT count(*) FROM push_devices').fetchone()[0],0)
    def test_installation_switching_accounts_discards_old_empire_reports(self):
        token='device_'+('a'*150)
        self.subscribe(token);self.report()
        self.subscribe(token,self.other,self.second['token'])
        self.assertEqual(self.count(),0)
        self.report()
        self.assertEqual(self.count(),0)
    def test_duplicate_requeue_is_idempotent(self):
        self.subscribe();self.report()
        report=self.world.data['players'][self.pid]['reports'][0]
        with self.world._atomic():
            push.enqueue_report(self.world,self.pid,report)
        self.assertEqual(self.count(),1)
    def test_invalid_registration_and_mismatched_session_are_rejected(self):
        for token in ('', 'a', 'x'*4097, '<script>'+('a'*100)):
            with self.assertRaises(Exception):
                self.subscribe(token)
        with self.assertRaises(Exception):
            self.subscribe(player=self.pid,session=self.second['token'])
    def test_unconfigured_push_does_not_attempt_external_delivery(self):
        self.subscribe();self.report()
        class Sender:
            def send(self,*args):raise AssertionError('must stay offline')
        with patch.dict('os.environ',{},clear=True):
            self.assertEqual(push.configuration(),{'configured':False})
            self.assertEqual(push.deliver_due(self.world,Sender()),0)
        self.assertEqual(self.count(),1)
    def test_delivery_is_outside_world_lock_and_only_after_commit(self):
        self.subscribe();self.report()
        world=self.world;calls=[]
        class Sender:
            def send(self,token,data):
                self_outer.assertFalse(world.lock._is_owned())
                self_outer.assertFalse(world.db.in_transaction)
                calls.append(data)
                return 'sent'
        self_outer=self
        with patch.object(push,'configuration',return_value={'configured':True}):
            self.assertEqual(push.deliver_due(world,Sender()),1)
            self.assertEqual(push.deliver_due(world,Sender()),0)
        self.assertEqual(len(calls),1);self.assertEqual(self.count(),0)
    def test_retries_are_persisted_and_invalid_tokens_removed(self):
        self.subscribe();self.report()
        class Sender:
            result='retry'
            def send(self,*args):return self.result
        sender=Sender()
        with patch.object(push,'configuration',return_value={'configured':True}):
            push.deliver_due(self.world,sender)
            self.assertEqual(self.world.db.execute('SELECT attempts,next_at FROM push_outbox').fetchone(),(1,NOW+30))
            self.world.now+=31;sender.result='unregistered'
            push.deliver_due(self.world,sender)
        self.assertEqual(self.count(),0)
        self.assertEqual(self.world.db.execute('SELECT count(*) FROM push_devices').fetchone()[0],0)
    def test_unregistration_does_not_delete_another_session_device(self):
        self.subscribe()
        push.unregister(self.world,self.other,self.second['token'])
        self.assertEqual(self.world.db.execute('SELECT count(*) FROM push_devices').fetchone()[0],1)
        push.unregister(self.world,self.pid,self.first['token'])
        self.assertEqual(self.world.db.execute('SELECT count(*) FROM push_devices').fetchone()[0],0)

if __name__=='__main__':unittest.main()

