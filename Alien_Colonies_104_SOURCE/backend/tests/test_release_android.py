"""Release gates use fake SDK output; these tests do not certify a real Android build."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import export_android as exporter
from tools import prepare_update as metadata

CERT = 'a' * 64
SDK = {'apksigner': 'sdk-apksigner', 'apkanalyzer': 'sdk-apkanalyzer'}
MANIFEST = ('<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
            'package="com.conradmafer.aliencolonies" android:versionCode="17" android:versionName="0.3.0">'
            '<application android:debuggable="false" /></manifest>')
SIGNATURE = 'Signer #1 certificate SHA-256 digest: ' + CERT + '\n'


class AndroidReleaseManifestTests(unittest.TestCase):
    def inspect(self, signature=SIGNATURE, manifest=MANIFEST, **expected):
        with patch.object(metadata, '_sdk_output', side_effect=[signature, manifest]):
            return metadata.inspect_signed_apk(Path('fixture.apk'), sdk_tools=SDK, **expected)

    def test_actual_manifest_and_certificate_are_required(self):
        result = self.inspect(require_release=True, expected_code=17, expected_name='0.3.0', expected_certificate=CERT)
        self.assertFalse(result['debuggable'])
        self.assertEqual(result['version_code'], 17)
        self.assertEqual(result['certificate_sha256'], CERT)

    def test_invalid_manifest_identity_version_and_debug_are_rejected(self):
        changes = [
            MANIFEST.replace('com.conradmafer.aliencolonies', 'com.example.other'),
            MANIFEST.replace('versionCode="17"', 'versionCode="16"'),
            MANIFEST.replace('versionName="0.3.0"', 'versionName="0.2.2"'),
            MANIFEST.replace('debuggable="false"', 'debuggable="true"'),
            MANIFEST.replace('debuggable="false"', 'debuggable="@bool/unknown"'),
            '<html>not an Android manifest</html>',
        ]
        for manifest in changes:
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                self.inspect(manifest=manifest, require_release=True, expected_code=17, expected_name='0.3.0')

    def test_missing_multiple_wrong_signatures_are_rejected(self):
        for signature in ('', 'Signer #1 certificate SHA-256 digest: abcd\n', SIGNATURE + SIGNATURE):
            with self.subTest(signature=signature), self.assertRaises(ValueError):
                self.inspect(signature=signature)
        with self.assertRaises(ValueError):
            self.inspect(expected_certificate='b' * 64)

    def test_sdk_nonzero_signature_verification_cannot_be_ignored(self):
        with patch.object(metadata.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, SIGNATURE, 'secret')):
            with self.assertRaisesRegex(ValueError, 'odrzucilo'):
                metadata.inspect_signed_apk(Path('fixture.apk'), sdk_tools=SDK)

    def test_no_debug_attribute_is_android_false_default(self):
        self.assertFalse(self.inspect(manifest=MANIFEST.replace(' android:debuggable="false"', ''),
                                      require_release=True)['debuggable'])

    def test_cli_reads_apk_manifest_instead_of_current_source_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            apk = Path(folder) / 'arbitrary-file-name.apk'
            with zipfile.ZipFile(apk, 'w') as archive:
                archive.writestr('AndroidManifest.xml', 'fixture only')
            verification = {'version_code': 17, 'version_name': '0.3.0', 'package': metadata.PACKAGE_ID,
                            'debuggable': False, 'certificate_sha256': CERT}
            with patch.object(metadata, 'inspect_signed_apk', return_value=verification), \
                 patch('sys.argv', ['prepare_update.py', str(apk), '--release']), redirect_stdout(io.StringIO()):
                self.assertEqual(metadata.main(), 0)
            details = (Path(folder) / 'DANE_AKTUALIZACJI_RAILWAY.txt').read_text()
            self.assertIn('PGR_LATEST_VERSION_CODE=17\n', details)
            self.assertIn('certificate_sha256=' + CERT, details)


class AndroidReleasePreflightTests(unittest.TestCase):
    def test_release_credentials_are_explicit_and_missing_keys_do_not_run_tools(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(exporter.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'GODOT_ANDROID_KEYSTORE_RELEASE_PATH'):
                exporter.release_signing()
            run.assert_not_called()

    def test_key_password_stays_in_environment_and_fingerprint_uses_exact_der(self):
        with tempfile.TemporaryDirectory() as folder:
            key = Path(folder) / 'user-selected.jks'
            key.write_bytes(b'keystore fixture')
            der = b'\x30fixture public certificate'
            values = {'GODOT_ANDROID_KEYSTORE_RELEASE_PATH': str(key),
                      'GODOT_ANDROID_KEYSTORE_RELEASE_USER': 'existing_alias',
                      'GODOT_ANDROID_KEYSTORE_RELEASE_PASSWORD': 'do-not-log-password'}
            with patch.dict(os.environ, values, clear=True), \
                 patch.object(exporter, 'android_tool', side_effect=lambda name: name), \
                 patch.object(exporter.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, der, b'')) as run:
                environment, sdk, digest = exporter.release_signing()
            command = run.call_args.args[0]
            self.assertNotIn(values['GODOT_ANDROID_KEYSTORE_RELEASE_PASSWORD'], command)
            self.assertIn('-storepass:env', command)
            self.assertEqual(digest, hashlib.sha256(der).hexdigest())
            self.assertEqual(environment['GODOT_ANDROID_KEYSTORE_RELEASE_USER'], 'existing_alias')

    def test_keytool_error_output_is_not_leaked(self):
        with tempfile.TemporaryDirectory() as folder:
            key = Path(folder) / 'key.jks'
            key.touch()
            values = {'GODOT_ANDROID_KEYSTORE_RELEASE_PATH': str(key),
                      'GODOT_ANDROID_KEYSTORE_RELEASE_USER': 'alias',
                      'GODOT_ANDROID_KEYSTORE_RELEASE_PASSWORD': 'private-password'}
            with patch.dict(os.environ, values, clear=True), patch.object(exporter, 'android_tool', return_value='tool'), \
                 patch.object(exporter.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, b'', b'private-password')):
                with self.assertRaises(ValueError) as error:
                    exporter.release_signing()
                self.assertNotIn('private-password', str(error.exception))

    def test_release_rejects_tunnel_http_and_private_dns(self):
        for endpoint in ({'server_url': 'https://x.trycloudflare.com', 'temporary': True},
                         {'server_url': 'http://public.example', 'temporary': False}):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                exporter.release_endpoint(endpoint)
        for address in ('127.0.0.1', '192.168.1.1', '::1'):
            with patch.object(socket, 'getaddrinfo', return_value=[(None, None, None, None, (address, 443))]), \
                 self.assertRaises(ValueError):
                exporter.release_endpoint({'server_url': 'https://hidden-private.example', 'temporary': False})
        with patch.object(socket, 'getaddrinfo', return_value=[(None, None, None, None, ('1.1.1.1', 443))]):
            exporter.release_endpoint({'server_url': 'https://public.example', 'temporary': False})

    def test_failed_metadata_publication_restores_both_previous_files(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            staging = directory / 'staging'
            staging.mkdir()
            apk, details = directory / 'game.apk', directory / 'details.txt'
            staged_apk, staged_details = staging / 'game.apk', staging / 'details.txt'
            for path, contents in ((apk, b'old apk'), (details, b'old details'),
                                   (staged_apk, b'new apk'), (staged_details, b'new details')):
                path.write_bytes(contents)
            original = Path.replace
            def failing_metadata(path, target):
                if path == staged_details:
                    raise OSError('disk full')
                return original(path, target)
            with patch.object(Path, 'replace', failing_metadata), self.assertRaises(OSError):
                exporter.publish_verified(staged_apk, apk, staged_details, details)
            self.assertEqual(apk.read_bytes(), b'old apk')
            self.assertEqual(details.read_bytes(), b'old details')


class AndroidReleaseExportFlowTests(unittest.TestCase):
    def test_previous_apk_with_same_or_newer_code_blocks_before_godot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'builds').mkdir()
            (root / 'export_presets.cfg').write_text(
                '[preset.2]\nname="Android Release"\n[preset.2.options]\nversion/code=17\nversion/name="0.3.0"\n')
            for previous_code in (17, 18):
                with self.subTest(previous_code=previous_code), \
                     patch.object(exporter, '__file__', str(root / 'tools' / 'export_android.py')), \
                     patch.object(exporter, 'choose_endpoint', return_value={'server_url': 'https://public.example', 'temporary': False}), \
                     patch.object(exporter, 'release_endpoint'), \
                     patch.object(exporter, 'release_signing', return_value=({}, SDK, CERT)), \
                     patch.object(exporter, 'inspect_signed_apk', return_value={'version_code': previous_code}) as inspect, \
                     patch.object(exporter.subprocess, 'run') as run, \
                     patch('sys.argv', ['export_android.py', '--release', '--previous-apk', 'old.apk', '--no-open']), \
                     redirect_stdout(io.StringIO()):
                    self.assertEqual(exporter.main(), 1)
                    self.assertEqual(inspect.call_args.kwargs['expected_certificate'], CERT)
                    run.assert_not_called()

    def exercise(self, *, verification_error=False, metadata_error=False, godot_error=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'tools').mkdir()
            (root / 'client').mkdir()
            (root / 'builds').mkdir()
            source = root / 'client' / 'server_config.json'
            original = b'{"server_url":"https://original.example","note":"preserve"}'
            source.write_bytes(original)
            presets = root / 'export_presets.cfg'
            presets.write_text('[preset.2]\nname="Android Release"\n[preset.2.options]\nversion/code=17\nversion/name="0.3.0"\n')
            original_presets = presets.read_bytes()
            apk = root / 'builds' / exporter.RELEASE_APK_NAME
            details = root / 'builds' / 'DANE_AKTUALIZACJI_RAILWAY_RELEASE.txt'
            apk.write_bytes(b'old apk')
            details.write_bytes(b'old metadata')
            commands = []
            def godot(command, **kwargs):
                commands.append(command)
                self.assertEqual(json.loads(source.read_text())['server_url'], 'https://public.example')
                self.assertEqual(apk.read_bytes(), b'old apk')
                self.assertEqual(kwargs['env']['GODOT_ANDROID_KEYSTORE_RELEASE_PASSWORD'], 'my-secret')
                if '--export-release' in command:
                    self.assertIn('Android Release', command)
                    with zipfile.ZipFile(command[-1], 'w') as archive:
                        archive.writestr('AndroidManifest.xml', 'synthetic fixture')
                return subprocess.CompletedProcess(command, int(godot_error), 'Godot diagnostic my-secret')
            verification = {'version_code': 17, 'version_name': '0.3.0', 'package': metadata.PACKAGE_ID,
                            'debuggable': False, 'certificate_sha256': CERT}
            secrets = {'GODOT_ANDROID_KEYSTORE_RELEASE_PASSWORD': 'my-secret'}
            actual_write = exporter.write_update_details
            def write(*args, **kwargs):
                if metadata_error:
                    raise OSError('cannot write metadata')
                return actual_write(*args, **kwargs)
            with patch.object(exporter, '__file__', str(root / 'tools' / 'export_android.py')), \
                 patch.dict(os.environ, secrets), \
                 patch.object(exporter, 'release_endpoint'), \
                 patch.object(exporter, 'release_signing', return_value=(secrets, SDK, CERT)), \
                 patch.object(exporter, 'choose_engine', return_value='godot'), \
                 patch.object(exporter.subprocess, 'run', side_effect=godot), \
                 patch.object(exporter, 'inspect_signed_apk', side_effect=ValueError('wrong signature') if verification_error else None,
                              return_value=verification) as inspect, \
                 patch.object(exporter, 'write_update_details', side_effect=write), \
                 patch('sys.argv', ['export_android.py', '--release', '--no-open', '--no-dialog', '--server-url', 'https://public.example']), \
                 redirect_stdout(io.StringIO()):
                result = exporter.main()
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(presets.read_bytes(), original_presets)
            self.assertEqual(list((root / 'builds').glob('apk-export-*')), [])
            log = (root / 'builds' / 'export_release_log.txt').read_text()
            self.assertNotIn('my-secret', log)
            if verification_error or metadata_error or godot_error:
                self.assertEqual(result, 1)
                self.assertEqual(apk.read_bytes(), b'old apk')
                self.assertEqual(details.read_bytes(), b'old metadata')
            else:
                self.assertEqual(result, 0)
                self.assertIn('--export-release', commands[-1])
                self.assertTrue(inspect.call_args.kwargs['require_release'])
                self.assertEqual(inspect.call_args.kwargs['expected_certificate'], CERT)
                self.assertIn('PGR_LATEST_VERSION_CODE=17\n', details.read_text())
                self.assertNotEqual(apk.read_bytes(), b'old apk')

    def test_verified_release_has_distinct_profile_and_metadata(self):
        self.exercise()

    def test_manifest_or_signature_failure_does_not_publish(self):
        self.exercise(verification_error=True)

    def test_metadata_failure_keeps_previous_apk(self):
        self.exercise(metadata_error=True)

    def test_godot_failure_restores_source_and_old_release(self):
        self.exercise(godot_error=True)


if __name__ == '__main__':
    unittest.main()
