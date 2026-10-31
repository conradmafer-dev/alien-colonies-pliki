"""HTTP locale isolation and persisted reports protect real game identities."""
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from server import i18n
from server.main import GameError, blank_ships, build_server
from tests.world_fixture import LocalTestWorld as World

EN = {
    'Zwiadowca': 'Scout', 'Zetanie': 'Zetans', 'Rój Khar': 'Khar Swarm',
    'Podaj nazwę i hasło.': 'Enter your name and password.',
    'Raport zwiadu': 'Scout report', 'Narodziny cywilizacji': 'Birth of a civilization',
    'Wybrano rasę: {0}. To stały wybór tego imperium.': 'Selected race: {0}. This choice is permanent.',
    'Ukończono projekt': 'Project completed',
    '{0}: {1}': '{0}: {1}', ', poziom {0}.': ', level {0}.',
    'Przebudzenie Zety': 'Zeta Awakening',
    'Siła pierwszej salwy': 'First volley strength',
    'Rozwiń kolonię': 'Develop your colony',
    '{0} — {1}. Zapasy: {2}. Flota: {3}.': '{0} — {1}. Resources: {2}. Fleet: {3}.',
    'metal': 'metal', 'kryształy': 'crystals', 'paliwo': 'fuel',
    'Żerowisko żelaza': 'Iron Feeding Grounds', 'brak statków': 'no ships',
    'Liczebność floty i hodowli ×{0:g}': 'Fleet and breeding multiplier ×{0:g}',
}
DE = {'Zwiadowca': 'Späher', 'Zetanie': 'Zetaner', 'Rój Khar': 'Khar-Schwarm',
      'Podaj nazwę i hasło.': 'Name und Passwort eingeben.', 'Raport zwiadu': 'Spähbericht'}
FR = {'Zwiadowca': 'Éclaireur', 'Podaj nazwę i hasło.': 'Saisissez votre nom et votre mot de passe.'}
CATALOGS = {'en': EN, 'de': DE, 'fr': FR}


