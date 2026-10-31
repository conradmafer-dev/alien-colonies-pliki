"""Real SQLite account lifecycle, session revocation and colony cleanup checks."""
import copy
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from server.main import GameError, blank_ships, build_server
from tests.world_fixture import LocalTestWorld as World


START = 1_900_000_000.0
PASSWORD = "account-password-123"
NEW_PASSWORD = "replacement-password-456"


class AccountManagementScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "accounts.sqlite3"
        self.world = World(str(self.path), speed=1, now=START)
        result = self.world.register("Owner Test", PASSWORD)
        self.token = result["token"]
        self.owner = result["state"]["player"]["id"]
        result = self.world.register("Other Test", PASSWORD)
        self.other_token = result["token"]
        self.other = result["state"]["player"]["id"]
        self.world.data["alien"]["next_expansion_at"] = START + 10_000_000

    def tearDown(self):
        self.world.close()
        self.tmp.cleanup()

    def recovery_code(self):
        return self.world.account_recovery_code(self.token, PASSWORD)["recovery_code"]

    def auth_fails(self, token):
        with self.assertRaises(GameError) as error:
            self.world.authenticate(token)
        self.assertEqual(error.exception.status, 401)

    def snapshot(self):
        return (copy.deepcopy(self.world.data),
                {table: self.world.db.execute("SELECT * FROM " + table + " ORDER BY 1").fetchall()
                 for table in ("accounts", "sessions", "account_recovery", "snapshot")})

    def restart(self):
        self.world.close()
        self.world = World(str(self.path), speed=1, now=START)

    def test_recovery_code_is_high_entropy_hashed_and_not_in_public_state_or_snapshot(self):
        code = self.recovery_code()
        self.assertRegex(code, r"^AC(?:-[0-9A-F]{8}){6}$")
        row = self.world.db.execute("SELECT code_hash FROM account_recovery WHERE player_id=?",
                                    (self.owner,)).fetchone()
        self.assertEqual(row[0], self.world._recovery_digest(code))
        self.assertRegex(row[0], r"^[0-9a-f]{64}$")
        self.assertEqual(self.world.account_status(self.owner), {"recovery_code_enabled": True})
        self.assertEqual(self.world.account_status(self.other), {"recovery_code_enabled": False})
        state_json = json.dumps(self.world.state(self.owner))
        world_json = json.dumps(self.world.data)
        self.assertNotIn(code, state_json + world_json)
        self.assertNotIn(row[0], state_json + world_json)
        sql_dump = "\n".join(self.world.db.iterdump())
        self.assertNotIn(code, sql_dump)
        self.assertNotIn(PASSWORD, sql_dump)

    def test_recovery_rotation_rejects_old_code_without_revoking_sessions(self):
        first = self.recovery_code()
        second = self.recovery_code()
        self.assertNotEqual(first, second)
        before = self.snapshot()
        with self.assertRaises(GameError):
            self.world.recover_account("Owner Test", first, NEW_PASSWORD)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.world.authenticate(self.token), self.owner)
        result = self.world.recover_account("Owner Test", second, NEW_PASSWORD)
        self.assertEqual(self.world.authenticate(result["token"]), self.owner)

    def test_recovery_survives_restart_is_single_use_and_revokes_all_old_sessions(self):
        code = self.recovery_code()
        extra_token = self.world.login("Owner Test", PASSWORD)["token"]
        self.restart()
        old_world = copy.deepcopy(self.world.data)
        # Human-readable codes accept case and separators after copying.
        result = self.world.recover_account("owner test", code.lower().replace("-", " "), NEW_PASSWORD)
        self.auth_fails(self.token)
        self.auth_fails(extra_token)
        self.assertEqual(self.world.authenticate(result["token"]), self.owner)
        self.assertEqual(self.world.authenticate(self.other_token), self.other)
        self.assertEqual(self.world.data["players"][self.owner], old_world["players"][self.owner])
        self.assertFalse(self.world.account_status(self.owner)["recovery_code_enabled"])
        with self.assertRaises(GameError):
            self.world.login("Owner Test", PASSWORD)
        self.assertTrue(self.world.login("Owner Test", NEW_PASSWORD)["ok"])
        before = self.snapshot()
        with self.assertRaises(GameError):
            self.world.recover_account("Owner Test", code, "another-password-789")
        self.assertEqual(self.snapshot(), before)
        self.restart()
        self.assertEqual(self.world.authenticate(result["token"]), self.owner)
        self.auth_fails(self.token)

    def test_recovery_invalid_inputs_do_not_change_any_account_or_consume_code(self):
        code = self.recovery_code()
        for name, candidate, password in (
                ("Owner Test", "AC-" + "0" * 48, NEW_PASSWORD),
                ("Unknown Test", code, NEW_PASSWORD),
                ("Other Test", code, NEW_PASSWORD),
                ("Owner Test", code, "short"),
                ("Owner Test", None, NEW_PASSWORD),
                ("Owner Test", [code], NEW_PASSWORD),
                ("Owner Test", "A" * 1000, NEW_PASSWORD)):
            with self.subTest(name=name, candidate=type(candidate).__name__, password=len(password)):
                before = self.snapshot()
                with self.assertRaises(GameError):
                    self.world.recover_account(name, candidate, password)
                self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.world.recover_account("Owner Test", code, NEW_PASSWORD)["ok"])

    def test_all_private_operations_require_current_password_and_keep_valid_session_on_typo(self):
        operations = [
            lambda token, password: self.world.account_recovery_code(token, password),
            lambda token, password: self.world.account_password(token, password, NEW_PASSWORD),
            lambda token, password: self.world.account_logout_others(token, password),
            lambda token, password: self.world.account_delete(token, password, "USUŃ KONTO"),
        ]
        for operation in operations:
            for password in ("wrong-password", "x", None, {"secret": PASSWORD}):
                before = self.snapshot()
                with self.assertRaises(GameError) as error:
                    operation(self.token, password)
                self.assertEqual(error.exception.status, 403)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.world.authenticate(self.token), self.owner)
            before = self.snapshot()
            with self.assertRaises(GameError) as error:
                operation("unknown-token-1234567890", PASSWORD)
            self.assertEqual(error.exception.status, 401)
            self.assertEqual(self.snapshot(), before)

    def test_password_change_returns_new_session_revokes_old_sessions_and_code(self):
        code = self.recovery_code()
        extra_token = self.world.login("Owner Test", PASSWORD)["token"]
        other_before = copy.deepcopy(self.world.data["players"][self.other])
        result = self.world.account_password(self.token, PASSWORD, NEW_PASSWORD)
        self.assertEqual(result["state"]["player"]["id"], self.owner)
        self.assertNotEqual(result["token"], self.token)
        self.auth_fails(self.token)
        self.auth_fails(extra_token)
        self.assertEqual(self.world.authenticate(result["token"]), self.owner)
        self.assertEqual(self.world.authenticate(self.other_token), self.other)
        self.assertEqual(self.world.data["players"][self.other], other_before)
        self.assertFalse(self.world.account_status(self.owner)["recovery_code_enabled"])
        with self.assertRaises(GameError):
            self.world.recover_account("Owner Test", code, "third-password-789")
        self.restart()
        self.assertEqual(self.world.authenticate(result["token"]), self.owner)
        self.assertTrue(self.world.login("Owner Test", NEW_PASSWORD)["ok"])

    def test_bad_new_password_does_not_revoke_sessions_or_code(self):
        self.recovery_code()
        for password in ("short", "a" * 129, None, 123):
            before = self.snapshot()
            with self.assertRaises(GameError):
                self.world.account_password(self.token, PASSWORD, password)
            self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.world.authenticate(self.token), self.owner)

    def test_logout_others_preserves_request_session_password_code_and_other_account(self):
        code = self.recovery_code()
        one = self.world.login("Owner Test", PASSWORD)["token"]
        two = self.world.login("Owner Test", PASSWORD)["token"]
        self.assertTrue(self.world.account_logout_others(one, PASSWORD)["ok"])
        self.auth_fails(self.token)
        self.auth_fails(two)
        self.assertEqual(self.world.authenticate(one), self.owner)
        self.assertEqual(self.world.authenticate(self.other_token), self.other)
        self.assertTrue(self.world.account_status(self.owner)["recovery_code_enabled"])
        self.restart()
        self.auth_fails(two)
        self.assertEqual(self.world.authenticate(one), self.owner)
        self.assertTrue(self.world.recover_account("Owner Test", code, NEW_PASSWORD)["ok"])

    def test_delete_requires_exact_confirmation_and_password(self):
        for confirmation in ("", "usun konto", "USUŃ KONTO ", True, None):
            before = self.snapshot()
            with self.assertRaises(GameError) as error:
                self.world.account_delete(self.token, PASSWORD, confirmation)
            self.assertEqual(error.exception.status, 400)
            self.assertEqual(self.snapshot(), before)

    def fleet(self, fid, owner, origin, target, status="outbound", mission="attack", cargo=0):
        value = {"id": fid, "owner_id": owner, "origin_id": origin, "target_id": target,
                 "status": status, "mission": mission, "ships": {**blank_ships(), "frigate": 1},
                 "cargo": {"metal": cargo, "crystal": 0, "fuel": 0}, "swarm_crystals": 0,
                 "seconds": 123, "arrives_at": START + 123}
        self.world.data["fleets"][fid] = value
        return value

    def test_delete_cleans_only_own_empire_and_leaves_foreign_flights_and_reports(self):
        self.recovery_code()
        home = self.world._owned(self.owner)
        extra = next(p for p in self.world.data["planets"].values() if p["owner_type"] == "empty")
        extra.update(owner_type="player", owner_id=self.owner, custom_racial_state={"old": 1})
        extra["ships"]["cruiser"] = 99
        extra["queue"] = [{"kind": "ship", "key": "cruiser", "amount": 10, "ends_at": START + 10}]
        extra["resources"]["metal"] = 99999
        other_home = self.world._owned(self.other)
        self.fleet("own-outbound", self.owner, home["id"], other_home["id"])
        self.fleet("own-returning", self.owner, extra["id"], other_home["id"], "returning", cargo=777)
        self.fleet("foreign-outbound", self.other, other_home["id"], home["id"])
        self.fleet("foreign-returning", self.other, other_home["id"], extra["id"], "returning", cargo=333)
        self.world._report(self.other, "Historyczny zwiad", "Owner Test odwiedził sektor.")
        foreign_before = {k: copy.deepcopy(f) for k, f in self.world.data["fleets"].items() if f["owner_id"] == self.other}
        other_before = copy.deepcopy(self.world.data["players"][self.other])
        other_home_before = copy.deepcopy(other_home)
        affected = [copy.deepcopy(home), copy.deepcopy(extra)]
        result = self.world.account_delete(self.token, PASSWORD, "USUŃ KONTO")
        self.assertTrue(result["deleted"])
        self.assertNotIn(self.owner, self.world.data["players"])
        for p in affected:
            expected = self.world._planet(p["id"], p["name"], p["system_id"], p["slot"])
            # Since 0.9.0, deleting a colony preserves its physical planet.
            expected["environment"] = p["environment"]
            # Planet traits survive a deleted colony (0.9.5+), just like terrain.
            if "rare_trait" in p:
                expected["rare_trait"] = p["rare_trait"]
            self.assertEqual(self.world.data["planets"][p["id"]], expected)
        self.assertEqual(self.world.data["fleets"], foreign_before)
        self.assertEqual(self.world.data["players"][self.other], other_before)
        self.assertEqual(self.world._owned(self.other), other_home_before)
        self.assertIsNone(self.world.db.execute("SELECT 1 FROM accounts WHERE id=?", (self.owner,)).fetchone())
        self.assertIsNone(self.world.db.execute("SELECT 1 FROM sessions WHERE player_id=?", (self.owner,)).fetchone())
        self.assertIsNone(self.world.db.execute("SELECT 1 FROM account_recovery WHERE player_id=?", (self.owner,)).fetchone())
        self.auth_fails(self.token)
        self.restart()
        self.assertNotIn(self.owner, self.world.data["players"])
        self.assertEqual(self.world.authenticate(self.other_token), self.other)
        self.assertEqual(self.world.data["fleets"], foreign_before)
        self.assertTrue(self.world.register("Owner Test", NEW_PASSWORD)["ok"])

    def test_deleted_target_makes_foreign_attack_return_and_land_only_once(self):
        home = self.world._owned(self.owner)
        other_home = self.world._owned(self.other)
        # This combat scenario explicitly builds its ship; launch accounts no
        # longer receive a free starting fleet.
        other_home["ships"]["frigate"] = 1
        other_home["ships"]["frigate"] -= 1
        initial_ships = dict(other_home["ships"])
        attack = self.fleet("foreign-attack", self.other, other_home["id"], home["id"])
        self.world.account_delete(self.token, PASSWORD, "USUŃ KONTO")
        self.world._complete_fleet(attack)
        self.assertEqual(attack["status"], "returning")
        self.assertEqual(attack["cargo"], {"metal": 0, "crystal": 0, "fuel": 0})
        self.world._complete_fleet(attack)
        self.world._complete_fleet(attack)
        self.assertNotIn(attack["id"], self.world.data["fleets"])
        self.assertEqual(other_home["ships"]["frigate"], initial_ships["frigate"] + 1)
        self.assertEqual(self.world.data["players"][self.other]["swarm_crystals"], 0)

    def test_atomic_failure_rolls_back_password_sessions_and_recovery(self):
        self.recovery_code()
        before = self.snapshot()
        save = self.world._save

        def fail_after_snapshot(*args, **kwargs):
            save(*args, **kwargs)
            raise sqlite3.OperationalError("simulated storage failure")

        with patch.object(self.world, "_save", side_effect=fail_after_snapshot):
            with self.assertRaises(GameError) as error:
                self.world.account_password(self.token, PASSWORD, NEW_PASSWORD)
        self.assertEqual(error.exception.status, 503)
        self.assertEqual(self.snapshot(), before)

    def test_atomic_failure_rolls_back_delete_in_ram_and_sqlite(self):
        self.recovery_code()
        before = self.snapshot()
        save = self.world._save

        def fail_after_snapshot(*args, **kwargs):
            save(*args, **kwargs)
            raise sqlite3.OperationalError("simulated storage failure")

        with patch.object(self.world, "_save", side_effect=fail_after_snapshot):
            with self.assertRaises(GameError) as error:
                self.world.account_delete(self.token, PASSWORD, "USUŃ KONTO")
        self.assertEqual(error.exception.status, 503)
        self.assertEqual(self.snapshot(), before)


