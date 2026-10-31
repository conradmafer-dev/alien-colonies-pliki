"""Data/packaging and source-contract checks. These are NOT Godot runtime tests.
Run separately from the historical server suite:
    python -m unittest tests.test_android_0114 -v
Additional actual native scene: tests/test_fleet_navigation_0114.tscn (requires Godot).
"""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from server import main as app, fleet_expansion
from server.i18n import language_scope

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ('en', 'pl', 'de', 'es', 'fr')


def source(name):
    return (ROOT / 'client/scripts' / name).read_text(encoding='utf-8')


def function(text, name):
    pattern = r'^func ' + re.escape(name) + r'\([^\n]*\).*?:\n(.*?)(?=^func |\Z)'
    match = re.search(pattern, text, re.M | re.S)
    if not match:
        raise AssertionError('Missing function ' + name)
    return match.group(1)


def make_fixtures():
    """Real server snapshots without live-account identifiers or real passwords."""
    result = {}
    with tempfile.TemporaryDirectory() as temp:
        world = app.World(str(Path(temp) / 'test.sqlite3'), 1, now=1800000000)
        try:
            for race in app.RACES:
                account = world.register('native_' + race, 'Fixture-only-114712')
                owner = account['state']['player']['id']
                pid = account['state']['planet_id']
                world.action(owner, {'type': 'choose_race', 'race_id': race, 'planet_id': pid})
                planet = world.data['planets'][pid]
                planet['resources'] = dict.fromkeys(app.RESOURCES, 10**8)
                result[race] = {}
                for locale in LOCALES:
                    with language_scope(locale):
                        result[race][locale] = world.state(owner, pid)
        finally:
            world.close()
    return result


