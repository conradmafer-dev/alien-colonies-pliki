"""Burst of concurrent beta players against a real, local HTTP server."""
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import threading
import unittest
from unittest.mock import patch

from server.main import build_server
from tests.world_fixture import LocalTestWorld as World


class PublicBetaBurst(unittest.TestCase):
    def test_fifteen_players_retry_orders_without_cross_account_or_duplicate_spending(self):
        world = World(':memory:', max_players=15, now=1_900_000_000)
        users = []
        for i in range(15):
            auth = world.register(f'BetaPilot{i:02}', 'local-test-password')
            pid = auth['state']['player']['id']
            world.action(pid, {'type':'choose_race', 'race_id':('zetans','symbionts','automatons')[i % 3]})
            state = world.state(pid)
            price = next(x['cost'] for x in state['catalog']['buildings'] if x['key']=='metal_mine')
            users.append((pid, auth['token'], state['resources'], price))
        server = build_server(world, '127.0.0.1', 0)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval':.01}, daemon=True)
        thread.start()

        def order(user):
            pid, token, before, cost = user
            conn = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=10)
            try:
                conn.request('POST','/api/action',json.dumps({'type':'build','key':'metal_mine','request_id':'retry-after-mobile-timeout'}),
                             {'Content-Type':'application/json','Authorization':'Bearer '+token,'X-PGR-Client-Version':'17'})
                response=conn.getresponse()
                payload=json.loads(response.read())
                self.assertEqual(response.status,200,payload)
                self.assertEqual(payload['state']['player']['id'],pid)
                self.assertEqual(len(payload['state']['queue']),1)
                return pid, payload['state']['queue'][0]['id']
            finally:
                conn.close()
        try:
            # Freeze wall time, not HTTP concurrency: production cannot obscure payment assertions.
            with patch('server.main.time.time',return_value=world.now):
                with ThreadPoolExecutor(max_workers=15) as pool:
                    results=list(pool.map(order, users*3))
            for pid, token, before, cost in users:
                state=world.state(pid)
                self.assertEqual(state['resources'],{k:before[k]-cost[k] for k in before})
                self.assertEqual(len(state['queue']),1)
                ids={queue_id for owner,queue_id in results if owner==pid}
                self.assertEqual(len(ids),1)
            self.assertEqual(len(world.data['players']),15)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            world.close()


if __name__=='__main__':
    unittest.main()
