"""Address selection and failed-export recovery without Android SDK dependencies."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.server_endpoint import baked_server_config, check_temporary_endpoint, choose_endpoint, validate_server_url


class ServerEndpointTests(unittest.TestCase):
    def test_address_precedence_and_temporary_tunnel_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "client").mkdir()
            with self.assertRaises(ValueError):
                choose_endpoint(root)
            (root / "data/server_endpoint.json").write_text(json.dumps({"server_url": "https://new.trycloudflare.com", "temporary": False}))
            self.assertEqual(choose_endpoint(root), {"server_url": "https://new.trycloudflare.com", "temporary": True})
            (root / "client/server_config.json").write_text(json.dumps({"server_url": "https://fixed.example"}))
            self.assertEqual(choose_endpoint(root)["server_url"], "https://fixed.example")
            self.assertEqual(choose_endpoint(root, "https://explicit.example/")["server_url"], "https://explicit.example")

    def test_local_only_run_cannot_be_sent_as_phone_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data/server_endpoint.json").write_text(json.dumps({"server_url": "http://127.0.0.1:8765", "local_only": True}))
            with self.assertRaises(ValueError):
                choose_endpoint(root, allow_local=True)

    def test_public_https_and_explicit_lan_rules(self):
        self.assertEqual(validate_server_url("https://GAME.example:443/"), "https://game.example")
        self.assertEqual(validate_server_url("http://192.168.1.8:8765", True), "http://192.168.1.8:8765")
        for value in ("http://game.example", "https://user:pass@game.example", "https://game.example/api", "https://game.example?x=1", "https://game.example/#token", "https://game.example:99999", "https://game.example:0", "https://game.example:", "https://game.example\n", "http://192.168.1.8:8765", "https://bad..example"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_server_url(value)
        for value in ("http://127.0.0.1:8765", "http://localhost:8765", "http://[::1]:8765", "http://0.0.0.0:8765"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_server_url(value, True)
        for value in ("http://desktop:8765", "http://100.64.0.1:8765", "https://999.999.999.999", "https://[fe80::1%eth0]", "https://" + ".".join(["a" * 63] * 5)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_server_url(value, True)

    def test_baked_configuration_present_during_export_and_restored_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "client").mkdir()
            path = root / "client/server_config.json"
            original = b'{"server_url":"", "editor_note":"keep me"}\n'
            path.write_bytes(original)
            with self.assertRaisesRegex(RuntimeError, "Godot failed"):
                with baked_server_config(root, {"server_url": "https://game.example"}):
                    self.assertEqual(json.loads(path.read_text()), {"server_url": "https://game.example"})
                    raise RuntimeError("Godot failed")
            self.assertEqual(path.read_bytes(), original)

    def test_expired_tunnel_is_rejected_before_export(self):
        with patch("tools.server_endpoint.urllib.request.build_opener") as build:
            build.return_value.open.side_effect = OSError("offline")
            with self.assertRaisesRegex(ValueError, "Tymczasowy serwer nie odpowiada"):
                check_temporary_endpoint({"server_url": "https://old.trycloudflare.com", "temporary": True})
            build.reset_mock()
            check_temporary_endpoint({"server_url": "https://game.example", "temporary": False})
            build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
