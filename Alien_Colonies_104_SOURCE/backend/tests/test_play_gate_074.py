"""0.7.4 compatibility regression tests. Disposable local servers only.
Static client checks are intentionally labelled as such; they do NOT execute Godot.
"""
from contextlib import contextmanager
import copy
import http.client
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch

from server import main as app
from server.balance_reset import BALANCE_RESET_ID

ROOT=Path(__file__).resolve().parents[1]

class PlayGateHTTPTests(unittest.TestCase):
    @contextmanager
    def running(self):
        world=app.World(':memory:')
        policy=app.load_update_policy({'PGR_LATEST_VERSION_CODE':'33','PGR_LATEST_VERSION':'0.7.4','PGR_MIN_VERSION_CODE':'33'})
        server=app.build_server(world,port=0,update_policy=policy)
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
        def request(path,method='GET',payload=None,versions=(),token=None):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_address[1],timeout=5)
            body=json.dumps(payload).encode() if payload is not None else b''
            try:
                connection.putrequest(method,path)
                connection.putheader('Content-Type','application/json')
                connection.putheader('Content-Length',str(len(body)))
                for v in versions:connection.putheader('X-PGR-Client-Version',v)
                if token:connection.putheader('Authorization','Bearer '+token)
                connection.endheaders(body)
                result=connection.getresponse();raw=result.read()
                try:data=json.loads(raw)
                except (ValueError,UnicodeDecodeError):data=raw.decode('utf-8')
                return result.status,data,dict(result.getheaders())
            finally:connection.close()
        try:yield world,server,request
        finally:
            server.shutdown();server.server_close();thread.join(3);world.close()

    def test_public_pages_and_manifest_available_with_enforcement(self):
        with self.running() as (_,_,request):
            for path in ('/health','/api/client-version','/privacy','/delete-account'):
                with self.subTest(path=path):self.assertEqual(request(path)[0],200)
            status,m,headers=request('/api/client-version')
            self.assertEqual(m['play_store_url'],app.PLAY_STORE_URL)
            self.assertEqual(m['download_url'],'')
            self.assertEqual(m['min_version_code'],33)
            self.assertEqual(headers['Cache-Control'],'no-store')

    def test_all_sensitive_routes_reject_legacy_clients_before_state_changes(self):
        with self.running() as (world,_,request):
            before=copy.deepcopy(world.data)
            paths=(('/api/state','GET'),('/api/login','POST'),('/api/register','POST'),
                   ('/api/action','POST'),('/api/preview','POST'),('/api/recover','POST'),
                   ('/api/account/password','POST'),('/api/logout','POST'))
            with patch.object(world,'advance',side_effect=AssertionError('gate must precede simulation')):
                for path,method in paths:
                    for version in ((),('31',),('32',),('0.7.4',),('33','33')):
                        with self.subTest(path=path,version=version):
                            status,err,_=request(path,method,{},version)
                            self.assertEqual(status,426)
                            self.assertEqual(err['code'],'update_required')
                            self.assertEqual(err['update']['min_version_code'],33)
            self.assertEqual(world.data,before)
            self.assertEqual(world.db.execute('SELECT count(*) FROM accounts').fetchone()[0],0)

    def test_current_can_login_and_old_session_becomes_current_without_losing_empire(self):
        with self.running() as (world,_,request):
            account=world.register('KeepEmpire','LocalPassword074!')
            token=account['token'];id=account['state']['player']['id']
            self.assertEqual(request('/api/state',versions=('32',),token=token)[0],426)
            status,state,_=request('/api/state',versions=('33',),token=token)
            self.assertEqual(status,200)
            self.assertEqual(state['state']['player']['id'],id)
            self.assertEqual(request('/api/state',versions=('34',),token=token)[0],200)
            self.assertEqual(request('/api/state',versions=('33',))[0],401)

    def test_disabling_minimum_restores_access_no_reinstallation_or_new_account(self):
        with self.running() as (world,server,request):
            account=world.register('RollbackPilot','LocalPassword074!')
            token=account['token']
            self.assertEqual(request('/api/state',versions=('31',),token=token)[0],426)
            # Production applies this new object after redeploy; no live admin API is added.
            server.update_policy=app.load_update_policy({'PGR_MIN_VERSION_CODE':'0'})
            self.assertEqual(request('/api/state',versions=('31',),token=token)[0],200)

    def test_version_header_is_not_an_authentication_bypass(self):
        with self.running() as (_,_,request):
            for code in ('33','9999','2100000000'):
                self.assertEqual(request('/api/action','POST',{'type':'build'},(code,))[0],401)

    def test_flat_and_packaged_server_code_are_identical(self):
        self.assertEqual((ROOT/'server/main.py').read_bytes(),(ROOT/'railway/app.py').read_bytes())
        for name in ('balance_reset.py','swarm_ai.py','defenses.py','intelligence.py'):
            self.assertEqual((ROOT/'server'/name).read_bytes(),(ROOT/'railway'/name).read_bytes())
        self.assertEqual(BALANCE_RESET_ID,'slow-economy-072')

