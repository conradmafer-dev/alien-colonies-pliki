"""Open registration, optional account limits, and existing world persistence."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import copy
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest

from server.main import GameError, VERSION, build_server
from tests.world_fixture import LocalTestWorld as World


PASSWORD = "open-test-password"
LEGACY_INVITE = "obsolete-invitation-should-never-appear-in-response-49b26"
START = 1_900_000_000.0


class OpenServerScenarios(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "private.sqlite3")
        self.world = World(self.db_path, now=START)

    def tearDown(self):
        self.world.close()
        self.temp.cleanup()

    @contextmanager
    def api(self):
        server = build_server(self.world, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(method, path, payload=None, token=None):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            body = json.dumps(payload).encode() if payload is not None else None
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            try:
                connection.request(method, path, body=body, headers=headers)
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally:
                connection.close()

        try:
            yield request
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_http_registration_is_open_to_more_than_two_accounts(self):
        with self.api() as request:
            users = []
            for name in ("FirstPilot", "SecondPilot", "ThirdPilot", "FourthPilot"):
                status, user = request("POST", "/api/register", {
                    "name": name, "password": PASSWORD,
                })
                self.assertEqual(status, 200, user)
                users.append(user)
            self.assertEqual(len(self.world.data["players"]), 4)
            self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 4)
            registered_players = {user["state"]["player"]["id"] for user in users}
            self.assertEqual(set(self.world.data["players"]), registered_players)
            self.assertEqual(len({u["state"]["home_id"] for u in users}), 4)
            self.assertEqual(len({u["token"] for u in users}), 4)
            for user in users:
                status, state = request("GET", "/api/state", token=user["token"])
                self.assertEqual(status, 200, state)
                self.assertEqual(state["state"]["player"]["id"], user["state"]["player"]["id"])
                visible_players = {p["owner_id"] for s in state["state"]["galaxy"]
                                   for p in s["planets"] if p["owner_type"] == "player"}
                # Registration does not grant reconnaissance of other empires.
                self.assertIn(user["state"]["player"]["id"], visible_players)
                self.assertTrue(visible_players <= registered_players)

    def test_default_has_no_configured_twenty_account_cap(self):
        for index in range(21):
            self.world.register(f"Pilot{index:02}", PASSWORD)
        self.assertEqual(self.world.max_players, 0)
        self.assertEqual(len(self.world.data["players"]), 21)

    def test_optional_limit_accepts_nonnegative_integers_only(self):
        for value in (-1, True, False, None, 2.0, "2"):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                World(":memory:", now=START, max_players=value)
        for value in (0, 1, 100):
            with self.subTest(value=value):
                world = World(":memory:", now=START, max_players=value)
                world.close()

    def test_concurrent_registration_respects_optional_admin_limit(self):
        self.world.max_players = 2
        self.world.register("HostPilot", PASSWORD)
        gate = threading.Barrier(2)

        def register(name):
            gate.wait(timeout=5)
            try:
                return 200, self.world.register(name, PASSWORD)
            except GameError as exc:
                return exc.status, exc.message

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(register, ("GuestOne", "GuestTwo")))
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(len(self.world.data["players"]), 2)
        self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 2)
        self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 2)
        self.assertEqual(sum(p["owner_type"] == "player" for p in self.world.data["planets"].values()), 2)

    def test_open_registration_still_needs_a_free_starting_planet(self):
        self.world.register("FirstPilot", PASSWORD)
        for planet in self.world.data["planets"].values():
            if planet["owner_type"] == "empty":
                planet["owner_type"], planet["owner_id"] = "alien", "khar"
        before = copy.deepcopy(self.world.data)
        with self.assertRaises(GameError) as caught:
            self.world.register("AnotherPilot", PASSWORD)
        self.assertEqual(caught.exception.status, 409)
        self.assertIn("planety startowej", caught.exception.message)
        self.assertEqual(self.world.data, before)
        self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 1)
        self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 1)

    def test_restart_and_changing_limit_preserve_accounts_sessions_and_progress(self):
        self.world.max_players = 2
        host = self.world.register("HostPilot", PASSWORD, LEGACY_INVITE)
        guest = self.world.register("GuestPilot", PASSWORD, LEGACY_INVITE)
        host_id = host["state"]["player"]["id"]
        guest_id = guest["state"]["player"]["id"]
        self.world.action(host_id, {"type": "build", "key": "metal_mine"})
        before = self.world.state(host_id)
        deadline = before["queue"][0]["ends_at"]
        self.world.close()
        self.world = World(self.db_path, now=deadline + 1, max_players=1)
        for user, player_id, name in ((host, host_id, "HostPilot"), (guest, guest_id, "GuestPilot")):
            self.assertEqual(self.world.authenticate(user["token"]), player_id)
            logged_in = self.world.login(name, PASSWORD)
            self.assertEqual(logged_in["state"]["player"]["id"], player_id)
            self.assertEqual(logged_in["state"]["home_id"], user["state"]["home_id"])
        self.assertEqual(len(self.world.data["players"]), 2)
        with self.assertRaises(GameError) as caught:
            self.world.register("ThirdPilot", PASSWORD)
        self.assertEqual(caught.exception.status, 409)
        after = self.world.state(host_id)
        self.assertEqual(after["buildings"]["metal_mine"], before["buildings"]["metal_mine"] + 1)
        self.assertEqual(after["queue"], [])
        self.assertGreater(after["resources"]["metal"], before["resources"]["metal"])
        # Removing the configured cap neither resets progress nor expires sessions.
        self.world.close()
        self.world = World(self.db_path, now=deadline + 1)
        self.world.register("ThirdPilot", PASSWORD)
        self.assertEqual(len(self.world.data["players"]), 3)
        self.assertEqual(self.world.authenticate(host["token"]), host_id)
        self.assertEqual(self.world.authenticate(guest["token"]), guest_id)
        self.assertEqual(self.world.state(host_id)["buildings"], after["buildings"])

    def test_legacy_invitation_field_is_ignored_and_never_retained(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        responses = []
        with redirect_stdout(stdout), redirect_stderr(stderr), self.api() as request:
            responses.append(request("GET", "/health"))
            for index, legacy in enumerate((LEGACY_INVITE, "wrong-code", None, True, {}, "\ud800")):
                status, user = request("POST", "/api/register", {
                    "name": f"OpenPilot{index}", "password": PASSWORD, "invite": legacy,
                })
                self.assertEqual(status, 200, user)
                responses.append((status, user))
            responses.append(request("POST", "/api/login", {"name": "OpenPilot0", "password": PASSWORD}))
            responses.append(request("GET", "/api/state", token=user["token"]))
        self.assertEqual(responses[0], (200, {"ok": True, "version": VERSION, "world_epoch": self.world.data["launch_reset_id"]}))
        for response in responses:
            encoded = json.dumps(response)
            self.assertNotIn(LEGACY_INVITE, encoded)
            self.assertNotIn('"invite"', encoded)
            self.assertNotIn('"invite_code"', encoded)
        self.assertNotIn(LEGACY_INVITE, stdout.getvalue() + stderr.getvalue())
        self.assertNotIn(LEGACY_INVITE, json.dumps(self.world.data))
        self.assertNotIn(LEGACY_INVITE, "\n".join(self.world.db.iterdump()))


if __name__ == "__main__":
    unittest.main()
