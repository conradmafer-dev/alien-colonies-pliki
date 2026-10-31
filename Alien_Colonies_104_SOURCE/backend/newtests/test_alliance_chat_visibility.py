"""Alliance history starts at account creation, not when the account joins."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World


class AllianceChatVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'world.sqlite3'
        self.world = World(self.path, now=2_000_000_000)
        self.sequence = 0
        self.leader = self.register('HistoryLeader')
        self.sender = self.register('HistorySender')
        self.alliance_id = self.act(self.leader, 'create', name='History Alliance', tag='HIS')['alliance']['id']
        self.join(self.sender)

    def tearDown(self):
        self.world.close()

    def register(self, name):
        return self.world.register(name, 'alliance-history-test-password')['state']['player']['id']

    def act(self, actor_id, action, **payload):
        self.sequence += 1
        return self.world.alliance_action(actor_id, {
            'action': action, 'request_id': f'chat-visibility-{self.sequence}', **payload})

    def send(self, player_id, text):
        return self.act(player_id, 'chat_send', text=text)['alliance']['chat'][-1]

    def join(self, player_id):
        self.act(self.leader, 'invite', player_id=player_id)
        return self.act(player_id, 'accept_invite', alliance_id=self.alliance_id)

    def feed(self, player_id):
        return self.world.alliance_view(player_id)['alliance']['chat']

    def reopen(self):
        now = self.world.now
        self.world.close()
        self.world = World(self.path, now=now)

    def test_same_clock_before_hidden_and_after_visible_in_join_response(self):
        old = self.send(self.leader, 'Before the account existed')
        newcomer = self.register('HistoryNewcomer')
        later = self.send(self.sender, 'After creation but before joining')
        self.assertEqual(old['at'], later['at'])
        self.assertGreater(later['id'], old['id'])
        result = self.join(newcomer)
        self.assertEqual([m['id'] for m in result['alliance']['chat']], [later['id']])
        self.assertEqual([m['id'] for m in self.feed(self.leader)], [old['id'], later['id']])
        self.assertNotIn(old['text'], json.dumps(result))

    def test_creation_boundary_and_later_history_persist_after_reopen(self):
        old = self.send(self.leader, 'Old persisted history')
        newcomer = self.register('PersistedNewcomer')
        later = self.send(self.sender, 'Recent persisted history')
        self.join(newcomer)
        floors = dict(self.world._player(newcomer)['chat_alliance_creation_floors'])
        self.reopen()
        self.assertEqual(self.world._player(newcomer)['chat_alliance_creation_floors'], floors)
        self.assertEqual(floors[self.alliance_id], old['id'])
        self.assertEqual([m['id'] for m in self.feed(newcomer)], [later['id']])

    def test_register_retry_does_not_move_creation_boundary(self):
        self.send(self.leader, 'Pre-creation')
        newcomer = self.register('StableBoundary')
        later = self.send(self.sender, 'Post-creation')
        before = dict(self.world._player(newcomer)['chat_alliance_creation_floors'])
        with self.world.lock, self.world._atomic():
            self.world._chat_register(newcomer)
        self.assertEqual(self.world._player(newcomer)['chat_alliance_creation_floors'], before)
        self.join(newcomer)
        self.assertEqual([m['id'] for m in self.feed(newcomer)], [later['id']])

    def test_accounts_without_migration_field_keep_existing_history(self):
        old = self.send(self.leader, 'Existing history must remain')
        self.world._player(self.sender).pop('chat_alliance_creation_floors')
        self.world._save()
        self.reopen()
        self.assertNotIn('chat_alliance_creation_floors', self.world._player(self.sender))
        self.assertEqual([m['id'] for m in self.feed(self.sender)], [old['id']])

    def test_alliance_created_after_account_has_no_prior_boundary(self):
        newcomer = self.register('FutureAllianceUser')
        founder = self.register('FutureAllianceLeader')
        later_alliance = self.act(founder, 'create', name='Later Alliance', tag='NEW')['alliance']['id']
        message = self.send(founder, 'Alliance created after your account')
        self.act(founder, 'invite', player_id=newcomer)
        result = self.act(newcomer, 'accept_invite', alliance_id=later_alliance)
        self.assertNotIn(later_alliance, self.world._player(newcomer)['chat_alliance_creation_floors'])
        self.assertEqual([m['id'] for m in result['alliance']['chat']], [message['id']])

    def test_pruned_history_uses_last_issued_id_instead_of_resetting_floor(self):
        old = self.send(self.leader, 'Removed history')
        alliance = self.world._alliance_for(self.leader)
        alliance['chat'] = []
        newcomer = self.register('PrunedHistoryUser')
        self.assertEqual(self.world._player(newcomer)['chat_alliance_creation_floors'][self.alliance_id], old['id'])
        later = self.send(self.sender, 'First message remaining after pruning')
        self.join(newcomer)
        self.assertEqual([m['id'] for m in self.feed(newcomer)], [later['id']])

    def test_cutoff_does_not_grant_nonmember_access_or_leak_through_directory(self):
        old = self.send(self.leader, 'Private alliance text')
        newcomer = self.register('OutsideHistoryUser')
        result = self.world.alliance_view(newcomer)
        self.assertIsNone(result['alliance'])
        self.assertNotIn(old['text'], json.dumps(result))
        self.assertNotIn('chat_alliance_creation_floors', json.dumps(self.world.state(newcomer)))


if __name__ == '__main__':
    unittest.main()
