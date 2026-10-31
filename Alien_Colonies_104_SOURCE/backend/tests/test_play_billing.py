"""Provider-isolated purchase tests; no credentials, live payments, or egress."""
import copy
from datetime import datetime, timezone
import json
import os
import unittest
from unittest.mock import patch

from play_billing import BillingError, BillingVerifier, GooglePlayProvider, PACKAGE_NAME, account_id, token_hash


NOW = 1_800_000_000.0


def stamp(instant):
    return datetime.fromtimestamp(instant, timezone.utc).isoformat().replace("+00:00", "Z")


def purchase(player="u_one", state="SUBSCRIPTION_STATE_ACTIVE", expiry=NOW + 3600, acknowledgement="ACKNOWLEDGEMENT_STATE_PENDING"):
    return {"startTime": stamp(NOW - 3600), "subscriptionState": state,
            "acknowledgementState": acknowledgement,
            "externalAccountIdentifiers": {"obfuscatedExternalAccountId": account_id(player)},
            "lineItems": [{"productId": "queue_planner", "expiryTime": stamp(expiry),
                           "offerDetails": {"basePlanId": "monthly"}, "autoRenewingPlan": {"autoRenewEnabled": True}}]}


class FakeProvider:
    ready = True
    package_name = PACKAGE_NAME
    def __init__(self, response):
        self.response, self.acknowledged, self.calls = response, [], 0
        self.error, self.ack_error = None, None
    def get_subscription(self, token):
        self.calls += 1
        if self.error:
            raise self.error
        return copy.deepcopy(self.response)
    def acknowledge(self, token):
        if self.ack_error:
            raise self.ack_error
        self.acknowledged.append(token)


