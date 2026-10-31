"""Registration is an immutable boundary for public chat history."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app


PASSWORD = 'chat-visibility-test-password'
NOW = 2_000_000_000


class ChatVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'world.sqlite3'
        self.world = app.World(self.path, now=NOW)
        self.first = self.register('First player')
        self.second = self.register('Second player')
        self.sequence = 0

    def tearDown(self):
        self.world.close()

    def register(self, name):
        return self.world.register(name, PASSWORD)['state']['player']['id']

    def send(self, sender, text, peer='', advance=4):
        self.world.now += advance
        self.sequence += 1
        return self.world.chat_send(sender, {
            'text': text, 'peer_id': peer,
            'request_id': f'visibility-{self.sequence:08d}',
        })['sent']

    def ids(self, player, **query):
        return [message['id'] for message in self.world.chat_feed(player, **query)['messages']]

    def boundary(self, player):
        return self.world.db.execute(
            'SELECT after_id FROM chat_visibility WHERE owner=?', (player,)
        ).fetchone()[0]

    def test_old_messages_hidden_but_later_same_clock_message_visible(self):
        old = self.send(self.first, 'Before account')
        newcomer = self.register('New player')
        current = self.send(self.second, 'After account in same clock tick', advance=0)
        self.assertEqual(old['at'], current['at'])
        self.assertEqual(self.boundary(newcomer), old['id'])
        self.assertEqual(self.ids(newcomer), [current['id']])
        self.assertEqual(self.ids(self.first), [old['id'], current['id']])
        self.assertEqual(self.world.chat_summary(newcomer)['global_unread'], 1)

    def test_boundary_uses_latest_message_even_when_it_is_private(self):
        public = self.send(self.first, 'Old public')
        private = self.send(self.first, 'Old private', peer=self.second)
        newcomer = self.register('New player')
        self.assertGreater(private['id'], public['id'])
        self.assertEqual(self.boundary(newcomer), private['id'])
        self.assertEqual(self.ids(newcomer), [])
        self.assertEqual(self.world.chat_inbox(newcomer)['threads'], [])
        self.assertEqual(self.world.chat_summary(newcomer)['unread'], 0)
        current = self.send(self.second, 'Direct welcome', peer=newcomer)
        self.assertEqual(self.ids(newcomer, peer=self.second), [current['id']])
        self.assertEqual(self.world.chat_summary(newcomer)['private_unread'], 1)

    def test_before_and_after_pagination_cannot_cross_registration(self):
        old = [self.send(self.first, f'Old {index}')['id'] for index in range(55)]
        newcomer = self.register('New player')
        current = [self.send(self.first, f'New {index}')['id'] for index in range(55)]
        page = self.world.chat_feed(newcomer)
        self.assertEqual([m['id'] for m in page['messages']], current[5:])
        self.assertTrue(page['has_older'])
        page = self.world.chat_feed(newcomer, before=current[5])
        self.assertEqual([m['id'] for m in page['messages']], current[:5])
        self.assertFalse(page['has_older'])
        self.assertEqual(self.ids(newcomer, before=current[0]), [])
        self.assertEqual(self.ids(newcomer, before=old[-1]), [])
        page = self.world.chat_feed(newcomer, after=old[0])
        self.assertEqual([m['id'] for m in page['messages']], current[:50])
        self.assertTrue(page['has_more'])
        self.assertEqual(self.ids(newcomer, after=current[49]), current[50:])

    def test_read_marker_changes_cannot_reveal_history_or_skip_future(self):
        old = self.send(self.first, 'Old public')
        newcomer = self.register('New player')
        current = self.send(self.first, 'New public')
        self.world.db.execute('DELETE FROM chat_reads WHERE owner=?', (newcomer,))
        self.world.db.commit()
        self.assertEqual(self.world.chat_summary(newcomer)['global_unread'], 1)
        self.world.chat_read(newcomer, {'last_id': old['id']})
        marker = self.world.db.execute(
            "SELECT last_id FROM chat_reads WHERE owner=? AND channel=''", (newcomer,)
        ).fetchone()[0]
        self.assertEqual(marker, 0)
        self.assertEqual(self.world.chat_summary(newcomer)['global_unread'], 1)
        self.world.chat_read(newcomer, {'last_id': 9_223_372_036_854_775_807})
        self.assertEqual(self.world.chat_summary(newcomer)['global_unread'], 0)
        future = self.send(self.first, 'Future public')
        self.assertEqual(self.world.chat_summary(newcomer)['global_unread'], 1)
        self.assertEqual(self.ids(newcomer), [current['id'], future['id']])
        self.assertEqual(self.boundary(newcomer), old['id'])

    def test_cutoff_survives_restart_and_repeated_registration_hook(self):
        old = self.send(self.first, 'Old public')
        newcomer = self.register('New player')
        current = self.send(self.first, 'New public')
        self.world._chat_register(newcomer)
        self.world.db.commit()
        at = self.world.now
        self.world.close()
        self.world = app.World(self.path, now=at)
        self.assertEqual(self.boundary(newcomer), old['id'])
        self.assertEqual(self.ids(newcomer), [current['id']])
        self.assertEqual(self.world.chat_summary(newcomer)['global_unread'], 1)

    def test_guessed_historical_id_cannot_be_reported(self):
        old = self.send(self.first, 'Old public')
        private = self.send(self.first, 'Unrelated private', peer=self.second)
        newcomer = self.register('New player')
        for message in (old, private):
            with self.subTest(message=message['id']), self.assertRaises(app.GameError) as hidden:
                self.world.chat_report(newcomer, {'message_id': message['id']})
            self.assertEqual(hidden.exception.status, 404)
        self.assertEqual(self.world.db.execute('SELECT COUNT(*) FROM chat_reports').fetchone()[0], 0)
        current = self.send(self.first, 'Visible public')
        self.assertTrue(self.world.chat_report(newcomer, {'message_id': current['id']})['ok'])
        self.assertEqual(self.world.db.execute('SELECT message_id FROM chat_reports').fetchone()[0], current['id'])

    def test_pre_migration_accounts_keep_history(self):
        old = self.send(self.first, 'Legacy public history')
        # An existing database has no visibility table until this deployment.
        self.world.db.execute('DROP TABLE chat_visibility')
        self.world.db.commit()
        at = self.world.now
        self.world.close()
        self.world = app.World(self.path, now=at)
        self.assertEqual(self.ids(self.second), [old['id']])
        newcomer = self.register('New player')
        self.assertEqual(self.ids(newcomer), [])

    def test_failed_registration_rolls_back_boundary(self):
        self.send(self.first, 'Existing public')
        before = self.world.db.execute('SELECT * FROM chat_visibility ORDER BY owner').fetchall()
        with patch.object(self.world, '_save', side_effect=OSError('disk unavailable')):
            with self.assertRaises(app.GameError):
                self.register('Failed player')
        self.assertEqual(self.world.db.execute('SELECT * FROM chat_visibility ORDER BY owner').fetchall(), before)
        self.assertIsNone(self.world.db.execute(
            'SELECT id FROM accounts WHERE name_key=?', ('failed player',)).fetchone())

    def test_account_deletion_removes_boundary(self):
        account = self.world.register('Temporary player', PASSWORD)
        player = account['state']['player']['id']
        self.assertIsNotNone(self.boundary(player))
        self.world.account_delete(account['token'], PASSWORD, 'DELETE ACCOUNT')
        self.assertIsNone(self.world.db.execute(
            'SELECT owner FROM chat_visibility WHERE owner=?', (player,)).fetchone())


if __name__ == '__main__':
    unittest.main()
