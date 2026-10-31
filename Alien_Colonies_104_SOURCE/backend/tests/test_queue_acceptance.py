"""Independent acceptance checks for paid planning and unchanged free lanes."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World, GameError, RESOURCES, build_server
from play_billing import BillingVerifier, account_id

NOW = 1900000000.0
PASSWORD = "queue-acceptance-local-password"


class QueueAcceptance(unittest.TestCase):
    def setUp(self):
        self.w = World(":memory:", now=NOW)
        self.addCleanup(self.w.close)
        self.pid = self.w.register("QueueAcceptance", PASSWORD)["state"]["player"]["id"]
        self.w.action(self.pid, {"type": "choose_race", "race_id": "zetans"})
        self.p = self.w._owned(self.pid)
        self.player = self.w._player(self.pid)
        self.p["resources"] = dict.fromkeys(RESOURCES, 10000000.0)
        self.p["buildings"].update(lab=2, shipyard=2)
        self.w.data["alien"]["next_expansion_at"] = NOW + 10000000

    def grant(self, begin=NOW, end=NOW + 100000):
        self.player["subscription"] = {"enable_queue_planning": True, "starts_at": begin, "expires_at": end}

    def action(self, kind, key, **extra):
        return self.w.action(self.pid, {"type": kind, "key": key, **extra})

    def plan(self, kind, key, **extra):
        return self.w.action(self.pid, {"type": "plan_project", "kind": kind, "key": key, **extra})

    def second(self):
        p = next(p for p in self.w.data["planets"].values() if p["owner_type"] == "empty")
        p.update(owner_type="player", owner_id=self.pid)
        p["resources"] = dict.fromkeys(RESOURCES, 10000000.0)
        p["buildings"].update(lab=2, shipyard=2)
        return p

    def stock_without_production(self):
        self.w.production = lambda planet, **kwargs: dict.fromkeys(RESOURCES, 0.0)

    def test_no_subscription_cannot_plan_even_with_client_paid_flags(self):
        before = copy.deepcopy(self.w.data)
        with self.assertRaises(GameError) as error:
            self.plan("build", "metal_mine", paid=True, subscription={"enable_queue_planning": True})
        self.assertEqual(error.exception.status, 403)
        self.assertEqual(self.w.data, before)

    def test_free_accounts_keep_three_parallel_active_lanes(self):
        for kind, key in (("build", "metal_mine"), ("research", "weapons"), ("ship", "scout")):
            self.action(kind, key)
        self.assertEqual({q["kind"] for q in self.p["queue"]}, {"build", "research", "ship"})
        for kind, key in (("build", "crystal_mine"), ("research", "propulsion"), ("ship", "frigate")):
            with self.assertRaises(GameError):
                self.action(kind, key)

    def test_no_subscription_activation_via_unknown_action(self):
        before = copy.deepcopy(self.w.data)
        with self.assertRaises(GameError):
            self.w.action(self.pid, {"type": "set_subscription", "enable_queue_planning": True, "expires_at": NOW + 99999})
        self.assertEqual(self.w.data, before)

    def test_ten_pending_building_limit_excludes_active(self):
        self.grant()
        self.action("build", "power_plant")
        for i in range(10):
            self.plan("build", "metal_mine")
        self.assertEqual(len(self.player["planned_orders"]), 10)
        before = copy.deepcopy(self.w.data)
        with self.assertRaises(GameError):
            self.plan("build", "crystal_mine")
        self.assertEqual(self.w.data, before)
        self.assertEqual(len(self.p["queue"]), 1)

    def test_ten_pending_research_limit_applies_across_colonies(self):
        self.grant()
        second = self.second()
        self.action("research", "weapons")
        for i in range(10):
            self.plan("research", "propulsion", planet_id=second["id"] if i % 2 else self.p["id"])
        self.assertEqual(len(self.player["planned_orders"]), 10)
        with self.assertRaises(GameError):
            self.plan("research", "weapons", planet_id=second["id"])

    def test_ship_and_defense_share_pending_and_active_lane(self):
        self.grant()
        self.action("ship", "scout")
        for i in range(10):
            self.plan("defense", "phase_sentinel")
        with self.assertRaises(GameError):
            self.plan("ship", "scout")
        self.assertEqual(len(self.p["queue"]), 1)

    def test_ship_amounts_are_strictly_bounded_and_cannot_be_booleans(self):
        self.grant()
        for amount in (0, 21, -1, True, "20", 20.0):
            with self.subTest(amount=amount), self.assertRaises(GameError):
                self.plan("ship", "scout", amount=amount)
        self.plan("ship", "scout", amount=20)
        self.assertEqual(self.p["queue"][0]["amount"], 20)

    def test_owned_planet_required_for_plan(self):
        self.grant()
        outsider = self.w.register("QueueOther", PASSWORD)["state"]["player"]["id"]
        foreign = self.w._owned(outsider)
        before = copy.deepcopy(self.w.data)
        with self.assertRaises(GameError):
            self.plan("build", "metal_mine", planet_id=foreign["id"])
        self.assertEqual(self.w.data, before)

    def test_foreign_pending_order_cannot_be_removed_or_reordered(self):
        self.grant()
        self.action("build", "power_plant")
        self.plan("build", "metal_mine")
        order_id = self.player["planned_orders"][0]["id"]
        outsider = self.w.register("QueueForeign", PASSWORD)["state"]["player"]["id"]
        for action in ("remove_planned_project", "reorder_planned_project"):
            before = copy.deepcopy(self.w.data)
            with self.subTest(action=action), self.assertRaises(GameError):
                self.w.action(outsider, {"type": action, "order_id": order_id})
            self.assertEqual(self.w.data, before)

    def test_pending_orders_neither_charge_nor_reserve_building_slot(self):
        import planetary
        self.grant()
        self.action("build", "power_plant")
        before = copy.deepcopy(self.p["resources"])
        fields = planetary.fields(self.p)
        self.plan("build", "metal_mine")
        self.plan("ship", "frigate", amount=20)  # Starts and charges its separate lane.
        after_ship = copy.deepcopy(self.p["resources"])
        self.plan("build", "crystal_mine")
        self.assertEqual(self.p["resources"], after_ship)
        self.assertEqual(planetary.fields(self.p), fields)
        self.assertGreater(before["metal"], after_ship["metal"])

    def test_cost_is_current_level_when_each_pending_upgrade_starts(self):
        self.grant()
        self.stock_without_production()
        before = copy.deepcopy(self.p["resources"])
        self.plan("build", "metal_mine")
        first = copy.deepcopy(self.p["queue"][0])
        self.plan("build", "metal_mine")
        self.w.advance(first["ends_at"])
        second = self.p["queue"][0]
        self.assertEqual(second["level"], first["level"] + 1)
        self.assertGreater(second["paid_cost"]["metal"], first["paid_cost"]["metal"])
        for resource in RESOURCES:
            self.assertEqual(self.p["resources"][resource], before[resource] - first["paid_cost"][resource] - second["paid_cost"][resource])

    def test_resource_wait_starts_at_affordability_time_during_offline_advance(self):
        self.grant()
        cost = next(x for x in self.w._catalog(self.pid, self.p)["ships"] if x["key"] == "scout")["cost"]
        self.p["resources"] = {r: max(0.0, value - 10.0) for r, value in cost.items()}
        self.w.production = lambda planet, **kwargs: dict.fromkeys(RESOURCES, 3600.0)
        self.plan("ship", "scout")
        self.assertFalse(self.p["queue"])
        self.assertEqual(self.w.state(self.pid)["planned_orders"][0]["status"], "waiting_resources")
        self.w.advance(NOW + 10.01)
        task = self.p["queue"][0]
        self.assertAlmostEqual(task["started_at"], NOW + 10, places=4)
        self.assertEqual(len(self.player["planned_orders"]), 0)

    def test_complete_multiple_jobs_offline_chronologically_once(self):
        self.grant()
        self.stock_without_production()
        before = self.p["ships"]["scout"]
        for i in range(3):
            self.plan("ship", "scout")
        duration = self.p["queue"][0]["seconds"]
        self.w.advance(NOW + duration * 3)
        self.assertEqual(self.p["ships"]["scout"], before + 3)
        self.assertFalse(self.p["queue"])
        self.assertFalse(self.player["planned_orders"])
        self.w.advance(self.w.now)
        self.assertEqual(self.p["ships"]["scout"], before + 3)

    def test_research_remains_one_empire_lane_and_uses_selected_colony(self):
        self.grant()
        second = self.second()
        self.plan("research", "weapons")
        first = self.p["queue"][0]
        self.plan("research", "propulsion", planet_id=second["id"])
        self.assertFalse(second["queue"])
        self.w.advance(first["ends_at"])
        self.assertFalse(self.p["queue"])
        self.assertEqual(len(second["queue"]), 1)
        self.assertEqual(second["queue"][0]["key"], "propulsion")

    def test_exact_expiry_blocks_next_start_but_active_project_completes(self):
        self.grant()
        self.plan("ship", "scout")
        deadline = self.p["queue"][0]["ends_at"]
        self.player["subscription"]["expires_at"] = deadline
        self.plan("ship", "scout")
        before = self.p["ships"]["scout"]
        self.w.advance(deadline + 1)
        self.assertEqual(self.p["ships"]["scout"], before + 1)
        self.assertFalse(self.p["queue"])
        self.assertEqual(len(self.player["planned_orders"]), 1)
        self.assertFalse(self.w.state(self.pid)["premium"]["queue_planning_active"])

    def test_new_entitlement_never_starts_existing_order_before_verified_start(self):
        self.grant()
        self.p["resources"] = dict.fromkeys(RESOURCES, 0.0)
        self.plan("ship", "scout")
        self.p["resources"] = dict.fromkeys(RESOURCES, 100000.0)
        self.grant(NOW + 30, NOW + 10000)
        self.w.advance(NOW + 30)
        self.assertEqual(self.p["queue"][0]["started_at"], NOW + 30)

    def test_paid_period_after_gap_wakes_waiting_order_at_its_start(self):
        self.grant(end=NOW + 5)
        cost = next(x for x in self.w._catalog(self.pid, self.p)["ships"] if x["key"] == "scout")["cost"]
        self.p["resources"] = {r: max(0.0, value - 10.0) for r, value in cost.items()}
        self.w.production = lambda planet, **kwargs: dict.fromkeys(RESOURCES, 3600.0)
        self.plan("ship", "scout")
        self.player["subscription"].update(starts_at=NOW + 20, expires_at=NOW + 1000,
            periods=[{"starts_at": NOW, "expires_at": NOW + 5},
                     {"starts_at": NOW + 20, "expires_at": NOW + 1000}])
        self.w.advance(NOW + 21)
        self.assertEqual(self.p["queue"][0]["started_at"], NOW + 20)

    def test_private_billing_receipt_fields_are_absent_from_public_state(self):
        self.grant()
        secret = "private-purchase-token-acceptance"
        self.player["subscription"].update(_play_token=secret, _play_token_hash="privatehash", _play_token_history=["privatehistory"])
        body = json.dumps(self.w.state(self.pid))
        for value in (secret, "privatehash", "privatehistory", "_play_token"):
            self.assertNotIn(value, body)

    def test_request_replay_does_not_add_second_waiting_order(self):
        self.grant()
        self.action("ship", "scout")
        request = {"type": "plan_project", "kind": "ship", "key": "scout", "request_id": "independent-replay"}
        self.w.action(self.pid, request)
        before = copy.deepcopy(self.w.data)
        self.w.action(self.pid, request)
        self.assertEqual(self.w.data, before)

    def test_pending_orders_and_verified_entitlement_survive_restart(self):
        self.grant()
        self.action("ship", "scout")
        self.plan("ship", "scout")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "world.sqlite3"
            persistent = World(path, now=NOW)
            persistent.data = copy.deepcopy(self.w.data)
            persistent._save()
            persistent.close()
            restored = World(path, now=NOW)
            try:
                self.assertEqual(restored.state(self.pid)["planned_orders"], self.w.state(self.pid)["planned_orders"])
                self.assertTrue(restored.state(self.pid)["premium"]["queue_planning_active"])
                duration = restored._owned(self.pid)["queue"][0]["seconds"]
                restored.advance(NOW + duration * 2)
                self.assertFalse(restored._player(self.pid)["planned_orders"])
            finally:
                restored.close()

    def test_stalled_google_verification_does_not_block_other_players_state(self):
        entered, release = threading.Event(), threading.Event()
        iso = lambda timestamp: datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")
        owner_id = self.pid

        class BlockingProvider:
            ready = True
            package_name = "com.conradmafer.aliencolonies"

            def get_subscription(self, token):
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("local provider released too late")
                return {"startTime": iso(NOW - 10), "subscriptionState": "SUBSCRIPTION_STATE_ACTIVE",
                    "acknowledgementState": "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
                    "externalAccountIdentifiers": {"obfuscatedExternalAccountId": account_id(owner_id)},
                    "lineItems": [{"productId": "queue_planner", "offerDetails": {"basePlanId": "monthly"}, "expiryTime": iso(NOW + 1000)}]}

            def acknowledge(self, token):
                raise AssertionError("ack already complete")

        self.w.billing_verifier = BillingVerifier(BlockingProvider(), clock=lambda: NOW)
        own_token = self.w.login("QueueAcceptance", PASSWORD)["token"]
        other = self.w.register("QueueResponsive", PASSWORD)
        server = build_server(self.w, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        endpoint = "http://127.0.0.1:" + str(server.server_address[1])

        def request(path, token, body=None, timeout=4):
            headers = {"Authorization": "Bearer " + token, "X-PGR-Client-Version": "51"}
            if body is not None:
                headers["Content-Type"] = "application/json"
            request = Request(endpoint + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)

        with ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(request, "/api/billing/verify", own_token, {"purchase_token": "local-purchase-receipt"})
            try:
                self.assertTrue(entered.wait(2), "verification did not reach provider")
                # This response must finish while the provider is still blocked.
                state = request("/api/state", other["token"], timeout=1.0)
                self.assertTrue(state["ok"])
                self.assertFalse(state["state"]["premium"]["queue_planning_active"])
                self.assertFalse(future.done())
            finally:
                release.set()
            result = future.result(3)
            self.assertTrue(result["state"]["premium"]["queue_planning_active"])


if __name__ == "__main__":
    unittest.main()
