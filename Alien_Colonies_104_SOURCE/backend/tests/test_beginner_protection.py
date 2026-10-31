"""Protection notices follow real dispatches and persist independently of reports."""
import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World, GameError, RESOURCES, LEGACY_WELCOME_REPORT_TEXT, WELCOME_REPORT_TEXT
from beginner_protection import LEGACY_START_TEXT, START_TEXT
from i18n import language_scope, store_text, t
import swarm

NOW = 2_000_000_000.0
DAY = 86400
THREE_DAYS = 3 * DAY


class BeginnerProtectionTests(unittest.TestCase):
    def setUp(self):
        self.w = World(':memory:', now=NOW, speed=1000)
        self.addCleanup(lambda: self.w.close())
        self.owner = self.account('NewExplorer')
        self.w.data['alien']['next_expansion_at'] = NOW + 100 * DAY

    def account(self, name):
        pid = self.w.register(name, 'protection-test-password')['state']['player']['id']
        self.w.action(pid, {'type': 'choose_race', 'race_id': 'zetans'})
        home = self.w._owned(pid)
        home['resources'] = dict.fromkeys(RESOURCES, 1_000_000.)
        home['ships'].update(scout=20, frigate=20, colonizer=20)
        return pid

    def reports(self, owner=None, event=None):
        reports = self.w._player(owner or self.owner)['reports']
        return [r for r in reports if r.get('protection_event') == event] if event else [
            r for r in reports if r.get('protection_event')]

    def dispatch(self, target, mission='attack', **extra):
        self.w._capture_planetary_intel(self.owner, target)
        ship = {'attack': 'frigate', 'colonize': 'colonizer', 'scout': 'scout'}[mission]
        return self.w.action(self.owner, {'type': 'fleet', 'mission': mission,
            'target_id': target['id'], 'ships': {ship: 1}, **extra})

    def enemy(self, protected=False):
        owner = self.account('OtherExplorer')
        if not protected:
            self.w._player(owner)['protected_until'] = NOW
        return self.w._owned(owner)

    def empty(self):
        return next(p for p in self.w.data['planets'].values() if p['owner_type'] == 'empty')

    def save_snapshot(self, path):
        self.w._save()
        db = sqlite3.connect(path)
        self.w.db.backup(db)
        db.close()

    def restore(self, path, now):
        self.save_snapshot(path)
        return World(path, now=now, speed=1000)

    def legacy_protection(self):
        """An actual pre-72h account, including its already delivered reports."""
        player = self.w._player(self.owner)
        player.pop('protection_duration_version')
        player['protected_until'] = NOW + DAY
        for report in player['reports']:
            text = (LEGACY_START_TEXT if report.get('protection_event') == 'started' else
                    LEGACY_WELCOME_REPORT_TEXT if report['title'] == 'Witaj w Alien Colonies' else None)
            if text is not None:
                report['text'] = text
                report['i18n']['text'] = store_text(t(text))
                report['read'] = True
        return player

    def test_new_empire_gets_one_start_report_and_all_supported_languages_render_it(self):
        self.assertEqual(self.w._player(self.owner)['protected_until'], NOW + THREE_DAYS)
        self.assertEqual(len(self.reports(event='started')), 1)
        for lang, title, duration in [('en', 'Beginner protection', '3 days'),
                                     ('pl', 'Ochrona początkującego', '3 dni'),
                                     ('de', 'Anfängerschutz', '3 Tage'),
                                     ('es', 'Protección de principiante', '3 días'),
                                     ('fr', 'Protection des débutants', '3 jours')]:
            with language_scope(lang):
                reports = self.w.state(self.owner)['reports']
                report = next(r for r in reports if r.get('protection_event') == 'started')
                self.assertEqual(report['title'], title)
                self.assertIn(duration, report['text'])
                self.assertNotIn('_l10n', json.dumps(report))
                welcome_id = next(r['id'] for r in self.w._player(self.owner)['reports']
                                  if r['title'] == 'Witaj w Alien Colonies')
                self.assertIn(duration, next(r['text'] for r in reports if r['id'] == welcome_id))
        self.w.advance(NOW)
        self.w._ensure_progression()
        self.assertEqual(len(self.reports(event='started')), 1)

    def test_expiry_uses_real_deadline_not_speed_and_is_reported_exactly_once(self):
        self.w.advance(NOW + DAY)
        self.assertFalse(self.reports(event='ended'))
        self.w.advance(NOW + THREE_DAYS - 1)
        self.assertFalse(self.reports(event='ended'))
        self.w.advance(NOW + THREE_DAYS)
        ended = self.reports(event='ended')
        self.assertEqual(len(ended), 1)
        self.assertEqual(ended[0]['at'], NOW + THREE_DAYS)
        self.assertEqual(ended[0]['protection_end_reason'], 'expired')
        self.w.advance(NOW + 4 * DAY)
        self.assertEqual(len(self.reports(event='ended')), 1)

    def test_offline_expiry_and_restart_preserve_both_notice_markers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'protection.sqlite3'
            restored = self.restore(path, NOW + 4 * DAY)
            try:
                player = restored._player(self.owner)
                ended = [r for r in player['reports'] if r.get('protection_event') == 'ended']
                self.assertEqual(len(ended), 1)
                self.assertEqual(ended[0]['at'], NOW + THREE_DAYS)
            finally:
                restored.close()
            again = World(path, now=NOW + 5 * DAY)
            try:
                events = [r['protection_event'] for r in again._player(self.owner)['reports'] if r.get('protection_event')]
                self.assertCountEqual(events, ['started', 'ended'])
            finally:
                again.close()

    def test_rotation_does_not_recreate_start_or_end_report(self):
        self.w._player(self.owner)['reports'].clear()
        self.w.advance(NOW + THREE_DAYS)
        self.assertEqual(len(self.reports(event='ended')), 1)
        self.w._player(self.owner)['reports'].clear()
        self.w._ensure_progression()
        self.w.advance(NOW + 4 * DAY)
        self.assertFalse(self.reports())

    def test_migration_notifies_active_empire_without_resetting_deadline(self):
        player = self.w._player(self.owner)
        player.pop('protection_notice')
        player['reports'].clear()
        player['protected_until'] = NOW + 100
        self.w._ensure_progression()
        self.assertEqual(player['protected_until'], NOW + 100)
        self.assertEqual(len(self.reports(event='started')), 1)
        self.w.advance(NOW + 101)
        self.assertEqual(len(self.reports(event='ended')), 1)

    def test_migration_does_not_send_historical_notices_for_expired_empire(self):
        player = self.w._player(self.owner)
        player.pop('protection_notice')
        player['reports'].clear()
        player['protected_until'] = NOW - DAY
        self.w._ensure_progression()
        self.w.advance(NOW + DAY)
        self.assertEqual(player['protected_until'], NOW - DAY)
        self.assertFalse(self.reports())

    def test_rejected_attack_keeps_protection_and_does_not_send_end_report(self):
        target = self.enemy(protected=True)
        with self.assertRaises(GameError):
            self.dispatch(target)
        self.assertEqual(self.w._player(self.owner)['protected_until'], NOW + THREE_DAYS)
        self.assertFalse(self.reports(event='ended'))

    def test_paid_player_attack_ends_protection_once_even_after_repeated_dispatch(self):
        target = self.enemy()
        self.dispatch(target, request_id='first-attack')
        fleet_count = len(self.w.data['fleets'])
        ships = dict(self.w._owned(self.owner)['ships'])
        self.dispatch(target, request_id='first-attack')  # Idempotent retry.
        self.assertEqual(len(self.w.data['fleets']), fleet_count)
        self.assertEqual(self.w._owned(self.owner)['ships'], ships)
        self.dispatch(target, request_id='second-attack')
        self.assertEqual(self.w._player(self.owner)['protected_until'], NOW)
        ended = self.reports(event='ended')
        self.assertEqual(len(ended), 1)
        self.assertEqual(ended[0]['protection_end_reason'], 'hostile_action')

    def test_serialized_end_report_renders_per_request_without_replaying_notice(self):
        self.w.advance(NOW + THREE_DAYS)
        self.w.data = json.loads(json.dumps(self.w.data))
        for lang, title, intro in [
            ('en', 'Protection ended', 'Your beginner protection has expired.'),
            ('pl', 'Ochrona zakończona', 'Upłynął czas ochrony początkującego.'),
            ('de', 'Schutz beendet', 'Dein Anfängerschutz ist abgelaufen.'),
            ('es', 'Protección terminada', 'Tu protección de principiante ha expirado.'),
            ('fr', 'Protection terminée', 'Ta protection des débutants a expiré.')]:
            with language_scope(lang):
                report = next(r for r in self.w.state(self.owner)['reports'] if r.get('protection_event') == 'ended')
                self.assertEqual(report['title'], title)
                self.assertTrue(report['text'].startswith(intro))
        self.assertEqual(len(self.reports(event='ended')), 1)
        self.w._player(self.owner)['reports'].clear()
        with tempfile.TemporaryDirectory() as folder:
            restored = self.restore(Path(folder) / 'retained.sqlite3', NOW + THREE_DAYS + 1)
            try:
                self.assertFalse([r for r in restored.state(self.owner)['reports'] if r.get('protection_event')])
            finally:
                restored.close()

    def test_scout_and_swarm_attack_preserve_beginner_protection(self):
        target = next(p for p in self.w.data['planets'].values() if p['owner_id'] == 'khar')
        self.dispatch(target, 'scout')
        self.dispatch(target)
        self.assertEqual(self.w._player(self.owner)['protected_until'], NOW + THREE_DAYS)
        self.assertFalse(self.reports(event='ended'))

    def test_swarm_raid_waits_for_the_full_three_day_deadline(self):
        home = self.w._owned(self.owner)
        home['ships'] = dict.fromkeys(home['ships'], 0)
        home['defenses'] = {}
        hive = next(p for p in self.w.data['planets'].values()
                    if p['owner_id'] == swarm.OWNER_ID and p['galaxy_id'] == home['galaxy_id'])
        hive['ships'] = {**dict.fromkeys(swarm.SHIPS, 0), 'frigate': 3000, 'cruiser': 500, 'cargo': 200}
        hive['resources'] = dict.fromkeys(RESOURCES, 100_000_000.)
        hive['swarm_next_attack_at'] = 0
        self.w.data['alien']['swarm_next_raid_at'] = NOW
        party = {**dict.fromkeys(swarm.SHIPS, 0), **swarm.RAID_PARTY}
        for elapsed in (DAY, 2 * DAY, THREE_DAYS - 1):
            with self.subTest(elapsed=elapsed):
                self.w.now = NOW + elapsed
                before = copy.deepcopy(self.w.data)
                self.assertIsNone(self.w._swarm_launch(hive, home, 'attack', party, raid=True))
                self.assertEqual(self.w.data, before)
        self.w.now = NOW + THREE_DAYS
        self.assertIsNotNone(self.w._swarm_launch(hive, home, 'attack', party, raid=True))

    def test_colonizing_empty_planet_keeps_protection_but_capture_dispatch_ends_it(self):
        empty = self.empty()
        self.dispatch(empty, 'colonize')
        self.assertFalse(self.reports(event='ended'))
        enemy_home = self.enemy()
        colony = next(p for p in self.w.data['planets'].values() if p['owner_type'] == 'empty' and p['id'] != empty['id'])
        colony.update(owner_type='player', owner_id=enemy_home['owner_id'])
        self.dispatch(colony, 'colonize')
        self.assertEqual(self.reports(event='ended')[0]['protection_end_reason'], 'hostile_action')

    def test_planet_settled_during_flight_ends_protection_when_capture_arrives(self):
        target = self.empty()
        self.dispatch(target, 'colonize')
        fleet = next(f for f in self.w.data['fleets'].values() if f['owner_id'] == self.owner)
        enemy_home = self.enemy()
        target.update(owner_type='player', owner_id=enemy_home['owner_id'])
        self.w.advance(fleet['arrives_at'])
        self.assertEqual(target['owner_id'], self.owner)
        self.assertEqual(self.reports(event='ended')[0]['protection_end_reason'], 'hostile_action')

    def test_alliance_defense_support_ends_protection_with_specific_reason(self):
        target = self.enemy()
        self.w.alliance_action(self.owner, {'action': 'create', 'name': 'Protection allies', 'tag': 'PAL', 'request_id': 'pact'})
        alliance = self.w._alliance_for(self.owner)
        self.w._alliance_join(target['owner_id'], alliance, 'member')
        self.w._capture_planetary_intel(self.owner, target)
        self.w.alliance_operation(self.owner, {'action': 'defend', 'target_id': target['id'],
            'planet_id': self.w._owned(self.owner)['id'], 'ships': {'frigate': 1}, 'hold_hours': 1,
            'request_id': 'send-support'})
        self.assertEqual(self.reports(event='ended')[0]['protection_end_reason'], 'alliance_support')

    def test_failed_storage_rolls_back_dispatch_notice_and_deadline_together(self):
        target = self.enemy()
        self.w._capture_planetary_intel(self.owner, target)
        before = copy.deepcopy(self.w.data)
        with patch.object(self.w, '_save', side_effect=OSError('test disk unavailable')):
            with self.assertRaises(GameError):
                self.w.action(self.owner, {'type': 'fleet', 'mission': 'attack', 'target_id': target['id'], 'ships': {'frigate': 1}})
        self.assertEqual(self.w.data, before)

    def test_badge_obeys_fog_of_war_and_ages_known_deadline_without_live_owner_lookup(self):
        enemy_home = self.enemy(protected=True)
        known = [p for s in self.w.state(self.owner)['galaxy'] for p in s['planets']]
        self.assertNotIn(enemy_home['id'], {p['id'] for p in known})
        own = next(p for p in known if p['id'] == self.w._owned(self.owner)['id'])
        self.assertTrue(own['is_protected'])
        self.w._capture_system_intel(self.owner, enemy_home)
        self.w._player(enemy_home['owner_id'])['protected_until'] = NOW
        known = [p for s in self.w.state(self.owner)['galaxy'] for p in s['planets']]
        remembered = next(p for p in known if p['id'] == enemy_home['id'])
        self.assertTrue(remembered['is_protected'], 'No live data leaked into a dated scout snapshot')
        self.w.advance(NOW + THREE_DAYS)
        known = [p for s in self.w.state(self.owner)['galaxy'] for p in s['planets']]
        self.assertFalse(next(p for p in known if p['id'] == enemy_home['id'])['is_protected'])
        self.assertFalse(next(p for p in known if p['id'] == own['id'])['is_protected'])

    def test_active_legacy_protection_extends_once_and_updates_existing_reports_in_place(self):
        player = self.legacy_protection()
        before = copy.deepcopy(player['reports'])
        epoch = self.w.data['launch_reset_id']
        swarm_deadline = self.w.data['alien']['swarm_next_raid_at']
        self.w.now = NOW + DAY / 2
        self.w._ensure_progression()
        self.assertEqual(player['protected_until'], NOW + THREE_DAYS)
        self.assertEqual(player['protection_duration_version'], 2)
        self.assertEqual(self.w.data['launch_reset_id'], epoch)
        self.assertEqual(self.w.data['alien']['swarm_next_raid_at'], swarm_deadline)
        self.assertEqual(len(player['reports']), len(before))
        for old, new in zip(before, player['reports']):
            self.assertEqual({k: v for k, v in old.items() if k not in ('text', 'i18n')},
                             {k: v for k, v in new.items() if k not in ('text', 'i18n')})
            if old.get('protection_event') == 'started':
                self.assertEqual(new['text'], START_TEXT)
                self.assertEqual(new['i18n']['text']['source'], START_TEXT)
            elif old['title'] == 'Witaj w Alien Colonies':
                self.assertEqual(new['text'], WELCOME_REPORT_TEXT)
                self.assertEqual(new['i18n']['text']['source'], WELCOME_REPORT_TEXT)
            else:
                self.assertEqual(old, new)
        self.w._ensure_progression()
        self.assertEqual(player['protected_until'], NOW + THREE_DAYS)
        self.assertEqual(len(player['reports']), len(before))

    def test_legacy_extension_survives_repeated_restart_without_restarting_the_clock(self):
        self.legacy_protection()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'extension.sqlite3'
            restored = self.restore(path, NOW + DAY / 2)
            try:
                player = restored._player(self.owner)
                self.assertEqual(player['protected_until'], NOW + THREE_DAYS)
                self.assertEqual(player['protection_duration_version'], 2)
                reports = copy.deepcopy(player['reports'])
            finally:
                restored.close()
            again = World(path, now=NOW + 2 * DAY, speed=1000)
            try:
                player = again._player(self.owner)
                self.assertEqual(player['protected_until'], NOW + THREE_DAYS)
                self.assertEqual(player['reports'], reports)
                self.assertTrue(again.state(self.owner)['player']['protected_until'] > again.now)
            finally:
                again.close()

    def test_legacy_expired_during_offline_time_is_not_revived_from_saved_cursor(self):
        player = self.legacy_protection()
        history = copy.deepcopy(player['reports'])
        with tempfile.TemporaryDirectory() as folder:
            restored = self.restore(Path(folder) / 'expired.sqlite3', NOW + DAY + 1)
            try:
                player = restored._player(self.owner)
                self.assertEqual(player['protected_until'], NOW + DAY)
                self.assertEqual(player['protection_duration_version'], 2)
                ended = [r for r in player['reports'] if r.get('protection_event') == 'ended']
                self.assertEqual(len(ended), 1)
                self.assertEqual(ended[0]['at'], NOW + DAY)
                self.assertEqual(ended[0]['protection_end_reason'], 'expired')
                for old in history:
                    self.assertEqual(next(r for r in player['reports'] if r['id'] == old['id']), old)
            finally:
                restored.close()

    def test_legacy_forfeited_protection_and_historical_reports_remain_ended(self):
        self.legacy_protection()
        self.dispatch(self.enemy())
        player = self.w._player(self.owner)
        reports = copy.deepcopy(player['reports'])
        self.assertEqual(player['protected_until'], NOW)
        self.w._ensure_progression()
        self.assertEqual(player['protected_until'], NOW)
        self.assertTrue(player['protection_notice']['ended'])
        self.assertEqual(player['reports'], reports)
        self.assertEqual(player['protection_duration_version'], 2)

    def test_extension_does_not_recreate_reports_removed_by_retention(self):
        player = self.legacy_protection()
        player['reports'].clear()
        self.w._ensure_progression()
        self.assertEqual(player['protected_until'], NOW + THREE_DAYS)
        self.assertFalse(player['reports'])

    def test_legacy_plain_reports_keep_translation_and_metadata_during_extension(self):
        player = self.legacy_protection()
        for report in player['reports']:
            report.pop('i18n', None)
        self.w._ensure_progression()
        with language_scope('en'):
            reports = self.w.state(self.owner)['reports']
        started = next(r for r in reports if r.get('protection_event') == 'started')
        self.assertEqual(started['title'], 'Beginner protection')
        self.assertIn('3 days', started['text'])
        welcome = next(r for r in reports if r['title'] == 'Welcome to Alien Colonies')
        self.assertIn('3 days', welcome['text'])

    def test_expired_legacy_plain_welcome_still_uses_its_historical_translation(self):
        player = self.legacy_protection()
        player['protected_until'] = NOW - 1
        welcome = next(r for r in player['reports'] if r['title'] == 'Witaj w Alien Colonies')
        welcome.pop('i18n')
        self.w._ensure_progression()
        self.assertEqual(welcome['text'], LEGACY_WELCOME_REPORT_TEXT)
        with language_scope('en'):
            rendered = next(r for r in self.w.state(self.owner)['reports'] if r['id'] == welcome['id'])
        self.assertEqual(rendered['title'], 'Welcome to Alien Colonies')
        self.assertIn('24 hours', rendered['text'])
        self.assertNotIn('3 days', rendered['text'])

    def test_failed_migration_write_preserves_old_deadline_and_reports_for_safe_retry(self):
        self.legacy_protection()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'failed-migration.sqlite3'
            self.save_snapshot(path)
            with sqlite3.connect(path) as db:
                before = db.execute('SELECT body FROM snapshot WHERE id=1').fetchone()[0]
            with patch.object(World, '_save', side_effect=OSError('test disk unavailable')):
                with self.assertRaises(GameError):
                    World(path, now=NOW + DAY / 2, speed=1000)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT body FROM snapshot WHERE id=1').fetchone()[0], before)
            restored = World(path, now=NOW + DAY / 2, speed=1000)
            try:
                player = restored._player(self.owner)
                self.assertEqual(player['protected_until'], NOW + THREE_DAYS)
                self.assertEqual(player['protection_duration_version'], 2)
                self.assertEqual(len([r for r in player['reports'] if r.get('protection_event') == 'started']), 1)
            finally:
                restored.close()


if __name__ == '__main__':
    unittest.main()
