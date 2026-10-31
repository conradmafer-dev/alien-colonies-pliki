"""Exercise the export entry point without running Godot or installing an APK.

Synthetic ZIP fixtures validate publication and rollback, not Android signatures.
"""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import export_android


SHUTDOWN_MESSAGE = (
    'ERROR: EditorSettings not instantiated yet when getting setting '
    '"export/android/shutdown_adb_on_exit".'
)
ORIGINAL_CONFIG = b'{"server_url": "https://original.studio.pl", "note": "preserve me"}\n'
NEW_SERVER_URL = "https://build.studio.pl"
OLD_DETAILS = b"metadata belonging to the previous successful APK\n"


class AndroidExportScenarios(unittest.TestCase):
    def make_apk_fixture(self, path, contents=b"synthetic new APK payload"):
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("AndroidManifest.xml", contents)

    def exercise_export(self, outputs, codes=(0, 0), apk_kind="valid", extra_args=()):
        """Use real temporary files while replacing only process/tool selection."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "tools").mkdir()
            (root / "client").mkdir()
            (root / "builds").mkdir()
            config = root / "client" / "server_config.json"
            config.write_bytes(ORIGINAL_CONFIG)
            (root / "export_presets.cfg").write_text(
                '[preset.0.options]\nversion/code=6\nversion/name="0.1.5"\n',
                encoding="utf-8",
            )
            artifact = root / "builds" / export_android.APK_NAME
            self.make_apk_fixture(artifact, b"previous successful APK payload")
            old_apk = artifact.read_bytes()
            details = root / "builds" / "DANE_AKTUALIZACJI_RAILWAY.txt"
            details.write_bytes(OLD_DETAILS)
            calls = []

            def fake_godot(command, **kwargs):
                stage = len(calls)
                calls.append(command)
                self.assertEqual(kwargs["cwd"], root)
                self.assertIsNone(kwargs["env"], "Debug must preserve Godot environment/settings, not replace signing credentials")
                self.assertEqual(json.loads(config.read_text())["server_url"], NEW_SERVER_URL)
                self.assertEqual(artifact.read_bytes(), old_apk)
                self.assertEqual(details.read_bytes(), OLD_DETAILS)
                if stage == 0:
                    self.assertIn("--import", command)
                else:
                    self.assertEqual(stage, 1, "Only import and export should run")
                    self.assertIn("--export-debug", command)
                    staged_apk = Path(command[-1])
                    self.assertNotEqual(staged_apk, artifact)
                    self.assertFalse(staged_apk.exists(), "An export needs a fresh output path")
                    if apk_kind == "valid":
                        self.make_apk_fixture(staged_apk)
                    elif apk_kind == "empty":
                        staged_apk.write_bytes(b"")
                    elif apk_kind == "corrupt":
                        staged_apk.write_bytes(b"not a ZIP archive")
                    elif apk_kind == "source_zip":
                        with zipfile.ZipFile(staged_apk, "w") as archive:
                            archive.writestr("project.godot", "source, not APK")
                    elif apk_kind == "bad_crc":
                        payload = b"unique fixture bytes to corrupt"
                        self.make_apk_fixture(staged_apk, payload)
                        raw = staged_apk.read_bytes()
                        self.assertEqual(raw.count(payload), 1)
                        staged_apk.write_bytes(raw.replace(payload, b"X" + payload[1:]))
                    else:
                        self.assertEqual(apk_kind, "missing")
                return subprocess.CompletedProcess(command, codes[stage], outputs[stage])

            with (
                patch.object(export_android, "__file__", str(root / "tools" / "export_android.py")),
                patch.object(export_android, "choose_engine", return_value="fixture-godot"),
                patch.object(export_android, "release_signing", side_effect=AssertionError("Test APK must not request a release key")),
                patch.dict(export_android.os.environ, {}, clear=True),
                patch.object(export_android.subprocess, "run", side_effect=fake_godot),
                patch.object(export_android.sys, "argv", [
                    "export_android.py", "--no-dialog", "--no-open", "--server-url", NEW_SERVER_URL, *extra_args,
                ]),
                redirect_stdout(io.StringIO()),
            ):
                result = export_android.main()

            self.assertEqual(config.read_bytes(), ORIGINAL_CONFIG,
                             "Editor server configuration must be restored on every exit")
            self.assertEqual(list((root / "builds").glob("apk-export-*")), [],
                             "Temporary export directories must be removed")
            return {
                "result": result,
                "calls": calls,
                "old_apk": old_apk,
                "apk": artifact.read_bytes(),
                "details": details.read_bytes(),
            }

    def assert_previous_release_preserved(self, outcome, expected_calls):
        self.assertEqual(outcome["result"], 1)
        self.assertEqual(len(outcome["calls"]), expected_calls)
        self.assertEqual(outcome["apk"], outcome["old_apk"])
        self.assertEqual(outcome["details"], OLD_DETAILS)

    def test_successful_import_and_export_accept_only_known_shutdown_diagnostic(self):
        outputs = [
            "Import/export completed.\n",
            SHUTDOWN_MESSAGE + "\n   at: _EDITOR_GET (editor/settings/editor_settings.cpp:1531)\n",
            "\x1b[91m" + SHUTDOWN_MESSAGE + "\x1b[0m\n",
            "\x1b[91mERROR:\x1b[0m" + SHUTDOWN_MESSAGE[len("ERROR:"):] + "\n",
        ]
        for output in outputs:
            with self.subTest(output=repr(output)):
                outcome = self.exercise_export((output, output))
                self.assertEqual(outcome["result"], 0)
                self.assertEqual(len(outcome["calls"]), 2)
                self.assertNotEqual(outcome["apk"], outcome["old_apk"])
                metadata = outcome["details"].decode("utf-8")
                self.assertIn("PGR_LATEST_VERSION_CODE=6\n", metadata)
                self.assertIn("PGR_LATEST_VERSION=0.1.5\n", metadata)
                self.assertIn("PGR_APK_SHA256=" + hashlib.sha256(outcome["apk"]).hexdigest(), metadata)
                self.assertIn("PGR_APK_SIZE_BYTES=" + str(len(outcome["apk"])), metadata)

    def test_explicit_test_mode_exports_without_any_release_credentials(self):
        outcome = self.exercise_export(("Import complete", "Export complete"), extra_args=("--test",))
        self.assertEqual(outcome["result"], 0)
        self.assertIn("--export-debug", outcome["calls"][-1])
        self.assertIn("Android Test", outcome["calls"][-1])
        self.assertNotIn("--export-release", outcome["calls"][-1])

    def test_real_errors_still_block_both_stages_even_with_exit_zero(self):
        errors = [
            "SCRIPT ERROR: Parse Error: Identifier missing in current scope.\n",
            "Parse Error: Unexpected token in client/main.gd.\n",
            "ERROR: Android export templates are missing.\n",
            SHUTDOWN_MESSAGE.replace("shutdown_adb_on_exit", "android_sdk_path") + "\n",
            SHUTDOWN_MESSAGE + " Additional failure.\n",
        ]
        for stage in (0, 1):
            for error in errors:
                with self.subTest(stage=stage, error=error):
                    outputs = [SHUTDOWN_MESSAGE + "\n", SHUTDOWN_MESSAGE + "\n"]
                    outputs[stage] += error
                    outcome = self.exercise_export(outputs)
                    self.assert_previous_release_preserved(outcome, stage + 1)

    def test_known_shutdown_diagnostic_cannot_override_nonzero_exit(self):
        for stage in (0, 1):
            with self.subTest(stage=stage):
                codes = [0, 0]
                codes[stage] = 1
                outcome = self.exercise_export((SHUTDOWN_MESSAGE, SHUTDOWN_MESSAGE), codes)
                self.assert_previous_release_preserved(outcome, stage + 1)

    def test_success_logs_cannot_publish_missing_or_damaged_apk(self):
        for apk_kind in ("missing", "empty", "corrupt", "source_zip", "bad_crc"):
            with self.subTest(apk_kind=apk_kind):
                outcome = self.exercise_export((SHUTDOWN_MESSAGE, SHUTDOWN_MESSAGE), apk_kind=apk_kind)
                self.assert_previous_release_preserved(outcome, 2)


if __name__ == "__main__":
    unittest.main()
