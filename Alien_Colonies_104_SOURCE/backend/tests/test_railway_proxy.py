"""HTTP regressions for the Railway proxy adapter; no external services needed."""
from contextlib import contextmanager
import http.client
import importlib.util
import json
from pathlib import Path
import threading
import unittest


from server import main as app


class RailwayProxyScenarios(unittest.TestCase):
    @contextmanager
    def api(self, trusted=None):
        world = app.World(":memory:")
        server = app.build_server(world, "127.0.0.1", 0, trust_proxy_header=trusted)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()

        def request(method="GET", path="/api/state", payload=None, token=None, headers=()):
            body = json.dumps(payload).encode() if payload is not None else b""
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            try:
                connection.putrequest(method, path)
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Content-Length", str(len(body)))
                if token:
                    connection.putheader("Authorization", "Bearer " + token)
                for key, value in headers:
                    connection.putheader(key, value)
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

    def test_verified_players_share_proxy_but_not_quota(self):
        with self.api("X-Real-IP") as (world, request):
            first = world.register("FirstPilot", "test-password")
            second = world.register("SecondPilot", "test-password")
            same_address = [("X-Real-IP", "198.51.100.4")]
            for _ in range(180):
                self.assertEqual(request(token=first["token"], headers=same_address)[0], 200)
            self.assertEqual(request(token=first["token"], headers=same_address)[0], 429)
            status, response = request(token=second["token"], headers=same_address)
            self.assertEqual(status, 200)
            self.assertEqual(response["state"]["player"]["id"], second["state"]["player"]["id"])
            another_session = world.login("FirstPilot", "test-password")
            self.assertEqual(request(token=another_session["token"], headers=same_address)[0], 429)

    def test_standalone_ignores_forged_proxy_headers(self):
        with self.api() as (_, request):
            for index in range(13):
                status, _ = request("POST", "/api/login", {}, headers=[
                    ("X-Real-IP", f"198.51.100.{index + 1}"),
                    ("X-Forwarded-For", f"203.0.113.{index + 1}"),
                ])
                self.assertEqual(status, 400 if index < 12 else 429)

    def test_trusted_real_ips_have_distinct_login_registration_buckets(self):
        with self.api("X-Real-IP") as (_, request):
            first = [("X-Real-IP", "198.51.100.7")]
            second = [("X-Real-IP", "198.51.100.8")]
            for _ in range(12):
                self.assertEqual(request("POST", "/api/login", {}, headers=first)[0], 400)
            self.assertEqual(request("POST", "/api/register", {}, headers=first)[0], 429)
            self.assertEqual(request("POST", "/api/register", {}, headers=second)[0], 400)

    def test_missing_malformed_duplicate_and_forwarded_for_fall_back_to_socket(self):
        invalid_headers = [
            [],
            [("X-Forwarded-For", "198.51.100.1")],
            [("X-Real-IP", "")],
            [("X-Real-IP", "not-an-ip")],
            [("X-Real-IP", "198.51.100.1, 198.51.100.2")],
            [("X-Real-IP", "198.51.100.1"), ("X-Real-IP", "198.51.100.2")],
            [("X-Real-IP", "198.51.100.1:443")],
            [("X-Real-IP", "[2001:db8::1]")],
            [("X-Real-IP", "fe80::1%eth0")],
            [("X-Real-IP", "999.1.1.1")],
            [("X-Real-IP", "001.002.003.004")],
            [("X-Real-IP", "a" * 46)],
        ]
        with self.api("X-Real-IP") as (_, request):
            for headers in invalid_headers:
                with self.subTest(headers=headers):
                    self.assertEqual(request("POST", "/api/login", {}, headers=headers)[0], 400)
            self.assertEqual(request("POST", "/api/login", {})[0], 429)

    def test_equivalent_ipv6_representations_share_authentication_bucket(self):
        with self.api("X-Real-IP") as (_, request):
            for _ in range(12):
                self.assertEqual(request("POST", "/api/login", {}, headers=[
                    ("X-Real-IP", "2001:db8::1")
                ])[0], 400)
            self.assertEqual(request("POST", "/api/login", {}, headers=[
                ("X-Real-IP", "2001:0DB8:0000:0000:0000:0000:0000:0001")
            ])[0], 429)

    def test_health_is_independent_and_invalid_tokens_are_limited_by_real_ip(self):
        with self.api("X-Real-IP") as (world, request):
            player = world.register("LivePilot", "test-password")
            first = [("X-Real-IP", "203.0.113.4")]
            second = [("X-Real-IP", "203.0.113.5")]
            for _ in range(180):
                self.assertEqual(request(path="/health", headers=first)[0], 200)
            for _ in range(180):
                self.assertEqual(request(token="invalid-session-token-012345", headers=first)[0], 401)
            self.assertEqual(request(headers=first)[0], 429)
            self.assertEqual(request(headers=second)[0], 401)
            self.assertEqual(request(path="/health", headers=first),
                             (200, {"ok": True, "version": app.VERSION}))
            self.assertEqual(request(token=player["token"], headers=first)[0], 200)

    def test_proxy_header_configuration_is_explicit(self):
        world = app.World(":memory:")
        try:
            for header in (True, "X-Forwarded-For", "Forwarded", ""):
                with self.subTest(header=header), self.assertRaises(ValueError):
                    app.build_server(world, port=0, trust_proxy_header=header)
        finally:
            world.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