class Android114(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = make_fixtures()
        cls.art = json.loads((ROOT / 'docs/ANDROID_ART_0112.json').read_text())['assets']
        cls.catalogs = {lang: json.loads((ROOT / 'localization' / (lang+'.json')).read_text()) for lang in LOCALES}
        cls.main = source('main.gd')

    def test_client_versions_and_package_identity(self):
        self.assertIn('const CLIENT_VERSION_CODE: int = 48', self.main)
        self.assertIn('const CLIENT_VERSION_NAME: String = "0.11.4"', self.main)
        self.assertIn('config/version="0.11.4"', (ROOT/'project.godot').read_text())
        presets = (ROOT/'export_presets.cfg').read_text()
        self.assertEqual(presets.count('version/code=48'), 2)
        self.assertEqual(presets.count('version/name="0.11.4"'), 2)
        self.assertEqual(presets.count('package/unique_name="com.conradmafer.aliencolonies"'), 2)
        self.assertIn('keystore/release=""', presets)

    def test_local_server_and_railway_are_latest_same_gameplay_code(self):
        self.assertEqual(app.VERSION, '0.11.3')
        self.assertEqual((ROOT/'server/main.py').read_bytes(), (ROOT/'railway/app.py').read_bytes())
        for path in (ROOT/'railway').glob('*.py'):
            self.assertEqual(path.read_bytes(), (ROOT/'server'/path.name).read_bytes(), path.name)
        self.assertTrue((ROOT/'railway/web/play/index.html').is_file())
        self.assertTrue((ROOT/'railway/fleet_expansion.py').is_file())

    def test_assets_exist_match_manifest_and_are_distinct(self):
        self.assertEqual(len(self.art), 47)
        hashes = set()
        for item in self.art:
            path = ROOT/item['path']
            data = path.read_bytes()
            self.assertEqual(data[:4], b'RIFF')
            self.assertEqual(data[8:12], b'WEBP')
            digest = hashlib.sha256(data).hexdigest()
            self.assertEqual(digest, item['sha256'])
            self.assertNotIn(digest, hashes, item['key'])
            hashes.add(digest)
        self.assertEqual(sum(x['kind']=='ship' for x in self.art), 12)
        self.assertEqual(sum(x['kind']=='research' for x in self.art), 35)

    def test_all_catalogue_ids_have_native_images_in_allowlist(self):
        lib = source('art_library.gd')
        pictures = {x['key'] for x in self.art}
        research = set()
        for race, locales in self.fixtures.items():
            for item in locales['en']['catalog']['ships']:
                if item['key'] in fleet_expansion.CAPITAL_ROLES:
                    self.assertIn('races/'+race+'/'+item['key'], pictures)
                    self.assertIn('"'+item['key']+'"', lib)
            for item in locales['en']['catalog']['research']:
                research.add(item['key'])
                self.assertIn('research/'+item['key'], pictures)
                self.assertIn('"'+item['key']+'"', lib)
        self.assertEqual(len(research),35)
        self.assertIn('entry.get("unit_key", entry.get("key", fallback))', lib)
        self.assertIn('catalog_art_key', source('battle_board.gd'))
        self.assertIn('host._catalog_texture(key, "research")', source('research_tree.gd'))

    def test_all_new_names_and_descriptions_have_five_native_translations(self):
        for race in app.RACES:
            catalog = self.fixtures[race]['pl']['catalog']
            new_ships = [item for item in catalog['ships'] if item['key'] in fleet_expansion.CAPITAL_ROLES]
            for item in catalog['research'] + new_ships:
                for field in ('name', 'description'):
                    authored = item[field]
                    if field == 'description' and item['key'] in fleet_expansion.CAPITAL_ROLES:
                        # The API composes a translated class prefix with the base description.
                        authored = fleet_expansion.SHIPS[race][item['key']][1]
                    for locale in LOCALES:
                        self.assertTrue(self.catalogs[locale].get(authored), (locale, item['key'], field, authored))
                        if locale == 'en':
                            self.assertNotRegex(self.catalogs[locale][authored], r'[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]')

    def test_no_polish_new_content_in_english_server_snapshot(self):
        for race, locales in self.fixtures.items():
            for group in ('research', 'ships'):
                for item in locales['en']['catalog'][group]:
                    for field in ('name', 'description','effect_current','effect_next','role_name','reason'):
                        value = str(item.get(field,''))
                        displayed = self.catalogs['en'].get(value, value)  # main._server_text
                        self.assertNotRegex(displayed, r'[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]', (race,item['key'],field))

    def test_client_only_labels_have_translations_and_printf_matches(self):
        for key in ('Wczytywanie kolonii…','Odblokowuje','Poziom %d · %s','Wymagany poziom tego badania; pozostałe wymagania sprawdzisz w szczegółach.'):
            for locale in LOCALES:
                text = self.catalogs[locale][key]
                self.assertEqual(re.findall(r'%[ds]',key),re.findall(r'%[ds]',text))

    def test_graph_has_25_ordered_nodes_per_race_and_endgame_row_nine(self):
        for race, locales in self.fixtures.items():
            research = locales['en']['catalog']['research']
            self.assertEqual(len(research),25)
            positions=[(x['tree']['row'], x['tree']['column']) for x in research]
            self.assertEqual(positions, sorted(positions))
            self.assertEqual(len(set(positions)),25)
            self.assertEqual(max(x[0] for x in positions),9)
            self.assertTrue(all(0 <= x[1] <= 2 for x in positions))
            by_key={x['key']:x for x in research}
            for item in research:
                for req in item['requirements']:
                    if req['group']=='research':
                        self.assertLess(by_key[req['key']]['tree']['row'],item['tree']['row'])
            self.assertIn('custom_minimum_size.y = (last_row + 1) * ROW_STEP', source('research_tree.gd'))

    def test_unlock_navigation_uses_authoritative_ids_and_required_levels(self):
        for race, locales in self.fixtures.items():
            research={x['key']:x for x in locales['en']['catalog']['research']}
            for ship in locales['en']['catalog']['ships']:
                for req in ship['requirements']:
                    if req['group']=='research':
                        matches=[u for u in research[req['key']]['unlocks'] if u['group']=='ships' and u['key']==ship['key']]
                        self.assertEqual(len(matches),1)
                        self.assertEqual(matches[0]['level'],req['level'])
        ui=source('compact_ui.gd')
        self.assertIn('host.megastructure_ui.open_projects()', ui)
        self.assertIn('host.research_tree.open_details(key)', ui)
        self.assertIn('host.detailed_descriptions, false',ui)
        self.assertIn('include_requirements and not requirement_lines.is_empty()',source('catalog_details.gd'))

    def test_rich_early_colony_cannot_build_capitals_without_research(self):
        for locales in self.fixtures.values():
            for item in locales['en']['catalog']['ships']:
                if item['key'] in fleet_expansion.CAPITAL_ROLES:
                    self.assertFalse(item['enabled'])
                    self.assertTrue(any(r['group']=='research' and not r['met'] for r in item['requirements']))

    def test_background_get_does_not_set_command_busy_flag_source_contract(self):
        body=function(self.main,'_request_state')
        self.assertNotRegex(body,r'(?m)^\s*request_pending\s*=')
        self.assertIn('state_request_pending = true',body)
        self.assertIn('HTTPRequest.new()',body)
        self.assertIn('HTTPClient.METHOD_GET',body)
        request=function(self.main,'_request')
        self.assertLess(request.index('if kind == "state"'), request.index('if request_pending:'))
        self.assertLess(request.index('_cancel_state_request()'),request.index('request_pending = true'))

    def test_old_read_generation_is_rejected_and_cannot_clear_mutation_flag(self):
        body=function(self.main,'_on_state_response')
        self.assertIn('if generation != state_request_generation:',body)
        self.assertNotRegex(body,r'(?m)^\s*request_pending\s*=')
        self.assertIn('state_request_generation += 1', function(self.main,'_cancel_state_request'))
        for method in ('_reset_world','_on_connection_edited','_apply_language_change'):
            self.assertIn('_cancel_state_request()',function(self.main,method),method)

    def test_interactions_defer_state_replacement_without_replaying_purchases(self):
        guard=source('interaction_guard.gd')
        self.assertIn('event.canceled',guard)
        self.assertIn('NOTIFICATION_APPLICATION_FOCUS_OUT',guard)
        self.assertNotIn('accept_event(',guard)
        self.assertNotIn('Input.parse_input_event',guard)
        self.assertIn('if _ui_interacting():',function(self.main,'_apply_state'))
        self.assertIn('deferred_state = next_state.duplicate(true)',function(self.main,'_apply_state'))
        self.assertIn('_flush_deferred_state()',function(self.main,'_process'))
        self.assertIn('request_pending',function(self.main,'_flush_deferred_state'))
        self.assertIn('BaseButton.ACTION_MODE_BUTTON_RELEASE',function(self.main,'_button'))
        self.assertIn('event.canceled',source('catalog_card.gd'))

    def test_colony_change_stays_foreground_to_prevent_wrong_planet_orders(self):
        self.assertIn('"colony" if not requested_planet.is_empty() else "state"',function(self.main,'_poll'))
        self.assertIn('_poll(true)',function(self.main,'_select_owned_planet'))
        self.assertIn('not requested_planet.is_empty()', function(self.main,'_request'))

    def test_settings_and_persisted_language_keep_native_entry_points(self):
        self.assertIn('menu.name = "SettingsButton"', self.main)
        self.assertIn('_add_language_picker(options_panel)',self.main)
        self.assertIn('var locale: String = "en"', source('i18n.gd'))
        self.assertIn('user://language.cfg',source('i18n.gd'))
        self.assertIn('settings.save(SETTINGS_PATH)',source('i18n.gd'))
        self.assertGreaterEqual(self.main.count('"Accept-Language: " + I18n.locale'),3)

    def test_server_tests_and_private_sources_are_excluded_from_android(self):
        filters=re.findall(r'^exclude_filter="(.*)"$',(ROOT/'export_presets.cfg').read_text(),re.M)
        for value in filters:
            for exclusion in ('railway/*','server/*','tests/*','*.keystore','*.jks','data/*'):
                self.assertIn(exclusion,value.split(','))


if __name__=='__main__':
    unittest.main(verbosity=2)
