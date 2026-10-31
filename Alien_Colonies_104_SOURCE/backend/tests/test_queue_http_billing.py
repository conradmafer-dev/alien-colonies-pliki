"""Receipt verification reauthenticates after I/O and never leaks private tokens."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World, build_server, UpdatePolicy
from play_billing import BillingVerifier, account_id


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


class BlockingProvider:
    ready = True
    package_name = "com.conradmafer.aliencolonies"

    def __init__(self):
        self.entered, self.release = threading.Event(), threading.Event()
        self.player_id = ""

    def get_subscription(self, token):
        self.entered.set()
        if not self.release.wait(5):
            raise RuntimeError("test provider timeout")
        now = time.time()
        return {"subscriptionState": "SUBSCRIPTION_STATE_ACTIVE", "startTime": timestamp(now - 60),
                "acknowledgementState": "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
                "externalAccountIdentifiers": {"obfuscatedExternalAccountId": account_id(self.player_id)},
                "lineItems": [{"productId": "queue_planner", "expiryTime": timestamp(now + 3600),
                               "offerDetails": {"basePlanId": "monthly"}}]}

    def acknowledge(self, token):
        raise AssertionError("already acknowledged receipt")


class BillingHTTPReauthentication(unittest.TestCase):
    def setUp(self):
        self.provider = BlockingProvider()
        self.world = World(":memory:", billing_verifier=BillingVerifier(self.provider))
        result = self.world.register("BillingHttp", "billing-http-local-password")
        self.pid, self.token = result["state"]["player"]["id"], result["token"]
        self.provider.player_id = self.pid
        self.server = build_server(self.world, port=0, update_policy=UpdatePolicy(min_version_code=1))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_address[1])
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.provider.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(3)
        self.world.close()

    def request(self, path, body=None):
        headers = {"Authorization": "Bearer " + self.token, "X-PGR-Client-Version": "51"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
        try:
            with urlopen(req, timeout=7) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_session_revoked_during_provider_verification_cannot_grant_subscription(self):
        response = []
        thread = threading.Thread(target=lambda: response.append(self.request("/api/action", {
            "type": "verify_subscription", "purchase_token": "local-test-receipt-" + "x" * 32})))
        thread.start()
        self.assertTrue(self.provider.entered.wait(2))
        self.world.logout(self.token)
        self.provider.release.set()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(response[0][0], 401)
        self.assertNotIn("subscription", self.world._player(self.pid))

    def test_public_verification_response_contains_no_private_receipt(self):
        self.provider.release.set()
        receipt = "local-test-receipt-" + "x" * 32
        status, response = self.request("/api/billing/verify", {"purchase_token": receipt})
        self.assertEqual(status, 200)
        premium = response["state"]["premium"]
        self.assertTrue(premium["queue_planning_active"])
        self.assertEqual(premium["billing_account_id"], account_id(self.pid))
        self.assertEqual(premium["obfuscated_account_id"], account_id(self.pid))
        self.assertEqual(premium["product_id"], "queue_planner")
        self.assertTrue(premium["configured"])
        raw = json.dumps(response)
        self.assertNotIn(receipt, raw)
        self.assertNotIn('"_play', raw)

    def test_offline_receipts_are_swept_without_state_polling(self):
        self.world._player(self.pid)["subscription"] = {"_play_token": "local-test-receipt-" + "x" * 32, "_verified_at": 0}
        with patch.object(self.server, "schedule_billing_refresh") as schedule:
            self.server.schedule_due_billing_refreshes()
            schedule.assert_called_once_with(self.pid)


if __name__ == "__main__":
    unittest.main()