class ServerLocalizationTests(unittest.TestCase):
    def setUp(self):
        # Known tiny translations exercise protocol behavior independently of
        # editorial wording changes in the full production catalogs.
        self.catalog_patch = patch.object(i18n, '_catalog', side_effect=lambda lang: CATALOGS.get(lang, {}))
        self.catalog_patch.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'localization.sqlite3')
        self.world = World(self.path, now=1_900_000_000)
        self.login = self.world.register('Zwiadowca', 'password-for-testing')
        self.player = self.login['state']['player']['id']
        self.home = self.world._owned(self.player)
        self.home['name'] = 'Zetanie'
        self.server = None

    def tearDown(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.worker.join(timeout=3)
        self.world.close()
        self.tmp.cleanup()
        self.catalog_patch.stop()

    def start_server(self):
        self.server = build_server(self.world, '127.0.0.1', 0)
        self.worker = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        self.worker.start()

    def request(self, locale=None, path='/api/state', body=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=10)
        headers = {'Authorization': 'Bearer ' + self.login['token'], 'Content-Type': 'application/json'}
        if locale is not None:
            headers['Accept-Language'] = locale
        try:
            conn.request('POST' if body is not None else 'GET', path,
                         json.dumps(body) if body is not None else None, headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read()), response.getheader('Vary')
        finally:
            conn.close()

    def test_language_negotiation_regions_quality_and_unsupported_fallback(self):
        self.assertEqual(i18n.negotiate_language('de-DE;q=0.8,fr-FR;q=0.9,en;q=0.2'), 'fr')
        self.assertEqual(i18n.negotiate_language('pl-PL'), 'pl')
        self.assertEqual(i18n.negotiate_language('es_MX'), 'es')
        for unsupported in ('', 'ja-JP', '*', 'de;q=0', 'de;q=NaN', 'de;q=4'):
            self.assertEqual(i18n.negotiate_language(unsupported), 'en')

    def test_nested_scopes_restore_and_threads_never_share_language(self):
        self.assertEqual(i18n.t('Zwiadowca'), 'Zwiadowca')
        with i18n.language_scope('en'):
            self.assertEqual(i18n.t('Zwiadowca'), 'Scout')
            with i18n.language_scope('de'):
                self.assertEqual(i18n.t('Zwiadowca'), 'Späher')
            self.assertEqual(i18n.t('Zwiadowca'), 'Scout')
        gate = threading.Barrier(2)
        def render(locale):
            with i18n.language_scope(locale):
                gate.wait(timeout=3)
                return str(i18n.t('Zwiadowca'))
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(render, ('en', 'de'))), ['Scout', 'Späher'])
        self.assertEqual(i18n.t('Zwiadowca'), 'Zwiadowca')

    def test_http_defaults_english_and_keeps_user_names_and_ids_literal(self):
        self.start_server()
        status, result, vary = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(vary, 'Accept-Language')
        state = result['state']
        self.assertEqual(state['catalog']['ships'][0]['name'], 'Scout')
        self.assertEqual(state['catalog']['ships'][0]['key'], 'scout')
        self.assertEqual(state['player']['id'], self.player)
        self.assertEqual(state['player']['name'], 'Zwiadowca')
        self.assertEqual(state['planet_name'], 'Zetanie')
        self.assertEqual(self.home['name'], 'Zetanie')

    def test_simultaneous_http_requests_and_errors_use_their_own_locale(self):
        self.start_server()
        locales = ('de-DE', 'fr-FR', 'pl-PL', 'en-US') * 2
        expected = ('Späher', 'Éclaireur', 'Zwiadowca', 'Scout') * 2
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(self.request, locales))
        self.assertEqual([value[1]['state']['catalog']['ships'][0]['name'] for value in results], list(expected))
        for locale, message in (('en', 'Enter your name and password.'), ('de', 'Name und Passwort eingeben.'), ('pl', 'Podaj nazwę i hasło.')):
            status, result, _ = self.request(locale, '/api/login', {})
            self.assertEqual(status, 400)
            self.assertEqual(result['error'], message)

    def test_skill_catalog_onboarding_and_swarm_have_localized_display_only(self):
        self.world.action(self.player, {'type': 'choose_race', 'race_id': 'zetans'})
        with i18n.language_scope('en'):
            state = self.world.state(self.player)
            self.assertEqual(state['player']['race_name'], 'Zetans')
            root = next(n for n in state['skill_tree']['nodes'] if n['id'] == 'zetans_root')
            self.assertEqual(root['name'], 'Zeta Awakening')
            self.assertEqual(root['description'], 'First volley strength +35%.')
            self.assertEqual(state['onboarding']['steps'][0]['title'], 'Develop your colony')
            hive = next(p for s in state['galaxy'] for p in s['planets'] if p['owner_id'] == 'khar')
            self.assertEqual(hive['race_name'], 'Khar Swarm')
            self.assertFalse(hive['has_scout'])
            actual = self.world.data['planets'][hive['id']]
            self.world._capture_swarm_intel(self.player, actual)
            hive = self.world._public_swarm_intel(self.player, actual)
            self.assertTrue(hive['swarm_threat_high'])
            self.assertEqual(hive['swarm_buildings'][0]['key'], 'metal_mine')
            self.assertEqual(hive['swarm_buildings'][0]['name'], 'Iron Feeding Grounds')

    def test_generated_scout_report_rerenders_after_language_switch_and_reload(self):
        target = next(p for p in self.world.data['planets'].values() if p['owner_id'] == 'khar')
        target['name'] = 'Zwiadowca'  # Exact translation key used as a planet name.
        fleet = {'id': 'test-scout', 'owner_id': self.player, 'origin_id': self.home['id'],
                 'target_id': target['id'], 'ships': {**blank_ships(), 'scout': 1},
                 'cargo': {'metal': 0, 'crystal': 0, 'fuel': 0}, 'mission': 'scout',
                 'status': 'outbound', 'seconds': 20, 'arrives_at': self.world.now}
        self.world.data['fleets'][fleet['id']] = fleet
        with i18n.language_scope('de'):
            self.world._complete_fleet(fleet)
        stored = self.world.data['players'][self.player]['reports'][0]
        self.assertEqual(stored['title'], 'Raport zwiadu')
        self.assertIn('i18n', stored)
        self.world._save()
        self.world.close()
        self.world = World(self.path, now=1_900_000_000)
        with i18n.language_scope('en'):
            report = self.world.state(self.player)['reports'][0]
            self.assertEqual(report['title'], 'Scout report')
            self.assertEqual('Zwiadowca — Khar Swarm.', report['text'])
            self.assertEqual(report['scout']['swarm_buildings'][0]['name'], 'Iron Feeding Grounds')
            self.assertNotIn('i18n', report)
        with i18n.language_scope('pl'):
            report = self.world.state(self.player)['reports'][0]
            self.assertEqual('Zwiadowca — Rój Khar.', report['text'])

    def test_saved_action_replay_is_localized_without_repeating_mutation(self):
        payload = {'type': 'choose_race', 'race_id': 'zetans', 'request_id': 'same-action'}
        with i18n.language_scope('de'):
            self.world.action(self.player, payload)
        count = len(self.world.data['players'][self.player]['reports'])
        self.world._save()
        self.world.close()
        self.world = World(self.path, now=1_900_000_000)
        with i18n.language_scope('en'):
            result = self.world.action(self.player, payload)
            self.assertEqual(result['message'], 'Selected race: Zetans. This choice is permanent.')
        self.assertEqual(len(self.world.data['players'][self.player]['reports']), count)

    def test_legacy_report_body_and_confirmation_token_are_not_guessed(self):
        self.world.data['players'][self.player]['reports'] = [
            {'id': 'legacy', 'title': 'Raport zwiadu', 'text': 'Zwiadowca visited Zetanie.', 'at': 1}]
        with i18n.language_scope('de'):
            report = self.world.state(self.player)['reports'][0]
        self.assertEqual(report['title'], 'Spähbericht')
        self.assertEqual(report['text'], 'Zwiadowca visited Zetanie.')
        with i18n.language_scope('en'):
            with self.assertRaises(GameError):
                self.world.account_delete(self.login['token'], 'password-for-testing', 'delete account')
            result = self.world.account_delete(self.login['token'], 'password-for-testing', 'USUŃ KONTO')
            self.assertTrue(result['ok'])

    def test_canonical_english_confirmation_works_in_every_ui_locale(self):
        with i18n.language_scope('fr'):
            result = self.world.account_delete(self.login['token'], 'password-for-testing', 'DELETE ACCOUNT')
        self.assertTrue(result['ok'])
        self.assertNotIn(self.player, self.world.data['players'])

    def test_decimal_formatting_preserves_punctuation_and_relocalizable_metadata(self):
        from server.races import research_effect_text
        with i18n.language_scope('pl'):
            value = research_effect_text('multiplication', 1)
            self.assertIn('1,2', value)
        self.assertEqual(i18n.render_text(i18n.store_text(value), 'en'), 'Fleet and breeding multiplier ×1.2')


if __name__ == '__main__':
    unittest.main()
