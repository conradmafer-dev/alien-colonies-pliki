import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import app
import rankings


class EmpireRenameTests(unittest.TestCase):
    def setUp(self):
        self.world = app.World(':memory:')
        self.account = self.world.register('Old Empire', 'rename-test-password')
        self.player = self.account['state']['player']['id']
        self.token = self.account['token']

    def tearDown(self):
        self.world.close()

    def test_identity_progress_sessions_and_password_login_survive(self):
        before = copy.deepcopy(self.world._player(self.player))
        planets = copy.deepcopy(self.world.data['planets'])
        sessions = self.world.db.execute('SELECT * FROM sessions').fetchall()
        response = self.world.account_rename(self.token, '  New Empire  ')
        self.assertEqual(response['name'], 'New Empire')
        self.assertEqual(response['state']['player']['id'], self.player)
        self.assertEqual(self.world.data['planets'], planets)
        self.assertEqual(self.world.db.execute('SELECT * FROM sessions').fetchall(), sessions)
        self.assertEqual(self.world.authenticate(self.token), self.player)
        for key, value in before.items():
            if key not in ('name', 'activity', 'trait_intel'):
                self.assertEqual(self.world._player(self.player)[key], value, key)
        self.assertEqual(rankings.view(self.world, self.player)['self']['name'], 'New Empire')
        self.assertEqual(self.world.login('New Empire', 'rename-test-password')['state']['player']['id'], self.player)
        with self.assertRaises(app.GameError):
            self.world.login('Old Empire', 'rename-test-password')

    def test_duplicate_invalid_and_expired_requests_preserve_name(self):
        self.world.register('Other Empire', 'rename-test-password')
        for name in ('OTHER EMPIRE', '', 'xy', 'x' * 21, '<script>', None, True):
            with self.subTest(name=name), self.assertRaises(app.GameError):
                self.world.account_rename(self.token, name)
            self.assertEqual(self.world._player(self.player)['name'], 'Old Empire')
        with self.assertRaises(app.GameError):
            self.world.account_rename('invalid-session', 'Unauthorised')

    def test_unicode_normalization_and_case_change(self):
        response = self.world.account_rename(self.token, 'Ｏｌｄ Ｅｍｐｉｒｅ')
        self.assertEqual(response['name'], 'Old Empire')
        self.world.account_rename(self.token, 'OLD EMPIRE')
        self.assertEqual(self.world._player(self.player)['name'], 'OLD EMPIRE')

    def test_storage_failure_rolls_back_both_world_and_login_key(self):
        with patch.object(self.world, '_save', side_effect=OSError('simulated storage failure')):
            with self.assertRaises(app.GameError) as raised:
                self.world.account_rename(self.token, 'Unsaved Empire')
            self.assertEqual(raised.exception.status, 503)
        self.assertEqual(self.world._player(self.player)['name'], 'Old Empire')
        self.assertEqual(self.world.db.execute('SELECT name_key FROM accounts WHERE id=?', (self.player,)).fetchone()[0], 'old empire')

    def test_http_requires_session_and_ignores_supplied_other_player_id(self):
        other = self.world.register('Other Empire', 'rename-test-password')['state']['player']['id']
        server = app.build_server(self.world, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def request(token):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=5)
                headers = {'Content-Type': 'application/json', 'X-PGR-Client-Version': '93'}
                if token:
                    headers['Authorization'] = 'Bearer ' + token
                connection.request('POST', '/api/account/rename', json.dumps({'name': 'Renamed Empire', 'player_id': other}), headers)
                response = connection.getresponse()
                result = (response.status, json.loads(response.read()))
                connection.close()
                return result
            self.assertEqual(request(None)[0], 401)
            code, response = request(self.token)
            self.assertEqual(code, 200, response)
            self.assertEqual(self.world._player(other)['name'], 'Other Empire')
            self.assertEqual(self.world._player(self.player)['name'], 'Renamed Empire')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
