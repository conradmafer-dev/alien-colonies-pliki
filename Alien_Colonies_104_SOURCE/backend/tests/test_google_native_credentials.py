"""Native Credential Manager tokens reuse the established Google subject identity."""
import copy
import hashlib
import http.client
import json
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import app
import test_google_signin as fixtures
from google_signin import (FLOW_TTL, GoogleSignInError, GoogleSignInService,
                           NATIVE_VERIFY_WORKERS)


class NativeProvider(fixtures.FakeProvider):
    client_id = "123-web.apps.googleusercontent.com"
    def __init__(self):
        super().__init__()
        self.native_hook = None
    def verify_native(self, encoded, flow):
        if self.native_hook:
            self.native_hook(encoded, flow)
        if self.error:
            raise self.error
        return self.subject


class NativeCredentialScenarios(unittest.TestCase):
    def setUp(self):
        self.world = app.World(":memory:", now=fixtures.NOW)
        self.clock = 100.0
        self.provider = NativeProvider()
        self.service = GoogleSignInService(self.world, self.provider, clock=lambda: self.clock)
    def tearDown(self):
        self.world.close()
    def start(self, **kwargs):
        return self.service.start(client="android", native=True, **kwargs)
    def verify(self, flow):
        return self.service.native_verify(flow["flow_id"], flow["poll_secret"], "local-id-token")
    def complete(self, flow, name="Native Empire"):
        return self.service.complete(flow["flow_id"], flow["poll_secret"], name)

    def test_start_returns_challenge_without_browser_code_or_ticket(self):
        first, second = self.start(), self.start()
        self.assertEqual(set(first), {"ok", "flow_id", "poll_secret", "nonce", "server_client_id", "expires_in"})
        self.assertEqual(first["server_client_id"], self.provider.client_id)
        self.assertEqual(len(first["nonce"]), 43)
        self.assertNotEqual(first["nonce"], second["nonce"])
        self.assertNotIn(first["poll_secret"], json.dumps(self.service.flows))
        self.assertTrue(self.service.config()["native_configured"])
        self.assertEqual(len(self.world.data["players"]), 0)

    def test_name_required_then_one_empire_created_and_proof_consumed(self):
        flow = self.start()
        with self.assertRaises(GoogleSignInError):
            self.complete(flow)
        self.assertEqual(self.verify(flow), {"ok": True, "status": "needs_name"})
        with self.assertRaises(app.GameError):
            self.complete(flow, "x")
        result = self.complete(flow)
        self.assertEqual(self.world.authenticate(result["token"]), result["state"]["player"]["id"])
        self.assertTrue(result["state"]["account"]["google_linked"])
        for operation in (lambda: self.complete(flow), lambda: self.verify(flow)):
            with self.assertRaises(GoogleSignInError) as caught:
                operation()
            self.assertEqual(caught.exception.status, 410)
        self.assertEqual(len(self.world.data["players"]), 1)

    def test_existing_browser_google_identity_keeps_original_empire(self):
        prior = self.service.start(client="web", browser_cookie="C" * 43)
        query = parse_qs(urlsplit(prior["authorization_url"]).query)
        self.service.open(prior["flow_id"], query["open"][0], "C" * 43)
        state = self.service.flows[prior["flow_id"]]["state"]
        self.service.callback(state, "C" * 43, code="browser-google-code")
        original = self.complete(prior, "Browser Empire")
        player_id = original["state"]["player"]["id"]
        before = copy.deepcopy(self.world.data["players"][player_id])
        native = self.start()
        self.assertEqual(self.verify(native), {"ok": True, "status": "ready"})
        result = self.complete(native, "Should Not Rename")
        self.assertEqual(result["state"]["player"]["id"], player_id)
        self.assertEqual(self.world.data["players"][player_id], before)
        self.assertEqual(len(self.world.data["players"]), 1)
        self.assertNotIn(self.provider.subject, json.dumps(result["state"]))

    def test_wrong_poll_or_cross_flow_proof_cannot_consume_challenge(self):
        flow, other = self.start(), self.start()
        for proof in (None, "wrong", other["poll_secret"]):
            with self.subTest(proof=proof), self.assertRaises(GoogleSignInError):
                self.service.native_verify(flow["flow_id"], proof, "local-token")
        self.assertEqual(self.service.flows[flow["flow_id"]]["status"], "pending")
        self.assertEqual(self.verify(flow)["status"], "needs_name")

    def test_native_verify_cannot_accept_browser_flow_and_native_cannot_open_browser(self):
        browser = self.service.start(client="web", browser_cookie="C" * 43)
        with self.assertRaises(GoogleSignInError):
            self.verify(browser)
        native = self.start()
        with patch("google_signin.digest", return_value=self.service.flows[native["flow_id"]]["open_hash"]):
            with self.assertRaises(GoogleSignInError):
                self.service.open(native["flow_id"], "O" * 43)
        with self.assertRaises(GoogleSignInError):
            self.service.start(client="web", native=True, browser_cookie="C" * 43)

    def test_native_works_without_app_link_ticket(self):
        flow = self.start()
        self.verify(flow)
        self.assertEqual(self.service.status(flow["flow_id"], flow["poll_secret"])["status"], "needs_name")
        self.assertTrue(self.complete(flow)["ok"])

    def test_provider_error_is_terminal_and_secrets_are_not_exposed(self):
        flow = self.start()
        self.provider.error = RuntimeError("private-id-token and provider-secret")
        with self.assertRaises(GoogleSignInError) as caught:
            self.verify(flow)
        self.assertEqual(caught.exception.status, 401)
        self.assertNotIn("private-id-token", str(caught.exception))
        self.assertNotIn("provider-secret", json.dumps(self.service.flows))
        self.provider.error = None
        with self.assertRaises(GoogleSignInError) as caught:
            self.verify(flow)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(len(self.world.data["players"]), 0)

    def test_expired_flow_is_rejected_before_or_after_provider_io(self):
        flow = self.start()
        self.clock += FLOW_TTL
        with self.assertRaises(GoogleSignInError) as caught:
            self.verify(flow)
        self.assertEqual(caught.exception.status, 410)
        later = self.start()
        def expire(encoded, checked):
            self.clock += FLOW_TTL
        self.provider.native_hook = expire
        with self.assertRaises(GoogleSignInError) as caught:
            self.verify(later)
        self.assertEqual(caught.exception.status, 410)
        self.assertEqual(len(self.world.data["players"]), 0)

    def test_restart_loses_incomplete_challenge(self):
        flow = self.start()
        self.service = GoogleSignInService(self.world, self.provider)
        with self.assertRaises(GoogleSignInError):
            self.verify(flow)

    def test_provider_io_holds_neither_lock_and_duplicate_attempt_is_rejected(self):
        flow = self.start()
        entered, release = threading.Event(), threading.Event()
        results = []
        def block(encoded, checked):
            entered.set()
            self.assertTrue(release.wait(3))
        self.provider.native_hook = block
        worker = threading.Thread(target=lambda: results.append(self.verify(flow)))
        worker.start()
        self.assertTrue(entered.wait(3))
        try:
            for lock in (self.service.lock, self.world.lock):
                self.assertTrue(lock.acquire(timeout=.2))
                lock.release()
            with self.assertRaises(GoogleSignInError) as caught:
                self.verify(flow)
            self.assertEqual(caught.exception.status, 409)
        finally:
            release.set()
            worker.join(3)
        self.assertEqual(results, [{"ok": True, "status": "needs_name"}])

    def test_concurrency_is_bounded_without_consuming_overflow_challenge(self):
        for _ in range(NATIVE_VERIFY_WORKERS):
            self.assertTrue(self.service.native_verify_slots.acquire(blocking=False))
        flow = self.start()
        try:
            with self.assertRaises(GoogleSignInError) as caught:
                self.verify(flow)
            self.assertEqual(caught.exception.status, 429)
            self.assertEqual(self.service.flows[flow["flow_id"]]["status"], "pending")
        finally:
            for _ in range(NATIVE_VERIFY_WORKERS):
                self.service.native_verify_slots.release()
        self.assertEqual(self.verify(flow)["status"], "needs_name")

    def test_link_binding_rechecks_original_session_before_account_write(self):
        self.world.require_google_registration = False
        prior = self.world.register("Legacy Empire", fixtures.PASSWORD)
        self.world.require_google_registration = True
        player_id = prior["state"]["player"]["id"]
        flow = self.start(mode="link", player_id=player_id, session_hash=hashlib.sha256(prior["token"].encode()).hexdigest())
        self.verify(flow)
        self.world.logout(prior["token"])
        with self.assertRaises(app.GameError) as caught:
            self.complete(flow)
        self.assertEqual(caught.exception.status, 401)
        self.assertEqual(self.world.db.execute("SELECT count(*) FROM google_accounts").fetchone()[0], 0)