class BillingTests(unittest.TestCase):
    def setUp(self):
        self.now = NOW
        self.player = {"id": "u_one"}
        self.players = {"u_one": self.player, "u_two": {"id": "u_two"}}
        self.provider = FakeProvider(purchase())
        self.verifier = BillingVerifier(self.provider, clock=lambda: self.now)
    def verify(self, token="secret_purchase_token"):
        return self.verifier.verify_purchase(self.player, token, self.players)
    def assert_rejected(self, code):
        with self.assertRaises(BillingError) as caught:
            self.verify()
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn("secret_purchase_token", str(caught.exception))
        self.assertNotIn("subscription", self.player)
        self.assertEqual(self.provider.acknowledged, [])
    def test_active_is_verified_acknowledged_and_public_response_is_safe(self):
        public = self.verify()
        self.assertTrue(public["queue_planning_active"])
        self.assertEqual(public["expires_at"], NOW + 3600)
        self.assertEqual(public["starts_at"], NOW)
        self.assertEqual(public["billing_account_id"], account_id("u_one"))
        self.assertEqual(self.provider.acknowledged, ["secret_purchase_token"])
        serialized = json.dumps(public)
        self.assertNotIn("secret_purchase_token", serialized)
        self.assertNotIn(token_hash("secret_purchase_token"), serialized)
        self.assertEqual(self.player["subscription"]["_play_token"], "secret_purchase_token")
    def test_wrong_product_and_plan_do_not_grant_or_acknowledge(self):
        for field, value in (("productId", "different_product"), ("plan", "yearly")):
            with self.subTest(field=field):
                self.setUp()
                if field == "plan":
                    self.provider.response["lineItems"][0]["offerDetails"]["basePlanId"] = value
                else:
                    self.provider.response["lineItems"][0][field] = value
                self.assert_rejected("wrong_product")
    def test_wrong_package_is_rejected(self):
        self.provider.response["packageName"] = "com.example.somewhere"
        self.assert_rejected("wrong_package")
    def test_wrong_or_missing_account_is_rejected(self):
        for identifiers in ({}, {"obfuscatedExternalAccountId": account_id("u_two")}):
            with self.subTest(identifiers=identifiers):
                self.setUp()
                self.provider.response["externalAccountIdentifiers"] = identifiers
                self.assert_rejected("wrong_account")
    def test_out_of_app_resubscribe_retains_verified_account(self):
        self.provider.response.pop("externalAccountIdentifiers")
        self.provider.response["outOfAppPurchaseContext"] = {"expiredExternalAccountIdentifiers": {"obfuscatedExternalAccountId": account_id("u_one")}}
        self.assertTrue(self.verify()["queue_planning_active"])
    def test_pending_is_never_acknowledged(self):
        self.provider.response = purchase(state="SUBSCRIPTION_STATE_PENDING")
        self.assert_rejected("purchase_pending")
    def test_pause_hold_expired_unspecified_and_pending_canceled_do_not_grant(self):
        for state in ("SUBSCRIPTION_STATE_PAUSED", "SUBSCRIPTION_STATE_ON_HOLD", "SUBSCRIPTION_STATE_EXPIRED", "SUBSCRIPTION_STATE_UNSPECIFIED"):
            with self.subTest(state=state):
                self.setUp()
                self.provider.response = purchase(state=state)
                self.assertFalse(self.verify()["queue_planning_active"])
                self.assertEqual(self.provider.acknowledged, [])
    def test_cancel_preserves_remaining_paid_period_and_grace_is_entitled(self):
        for state in ("SUBSCRIPTION_STATE_CANCELED", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"):
            with self.subTest(state=state):
                self.setUp()
                self.provider.response = purchase(state=state)
                self.assertTrue(self.verify()["queue_planning_active"])
                self.now = NOW + 3600
                self.assertFalse(self.verifier.public_entitlement(self.player)["queue_planning_active"])
    def test_expired_date_future_start_and_malformed_dates_do_not_grant(self):
        self.provider.response = purchase(expiry=NOW)
        self.assertFalse(self.verify()["queue_planning_active"])
        self.setUp()
        self.provider.response["startTime"] = stamp(NOW + 1)
        self.assertFalse(self.verify()["queue_planning_active"])
        for invalid in ("2099-01-01", "invalid", "NaN", None):
            with self.subTest(invalid=invalid):
                self.setUp()
                self.provider.response["lineItems"][0]["expiryTime"] = invalid
                self.assert_rejected("invalid_provider_response")
    def test_acknowledgement_failure_does_not_save_entitlement(self):
        self.provider.ack_error = BillingError("billing_temporarily_unavailable", "Try later", 503)
        self.assert_rejected("billing_temporarily_unavailable")
    def test_already_acknowledged_restore_is_idempotent(self):
        self.provider.response["acknowledgementState"] = "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"
        self.verify()
        self.now += 100
        self.verify()
        self.assertEqual(self.provider.acknowledged, [])
        self.assertEqual(len(self.player["subscription"]["periods"]), 1)
        self.assertEqual(self.player["subscription"]["starts_at"], NOW)
    def test_token_and_linked_token_cannot_transfer_to_another_player(self):
        for linked in (False, True):
            with self.subTest(linked=linked):
                self.setUp()
                self.players["u_two"]["subscription"] = {"_play_token_hash": token_hash("owned-token"), "_play_token_history": [token_hash("owned-token")]}
                if linked:
                    self.provider.response["linkedPurchaseToken"] = "owned-token"
                with self.assertRaises(BillingError) as caught:
                    self.verify("new-token" if linked else "owned-token")
                self.assertEqual(caught.exception.code, "token_already_used")
                self.assertNotIn("subscription", self.player)
    def test_replaced_token_cannot_overwrite_current_subscription(self):
        self.verify("old-token")
        self.now += 100
        self.provider.response["linkedPurchaseToken"] = "old-token"
        self.verify("new-token")
        self.provider.response.pop("linkedPurchaseToken")
        with self.assertRaises(BillingError) as caught:
            self.verify("old-token")
        self.assertEqual(caught.exception.code, "subscription_replaced")
        self.assertEqual(self.player["subscription"]["_play_token"], "new-token")
    def test_renewal_before_expiry_extends_continuously_but_recovery_after_gap_starts_now(self):
        self.verify()
        self.now += 500
        self.provider.response["lineItems"][0]["expiryTime"] = stamp(NOW + 7200)
        self.verify()
        self.assertEqual(self.player["subscription"]["starts_at"], NOW)
        self.now = NOW + 9000
        self.provider.response["lineItems"][0]["expiryTime"] = stamp(NOW + 12000)
        self.verify()
        self.assertEqual(self.player["subscription"]["starts_at"], self.now)
        self.assertEqual(len(self.player["subscription"]["periods"]), 2)
        self.assertEqual(self.player["subscription"]["periods"][0]["expires_at"], NOW + 7200)
    def test_hold_truncates_future_interval_and_preserves_paid_history(self):
        self.verify()
        self.now += 500
        self.provider.response["subscriptionState"] = "SUBSCRIPTION_STATE_ON_HOLD"
        self.verify()
        sub = self.player["subscription"]
        self.assertFalse(sub["enable_queue_planning"])
        self.assertEqual(sub["periods"], [{"starts_at": NOW, "expires_at": self.now}])
    def test_refresh_is_bounded_and_outage_never_extends_known_expiry(self):
        self.verify()
        self.assertFalse(self.verifier.refresh_player(self.player, self.players))
        self.assertEqual(self.provider.calls, 1)
        self.now += 301
        self.provider.error = BillingError("billing_temporarily_unavailable", "Try later", 503)
        self.assertFalse(self.verifier.refresh_player(self.player, self.players))
        self.assertTrue(self.verifier.public_entitlement(self.player)["queue_planning_active"])
        self.assertFalse(self.verifier.is_refresh_due(self.player))
        self.now = NOW + 3601
        self.assertFalse(self.verifier.public_entitlement(self.player)["queue_planning_active"])
        self.assertEqual(self.player["subscription"]["expires_at"], NOW + 3600)
    def test_terminal_provider_rejection_stops_future_access(self):
        self.verify()
        self.now += 301
        self.provider.error = BillingError("purchase_not_found", "Not found")
        self.assertTrue(self.verifier.refresh_player(self.player, self.players))
        self.assertFalse(self.verifier.public_entitlement(self.player)["queue_planning_active"])
    def test_stale_terminal_error_cannot_invalidate_newer_success(self):
        self.verify()
        self.now += 10
        check_started = self.now
        self.now += 10
        self.verify()
        self.assertFalse(self.verifier.invalidate_player(self.player, checked_started=check_started))
        self.assertTrue(self.verifier.public_entitlement(self.player)["queue_planning_active"])
    def test_disabled_provider_and_bad_environment_fail_closed_without_crashing(self):
        for env in ({}, {"ALIEN_PLAY_SERVICE_ACCOUNT_JSON": "not-json"}, {"GOOGLE_APPLICATION_CREDENTIALS": "/no/such/path"}):
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
                provider = GooglePlayProvider.from_env()
                self.assertFalse(provider.ready)
                verifier = BillingVerifier(provider, clock=lambda: NOW)
                with self.assertRaises(BillingError) as caught:
                    verifier.verify_purchase(self.player, "token", self.players)
                self.assertEqual(caught.exception.code, "billing_unavailable")
    def test_check_phase_does_not_mutate_until_applied_under_world_lock(self):
        verified = self.verifier.check_purchase(self.player["id"], "token")
        self.assertNotIn("subscription", self.player)
        public = self.verifier.apply_purchase(self.player, verified, self.players)
        self.assertTrue(public["queue_planning_active"])
        self.assertNotIn("token", repr(verified))
    def test_stale_verification_cannot_overwrite_newer_renewal(self):
        stale = self.verifier.check_purchase(self.player["id"], "token")
        self.now += 100
        self.provider.response["lineItems"][0]["expiryTime"] = stamp(NOW + 7200)
        self.verify("token")
        with self.assertRaises(BillingError) as caught:
            self.verifier.apply_purchase(self.player, stale, self.players)
        self.assertEqual(caught.exception.code, "stale_verification")
        self.assertEqual(self.player["subscription"]["expires_at"], NOW + 7200)
    def test_slow_old_active_response_cannot_overwrite_newer_refund_check(self):
        self.verify("token")
        self.now += 10
        old_response = purchase(acknowledgement="ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED")
        original_get = self.provider.get_subscription
        def slow_response(token):
            self.provider.get_subscription = original_get
            self.now += 10
            self.provider.response = purchase(state="SUBSCRIPTION_STATE_EXPIRED", expiry=self.now)
            self.verify(token)
            return old_response
        self.provider.get_subscription = slow_response
        stale = self.verifier.check_purchase(self.player["id"], "token")
        with self.assertRaises(BillingError) as caught:
            self.verifier.apply_purchase(self.player, stale, self.players)
        self.assertEqual(caught.exception.code, "stale_verification")
        self.assertFalse(self.verifier.public_entitlement(self.player)["queue_planning_active"])
    def test_invalid_token_is_rejected_before_network(self):
        for token in ("", None, "token\nsecret", "x" * 4097):
            with self.subTest(token=token):
                with self.assertRaises(BillingError) as caught:
                    self.verify(token)
                self.assertEqual(caught.exception.code, "invalid_token")
        self.assertEqual(self.provider.calls, 0)


if __name__ == "__main__":
    unittest.main()
