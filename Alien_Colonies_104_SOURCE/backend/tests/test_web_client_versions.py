"""HTTP regressions: Android minimum builds must not block the hosted browser."""
from contextlib import contextmanager
import http.client
import json
from pathlib import Path
import sys
import threading
import unittest

# Import the deployable root server, rather than a possibly stale package copy.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


PASSWORD = "web-version-regression-password"
BROWSER_METADATA = (
    ("Sec-Fetch-Site", "same-origin"),
    ("Sec-Fetch-Dest", "empty"),
    ("Sec-Fetch-Mode", "cors"),
)


class WebClientVersionHTTPTests(unittest.TestCase):
    @contextmanager
    def api(self):
        # In-memory worlds also disable filesystem backups.
        world = app.World(":memory:", speed=1, apply_balance_reset=False)
        policy = app.UpdatePolicy(latest_version_code=50, latest_version="0.11.5", min_version_code=50)
        server = app.build_server(world, port=0, update_policy=policy)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()

        def request(method="GET", path="/api/state", payload=None, token=None,
                    versions=(), platforms=(), headers=()):
            body = json.dumps(payload).encode() if payload is not None else b""
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            try:
                connection.putrequest(method, path)
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Content-Length", str(len(body)))
                if token is not None:
                    connection.putheader("Authorization", "Bearer " + token)
                for value in versions:
                    connection.putheader("X-PGR-Client-Version", value)
                for value in platforms:
                    connection.putheader("X-PGR-Client-Platform", value)
                for name, value in headers:
                    connection.putheader(name, value)
                connection.endheaders(body)
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally:
                connection.close()

        try:
            yield world, request
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            world.close()

    def assert_login_registration_and_state_work(self, request, name, **signals):
        credentials = {"name": name, "password": PASSWORD}
        status, registered = request("POST", "/api/register", credentials, **signals)
        self.assertEqual(status, 200, registered)
        self.assertTrue(registered["ok"])
        status, logged_in = request("POST", "/api/login", credentials, **signals)
        self.assertEqual(status, 200, logged_in)
        self.assertTrue(logged_in["ok"])
        status, state = request(token=logged_in["token"], **signals)
        self.assertEqual(status, 200, state)
        self.assertTrue(state["ok"])
        self.assertEqual(state["state"]["home_id"], registered["state"]["home_id"])

    def test_explicit_web_can_register_login_and_play_with_old_or_missing_version(self):
        with self.api() as (_, request):
            for index, versions in enumerate((("46",), ())):
                with self.subTest(versions=versions):
                    self.assert_login_registration_and_state_work(
                        request, "WebPilot" + str(index), platforms=("web",), versions=versions)

    def test_already_loaded_web_without_platform_header_can_register_login_and_play(self):
        with self.api() as (_, request):
            for index, versions in enumerate((("46",), ())):
                with self.subTest(versions=versions):
                    self.assert_login_registration_and_state_work(
                        request, "LegacyWeb" + str(index), headers=BROWSER_METADATA, versions=versions)

    def test_old_android_stays_blocked_and_current_android_can_play(self):
        with self.api() as (_, request):
            for platforms in (("android",), ()):
                with self.subTest(platforms=platforms):
                    status, error = request(versions=("49",), platforms=platforms)
                    self.assertEqual(status, 426, error)
                    self.assertEqual(error["code"], "update_required")
            self.assert_login_registration_and_state_work(
                request, "AndroidPilot", platforms=("android",), versions=("50",))

    def test_native_without_platform_header_can_still_use_current_version(self):
        with self.api() as (_, request):
            self.assert_login_registration_and_state_work(request, "NativePilot", versions=("50",))

    def test_missing_malformed_and_duplicate_android_versions_stay_blocked(self):
        with self.api() as (_, request):
            invalid_versions = (
                (), ("",), ("49",), ("-1",), ("50.0",), ("50 ",),
                ("49,50",), ("50", "50"), ("2100000001",), ("9" * 100,), ("version50",),
            )
            for versions in invalid_versions:
                with self.subTest(versions=versions):
                    status, error = request(versions=versions, platforms=("android",))
                    self.assertEqual(status, 426, error)
                    self.assertEqual(error["code"], "update_required")

    def test_unknown_or_duplicate_platform_cannot_use_browser_fallback(self):
        with self.api() as (_, request):
            invalid_platforms = (("",), ("desktop",), ("web,android",), ("web", "web"), ("web", "android"))
            for platforms in invalid_platforms:
                with self.subTest(platforms=platforms):
                    status, error = request(versions=("46",), platforms=platforms, headers=BROWSER_METADATA)
                    self.assertEqual(status, 426, error)
                    self.assertEqual(error["code"], "update_required")

    def test_cross_site_or_incomplete_browser_metadata_does_not_exempt_native(self):
        with self.api() as (_, request):
            invalid_metadata = (
                (("Sec-Fetch-Site", "cross-site"), ("Sec-Fetch-Dest", "empty"), ("Sec-Fetch-Mode", "cors")),
                (("Sec-Fetch-Site", "same-origin"),),
                (("Sec-Fetch-Site", "same-origin"), ("Sec-Fetch-Dest", "document"), ("Sec-Fetch-Mode", "navigate")),
                BROWSER_METADATA + (("Sec-Fetch-Site", "same-origin"),),
            )
            for headers in invalid_metadata:
                with self.subTest(headers=headers):
                    status, error = request(versions=("46",), headers=headers)
                    self.assertEqual(status, 426, error)

    def test_web_exemption_does_not_bypass_authentication(self):
        with self.api() as (_, request):
            for signals in (
                {"platforms": ("web",), "versions": ("46",)},
                {"headers": BROWSER_METADATA, "versions": ("46",)},
            ):
                for token in (None, "invalid-session-token"):
                    with self.subTest(signals=signals, token=token):
                        status, error = request(token=token, **signals)
                        self.assertEqual(status, 401, error)
                        self.assertFalse(error["ok"])

    def test_public_update_manifest_preserves_android_minimum_50(self):
        with self.api() as (_, request):
            for signals in ({}, {"platforms": ("web",), "versions": ("46",)},
                            {"platforms": ("android",), "versions": ("49",)}):
                with self.subTest(signals=signals):
                    status, manifest = request(path="/api/client-version", **signals)
                    self.assertEqual(status, 200, manifest)
                    self.assertEqual(manifest["min_version_code"], 50)
                    self.assertEqual(manifest["latest_version_code"], 50)
                    self.assertEqual(manifest["distribution"], "google_play")


if __name__ == "__main__":
    unittest.main()
