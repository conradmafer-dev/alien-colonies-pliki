"""Source contracts/localizations plus real server mission tests.
These are deliberately NOT presented as executed native Godot UI tests.
Run: python -m unittest tests.test_visual_fleet_0114 -v
"""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from server import main as app

ROOT = Path(__file__).resolve().parents[1]


def source(name):
    return (ROOT / 'client/scripts' / name).read_text(encoding='utf-8')


def function(text, name):
    match = re.search(r'^(?:static )?func ' + re.escape(name) + r'\([^\n]*\).*?:\n(.*?)(?=^(?:static )?func |\Z)', text, re.M | re.S)
    if not match:
        raise AssertionError('Missing function: ' + name)
    return match.group(1)


class VisualFleetSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = source('main.gd')
        cls.ui = source('fleet_navigation.gd')
        cls.model = source('fleet_navigation_model.gd')
        cls.route = source('fleet_route.gd')
        cls.compact = source('compact_ui.gd')

    def test_new_component_is_wired_into_production_scene(self):
        ready = function(self.main, '_ready')
        self.assertLess(ready.index('compact_ui.setup(self)'), ready.index('fleet_navigation.setup(self)'))
        self.assertLess(ready.index('planetary_ui.setup(self)'), ready.index('fleet_navigation.setup(self)'))
        self.assertIn('fleet_navigation.refresh()', function(self.main, '_apply_state_now'))
        self.assertIn('fleet_navigation.composer_opened()', function(self.compact, 'open_composer'))

    def test_default_empty_destination_uses_graphical_picker(self):
        self.assertIn('host.selected_target.is_empty()', function(self.ui, 'composer_opened'))
        self.assertIn('open_destination_map()', function(self.ui, 'composer_opened'))
        self.assertIn('picker_map = GalaxyMap.new()', function(self.ui, 'open_destination_map'))
        self.assertIn('picker_map.system_selected.connect(_select_system)', self.ui)
        self.assertIn('VisualDestinationPlanets', self.ui)
        self.assertIn('picture.texture = _art(record)', self.ui)

    def test_destinations_and_facts_are_public_state_not_mockup_values(self):
        self.assertIn('world.get("galaxy", [])', self.model)
        self.assertIn('environment.get("multipliers", {})', self.ui)
        for fake in ('420 LY', 'Zeta-3', '3h 28m', '120000', 'Habitability'):
            self.assertNotIn(fake, self.ui + self.model)
        self.assertIn('get("known", false)', function(self.ui, '_art'))
        self.assertIn('return null', function(self.ui, '_art'))

    def test_unknown_target_is_recon_only_and_origin_is_rejected(self):
        check = function(self.model, 'mission_reason')
        self.assertIn('world.get("planet_id", "")', check)
        self.assertIn('record.get("known", false)', check)
        self.assertIn('mission != 0', check)
        self.assertIn('"planet": {}', function(self.model, 'target'))
        self.assertIn('visibility_text', self.ui)

    def test_destination_switch_preserves_fleet_cargo_and_source(self):
        choose = function(self.ui, '_select_destination')
        self.assertIn('host.selected_target = id', choose)
        self.assertNotIn('selected_planet =', choose)
        self.assertNotIn('cargo_inputs', choose)
        self.assertNotIn('.value = 0', choose)
        self.assertNotIn('.clear()', choose)
        required = function(self.ui, '_add_required_ship')
        self.assertIn('value) < 1', required)
        self.assertIn('.value = 1', required)
        self.assertIn('get(key, 0)) > 0', required)

    def test_model_blocks_wrong_context_and_missing_units(self):
        check = function(self.model, 'mission_reason')
        self.assertIn('kind != "empty"', check)
        self.assertIn('allied(world, record)', check)
        self.assertIn('protected_until', check)
        draft = function(self.model, 'draft_reason')
        for text in ('"scout"', '"colonizer"', '"combat"', '"colonies"', '"outbound"', '10000'):
            self.assertIn(text, draft)
        self.assertIn('>= 8', draft)
        self.assertIn('capacity(world, ships)', draft)

    def test_colonization_and_transport_both_include_supplies(self):
        self.assertIn('index in [1, 3]', function(self.main, '_mission_changed'))
        self.assertIn('mission_picker.selected in [1, 3]', function(self.main, '_fleet_payload'))
        self.assertIn('payload["cargo"] = cargo', function(self.main, '_fleet_payload'))
        self.assertIn('roundf(total * 1000000.0) / 1000000.0', function(self.model, 'capacity'))

    def test_ui_never_computes_route_prices_or_sends_new_endpoint(self):
        for api in ('HTTPRequest', 'HTTPClient', 'http.request', '"/api/action"', '"/api/preview"'):
            self.assertNotIn(api, self.ui + self.model + self.route)
        for field in ('seconds', 'fuel_cost', 'capacity'):
            self.assertIn('last_quote.get("'+field+'"', function(self.ui, 'refresh'))
        self.assertIn('fleet_navigation.accept_quote(response)', function(self.main, '_handle_response'))

    def test_old_quote_cannot_follow_changed_payload(self):
        self.assertIn('last_quote.clear()', function(self.ui, 'invalidate'))
        self.assertIn('preview_fingerprint != host._fleet_fingerprint()', function(self.ui, 'accept_quote'))
        self.assertIn('preview_requested_fingerprint != _fleet_fingerprint()', function(self.main, '_handle_response'))
        self.assertIn('confirmation_fingerprint != host._fleet_fingerprint()', function(self.ui, '_confirm_dispatch'))
        self.assertIn('preview_fingerprint != _fleet_fingerprint()', function(self.main, '_send_fleet'))

    def test_confirmation_cannot_replay_or_skip_server_checks(self):
        setup = function(self.ui, 'setup')
        self.assertIn('pressed.disconnect(host._send_fleet)', setup)
        self.assertIn('pressed.connect(confirm_departure)', setup)
        confirm = function(self.ui, '_confirm_dispatch')
        self.assertIn('host.request_pending', confirm)
        self.assertIn('not host.quote_ready', confirm)
        self.assertIn('not draft_reason().is_empty()', confirm)
        self.assertIn('host._send_fleet()', confirm)
        self.assertIn('payload["request_id"] = _new_request_id()', function(self.main, '_send_fleet'))

    def test_price_signature_ignores_timestamp_only_intel_updates(self):
        signature = function(self.main, '_quote_world_signature')
        self.assertNotIn('observed_at', signature)
        self.assertNotIn('scouted_at', signature)
        for text in ('owner_id', 'owner_type', 'alliance_id', 'protected_until', 'navigation_stats', 'mission_slots', 'own_planets'):
            self.assertIn(text, signature)

    def test_long_quote_is_scrollable_dock_has_short_destination(self):
        setup = function(self.ui, 'setup')
        self.assertIn('host.quote_label.reparent(summary)', setup)
        self.assertIn('dock_target.max_lines_visible = 2', setup)
        self.assertIn('dock_summary.max_lines_visible = 2', setup)
        self.assertIn('host.send_button', setup)
        self.assertIn('host.preview_button.disabled', self.ui)

    def test_modal_back_and_touch_layers_reuse_existing_behavior(self):
        self.assertIn('host.compact_ui._begin_details', self.ui)
        self.assertIn('close_details()', function(self.ui, '_select_destination'))
        self.assertIn('Control.MOUSE_FILTER_IGNORE', function(self.ui, '_button_margin'))
        self.assertIn('picture.mouse_filter = Control.MOUSE_FILTER_IGNORE', self.ui)
        self.assertIn('Control.MOUSE_FILTER_IGNORE', function(self.route, '_ready'))
        self.assertIn('NOTIFICATION_WM_GO_BACK_REQUEST', self.main)

    def test_map_zoom_and_pan_retained_and_route_does_not_change_coordinates(self):
        self.assertIn('picker_map.zoom_out', self.ui)
        self.assertIn('picker_map.zoom_in', self.ui)
        self.assertIn('picker_map.reset_view', self.ui)
        self.assertIn('set_route(origin_system, browse_system)', self.ui)
        galaxy = source('galaxy_map.gd')
        self.assertIn('func set_route(', galaxy)
        self.assertIn('_draw_route()', function(galaxy, '_draw'))
        self.assertNotIn('systems =', function(galaxy, 'set_route'))

    def test_auth_update_gate_and_tunnel_mode_are_preserved(self):
        self.assertIn('payload["travel_mode"] = "tunnel"', function(self.main, '_fleet_payload'))
        self.assertIn('_append(host.megastructure_ui.fleet_box, form)', self.ui)
        self.assertIn('host.update_required', function(self.ui, '_confirm_dispatch'))
        self.assertIn('not host.requested_planet.is_empty()', function(self.ui, 'refresh'))
        self.assertIn('Accept-Language', self.main)

    def test_all_new_strings_have_five_locales_and_matching_placeholders(self):
        additions = json.loads((ROOT/'localization/fleet_navigation_source.json').read_text())
        self.assertEqual(set(additions), {'en', 'pl', 'de', 'es', 'fr'})
        placeholders = re.compile(r'%(?:\d+\$)?[-+0 #]*\d*(?:\.\d+)?[sdf]')
        for locale, mapping in additions.items():
            self.assertEqual(set(mapping), set(additions['pl']))
            full = json.loads((ROOT/'localization'/f'{locale}.json').read_text())
            for key, value in mapping.items():
                self.assertTrue(value)
                self.assertEqual(full[key], value, (locale, key))
                self.assertEqual(placeholders.findall(key), placeholders.findall(value), (locale, key))
        # Every literal I18n.t string in new code must exist in all five dictionaries.
        literals = re.findall(r'I18n\.t\(("(?:[^"\\]|\\.)*")\)', self.ui + self.route)
        for quoted in literals:
            key = json.loads(quoted)
            for locale in additions:
                full = json.loads((ROOT/'localization'/f'{locale}.json').read_text())
                self.assertTrue(full.get(key), (locale, key))

    def test_native_runtime_scene_is_present_and_all_requests_are_intercepted(self):
        scene = (ROOT/'tests/test_fleet_navigation_0114.gd').read_text()
        self.assertIn('func _request(path: String, payload: Dictionary, kind: String, _method: int = HTTPClient.METHOD_POST)', scene)
        self.assertIn('captured.append', scene)
        self.assertNotIn('super._request(', scene)
        self.assertIn('test_fleet_navigation_0114.gd', (ROOT/'tests/test_fleet_navigation_0114.tscn').read_text())


