"""Real SQLite/HTTP checks for chat privacy, durability and safe retries."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from server.main import World, GameError, build_server

PASSWORD = 'communication-test-123'
START = 2_000_000_000


class CommunicationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'world.sqlite3'
        self.w = World(self.path, now=START)
        self.accounts = [self.w.register(name, PASSWORD) for name in ('ChatAlice', 'ChatBob', 'ChatCarol')]
        self.a, self.b, self.c = [account['state']['player']['id'] for account in self.accounts]
        self.sequence = 0

    def tearDown(self):
        self.w.close()

    def send(self, sender, peer='', text='Hello 👽'):
        self.w.now += 4
        self.sequence += 1
        return self.w.chat_send(sender, {'peer_id': peer, 'text': text, 'request_id': f'message-{self.sequence:08d}'})['sent']

    def test_private_content_only_reaches_participants(self):
        message = self.send(self.a, self.b, 'Private treaty')
        self.assertEqual(self.w.chat_feed(self.a,self.b)['messages'][0]['text'], 'Private treaty')
        self.assertEqual(self.w.chat_feed(self.b,self.a)['messages'][0]['id'], message['id'])
        for peer in ('',self.a,self.b):
            self.assertEqual(self.w.chat_feed(self.c,peer)['messages'], [])
        self.assertEqual(self.w.chat_inbox(self.c)['threads'], [])
        self.assertNotIn('Private treaty', json.dumps(self.w.state(self.c)))
        self.assertNotIn('Private treaty', json.dumps(self.w.data))

    def test_global_and_private_unread_are_independent(self):
        public = self.send(self.a, text='Public hello')
        private = self.send(self.a, self.b)
        self.assertEqual(self.w.chat_summary(self.b)['unread'],2)
        self.assertEqual(self.w.chat_summary(self.c)['unread'],1)
        self.assertEqual(self.w.chat_summary(self.a)['unread'],0)
        self.w.chat_read(self.b,{'last_id':public['id']})
        self.assertEqual(self.w.chat_summary(self.b)['global_unread'],0)
        self.assertEqual(self.w.chat_summary(self.b)['private_unread'],1)
        self.w.chat_read(self.b,{'peer_id':self.a,'last_id':private['id']})
        self.assertEqual(self.w.chat_summary(self.b)['unread'],0)

    def test_retry_is_idempotent_even_during_rate_limit(self):
        payload={'peer_id':self.b,'text':'One message','request_id':'same-request-123'}
        first=self.w.chat_send(self.a,payload)['sent']
        self.assertEqual(self.w.chat_send(self.a,payload)['sent'],first)
        self.assertEqual(len(self.w.chat_feed(self.b,self.a)['messages']),1)
        with self.assertRaises(GameError) as conflict:
            self.w.chat_send(self.a,{**payload,'text':'Changed'})
        self.assertEqual(conflict.exception.status,409)
        with self.assertRaises(GameError):
            self.w.chat_send(self.a,{**payload,'peer_id':self.c})

    def test_read_marker_never_skips_future_messages_or_other_channels(self):
        first=self.send(self.a,self.b)
        unrelated=self.send(self.c,self.a)
        self.w.chat_read(self.b,{'peer_id':self.a,'last_id':unrelated['id']+999999})
        marker=self.w.db.execute('SELECT last_id FROM chat_reads WHERE owner=? AND channel=?',(self.b,self.a)).fetchone()[0]
        self.assertEqual(marker,first['id'])
        second=self.send(self.a,self.b)
        self.assertEqual(self.w.chat_summary(self.b)['unread'],1)
        self.w.chat_read(self.b,{'peer_id':self.a,'last_id':first['id']})
        self.assertEqual(self.w.chat_summary(self.b)['unread'],1)
        self.assertGreater(second['id'],first['id'])

    def test_block_hides_global_and_stops_direct_messages_both_ways(self):
        self.send(self.a,text='Old global')
        self.send(self.a,self.b)
        self.w.chat_block(self.b,{'peer_id':self.a,'blocked':True})
        self.assertEqual(self.w.chat_feed(self.b)['messages'],[])
        self.assertEqual(self.w.chat_summary(self.b)['unread'],0)
        for sender,peer in [(self.a,self.b),(self.b,self.a)]:
            with self.assertRaises(GameError) as blocked:
                self.send(sender,peer)
            self.assertEqual(blocked.exception.status,403)
        self.w.chat_block(self.b,{'peer_id':self.a,'blocked':False})
        self.send(self.a,self.b,'Works again')
        self.assertEqual(self.w.chat_feed(self.b,self.a)['messages'][-1]['text'],'Works again')

    def test_message_paging_has_no_duplicates_and_orders_by_id(self):
        ids=[self.send(self.a,self.b,str(index))['id'] for index in range(55)]
        page=self.w.chat_feed(self.b,self.a)
        self.assertTrue(page['has_older'])
        self.assertEqual([m['id'] for m in page['messages']],ids[5:])
        earlier=self.w.chat_feed(self.b,self.a,before=ids[5])
        self.assertFalse(earlier['has_older'])
        self.assertEqual([m['id'] for m in earlier['messages']],ids[:5])
        recent=self.w.chat_feed(self.b,self.a,after=ids[-3])
        self.assertEqual([m['id'] for m in recent['messages']],ids[-2:])

    def test_validation_does_not_store_invalid_text_or_targets(self):
        for text in ('', '   ', '\x00\x01', 'x'*501, '\n'.join(['a']*11), None, ['hello']):
            with self.subTest(text=repr(text)[:30]), self.assertRaises(GameError):
                self.send(self.a,self.b,text)
        for peer in (self.a,'khar','missing',None,{},[],'x'*1000):
            with self.subTest(peer=repr(peer)[:30]), self.assertRaises(GameError):
                self.send(self.a,peer)
        self.assertEqual(self.w.chat_feed(self.b,self.a)['messages'],[])
        self.assertEqual(len(self.send(self.a,self.b,'👽'*500)['text']),500)
        plain=self.send(self.a,self.b,'[url=https://example.com]plain[/url]')
        self.assertEqual(plain['text'],'[url=https://example.com]plain[/url]')

    def test_rate_limit_is_shared_across_channels_and_retry_safe(self):
        self.send(self.a,self.b)
        with self.assertRaises(GameError) as fast:
            self.w.chat_send(self.a,{'peer_id':self.c,'text':'Too fast','request_id':'rate-check-123'})
        self.assertEqual(fast.exception.status,429)
        self.w.now += 3
        self.w.chat_send(self.a,{'peer_id':self.c,'text':'Allowed','request_id':'rate-check-123'})

    def test_moderation_reports_require_visible_message_and_are_unique(self):
        private=self.send(self.a,self.b)
        for viewer in (self.a,self.c):
            with self.assertRaises(GameError) as hidden:
                self.w.chat_report(viewer,{'message_id':private['id']})
            self.assertEqual(hidden.exception.status,404)
        for _ in range(2):
            self.w.chat_report(self.b,{'message_id':private['id']})
        self.assertEqual(self.w.db.execute('SELECT COUNT(*) FROM chat_reports').fetchone()[0],1)
        self.w.db.execute('INSERT INTO chat_mutes VALUES(?,?)',(self.a,self.w.now+3600))
        self.w.db.commit()
        with self.assertRaises(GameError) as muted:
            self.send(self.a)
        self.assertEqual(muted.exception.status,403)

    def test_restart_keeps_messages_blocks_and_read_positions(self):
        self.send(self.a,text='Persistent')
        message=self.send(self.b,self.a,'Private persistent')
        self.w.chat_read(self.a,{'peer_id':self.b,'last_id':message['id']})
        self.w.chat_block(self.a,{'peer_id':self.c,'blocked':True})
        at=self.w.now
        self.w.close()
        self.w=World(self.path,now=at)
        self.assertEqual(self.w.chat_feed(self.a,self.b)['messages'][0]['text'],'Private persistent')
        self.assertEqual(self.w.chat_summary(self.a)['unread'],0)
        self.assertTrue(self.w.chat_feed(self.a,self.c)['permissions']['blocked_by_you'])

    def test_failed_commit_does_not_publish_message(self):
        with patch.object(self.w,'_save',side_effect=OSError('disk unavailable')):
            with self.assertRaises(GameError) as failure:
                self.send(self.a,self.b,'Not committed')
        self.assertEqual(failure.exception.status,503)
        self.assertEqual(self.w.chat_feed(self.b,self.a)['messages'],[])
        self.assertEqual(self.w.chat_summary(self.b)['unread'],0)

    def test_account_deletion_removes_its_chat_data(self):
        self.send(self.a,text='Delete public')
        private=self.send(self.a,self.b,'Delete private')
        self.w.chat_report(self.b,{'message_id':private['id']})
        self.w.chat_block(self.c,{'peer_id':self.a,'blocked':True})
        self.w.account_delete(self.accounts[0]['token'],PASSWORD,'DELETE ACCOUNT')
        self.assertEqual(self.w.db.execute('SELECT COUNT(*) FROM chat_messages').fetchone()[0],0)
        self.assertEqual(self.w.db.execute('SELECT COUNT(*) FROM chat_reports').fetchone()[0],0)
        self.assertEqual(self.w.db.execute('SELECT COUNT(*) FROM chat_blocks').fetchone()[0],0)
        self.assertEqual(self.w.chat_inbox(self.b)['threads'],[])

    def test_history_retention_and_new_account_baseline(self):
        self.send(self.a,text='Historical')
        newcomer=self.w.register('New Chat Player',PASSWORD)['state']['player']['id']
        self.assertEqual(self.w.chat_summary(newcomer)['unread'],0)
        self.assertEqual(len(self.w.chat_feed(newcomer)['messages']),0)
        self.w.now += 31*86400
        self.assertEqual(self.w.chat_feed(self.b)['messages'],[])
        self.assertEqual(self.w.chat_summary(self.b)['unread'],0)
        self.send(self.a,text='Current')
        self.assertEqual(self.w.db.execute('SELECT COUNT(*) FROM chat_messages').fetchone()[0],1)

    def test_http_authentication_and_recipient_isolation(self):
        server=build_server(self.w,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        def request(path, account=None, payload=None):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_address[1],timeout=5)
            headers={'Content-Type':'application/json','Accept-Language':'en'}
            if account is not None:
                headers['Authorization']='Bearer '+self.accounts[account]['token']
            conn.request('POST' if payload is not None else 'GET',path,json.dumps(payload) if payload is not None else None,headers)
            response=conn.getresponse()
            status,data=response.status,json.loads(response.read())
            conn.close()
            return status,data
        try:
            self.assertEqual(request('/api/chat')[0],401)
            self.assertEqual(request('/api/chat/send',payload={'text':'Forged'})[0],401)
            status,data=request('/api/chat/send',0,{'peer_id':self.b,'sender_id':self.c,'text':'HTTP private','request_id':'http-message-123'})
            self.assertEqual(status,200)
            self.assertEqual(data['sent']['sender_id'],self.a)
            self.assertEqual(request('/api/chat?peer_id='+self.a,1)[1]['messages'][0]['text'],'HTTP private')
            self.assertEqual(request('/api/chat?peer_id='+self.a,2)[1]['messages'],[])
            self.assertEqual(request('/api/chat/inbox',2)[1]['threads'],[])
            self.assertEqual(request('/api/chat?before=bad',1)[0],400)
            self.assertEqual(request('/api/chat?before=9999999999999999999999',1)[0],400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__=='__main__':
    unittest.main()
