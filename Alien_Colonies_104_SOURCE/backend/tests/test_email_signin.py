"""Offline passwordless email lifecycle/provider/HTTP integration tests."""
import http.client
import json
from pathlib import Path
import re
import secrets
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import email_signin as email


class FakeProvider:
    ready = True
    origin = "https://aliencolonies.com"

    def __init__(self):
        self.messages = []
        self.fail = False
        self.during_send = None

    def send(self, address, link, *, request_id):
        if self.during_send:
            self.during_send()
        if self.fail:
            raise RuntimeError("private-provider-error-with-link-" + link)
        self.messages.append((address, link, request_id))


class EmailSignInTests(unittest.TestCase):
    def setUp(self):
        self.world = app.World(":memory:")
        self.provider = FakeProvider()
        self.now = 1000.0
        self.service = email.EmailSignInService(self.world, self.provider, clock=lambda: self.now)
        self.cookie = secrets.token_urlsafe(32)

    def tearDown(self):
        self.world.close()

    def start(self, address="pilot@example.com", native=False):
        result = self.service.start(address, client="android" if native else "web",
                                    handoff=email.NATIVE_HANDOFF if native else None,
                                    browser_cookie=None if native else self.cookie, ip="fixture-ip")
        query = parse_qs(urlsplit(self.provider.messages[-1][1]).query)
        return result, query["token"][0]

    def confirm(self, result, token, native=False):
        document, browser_cookie = self.service.open(result["flow_id"], token, None if native else self.cookie)
        csrf = re.search(r'name="csrf" value="([^"]+)"', document)[1]
        callback = self.service.confirm(result["flow_id"], browser_cookie, csrf)
        return parse_qs(urlsplit(callback).query)["handoff_ticket"][0] if callback else None

    def proof(self, result, ticket=None):
        return {"flow_id": result["flow_id"], "poll_secret": result["poll_secret"],
                "browser_cookie": self.cookie, "handoff_ticket": ticket}

    def test_web_verified_signup_and_later_login_keep_same_empire(self):
        flow, token = self.start()
        self.assertEqual(self.world.data["players"], {})
        self.assertEqual(self.service.status(**self.proof(flow))["status"], "pending")
        self.confirm(flow, token)
        self.assertEqual(self.service.status(**self.proof(flow))["status"], "needs_name")
        self.assertEqual(self.world.data["players"], {})
        with self.assertRaises(app.GameError):
            self.service.complete(**self.proof(flow))
        self.assertEqual(self.world.data["players"], {})
        result = self.service.complete(**self.proof(flow), name="Email Pilot")
        player = result["state"]["player"]["id"]
        self.assertTrue(result["state"]["account"]["email_linked"])
        self.assertFalse(result["state"]["account"]["password_login_enabled"])
        self.assertFalse(result["state"]["account"].get("google_linked", False))
        self.assertEqual(sum(result["state"]["ships"].values()), 0)
        self.now += 61
        new_flow, new_token = self.start("PILOT@EXAMPLE.COM")
        self.confirm(new_flow, new_token)
        self.assertEqual(self.service.status(**self.proof(new_flow))["status"], "ready")
        again = self.service.complete(**self.proof(new_flow))
        self.assertEqual(again["state"]["player"]["id"], player)
        self.assertEqual(len(self.world.data["players"]), 1)
        self.assertNotEqual(again["token"], result["token"])

    def test_native_requires_mailbox_handoff_and_poll_secret_every_time(self):
        flow, token = self.start(native=True)
        ticket = self.confirm(flow, token, native=True)
        self.assertEqual(self.service.status(**self.proof(flow))["status"], "pending")
        with self.assertRaises(email.EmailSignInError):
            self.service.complete(**self.proof(flow), name="Native Pilot")
        self.assertEqual(self.service.status(**self.proof(flow, ticket))["status"], "needs_name")
        with self.assertRaises(email.EmailSignInError):
            self.service.complete(**self.proof(flow), name="Native Pilot")
        result = self.service.complete(**self.proof(flow, ticket), name="Native Pilot")
        self.assertTrue(result["ok"])
        with self.assertRaises(email.EmailSignInError):
            self.service.complete(**self.proof(flow, ticket), name="Native Pilot")

    def test_email_does_not_claim_existing_google_empire_by_name(self):
        google = self.world.google_complete("fixture-google-subject", "Protected Empire")
        flow, token = self.start()
        self.confirm(flow, token)
        with self.assertRaises(app.GameError):
            self.service.complete(**self.proof(flow), name="Protected Empire")
        self.assertEqual(len(self.world.data["players"]), 1)
        self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM email_accounts").fetchone()[0], 0)
        created = self.service.complete(**self.proof(flow), name="Separate Empire")
        self.assertNotEqual(created["state"]["player"]["id"], google["state"]["player"]["id"])

    def test_mail_scanner_get_does_not_consume_or_create_account(self):
        flow, token = self.start(native=True)
        first_doc, _ = self.service.open(flow["flow_id"], token)
        second_doc, _ = self.service.open(flow["flow_id"], token)
        self.assertNotEqual(first_doc, second_doc)
        self.assertEqual(self.service.flows[flow["flow_id"]]["status"], "pending")
        self.assertFalse(self.world.data["players"])
        self.confirm(flow, token, native=True)
        with self.assertRaises(email.EmailSignInError):
            self.service.open(flow["flow_id"], token)

    def test_rate_limited_address_response_does_not_reveal_account(self):
        first, _ = self.start()
        second = self.service.start("PILOT@EXAMPLE.COM", browser_cookie=self.cookie, ip="fixture-ip")
        self.assertEqual(len(self.provider.messages), 1)
        self.assertEqual(set(first), set(second))
        self.assertEqual(first["message"], second["message"])
        self.assertEqual(self.service.status(**self.proof(second))["status"], "pending")
        self.now += 61
        self.start()
        self.assertEqual(len(self.provider.messages), 2)

    def test_delivery_runs_outside_world_and_service_locks(self):
        acquired = []
        def during_send():
            def check():
                for lock in (self.world.lock, self.service.lock):
                    got = lock.acquire(timeout=.3)
                    acquired.append(got)
                    if got:
                        lock.release()
            thread = threading.Thread(target=check)
            thread.start()
            thread.join(1)
        self.provider.during_send = during_send
        self.start()
        self.assertEqual(acquired, [True, True])

    def test_delivery_failure_has_no_private_provider_data(self):
        self.provider.fail = True
        with self.assertRaises(email.EmailSignInError) as caught:
            self.start()
        self.assertEqual(caught.exception.status, 503)
        self.assertNotIn("private-provider", caught.exception.message)
        self.assertNotIn("token=", caught.exception.message)
        self.assertFalse(self.service.flows)
        self.assertFalse(self.world.data["players"])

    def test_disabled_provider_and_bad_address_fail_without_sending(self):
        self.assertFalse(email.ResendEmailProvider().ready)
        self.assertFalse(email.ResendEmailProvider("fixture-key", "Sender <bad>").ready)
        self.assertFalse(email.ResendEmailProvider("fixture-key", "pilot@example.com", "http://example.com").ready)
        self.assertEqual(email.normalize_email(" PILOT+second@Example.COM "), "pilot+second@example.com")
        self.assertNotEqual(email.email_key("pilot+second@example.com"), email.email_key("pilot@example.com"))
        for value in ("bad", "a..b@example.com", "a@-bad.example", "a@example.com\r\nBcc:x@example.com", [], None):
            with self.subTest(value=value):
                with self.assertRaises(email.EmailSignInError):
                    self.service.start(value, browser_cookie=self.cookie)
        self.assertFalse(self.provider.messages)

    def test_recent_email_proof_supports_deletion_and_logout_others(self):
        result = self.world.email_complete("pilot@example.com", "Email Pilot")
        old_token = result["token"]
        fresh = self.world.email_complete("pilot@example.com")
        self.world.account_logout_others(fresh["token"], "")
        with self.assertRaises(app.GameError):
            self.world.authenticate(old_token)
        self.world.account_delete(fresh["token"], "", "DELETE ACCOUNT")
        self.assertFalse(self.world.data["players"])
        for table in ("email_accounts", "email_sessions"):
            self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0], 0)

    def test_resend_provider_uses_fixed_https_endpoint_no_redirects(self):
        provider = email.ResendEmailProvider("fixture-key-not-real", "Alien Colonies <login@example.com>")
        self.assertTrue(provider.ready)
        with patch.object(email, "build_opener") as factory:
            response = factory.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'{"id":"delivery-fixture"}'
            provider.send("pilot@example.com", "https://aliencolonies.com/api/auth/email/open?fixture=1", request_id="fixture")
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.resend.com/emails")
            self.assertEqual(factory.return_value.open.call_args.kwargs["timeout"], 8)
            payload = json.loads(request.data)
            self.assertEqual(payload["to"], ["pilot@example.com"])
            self.assertIn("expires in 15 minutes", payload["text"])
            self.assertIsInstance(factory.call_args.args[0], email._NoRedirects)


