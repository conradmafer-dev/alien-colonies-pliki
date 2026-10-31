"""Exact reward time, offline settlement and transactional currency regressions."""
import copy
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import app
import rankings

NOW = 2_000_000_000.0
DAY = 86400
PASSWORD = "ranking-rewards104-test-password"


class RankingRewardTimeTests(unittest.TestCase):
    def setUp(self):
        self.w = app.World(":memory:", now=NOW)
        self.addCleanup(self.w.close)
        account = self.w.register("RewardAlpha", PASSWORD)
        owner = account["state"]["player"]["id"]
        template = self.w._player(owner)
        self.rows = []
        for index in range(31):
            pid = owner if index == 0 else "reward-fixture-" + str(index)
            if index:
                self.w.data["players"][pid] = {**copy.deepcopy(template), "id": pid, "name": f"Reward{index:02}"}
            self.rows.append({"player_id": pid, "name": self.w._player(pid)["name"], "race_id": "zetans",
                "scores": {"total": 100-index, "buildings": 100-index, "fleet": index, "research": 0, "defense": 0}})
        self.mock_rows = patch("rankings._rows", return_value=self.rows)
        self.mock_rows.start()
        self.addCleanup(self.mock_rows.stop)
        self.owner = owner

    def settle(self, seconds):
        with self.w._atomic():
            self.w.now += seconds
            rankings.accrue_rewards(self.w, self.w.now)

    def move(self, owner, position):
        ordered = rankings._overall(self.rows)
        row = next(row for row in ordered if row["player_id"] == owner)
        ordered.remove(row)
        ordered.insert(position-1, row)
        for index, item in enumerate(ordered):
            item["scores"]["total"] = 100-index

    def reset_progress(self):
        self.w.now = NOW
        self.w.data["ranking_reward_settled_ms"] = round(NOW * 1000)
        for player in self.w.data["players"].values():
            player.update(ranking_reward_units=0, ranking_reward_total=0, swarm_crystals=0, reports=[])

    def test_all_bracket_boundaries_include_11_to_30_and_pause_at_31(self):
        for position, days in ((1,3),(2,5),(3,5),(4,7),(10,7),(11,14),(30,14),(31,0)):
            with self.subTest(position=position):
                value = rankings.reward_state(self.w, self.rows[position-1]["player_id"])
                self.assertEqual(value["position"], position)
                self.assertEqual(value["days_per_crystal"], days)
                self.assertEqual(value["active"], bool(days))
                self.assertEqual(value["remaining_seconds"], days*DAY if days else None)

    def test_full_crystal_at_exact_threshold_not_one_millisecond_early(self):
        for position, days in ((1,3),(2,5),(4,7),(11,14),(30,14)):
            with self.subTest(position=position):
                self.reset_progress()
                owner = self.rows[position-1]["player_id"]
                self.settle(days*DAY-0.001)
                self.assertEqual(self.w._player(owner)["swarm_crystals"], 0)
                self.settle(0.001)
                self.assertEqual(self.w._player(owner)["swarm_crystals"], 1)
                self.assertEqual(self.w._player(owner)["ranking_reward_units"], 0)
                self.settle(0)
                self.assertEqual(self.w._player(owner)["swarm_crystals"], 1)

    def test_fraction_is_preserved_when_moving_from_first_to_second(self):
        self.settle(1.5*DAY)
        self.assertEqual(rankings.reward_state(self.w, self.owner)["progress"], 0.5)
        self.move(self.owner, 2)
        self.assertEqual(rankings.reward_state(self.w, self.owner)["remaining_seconds"], 2.5*DAY)
        self.settle(2.5*DAY)
        player = self.w._player(self.owner)
        self.assertEqual(player["swarm_crystals"], 1)
        self.assertEqual(player["ranking_reward_units"], 0)

    def test_outside_top_30_pauses_and_reentry_keeps_existing_fraction(self):
        self.settle(1.5*DAY)
        self.move(self.owner, 31)
        self.settle(20*DAY)
        value = rankings.reward_state(self.w, self.owner)
        self.assertFalse(value["active"])
        self.assertEqual(value["progress"], 0.5)
        self.assertIsNone(value["remaining_seconds"])
        self.move(self.owner, 30)
        self.assertEqual(rankings.reward_state(self.w, self.owner)["remaining_seconds"], 7*DAY)
        self.settle(7*DAY)
        self.assertEqual(self.w._player(self.owner)["swarm_crystals"], 1)

    def test_offline_batch_awards_whole_crystals_once_and_keeps_remainder(self):
        self.settle(10*DAY)
        player = self.w._player(self.owner)
        self.assertEqual(player["swarm_crystals"], 3)
        self.assertEqual(player["ranking_reward_total"], 3)
        self.assertEqual(player["ranking_reward_units"], rankings.REWARD_UNIT//3)
        reports = [row for row in player["reports"] if row["kind"] == "ranking"]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["swarm_crystals"], 3)
        self.assertEqual(reports[0]["art_key"], "swarm/crystal")
        self.assertEqual(reports[0]["at"], NOW+10*DAY)
        self.settle(0)
        self.assertEqual(player["swarm_crystals"], 3)

    def test_fractional_time_is_independent_of_poll_frequency_and_server_speed(self):
        self.w.speed = 1000
        for millis in range(1,1001):
            self.w.now = NOW + millis/1000
            rankings.accrue_rewards(self.w, self.w.now)
        self.assertEqual(self.w._player(self.owner)["ranking_reward_units"], 70_000)
        saved = copy.deepcopy(self.w.data)
        rankings.accrue_rewards(self.w, NOW)
        self.assertEqual(self.w.data, saved)

    def test_category_and_repeated_read_do_not_change_rate_or_saved_world(self):
        self.settle(DAY)
        before, changes = copy.deepcopy(self.w.data), self.w.db.total_changes
        for category in rankings.CATEGORIES:
            view = rankings.view(self.w, self.owner, category)
            self.assertEqual(view["reward"]["position"], 1)
            self.assertEqual(view["reward"]["days_per_crystal"], 3)
            self.assertEqual(view["reward"]["progress_units"], DAY*1000*70)
            self.assertNotIn("ranking_reward_units", view["items"][0])
            self.assertNotIn("swarm_crystals", view["items"][0])
        self.assertEqual(self.w.data, before)
        self.assertEqual(self.w.db.total_changes, changes)

    def test_database_failure_rolls_back_reward_clock_wallet_and_report(self):
        before = copy.deepcopy(self.w.data)
        with patch.object(self.w, "_save", side_effect=sqlite3.OperationalError("simulated full disk")):
            with self.assertRaises(app.GameError):
                self.settle(3*DAY)
        self.assertEqual(self.w.data, before)
        self.assertEqual(self.w.now, NOW)
        self.settle(3*DAY)
        self.assertEqual(self.w._player(self.owner)["swarm_crystals"], 1)
        self.assertEqual(len([r for r in self.w._player(self.owner)["reports"] if r["kind"]=="ranking"]), 1)


