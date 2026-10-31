"""Check the addresses shipped to phones and exclusive ownership of a hosted world."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.host_server import HostLock, open_server_environment, public_origin, write_endpoint


class HostLauncherTests(unittest.TestCase):
    def test_public_origin_accepts_only_https_origin_without_credentials_or_extras(self):
        for address in ("https://game.example.com", "https://game.example.com:8443", "https://[2001:db8::1]:8443"):
            with self.subTest(address=address):
                self.assertEqual(public_origin(address + "/"), address)
        for address in ("http://game.example.com", "https://name:password@game.example.com",
                        "https://game.example.com/game", "https://game.example.com?x=1",
                        "https://game.example.com#", "https://game.example.com?",
                        "https://game.example.com:", "https://game.example.com:70000",
                        "https://game.example.com:0", " https://game.example.com",
                        "https://game.example.com\n", "https://bad_host", "https://game.example.com\\evil",
                        "https:///", "https://-bad.example", "https://game..example.com"):
            with self.subTest(address=address), self.assertRaises(argparse.ArgumentTypeError):
                public_origin(address)

    def test_endpoint_replaces_old_address_and_marks_local_only_for_exporter(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            write_endpoint(directory, "https://game.example.com", temporary=False, local_only=False)
            self.assertEqual(json.loads((directory / "server_endpoint.json").read_text()), {
                "server_url": "https://game.example.com", "temporary": False, "local_only": False,
            })
            write_endpoint(directory, "http://127.0.0.1:8765", temporary=False, local_only=True)
            self.assertEqual(json.loads((directory / "server_endpoint.json").read_text()), {
                "server_url": "http://127.0.0.1:8765", "temporary": False, "local_only": True,
            })
            self.assertEqual((directory / "ADRES_SERWERA.txt").read_text(), "http://127.0.0.1:8765\n")
            self.assertFalse((directory / "server_endpoint.json.tmp").exists())

    def test_explicit_quick_tunnel_address_still_marked_temporary(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            write_endpoint(directory, "https://new-name.trycloudflare.com", temporary=False, local_only=False)
            self.assertTrue(json.loads((directory / "server_endpoint.json").read_text())["temporary"])

    def test_inherited_invitation_cannot_close_registration(self):
        with patch.dict(os.environ, {"PGR_INVITE_CODE": "previous-secret", "PGR_TEST_UNRELATED": "preserve"}):
            environment = open_server_environment()
            self.assertNotIn("PGR_INVITE_CODE", environment)
            self.assertEqual(environment["PGR_TEST_UNRELATED"], "preserve")
            self.assertEqual(os.environ["PGR_INVITE_CODE"], "previous-secret")

    def test_only_one_launcher_can_own_a_world_at_a_time(self):
        with tempfile.TemporaryDirectory() as folder:
            first = HostLock(Path(folder))
            try:
                with self.assertRaises(RuntimeError):
                    HostLock(Path(folder))
            finally:
                first.close()
            second = HostLock(Path(folder))
            second.close()


if __name__ == "__main__":
    unittest.main()
