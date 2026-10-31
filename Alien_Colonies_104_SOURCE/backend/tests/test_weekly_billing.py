"""Weekly/trial entitlement regression tests using Google-shaped provider replies."""
import copy
import unittest

from play_billing import BillingError, BillingVerifier
from test_play_billing import FakeProvider, NOW, purchase, stamp


WEEK = 7 * 24 * 60 * 60


def weekly_purchase(*, offer_id=None, expiry=NOW + WEEK, state="SUBSCRIPTION_STATE_ACTIVE"):
    response = purchase(expiry=expiry, state=state)
    response["startTime"] = stamp(NOW)
    details = response["lineItems"][0]["offerDetails"]
    details["basePlanId"] = "weekly"
    if offer_id is not None:
        details["offerId"] = offer_id
    return response


class WeeklyBillingTests(unittest.TestCase):
    def setUp(self):
        self.now = NOW
        self.player = {"id": "u_one"}
        self.players = {"u_one": self.player}
        self.provider = FakeProvider(weekly_purchase())
        self.verifier = BillingVerifier(self.provider, clock=lambda: self.now)

    def verify(self, token="weekly-token"):
        return self.verifier.verify_purchase(self.player, token, self.players)

    def test_weekly_base_plan_without_trial_is_accepted(self):
        public = self.verify()
        self.assertTrue(public["queue_planning_active"])
        self.assertEqual(public["base_plan_id"], "weekly")
        self.assertEqual(public["expires_at"], NOW + WEEK)
        self.assertEqual(public["supported_base_plan_ids"], ["monthly", "weekly"])
        self.assertEqual(self.player["subscription"]["base_plan_id"], "weekly")
        self.assertEqual(self.provider.acknowledged, ["weekly-token"])

    def test_seven_day_trial_starts_from_google_and_stops_at_exact_expiry(self):
        self.provider.response = weekly_purchase(offer_id="trial-7d")
        public = self.verify()
        self.assertTrue(public["queue_planning_active"])
        self.assertEqual(public["starts_at"], NOW)
        self.assertEqual(public["expires_at"], NOW + WEEK)
        self.now = NOW + WEEK - 0.001
        self.assertTrue(self.verifier.public_entitlement(self.player)["queue_planning_active"])
        self.now = NOW + WEEK
        self.assertFalse(self.verifier.public_entitlement(self.player)["queue_planning_active"])
        self.assertEqual(self.player["subscription"]["expires_at"], NOW + WEEK)

    def test_trial_renews_weekly_continuously_only_after_google_confirms_extension(self):
        self.provider.response = weekly_purchase(offer_id="trial-7d")
        self.verify()
        self.now = NOW + WEEK
        self.assertFalse(self.verifier.public_entitlement(self.player)["queue_planning_active"])
        self.provider.response["acknowledgementState"] = "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"
        self.provider.response["lineItems"][0]["expiryTime"] = stamp(NOW + 2 * WEEK)
        public = self.verify()
        self.assertTrue(public["queue_planning_active"])
        self.assertEqual(public["base_plan_id"], "weekly")
        self.assertEqual(self.player["subscription"]["periods"], [{"starts_at": NOW, "expires_at": NOW + 2 * WEEK}])
        self.assertEqual(self.provider.acknowledged, ["weekly-token"])

    def test_canceled_trial_keeps_remaining_trial_then_expires(self):
        self.provider.response = weekly_purchase(offer_id="trial-7d")
        self.verify()
        self.now += 3600
        self.provider.response["subscriptionState"] = "SUBSCRIPTION_STATE_CANCELED"
        self.provider.response["acknowledgementState"] = "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"
        self.provider.response["lineItems"][0]["autoRenewingPlan"]["autoRenewEnabled"] = False
        self.assertTrue(self.verify()["queue_planning_active"])
        self.now = NOW + WEEK
        self.assertFalse(self.verifier.public_entitlement(self.player)["queue_planning_active"])
        self.assertFalse(self.verify()["queue_planning_active"])
        self.assertEqual(self.player["subscription"]["periods"], [{"starts_at": NOW, "expires_at": NOW + WEEK}])

    def test_weekly_late_recovery_does_not_backdate_unknown_gap(self):
        self.verify()
        self.now = NOW + WEEK + 600
        self.provider.response["lineItems"][0]["expiryTime"] = stamp(NOW + 2 * WEEK)
        self.verify()
        self.assertEqual(self.player["subscription"]["periods"], [
            {"starts_at": NOW, "expires_at": NOW + WEEK},
            {"starts_at": self.now, "expires_at": NOW + 2 * WEEK},
        ])

    def test_monthly_subscribers_remain_monthly_and_can_renew(self):
        self.provider.response = purchase(expiry=NOW + 30 * 86400)
        self.assertEqual(self.verify()["base_plan_id"], "monthly")
        self.now += 600
        self.provider.response["lineItems"][0]["expiryTime"] = stamp(NOW + 60 * 86400)
        public = self.verify()
        self.assertEqual(public["base_plan_id"], "monthly")
        self.assertEqual(self.player["subscription"]["base_plan_id"], "monthly")
        self.assertEqual(public["starts_at"], NOW)
        self.assertEqual(public["expires_at"], NOW + 60 * 86400)

    def test_unknown_missing_and_malformed_plan_rejected_without_acknowledgement(self):
        for plan in ("yearly", "weekly-unapproved", "", None, [], {"id": "weekly"}):
            with self.subTest(plan=plan):
                self.provider.response = weekly_purchase(offer_id="trial-7d")
                self.provider.response["lineItems"][0]["offerDetails"]["basePlanId"] = plan
                with self.assertRaises(BillingError) as caught:
                    self.verify()
                self.assertEqual(caught.exception.code, "wrong_product")
                self.assertNotIn("subscription", self.player)
                self.assertEqual(self.provider.acknowledged, [])

    def test_two_matching_supported_plans_are_rejected_as_ambiguous(self):
        second = copy.deepcopy(self.provider.response["lineItems"][0])
        second["offerDetails"]["basePlanId"] = "monthly"
        self.provider.response["lineItems"].append(second)
        with self.assertRaises(BillingError) as caught:
            self.verify()
        self.assertEqual(caught.exception.code, "wrong_product")
        self.assertNotIn("subscription", self.player)
        self.assertEqual(self.provider.acknowledged, [])

    def test_checked_snapshot_keeps_provider_plan_when_applied(self):
        verified = self.verifier.check_purchase(self.player["id"], "weekly-token")
        self.provider.response["lineItems"][0]["offerDetails"]["basePlanId"] = "monthly"
        public = self.verifier.apply_purchase(self.player, verified, self.players)
        self.assertEqual(verified.base_plan_id, "weekly")
        self.assertEqual(public["base_plan_id"], "weekly")

    def test_new_purchase_default_does_not_relabel_legacy_google_record(self):
        self.assertEqual(self.verifier.public_entitlement(self.player)["base_plan_id"], "weekly")
        self.player["subscription"] = {"_play_token": "old-token", "enable_queue_planning": True,
                                       "starts_at": NOW - 600, "expires_at": NOW + 600}
        public = self.verifier.public_entitlement(self.player)
        self.assertEqual(public["base_plan_id"], "monthly")
        self.assertTrue(public["queue_planning_active"])

    def test_supported_plans_does_not_claim_unconfigured_provider_is_ready(self):
        self.provider.ready = False
        public = self.verifier.public_entitlement(self.player)
        self.assertEqual(public["supported_base_plan_ids"], ["monthly", "weekly"])
        self.assertFalse(public["provider_ready"])
        with self.assertRaises(BillingError) as caught:
            self.verify()
        self.assertEqual(caught.exception.code, "billing_unavailable")


if __name__ == "__main__":
    unittest.main()
