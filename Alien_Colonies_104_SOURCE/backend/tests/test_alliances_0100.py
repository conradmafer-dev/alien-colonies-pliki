"""Membership, recruitment, authorization and durable alliance privacy invariants."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from server.main import World, GameError
from server.alliances import MAX_MEMBERS, DEPARTURE_SECONDS, RECRUITMENT_SECONDS

NOW = 1900000000
PASSWORD = 'alliance-test-password'


class Alliances(unittest.TestCase):
    def setUp(self):
        self.w = World(':memory:', now=NOW)
        self.addCleanup(self.w.close)
        self.sequence = 0
        self.a, self.b, self.c = [self.register('AllianceUser' + str(n)) for n in range(3)]

    def register(self, name, world=None):
        return (world or self.w).register(name, PASSWORD)['state']['player']['id']

    def act(self, pid, action, **payload):
        self.sequence += 1
        payload.setdefault('request_id', 'request-' + str(self.sequence))
        return self.w.alliance_action(pid, dict(payload, action=action))

    def create(self, pid=None, name='Defenders', tag='DEF'):
        return self.act(pid or self.a, 'create', name=name, tag=tag)['alliance']['id']

    def join(self, pid, leader=None):
        leader = leader or self.a
        self.act(leader, 'invite', player_id=pid)
        return self.act(pid, 'accept_invite', alliance_id=self.w._alliance_for(leader)['id'])

    def fail_unchanged(self, pid, action, status=None, **payload):
        before = copy.deepcopy(self.w.data)
        with self.assertRaises(GameError) as caught:
            self.act(pid, action, **payload)
        if status:
            self.assertEqual(caught.exception.status, status)
        self.assertEqual(self.w.data, before)

    def test_create_normalizes_identity_and_duplicate_request_is_once(self):
        result = self.act(self.a, 'create', name='  Łowcy   Roju  ', tag='abc', request_id='create-once')
        aid = result['alliance']['id']
        self.assertEqual((result['alliance']['name'], result['alliance']['tag']), ('Łowcy Roju', 'ABC'))
        again = self.act(self.a, 'create', name='  Łowcy   Roju  ', tag='abc', request_id='create-once')
        self.assertEqual(again['alliance']['id'], aid)
        self.assertEqual(len(self.w.data['alliances']), 1)
        self.assertEqual(self.w._alliance_role(self.a), 'leader')
        self.fail_unchanged(self.a, 'create', name='Different', tag='XYZ', request_id='create-once', status=409)

    def test_unique_names_normalized_unicode_and_tags(self):
        self.create(name='ŁOWCY Khar', tag='ABC')
        self.fail_unchanged(self.b, 'create', name='łowcy  khar', tag='XYZ', status=409)
        self.fail_unchanged(self.b, 'create', name='Different', tag='abc', status=409)
        self.act(self.b, 'create', name='Café fleet', tag='NEW')
        self.fail_unchanged(self.c, 'create', name='Cafe\u0301 fleet', tag='END', status=409)

    def test_invalid_payloads_cannot_write_snapshot(self):
        for patch in ({'name': 'ab'}, {'name': '\u202eevil'}, {'tag': 'ŻAB'}, {'tag': 'AB'},
                      {'tag': 'A_B'}, {'description': 'x' * 501}, {'description': 'bad\x00text'},
                      {'request_id': ''}, {'request_id': ['bad']}, {'name': None}):
            with self.subTest(patch=patch):
                payload = {'name': 'Defenders', 'tag': 'DEF', **patch}
                self.fail_unchanged(self.a, 'create', **payload)
        for payload in (None, [], {'action': []}, {'action': 'create'},
                        {'action': 'create', 'request_id': 'nan', 'name': float('nan')}):
            before = copy.deepcopy(self.w.data)
            with self.assertRaises(GameError):
                self.w.alliance_action(self.a, payload)
            self.assertEqual(before, self.w.data)

    def test_accept_invitation_requires_actual_recipient(self):
        aid = self.create()
        self.act(self.a, 'invite', player_name=self.w._player(self.b)['name'].lower())
        self.assertEqual(self.w.alliance_summary(self.b)['invitations_count'], 1)
        self.fail_unchanged(self.c, 'accept_invite', alliance_id=aid, status=409)
        self.act(self.b, 'accept_invite', alliance_id=aid)
        self.assertTrue(self.w._allied(self.a, self.b))
        self.assertEqual(self.w.alliance_summary(self.b)['invitations_count'], 0)
        self.assertEqual(self.w._alliance_role(self.b), 'member')

    def test_applications_visible_only_to_managers_and_applicant(self):
        aid = self.create()
        self.join(self.b)
        self.act(self.c, 'apply', alliance_id=aid, text='A confidential application')
        self.assertEqual(self.w.alliance_view(self.a)['alliance']['applications'][0]['text'], 'A confidential application')
        self.assertNotIn('applications', self.w.alliance_view(self.b)['alliance'])
        self.assertEqual(len(self.w.alliance_view(self.c)['applications']), 1)
        self.fail_unchanged(self.b, 'approve_application', player_id=self.c, status=403)
        self.act(self.a, 'approve_application', player_id=self.c)
        self.assertTrue(self.w._allied(self.a, self.c))
        self.assertFalse(self.w.alliance_view(self.c)['applications'])

    def test_join_clears_recruitment_globally(self):
        aid = self.create()
        other = self.create(self.c, 'Others', 'OTH')
        self.act(self.b, 'apply', alliance_id=other)
        self.act(self.a, 'invite', player_id=self.b)
        self.act(self.c, 'invite', player_id=self.b)
        self.act(self.b, 'accept_invite', alliance_id=aid)
        for alliance in self.w.data['alliances'].values():
            self.assertNotIn(self.b, alliance['invitations'])
            self.assertNotIn(self.b, alliance['applications'])
        self.fail_unchanged(self.b, 'accept_invite', alliance_id=other, status=409)

    def test_recruitment_expiry_is_checked_on_read_and_write(self):
        aid = self.create()
        self.act(self.a, 'invite', player_id=self.b)
        self.act(self.c, 'apply', alliance_id=aid)
        self.w.now += RECRUITMENT_SECONDS
        self.assertFalse(self.w.alliance_view(self.b)['invitations'])
        self.assertFalse(self.w.alliance_view(self.a)['alliance']['applications'])
        self.fail_unchanged(self.b, 'accept_invite', alliance_id=aid, status=409)
        self.fail_unchanged(self.a, 'approve_application', player_id=self.c, status=404)

    def test_decline_withdraw_reject_and_cancel(self):
        aid = self.create()
        self.act(self.a, 'invite', player_id=self.b)
        self.act(self.b, 'decline_invite', alliance_id=aid)
        self.fail_unchanged(self.a, 'invite', player_id=self.b, status=429)
        self.w.now += 60
        self.act(self.a, 'invite', player_id=self.b)
        self.act(self.a, 'cancel_invite', player_id=self.b)
        self.act(self.c, 'apply', alliance_id=aid)
        self.act(self.c, 'withdraw_application', alliance_id=aid)
        self.fail_unchanged(self.c, 'apply', alliance_id=aid, status=429)
        self.w.now += 60
        self.act(self.c, 'apply', alliance_id=aid)
        self.act(self.a, 'reject_application', player_id=self.c)
        self.assertFalse(self.w.alliance_view(self.c)['applications'])

    def test_officers_can_recruit_and_kick_members_but_cannot_manage_leaders(self):
        aid = self.create()
        self.join(self.b)
        self.act(self.a, 'set_role', player_id=self.b, role='officer')
        self.act(self.c, 'apply', alliance_id=aid)
        self.act(self.b, 'approve_application', player_id=self.c)
        for action, fields in [('set_role', {'player_id': self.c, 'role': 'officer'}),
                               ('transfer_leader', {'player_id': self.b}),
                               ('edit', {'description': 'bad'}), ('disband', {'confirmation': 'DEF'}),
                               ('kick', {'player_id': self.a})]:
            self.fail_unchanged(self.b, action, status=403, **fields)
        self.act(self.b, 'kick', player_id=self.c)
        self.assertIsNone(self.w._alliance_for(self.c))

    def test_officer_cannot_kick_peer_officer_or_self(self):
        self.create()
        self.join(self.b)
        self.join(self.c)
        for pid in (self.b, self.c):
            self.act(self.a, 'set_role', player_id=pid, role='officer')
        self.fail_unchanged(self.b, 'kick', player_id=self.c, status=403)
        self.fail_unchanged(self.b, 'kick', player_id=self.b, status=403)
        self.act(self.a, 'kick', player_id=self.b)

    def test_only_current_members_of_own_alliance_are_actionable(self):
        self.create()
        self.create(self.b, 'Enemies', 'ENM')
        for action, fields in [('kick', {'player_id': self.b}),
                               ('set_role', {'player_id': self.b, 'role': 'officer'}),
                               ('transfer_leader', {'player_id': self.b})]:
            self.fail_unchanged(self.a, action, **fields)
        self.assertEqual(self.w._alliance_role(self.b), 'leader')

    def test_transfer_required_before_leader_leaves(self):
        self.create()
        self.join(self.b)
        self.fail_unchanged(self.a, 'leave', status=409)
        self.act(self.a, 'transfer_leader', player_id=self.b, request_id='transfer-once')
        self.act(self.a, 'transfer_leader', player_id=self.b, request_id='transfer-once')
        self.assertEqual(self.w._alliance_role(self.a), 'officer')
        self.act(self.a, 'leave')
        self.assertEqual(self.w._alliance_role(self.b), 'leader')

    def test_departure_truce_mutual_and_cooldown_exact_deadline(self):
        self.create()
        self.join(self.b)
        self.act(self.b, 'leave', request_id='leave-once')
        before = copy.deepcopy(self.w.data['alliance_truces'])
        self.w.now += 10
        self.act(self.b, 'leave', request_id='leave-once')
        self.assertEqual(before, self.w.data['alliance_truces'])
        self.assertTrue(self.w._alliance_attack_block(self.a, self.b))
        self.assertTrue(self.w._alliance_attack_block(self.b, self.a))
        self.assertFalse(self.w._alliance_attack_block(self.b, self.c))
        self.fail_unchanged(self.b, 'create', name='Others', tag='OTH', status=409)
        self.fail_unchanged(self.b, 'apply', alliance_id=self.w._alliance_for(self.a)['id'], status=409)
        self.fail_unchanged(self.a, 'invite', player_id=self.b, status=409)
        self.w.now = NOW + DEPARTURE_SECONDS
        self.assertFalse(self.w._alliance_attack_block(self.a, self.b))
        self.create(self.b, 'Others', 'OTH')

    def test_disband_requires_exact_confirmation_and_truces_every_pair(self):
        aid = self.create()
        self.join(self.b)
        self.join(self.c)
        self.fail_unchanged(self.a, 'disband')
        self.fail_unchanged(self.a, 'disband', confirmation='def')
        self.act(self.a, 'disband', confirmation='DEF', request_id='disband-once')
        self.assertNotIn(aid, self.w.data['alliances'])
        for one, two in ((self.a, self.b), (self.a, self.c), (self.b, self.c)):
            self.assertTrue(self.w._alliance_attack_block(one, two))
            self.assertEqual(self.w._player(one)['alliance_join_after'], NOW + DEPARTURE_SECONDS)
        self.act(self.a, 'disband', confirmation='DEF', request_id='disband-once')

    def test_last_member_leave_disbands_and_cannot_evade_cooldown(self):
        aid = self.create()
        self.act(self.a, 'leave')
        self.assertNotIn(aid, self.w.data['alliances'])
        self.fail_unchanged(self.a, 'create', name='Defenders', tag='DEF', status=409)

    def test_private_chat_membership_throttling_validation_and_retries(self):
        self.create()
        self.join(self.b)
        self.act(self.b, 'chat_send', text='Private fleet coordination', request_id='chat-once')
        self.act(self.b, 'chat_send', text='Private fleet coordination', request_id='chat-once')
        self.assertEqual(len(self.w.alliance_view(self.a)['alliance']['chat']), 1)
        self.assertNotIn('Private fleet coordination', json.dumps(self.w.alliance_view(self.c)))
        self.fail_unchanged(self.c, 'chat_send', text='intrusion', status=403)
        self.fail_unchanged(self.b, 'chat_send', text='spam', status=429)
        self.w.now += 2
        for text in (' ', 'a' * 501, 'invisible\u202etext'):
            self.fail_unchanged(self.b, 'chat_send', text=text)
        self.act(self.a, 'kick', player_id=self.b)
        self.fail_unchanged(self.b, 'chat_send', text='Private fleet coordination', request_id='chat-once', status=403)
        self.assertNotIn('Private fleet coordination', json.dumps(self.w.alliance_view(self.b)))

    def test_alliance_chat_respects_global_mute_and_limits_vertical_spam(self):
        self.create()
        self.w.db.execute('INSERT INTO chat_mutes VALUES(?,?)', (self.a, NOW + 60))
        self.w.db.commit()
        self.fail_unchanged(self.a, 'chat_send', text='Muted evasion', status=403)
        self.w.now += 60
        self.fail_unchanged(self.a, 'chat_send', text='spam\n' * 10)
        self.act(self.a, 'chat_send', text='Windows line\r\nsecond line')
        self.assertEqual(self.w._alliance_for(self.a)['chat'][0]['text'], 'Windows line\nsecond line')

    def test_duplicate_command_checks_current_manager_permission(self):
        self.create()
        self.join(self.b)
        self.act(self.a, 'set_role', player_id=self.b, role='officer')
        self.act(self.b, 'invite', player_id=self.c, request_id='officer-invite')
        self.act(self.a, 'set_role', player_id=self.b, role='member')
        self.fail_unchanged(self.b, 'invite', player_id=self.c, request_id='officer-invite', status=403)

    def test_chat_history_is_bounded_and_no_internal_object_can_be_mutated(self):
        self.create()
        for n in range(105):
            self.w.now = NOW + 3 * n
            self.act(self.a, 'chat_send', text='line ' + str(n))
        result = self.w.alliance_view(self.a)
        self.assertEqual(len(result['alliance']['chat']), 100)
        self.assertEqual(result['alliance']['chat'][0]['text'], 'line 5')
        result['alliance']['chat'][0]['text'] = 'client mutation'
        result['alliance']['members'][0]['role'] = 'member'
        self.assertEqual(self.w._alliance_for(self.a)['chat'][0]['text'], 'line 5')
        self.assertEqual(self.w._alliance_role(self.a), 'leader')

    def test_roster_and_directory_never_include_empire_secrets(self):
        self.create()
        self.join(self.b)
        self.w._player(self.b)['research']['weapons'] = 937
        self.w._owned(self.b)['resources']['metal'] = 81234567
        view = self.w.alliance_view(self.a)
        own = next(m for m in view['alliance']['members'] if m['id'] == self.b)
        self.assertEqual(set(own), {'id', 'player_id', 'name', 'race_id', 'role', 'joined_at'})
        serialized = json.dumps(view)
        for private in ('research', 'resources', 'planets', 'protected_until', 'system_intel', 'password', 'online'):
            self.assertNotIn('"' + private + '"', serialized)
        outside = self.w.alliance_view(self.c)
        self.assertIsNone(outside['alliance'])
        self.assertNotIn('members', outside['directory'][0])
        self.assertNotIn('chat', outside['directory'][0])

    def test_member_limit_race_is_serialized(self):
        aid = self.create()
        # Directly seed ordinary memberships to keep the capacity test focused.
        alliance = self.w._alliance_for(self.a)
        for n in range(MAX_MEMBERS - 2):
            pid = 'capacity-' + str(n)
            self.w.data['players'][pid] = {'id': pid, 'name': pid, 'alliance_id': aid}
            alliance['members'][pid] = {'role': 'member', 'joined_at': NOW}
        for pid in (self.b, self.c):
            self.act(self.a, 'invite', player_id=pid)
        def accept(pid):
            try:
                return self.w.alliance_action(pid, {'action': 'accept_invite', 'alliance_id': aid, 'request_id': 'race-' + pid})
            except GameError as error:
                return error
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(accept, (self.b, self.c)))
        self.assertEqual(sum(isinstance(r, GameError) for r in results), 1)
        self.assertEqual(len(alliance['members']), MAX_MEMBERS)
        self.assertEqual(sum(self.w._allied(self.a, p) for p in (self.b, self.c)), 1)

    def test_two_concurrent_accepts_cannot_join_two_alliances(self):
        one = self.create()
        two = self.create(self.c, 'Others', 'OTH')
        self.act(self.a, 'invite', player_id=self.b)
        self.act(self.c, 'invite', player_id=self.b)
        def accept(aid):
            try:
                return self.w.alliance_action(self.b, {'action': 'accept_invite', 'alliance_id': aid, 'request_id': 'race-' + aid})
            except GameError as error:
                return error
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(accept, (one, two)))
        self.assertEqual(sum(isinstance(r, GameError) for r in results), 1)
        self.assertEqual(sum(self.b in a['members'] for a in self.w.data['alliances'].values()), 1)

    def test_join_and_depart_hooks_observe_membership_before_removal(self):
        calls = []
        self.w._alliance_member_joined = lambda pid, aid: calls.append(('join', pid, self.w._alliance_for(pid)['id'] == aid))
        self.w._alliance_member_departed = lambda pid, aid: calls.append(('depart', pid, self.w._alliance_for(pid)['id'] == aid))
        self.create()
        self.join(self.b)
        self.act(self.b, 'leave')
        self.assertEqual(calls, [('join', self.a, True), ('join', self.b, True), ('depart', self.b, True)])

    def test_account_delete_elects_officer_and_purges_authored_chat(self):
        aid = self.create()
        self.join(self.b)
        self.w.now += 1
        self.join(self.c)
        self.act(self.a, 'set_role', player_id=self.c, role='officer')
        self.act(self.a, 'chat_send', text='Delete my private content')
        with self.w._atomic():
            self.w._alliance_account_delete(self.a)
        alliance = self.w.data['alliances'][aid]
        self.assertEqual(alliance['leader_id'], self.c)
        self.assertEqual(alliance['members'][self.c]['role'], 'leader')
        self.assertNotIn('Delete my private content', json.dumps(self.w.alliance_view(self.c)))
        self.assertIsNone(self.w._alliance_for(self.a))

    def test_account_delete_tiebreaker_is_stable(self):
        self.create()
        self.join(self.b)
        self.join(self.c)
        with self.w._atomic():
            self.w._alliance_account_delete(self.a)
        self.assertEqual(self.w._alliance_for(self.b)['leader_id'], min(self.b, self.c))

    def test_atomic_save_failure_rolls_back_membership_and_request_cache(self):
        self.create()
        before = copy.deepcopy(self.w.data)
        original_save = self.w._save
        def broken_save(*args, **kwargs):
            raise OSError('simulated disk failure')
        self.w._save = broken_save
        try:
            with self.assertRaises(GameError) as caught:
                self.act(self.a, 'invite', player_id=self.b, request_id='retry-after-disk')
            self.assertEqual(caught.exception.status, 503)
            self.assertEqual(before, self.w.data)
        finally:
            self.w._save = original_save
        self.act(self.a, 'invite', player_id=self.b, request_id='retry-after-disk')
        self.assertEqual(self.w.alliance_summary(self.b)['invitations_count'], 1)

    def test_migration_idempotence_and_unrelated_world_data_untouched(self):
        before = copy.deepcopy({k: v for k, v in self.w.data.items() if k not in ('players', 'alliances', 'alliance_truces', 'alliances_schema')})
        self.w._ensure_alliances()
        once = copy.deepcopy(self.w.data)
        self.w._ensure_alliances()
        self.assertEqual(self.w.data, once)
        self.assertEqual(before, {k: v for k, v in self.w.data.items() if k not in ('players', 'alliances', 'alliance_truces', 'alliances_schema')})
        self.create()
        self.join(self.b)
        self.w._ensure_alliances()
        after = copy.deepcopy(self.w.data)
        self.w._ensure_alliances()
        self.assertEqual(after, self.w.data)

    def test_restart_preserves_membership_chat_truce_and_request_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'world.sqlite3'
            world = World(path, now=NOW)
            a = self.register('PersistentLeader', world)
            b = self.register('PersistentMember', world)
            def send(pid, action, request_id, **kwargs):
                return world.alliance_action(pid, dict(kwargs, action=action, request_id=request_id))
            aid = send(a, 'create', 'create', name='Persistent', tag='PER')['alliance']['id']
            send(a, 'invite', 'invite', player_id=b)
            send(b, 'accept_invite', 'accept', alliance_id=aid)
            send(a, 'chat_send', 'chat', text='Remember this')
            send(b, 'leave', 'leave')
            world.close()
            world = World(path, now=NOW + 10)
            try:
                self.assertEqual(world.alliance_view(a)['alliance']['chat'][0]['text'], 'Remember this')
                self.assertTrue(world._alliance_attack_block(a, b))
                send(a, 'chat_send', 'chat', text='Remember this')
                self.assertEqual(len(world.alliance_view(a)['alliance']['chat']), 1)
                self.assertEqual(world.alliance_view(b)['cooldown_until'], NOW + DEPARTURE_SECONDS)
            finally:
                world.close()


if __name__ == '__main__':
    unittest.main()
