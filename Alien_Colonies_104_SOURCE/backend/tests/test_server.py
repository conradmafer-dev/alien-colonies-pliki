"""Stateful regression scenarios for the authoritative multiplayer server.

Run from the project directory: python3 -m unittest discover -s tests -v
No third-party packages, external server, network service or sleeps required.
"""

from concurrent.futures import ThreadPoolExecutor
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from server.main import GameError, VERSION, build_server
from tests.world_fixture import LocalTestWorld as World
from server import swarm


PASSWORD = "test-password-123"
START = 1_900_000_000.0
RESOURCE_KEYS = ("metal", "crystal", "fuel")


def state_of(response):
    return response.get("state", response)


class WorldScenarios(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "world.sqlite3")
        self.world = World(db_path=self.db_path, speed=10, now=START)
        self.alice = self.world.register("Alicja", PASSWORD)
        self.bob = self.world.register("Bartosz", PASSWORD)
        self.a = state_of(self.alice)["player"]["id"]
        self.b = state_of(self.bob)["player"]["id"]
        # These route/storage regressions begin after local systems were scouted.
        # Dedicated 0.9.0 tests cover the initial hidden galaxy.
        targets = [self.world._owned(self.a), self.world._owned(self.b)]
        targets.append(next(p for p in self.world.data["planets"].values() if p["owner_type"] == "empty" and p["galaxy_id"] == "g1"))
        for owner in (self.a, self.b):
            for target in targets: self.world._capture_planetary_intel(owner, target)

    def tearDown(self):
        self.world.close()
        self.temp.cleanup()

    def state(self, player=None, planet=None):
        return state_of(self.world.state(player or self.a, planet))

    def act(self, player=None, **payload):
        player = player or self.a
        payload.setdefault("planet_id", self.state(player)["home_id"])
        return self.world.action(player, payload)

    def empty_target(self):
        return next(
            p["id"] for s in self.state()["galaxy"] for p in s["planets"]
            if p["owner_type"] == "empty"
        )

    def owner_of(self, planet):
        return self.world.data["planets"][planet]

    def economic_state(self, player=None):
        state = self.state(player)
        return copy.deepcopy({key: state[key] for key in (
            "resources", "buildings", "research", "ships", "queue", "fleets"
        )})

    def assert_rejected(self, operation):
        with self.assertRaises(GameError) as caught:
            operation()
        self.assertGreaterEqual(caught.exception.status, 400)
        self.assertLess(caught.exception.status, 500)

    def finish_fleets(self, *players):
        for _ in range(12):
            fleets = [f for p in (players or (self.a,)) for f in self.state(p)["fleets"]]
            if not fleets:
                return
            self.world.advance(max(self.world.now, min(f["arrives_at"] for f in fleets)) + 0.01)
        self.fail("Fleets did not reach a terminal state after 12 arrivals")

    def test_two_accounts_share_galaxy_but_keep_private_state(self):
        a, b = self.state(self.a), self.state(self.b)
        self.assertNotEqual(self.a, self.b)
        self.assertNotEqual(a["home_id"], b["home_id"])
        self.assertEqual([s["id"] for s in a["galaxy"]], [s["id"] for s in b["galaxy"]])
        self.assertNotEqual(a["galaxy"], b["galaxy"])  # Per-player observations.
        self.assertEqual(self.owner_of(a["home_id"])["owner_id"], self.a)
        self.assertEqual(self.owner_of(b["home_id"])["owner_id"], self.b)
        bob_before = self.economic_state(self.b)
        self.act(type="build", key="metal_mine")
        self.assertTrue(self.state(self.a)["queue"])
        self.assertEqual(self.economic_state(self.b), bob_before)
        self.assertNotEqual(self.alice["token"], self.bob["token"])

    def test_cannot_read_or_spend_another_players_planet(self):
        target = self.state(self.b)["home_id"]
        before_a, before_b = self.economic_state(self.a), self.economic_state(self.b)
        invalid = [
            lambda: self.world.state(self.a, target),
            lambda: self.act(type="build", key="metal_mine", planet_id=target),
            lambda: self.act(type="fleet", mission="scout", target_id=self.empty_target(),
                             planet_id=target, ships={"scout": 1}),
        ]
        for operation in invalid:
            with self.subTest(operation=operation):
                self.assert_rejected(operation)
        self.assertEqual(self.economic_state(self.a), before_a)
        self.assertEqual(self.economic_state(self.b), before_b)

    def test_invalid_counts_cargo_and_overspend_are_atomic(self):
        before = self.economic_state()
        target = self.empty_target()
        for amount in (-1, 0, 21, 1.5, True, "1", float("nan")):
            with self.subTest(ship_amount=amount):
                self.assert_rejected(lambda: self.act(type="ship", key="scout", amount=amount))
                self.assertEqual(self.economic_state(), before)
        self.assert_rejected(lambda: self.act(type="ship", key="frigate", amount=20))
        self.assertEqual(self.economic_state(), before)
        for count in (-1, 0, 3, 1000000, True, 1.5, "1", float("nan")):
            with self.subTest(fleet_count=count):
                self.assert_rejected(lambda: self.act(type="fleet", mission="scout", target_id=target,
                                                     ships={"scout": count}))
                self.assertEqual(self.economic_state(), before)
        for cargo in ({"metal": -1}, {"fuel": float("nan")}, {"metal": True},
                      {"metal": 10**12}, {"unknown": 1}):
            with self.subTest(cargo=cargo):
                self.assert_rejected(lambda: self.act(type="fleet", mission="colonize", target_id=target,
                                                     ships={"colonizer": 1}, cargo=cargo))
                self.assertEqual(self.economic_state(), before)

    def test_build_completes_once_and_busy_queue_cannot_be_overwritten(self):
        level = self.state()["buildings"]["metal_mine"]
        self.act(type="build", key="metal_mine")
        queued = self.state()["queue"]
        self.assertEqual(len(queued), 1)
        before = self.economic_state()
        self.assert_rejected(lambda: self.act(type="build", key="crystal_mine"))
        self.assertEqual(self.economic_state(), before)
        deadline = queued[0]["ends_at"]
        self.world.advance(deadline - 0.001)
        self.assertEqual(self.state()["buildings"]["metal_mine"], level)
        self.world.advance(deadline)
        self.assertEqual(self.state()["buildings"]["metal_mine"], level + 1)
        self.assertEqual(self.state()["queue"], [])
        self.world.advance(deadline)
        self.world.advance(deadline + 30)
        self.assertEqual(self.state()["buildings"]["metal_mine"], level + 1)

    def test_fleet_preview_is_pure_and_scout_returns_once(self):
        payload = {"type": "fleet", "planet_id": self.state()["home_id"], "mission": "scout",
                   "target_id": self.empty_target(), "ships": {"scout": 1}}
        before = self.economic_state()
        quote = self.world.preview(self.a, payload)
        self.assertGreater(quote["seconds"], 0)
        self.assertGreaterEqual(quote["fuel_cost"], 0)
        self.assertEqual(self.economic_state(), before)
        self.world.action(self.a, payload)
        launched = self.state()
        self.assertEqual(launched["ships"]["scout"], before["ships"]["scout"] - 1)
        self.assertAlmostEqual(launched["resources"]["fuel"], before["resources"]["fuel"] - quote["fuel_cost"], places=3)
        self.assertEqual(len(launched["fleets"]), 1)
        self.finish_fleets(self.a)
        complete = self.state()
        self.assertEqual(complete["ships"], before["ships"])
        self.assertGreater(len(complete["reports"]), 0)
        self.world.advance(self.world.now)
        self.world.advance(self.world.now + 30)
        self.assertEqual(self.state()["ships"], complete["ships"])
        ids = [r["id"] for r in self.state()["reports"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_two_players_racing_for_one_colony_cannot_overwrite_owner(self):
        target = self.empty_target()
        for player in (self.a, self.b):
            self.act(player, type="fleet", mission="colonize", target_id=target, ships={"colonizer": 1})
        arrivals = [(self.state(p)["fleets"][0]["arrives_at"], p) for p in (self.a, self.b)]
        self.world.advance(min(at for at, _ in arrivals) + 0.0001)
        winner = self.owner_of(target)["owner_id"]
        self.assertIn(winner, (self.a, self.b))
        if arrivals[0][0] != arrivals[1][0]:
            self.assertEqual(winner, min(arrivals)[1])
        loser = self.b if winner == self.a else self.a
        self.finish_fleets(self.a, self.b)
        self.assertEqual(self.owner_of(target)["owner_id"], winner)
        self.assertEqual(len(self.state(winner)["own_planets"]), 2)
        self.assertEqual(len(self.state(loser)["own_planets"]), 1)
        self.assertEqual(self.state(loser)["ships"]["colonizer"], 1)
        self.assertEqual(self.state(winner)["ships"]["colonizer"], 0)
        self.world.advance(self.world.now + 10)
        self.assertEqual(self.owner_of(target)["owner_id"], winner)

    def test_new_player_protection_blocks_attack_without_losing_ships(self):
        before_a, before_b = self.economic_state(self.a), self.economic_state(self.b)
        payload = {"type": "fleet", "planet_id": self.state()["home_id"], "mission": "attack",
                   "target_id": self.state(self.b)["home_id"], "ships": {"frigate": 1}}
        self.assertGreater(self.state(self.b)["player"]["protected_until"], self.world.now)
        self.assert_rejected(lambda: self.world.preview(self.a, payload))
        self.assert_rejected(lambda: self.world.action(self.a, payload))
        self.assertEqual(self.economic_state(self.a), before_a)
        self.assertEqual(self.economic_state(self.b), before_b)

    def test_transport_delivers_cargo_once_and_returns_the_ship(self):
        target = self.empty_target()
        self.act(type="fleet", mission="colonize", target_id=target, ships={"colonizer": 1})
        self.finish_fleets(self.a)
        colony_before = self.state(self.a, target)
        home_before = self.state()
        sent_at = self.world.now
        self.act(type="fleet", mission="transport", target_id=target,
                 ships={"cargo": 1}, cargo={"metal": 120})
        home_departed = self.state()
        self.assertAlmostEqual(home_departed["resources"]["metal"], home_before["resources"]["metal"] - 120, places=2)
        arrival = home_departed["fleets"][0]["arrives_at"]
        self.world.advance(arrival)
        colony_arrived = self.state(self.a, target)
        produced = colony_before["production"]["metal"] * (arrival - sent_at) / 3600
        self.assertAlmostEqual(colony_arrived["resources"]["metal"],
                               colony_before["resources"]["metal"] + produced + 120, delta=2)
        self.world.advance(arrival)
        self.assertEqual(self.state(self.a, target)["resources"], colony_arrived["resources"])
        self.finish_fleets(self.a)
        self.assertEqual(self.state()["ships"]["cargo"], home_before["ships"]["cargo"])

    def test_restart_preserves_sessions_builds_and_fleet_completion(self):
        self.act(type="build", key="metal_mine")
        self.act(type="fleet", mission="scout", target_id=self.empty_target(), ships={"scout": 1})
        before = self.economic_state()
        token = self.alice["token"]
        clock = self.world.now
        self.world.close()
        self.world = World(db_path=self.db_path, speed=10, now=clock)
        self.assertEqual(self.world.authenticate(token), self.a)
        self.assertEqual(self.economic_state(), before)
        deadline = self.state()["queue"][0]["ends_at"]
        self.world.advance(deadline)
        self.finish_fleets(self.a)
        completed = self.economic_state()
        clock = self.world.now
        self.world.close()
        self.world = World(db_path=self.db_path, speed=10, now=clock)
        self.assertEqual(self.world.authenticate(token), self.a)
        self.world.advance(clock)
        self.assertEqual(self.economic_state(), completed)
        self.assertEqual(completed["buildings"]["metal_mine"], before["buildings"]["metal_mine"] + 1)
        self.assertEqual(completed["ships"]["scout"], before["ships"]["scout"] + 1)

    def test_aliens_need_real_resources_ship_and_fuel_before_expanding(self):
        colonies = [p for p in self.world.data["planets"].values() if p["owner_type"] == "alien"]
        initial_count = len(colonies)
        self.world.data["alien"]["next_expansion_at"] = self.world.now + 1_000_000
        self.world.data["alien"]["swarm_next_colonization_at"] = self.world.now
        for colony in colonies:
            colony["resources"] = dict.fromkeys(RESOURCE_KEYS, 0.0)
            colony["buildings"]["power_plant"] = 0
            colony["ships"]["colonizer"] = 0
        self.world._alien_turn()
        self.assertTrue(all(not p["queue"] for p in colonies))
        self.assertFalse(self.world.data["fleets"])
        source = colonies[0]
        target = next(p for p in self.world.data["planets"].values() if p["owner_type"] == "empty")
        # Isolate the paid construction and launcher: economic AI priorities and
        # the seven-day strategic gate have their own fortress-policy tests.
        cost = dict(zip(RESOURCE_KEYS, swarm.SHIPS["colonizer"][2]))
        source["resources"] = dict(cost)
        self.assertTrue(self.world._swarm_queue(source, "ship", "colonizer"))
        self.assertEqual(source["resources"], dict.fromkeys(RESOURCE_KEYS, 0))
        self.assertEqual(source["ships"]["colonizer"], 0)
        self.world.advance(source["queue"][0]["ends_at"])
        self.assertEqual(source["ships"]["colonizer"], 1)
        ships = dict.fromkeys(swarm.SHIPS, 0)
        ships.update(swarm.EXPANSION_ESCORT, colonizer=1)
        self.assertIsNone(self.world._swarm_launch(source, target, "colonize", ships))
        self.assertEqual(sum(p["owner_id"] == "khar" for p in self.world.data["planets"].values()), initial_count)
        source["resources"]["fuel"] = 100_000
        expedition = self.world._swarm_launch(source, target, "colonize", ships)
        self.assertIsNotNone(expedition)
        self.assertEqual(source["ships"]["colonizer"], 0)
        self.assertLess(source["resources"]["fuel"], 100_000)
        self.world.advance(expedition["arrives_at"])
        self.assertEqual(sum(p["owner_id"] == "khar" for p in self.world.data["planets"].values()), initial_count + 1)
        self.world.advance(self.world.now)
        self.assertEqual(sum(p["owner_id"] == "khar" for p in self.world.data["planets"].values()), initial_count + 1)


class HTTPScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.world = World(db_path=str(Path(cls.temp.name) / "http.sqlite3"), speed=10)
        cls.server = build_server(cls.world, "127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.world.close()
        cls.temp.cleanup()

    def request(self, method, path, payload=None, token=None, raw=None, headers=None):
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        if token:
            request_headers["Authorization"] = "Bearer " + token
        body = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            data = json.loads(response.read())
            return response.status, data
        finally:
            connection.close()

    def register(self, name):
        status, data = self.request("POST", "/api/register", {"name": name, "password": PASSWORD})
        self.assertIn(status, (200, 201), data)
        self.assertTrue(data["ok"])
        return data

    def test_health_and_authentication_reject_invalid_credentials(self):
        status, health = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(health, {"ok": True, "version": VERSION})
        user = self.register("HttpAuth")
        for token in (None, "invalid-token"):
            status, data = self.request("GET", "/api/state", token=token)
            self.assertEqual(status, 401)
            self.assertFalse(data["ok"])
            self.assertIsInstance(data["error"], str)
        status, data = self.request("POST", "/api/login", {"name": "HttpAuth", "password": "incorrect-password"})
        self.assertEqual(status, 401)
        status, data = self.request("GET", "/api/state", token=user["token"])
        self.assertEqual(status, 200)
        self.assertEqual(data["state"]["player"]["id"], user["state"]["player"]["id"])

    def test_malformed_json_wrong_shapes_and_large_body_return_errors(self):
        for raw in (b"{", b"[]", b"null", b"true", b'"string"', b'{"name":NaN}'):
            with self.subTest(raw=raw):
                status, data = self.request("POST", "/api/register", raw=raw)
                self.assertEqual(status, 400, data)
                self.assertFalse(data["ok"])
                self.assertIsInstance(data["error"], str)
        user = self.register("InvalidPayload")
        status, data = self.request("POST", "/api/action", token=user["token"],
                                    raw=b'{"type":"ship","key":"scout","amount":1e999}')
        self.assertEqual(status, 400, data)
        self.assertFalse(data["ok"])
        # Reject by Content-Length before attempting to allocate/read an unbounded body.
        status, data = self.request("POST", "/api/register", raw=b"{}", headers={"Content-Length": "10000000"})
        self.assertEqual(status, 413, data)
        self.assertFalse(data["ok"])
        self.assertEqual(self.request("GET", "/health")[0], 200)

    def test_concurrent_fleet_orders_cannot_spend_one_colonizer_twice(self):
        user = self.register("Concurrent")
        state = user["state"]
        targets = [p["id"] for p in self.world.data["planets"].values() if p["owner_type"] == "empty" and p["galaxy_id"] == "g1"][:2]
        for target in targets:
            self.world._capture_planetary_intel(state["player"]["id"], self.world.data["planets"][target])
        gate = threading.Barrier(2)

        def launch(target):
            gate.wait(timeout=5)
            return self.request("POST", "/api/action", {
                "type": "fleet", "planet_id": state["home_id"], "mission": "colonize",
                "target_id": target, "ships": {"colonizer": 1},
            }, token=user["token"])

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(launch, targets))
        self.assertEqual(sum(status == 200 for status, _ in results), 1, results)
        self.assertEqual(sum(400 <= status < 500 for status, _ in results), 1, results)
        status, data = self.request("GET", "/api/state", token=user["token"])
        self.assertEqual(status, 200)
        self.assertEqual(data["state"]["ships"]["colonizer"], 0)
        self.assertEqual(len(data["state"]["fleets"]), 1)


if __name__ == "__main__":
    unittest.main()