class EmailHttpTests(unittest.TestCase):
    def setUp(self):
        self.world = app.World(":memory:")
        self.server = app.build_server(self.world, "127.0.0.1", 0)
        self.provider = FakeProvider()
        self.server.email_signin = email.EmailSignInService(self.world, self.provider)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(2)
        self.server.server_close()
        self.world.close()

    def request(self, path, body=None, cookie=None, form=False, origin=True):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        headers = {"X-PGR-Client-Version": "65", "Accept-Language": "en"}
        if cookie:
            headers["Cookie"] = cookie
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
            if origin:
                headers["Origin"] = self.provider.origin
        encoded = (urlencode(body) if form else json.dumps(body)) if body is not None else None
        connection.request("GET" if body is None else "POST", path, encoded, headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode()
        connection.close()
        return result

    def test_config_start_confirmation_and_completion_http(self):
        code, _, body = self.request("/api/auth/email/config")
        self.assertEqual(code, 200)
        self.assertTrue(json.loads(body)["configured"])
        code, headers, body = self.request("/api/auth/email/start", {"email": "pilot@example.com", "client": "web"})
        self.assertEqual(code, 200)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        for flag in ("Secure", "HttpOnly", "SameSite=Lax", "Path=/"):
            self.assertIn(flag, headers["Set-Cookie"])
        flow = json.loads(body)
        link = urlsplit(self.provider.messages[-1][1])
        code, headers, document = self.request(link.path + "?" + link.query, cookie=cookie)
        self.assertEqual(code, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Referrer-Policy"], "strict-origin")
        self.assertNotIn("poll_secret", document)
        confirmation_cookie = headers["Set-Cookie"].split(";", 1)[0]
        csrf = re.search(r'name="csrf" value="([^"]+)"', document)[1]
        code, _, document = self.request("/api/auth/email/confirm", {"flow_id": flow["flow_id"], "csrf": csrf}, cookie=confirmation_cookie, form=True)
        self.assertEqual(code, 200)
        self.assertIn("original Alien Colonies tab", document)
        proof = {"flow_id": flow["flow_id"], "poll_secret": flow["poll_secret"]}
        code, _, body = self.request("/api/auth/email/status", proof, cookie=cookie)
        self.assertEqual(json.loads(body)["status"], "needs_name")
        code, _, body = self.request("/api/auth/email/complete", {**proof, "name": "HTTP Pilot"}, cookie=cookie)
        self.assertEqual(code, 200)
        self.assertTrue(json.loads(body)["state"]["account"]["email_linked"])
        code, _, _ = self.request("/api/auth/email/complete", proof, cookie=cookie)
        self.assertEqual(code, 410)


if __name__ == "__main__":
    unittest.main()
