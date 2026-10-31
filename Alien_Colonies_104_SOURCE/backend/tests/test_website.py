"""Tests of the existing game API and additive website on one local world."""
import http.client
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, os.environ.get("ALIEN_SERVER_DIR", str(ROOT.parent / "pogranicze-serwer")))
import app
import run
import website

website.install_website(hosted=False, origin="")


class IntegratedWebsiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "private_test.sqlite3"
        self.start()

    def start(self):
        self.world = app.World(str(self.db), 1)
        self.server = app.build_server(self.world, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.thread.join(3)
        self.server.server_close()
        self.world.close()

    def tearDown(self):
        self.stop()
        self.temp.cleanup()

    def request(self, path, *, method="GET", body=None, token=None, version="46", host=None, extra_headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        headers = {"Accept-Language": "pl"}
        if version is not None:
            headers["X-PGR-Client-Version"] = version
        if token:
            headers["Authorization"] = "Bearer " + token
        if body is not None:
            headers["Content-Type"] = "application/json"
        if host is not None:
            headers["Host"] = host
        if extra_headers:
            headers.update(extra_headers)
        conn.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def register(self):
        name = "test_" + secrets.token_hex(3)
        password = secrets.token_urlsafe(15)
        status, headers, raw = self.request("/api/register", method="POST", body={"name": name, "password": password})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        return name, password, json.loads(raw)

    def test_site_and_api_share_one_world_and_restart_preserves_account(self):
        name, password, account = self.register()
        player_id = account["state"]["player"]["id"]
        world_id = id(self.server.world)
        self.assertIn(b"Alien Colonies", self.request("/")[2])
        self.assertEqual(id(self.server.world), world_id)
        self.stop()
        self.start()
        status, headers, body = self.request("/api/state", token=account["token"])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["state"]["player"]["id"], player_id)
        status, _, raw = self.request("/api/login", method="POST", body={"name": name, "password": password})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["state"]["player"]["id"], player_id)
        self.assertTrue(self.db.is_file())

    def test_ui_entrypoints_are_not_cached_across_releases(self):
        for path in ('/play/game.js','/play/game.js?v=old','/play/galaxy-map.js','/play/locales/en.json','/play/release.json'):
            status,headers,body=self.request(path)
            self.assertEqual(status,200,path)
            self.assertEqual(headers['Cache-Control'],'no-store',path)
        self.assertEqual(json.loads(self.request('/play/release.json')[2])['version'], app.VERSION)

    def test_android_version_gate_is_not_bypassed(self):
        self.server.update_policy = app.UpdatePolicy(latest_version_code=47, min_version_code=47)
        for version in (None, "46", "broken"):
            with self.subTest(version=version):
                status, _, raw = self.request("/api/register", method="POST", body={"name": "blocked", "password": "not-a-real-password"}, version=version)
                self.assertEqual(status, 426)
                self.assertEqual(json.loads(raw)["code"], "update_required")
        self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 0)
        status, _, body = self.request("/api/client-version", version=None)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["min_version_code"], 47)

    def test_authentication_and_private_cache_policy_preserved(self):
        status, headers, body = self.request("/api/state")
        self.assertEqual(status, 401)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertFalse(json.loads(body)["ok"])

    def test_seo_pages_and_metadata_use_actual_domain(self):
        self.server.website_origin = "https://aliencolonies.com"
        titles = set()
        for path in website.PAGES:
            status, headers, raw = self.request(path)
            self.assertEqual(status, 200)
            self.assertNotIn("X-Robots-Tag", headers)
            text = raw.decode()
            self.assertNotIn("__SITE_ORIGIN__", text)
            self.assertIn('href="https://aliencolonies.com' + path + '"', text)
            titles.add(text.split("<title>")[1].split("</title>")[0])
        self.assertEqual(len(titles), len(website.PAGES))
        status, _, body = self.request("/sitemap.xml")
        document = ET.fromstring(body)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = [element.text for element in document.findall("sm:url/sm:loc", namespace)]
        self.assertEqual(locations, ["https://aliencolonies.com" + page for page in website.PAGES])
        self.assertIn(b"Sitemap: https://aliencolonies.com/sitemap.xml", self.request("/robots.txt")[2])
        self.assertEqual(self.request("/play/")[1]["X-Robots-Tag"], "noindex, nofollow")

    def test_robots_allows_reading_game_noindex_and_preserves_private_blocks(self):
        self.server.website_hosted = True
        self.server.website_origin = "https://aliencolonies.com"
        status, headers, raw = self.request("/robots.txt", version=None)
        self.assertEqual(status, 200)
        rules = raw.decode().splitlines()
        self.assertIn("Allow: /", rules)
        self.assertNotIn("Disallow: /play/", rules)
        self.assertNotIn("Disallow: /play", rules)
        for path in ("/api/", "/delete-account", "/health", "/site-config"):
            self.assertIn("Disallow: " + path, rules)
        for path in ("/play/", "/play/index.html"):
            status, headers, body = self.request(path, version=None)
            self.assertEqual(status, 200)
            self.assertEqual(headers["X-Robots-Tag"], "noindex, nofollow")
            self.assertIn(b'name="robots" content="noindex', body)
        status, headers, body = self.request("/sitemap.xml", version=None)
        self.assertEqual(status, 200)
        self.assertNotIn("X-Robots-Tag", headers)
        self.assertNotIn(b"/play/", body)

    def test_index_and_missing_slash_aliases_preserve_queries(self):
        self.server.website_origin = "https://aliencolonies.com"
        for page in website.PAGES:
            aliases = [page + "index.html"]
            if page != "/":
                aliases.append(page.rstrip("/"))
            for alias in aliases:
                for method in ("GET", "HEAD"):
                    with self.subTest(alias=alias, method=method):
                        status, headers, body = self.request(alias + "?source=guide&term=a%20b", method=method)
                        self.assertEqual(status, 308)
                        self.assertEqual(headers["Location"], page + "?source=guide&term=a%20b")
                        self.assertEqual(body, b"")

    def test_legacy_host_redirects_only_public_documents_in_hosted_mode(self):
        self.server.website_hosted = True
        self.server.website_origin = "https://colonies.example"
        for page in website.PAGES:
            with self.subTest(page=page):
                status, headers, body = self.request(page + "index.html?from=old", host=website.LEGACY_HOST, version=None)
                self.assertEqual(status, 308)
                self.assertEqual(headers["Location"], "https://colonies.example" + page + "?from=old")
                self.assertEqual(body, b"")
        status, headers, body = self.request("/?from=old", method="HEAD", host=website.LEGACY_HOST)
        self.assertEqual(status, 308)
        self.assertEqual(headers["Location"], "https://colonies.example/?from=old")
        self.assertEqual(body, b"")
        for host in ("colonies.example", "127.0.0.1", "localhost", "unrecognized.example"):
            with self.subTest(host=host):
                status, headers, _ = self.request("/", host=host, extra_headers={
                    "X-Forwarded-Host": website.LEGACY_HOST,
                    "Forwarded": "host=" + website.LEGACY_HOST,
                })
                self.assertEqual(status, 200)
                self.assertNotIn("Location", headers)
        # Neither a local development server nor a same-host origin loops.
        self.server.website_hosted = False
        self.assertEqual(self.request("/", host=website.LEGACY_HOST)[0], 200)
        self.server.website_hosted = True
        self.server.website_origin = "https://" + website.LEGACY_HOST
        self.assertEqual(self.request("/", host=website.LEGACY_HOST)[0], 200)

    def test_legacy_host_keeps_android_api_game_assets_and_account_pages(self):
        self.server.website_hosted = True
        self.server.website_origin = "https://aliencolonies.com"
        for path in ("/health", "/privacy", "/delete-account", "/play/", "/assets/site.css", "/robots.txt", "/sitemap.xml", "/site-config"):
            with self.subTest(path=path):
                status, headers, _ = self.request(path, host=website.LEGACY_HOST, version=None)
                self.assertEqual(status, 200)
                self.assertNotIn("Location", headers)
        status, headers, _ = self.request("/play?register=1", host=website.LEGACY_HOST)
        self.assertEqual(status, 308)
        self.assertEqual(headers["Location"], "/play/?register=1")
        name, password, account = self.register()
        status, headers, raw = self.request("/api/login", method="POST", host=website.LEGACY_HOST,
                                          body={"name": name, "password": password})
        self.assertEqual(status, 200)
        self.assertNotIn("Location", headers)
        self.assertEqual(json.loads(raw)["state"]["player"]["id"], account["state"]["player"]["id"])
        status, headers, _ = self.request("/api/state", host=website.LEGACY_HOST, token=account["token"])
        self.assertEqual(status, 200)
        self.assertNotIn("Location", headers)
        self.server.update_policy = app.UpdatePolicy(latest_version_code=47, min_version_code=47)
        status, headers, _ = self.request("/api/state", host=website.LEGACY_HOST, token=account["token"], version="46")
        self.assertEqual(status, 426)
        self.assertNotIn("Location", headers)

    def test_local_development_is_not_indexable(self):
        for path in ("/", "/poradnik/", "/play/"):
            status, headers, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertEqual(headers["X-Robots-Tag"], "noindex, nofollow")
            self.assertNotIn(b"__SITE_ORIGIN__", body)
        self.assertTrue(json.loads(self.request("/site-config")[2])["development"])
        self.assertIn(b"Disallow: /", self.request("/robots.txt")[2])

    def test_static_head_redirects_and_path_confinement(self):
        status, headers, body = self.request("/assets/site.css", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 100)
        self.assertEqual(self.request("/play?register=1")[1]["Location"], "/play/?register=1")
        for path in ("/../run.py", "/%2e%2e/run.py", "/%00", "/.test-data/private_test.sqlite3", "/not-found"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)

    def test_original_health_and_account_pages_are_preserved(self):
        status, _, health = self.request("/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(health)["ok"])
        for path in ("/privacy", "/privacy/", "/delete-account", "/delete-account/"):
            status, headers, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertIn("Content-Security-Policy", headers)
            self.assertIn(b"Alien Colonies", body)

    def test_existing_railway_volume_path_and_world_lock(self):
        directory, argv, trusted = run.configuration(None, None, {"RAILWAY_SERVICE_ID": "test-service", "RAILWAY_VOLUME_MOUNT_PATH": self.temp.name, "PORT": "8080"})
        self.assertEqual(directory, Path(self.temp.name))
        self.assertIn(str(self.db), argv)
        self.assertEqual(trusted, "X-Real-IP")
        lock = run.WorldFileLock(directory)
        try:
            with self.assertRaises(RuntimeError):
                run.WorldFileLock(directory)
        finally:
            lock.close()

    def test_symlinked_index_cannot_read_outside_web(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            (temp / "web").mkdir()
            secret = temp / "outside.txt"
            secret.write_text("outside-secret-fixture")
            (temp / "web" / "index.html").symlink_to(secret)
            with patch.object(website, "WEB", temp / "web"):
                status, _, body = self.request("/")
                self.assertEqual(status, 404)
                self.assertNotIn(b"outside-secret-fixture", body)


if __name__ == "__main__":
    unittest.main()
