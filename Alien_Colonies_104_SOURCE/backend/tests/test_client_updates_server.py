"""Update compatibility regressions; local HTTP only, no download or external account."""
from contextlib import contextmanager
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from server import main as app


DOWNLOAD = "https://example.org/pogranicze/latest.apk?source=game"
PASSWORD = "update-test-password"
APK_SHA256 = "abcdef0123456789" * 4
APK_SIZE_BYTES = 10_485_760


class UpdateConfigurationScenarios(unittest.TestCase):
    def test_shared_client_download_url_cases(self):
        cases = json.loads((Path(__file__).with_name("update_url_cases.json")).read_text(encoding="utf-8"))
        for url in cases["valid"]:
            with self.subTest(url=url):
                self.assertEqual(app.validate_download_url(url), url)
        for url in cases["invalid"]:
            with self.subTest(url=url):
                try:
                    accepted = bool(app.validate_download_url(url))
                except ValueError:
                    accepted = False
                self.assertFalse(accepted)

    def test_default_accepts_old_clients_and_uses_only_google_play(self):
        m = app.load_update_policy({}).manifest()
        self.assertEqual(m["min_version_code"], 0)
        self.assertEqual(m["latest_version_code"], app.CLIENT_VERSION_CODE)
        self.assertEqual(m["latest_version"], app.VERSION)
        self.assertEqual(m["distribution"], "google_play")
        self.assertEqual(m["package_id"], "com.conradmafer.aliencolonies")
        self.assertEqual(m["play_store_url"], "https://play.google.com/store/apps/details?id=com.conradmafer.aliencolonies")
        self.assertEqual((m["download_url"], m["apk_sha256"], m["apk_size_bytes"]), ("", "", 0))

    def test_required_update_without_external_apk_metadata(self):
        m = app.load_update_policy({"PGR_MIN_VERSION_CODE":"33", "PGR_LATEST_VERSION_CODE":"33", "PGR_LATEST_VERSION":"0.7.4"}).manifest()
        self.assertEqual(m["min_version_code"], 33)
        self.assertEqual(m["download_url"], "")
        self.assertTrue(m["play_store_url"].startswith("https://play.google.com/"))

    def test_obsolete_apk_environment_cannot_redirect_or_break_startup(self):
        for legacy in ("", "javascript:alert(1)", "http://localhost/file.apk", DOWNLOAD, "\n", None, 123):
            with self.subTest(legacy=legacy):
                m = app.load_update_policy({"PGR_MIN_VERSION_CODE":"33", "PGR_DOWNLOAD_URL":legacy,
                    "PGR_APK_SHA256":legacy, "PGR_APK_SIZE_BYTES":legacy}).manifest()
                self.assertEqual((m["download_url"], m["apk_sha256"], m["apk_size_bytes"]), ("", "", 0))
                self.assertEqual(m["play_store_url"], app.PLAY_STORE_URL)

    def test_environment_policy_is_parsed_once_and_manifest_is_copy(self):
        env = {"PGR_LATEST_VERSION_CODE":"33", "PGR_MIN_VERSION_CODE":"31", "PGR_UPDATE_MESSAGE":"Nowa wersja."}
        policy=app.load_update_policy(env)
        env["PGR_MIN_VERSION_CODE"]="99"
        m=policy.manifest();m["min_version_code"]=99
        self.assertEqual(policy.min_version_code,31)
        self.assertEqual(policy.manifest()["min_version_code"],31)
        self.assertEqual(policy.manifest()["message"],"Nowa wersja.")

    def test_invalid_version_numbers_or_metadata_are_rejected(self):
        for key in ("PGR_LATEST_VERSION_CODE", "PGR_MIN_VERSION_CODE"):
            for value in ("", "-1", "+5", "5.0", " 5", "5 ", "٥", "2100000001", "9" * 100, True, 33, None):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    app.load_update_policy({key:value})
        for kwargs in ({"latest_version_code":True}, {"min_version_code":1.0},
                       {"min_version_code":app.CLIENT_VERSION_CODE+1},
                       {"latest_version":""}, {"latest_version":" "}, {"latest_version":"x"*41},
                       {"latest_version":"x\ny"}, {"message":"x"*301}, {"message":"x\ry"}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):app.UpdatePolicy(**kwargs)

    def test_legacy_constructor_arguments_are_ignored(self):
        for value in (None, True, 1.1, DOWNLOAD, "not-a-hash", -99):
            m=app.UpdatePolicy(min_version_code=33, download_url=value, apk_sha256=value, apk_size_bytes=value).manifest()
            self.assertEqual((m["download_url"],m["apk_sha256"],m["apk_size_bytes"]),("","",0))

    def test_download_url_accepts_https_paths_and_queries(self):
        for url in (DOWNLOAD, "https://github.com/example/game/releases/latest",
                    "https://play.google.com/store/apps/details?id=com.example.game",
                    "https://downloads.example.org:443/game.apk", "https://example.org/gra-%C5%BC.apk"):
            with self.subTest(url=url):
                self.assertEqual(app.validate_download_url(url), url)

    def test_download_url_rejects_local_unsafe_and_malformed_destinations(self):
        for url in ("http://example.org/game.apk", "javascript:alert(1)", "file:///tmp/game.apk",
                    "https://name:password@example.org/file", "https://example.org/#part", "https://example.org/#",
                    "https://example.org:0/file", "https://example.org:65536/file", "https://example.org:/file",
                    "https://example.org\\@127.0.0.1/file", "https://example.org/with space", " https://example.org",
                    "https://example.org/line\nbreak", "https://localhost/file", "https://myhost.local/file",
                    "https://host.internal/file", "https://host.home.arpa/file", "https://127.0.0.1/file",
                    "HTTPS://example.org/file", "https://example.org:000443/file", "https://example.org/gra-ż.apk",
                    "https://example.org/%00file", "https://example.org/%1ffile",
                    "https://example.org/%7Ffile", "https://example.org/%5cfile", "https://host.example/file",
                    "https://host.onion/file", "https://8.8.8.8:443/game.apk", "https://[2001:4860:4860::8888]/game.apk",
                    "https://10.0.0.1/file", "https://192.168.1.1/file", "https://169.254.169.254/file",
                    "https://[::1]/file", "https://[fc00::1]/file", "https://[::ffff:127.0.0.1]/file",
                    "https://[fe80::1%eth0]/file", "https://999.1.1.1/file", "https://127.1/file",
                    "https://2130706433/file", "https://0x7f000001/file", "https://bad_name.org/file",
                    "https://example.org../file", "https://" + "a" * 64 + ".org/file"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                app.validate_download_url(url)

    def test_invalid_policy_is_rejected_before_opening_world(self):
        for env in ({"PGR_MIN_VERSION_CODE":"bad"}, {"PGR_LATEST_VERSION_CODE":"31","PGR_MIN_VERSION_CODE":"33"}):
            with patch.dict(app.os.environ,env,clear=True),patch.object(app,"World") as world:
                with self.assertRaises(ValueError): app.main(["--port","0"])
                world.assert_not_called()


class UpdateHTTPScenarios(unittest.TestCase):
    @contextmanager
    def api(self, policy=None):
        world = app.World(":memory:")
        server = app.build_server(world, port=0, update_policy=policy)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()

        def request(method="GET", path="/api/state", payload=None, token=None, versions=()):
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode() if payload is not None else b""
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            try:
                connection.putrequest(method, path)
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Content-Length", str(len(body)))
                if token:
                    connection.putheader("Authorization", "Bearer " + token)
                for version in versions:
                    connection.putheader("X-PGR-Client-Version", version)
                connection.endheaders(body)
                response = connection.getresponse()
                return response.status, json.loads(response.read()), dict(response.getheaders())
            finally:
                connection.close()

        try:
            yield world, request
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            world.close()

    def test_public_manifest_and_health_work_during_mandatory_update(self):
        policy = app.UpdatePolicy(latest_version_code=6, latest_version="0.1.5", min_version_code=6,
                                  download_url=DOWNLOAD, apk_sha256=APK_SHA256, apk_size_bytes=APK_SIZE_BYTES)
        with self.api(policy) as (_, request):
            status, manifest, headers = request(path="/api/client-version")
            self.assertEqual(status, 200)
            self.assertEqual(manifest, policy.manifest())
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(request(path="/health")[:2], (200, {"ok": True, "version": app.VERSION}))
            status, error, _ = request(versions=("5",))
            self.assertEqual(status, 426)
            self.assertEqual(error["update"]["apk_sha256"], "")
            self.assertEqual(error["update"]["apk_size_bytes"], 0)

    def test_optional_update_keeps_old_apk_registration_and_gameplay_working(self):
        policy = app.UpdatePolicy(latest_version_code=6, latest_version="0.1.5", download_url=DOWNLOAD,
                                  apk_sha256=APK_SHA256, apk_size_bytes=APK_SIZE_BYTES)
        with self.api(policy) as (_, request):
            status, manifest, _ = request(path="/api/client-version")
            self.assertEqual(status, 200)
            self.assertEqual(manifest["apk_sha256"], "")
            self.assertEqual(manifest["apk_size_bytes"], 0)
            status, account, _ = request("POST", "/api/register", {"name": "OldPilot", "password": PASSWORD})
            self.assertEqual(status, 200)
            self.assertEqual(request(token=account["token"])[0], 200)
            self.assertEqual(request(token=account["token"], versions=("bad-header",))[0], 200)

    def test_blocked_requests_never_read_body_or_advance_mutate_world_or_sessions(self):
        policy = app.UpdatePolicy(min_version_code=5, download_url=DOWNLOAD)
        with self.api(policy) as (world, request):
            account = world.register("ExistingPilot", PASSWORD)
            data_before = copy.deepcopy(world.data)
            accounts_before = world.db.execute("SELECT * FROM accounts").fetchall()
            sessions_before = world.db.execute("SELECT * FROM sessions").fetchall()
            with patch.object(world, "advance", side_effect=AssertionError("Version gate must run before world.advance")):
                for method, path in (("GET", "/api/state"), ("POST", "/api/login"), ("POST", "/api/register"),
                                     ("POST", "/api/action"), ("POST", "/api/preview"), ("POST", "/api/logout")):
                    with self.subTest(path=path):
                        status, error, headers = request(method, path, b"this is not JSON", token=account["token"])
                        self.assertEqual(status, 426)
                        self.assertEqual(error["code"], "update_required")
                        self.assertFalse(error["ok"])
                        self.assertEqual(error["update"], policy.manifest())
                        self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(world.data, data_before)
            self.assertEqual(world.db.execute("SELECT * FROM accounts").fetchall(), accounts_before)
            self.assertEqual(world.db.execute("SELECT * FROM sessions").fetchall(), sessions_before)

    def test_missing_malformed_duplicate_and_older_versions_are_blocked(self):
        with self.api(app.UpdatePolicy(min_version_code=5, download_url=DOWNLOAD)) as (_, request):
            for versions in ((), ("",), ("4",), ("-1",), ("5.0",), ("5 ",), ("1,5",), ("5", "5"),
                             ("2100000001",), ("9" * 100,), ("version5",)):
                with self.subTest(versions=versions):
                    self.assertEqual(request(versions=versions)[0], 426)

    def test_compatible_version_still_requires_authentication_and_can_play(self):
        with self.api(app.UpdatePolicy(min_version_code=5, download_url=DOWNLOAD)) as (_, request):
            self.assertEqual(request(versions=("5",))[0], 401)
            status, account, _ = request("POST", "/api/register", {"name": "NewPilot", "password": PASSWORD}, versions=("5",))
            self.assertEqual(status, 200)
            self.assertEqual(request(token=account["token"], versions=("5",))[0], 200)
            status, action, _ = request("POST", "/api/action", {
                "type": "build", "key": "metal_mine", "planet_id": account["state"]["home_id"],
                "request_id": "update-test-build",
            }, token=account["token"], versions=("5",))
            self.assertEqual(status, 200, action)
            self.assertEqual(len(action["state"]["queue"]), 1)
            self.assertEqual(request(token=account["token"], versions=("6",))[0], 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
