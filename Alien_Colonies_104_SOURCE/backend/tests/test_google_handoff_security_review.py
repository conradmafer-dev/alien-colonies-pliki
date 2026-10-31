"""Independent edge regressions for the native browser-return trust boundary."""
import hashlib
import json
import unittest
from urllib.parse import parse_qs, urlsplit

import app
from google_signin import NATIVE_HANDOFF
from test_google_native_handoff import FakeProvider
import test_google_signin


class HandoffSecurityReview(unittest.TestCase):
    def setUp(self):
        self.http = test_google_signin.GoogleHTTPScenarios()
        self.http.setUp()
        self.world = self.http.world
        self.service = self.http.server.google_signin
        self.service.provider = FakeProvider()

    def tearDown(self):
        self.http.tearDown()

    def verified(self, *, client="android", handoff=NATIVE_HANDOFF, **kwargs):
        browser_cookie = "B" * 43 if client == "web" else None
        flow = self.service.start(client=client, handoff=handoff,
                                  browser_cookie=browser_cookie, **kwargs)
        opener = parse_qs(urlsplit(flow["authorization_url"]).query)["open"][0]
        location, cookie = self.service.open(flow["flow_id"], opener, browser_cookie)
        native = self.service.flows[flow["flow_id"]]
        if location is None:
            self.service.confirm(flow["flow_id"], cookie, native["confirm_csrf"], flow["verification_code"])
        self.service.callback(native["state"], cookie, code="review-code")
        return flow, native["state"], cookie

    def acknowledge(self, flow, state, cookie):
        location = self.service.browser_handoff(state, cookie)
        ticket = parse_qs(urlsplit(location).query)["handoff_ticket"][0]
        return self.service.status(flow["flow_id"], flow["poll_secret"], handoff_ticket=ticket)

    def test_payload_cannot_downgrade_already_started_native_flow_to_web_or_confirmed(self):
        flow, state, cookie = self.verified()
        location = self.service.browser_handoff(state, cookie)
        proof = {"flow_id": flow["flow_id"], "poll_secret": flow["poll_secret"]}
        # All of these are attacker-controlled request fields. The start-time
        # server record, not this payload, decides whether handoff is required.
        for override in ({"client": "web", "handoff": None},
                         {"handoff_received": True, "confirmed": True},
                         {"client": "android", "verification_code": "123456"}):
            with self.subTest(override=override):
                status, _, raw = self.http.request("/api/auth/google/status", {**proof, **override})
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(raw), {"ok": True, "status": "pending"})
                status, _, raw = self.http.request("/api/auth/google/complete", {**proof, **override, "name": "Hijacked Empire"})
                self.assertEqual(status, 409)
                self.assertNotIn(location, raw.decode())
        self.assertEqual(self.world.db.execute("SELECT count(*) FROM google_accounts").fetchone()[0], 0)

    def test_name_validation_can_retry_after_handoff_without_reopening_browser(self):
        flow, state, cookie = self.verified()
        self.assertEqual(self.acknowledge(flow, state, cookie)["status"], "needs_name")
        for name in ("", "Legacy HTTP"):
            with self.subTest(name=name), self.assertRaises(app.GameError):
                self.service.complete(flow["flow_id"], flow["poll_secret"], name)
            self.assertEqual(self.service.status(flow["flow_id"], flow["poll_secret"])["status"], "needs_name")
        result = self.service.complete(flow["flow_id"], flow["poll_secret"], "Retry Empire")
        self.assertEqual(result["state"]["player"]["name"], "Retry Empire")
        self.assertEqual(self.world.db.execute("SELECT count(*) FROM google_accounts").fetchone()[0], 1)

    def test_link_rechecks_original_session_even_after_valid_native_handoff(self):
        previous = self.world.login("Legacy HTTP", "legacy-password-123")
        player_id = previous["state"]["player"]["id"]
        session_hash = hashlib.sha256(previous["token"].encode()).hexdigest()
        flow, state, cookie = self.verified(mode="link", player_id=player_id, session_hash=session_hash)
        self.assertEqual(self.acknowledge(flow, state, cookie)["status"], "ready")
        with self.world.lock:
            self.world.db.execute("DELETE FROM sessions WHERE token_hash=?", (session_hash,))
            self.world.db.commit()
        with self.assertRaises(app.GameError) as error:
            self.service.complete(flow["flow_id"], flow["poll_secret"])
        self.assertEqual(error.exception.status, 401)
        self.assertEqual(self.world.db.execute("SELECT count(*) FROM google_accounts").fetchone()[0], 0)

    def test_legacy_callback_page_does_not_fail_if_polling_claims_session_first(self):
        # Browser callback and app polling run on separate HTTP threads. A
        # complete claim can win the race before callback HTML is rendered.
        for client in ("web", "android"):
            with self.subTest(client=client):
                self.service.provider.subject = "review_" + client
                flow, state, cookie = self.verified(client=client, handoff=None)
                result = self.service.complete(flow["flow_id"], flow["poll_secret"], "Legacy " + client)
                self.assertTrue(result["token"])
                self.assertIsNone(self.service.browser_handoff(state, cookie))


if __name__ == "__main__":
    unittest.main()