class NativeProviderCryptographicChecks(unittest.TestCase):
    """Real Google JWT verifier, locally generated RSA certificate and no egress."""
    def setUp(self):
        self.fixture = fixtures.ProviderCryptographicChecks()
        self.fixture.setUp()
        self.provider = self.fixture.provider
        self.fixture.request_patch.stop()
        self.cert_calls = []
        self.cache_control, self.age = "public, max-age=300", "0"
        owner = self
        class Certificates:
            status = 200
            data = json.dumps({"fixture-key": owner.fixture.certificate}).encode()
            @property
            def headers(self):
                return {"Cache-Control": owner.cache_control, "Age": owner.age}
        def request(*args, **kwargs):
            self.cert_calls.append((args, kwargs))
            return Certificates()
        self.patch = patch("google.auth.transport.requests.Request", return_value=request)
        self.patch.start()
        self.flow = {"nonce": "N" * 43, "issued_at": time.time() - 15}
    def tearDown(self):
        self.patch.stop()
    def encode(self, **changes):
        from google.auth import jwt
        from google.auth.crypt import RSASigner
        return jwt.encode(RSASigner.from_string(self.fixture.private_pem, key_id="fixture-key"),
                          {**self.fixture.claims, **changes}).decode()
    def test_signed_android_presenter_with_server_audience_and_exact_nonce_is_valid(self):
        encoded = self.encode(azp="456-android.apps.googleusercontent.com", email="ignored@example.com")
        self.assertEqual(self.provider.verify_native(encoded, self.flow), "rsa_subject")
        self.assertEqual(self.cert_calls[0][1]["timeout"], 8)
        self.assertEqual(self.fixture.closed, [True])
        with self.assertRaises(ValueError):
            self.provider.validate_claims({**self.fixture.claims, "azp": "456-android.apps.googleusercontent.com"}, "N" * 43)
    def test_invalid_signature_cannot_authenticate(self):
        head, payload, signature = self.encode().split(".")
        forged = head + "." + payload + "." + "A" * len(signature)
        with self.assertRaises(GoogleSignInError) as caught:
            self.provider.verify_native(forged, self.flow)
        self.assertEqual(caught.exception.status, 401)
        self.assertNotIn(forged, caught.exception.message)
    def test_signed_wrong_audience_nonce_issuer_time_or_malformed_presenter_are_rejected(self):
        cases = [{"aud": "other.apps.googleusercontent.com"}, {"nonce": "another_nonce"},
                 {"iss": "https://attacker.example"}, {"iat": time.time() - 3600},
                 {"iat": time.time() + 3600}, {"exp": time.time() - 1},
                 {"azp": "not-a-google-client"}, {"azp": [self.provider.client_id]},
                 {"sub": ""}, {"sub": "with space"}, {"aud": [self.provider.client_id]}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(GoogleSignInError):
                self.provider.verify_native(self.encode(**changes), self.flow)
    def test_malformed_or_oversized_token_is_rejected_without_certificate_io(self):
        for encoded in (None, {}, "A" * 17000, "none.unsigned.", "bad token"):
            with self.subTest(encoded_type=type(encoded)), self.assertRaises(GoogleSignInError):
                self.provider.verify_native(encoded, self.flow)
        self.assertFalse(self.cert_calls)
    def test_public_certificate_cache_avoids_repeat_io_until_ttl_expires(self):
        encoded = self.encode()
        with patch("google_signin.time.monotonic", return_value=100):
            self.provider.verify_native(encoded, self.flow)
            self.provider.verify_native(encoded, self.flow)
        self.assertEqual(len(self.cert_calls), 1)
        self.assertNotIn(encoded, repr(self.provider._certificate_cache))
        with patch("google_signin.time.monotonic", return_value=401):
            self.provider.verify_native(encoded, self.flow)
        self.assertEqual(len(self.cert_calls), 2)
    def test_no_store_no_cache_and_expired_age_disable_certificate_caching(self):
        for control, age in (("no-store, max-age=300", "0"), ("max-age=300, no-cache", "0"),
                             ("public, max-age=300", "301"), ("public", "0")):
            with self.subTest(control=control, age=age):
                self.provider._certificate_cache = None
                self.cache_control, self.age = control, age
                before = len(self.cert_calls)
                self.provider.verify_native(self.encode(), self.flow)
                self.provider.verify_native(self.encode(), self.flow)
                self.assertEqual(len(self.cert_calls), before + 2)
    def test_jwks_marker_is_rejected_before_verifier_can_create_another_network_client(self):
        for keys in ("even-a-string-is-a-jwks-marker", []):
            response = SimpleNamespace(status=200, data=json.dumps({"keys": keys}).encode(),
                                       headers={"Cache-Control": "max-age=300"})
            with self.subTest(keys=keys), patch("google.auth.transport.requests.Request", return_value=lambda *args, **kwargs: response):
                with self.assertRaises(ValueError):
                    self.provider._native_certificates("https://www.googleapis.com/oauth2/v1/certs")
                self.assertIsNone(self.provider._certificate_cache)


class NativeCredentialHTTPChecks(unittest.TestCase):
    def setUp(self):
        self.world = app.World(":memory:", now=fixtures.NOW)
        self.server = app.build_server(self.world, port=0, update_policy=app.UpdatePolicy(min_version_code=63, latest_version_code=63))
        self.server.google_signin = GoogleSignInService(self.world, NativeProvider())
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
    def tearDown(self):
        self.server.shutdown()
        self.worker.join(3)
        self.server.server_close()
        self.world.close()
    def request(self, path, body, **overrides):
        headers = {"Content-Type": "application/json", "X-PGR-Client-Platform": "android", "X-PGR-Client-Version": "65"}
        headers.update(overrides)
        headers = {key: value for key, value in headers.items() if value is not None}
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        connection.request("POST", path, json.dumps(body), headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), json.loads(response.read())
        connection.close()
        return result
    def test_real_native_http_flow_creates_session_without_cookie_or_browser_roundtrip(self):
        status, headers, flow = self.request("/api/auth/google/native/start", {"client": "android", "mode": "login"})
        self.assertEqual(status, 200)
        self.assertNotIn("Set-Cookie", headers)
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, _, result = self.request("/api/auth/google/native/verify", {**flow, "id_token": "local-id-token"})
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "needs_name")
        status, _, result = self.request("/api/auth/google/complete", {**flow, "name": "Native HTTP"})
        self.assertEqual(status, 200)
        self.assertEqual(self.world.authenticate(result["token"]), result["state"]["player"]["id"])
    def test_native_requires_android_platform_and_current_valid_version(self):
        cases = [({"X-PGR-Client-Platform": "web"}, 400),
                 ({"X-PGR-Client-Platform": None}, 400),
                 ({"X-PGR-Client-Version": "62"}, 426),
                 ({"X-PGR-Client-Version": None}, 426),
                 ({"X-PGR-Client-Version": "invalid"}, 426),
                 ({"X-PGR-Client-Version": "9999999999"}, 426)]
        for headers, expected in cases:
            with self.subTest(headers=headers):
                status, _, _ = self.request("/api/auth/google/native/start", {"client": "android"}, **headers)
                self.assertEqual(status, expected)
        self.assertFalse(self.server.google_signin.flows)
    def test_native_rejects_web_body_and_link_without_existing_authenticated_account(self):
        status, _, _ = self.request("/api/auth/google/native/start", {"client": "web"})
        self.assertEqual(status, 400)
        status, _, _ = self.request("/api/auth/google/native/start", {"client": "android", "mode": "link"})
        self.assertEqual(status, 401)
        self.assertFalse(self.server.google_signin.flows)