class PlayGateStaticClientTests(unittest.TestCase):
    def setUp(self):
        self.text=(ROOT/'client/scripts/main.gd').read_text()
        self.ui=(ROOT/'client/scripts/compact_ui.gd').read_text()
    def method(self,name):return self.text.split('func '+name+'(',1)[1].split('\n\nfunc ',1)[0]
    def test_gate_rejects_before_account_callback_and_ignores_broken_metadata(self):
        s=self.method('_on_response')
        self.assertLess(s.index('if response_code == 426:'),s.index('_on_account_response('))
        gate=self.method('_handle_required_update')
        self.assertIn('\n\tupdate_required = true',gate)
        self.assertIn('\n\t_show_update()',gate)
        self.assertNotIn('\n\t\t_show_update()',gate)
    def test_failed_probe_never_clears_required_flag(self):
        self.assertNotIn('update_required = false',self.method('_update_check_failed'))
        self.assertIn('was_required and not update_required',self.method('_on_update_response'))
    def test_known_minimum_disables_gameplay_and_later_button(self):
        for method in ('_request','_poll','_send_fleet'):
            self.assertIn('if update_required',self.method(method))
        self.assertIn('update_later_button.visible = not update_required',self.method('_show_update'))
        self.assertIn('if update_required:',self.method('_dismiss_update'))
    def test_fixed_play_link_and_no_legacy_download_in_play_export(self):
        self.assertIn('com.conradmafer.aliencolonies',self.text)
        self.assertIn('OS.shell_open("market://details?id=" + PLAY_STORE_PACKAGE_ID)',self.method('_open_google_play_update'))
        self.assertNotIn('download_url',self.method('_open_google_play_update'))
        self.assertIn('client/scripts/apk_download.gd',(ROOT/'export_presets.cfg').read_text())
    def test_both_http_channels_send_same_version_header(self):
        for method in ('_request','_check_client_version'):
            self.assertIn('"X-PGR-Client-Version: " + str(CLIENT_VERSION_CODE)',self.method(method))
        self.assertIn('NOTIFICATION_APPLICATION_RESUMED',self.text)
        self.assertIn('update_timer.wait_time = 60.0',self.text)
    def test_release_and_signing_sync_contracts(self):
        self.assertIn(f'const CLIENT_VERSION_CODE: int = {app.CLIENT_VERSION_CODE}',self.text)
        self.assertIn(f'const CLIENT_VERSION_NAME: String = "{app.VERSION}"',self.text)
        self.assertIn(f'version/code={app.CLIENT_VERSION_CODE}',(ROOT/'export_presets.cfg').read_text())
        ps=(ROOT/'tools/build_google_play_aab.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('VERSION_SYNC_074',ps)
        self.assertLess(ps.index('VERSION_SYNC_074'),ps.index("Write-Status '[1/3] Import projektu...'"))
        for key in ('Export-Clixml','Import-Clixml','AlienColonies\\AabBuild','GODOT_ANDROID_KEYSTORE_RELEASE_PASSWORD'):
            self.assertIn(key,ps)
    def test_compact_ui_calls_only_existing_host_symbols(self):
        refs=set(re.findall(r'host\.(\w+)',self.ui))
        defined=set(re.findall(r'^(?:var|const|func)\s+(\w+)',self.text,re.M))
        self.assertEqual(refs-defined-{'add_child','get_tree','is_inside_tree'},set())
    def test_catalogues_preserve_actions_and_art(self):
        for node in ('heading','level','action','costs','amount','reason','art'):
            self.assertIn('controls["'+node+'"]',self.ui)
        self.assertIn('_open_catalog.bind(controls)',self.ui)
        self.assertIn('_details_art(controls["art"].texture)',self.ui)
    def test_scout_and_report_keep_existing_server_data_handlers(self):
        self.assertIn('host._swarm_planet_details(modal_body, planet)',self.ui)
        self.assertIn('host._add_scout_data(modal_body, report["scout"])',self.ui)
        self.assertNotIn('HTTPRequest',self.ui)
    def test_mission_selection_does_not_show_unavailable_ships(self):
        self.assertIn('selection.visible = count > 0',self.ui)
        self.assertIn('quantity.max_value = count',self.ui)
        self.assertIn('host.current_tab == 2 and host.fleet_mode == 0 and composing',self.ui)
    def test_galaxy_and_detail_back_preserve_the_expected_navigation(self):
        self.assertIn('host.galaxy_overview.visible',self.ui)
        self.assertIn('galaxy_map.call("reset_view")',self.method('_show_full_galaxy_map'))
        self.assertIn('compact_ui.close_details()',self.method('_notification'))
    def test_manual_version_sync_and_docs_exist(self):
        self.assertTrue((ROOT/'tools/sync_client_version.py').exists())
        self.assertTrue((ROOT/'docs/GOOGLE_PLAY_UPDATES_074_PL.md').exists())

if __name__=='__main__':unittest.main(verbosity=2)
