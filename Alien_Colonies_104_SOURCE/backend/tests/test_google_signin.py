"""OAuth provider isolation, real SQLite identities and HTTP handoff security."""
import copy
import hashlib
import http.client
from http.cookies import SimpleCookie
import json
import os
import re
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit, urlencode

import app
from google_signin import (COOKIE_NAME, FLOW_TTL, GoogleOAuthProvider,
                           GoogleSignInError, GoogleSignInService)


NOW = 1_900_000_000.0
PASSWORD = "legacy-password-123"


class FakeProvider:
    ready = True
    origin = "https://aliencolonies.com"
    def __init__(self):
        self.subject, self.error = "google_subject_one", None
        self.exchange_hook = None
    def authorization_url(self, flow):
        return "https://accounts.google.com/o/oauth2/v2/auth?state=" + flow["state"]
    def exchange(self, code, flow):
        if self.exchange_hook:
            self.exchange_hook()
        if self.error:
            raise self.error
        return self.subject


class GoogleSignInScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "google.sqlite3"
        self.world = app.World(str(self.path), now=NOW)
        self.provider = FakeProvider()
        self.clock = 100.0
        self.service = GoogleSignInService(self.world, self.provider, clock=lambda: self.clock)
    def tearDown(self):
        self.world.close()
        self.tmp.cleanup()
    def begin(self, mode="login", **kw):
        result = self.service.start(mode, **kw)
        query = parse_qs(urlsplit(result["authorization_url"]).query)
        location, cookie = self.service.open(query["flow"][0], query["open"][0])
        if "verification_code" in result:
            self.assertIsNone(location)
            native = self.service.flows[result["flow_id"]]
            self.service.confirm(result["flow_id"], cookie, native["confirm_csrf"], result["verification_code"])
        return result, self.service.flows[result["flow_id"]]["state"], cookie
    def verified(self, mode="login", **kw):
        flow, state, cookie = self.begin(mode, **kw)
        self.assertTrue(self.service.callback(state, cookie, code="provider_code"))
        return flow
    def complete(self, flow, name="New Empire"):
        return self.service.complete(flow["flow_id"], flow["poll_secret"], name)
    def legacy(self, name="Legacy Empire"):
        self.world.require_google_registration = False
        result = self.world.register(name, PASSWORD)
        self.world.require_google_registration = True
        return result

    def test_unknown_subject_requires_name_before_creating_one_empire(self):
        flow = self.verified()
        self.assertEqual(self.service.status(flow["flow_id"], flow["poll_secret"]), {"ok": True, "status": "needs_name"})
        self.assertEqual(len(self.world.data["players"]), 0)
        with self.assertRaises(app.GameError):
            self.complete(flow, None)
        result = self.complete(flow)
        self.assertTrue(result["state"]["account"]["google_linked"])
        self.assertFalse(result["state"]["account"]["password_login_enabled"])
        self.assertEqual(self.world.authenticate(result["token"]), result["state"]["player"]["id"])
        self.assertEqual(self.world.db.execute("SELECT count(*) FROM google_accounts").fetchone()[0], 1)

    def test_same_google_subject_always_returns_original_empire_even_other_name(self):
        first = self.complete(self.verified())
        flow = self.verified()
        self.assertEqual(self.service.status(flow["flow_id"], flow["poll_secret"])["status"], "ready")
        second = self.complete(flow, "Different Empire")
        self.assertEqual(first["state"]["player"]["id"], second["state"]["player"]["id"])
        self.assertEqual(len(self.world.data["players"]), 1)

    def test_duplicate_and_invalid_names_are_retryable_without_claim_or_registration(self):
        legacy = self.legacy()
        flow = self.verified()
        before = copy.deepcopy(self.world.data)
        for name in ("Legacy Empire", "x", "<script>", ["bad"], None):
            with self.subTest(name=name):
                with self.assertRaises(app.GameError):
                    self.complete(flow, name)
                self.assertEqual(self.world.data, before)
        self.assertEqual(self.world.db.execute("SELECT count(*) FROM google_accounts").fetchone()[0], 0)
        self.assertNotEqual(self.complete(flow)["state"]["player"]["id"], legacy["state"]["player"]["id"])

    def test_poll_proof_is_required_and_never_appears_in_browser_url_or_world(self):
        flow, state, cookie = self.begin()
        self.assertNotIn(flow["poll_secret"], flow["authorization_url"])
        self.assertNotIn(flow["poll_secret"], json.dumps(self.service.flows))
        self.assertNotIn(flow["poll_secret"], json.dumps(self.world.data))
        wrong = "A" * 43
        for action in (self.service.status, self.service.complete):
            with self.assertRaises(GoogleSignInError):
                action(flow["flow_id"], wrong)
        with self.assertRaises(GoogleSignInError):
            self.service.complete(flow["flow_id"], flow["poll_secret"], "Too Early")
        self.assertEqual(len(self.world.data["players"]), 0)

    def test_open_cookie_state_and_callback_are_all_single_use(self):
        flow = self.service.start()
        query = parse_qs(urlsplit(flow["authorization_url"]).query)
        with self.assertRaises(GoogleSignInError):
            self.service.open(flow["flow_id"], "B" * 43)
        _, cookie = self.service.open(flow["flow_id"], query["open"][0])
        with self.assertRaises(GoogleSignInError):
            self.service.open(flow["flow_id"], query["open"][0])
        state = self.service.flows[flow["flow_id"]]["state"]
        self.service.confirm(flow["flow_id"], cookie, self.service.flows[flow["flow_id"]]["confirm_csrf"], flow["verification_code"])
        for bad_state, bad_cookie in (("B" * 43, cookie), (state, "B" * 43), (state, None)):
            with self.assertRaises(GoogleSignInError):
                self.service.callback(bad_state, bad_cookie, code="code")
        self.assertTrue(self.service.callback(state, cookie, code="code"))
        with self.assertRaises(GoogleSignInError):
            self.service.callback(state, cookie, code="code")
        self.complete(flow)
        with self.assertRaises(GoogleSignInError):
            self.complete(flow)

    def test_failed_or_cancelled_google_never_creates_session_or_account(self):
        for canceled in (False, True):
            flow, state, cookie = self.begin()
            self.provider.error = GoogleSignInError("Fixed authentication failure", 401)
            self.assertFalse(self.service.callback(state, cookie, code="code", error="access_denied" if canceled else None))
            self.assertEqual(self.service.status(flow["flow_id"], flow["poll_secret"])["status"], "error")
            with self.assertRaises(GoogleSignInError):
                self.complete(flow)
        self.assertEqual(self.world.db.execute("SELECT count(*) FROM accounts").fetchone()[0], 0)
        self.assertEqual(self.world.db.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)

    def test_expired_flow_and_proof_are_rejected_and_pruned(self):
        flow = self.verified()
        self.clock += FLOW_TTL
        with self.assertRaises(GoogleSignInError):
            self.complete(flow)
        self.assertEqual(self.service.flows, {})

    def test_pending_flow_store_has_a_hard_cap(self):
        for _ in range(512):
            self.service.start()
        with self.assertRaises(GoogleSignInError) as caught:
            self.service.start()
        self.assertEqual(caught.exception.status, 429)
        self.clock += FLOW_TTL
        self.service.start()
        self.assertEqual(len(self.service.flows), 1)

    def test_claim_is_single_use_under_concurrent_calls(self):
        flow = self.verified()
        results = []
        def claim():
            try:
                results.append(self.complete(flow))
            except GoogleSignInError:
                results.append(None)
        workers = [threading.Thread(target=claim) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(5)
            self.assertFalse(worker.is_alive())
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(len(self.world.data["players"]), 1)

    def test_network_exchange_holds_neither_simulation_nor_flow_lock(self):
        flow, state, cookie = self.begin()
        def check_other_thread():
            acquired = []
            def try_locks():
                with self.world.lock:
                    with self.service.lock:
                        acquired.append(True)
            thread = threading.Thread(target=try_locks)
            thread.start()
            thread.join(1)
            self.assertEqual(acquired, [True])
        self.provider.exchange_hook = check_other_thread
        self.assertTrue(self.service.callback(state, cookie, code="code"))

    def test_link_preserves_progress_existing_password_and_player_identity(self):
        legacy = self.legacy()
        player_id = legacy["state"]["player"]["id"]
        before = copy.deepcopy(self.world.data["players"][player_id])
        flow = self.verified("link", player_id=player_id, session_hash=hashlib.sha256(legacy["token"].encode()).hexdigest())
        result = self.complete(flow, "Ignored Name")
        self.assertEqual(result["state"]["player"]["id"], player_id)
        self.assertEqual(self.world.data["players"][player_id], before)
        self.assertTrue(result["state"]["account"]["password_login_enabled"])
        self.assertEqual(self.world.login("Legacy Empire", PASSWORD)["state"]["player"]["id"], player_id)

    def test_link_rechecks_original_session_and_cannot_switch_empire(self):
        legacy = self.legacy()
        player_id = legacy["state"]["player"]["id"]
        flow = self.verified("link", player_id=player_id, session_hash=hashlib.sha256(legacy["token"].encode()).hexdigest())
        self.world.logout(legacy["token"])
        with self.assertRaises(app.GameError) as caught:
            self.complete(flow)
        self.assertEqual(caught.exception.status, 401)
        self.assertEqual(self.world.db.execute("SELECT count(*) FROM google_accounts").fetchone()[0], 0)

    def test_one_google_account_and_one_subject_per_empire(self):
        first = self.complete(self.verified())
        other = self.legacy("Other Empire")
        other_id = other["state"]["player"]["id"]
        flow = self.verified("link", player_id=other_id, session_hash=hashlib.sha256(other["token"].encode()).hexdigest())
        with self.assertRaises(app.GameError) as caught:
            self.complete(flow)
        self.assertEqual(caught.exception.status, 409)
        first_id = first["state"]["player"]["id"]
        self.provider.subject = "different_google_subject"
        flow = self.verified("link", player_id=first_id, session_hash=hashlib.sha256(first["token"].encode()).hexdigest())
        with self.assertRaises(app.GameError) as caught:
            self.complete(flow)
        self.assertEqual(caught.exception.status, 409)

    def test_link_identity_survives_restart_and_does_not_leak_into_state(self):
        result = self.complete(self.verified())
        player_id = result["state"]["player"]["id"]
        self.assertNotIn(self.provider.subject, json.dumps(result["state"]) + json.dumps(self.world.data))
        self.world.close()
        self.world = app.World(str(self.path), now=NOW)
        self.service = GoogleSignInService(self.world, self.provider, clock=lambda: self.clock)
        self.assertEqual(self.complete(self.verified())["state"]["player"]["id"], player_id)

    def test_google_only_sensitive_actions_require_recent_google_sign_in(self):
        result = self.complete(self.verified())
        self.assertTrue(self.world.account_recovery_code(result["token"], "")["ok"])
        self.world.now = NOW + 301
        with self.assertRaises(app.GameError) as caught:
            self.world.account_recovery_code(result["token"], "")
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.world.authenticate(result["token"]), result["state"]["player"]["id"])

    def test_google_account_delete_removes_identity_and_sessions(self):
        result = self.complete(self.verified())
        self.assertTrue(self.world.account_delete(result["token"], "", "DELETE ACCOUNT")["deleted"])
        for table in ("google_accounts", "google_sessions", "accounts", "sessions"):
            self.assertEqual(self.world.db.execute("SELECT count(*) FROM " + table).fetchone()[0], 0)

    def test_google_account_can_explicitly_set_a_password_then_normal_password_rules_apply(self):
        result = self.complete(self.verified())
        updated = self.world.account_password(result["token"], "", PASSWORD)
        self.assertTrue(updated["state"]["account"]["password_login_enabled"])
        self.assertEqual(self.world.login("New Empire", PASSWORD)["state"]["player"]["id"], result["state"]["player"]["id"])
        with self.assertRaises(app.GameError):
            self.world.account_recovery_code(updated["token"], "")

    def test_configured_google_blocks_legacy_signup_but_preserves_password_login(self):
        legacy = self.legacy()
        with self.assertRaises(app.GameError) as caught:
            self.world.register("Spam Empire", PASSWORD)
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.world.login("Legacy Empire", PASSWORD)["state"]["player"]["id"], legacy["state"]["player"]["id"])

    def test_missing_configuration_is_graceful_and_does_not_activate_default_signup_gate(self):
        with patch.dict(os.environ, {}, clear=True):
            service = GoogleSignInService(self.world)
        self.assertEqual(service.config(), {"ok": True, "configured": False, "native_configured": False, "require_google_registration": False})
        with self.assertRaises(GoogleSignInError) as caught:
            service.start()
        self.assertEqual(caught.exception.status, 503)
        self.assertTrue(self.world.register("Legacy Signup", PASSWORD)["ok"])

    def test_forwarded_web_open_link_cannot_authorize_in_a_different_browser(self):
        cookie = "W" * 43
        flow = self.service.start(client="web", browser_cookie=cookie)
        query = parse_qs(urlsplit(flow["authorization_url"]).query)
        self.assertNotIn("verification_code", flow)
        for other_cookie in (None, "A" * 43):
            with self.assertRaises(GoogleSignInError):
                self.service.open(flow["flow_id"], query["open"][0], other_cookie)
        self.assertFalse(self.service.flows[flow["flow_id"]]["opened"])
        location, bound_cookie = self.service.open(flow["flow_id"], query["open"][0], cookie)
        self.assertTrue(location.startswith("https://accounts.google.com/"))
        self.assertEqual(bound_cookie, cookie)

    def test_native_open_only_shows_entry_form_and_requires_code_from_app(self):
        flow = self.service.start(client="android")
        query = parse_qs(urlsplit(flow["authorization_url"]).query)
        location, cookie = self.service.open(flow["flow_id"], query["open"][0])
        self.assertIsNone(location)
        self.assertRegex(flow["verification_code"], r"^[0-9]{6}$")
        raw = self.service.confirmation_document(flow["flow_id"]).decode()
        self.assertNotIn(flow["verification_code"], raw + flow["authorization_url"])
        self.assertNotIn(flow["poll_secret"], raw + flow["authorization_url"])
        state = self.service.flows[flow["flow_id"]]["state"]
        with self.assertRaises(GoogleSignInError):
            self.service.callback(state, cookie, code="unconfirmed_code")
        csrf = self.service.flows[flow["flow_id"]]["confirm_csrf"]
        for wrong_cookie, wrong_csrf in (("A" * 43, csrf), (cookie, "A" * 43)):
            with self.assertRaises(GoogleSignInError):
                self.service.confirm(flow["flow_id"], wrong_cookie, wrong_csrf, flow["verification_code"])
        location = self.service.confirm(flow["flow_id"], cookie, csrf, flow["verification_code"])
        self.assertTrue(location.startswith("https://accounts.google.com/"))
        with self.assertRaises(GoogleSignInError):
            self.service.confirm(flow["flow_id"], cookie, csrf, flow["verification_code"])
        self.assertTrue(self.service.callback(state, cookie, code="confirmed_code"))

    def test_five_wrong_native_codes_lock_the_flow_and_correct_code_no_longer_works(self):
        flow = self.service.start(client="android")
        query = parse_qs(urlsplit(flow["authorization_url"]).query)
        _, cookie = self.service.open(flow["flow_id"], query["open"][0])
        csrf = self.service.flows[flow["flow_id"]]["confirm_csrf"]
        for index in range(5):
            with self.assertRaises(GoogleSignInError) as caught:
                self.service.confirm(flow["flow_id"], cookie, csrf, "000000")
            self.assertEqual(caught.exception.status, 429 if index == 4 else 400)
        self.assertEqual(self.service.status(flow["flow_id"], flow["poll_secret"])["status"], "error")
        with self.assertRaises(GoogleSignInError):
            self.service.confirm(flow["flow_id"], cookie, csrf, flow["verification_code"])

    def test_storage_failure_rolls_back_google_identity_and_empire_and_flow_can_retry(self):
        flow = self.verified()
        before = copy.deepcopy(self.world.data)
        with patch.object(self.world, "_save", side_effect=OSError("disk full")):
            with self.assertRaises(app.GameError) as caught:
                self.complete(flow)
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(self.world.data, before)
        for table in ("accounts", "sessions", "google_accounts", "google_sessions"):
            self.assertEqual(self.world.db.execute("SELECT count(*) FROM " + table).fetchone()[0], 0)
        self.assertTrue(self.complete(flow)["ok"])