class RankingRewardWorldTests(unittest.TestCase):
    def create(self, path=":memory:"):
        world = app.World(path, now=NOW)
        account = world.register("AlphaRewardWorld", PASSWORD)
        owner = account["state"]["player"]["id"]
        world.action(owner, {"type":"choose_race", "race_id":"zetans"})
        world.data["alien"]["next_expansion_at"] = NOW + 1000*DAY
        return world, owner, account

    def test_restart_settles_offline_time_and_does_not_pay_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"world.sqlite3"
            world, owner, account = self.create(path)
            world.advance(NOW+DAY)
            self.assertEqual(rankings.reward_state(world,owner)["progress_units"], rankings.REWARD_UNIT//3)
            world.close()
            world = app.World(path, now=NOW+3*DAY)
            self.assertEqual(world.authenticate(account["token"]),owner)
            self.assertEqual(world._player(owner)["swarm_crystals"],1)
            world.close()
            world = app.World(path, now=NOW+3*DAY)
            try:
                self.assertEqual(world._player(owner)["swarm_crystals"],1)
                self.assertEqual(world._player(owner)["ranking_reward_units"],0)
            finally: world.close()

    def test_existing_world_activation_never_pays_for_pre_release_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"old-world.sqlite3"
            world, owner, _ = self.create(path)
            epoch = world.data["launch_reset_id"]
            home = world._owned(owner)["id"]
            for key in list(world.data):
                if key.startswith("ranking_reward_"):world.data.pop(key)
            world.close()
            world = app.World(path, now=NOW+30*DAY)
            try:
                self.assertEqual(world._player(owner)["swarm_crystals"],0)
                self.assertEqual(world.data["ranking_reward_started_at"],NOW+30*DAY)
                self.assertEqual(world.data["launch_reset_id"],epoch)
                self.assertEqual(world._owned(owner)["id"],home)
                world.advance(NOW+33*DAY)
                self.assertEqual(world._player(owner)["swarm_crystals"],1)
            finally: world.close()

    def test_asset_completion_changes_rate_only_after_its_deadline(self):
        world, alpha, _ = self.create()
        self.addCleanup(world.close)
        beta = world.register("BetaRewardWorld", PASSWORD)["state"]["player"]["id"]
        world.action(beta,{"type":"choose_race","race_id":"zetans"})
        for owner in (alpha,beta):
            planet=world._owned(owner)
            planet["ships"]=dict.fromkeys(planet["ships"],0)
            planet["buildings"]=dict.fromkeys(planet["buildings"],0)
            planet["buildings"]["shipyard"]=3
            planet["resources"]=dict.fromkeys(app.RESOURCES,1_000_000.)
        world._owned(alpha)["ships"]["scout"]=10
        world.action(beta,{"type":"ship","key":"frigate","amount":10})
        world._owned(beta)["queue"][0]["ends_at"]=NOW+DAY
        self.assertEqual(rankings.reward_state(world,alpha)["position"],1)
        world.advance(NOW+3*DAY)
        self.assertEqual(rankings.reward_state(world,beta)["position"],1)
        self.assertEqual(world._player(alpha)["ranking_reward_units"],DAY*1000*70+2*DAY*1000*42)
        self.assertEqual(world._player(beta)["ranking_reward_units"],DAY*1000*42+2*DAY*1000*70)

    def test_new_account_has_no_credit_for_time_before_creation(self):
        world, owner, _ = self.create()
        self.addCleanup(world.close)
        world.advance(NOW+3*DAY)
        other = world.register("NewRewardWorld", PASSWORD)["state"]["player"]["id"]
        self.assertEqual(world._player(owner)["swarm_crystals"],1)
        self.assertEqual(rankings.reward_state(world,other)["progress_units"],0)
        self.assertEqual(world._player(other)["swarm_crystals"],0)


if __name__ == "__main__":
    unittest.main()
