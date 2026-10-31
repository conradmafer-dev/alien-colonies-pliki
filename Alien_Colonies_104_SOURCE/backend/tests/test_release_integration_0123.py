"""Cross-release regressions for the live-world 0.12.3 integration.

Exercise disk migrations and real authenticated HTTP/paid missions, where the
ring/activity release intersects the later signup and colony-capture releases.
"""
import copy
import http.client
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from backups import SQLiteBackups
from inactivity import ACTIVITY_HEADER, INACTIVE_AFTER_SECONDS

NOW = 1_900_000_000.0
DAY = 86400
PASSWORD = "release-integration-password"


def legacy_map(world):
    """Restore the topology actually running before the additive migration."""
    data = copy.deepcopy(world.data)
    data["systems"] = [s for s in data["systems"] if s["ring_index"] == 0]
    retained = {pid for system in data["systems"] for pid in system["planet_ids"]}
    data["planets"] = {pid: p for pid, p in data["planets"].items() if pid in retained}
    for system in data["systems"]:
        for key in ("ring_index", "ring_order", "ring_size", "ring_radius"):
            system.pop(key)
    data["galaxy_schema_version"] = 1
    data.pop("activity_schema_version", None)
    data.pop("activity_policy_started_at", None)
    world.data = data
    world._navigation_cache = None


class ReleaseMigrationIntegration(unittest.TestCase):
    def test_failed_required_backup_prevents_world_or_account_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "integration.sqlite3")
            initial = app.World(database, now=NOW)
            legacy_map(initial)
            owner = initial.register("BackupOwner", PASSWORD)["state"]["player"]["id"]
            initial._player(owner).pop("last_active_at", None)
            initial.close()
            with sqlite3.connect(database) as connection:
                before = connection.execute("SELECT body FROM snapshot WHERE id=1").fetchone()[0]
                accounts = connection.execute("SELECT * FROM accounts ORDER BY id").fetchall()
            with patch.object(SQLiteBackups, "maybe_create", return_value=None) as backup:
                with self.assertRaises(OSError):
                    app.World(database, now=NOW + DAY)
                self.assertTrue(any(call.kwargs.get("force") for call in backup.call_args_list))
            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute("SELECT body FROM snapshot WHERE id=1").fetchone()[0], before)
                self.assertEqual(connection.execute("SELECT * FROM accounts ORDER BY id").fetchall(), accounts)
            restored = app.World(database, now=NOW + DAY)
            try:
                self.assertEqual(len(restored.data["systems"]), 930)
                self.assertEqual(restored._player(owner)["last_active_at"], NOW + DAY)
                preserved_backup = False
                for candidate in (Path(directory) / "backups").glob("*.sqlite3"):
                    with sqlite3.connect(candidate) as connection:
                        preserved_backup |= connection.execute("SELECT body FROM snapshot WHERE id=1").fetchone()[0] == before
                self.assertTrue(preserved_backup, "The committed legacy save must exist in a verified backup")
            finally:
                restored.close()

    def test_expansion_recounts_real_half_occupancy_without_moving_existing_homes(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "occupancy.sqlite3")
            initial = app.World(database, now=NOW)
            legacy_map(initial)
            owner = initial.register("OriginalOwner", PASSWORD)["state"]["player"]["id"]
            local = [p for p in initial.data["planets"].values() if p["galaxy_id"] == "g1"]
            legacy_total = len(local)
            occupied = sum(p["owner_type"] != "empty" for p in local)
            for planet in (p for p in local if p["owner_type"] == "empty"):
                if occupied * 2 >= legacy_total:
                    break
                planet.update(owner_type="player", owner_id=owner)
                occupied += 1
            before = initial.register("BeforeExpansion", PASSWORD)["state"]
            self.assertEqual(before["planet_galaxy_id"], "g2")
            home_ids = {pid: player["home_id"] for pid, player in initial.data["players"].items()}
            colonies = {p["id"]: p["owner_id"] for p in initial.data["planets"].values() if p["owner_type"] == "player"}
            initial.close()
            expanded = app.World(database, now=NOW)
            try:
                self.assertGreater(len([p for p in expanded.data["planets"].values() if p["galaxy_id"] == "g1"]), legacy_total)
                after = expanded.register("AfterExpansion", PASSWORD)["state"]
                self.assertEqual(after["planet_galaxy_id"], "g1")
                for pid, home_id in home_ids.items():
                    self.assertEqual(expanded._player(pid)["home_id"], home_id)
                for planet_id, owner_id in colonies.items():
                    self.assertEqual(expanded.data["planets"][planet_id]["owner_id"], owner_id)
                self.assertTrue(after["colonization_capture"]["enabled"])
            finally:
                expanded.close()