class AccountHTTPScenarios(unittest.TestCase):
    def setUp(self):
        self.world = World(":memory:", speed=1, now=START)
        self.world.data["alien"]["next_expansion_at"] = START + 10_000_000
        self.server = build_server(self.world, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.world.close()

    def request(self, path, payload=None, token=None, method="POST"):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        connection.request(method, path, json.dumps(payload or {}), headers)
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_http_recovery_change_password_logout_and_delete_contract(self):
        status, first = self.request("/api/register", {"name": "HTTP Player", "password": PASSWORD})
        self.assertEqual(status, 200)
        token = first["token"]
        self.assertFalse(first["state"]["account"]["recovery_code_enabled"])
        status, result = self.request("/api/account/recovery-code", {"password": "wrong-password"}, token)
        self.assertEqual(status, 403)
        status, result = self.request("/api/account/recovery-code", {"password": PASSWORD}, token)
        self.assertEqual(status, 200)
        code = result["recovery_code"]
        status, result = self.request("/api/recover", {"name": "HTTP Player", "recovery_code": code,
                                                     "new_password": NEW_PASSWORD})
        self.assertEqual(status, 200)
        recovered = result["token"]
        self.assertFalse(result["state"]["account"]["recovery_code_enabled"])
        status, _ = self.request("/api/account/recovery-code", {"password": NEW_PASSWORD}, token)
        self.assertEqual(status, 401)
        status, result = self.request("/api/account/password", {"password": NEW_PASSWORD,
                                                               "new_password": PASSWORD}, recovered)
        self.assertEqual(status, 200)
        current = result["token"]
        status, _ = self.request("/api/account/logout-others", {"password": PASSWORD}, current)
        self.assertEqual(status, 200)
        status, _ = self.request("/api/account/delete", {"password": PASSWORD, "confirmation": "no"}, current)
        self.assertEqual(status, 400)
        status, result = self.request("/api/account/delete", {"password": PASSWORD,
                                                             "confirmation": "USUŃ KONTO"}, current)
        self.assertEqual(status, 200)
        self.assertTrue(result["deleted"])
        status, _ = self.request("/api/state", token=current, method="GET")
        self.assertEqual(status, 401)

    def test_private_reauth_attempts_share_limit_across_account_routes(self):
        registered = self.world.register("Limited Player", PASSWORD)
        token = registered["token"]
        paths = ["/api/account/recovery-code", "/api/account/password", "/api/account/logout-others",
                 "/api/account/delete"]
        for index in range(12):
            status, _ = self.request(paths[index % len(paths)], {"password": "wrong-password"}, token)
            self.assertEqual(status, 403)
        status, result = self.request("/api/account/recovery-code", {"password": PASSWORD}, token)
        self.assertEqual(status, 429)
        self.assertFalse(result["ok"])
        self.assertFalse(self.world.account_status(registered["state"]["player"]["id"])["recovery_code_enabled"])

    def test_public_recovery_login_and_registration_share_ip_limit(self):
        registered = self.world.register("Public Limited", PASSWORD)
        code = self.world.account_recovery_code(registered["token"], PASSWORD)["recovery_code"]
        attempts = [
            ("/api/recover", {"name": "Public Limited", "recovery_code": "wrong-code",
                              "new_password": NEW_PASSWORD}, 401),
            ("/api/login", {"name": "Public Limited", "password": "wrong-password"}, 401),
            ("/api/register", {"name": "x", "password": PASSWORD}, 400),
        ]
        for index in range(12):
            path, payload, expected = attempts[index % len(attempts)]
            status, _ = self.request(path, payload)
            self.assertEqual(status, expected)
        status, result = self.request("/api/recover", {"name": "Public Limited", "recovery_code": code,
                                                     "new_password": NEW_PASSWORD})
        self.assertEqual(status, 429)
        self.assertFalse(result["ok"])
        self.assertEqual(self.world.authenticate(registered["token"]), registered["state"]["player"]["id"])
        self.assertTrue(self.world.account_status(registered["state"]["player"]["id"])["recovery_code_enabled"])


if __name__ == "__main__":
    unittest.main()

