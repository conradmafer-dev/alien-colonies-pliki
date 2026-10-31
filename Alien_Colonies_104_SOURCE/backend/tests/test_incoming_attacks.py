import copy
import unittest

from server.main import blank_ships
from tests.world_fixture import LocalTestWorld as World


class IncomingAttacksTests(unittest.TestCase):
    def setUp(self):
        self.world = World(":memory:", now=1000)
        self.players = []
        for index in range(3):
            result = self.world.register(f"Gracz{index}", "test-pass-123")
            player = self.world.authenticate(result["token"])
            self.players.append(player)
            self.world.data["players"][player]["protected_until"] = 0
        self.attacker, self.defender, self.other = self.players
        self.origin = self.world._owned(self.attacker)
        self.target = self.world._owned(self.defender)

    def tearDown(self):
        self.world.close()

    def flight(self, ident, *, owner=None, target=None, mission="attack", status="outbound", eta=1100):
        owner = owner or self.attacker
        home = self.origin if owner != "khar" else next(p for p in self.world.data["planets"].values() if p["owner_id"] == "khar")
        fleet = {"id": ident, "owner_id": owner, "origin_id": home["id"],
                 "target_id": (target or self.target)["id"], "mission": mission,
                 "status": status, "ships": {**blank_ships(), "frigate": 999},
                 "cargo": {"metal": 123456, "crystal": 456789, "fuel": 123}, "swarm_crystals": 177,
                 "seconds": 100, "arrives_at": eta, "started_at": eta - 100}
        self.world.data["fleets"][ident] = fleet
        return fleet

    def test_only_enemy_outbound_attacks_on_own_planets_sorted_without_secrets(self):
        self.flight("later", eta=1200)
        old = self.flight("swarm", owner="khar", eta=1100)
        del old["started_at"]  # Existing saves recover a real start from duration.
        self.flight("returning", status="returning")
        self.flight("scout", mission="scout")
        self.flight("transport", mission="transport")
        self.flight("colonize", mission="colonize")
        self.flight("friendly", owner=self.defender)
        self.flight("other-target", target=self.world._owned(self.other))
        before = copy.deepcopy(self.world.data["fleets"])
        state = self.world.state(self.defender)
        alerts = state["incoming_attacks"]
        self.assertEqual([a["id"] for a in alerts], ["swarm", "later"])
        expected = {"id", "attacker_name", "origin_name", "target_name", "origin_id", "target_id", "arrives_at", "started_at", "seconds"}
        self.assertTrue(all(set(alert) == expected for alert in alerts))
        self.assertEqual(alerts[0]["attacker_name"], "Rój Khar")
        self.assertEqual(alerts[0]["started_at"], 1000)
        self.assertEqual(alerts[1]["attacker_name"], "Gracz0")
        self.assertTrue(all(not {"ships", "cargo", "swarm_crystals"} & set(f) for f in state["alien"]["fleets"]))
        self.assertEqual(before, self.world.data["fleets"])

    def test_launch_creates_one_alarm_and_replay_does_not_duplicate(self):
        payload = {"type": "fleet", "mission": "attack", "target_id": self.target["id"],
                   "ships": {"frigate": 1}, "request_id": "launch-unique"}
        first = self.world.action(self.attacker, payload)
        self.world.action(self.attacker, payload)
        state = self.world.state(self.defender)
        self.assertEqual(len(state["incoming_attacks"]), 1)
        reports = [r for r in state["reports"] if r["title"] == "Nadciąga wroga flota"]
        self.assertEqual(len(reports), 1)
        self.assertIn(self.target["name"], reports[0]["text"])
        alert = state["incoming_attacks"][0]
        self.assertEqual(alert["arrives_at"], first["state"]["fleets"][0]["arrives_at"])
        fleet = self.world.data["fleets"][alert["id"]]
        self.world._return(fleet)
        self.assertFalse(self.world.state(self.defender)["incoming_attacks"])

    def test_alert_disappears_when_target_no_longer_belongs_to_player(self):
        self.flight("reassigned")
        self.assertEqual(len(self.world.state(self.defender)["incoming_attacks"]), 1)
        # Provide a second colony so state is still meaningful after home loss.
        second = next(p for p in self.world.data["planets"].values() if not p["owner_id"])
        second["owner_id"], second["owner_type"] = self.defender, "player"
        self.world.data["players"][self.defender]["home_id"] = second["id"]
        self.target["owner_id"], self.target["owner_type"] = self.other, "player"
        self.assertFalse(self.world.state(self.defender)["incoming_attacks"])
        self.assertEqual(len(self.world.state(self.other)["incoming_attacks"]), 1)


if __name__ == "__main__":
    unittest.main()