class ReleaseCaptureActivityIntegration(unittest.TestCase):
    def setUp(self):
        self.world = app.World(":memory:", now=NOW)
        self.addCleanup(self.world.close)
        self.tokens = {}
        self.owners = []
        for name, race in (("InactiveSettler", "zetans"), ("ActiveCapturer", "automatons")):
            result = self.world.register(name, PASSWORD)
            owner = result["state"]["player"]["id"]
            self.tokens[owner] = result["token"]
            self.owners.append(owner)
            self.world.action(owner, {"type": "choose_race", "race_id": race})
            self.world._player(owner)["protected_until"] = 0
            home = self.world._owned(owner)
            home["resources"] = dict.fromkeys(app.RESOURCES, 1_000_000.)
            home["ships"]["colonizer"] = 1
        self.old, self.new = self.owners
        inner = next(system for system in self.world.data["systems"]
                     if system["galaxy_id"] == "g1" and system["ring_index"] == 2)
        self.colony = next(self.world.data["planets"][pid] for pid in inner["planet_ids"]
                           if self.world.data["planets"][pid]["owner_type"] == "empty")
        self.colony.update(owner_type="player", owner_id=self.old)
        for key in ("metal_mine", "crystal_mine", "refinery", "power_plant"):
            self.colony["buildings"][key] = 2
        self.colony["buildings"]["phase_matrix"] = 3
        self.world._ensure_race_buildings(self.colony)
        self.colony["resources"] = {"metal": 100., "crystal": 200., "fuel": 300.}
        alien = self.world.data["alien"]
        alien["next_expansion_at"] = NOW + 365 * DAY
        alien["swarm_next_raid_at"] = NOW + 365 * DAY
        alien["swarm_next_colonization_by_galaxy"] = dict.fromkeys(app.GALAXIES_BY_ID, NOW + 365 * DAY)

    def capture_after_inactivity(self):
        self.world.advance(NOW + 8 * DAY)
        self.assertEqual(self.world.production(self.colony), dict.fromkeys(app.RESOURCES, 0.0))
        # Keep the fixture below storage capacity: these assertions exercise
        # inactivity and ownership clocks, rather than full warehouses.
        self.colony["resources"] = {"metal": 100., "crystal": 200., "fuel": 300.}
        stock = dict(self.colony["resources"])
        self.world.mark_player_activity(self.new)
        self.world._capture_planetary_intel(self.new, self.colony)
        payload = {"type": "fleet", "mission": "colonize", "target_id": self.colony["id"],
                   "ships": {"colonizer": 1}}
        quote = self.world.preview(self.new, payload)
        self.assertEqual(quote["colonization_kind"], "capture")
        self.assertIn(self.colony["system_id"], quote["route"]["system_ids"])
        self.world.action(self.new, payload)
        flight = next(f for f in self.world.data["fleets"].values() if f["owner_id"] == self.new)
        arrival = flight["arrives_at"]
        self.world.advance(arrival)
        self.assertEqual(self.colony["owner_id"], self.new)
        self.assertEqual(self.colony["resources"], stock, "Paused old ownership must grant no income before arrival")
        return arrival, stock

    def test_captured_inactive_inner_colony_resumes_only_under_new_owners_clock(self):
        arrival, stock = self.capture_after_inactivity()
        state = self.world.state(self.new, self.colony["id"])
        self.assertFalse(state["production_status"]["paused"])
        self.assertEqual(state["buildings"]["phase_matrix"], 3)
        self.assertIn("phase_matrix", [item["key"] for item in state["inactive_racial_buildings"]])
        rates = self.world.production(self.colony)
        self.assertTrue(all(rate > 0 for rate in rates.values()))
        self.world.advance(arrival + 3600)
        for resource in app.RESOURCES:
            self.assertAlmostEqual(self.colony["resources"][resource], stock[resource] + rates[resource])
        self.assertTrue(self.world._production_status(self.old)["paused"])
        self.assertEqual(self.world._player(self.old)["last_active_at"], NOW)

    def test_old_android_state_refresh_after_capture_falls_home_and_resumes_only_on_input(self):
        arrival, _ = self.capture_after_inactivity()
        server = app.build_server(self.world, port=0, update_policy=app.UpdatePolicy(min_version_code=1))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def request(planet_id, active, version):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            try:
                headers = {"Authorization": "Bearer " + self.tokens[self.old], "X-PGR-Client-Version": str(version)}
                if active:
                    headers[ACTIVITY_HEADER] = "1"
                connection.request("GET", "/api/state?planet_id=" + planet_id, headers=headers)
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally:
                connection.close()
        try:
            with patch("app.time.time", return_value=arrival):
                for version in (68, 69, 70):
                    status, response = request(self.colony["id"], False, version)
                    self.assertEqual(status, 200)
                    self.assertEqual(response["state"]["planet_id"], self.world._player(self.old)["home_id"])
                    self.assertEqual(response["state"]["selected_planet_lost"]["planet_id"], self.colony["id"])
                    self.assertTrue(response["state"]["production_status"]["paused"])
                stock = dict(self.world._owned(self.old)["resources"])
                self.assertEqual(request("unknown-planet", True, 70)[0], 403)
                self.assertEqual(self.world._player(self.old)["last_active_at"], NOW)
                status, response = request(self.colony["id"], True, 70)
                self.assertEqual(status, 200)
                self.assertFalse(response["state"]["production_status"]["paused"])
                self.assertEqual(self.world._player(self.old)["last_active_at"], arrival)
                self.assertEqual(self.world._owned(self.old)["resources"], stock)
                self.assertEqual(response["state"]["production_status"]["stops_at"], arrival + INACTIVE_AFTER_SECONDS)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(3)


if __name__ == "__main__":
    unittest.main()
