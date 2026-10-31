"""No-code Android browser return requires two independent, short-lived proofs."""
import hashlib
import html
import http.client
import json
import re
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

import app
from google_signin import (FLOW_TTL, GoogleSignInError, GoogleSignInService,
                           NATIVE_CALLBACK, NATIVE_HANDOFF)


NOW = 1_900_000_000.0


class FakeProvider:
    ready = True
    origin = "https://aliencolonies.com"
    subject = "native_google_subject"
    error = None
    def authorization_url(self, flow):
        return "https://accounts.google.com/o/oauth2/v2/auth?state=" + flow["state"]
    def exchange(self, code, flow):
        if self.error:
            raise self.error
        return self.subject


class NativeHandoffScenarios(unittest.TestCase):
    def setUp(self):
        self.world = app.World(":memory:", now=NOW)
        self.provider = FakeProvider()
        self.clock = 100.0
        self.service = GoogleSignInService(self.world, self.provider, clock=lambda: self.clock)
    def tearDown(self):
        self.world.close()
    def begin(self):
        start = self.service.start(client="android", handoff=NATIVE_HANDOFF)
        query = parse_qs(urlsplit(start["authorization_url"]).query)
        location, cookie = self.service.open(start["flow_id"], query["open"][0])
        state = parse_qs(urlsplit(location).query)["state"][0]
        return start, state, cookie
    def verified(self, *, error=None):
        start, state, cookie = self.begin()
        self.service.callback(state, cookie, code="test_provider_code", error=error)
        location = self.service.browser_handoff(state, cookie)
        query = parse_qs(urlsplit(location).query)
        self.assertEqual(query["flow_id"], [start["flow_id"]])
        return start, query["handoff_ticket"][0], location
    def status(self, start, ticket=None):
        return self.service.status(start["flow_id"], start["poll_secret"], handoff_ticket=ticket)
    def complete(self, start, name="No Code Empire"):
        return self.service.complete(start["flow_id"], start["poll_secret"], name)

    def test_new_android_start_opens_google_directly_without_a_manual_code(self):
        start, state, cookie = self.begin()
        self.assertNotIn("verification_code", start)
        self.assertEqual(start["handoff"], NATIVE_HANDOFF)
        flow = self.service.flows[start["flow_id"]]
        self.assertIsNone(flow["code_hash"])
        self.assertTrue(flow["confirmed"])
        self.assertEqual(self.status(start), {"ok": True, "status": "pending"})
        with self.assertRaises(GoogleSignInError):
            self.service.confirmation_document(start["flow_id"])
        with self.assertRaises(GoogleSignInError):
            self.service.confirm(start["flow_id"], cookie, flow["confirm_csrf"], "123456")

    def test_no_silent_protocol_fallback_for_invalid_handoff_or_web(self):
        for client, handoff in (("web", NATIVE_HANDOFF), ("android", "unknown"), ("android", [])):
            with self.subTest(client=client, handoff=handoff), self.assertRaises(GoogleSignInError):
                self.service.start(client=client, handoff=handoff, browser_cookie="C" * 43)

    def test_forwarded_browser_url_cannot_be_claimed_with_poll_proof_alone(self):
        start, ticket, location = self.verified()
        self.assertTrue(location.startswith(NATIVE_CALLBACK + "?"))
        self.assertNotIn(start["poll_secret"], location)
        self.assertNotIn(self.provider.subject, location)
        self.assertNotIn(ticket, json.dumps(self.service.flows))
        self.assertNotIn(ticket, json.dumps(self.status(start)))
        self.assertEqual(self.status(start), {"ok": True, "status": "pending"})
        with self.assertRaises(GoogleSignInError) as error:
            self.complete(start)
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(len(self.world.data["players"]), 0)
        self.assertEqual(self.status(start, ticket), {"ok": True, "status": "needs_name"})
        result = self.complete(start)
        self.assertEqual(self.world.authenticate(result["token"]), result["state"]["player"]["id"])

    def test_ticket_alone_and_invalid_poll_cannot_consume_valid_handoff(self):
        start, ticket, _ = self.verified()
        for poll in (None, "wrong", "P" * 43):
            with self.subTest(poll=poll), self.assertRaises(GoogleSignInError):
                self.service.status(start["flow_id"], poll, handoff_ticket=ticket)
        self.assertFalse(self.service.flows[start["flow_id"]]["handoff_received"])
        self.assertEqual(self.status(start, ticket)["status"], "needs_name")

    def test_invalid_ticket_is_retryable_and_success_latches_for_poll_retries(self):
        start, ticket, _ = self.verified()
        for wrong in (None, "", "wrong", "T" * 43, [ticket], {"value": ticket}):
            with self.subTest(ticket=wrong):
                self.assertEqual(self.status(start, wrong)["status"], "pending")
        self.assertEqual(self.status(start, ticket)["status"], "needs_name")
        self.assertIsNone(self.service.flows[start["flow_id"]]["handoff_hash"])
        self.assertEqual(self.status(start)["status"], "needs_name")
        self.assertEqual(self.status(start, ticket)["status"], "needs_name")
        self.complete(start)
        with self.assertRaises(GoogleSignInError):
            self.status(start, ticket)
        with self.assertRaises(GoogleSignInError):
            self.complete(start)

    def test_ticket_is_specific_to_its_flow_and_expires_with_it(self):
        first, ticket_a, _ = self.verified()
        second, ticket_b, _ = self.verified()
        self.assertEqual(self.status(first, ticket_b)["status"], "pending")
        self.assertEqual(self.status(second, ticket_a)["status"], "pending")
        self.clock += FLOW_TTL
        for start, ticket in ((first, ticket_a), (second, ticket_b)):
            with self.assertRaises(GoogleSignInError):
                self.status(start, ticket)
        self.assertEqual(len(self.world.data["players"]), 0)

    def test_browser_handoff_requires_oauth_success_or_bound_error_and_original_cookie(self):
        start, state, cookie = self.begin()
        with self.assertRaises(GoogleSignInError):
            self.service.browser_handoff(state, cookie)
        self.service.callback(state, cookie, code="test_code")
        for wrong in (None, "X" * 43):
            with self.assertRaises(GoogleSignInError):
                self.service.browser_handoff(state, wrong)
        location = self.service.browser_handoff(state, cookie)
        ticket = parse_qs(urlsplit(location).query)["handoff_ticket"][0]
        self.assertEqual(self.status(start, ticket)["status"], "needs_name")
        with self.assertRaises(GoogleSignInError):
            self.service.browser_handoff(state, cookie)

    def test_browser_ticket_cannot_be_issued_twice_even_before_app_claim(self):
        start, state, cookie = self.begin()
        self.service.callback(state, cookie, code="test_code")
        self.service.browser_handoff(state, cookie)
        with self.assertRaises(GoogleSignInError):
            self.service.browser_handoff(state, cookie)

    def test_cancel_and_provider_failure_return_to_app_without_creating_account(self):
        for canceled in (False, True):
            self.provider.error = GoogleSignInError("Provider test failure", 401)
            start, ticket, _ = self.verified(error="access_denied" if canceled else None)
            self.assertEqual(self.status(start)["status"], "pending")
            self.assertEqual(self.status(start, ticket)["status"], "error")
            with self.assertRaises(GoogleSignInError):
                self.complete(start)
        self.assertEqual(len(self.world.data["players"]), 0)

    def test_link_cannot_be_completed_until_original_app_receives_handoff(self):
        self.world.require_google_registration = False
        old = self.world.register("Legacy Empire", "legacy-password-123")
        start = self.service.start(mode="link", client="android", handoff=NATIVE_HANDOFF,
                                   player_id=old["state"]["player"]["id"],
                                   session_hash=hashlib.sha256(old["token"].encode()).hexdigest())
        query = parse_qs(urlsplit(start["authorization_url"]).query)
        location, cookie = self.service.open(start["flow_id"], query["open"][0])
        state = parse_qs(urlsplit(location).query)["state"][0]
        self.service.callback(state, cookie, code="test_code")
        with self.assertRaises(GoogleSignInError):
            self.complete(start)
        ticket = parse_qs(urlsplit(self.service.browser_handoff(state, cookie)).query)["handoff_ticket"][0]
        self.assertEqual(self.status(start, ticket)["status"], "ready")
        linked = self.complete(start)
        self.assertEqual(linked["state"]["player"]["id"], old["state"]["player"]["id"])
        self.assertTrue(linked["state"]["account"]["google_linked"])


