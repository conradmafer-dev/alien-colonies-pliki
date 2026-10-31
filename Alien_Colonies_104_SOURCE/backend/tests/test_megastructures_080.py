"""Real construction, atomic energy accounting, offline windows and fleet returns."""
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path

from server import technology
from server.main import GameError
from server.megastructures import empty_project
from tests.world_fixture import LocalTestWorld as World


class MegastructureTests(unittest.TestCase):
    def setUp(self):
        self.world = World(":memory:", speed=1000, now=1900000000)
        account = self.world.register("Mega080", "test-password-123")
        self.pid = account["state"]["player"]["id"]
        self.world.action(self.pid, {"type": "choose_race", "race_id": "zetans"})
        self.player = self.world.data["players"][self.pid]
        self.planet = self.world.data["planets"][self.player["home_id"]]
        self.planet["resources"] = dict.fromkeys(("metal", "crystal", "fuel"), 1000000000)
        for key in self.planet["buildings"]:
            self.planet["buildings"][key] = 12 if key in ("lab", "shipyard", "power_plant") else 1
        self.player["research"].update({k: v["max_level"] for k, v in technology.RESEARCH.items()})
        self.planet["ships"].update(scout=10, frigate=10, cargo=10, colonizer=2)
        self.target = next(p for p in self.world.data["planets"].values() if p["owner_type"] == "empty" and p["galaxy_id"] == "g6")

    def tearDown(self):
        self.world.db.close()

    def act(self, **payload):
        return self.world.action(self.pid, payload)

    def ready(self, target=None):
        project = empty_project()
        project.update(origin_id=self.planet["id"], dyson_stage=4, gate_level=1)
        self.player["megastructure"] = project
        project["energy"] = self.world._mega_profile(self.player)["capacity"]
        self.world._capture_planetary_intel(self.pid, target or self.target)
        self.act(type="tunnel_open", target_id=(target or self.target)["id"])
        self.world.advance(project["window"]["ready_at"])
        return project

    def payload(self, **changes):
        result = {"type": "fleet", "mission": "scout", "target_id": self.target["id"],
                  "ships": {"scout": 1}, "travel_mode": "tunnel"}
        result.update(changes)
        return result

    def test_actual_four_stage_construction_and_gate_unlock(self):
        with self.assertRaises(GameError):
            self.act(type="megabuild", key="wormhole")
        project = self.player["megastructure"]
        for stage in range(1, 5):
            before = self.planet["resources"]["metal"]
            entry = self.world._mega_state(self.pid, self.planet)["projects"][0]
            self.act(type="megabuild", key="dyson", request_id="stage-" + str(stage))
            self.assertEqual(self.planet["resources"]["metal"], before - entry["cost"]["metal"])
            self.assertEqual(project["dyson_stage"], stage - 1)
            self.assertFalse(self.planet["queue"])
            self.world.advance(project["queue"]["ends_at"])
            self.assertEqual(project["dyson_stage"], stage)
        self.act(type="megabuild", key="wormhole")
        self.world.advance(project["queue"]["ends_at"])
        self.assertEqual(project["gate_level"], 1)
        self.assertGreater(self.world.energy(self.planet)["supply"], 100000)
        self.assertGreater(project["energy"], 0)

    def test_cancel_refunds_once_and_retains_completed_stages(self):
        before = copy.deepcopy(self.planet["resources"])
        self.act(type="megabuild", key="dyson")
        project = self.player["megastructure"]
        queue = copy.deepcopy(project["queue"])
        payload = {"type": "megacancel", "queue_id": queue["id"], "request_id": "cancel-080"}
        self.world.action(self.pid, payload)
        self.assertEqual(before, self.planet["resources"])
        self.assertEqual(project["origin_id"], "")
        self.world.action(self.pid, payload)
        self.assertEqual(before, self.planet["resources"])

    def test_stabilization_is_real_time_and_window_has_fixed_destination(self):
        project = self.ready()
        self.assertEqual(project["window"]["ready_at"] - project["window"]["opened_at"], 60)
        self.assertEqual(project["window"]["closes_at"] - project["window"]["ready_at"], 300)
        other = next(p for p in self.world.data["planets"].values() if p["owner_type"] == "empty" and p["id"] != self.target["id"])
        with self.assertRaises(GameError):
            self.world.preview(self.pid, self.payload(target_id=other["id"]))
        with self.assertRaises(GameError):
            self.act(type="tunnel_open", target_id=other["id"])
        self.act(type="tunnel_close")
        self.act(type="tunnel_open", target_id=self.target["id"])
        with self.assertRaises(GameError):
            self.world.preview(self.pid, self.payload())

    def test_close_does_not_strand_fleet_and_duplicate_send_costs_once(self):
        project = self.ready()
        payload = self.payload(request_id="flight-080", energy_cost=0, seconds=1)
        preview = self.world.preview(self.pid, payload)
        self.assertEqual(preview["seconds"], 120)
        self.assertEqual(preview["fuel_cost"], 0)
        before_energy = project["energy"]
        before_ships = self.planet["ships"]["scout"]
        self.world.action(self.pid, payload)
        self.assertEqual(project["energy"], before_energy - preview["tunnel"]["energy_cost"])
        paid = project["energy"]
        self.world.action(self.pid, payload)
        self.assertEqual(project["energy"], paid)
        self.assertEqual(len([f for f in self.world.data["fleets"].values() if f["owner_id"] == self.pid]), 1)
        self.act(type="tunnel_close")
        self.world.advance(self.world.now + 241)
        self.assertEqual(self.planet["ships"]["scout"], before_ships)
        self.assertFalse([f for f in self.world.data["fleets"].values() if f["owner_id"] == self.pid])

    def test_offline_energy_matches_segmented_advancement_and_window_expiry(self):
        project = self.ready()
        before = project["energy"]
        rate = self.world._mega_profile(self.player)["charge_per_second"]
        upkeep = project["window"]["upkeep_per_second"]
        start = self.world.now
        self.world.advance(start + 900)
        expected = min(self.world._mega_profile(self.player)["capacity"], before + rate * 900 - upkeep * 300)
        self.assertAlmostEqual(project["energy"], expected, places=4)
        self.assertIsNone(project["window"])
        one_shot = project["energy"]
        self.world.now = start
        self.world.data["last_update"] = start
        project["energy"] = before
        project["window"] = {"id": "test", "opened_at": start - 60, "ready_at": start,
                             "closes_at": start + 300, "target_id": self.target["id"], "upkeep_per_second": upkeep}
        for seconds in range(30, 901, 30):
            self.world.advance(start + seconds)
        self.assertAlmostEqual(project["energy"], one_shot, places=4)

    def test_insufficient_open_and_transfer_are_atomic_and_keep_upkeep_reserved(self):
        project = self.ready()
        profile = self.world._mega_profile(self.player)
        project["energy"] = (project["window"]["upkeep_per_second"] - profile["charge_per_second"]) * 300
        before = copy.deepcopy(self.planet["ships"])
        energy = project["energy"]
        payload = self.payload(allow_unaffordable=True)
        preview = self.world.preview(self.pid, payload)
        self.assertFalse(preview["affordable"])
        self.assertGreater(preview["tunnel"]["energy_shortfall"], 0)
        with self.assertRaises(GameError):
            self.world.action(self.pid, payload)
        self.assertEqual(before, self.planet["ships"])
        self.assertEqual(energy, project["energy"])
        self.act(type="tunnel_close")
        project["energy"] = 1
        with self.assertRaises(GameError):
            self.act(type="tunnel_open", target_id=self.target["id"])
        self.assertEqual(project["energy"], 1)

    def test_mass_and_cargo_increase_energy_and_cannot_be_spoofed(self):
        self.ready()
        first = self.world.preview(self.pid, self.payload())
        second = self.world.preview(self.pid, self.payload(ships={"scout": 2}))
        self.assertGreater(second["tunnel"]["energy_cost"], first["tunnel"]["energy_cost"])
        empty = self.world.preview(self.pid, self.payload(mission="colonize", ships={"colonizer": 1}))
        loaded = self.world.preview(self.pid, self.payload(mission="colonize", ships={"colonizer": 1}, cargo={"metal": 100}))
        self.assertGreater(loaded["tunnel"]["energy_cost"], empty["tunnel"]["energy_cost"])

    def test_attack_keeps_new_player_protection_and_real_warning(self):
        bob = self.world.register("Defender080", "test-password-123")["state"]
        bid = bob["player"]["id"]
        target = self.world.data["planets"][bob["home_id"]]
        self.ready(target)
        payload = self.payload(mission="attack", target_id=target["id"], ships={"frigate": 1})
        with self.assertRaises(GameError):
            self.world.action(self.pid, payload)
        self.world.data["players"][bid]["protected_until"] = 0
        self.world.action(self.pid, payload)
        attacks = self.world.state(bid)["incoming_attacks"]
        self.assertEqual(len(attacks), 1)
        self.assertEqual(attacks[0]["arrives_at"] - self.world.now, 120)

    def test_restart_preserves_flight_return_reservation_and_closes_offline_window(self):
        self.ready()
        self.world.action(self.pid, self.payload())
        self.world._save()
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "restart.sqlite3")
            dest = sqlite3.connect(path)
            self.world.db.backup(dest)
            dest.close()
            restored = World(path, speed=1000, now=self.world.now + 900)
            try:
                self.assertFalse([f for f in restored.data["fleets"].values() if f["owner_id"] == self.pid])
                self.assertEqual(restored.data["planets"][self.planet["id"]]["ships"]["scout"], 10)
                self.assertIsNone(restored.data["players"][self.pid]["megastructure"]["window"])
            finally:
                restored.db.close()

    def test_cannot_use_another_colony_as_gateway_origin(self):
        self.ready()
        colony = next(p for p in self.world.data["planets"].values() if p["owner_type"] == "empty" and p["id"] != self.target["id"])
        colony.update(owner_id=self.pid, owner_type="player")
        colony["ships"]["scout"] = 1
        before = copy.deepcopy(self.player["megastructure"])
        with self.assertRaises(GameError):
            self.world.action(self.pid, self.payload(planet_id=colony["id"]))
        with self.assertRaises(GameError):
            self.act(type="tunnel_close", planet_id=colony["id"])
        self.assertEqual(before, self.player["megastructure"])


if __name__ == "__main__":
    unittest.main()
