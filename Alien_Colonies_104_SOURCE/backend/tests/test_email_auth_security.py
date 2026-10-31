"""Independent adversarial tests for the email-link authentication boundary.

All mail is captured locally, all accounts use a disposable SQLite database,
and all HTTP traffic is loopback. No production account or provider is touched.
"""
import concurrent.futures
import http.client
import json
from pathlib import Path
import re
import secrets
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit
from unittest.mock import patch

import app
from email_signin import (
    EmailSignInError, EmailSignInService,
    FLOW_TTL, NATIVE_HANDOFF, RECENT_EMAIL_SECONDS, ResendEmailProvider,
)


class CapturingSender:
    ready = True
    origin = "https://aliencolonies.com"

    def __init__(self):
        self.messages = []
        self.hook = None

    def send(self, address, link, *, request_id):
        if self.hook:
            self.hook()
        self.messages.append((address, link, request_id))


class EmailAdversarialReview(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temporary.name) / "email-security.sqlite3"
        self.world = app.World(str(self.db_path), now=1_900_000_000.0)
        self.sender = CapturingSender()
        self.clock = 100.0
        self.service = EmailSignInService(self.world, self.sender, clock=lambda: self.clock)
        self.server = None

    def tearDown(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.worker.join(3)
        self.world.close()
        self.temporary.cleanup()

    def begin(self, address="pilot@example.com", *, client="android"):
        cookie = secrets.token_urlsafe(32) if client == "web" else None
        flow = self.service.start(address, client=client,
                                  handoff=NATIVE_HANDOFF if client == "android" else None,
                                  browser_cookie=cookie, ip=secrets.token_hex(8))
        link = next(link for _, link, request_id in self.sender.messages
                    if request_id == flow["flow_id"])
        token = parse_qs(urlsplit(link).query)["token"][0]
        return flow, cookie, token

    def verified(self, address="pilot@example.com", *, client="android"):
        flow, cookie, token = self.begin(address, client=client)
        document, confirmation_cookie = self.service.open(flow["flow_id"], token, cookie)
        csrf = re.search(r'name="csrf" value="([^"]+)"', document)[1]
        callback = self.service.confirm(flow["flow_id"], confirmation_cookie, csrf)
        proof = {"browser_cookie": cookie} if client == "web" else {
            "handoff_ticket": parse_qs(urlsplit(callback).query)["handoff_ticket"][0]}
        return flow, proof

    def complete(self, flow, proof, name="Review Empire"):
        return self.service.complete(flow["flow_id"], flow["poll_secret"], name, **proof)

    def count(self, table):
        return self.world.db.execute("SELECT count(*) FROM " + table).fetchone()[0]

    def http(self, path, body=None, *, headers=None, form=False):
        if self.server is None:
            self.server = app.build_server(self.world, port=0)
            self.server.email_signin = self.service
            self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.worker.start()
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        header = {"X-PGR-Client-Version": "64", "Origin": self.sender.origin,
                  "Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
        header.update(headers or {})
        raw = (urlencode(body) if form else json.dumps(body)).encode() if body is not None else None
        connection.request("POST" if body is not None else "GET", path, raw, headers=header)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_native_poll_and_completed_status_cannot_replace_recipient_ticket(self):
        flow, proof = self.verified()
        self.assertEqual(self.service.status(flow["flow_id"], flow["poll_secret"], **proof)["status"], "needs_name")
        # A valid status read must not cache authorization for later callers.
        for candidate in (None, "A" * 43, "", {"ticket": proof["handoff_ticket"]}):
            with self.subTest(candidate=candidate):
                self.assertEqual(self.service.status(flow["flow_id"], flow["poll_secret"], handoff_ticket=candidate),
                                 {"ok": True, "status": "pending"})
                with self.assertRaises(EmailSignInError):
                    self.service.complete(flow["flow_id"], flow["poll_secret"], "Stolen Empire", handoff_ticket=candidate)
        self.assertEqual(self.count("accounts"), 0)
        self.assertTrue(self.complete(flow, proof)["token"])

    def test_http_request_fields_cannot_downgrade_native_flow_or_claim_it(self):
        flow, proof = self.verified()
        base = {"flow_id": flow["flow_id"], "poll_secret": flow["poll_secret"]}
        for extra in ({"client": "web", "handoff": None}, {"verified": True, "handoff_received": True},
                      {"email": "pilot@example.com", "_email_verified": True}):
            with self.subTest(extra=extra):
                status, _, raw = self.http("/api/auth/email/status", {**base, **extra})
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(raw), {"ok": True, "status": "pending"})
                status, _, _ = self.http("/api/auth/email/complete", {**base, **extra, "name": "Stolen Empire"})
                self.assertEqual(status, 409)
        self.assertEqual(self.count("accounts"), 0)
        status, _, raw = self.http("/api/auth/email/complete", {**base, **proof, "name": "Correct Empire"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(raw)["token"])

    def test_ticket_and_cookie_proofs_cannot_be_mixed_between_flows(self):
        for client in ("android", "web"):
            with self.subTest(client=client):
                first, proof_first = self.verified("first-" + client + "@example.com", client=client)
                second, proof_second = self.verified("second-" + client + "@example.com", client=client)
                with self.assertRaises(EmailSignInError):
                    self.complete(first, proof_second)
                with self.assertRaises(EmailSignInError):
                    self.complete(second, proof_first)
                first_result = self.complete(first, proof_first, "First " + client)
                second_result = self.complete(second, proof_second, "Second " + client)
                self.assertNotEqual(first_result["state"]["player"]["id"], second_result["state"]["player"]["id"])

    def test_scanner_get_is_non_consuming_and_only_latest_native_form_can_confirm(self):
        flow, _, token = self.begin()
        scanned, scanner_cookie = self.service.open(flow["flow_id"], token)
        actual, real_cookie = self.service.open(flow["flow_id"], token)
        scanner_csrf = re.search(r'name="csrf" value="([^"]+)"', scanned)[1]
        real_csrf = re.search(r'name="csrf" value="([^"]+)"', actual)[1]
        self.assertEqual(self.service.status(flow["flow_id"], flow["poll_secret"])["status"], "pending")
        for document in (scanned, actual):
            self.assertNotIn(token, document)
            self.assertNotIn(flow["poll_secret"], document)
        with self.assertRaises(EmailSignInError):
            self.service.confirm(flow["flow_id"], scanner_cookie, scanner_csrf)
        callback = self.service.confirm(flow["flow_id"], real_cookie, real_csrf)
        self.assertTrue(callback.startswith("com.conradmafer.aliencolonies://google-auth?"))
        with self.assertRaises(EmailSignInError):
            self.service.confirm(flow["flow_id"], real_cookie, real_csrf)
        with self.assertRaises(EmailSignInError):
            self.service.open(flow["flow_id"], token)
        self.assertEqual(self.count("accounts"), 0)

    def test_same_browser_confirmation_new_tab_and_original_tab_completion(self):
        status, headers, raw = self.http("/api/auth/email/start", {"email": "web@example.com", "client": "web"})
        self.assertEqual(status, 200)
        flow = json.loads(raw)
        original_cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertTrue(original_cookie.startswith("__Host-"))
        for flag in ("Path=/", "Secure", "HttpOnly", "SameSite=Lax"):
            self.assertIn(flag, headers["Set-Cookie"])
        link = self.sender.messages[-1][1]
        parsed = urlsplit(link)
        path = parsed.path + "?" + parsed.query
        self.assertEqual(self.http(path)[0], 403)  # recipient's different browser
        status, headers, raw = self.http(path, headers={"Cookie": original_cookie})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        # no-referrer makes Chromium navigation POSTs carry Origin:null.
        # strict-origin preserves the genuine origin but never the token URL.
        self.assertEqual(headers["Referrer-Policy"], "strict-origin")
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        confirmation_cookie = headers["Set-Cookie"].split(";", 1)[0]
        form = {"flow_id": flow["flow_id"], "csrf": re.search(r'name="csrf" value="([^"]+)"', raw.decode())[1]}
        for origin in ("https://attacker.example", "null"):
            self.assertEqual(self.http("/api/auth/email/confirm", form, form=True,
                                      headers={"Cookie": confirmation_cookie, "Origin": origin})[0], 403)
        status, headers, raw = self.http("/api/auth/email/confirm", form, form=True,
                                         headers={"Cookie": confirmation_cookie})
        self.assertEqual(status, 200)
        self.assertNotIn("Location", headers)
        self.assertNotIn(flow["poll_secret"].encode(), raw)
        proof = {"flow_id": flow["flow_id"], "poll_secret": flow["poll_secret"]}
        self.assertEqual(self.http("/api/auth/email/complete", {**proof, "name": "Web Empire"})[0], 403)
        status, _, raw = self.http("/api/auth/email/complete", {**proof, "name": "Web Empire"},
                                   headers={"Cookie": original_cookie})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(raw)["token"])

    def test_one_flow_claim_is_single_use_under_concurrency_and_later_replay(self):
        flow, proof = self.verified()
        barrier = threading.Barrier(4)
        def attempt():
            barrier.wait(timeout=5)
            try:
                return self.complete(flow, proof)
            except EmailSignInError:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: attempt(), range(4)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(self.count("accounts"), 1)
        self.assertEqual(self.count("sessions"), 1)
        for action in (self.service.status, self.service.complete):
            with self.assertRaises(EmailSignInError):
                action(flow["flow_id"], flow["poll_secret"], **proof)

    def test_concurrent_distinct_verified_links_for_same_email_create_one_identity(self):
        first, proof_first = self.verified("Pilot@Example.com")
        self.clock += 61
        second, proof_second = self.verified("pilot@example.COM")
        barrier = threading.Barrier(2)
        def claim(args):
            barrier.wait(timeout=5)
            return self.complete(*args)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(claim, [(first, proof_first, "First Name"), (second, proof_second, "Second Name")]))
        self.assertEqual(results[0]["state"]["player"]["id"], results[1]["state"]["player"]["id"])
        self.assertEqual(self.count("email_accounts"), 1)
        self.assertEqual(self.count("accounts"), 1)
        self.assertEqual(self.count("sessions"), 2)

    def test_restart_preserves_identity_but_rejects_stale_unfinished_flow(self):
        address = "restart@example.com"
        flow, proof = self.verified(address)
        result = self.complete(flow, proof)
        self.clock += 61
        stale, stale_proof = self.verified(address)
        self.world.close()
        self.world = app.World(str(self.db_path), now=1_900_000_000.0)
        self.service = EmailSignInService(self.world, self.sender, clock=lambda: self.clock)
        with self.assertRaises(EmailSignInError):
            self.complete(stale, stale_proof)
        fresh, fresh_proof = self.verified(address)
        self.assertEqual(self.complete(fresh, fresh_proof)["state"]["player"]["id"], result["state"]["player"]["id"])
        persistent = json.dumps(self.world.data) + " ".join(self.world.db.iterdump())
        for secret in (address, flow["poll_secret"], proof["handoff_ticket"], result["token"]):
            self.assertNotIn(secret, persistent)

    def test_recent_email_proof_is_session_bound_and_deletion_cascades(self):
        flow, proof = self.verified()
        first = self.complete(flow, proof)
        player_id = first["state"]["player"]["id"]
        self.clock += 61
        flow2, proof2 = self.verified()
        second = self.complete(flow2, proof2)
        self.world.account_logout_others(second["token"], "")
        with self.assertRaises(app.GameError):
            self.world.authenticate(first["token"])
        self.assertEqual(self.count("email_sessions"), 1)
        self.assertFalse(self.world._email_recent_session(second["token"], "another-player-id"))
        self.clock += 61
        stale, stale_proof = self.verified()
        self.world.account_delete(second["token"], "", "DELETE ACCOUNT")
        for table in ("accounts", "email_accounts", "sessions", "email_sessions"):
            self.assertEqual(self.count(table), 0)
        self.assertNotIn(player_id, self.world.data["players"])
        # A previously verified link cannot resurrect the deleted empire. At
        # most it can create a fresh one after another explicit name choice.
        with self.assertRaises(app.GameError):
            self.complete(stale, stale_proof, None)
        replacement = self.complete(stale, stale_proof, "Replacement Empire")
        self.assertNotEqual(replacement["state"]["player"]["id"], player_id)

    def test_expired_recent_session_cannot_authorize_account_deletion(self):
        result = self.complete(*self.verified())
        self.world.now += RECENT_EMAIL_SECONDS + 1
        with self.assertRaises(app.GameError) as error:
            self.world.account_delete(result["token"], "", "DELETE ACCOUNT")
        self.assertEqual(error.exception.status, 403)
        self.assertEqual(self.count("accounts"), 1)

    def test_mail_delivery_failure_holds_neither_world_nor_flow_lock_and_leaks_no_exception(self):
        marker = "SECRET_PROVIDER_TOKEN_AND_RECIPIENT"
        def failing_sender():
            acquired = []
            def acquire():
                with self.world.lock:
                    with self.service.lock:
                        acquired.append(True)
            worker = threading.Thread(target=acquire)
            worker.start()
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(acquired, [True])
            raise RuntimeError(marker)
        self.sender.hook = failing_sender
        with self.assertRaises(EmailSignInError) as error:
            self.begin()
        self.assertEqual(error.exception.status, 503)
        self.assertNotIn(marker, str(error.exception))
        self.assertEqual(self.service.flows, {})
        self.assertEqual(self.count("accounts"), 0)

    def test_host_and_unrecognized_callback_parameters_cannot_redirect_mail(self):
        status, _, raw = self.http("/api/auth/email/start", {"email": "origin@example.com", "client": "android",
                                                            "handoff": NATIVE_HANDOFF, "redirect_uri": "https://attacker.example"},
                                   headers={"Host": "attacker.example", "X-Forwarded-Host": "attacker.example"})
        self.assertEqual(status, 200)
        link = self.sender.messages[-1][1]
        self.assertTrue(link.startswith(self.sender.origin + "/api/auth/email/open?"))
        self.assertNotIn("attacker.example", link)
        query = urlsplit(link)
        status, _, _ = self.http(query.path + "?" + query.query + "&redirect=https://attacker.example")
        self.assertEqual(status, 410)

    def test_expiry_invalidates_all_browser_and_native_proofs(self):
        flow, proof = self.verified()
        self.clock += FLOW_TTL
        with self.assertRaises(EmailSignInError):
            self.complete(flow, proof)
        self.assertEqual(self.service.flows, {})
        self.assertEqual(self.count("accounts"), 0)

    def test_rate_limited_email_has_neutral_response_and_cannot_be_claimed(self):
        first, _, first_mail_token = self.begin()
        second = self.service.start("PILOT@example.com", client="android", handoff=NATIVE_HANDOFF, ip="other-device")
        self.assertEqual(set(first), set(second))
        for field in ("ok", "expires_in", "resend_after", "poll_after", "message", "handoff"):
            self.assertEqual(first[field], second[field])
        self.assertEqual(len(self.sender.messages), 1)
        with self.assertRaises(EmailSignInError):
            self.service.open(second["flow_id"], first_mail_token)
        self.assertEqual(self.service.status(second["flow_id"], second["poll_secret"]), {"ok": True, "status": "pending"})
        self.assertEqual(self.count("accounts"), 0)

    def test_rate_key_and_flow_caps_fail_closed_without_eviction(self):
        with patch("email_signin.MAX_RATE_KEYS", 12):
            for index in range(32):
                try:
                    self.service.start("bounded" + str(index) + "@example.com", client="android", handoff=NATIVE_HANDOFF,
                                       ip="unique-source-" + str(index))
                except EmailSignInError as error:
                    self.assertEqual(error.status, 429)
            self.assertLessEqual(len(self.service.rates), 12)
        self.service = EmailSignInService(self.world, self.sender, clock=lambda: self.clock)
        self.sender.messages.clear()
        with patch("email_signin.MAX_FLOWS", 2):
            first, cookie, mail_token = self.begin("retained@example.com")
            self.begin("other@example.com")
            with self.assertRaises(EmailSignInError) as error:
                self.begin("overflow@example.com")
            self.assertEqual(error.exception.status, 429)
            self.assertEqual(len(self.service.flows), 2)
            document, _ = self.service.open(first["flow_id"], mail_token, cookie)
            self.assertIn("Confirm my sign-in", document)

    def test_resend_provider_uses_fixed_endpoint_no_redirects_and_sanitized_failures(self):
        captured = {}
        provider = ResendEmailProvider("secret-test-provider-key", "Alien Colonies <login@aliencolonies.com>")
        class FailedTransport:
            def open(inner, request, timeout):
                captured.update(request=request, timeout=timeout)
                raise RuntimeError("secret-test-provider-key recipient@example.com private-link-token")
        def opener(*handlers):
            captured["handlers"] = handlers
            return FailedTransport()
        with patch("email_signin.build_opener", side_effect=opener), self.assertRaises(EmailSignInError) as error:
            provider.send("recipient@example.com", "https://aliencolonies.com/private-link-token", request_id="test-flow")
        self.assertEqual(captured["request"].full_url, "https://api.resend.com/emails")
        self.assertEqual(captured["request"].method, "POST")
        self.assertEqual(captured["timeout"], 8)
        self.assertTrue(any(handler.redirect_request(None, None, 302, "", {}, "https://attacker.example") is None
                            for handler in captured["handlers"]))
        for secret in ("secret-test-provider-key", "recipient@example.com", "private-link-token"):
            self.assertNotIn(secret, str(error.exception))


if __name__ == "__main__":
    unittest.main()
