"""Metadata describes exact file bytes; synthetic APK-shaped ZIPs are not installed."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.prepare_update import apk_metadata, write_update_details


class ReleaseMetadataScenarios(unittest.TestCase):
    def make_fixture(self, path, contents=b"test fixture, not an Android APK"):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("AndroidManifest.xml", contents)

    def test_digest_size_and_version_describe_exact_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            apk = Path(folder) / "synthetic.apk"
            self.make_fixture(apk)
            info = apk_metadata(apk, 6, "0.1.5")
            self.assertEqual(info["apk_sha256"], hashlib.sha256(apk.read_bytes()).hexdigest())
            self.assertEqual(info["apk_size_bytes"], apk.stat().st_size)
            self.assertEqual(info["latest_version_code"], 6)
            output = Path(folder) / "details.txt"
            write_update_details(apk, output, 6, "0.1.5")
            self.assertIn("PGR_APK_SHA256=" + info["apk_sha256"], output.read_text())
            self.make_fixture(apk, b"changed bytes")
            self.assertNotEqual(apk_metadata(apk, 6, "0.1.5")["apk_sha256"], info["apk_sha256"])

    def test_source_zip_html_and_oversized_apk_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            apk = Path(folder) / "wrong.apk"
            apk.write_text("<html>download page</html>")
            with self.assertRaises(ValueError):
                apk_metadata(apk, 6, "0.1.5")
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("project.godot", "source")
            with self.assertRaises(ValueError):
                apk_metadata(apk, 6, "0.1.5")
            self.make_fixture(apk)
            with patch("tools.prepare_update.MAX_APK_SIZE_BYTES", 10), self.assertRaises(ValueError):
                apk_metadata(apk, 6, "0.1.5")

    def test_invalid_input_never_overwrites_previous_details(self):
        with tempfile.TemporaryDirectory() as folder:
            apk, output = Path(folder) / "wrong.apk", Path(folder) / "details.txt"
            apk.write_text("broken")
            output.write_text("previous valid metadata")
            with self.assertRaises(ValueError):
                write_update_details(apk, output, 6, "0.1.5")
            self.assertEqual(output.read_text(), "previous valid metadata")


if __name__ == "__main__":
    unittest.main()
