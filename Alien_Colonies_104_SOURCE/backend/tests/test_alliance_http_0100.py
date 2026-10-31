"""Adversarial alliance API checks against real HTTP, SQLite and flight settlement.

Fixtures only choose starting positions and provision supplies. Alliance membership,
roles, operation dispatch, retries and error handling use authenticated public APIs.
"""
import copy
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from server.main import build_server
from tests.world_fixture import LocalTestWorld as World

START = 2_000_000_000
PASSWORD = "alliance-http-password"


class AllianceHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "alliances.sqlite3"
        self.clock = START
        self.clock_patch = patch("server.main.time.time", side_effect=lambda: self.clock)
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)
        self.w = World(self.path, speed=1, now=self.clock)
        self.w.data["alien"]["next_expansion_at"] = START + 1_000_000
        # Persisted snapshots contain plain names, unlike the fresh-world lazy
        # translation wrapper. Keep HTTP rollback assertions about game state.
        self.w.data["alien"]["name"] = "Rój Khar"
        self.accounts = [self.w.register(name, PASSWORD) for name in
                         ("HTTPLeader", "HTTPMember", "HTTPOutsider")]
        self.ids = [account["state"]["player"]["id"] for account in self.accounts]
        self.leader, self.member, self.outsider = self.ids
        for index, player_id in enumerate(self.ids):
            self.w.action(player_id, {"type": "choose_race", "race_id":
                                     ("zetans", "symbionts", "automatons")[index]})
            self.w._player(player_id)["protected_until"] = 0
            home = self.w._owned(player_id)
            home["resources"] = dict.fromkeys(("metal", "crystal", "fuel"), 5_000_000)
            home["ships"].update(frigate=40, cruiser=12, scout=10)
        self.sequence = 0
        self.w._save()
        self.start_server()

    def start_server(self):
        self.server = build_server(self.w, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def tearDown(self):
        self.stop_server()
        self.w.close()

    def restart(self):
        self.stop_server()
        self.w.close()
        self.w = World(self.path, speed=1, now=self.clock)
        self.start_server()

    def request(self, path, actor=0, payload=None, *, raw=None, token=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        headers = {"Content-Type": "application/json", "Accept-Language": "en"}
        if actor is not None:
            headers["Authorization"] = "Bearer " + (token or self.accounts[actor]["token"])
        body = raw if raw is not None else json.dumps(payload) if payload is not None else None
        connection.request("POST" if body is not None else "GET", path, body, headers)
        response = connection.getresponse()
        status, data = response.status, json.loads(response.read())
        connection.close()
        return status, data

    def nonce(self):
        self.sequence += 1
        return "alliance-http-%08d" % self.sequence

    def mutate(self, action, actor=0, **kwargs):
        payload = {"action": action, "request_id": self.nonce(), **kwargs}
        return self.request("/api/alliance", actor, payload)

    def expect_ok(self, response):
        status, data = response
        self.assertEqual(status, 200, data)
        self.assertTrue(data["ok"], data)
        return data

    def create(self):
        return self.expect_ok(self.mutate("create", name="HTTP Alliance", tag="HTT", description="Public description"))

    def join_member(self):
        self.create()
        alliance_id = self.w._player(self.leader)["alliance_id"]
        self.expect_ok(self.mutate("invite", player_id=self.member))
        self.expect_ok(self.mutate("accept_invite", 1, alliance_id=alliance_id))
        return alliance_id

    def reveal(self, actor, target):
        self.w._capture_planetary_intel(self.ids[actor], target)
        self.w._save()

    def attack_preview(self, actor, target):
        self.reveal(actor, target)
        return self.request("/api/preview", actor, {
            "mission": "attack", "planet_id": self.w._owned(self.ids[actor])["id"],
            "target_id": target["id"], "ships": {"frigate": 1}})

    def operation(self, action, actor=0, **kwargs):
        return self.request("/api/alliance/operation", actor,
                            {"action": action, "request_id": self.nonce(), **kwargs})

    def planned_attack(self):
        self.join_member()
        target = self.w._owned(self.outsider)
        self.reveal(0, target)
        result = self.expect_ok(self.operation("create", target_id=target["id"], delay_seconds=10000))
        return result["operation_id"], target

    def snapshot(self):
        return copy.deepcopy(self.w.data), "\n".join(self.w.db.iterdump())

    def test_every_alliance_endpoint_requires_valid_session_and_rejects_forged_identity(self):
        for route in ("/api/alliance", "/api/alliance/operations"):
            with self.subTest(route=route):
                self.assertEqual(self.request(route, None)[0], 401)
                self.assertEqual(self.request(route, 0, token="forged-token-1234567890")[0], 401)
        for route, body in (("/api/alliance", {"action": "create", "name": "Forged Team", "tag": "FOR"}),
                            ("/api/alliance/operation", {"action": "create", "target_id": "s1p1"}),
                            ("/api/alliance/operation/preview", {"action": "join", "operation_id": "forged"})):
            body.update(player_id=self.leader, owner_id=self.leader, request_id=self.nonce())
            with self.subTest(route=route):
                self.assertEqual(self.request(route, None, body)[0], 401)
        data = self.expect_ok(self.request("/api/alliance", 0, {
            "action": "create", "name": "Authenticated Team", "tag": "AUT",
            "player_id": self.outsider, "owner_id": self.outsider, "request_id": self.nonce()}))
        self.assertTrue(data)
        self.assertNotEqual(self.w._player(self.leader).get("alliance_id", ""), "")
        self.assertFalse(self.w._player(self.outsider).get("alliance_id"))

    def test_json_types_nonfinite_numbers_and_missing_nonces_fail_without_changes(self):
        self.w.advance(self.clock)
        before = self.snapshot()
        raw_values = ('[]', 'null', 'true', '{"action":"create","request_id":"invalid-json-1","delay_seconds":NaN}',
                      '{"action":"create","request_id":"invalid-json-2","delay_seconds":Infinity}',
                      '{"action":"create","request_id":"invalid-json-3","delay_seconds":1e999}')
        for raw in raw_values:
            with self.subTest(raw=raw):
                status, data = self.request("/api/alliance", raw=raw)
                self.assertEqual(status, 400, data)
                self.assertFalse(data["ok"])
                self.assertTrue(data["error"])
                self.assertEqual(self.snapshot(), before)
        for changes in ({"request_id": None}, {"request_id": True}, {"request_id": []},
                        {"request_id": ""}, {"action": []}, {"name": []}, {"tag": True}):
            payload = {"action": "create", "name": "Valid Alliance", "tag": "VAL", "request_id": self.nonce(), **changes}
            with self.subTest(changes=changes):
                status, data = self.request("/api/alliance", payload=payload)
                self.assertEqual(status, 400, data)
                self.assertFalse(data["ok"])
                self.assertTrue(data["error"])
                self.assertEqual(self.snapshot(), before)
        status, data = self.request("/api/alliance", payload={"action": "create", "name": "No Nonce", "tag": "NON"})
        self.assertEqual(status, 400, data)
        self.assertEqual(self.snapshot(), before)

    def test_create_retry_survives_restart_and_conflicting_nonce_never_changes_original(self):
        payload = {"action": "create", "name": "Durable Alliance", "tag": "DUR", "description": "Kept description",
                   "request_id": self.nonce()}
        self.expect_ok(self.request("/api/alliance", payload=payload))
        alliance_id = self.w._player(self.leader)["alliance_id"]
        before = self.snapshot()
        self.expect_ok(self.request("/api/alliance", payload=payload))
        self.assertEqual(self.snapshot(), before)
        self.restart()
        before = self.snapshot()
        self.expect_ok(self.request("/api/alliance", payload=payload))
        self.assertEqual(self.w._player(self.leader)["alliance_id"], alliance_id)
        self.assertEqual(self.snapshot(), before)
        status, result = self.request("/api/alliance", payload={**payload, "name": "Altered Alliance"})
        self.assertEqual(status, 409, result)
        self.assertEqual(self.snapshot(), before)

    def test_failed_save_rolls_back_alliance_creation_in_memory_and_sqlite_then_retry_works(self):
        payload = {"action": "create", "name": "Atomic Alliance", "tag": "ATM", "request_id": self.nonce()}
        self.w.advance(self.clock)
        before = self.snapshot()
        save = self.w._save

        def fail_after_mutation(*args, **kwargs):
            save(*args, **kwargs)
            if self.w._player(self.leader).get("alliance_id"):
                raise sqlite3.OperationalError("test write failure after snapshot")

        with patch.object(self.w, "_save", side_effect=fail_after_mutation):
            status, data = self.request("/api/alliance", payload=payload)
        self.assertEqual(status, 503, data)
        self.assertFalse(data["ok"])
        self.assertEqual(self.snapshot(), before)
        self.expect_ok(self.request("/api/alliance", payload=payload))
        self.restart()
        self.assertTrue(self.w._player(self.leader).get("alliance_id"))

    def test_recruitment_requires_consent_and_officers_cannot_take_leadership(self):
        self.create()
        alliance_id = self.w._player(self.leader)["alliance_id"]
        self.expect_ok(self.mutate("invite", player_id=self.member))
        self.assertFalse(self.w._player(self.member).get("alliance_id"))
        status, data = self.mutate("accept_invite", 2, alliance_id=alliance_id, player_id=self.member)
        self.assertEqual(status, 409, data)
        self.assertFalse(self.w._player(self.outsider).get("alliance_id"))
        self.expect_ok(self.mutate("accept_invite", 1, alliance_id=alliance_id))
        for action, fields in (("invite", {"player_id": self.outsider}),
                               ("kick", {"player_id": self.leader}),
                               ("edit", {"description": "Forged edit"}),
                               ("set_role", {"player_id": self.member, "role": "leader"})):
            with self.subTest(action=action):
                before = self.snapshot()
                status, data = self.mutate(action, 1, **fields)
                self.assertEqual(status, 403, data)
                self.assertEqual(self.snapshot(), before)
        self.expect_ok(self.mutate("set_role", player_id=self.member, role="officer"))
        self.expect_ok(self.mutate("invite", 1, player_id=self.outsider))
        for action, fields in (("transfer_leader", {"player_id": self.member}),
                               ("kick", {"player_id": self.leader}),
                               ("set_role", {"player_id": self.member, "role": "leader"}),
                               ("disband", {"confirmation": "HTT"})):
            with self.subTest(officer_action=action):
                status, data = self.mutate(action, 1, **fields)
                self.assertEqual(status, 403, data)
        self.assertEqual(self.w.data["alliances"][alliance_id]["leader_id"], self.leader)

    def test_private_chat_and_applications_never_leak_to_directory_or_outsiders(self):
        before_planets = {p["id"] for system in self.w.state(self.member)["galaxy"] for p in system["planets"]}
        alliance_id = self.join_member()
        self.expect_ok(self.mutate("chat_send", text="SECRET TACTICAL RENDEZVOUS 731"))
        self.expect_ok(self.mutate("apply", 2, alliance_id=alliance_id, text="PRIVATE APPLICATION 829"))
        leader_view = self.expect_ok(self.request("/api/alliance"))
        member_view = self.expect_ok(self.request("/api/alliance", 1))
        outsider_view = self.expect_ok(self.request("/api/alliance?alliance_id=" + alliance_id, 2))
        self.assertIn("SECRET TACTICAL RENDEZVOUS 731", json.dumps(leader_view["alliance"]))
        self.assertIn("SECRET TACTICAL RENDEZVOUS 731", json.dumps(member_view["alliance"]))
        self.assertNotIn("SECRET TACTICAL RENDEZVOUS 731", json.dumps(outsider_view))
        self.assertIn("PRIVATE APPLICATION 829", json.dumps(leader_view["alliance"]))
        self.assertNotIn("PRIVATE APPLICATION 829", json.dumps(member_view))
        self.assertIsNone(outsider_view["alliance"])
        for item in outsider_view["directory"]:
            self.assertFalse(set(item) & {"chat", "members", "applications", "invitations", "operations", "fleets"})
        outsider_state = self.expect_ok(self.request("/api/state", 2))["state"]
        self.assertNotIn("SECRET TACTICAL RENDEZVOUS 731", json.dumps(outsider_state))
        after_planets = {p["id"] for system in self.w.state(self.member)["galaxy"] for p in system["planets"]}
        self.assertEqual(after_planets, before_planets, "Joining cannot bypass observatory/scouting fog")
        self.restart()
        view = self.expect_ok(self.request("/api/alliance", 1))
        self.assertIn("SECRET TACTICAL RENDEZVOUS 731", json.dumps(view["alliance"]))
        self.assertNotIn("SECRET TACTICAL RENDEZVOUS 731", json.dumps(self.expect_ok(self.request("/api/alliance", 2))))

    def test_expulsion_revokes_chat_retries_and_applies_symmetric_temporary_truce(self):
        self.join_member()
        payload = {"action": "chat_send", "text": "Member private strategy", "request_id": self.nonce()}
        self.expect_ok(self.request("/api/alliance", 1, payload))
        self.expect_ok(self.mutate("kick", player_id=self.member))
        expelled = self.expect_ok(self.request("/api/alliance", 1))
        self.assertIsNone(expelled["alliance"])
        self.assertNotIn("Member private strategy", json.dumps(expelled))
        status, result = self.request("/api/alliance", 1, payload)
        self.assertEqual(status, 403, result)
        status, result = self.mutate("create", 1, name="Early Rejoin", tag="EAR")
        self.assertEqual(status, 409, result)
        for actor, target in ((0, self.w._owned(self.member)), (1, self.w._owned(self.leader))):
            status, result = self.attack_preview(actor, target)
            self.assertEqual(status, 403, result)
        self.clock += 86401
        self.expect_ok(self.request("/api/state", 1))
        for actor, target in ((0, self.w._owned(self.member)), (1, self.w._owned(self.leader))):
            self.expect_ok(self.attack_preview(actor, target))
        self.expect_ok(self.mutate("create", 1, name="Later Rejoin", tag="LAT"))

    def test_role_demotion_rechecks_permission_before_duplicate_admin_action(self):
        self.join_member()
        self.expect_ok(self.mutate("set_role", player_id=self.member, role="officer"))
        payload = {"action": "invite", "player_id": self.outsider, "request_id": self.nonce()}
        self.expect_ok(self.request("/api/alliance", 1, payload))
        self.expect_ok(self.mutate("set_role", player_id=self.member, role="member"))
        before = self.snapshot()
        status, result = self.request("/api/alliance", 1, payload)
        self.assertEqual(status, 403, result)
        self.assertEqual(self.snapshot(), before)

    def test_deleting_leader_elects_officer_and_preserves_planet_traits_and_other_reports(self):
        alliance_id = self.join_member()
        self.expect_ok(self.mutate("invite", player_id=self.outsider))
        self.expect_ok(self.mutate("accept_invite", 2, alliance_id=alliance_id))
        self.expect_ok(self.mutate("set_role", player_id=self.member, role="officer"))
        self.expect_ok(self.mutate("chat_send", text="Deleted account authored secret"))
        self.w._report(self.member, "Saved battle", "Historic combat result unchanged")
        historical_reports = copy.deepcopy(self.w._player(self.member)["reports"])
        home = self.w._owned(self.leader)
        environment, rare_trait = copy.deepcopy(home["environment"]), home["rare_trait"]
        home_id = home["id"]
        self.w._save()
        self.expect_ok(self.request("/api/account/delete", 0, {"password": PASSWORD, "confirmation": "DELETE ACCOUNT"}))
        self.assertEqual(self.request("/api/alliance", 0)[0], 401)
        remaining = self.expect_ok(self.request("/api/alliance", 1))["alliance"]
        self.assertEqual(remaining["leader_id"], self.member)
        self.assertEqual(remaining["role"], "leader")
        self.assertNotIn(self.leader, [m["player_id"] for m in remaining["members"]])
        self.assertNotIn("Deleted account authored secret", json.dumps(remaining))
        self.assertEqual(self.w.data["planets"][home_id]["environment"], environment)
        self.assertEqual(self.w.data["planets"][home_id]["rare_trait"], rare_trait)
        self.assertEqual(self.w._player(self.member)["reports"], historical_reports)
        self.restart()
        self.assertEqual(self.expect_ok(self.request("/api/alliance", 1))["alliance"]["leader_id"], self.member)
        self.assertEqual(self.w._player(self.member)["reports"], historical_reports)

    def test_simultaneous_accepts_cannot_put_one_player_into_two_alliances(self):
        self.create()
        first_id = self.w._player(self.leader)["alliance_id"]
        self.expect_ok(self.mutate("create", 2, name="Second Alliance", tag="SEC"))
        second_id = self.w._player(self.outsider)["alliance_id"]
        self.expect_ok(self.mutate("invite", player_id=self.member))
        self.expect_ok(self.mutate("invite", 2, player_id=self.member))
        barrier = threading.Barrier(2)
        results = []
        payloads = [{"action": "accept_invite", "alliance_id": aid, "request_id": self.nonce()}
                    for aid in (first_id, second_id)]

        def accept(payload):
            barrier.wait(timeout=3)
            results.append(self.request("/api/alliance", 1, payload))

        threads = [threading.Thread(target=accept, args=(payload,)) for payload in payloads]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        memberships = [aid for aid, team in self.w.data["alliances"].items() if self.member in team["members"]]
        self.assertEqual(memberships, [self.w._player(self.member)["alliance_id"]])
        self.restart()
        memberships = [aid for aid, team in self.w.data["alliances"].items() if self.member in team["members"]]
        self.assertEqual(memberships, [self.w._player(self.member)["alliance_id"]])

    def test_operation_preview_privacy_and_invalid_fleet_shapes_never_spend_ships_or_fuel(self):
        operation_id, target = self.planned_attack()
        normal = {"action": "join", "operation_id": operation_id,
                  "planet_id": self.w._owned(self.member)["id"], "ships": {"frigate": 2}}
        status, data = self.request("/api/alliance/operations", 2)
        self.assertEqual(status, 403, data)
        status, data = self.request("/api/alliance/operation/preview", 2, normal)
        self.assertEqual(status, 403, data)
        self.assertNotIn(target["name"], json.dumps(data))
        before = self.snapshot()
        self.expect_ok(self.request("/api/alliance/operation/preview", 1, normal))
        self.assertEqual(self.snapshot(), before)
        for ships in (None, [], {"frigate": True}, {"frigate": 1.5}, {"frigate": -1},
                      {"frigate": 10001}, {"unknown_ship": 1}, {"scout": 1}):
            with self.subTest(ships=ships):
                status, data = self.request("/api/alliance/operation", 1,
                                           {**normal, "ships": ships, "request_id": self.nonce()})
                self.assertEqual(status, 400, data)
                self.assertFalse(data["ok"])
                self.assertTrue(data["error"])
                self.assertEqual(self.snapshot(), before)
        for delay in (True, None, 299, 86401, 301.5):
            with self.subTest(delay=delay):
                status, data = self.operation("create", target_id=target["id"], delay_seconds=delay)
                self.assertEqual(status, 400, data)
                self.assertEqual(self.snapshot(), before)
        for hold in (True, None, 0, 2, 1.5):
            with self.subTest(hold=hold):
                status, data = self.operation("defend", 1, target_id=self.w._owned(self.leader)["id"],
                                             ships={"frigate": 1}, hold_hours=hold)
                self.assertEqual(status, 400, data)
                self.assertEqual(self.snapshot(), before)
        forged_origin = {**normal, "planet_id": self.w._owned(self.leader)["id"], "request_id": self.nonce()}
        status, data = self.request("/api/alliance/operation", 1, forged_origin)
        self.assertIn(status, (403, 404), data)
        self.assertEqual(self.snapshot(), before)

    def test_joint_launch_retry_restart_and_failed_write_charge_each_fleet_exactly_once(self):
        operation_id, target = self.planned_attack()
        origin = self.w._owned(self.member)
        payload = {"action": "join", "operation_id": operation_id, "planet_id": origin["id"],
                   "ships": {"frigate": 3}, "request_id": self.nonce()}
        quote = self.expect_ok(self.request("/api/alliance/operation/preview", 1, payload))
        initial_ships, initial_fuel = origin["ships"]["frigate"], origin["resources"]["fuel"]
        before = self.snapshot()
        save = self.w._save

        def fail_after_departure(*args, **kwargs):
            save(*args, **kwargs)
            if any(f["owner_id"] == self.member for f in self.w.data["fleets"].values()):
                raise sqlite3.OperationalError("test dispatch persistence failure")

        with patch.object(self.w, "_save", side_effect=fail_after_departure):
            status, data = self.request("/api/alliance/operation", 1, payload)
        self.assertEqual(status, 503, data)
        self.assertEqual(self.snapshot(), before)
        first = self.expect_ok(self.request("/api/alliance/operation", 1, payload))
        fleet_id = first["fleet_id"]
        self.assertEqual(origin["ships"]["frigate"], initial_ships - 3)
        self.assertEqual(origin["resources"]["fuel"], initial_fuel - quote["fuel_cost"])
        before = self.snapshot()
        self.assertEqual(self.expect_ok(self.request("/api/alliance/operation", 1, payload)), first)
        self.assertEqual(self.snapshot(), before)
        self.restart()
        before = self.snapshot()
        self.assertEqual(self.expect_ok(self.request("/api/alliance/operation", 1, payload)), first)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.w.data["fleets"]), [fleet_id])
        altered = {**payload, "ships": {"frigate": 4}}
        self.assertEqual(self.request("/api/alliance/operation", 1, altered)[0], 409)
        self.assertEqual(self.snapshot(), before)
        incoming = self.expect_ok(self.request("/api/state", 2))["state"]["incoming_attacks"]
        self.assertEqual([item["id"] for item in incoming], [fleet_id])
        self.assertFalse(set(incoming[0]) & {"ships", "cargo", "swarm_crystals"})

    def test_expulsion_recalls_support_revokes_old_dispatch_and_lands_without_duplicates(self):
        self.join_member()
        origin, target = self.w._owned(self.member), self.w._owned(self.leader)
        initial = copy.deepcopy(origin["ships"])
        payload = {"action": "defend", "target_id": target["id"], "planet_id": origin["id"],
                   "ships": {"frigate": 4}, "hold_hours": 1, "request_id": self.nonce()}
        first = self.expect_ok(self.request("/api/alliance/operation", 1, payload))
        self.clock = self.w.data["fleets"][first["fleet_id"]]["arrives_at"]
        self.expect_ok(self.request("/api/state", 1))
        self.assertEqual(self.w.data["fleets"][first["fleet_id"]]["status"], "holding")
        self.expect_ok(self.mutate("kick", player_id=self.member))
        returning = self.w.data["fleets"][first["fleet_id"]]
        self.assertEqual(returning["status"], "returning")
        self.assertEqual(self.request("/api/alliance/operations", 1)[0], 403)
        status, data = self.request("/api/alliance/operation", 1, payload)
        self.assertEqual(status, 403, data)
        self.clock = returning["arrives_at"]
        self.expect_ok(self.request("/api/state", 1))
        self.assertEqual(origin["ships"], initial)
        self.assertNotIn(first["fleet_id"], self.w.data["fleets"])
        self.w._complete_fleet(returning)
        self.assertEqual(origin["ships"], initial)
        self.assertEqual(self.w._player(self.member)["swarm_crystals"], 0)
        self.restart()
        self.assertEqual(self.w._owned(self.member)["ships"], initial)

    def test_deleting_operation_creator_cancels_guests_without_deleting_their_ships(self):
        operation_id, target = self.planned_attack()
        origin = self.w._owned(self.member)
        initial_ships = copy.deepcopy(origin["ships"])
        response = self.expect_ok(self.operation("join", 1, operation_id=operation_id,
                                                planet_id=origin["id"], ships={"frigate": 3}))
        fleet_id = response["fleet_id"]
        self.expect_ok(self.request("/api/account/delete", 0, {"password": PASSWORD, "confirmation": "DELETE ACCOUNT"}))
        self.assertEqual(self.w.data["alliance_operations"][operation_id]["status"], "cancelled")
        self.assertEqual(self.w.data["fleets"][fleet_id]["status"], "returning")
        self.clock = self.w.data["fleets"][fleet_id]["arrives_at"]
        self.expect_ok(self.request("/api/state", 1))
        self.assertEqual(origin["ships"], initial_ships)
        self.assertNotIn(fleet_id, self.w.data["fleets"])
        self.restart()
        self.assertEqual(self.w._owned(self.member)["ships"], initial_ships)
        self.assertEqual(self.w._player(self.member)["swarm_crystals"], 0)

    def test_joining_alliance_recalls_existing_hostile_solo_flight_and_blocks_fresh_attack(self):
        self.create()
        alliance_id = self.w._player(self.leader)["alliance_id"]
        origin, target = self.w._owned(self.leader), self.w._owned(self.member)
        self.reveal(0, target)
        before_target = copy.deepcopy(target["ships"])
        initial_ships = copy.deepcopy(origin["ships"])
        self.expect_ok(self.request("/api/action", 0, {"type": "fleet", "mission": "attack", "target_id": target["id"],
                                                       "ships": {"frigate": 2}, "request_id": self.nonce()}))
        fleet = next(iter(self.w.data["fleets"].values()))
        self.expect_ok(self.mutate("invite", player_id=self.member))
        self.expect_ok(self.mutate("accept_invite", 1, alliance_id=alliance_id))
        self.assertEqual(fleet["status"], "returning")
        self.assertEqual(self.attack_preview(0, target)[0], 403)
        self.clock = fleet["arrives_at"]
        self.expect_ok(self.request("/api/state"))
        self.assertEqual(origin["ships"], initial_ships)
        self.assertEqual(target["ships"], before_target)
        self.assertFalse(self.w.data["fleets"])

    def test_failed_battle_commit_replays_once_without_duplicate_reports_damage_or_loot(self):
        operation_id, target = self.planned_attack()
        target["ships"] = dict.fromkeys(target["ships"], 0)
        target["ships"]["frigate"] = 1
        target["defenses"] = {}
        target["resources"] = {"metal": 3000, "crystal": 1700, "fuel": 1100}
        self.w._save()
        for actor in (0, 1):
            self.expect_ok(self.operation("join", actor, operation_id=operation_id,
                                          planet_id=self.w._owned(self.ids[actor])["id"], ships={"cruiser": 4}))
        before = self.snapshot()
        before_reports = {pid: len(self.w._player(pid)["reports"]) for pid in self.ids}
        before_now = self.w.now
        self.clock = self.w.data["alliance_operations"][operation_id]["impact_at"]
        save = self.w._save

        def fail_after_combat(*args, **kwargs):
            save(*args, **kwargs)
            if self.w.data["alliance_operations"][operation_id]["status"] == "completed":
                raise sqlite3.OperationalError("test failure after combat and reports")

        with patch.object(self.w, "_save", side_effect=fail_after_combat):
            status, data = self.request("/api/state")
        self.assertEqual(status, 503, data)
        self.assertEqual(self.w.now, before_now)
        self.assertEqual(self.snapshot(), before)
        self.expect_ok(self.request("/api/state"))
        operation = self.w.data["alliance_operations"][operation_id]
        self.assertEqual(operation["status"], "completed")
        self.assertEqual(operation["result"]["outcome"], "attacker_wins")
        for pid in self.ids:
            self.assertEqual(len(self.w._player(pid)["reports"]), before_reports[pid] + 1)
        cargo = {resource: sum(f["cargo"][resource] for f in self.w.data["fleets"].values())
                 for resource in ("metal", "crystal", "fuel")}
        self.assertEqual(cargo, operation["result"]["cargo"])
        self.assertEqual(sum(target["ships"].values()), 0)
        settled = self.snapshot()
        self.expect_ok(self.request("/api/state"))
        self.assertEqual(self.snapshot(), settled)
        self.restart()
        self.assertEqual(self.w.data["alliance_operations"][operation_id]["status"], "completed")
        for pid in self.ids:
            self.assertEqual(len(self.w._player(pid)["reports"]), before_reports[pid] + 1)
        reports = [r for r in self.w._player(self.leader)["reports"] if r.get("battle_replay")]
        self.assertEqual(len(reports), 1)
        self.expect_ok(self.request("/api/battle-replay?report_id=" + reports[0]["id"]))
        self.assertEqual(self.request("/api/battle-replay?report_id=" + reports[0]["id"], 2)[0], 404)


if __name__ == "__main__":
    unittest.main()