class NativeHandoffHTTPScenarios(unittest.TestCase):
    def setUp(self):
        self.world = app.World(":memory:", now=NOW)
        self.server = app.build_server(self.world, port=0)
        self.server.google_signin = GoogleSignInService(self.world, FakeProvider())
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
    def tearDown(self):
        self.server.shutdown()
        self.worker.join(3)
        self.server.server_close()
        self.world.close()
    def request(self, path, data=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        headers = {"X-PGR-Client-Version": "57", "Content-Type": "application/json", **(headers or {})}
        conn.request("POST" if data is not None else "GET", path,
                     body=json.dumps(data).encode() if data is not None else None, headers=headers)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result
    def test_end_to_end_native_api_requires_callback_ticket_and_keeps_web_page_private(self):
        status, _, raw = self.request("/api/auth/google/start", {"mode": "login", "client": "android", "handoff": NATIVE_HANDOFF})
        self.assertEqual(status, 200)
        flow = json.loads(raw)
        self.assertNotIn("verification_code", flow)
        open_url = urlsplit(flow["authorization_url"])
        status, headers, raw = self.request(open_url.path + "?" + open_url.query, headers={"X-PGR-Client-Version": ""})
        self.assertEqual(status, 302)
        self.assertTrue(headers["Location"].startswith("https://accounts.google.com/"))
        state = parse_qs(urlsplit(headers["Location"]).query)["state"][0]
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, headers, raw = self.request("/api/auth/google/callback?state=" + state + "&code=test_code",
                                            headers={"Cookie": cookie, "X-PGR-Client-Version": ""})
        self.assertEqual(status, 200)
        page = raw.decode()
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertNotIn(flow["poll_secret"], page)
        self.assertNotIn("test_code", page)
        self.assertNotIn(FakeProvider.subject, page)
        nonce = re.search(r"<script nonce='([^']+)'", page).group(1)
        self.assertIn("script-src 'nonce-" + nonce + "'", headers["Content-Security-Policy"])
        self.assertIn("window.location.replace(", page)
        native_url = html.unescape(re.search(r"<a href='([^']+)'", page).group(1))
        parsed = urlsplit(native_url)
        self.assertEqual(parsed.scheme, "com.conradmafer.aliencolonies")
        self.assertEqual(parsed.netloc, "google-auth")
        values = parse_qs(parsed.query)
        self.assertEqual(set(values), {"flow_id", "handoff_ticket"})
        body = {"flow_id": flow["flow_id"], "poll_secret": flow["poll_secret"]}
        status, _, raw = self.request("/api/auth/google/status", body)
        self.assertEqual(json.loads(raw), {"ok": True, "status": "pending"})
        status, _, _ = self.request("/api/auth/google/complete", {**body, "name": "Native HTTP"})
        self.assertEqual(status, 409)
        status, _, raw = self.request("/api/auth/google/status", {**body, "handoff_ticket": values["handoff_ticket"][0]})
        self.assertEqual(json.loads(raw), {"ok": True, "status": "needs_name"})
        status, _, raw = self.request("/api/auth/google/complete", {**body, "name": "Native HTTP"})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(raw)["state"]["account"]["google_linked"])


if __name__ == "__main__":
    unittest.main()