class ProviderClaimChecks(unittest.TestCase):
    def setUp(self):
        self.provider = GoogleOAuthProvider("123-example.apps.googleusercontent.com", "private-placeholder")
        now = time.time()
        self.claims = {"aud": self.provider.client_id, "iss": "https://accounts.google.com",
                       "sub": "subject_one", "nonce": "N" * 43, "iat": now - 10, "exp": now + 3600}
    def test_valid_signed_claims_use_subject_and_not_name_or_email(self):
        self.claims.update(email="existing@example.com", name="Legacy Empire")
        self.assertEqual(self.provider.validate_claims(self.claims, "N" * 43), "subject_one")
    def test_wrong_audience_issuer_nonce_expiry_authorized_party_or_subject_are_rejected(self):
        invalid = (("aud", "different-client"), ("iss", "https://attacker.example"),
                   ("nonce", "wrong-nonce"), ("exp", time.time() - 1), ("exp", float("nan")),
                   ("iat", time.time() + 3600), ("azp", "different-client"), ("sub", ""), ("sub", "with space"))
        for key, value in invalid:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.provider.validate_claims({**self.claims, key: value}, "N" * 43)
    def test_authorization_uses_exact_redirect_nonce_state_and_pkce(self):
        flow = {"state": "S" * 43, "nonce": "N" * 43, "verifier": "V" * 64}
        query = parse_qs(urlsplit(self.provider.authorization_url(flow)).query)
        self.assertEqual(query["scope"], ["openid profile"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertNotEqual(query["code_challenge"], [flow["verifier"]])
        self.assertEqual(query["redirect_uri"], ["https://aliencolonies.com/api/auth/google/callback"])
        self.assertEqual(query["nonce"], [flow["nonce"]])
        self.assertEqual(query["state"], [flow["state"]])


class ProviderCryptographicChecks(unittest.TestCase):
    """Use Google's real verifier with local RSA certificates, without egress."""
    def setUp(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        from datetime import datetime, timedelta, timezone
        from google.auth.crypt import RSASigner
        from google.auth import jwt
        self.provider = GoogleOAuthProvider("123-example.apps.googleusercontent.com", "private-placeholder")
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.private_pem = self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Local Google verification fixture")])
        now = datetime.now(timezone.utc)
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(self.key.public_key())
                       .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
                       .not_valid_after(now + timedelta(days=1)).sign(self.key, hashes.SHA256()))
        self.certificate = certificate.public_bytes(serialization.Encoding.PEM).decode()
        seconds = int(time.time())
        self.claims = {"aud": self.provider.client_id, "iss": "https://accounts.google.com", "sub": "rsa_subject",
                       "nonce": "N" * 43, "iat": seconds - 10, "exp": seconds + 3600}
        self.encoded = jwt.encode(RSASigner.from_string(self.private_pem, key_id="fixture-key"), self.claims).decode()
        self.closed, self.cert_timeouts, self.post_fields = [], [], []
        owner = self
        class FakeSession:
            def close(inner):
                owner.closed.append(True)
        class FakeRequests:
            Session = FakeSession
            def post(inner, url, data, timeout):
                owner.post_fields.append((url, data, timeout))
                class Response:
                    status_code = 200
                    content = b"local response"
                    def json(inner):
                        return {"id_token": owner.encoded}
                return Response()
        class Certificates:
            status = 200
            data = json.dumps({"fixture-key": self.certificate}).encode()
        def request(*args, **kwargs):
            self.cert_timeouts.append(kwargs.get("timeout"))
            return Certificates()
        self.provider._requests = FakeRequests()
        self.request_patch = patch("google.auth.transport.requests.Request", return_value=request)
        self.request_patch.start()
        self.flow = {"nonce": "N" * 43, "verifier": "V" * 64}
    def tearDown(self):
        self.request_patch.stop()
    def test_real_google_verifier_accepts_rsa_signed_token_and_bounds_network_timeouts(self):
        self.assertEqual(self.provider.exchange("private-authorization-code", self.flow), "rsa_subject")
        self.assertEqual(self.closed, [True])
        self.assertEqual(self.cert_timeouts, [8])
        self.assertEqual(self.post_fields[0][2], (3, 8))
        self.assertEqual(self.post_fields[0][1]["code_verifier"], self.flow["verifier"])
    def test_forged_signature_and_wrong_nonce_are_rejected_without_secret_in_error(self):
        valid = self.encoded
        head, body, signature = self.encoded.split(".")
        self.encoded = head + "." + body + "." + ("A" * len(signature))
        for encoded, nonce in ((self.encoded, "N" * 43), (valid, "wrong_nonce")):
            self.encoded = encoded
            with self.assertRaises(GoogleSignInError) as caught:
                self.provider.exchange("private-authorization-code", {**self.flow, "nonce": nonce})
            self.assertEqual(caught.exception.status, 401)
            self.assertNotIn("private-authorization-code", caught.exception.message)
            self.assertNotIn(self.provider.client_secret, caught.exception.message)
    def test_invalid_provider_json_or_unsigned_token_cannot_authenticate(self):
        self.encoded = "A" * 80
        with self.assertRaises(GoogleSignInError) as caught:
            self.provider.exchange("private-authorization-code", self.flow)
        self.assertEqual(caught.exception.status, 401)


class GoogleHTTPScenarios(unittest.TestCase):
    def setUp(self):
        self.world = app.World(":memory:", now=NOW)
        self.world.register("Legacy HTTP", PASSWORD)
        self.server = app.build_server(self.world, port=0)
        self.server.google_signin = GoogleSignInService(self.world, FakeProvider())
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
    def tearDown(self):
        self.server.shutdown()
        self.worker.join(3)
        self.server.server_close()
        self.world.close()
    def request(self, path, data=None, *, headers=None, form=False):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        request_headers = {"X-PGR-Client-Version": "56", "Content-Type": "application/x-www-form-urlencoded" if form else "application/json", **(headers or {})}
        body = (urlencode(data) if form else json.dumps(data)).encode() if data is not None else None
        conn.request("POST" if data is not None else "GET", path, body=body, headers=request_headers)
        response = conn.getresponse()
        raw = response.read()
        status, response_headers = response.status, dict(response.getheaders())
        conn.close()
        return status, response_headers, raw
    def test_browser_open_and_callback_need_no_native_version_and_no_tokens_leak(self):
        status, headers, raw = self.request("/api/auth/google/start", {"mode": "login", "client": "web"})
        self.assertEqual(status, 200)
        flow = json.loads(raw)
        parsed = urlsplit(flow["authorization_url"])
        open_path = parsed.path + "?" + parsed.query
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, headers, raw = self.request(open_path, headers={"X-PGR-Client-Version": "", "Cookie": cookie})
        self.assertEqual(status, 302)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Lax", headers["Set-Cookie"])
        self.assertIn("Secure", headers["Set-Cookie"])
        self.assertNotIn(flow["poll_secret"], str(headers) + raw.decode())
        state = parse_qs(urlsplit(headers["Location"]).query)["state"][0]
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, headers, raw = self.request("/api/auth/google/callback?state=" + state + "&code=provider_code", headers={"Cookie": cookie, "X-PGR-Client-Version": ""})
        self.assertEqual(status, 200)
        self.assertNotIn(flow["poll_secret"], raw.decode())
        status, _, raw = self.request("/api/auth/google/complete", {"flow_id": flow["flow_id"], "poll_secret": flow["poll_secret"], "name": "HTTP Google"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(raw)["token"])
    def test_link_start_requires_valid_bearer_and_current_password(self):
        login = self.world.login("Legacy HTTP", PASSWORD)
        for headers, password in (({}, PASSWORD), ({"Authorization": "Bearer " + login["token"]}, "wrong-password")):
            status, _, _ = self.request("/api/auth/google/start", {"mode": "link", "password": password}, headers=headers)
            self.assertIn(status, (401, 403))
        status, _, _ = self.request("/api/auth/google/start", {"mode": "link", "password": PASSWORD}, headers={"Authorization": "Bearer " + login["token"]})
        self.assertEqual(status, 200)
    def test_extra_payload_fields_cannot_bypass_google_registration_policy(self):
        status, _, _ = self.request("/api/register", {"name": "Blocked Spam", "password": PASSWORD, "_google_verified": True, "google_subject": "forged"})
        self.assertEqual(status, 403)
        self.assertEqual(len(self.world.data["players"]), 1)

    def test_forwarded_browser_open_requires_start_cookie_before_google_redirect(self):
        status, headers, raw = self.request("/api/auth/google/start", {"mode": "login", "client": "web"})
        self.assertEqual(status, 200)
        flow = json.loads(raw)
        parsed = urlsplit(flow["authorization_url"])
        open_path = parsed.path + "?" + parsed.query
        status, _, _ = self.request(open_path)
        self.assertNotEqual(status, 302)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertNotIn(cookie.split("=", 1)[1], raw.decode())
        status, _, _ = self.request(open_path, headers={"Cookie": COOKIE_NAME + "=" + "A" * 43})
        self.assertNotEqual(status, 302)
        status, _, _ = self.request(open_path, headers={"Cookie": cookie})
        self.assertEqual(status, 302)

    def test_native_browser_confirmation_form_gates_oauth_and_verifies_code_cookie_and_csrf(self):
        status, _, raw = self.request("/api/auth/google/start", {"mode": "login", "client": "android"})
        self.assertEqual(status, 200)
        flow = json.loads(raw)
        parsed = urlsplit(flow["authorization_url"])
        status, headers, raw = self.request(parsed.path + "?" + parsed.query, headers={"X-PGR-Client-Version": ""})
        self.assertEqual(status, 200)
        self.assertNotIn("Location", headers)
        self.assertNotIn(flow["verification_code"], raw.decode())
        self.assertNotIn(flow["poll_secret"], raw.decode())
        # Chromium applies form-action to a form submission's redirect chain.
        # Merely checking that /confirm returns 302 missed the production bug:
        # form-action 'self' allowed the POST but blocked the Google redirect.
        policy = headers["Content-Security-Policy"]
        form_action = next(part.strip().split()[1:] for part in policy.split(";")
                           if part.strip().startswith("form-action "))
        self.assertIn("'self'", form_action)
        self.assertIn("https://accounts.google.com", form_action)
        self.assertNotIn("*", form_action)
        self.assertNotIn("https:", form_action)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        csrf = re.search(r"name='csrf' value='([^']+)'", raw.decode()).group(1)
        state = self.server.google_signin.flows[flow["flow_id"]]["state"]
        status, callback_headers, _ = self.request("/api/auth/google/callback?state=" + state + "&code=code", headers={"Cookie": cookie})
        self.assertEqual(status, 401)
        self.assertNotIn("Set-Cookie", callback_headers)
        form = {"flow": flow["flow_id"], "csrf": csrf, "code": flow["verification_code"]}
        status, _, _ = self.request("/api/auth/google/confirm", form, form=True)
        self.assertEqual(status, 410)
        status, _, _ = self.request("/api/auth/google/confirm", {**form, "csrf": "A" * 43}, form=True, headers={"Cookie": cookie})
        self.assertEqual(status, 401)
        status, headers, raw = self.request("/api/auth/google/confirm", {**form, "code": "000000"}, form=True, headers={"Cookie": cookie})
        self.assertEqual(status, 400)
        self.assertNotIn("Location", headers)
        status, headers, raw = self.request("/api/auth/google/confirm", form, form=True, headers={"Cookie": cookie, "X-PGR-Client-Version": ""})
        self.assertEqual(status, 302)
        self.assertTrue(headers["Location"].startswith("https://accounts.google.com/"))
        status, _, _ = self.request("/api/auth/google/callback?state=" + state + "&code=code", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        status, _, raw = self.request("/api/auth/google/complete", {"flow_id": flow["flow_id"], "poll_secret": flow["poll_secret"], "name": "Native HTTP"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(raw)["token"])


if __name__ == "__main__":
    unittest.main()