class ExistingServerMissionCompatibility(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.world = app.World(str(Path(self.temp.name)/'fleet.sqlite3'), 1, now=1800000000)
        account = self.world.register('visual_fleet_test', 'Offline-only-9274742')
        self.owner = account['state']['player']['id']
        self.pid = account['state']['planet_id']
        self.world.action(self.owner, {'type':'choose_race','race_id':'zetans','planet_id':self.pid})
        self.home = self.world.data['planets'][self.pid]
        self.home['resources'] = dict.fromkeys(app.RESOURCES, 10000000)
        self.home['ships'].update(scout=3,colonizer=2,cargo=2,frigate=8)
        self.free = next(p for p in self.world.data['planets'].values() if p['owner_type']=='empty' and p['galaxy_id']==self.home['galaxy_id'])
        self.world._capture_planetary_intel(self.owner, self.free)

    def tearDown(self):
        self.world.close()
        self.temp.cleanup()

    def payload(self, mission='colonize', **extra):
        return {'type':'fleet','planet_id':self.pid,'target_id':self.free['id'], 'mission':mission,
                'ships':{'colonizer':1, 'frigate':2, 'cargo':1}, 'cargo':{'metal':80,'crystal':40,'fuel':10}, **extra}

    def test_preview_with_colonization_supplies_is_pure(self):
        before = copy.deepcopy(self.home)
        fleets = copy.deepcopy(self.world.data['fleets'])
        response = self.world.preview(self.owner, self.payload())
        self.assertTrue(response['ok'] and response['affordable'])
        for field in ('seconds','fuel_cost','capacity'):
            self.assertGreater(response[field],0)
        self.assertEqual(self.home,before)
        self.assertEqual(self.world.data['fleets'],fleets)

    def test_chosen_target_and_cargo_reach_existing_action_unchanged(self):
        payload = self.payload(request_id='fleet-visual-confirm-1')
        quote = self.world.preview(self.owner,payload)
        before = copy.deepcopy(self.home)
        self.world.action(self.owner,payload)
        fleet = next(f for f in self.world.data['fleets'].values() if f['owner_id']==self.owner)
        self.assertEqual(fleet['target_id'],self.free['id'])
        self.assertEqual(fleet['cargo'],payload['cargo'])
        self.assertEqual(before['resources']['fuel'] - self.home['resources']['fuel'], quote['fuel_cost'] + 10)
        self.assertEqual(before['ships']['frigate']-self.home['ships']['frigate'],2)

    def test_double_confirmation_is_idempotent(self):
        payload = self.payload(request_id='fleet-visual-confirm-2')
        self.world.action(self.owner,payload)
        home = copy.deepcopy(self.home)
        fleets = copy.deepcopy(self.world.data['fleets'])
        self.world.action(self.owner,payload)
        self.assertEqual(self.home,home)
        self.assertEqual(self.world.data['fleets'],fleets)

    def test_unknown_target_only_accepts_scout(self):
        hidden = next(p for p in self.world.data['planets'].values() if p['owner_type']=='empty' and not self.world._known_planet(self.owner,p))
        payload = self.payload(target_id=hidden['id'])
        with self.assertRaises(app.GameError): self.world.preview(self.owner,payload)
        payload.update(mission='scout', ships={'scout':1}, cargo={})
        self.assertTrue(self.world.preview(self.owner,payload)['ok'])

    def test_missing_colonizer_and_over_capacity_are_rejected(self):
        for payload in (self.payload(ships={'frigate':1}), self.payload(cargo={'metal':9999999})):
            with self.subTest(payload=payload), self.assertRaises(app.GameError):
                self.world.preview(self.owner,payload)

    def test_target_ownership_is_revalidated_after_preview(self):
        payload = self.payload(request_id='fleet-changed-target-1')
        self.world.preview(self.owner,payload)
        self.free.update(owner_type='player',owner_id=self.owner)
        before = copy.deepcopy(self.home)
        with self.assertRaises(app.GameError): self.world.action(self.owner,payload)
        self.assertEqual(self.home,before)

    def test_unaffordable_preview_explains_shortfall_but_does_not_dispatch(self):
        self.home['resources'] = dict.fromkeys(app.RESOURCES,0)
        result = self.world.preview(self.owner,self.payload(allow_unaffordable=True))
        self.assertFalse(result['affordable'])
        self.assertGreater(result['shortfall']['fuel'],0)
        with self.assertRaises(app.GameError): self.world.action(self.owner,self.payload())

    def test_transport_to_own_colony_uses_same_supplies_flow(self):
        self.free.update(owner_id=self.owner,owner_type='player')
        result = self.world.preview(self.owner,self.payload('transport',ships={'cargo':1}))
        self.assertTrue(result['ok'])
        self.assertGreaterEqual(result['capacity'],130)

    def test_cross_galaxy_route_price_comes_from_server(self):
        near = self.world.preview(self.owner,self.payload())
        remote = next(p for p in self.world.data['planets'].values() if p['owner_type']=='empty' and p['galaxy_id']!=self.home['galaxy_id'])
        self.world._capture_planetary_intel(self.owner, remote)
        far = self.world.preview(self.owner,self.payload(target_id=remote['id'],allow_unaffordable=True))
        self.assertTrue(far['route']['intergalactic'])
        self.assertGreater(far['fuel_cost'],near['fuel_cost'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
