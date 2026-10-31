"""Valuation and authenticated HTTP regressions using isolated worlds only."""
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import app
import megastructures
import ogame_economy
import rankings
from races import UNIQUE_BUILDINGS

NOW = 2_000_000_000.0
PASSWORD = "ranking-regression-password"


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.w = app.World(":memory:", now=NOW)
        self.addCleanup(self.w.close)
        self.accounts = [self.w.register(name, PASSWORD) for name in ("Alpha", "Zulu")]
        self.a, self.b = [x["state"]["player"]["id"] for x in self.accounts]
        for owner, race in ((self.a, "zetans"), (self.b, "symbionts")):
            self.w.action(owner, {"type": "choose_race", "race_id": race})
            self.zero(owner)

    def zero(self, owner):
        planet = self.w._owned(owner)
        planet["buildings"] = dict.fromkeys(planet["buildings"], 0)
        planet["ships"] = dict.fromkeys(planet["ships"], 0)
        planet["defenses"] = dict.fromkeys(planet.get("defenses", {}), 0)
        self.w._player(owner)["research"] = dict.fromkeys(self.w._player(owner)["research"], 0)
        planet["resources"] = dict.fromkeys(app.RESOURCES, 10_000_000.)
        return planet

    def own(self, owner=None, category="total"):
        return rankings.view(self.w, owner or self.a, category)["self"]

    def test_cumulative_levels_use_real_prices_and_round_only_after_summing(self):
        p = self.w._owned(self.a)
        p["buildings"].update(metal_mine=3, shipyard=1)
        self.w._player(self.a)["research"]["propulsion"] = 2
        p["ships"].update(scout=2, cargo=3)
        p["defenses"]["phase_sentinel"] = 2
        self.assertEqual(rankings._level_value("buildings", "metal_mine", (60, 15, 0), 3), 355)
        base = self.w._specs(self.a, "research")["propulsion"][2]
        research = sum(sum(ogame_economy.cost("research", "propulsion", base, level).values()) for level in (0, 1))
        result = self.own()
        self.assertEqual(result["scores"]["buildings"], (355 + 700) // 1000)
        self.assertEqual(result["scores"]["research"], research // 1000)
        self.assertEqual(result["scores"]["fleet"], 14)
        self.assertEqual(result["scores"]["defense"], 16)
        self.assertEqual(result["score"], (355 + 700 + research + 14000 + 16000) // 1000)

    def test_stockpiles_crystals_queues_cargo_and_client_like_fields_have_no_value(self):
        initial = self.own()["score"]
        p = self.w._owned(self.a)
        p["resources"] = dict.fromkeys(app.RESOURCES, 8e15)
        p["queue"] = [{"kind": "ship", "count": 1000, "cost": dict.fromkeys(app.RESOURCES, 1e9)}]
        self.w._player(self.a).update(swarm_crystals=1000000, score=999999999)
        p["planned_queues"] = {"build": [{"key": "metal_mine", "level": 100}]}
        self.w.data["fleets"]["cargo-only"] = {"owner_id": self.a, "ships": {}, "cargo": dict.fromkeys(app.RESOURCES, 1e9), "swarm_crystals": 1000}
        self.assertEqual(self.own()["score"], initial)

    def test_all_flight_states_and_alliance_references_count_each_ship_once(self):
        p = self.w._owned(self.a)
        p["ships"]["frigate"] = 3
        self.assertEqual(self.own(category="fleet")["score"], 12)
        p["ships"]["frigate"] = 1
        fleet = {"owner_id": self.a, "ships": {"frigate": 2}, "mission": "alliance_defense"}
        self.w.data["fleets"]["support"] = fleet
        self.w.data["alliance_operations"]["operation"] = {"participants": [copy.deepcopy(fleet)]}
        for state in ("outbound", "holding", "stationed", "returning"):
            fleet["status"] = state
            self.assertEqual(self.own(category="fleet")["score"], 12, state)
            self.assertEqual(self.own(self.b, "fleet")["score"], 0)
        fleet["ships"]["frigate"] = 1
        self.assertEqual(self.own(category="fleet")["score"], 8)

    def test_real_dispatch_and_return_preserve_fleet_points(self):
        origin, target = self.w._owned(self.a), self.w._owned(self.b)
        origin["ships"]["scout"] = 3
        self.w._capture_planetary_intel(self.a, target)
        self.w.action(self.a, {"type": "fleet", "mission": "scout", "planet_id": origin["id"], "target_id": target["id"], "ships": {"scout": 2}, "cargo": {}})
        self.assertEqual(self.own(category="fleet")["score"], 3)
        fleet = next(f for f in self.w.data["fleets"].values() if f["owner_id"] == self.a)
        self.w.now = fleet["arrives_at"]
        self.w._complete_fleet(fleet)
        self.assertEqual(self.own(category="fleet")["score"], 3)
        self.w.now = fleet["arrives_at"]
        self.w._complete_fleet(fleet)
        self.assertEqual(self.own(category="fleet")["score"], 3)

    def test_research_is_global_and_foreign_colony_buildings_move_to_new_owner(self):
        colony = next(p for p in self.w.data["planets"].values() if p["owner_type"] == "empty")
        foreign_key, meta = next(iter(UNIQUE_BUILDINGS["zetans"].items()))
        colony.update(owner_type="player", owner_id=self.a, buildings={foreign_key: 3}, ships={}, defenses={})
        expected = rankings._level_value("buildings", foreign_key, tuple(meta["spec"][2]), 3) // 1000
        self.w._player(self.a)["research"]["propulsion"] = 3
        before_research = self.own()["scores"]["research"]
        self.assertEqual(self.own()["scores"]["buildings"], expected)
        colony["owner_id"] = self.b
        self.assertEqual(self.own()["scores"]["buildings"], 0)
        self.assertEqual(self.own(self.b)["scores"]["buildings"], expected)
        self.assertEqual(self.own()["scores"]["research"], before_research)

    def test_megastructures_count_completed_stages_not_pending_costs(self):
        project = self.w._player(self.a)["megastructure"]
        project.update(dyson_stage=2, gate_level=1, queue={"level": 3, "cost": [1e9] * 3})
        expected = sum(sum(s[1]) for s in megastructures.STAGES[:2]) + sum(megastructures.GATE[1])
        self.assertEqual(self.own()["scores"]["buildings"], expected // 1000)

    def test_read_is_immutable_and_does_not_publish_private_details(self):
        before = copy.deepcopy(self.w.data)
        changes = self.w.db.total_changes
        result = rankings.view(self.w, self.a)
        self.assertEqual(self.w.data, before)
        self.assertEqual(self.w.db.total_changes, changes)
        allowed = {"player_id", "name", "race_id", "position", "score", "scores", "is_self"}
        for row in result["items"]:
            self.assertEqual(set(row), allowed)
        self.assertNotIn("khar", [r["player_id"] for r in result["items"]])

    def test_paging_my_position_ties_filters_and_removed_accounts(self):
        self.w._owned(self.a)["ships"]["scout"] = 8
        template = copy.deepcopy(self.w._player(self.b))
        for index in range(105):
            owner = f"rank-fixture-{index:03}"
            self.w.data["players"][owner] = {**copy.deepcopy(template), "id": owner, "name": f"Pilot {index:03}"}
        result = rankings.view(self.w, self.b, around_me=True)
        self.assertEqual(result["players_total"], 107)
        self.assertEqual(result["pages"], 3)
        self.assertEqual(result["page"], 3)
        self.assertEqual(result["self"]["position"], 107)
        self.assertTrue(any(x["is_self"] for x in result["items"]))
        top = rankings.view(self.w, self.a, "fleet")
        self.assertEqual(top["items"][0]["player_id"], self.a)
        self.assertEqual(len(top["items"]), 50)
        self.assertEqual(rankings.view(self.w, self.a, page=999999)["page"], 3)
        self.w.data["players"].pop(self.b)
        self.assertEqual(rankings.view(self.w, self.a)["players_total"], 106)

    def test_race_bonuses_do_not_change_catalogue_unit_points(self):
        for owner in (self.a, self.b):
            self.w._owned(owner)["ships"]["frigate"] = 10
        self.assertEqual(self.own(self.a, "fleet")["score"], 40)
        self.assertEqual(self.own(self.b, "fleet")["score"], 40)

    def test_points_arrive_only_when_a_real_paid_project_finishes(self):
        planet = self.w._owned(self.a)
        # A shipyard level is worth a whole point after completion; the
        # in-progress prepaid resources must never count as finished assets.
        planet["buildings"]["shipyard"] = 1
        before = self.own()["score"]
        self.w.action(self.a, {"type": "build", "planet_id": planet["id"], "key": "shipyard"})
        self.assertEqual(self.own()["score"], before)
        end = planet["queue"][0]["ends_at"]
        self.w.advance(end)
        self.assertEqual(planet["buildings"]["shipyard"], 2)
        self.assertEqual(self.own()["score"], 2)

    def test_existing_account_scores_survive_restart_without_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "existing.sqlite3"
            w = app.World(path, now=NOW)
            account = w.register("Existing Empire", PASSWORD)
            owner = account["state"]["player"]["id"]
            w.action(owner, {"type": "choose_race", "race_id": "automatons"})
            w._owned(owner)["ships"]["cruiser"] = 7
            w._save()
            before = rankings.view(w, owner)["self"]["scores"]
            w.close()
            w = app.World(path, now=NOW)
            try:
                self.assertEqual(w.authenticate(account["token"]), owner)
                self.assertEqual(rankings.view(w, owner)["self"]["scores"], before)
                self.assertEqual(w._owned(owner)["ships"]["cruiser"], 7)
                self.assertFalse((Path(tmp) / "reset-backups").exists())
            finally:
                w.close()


class RankingHTTPTests(unittest.TestCase):
    def setUp(self):
        self.clock = patch("app.time.time", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.w = app.World(":memory:", now=NOW)
        self.account = self.w.register("HTTP Rank Pilot", PASSWORD)
        self.server = app.build_server(self.w, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)
        self.w.close()

    def get(self, path="/api/ranking", token=True):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
        headers = {"X-PGR-Client-Version": "92", "Accept-Language": "en"}
        if token:
            headers["Authorization"] = "Bearer " + self.account["token"]
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        body = json.loads(response.read())
        status = response.status
        connection.close()
        return status, body

    def test_authenticated_endpoint_and_categories(self):
        self.assertEqual(self.get(token=False)[0], 401)
        for category in rankings.CATEGORIES:
            code, body = self.get("/api/ranking?category=" + category)
            self.assertEqual(code, 200, body)
            self.assertEqual(body["category"], category)
            self.assertEqual(body["unit"], 1000)
            self.assertTrue(body["self"]["is_self"])

    def test_malformed_params_do_not_mutate_data(self):
        for query in ("page=0", "page=-1", "page=nan", "page=1&page=2", "category=secret", "category=", "around_me=2", "score=9999999", "page=9999999999999"):
            before = copy.deepcopy(self.w.data)
            code, body = self.get("/api/ranking?" + query)
            self.assertEqual(code, 400, (query, body))
            self.assertEqual(self.w.data, before)

    def test_logout_revokes_ranking_and_repeated_reads_are_stable(self):
        first = self.get()[1]
        self.assertEqual(first, self.get()[1])
        self.w.logout(self.account["token"])
        self.assertEqual(self.get()[0], 401)


if __name__ == "__main__":
    unittest.main()
