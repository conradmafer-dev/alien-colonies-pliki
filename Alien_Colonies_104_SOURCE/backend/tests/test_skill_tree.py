"""Gameplay and geometry guarantees for the shared racial skill wheel."""
import copy
import json
import math
import unittest
from collections import deque
from fractions import Fraction

from server import skill_tree as skills


class SkillWheelTests(unittest.TestCase):
    def setUp(self):
        self.graph = skills.graph()
        self.nodes = {node["id"]: node for node in self.graph["nodes"]}
        self.adj = {key: [] for key in self.nodes}
        for a, b in self.graph["edges"]:
            self.adj[a].append(b)
            self.adj[b].append(a)

    def distances(self, start):
        result, queue = {start: 0}, deque([start])
        while queue:
            node = queue.popleft()
            for neighbor in self.adj[node]:
                if neighbor not in result:
                    result[neighbor] = result[node] + 1
                    queue.append(neighbor)
        return result

    def test_sixty_unique_drawable_skills_and_three_distinct_sectors(self):
        self.assertEqual(len(self.nodes), 60)
        self.assertEqual(len({node["icon"] for node in self.nodes.values()}), 60)
        self.assertEqual(len({node["art_key"] for node in self.nodes.values()}), 60)
        self.assertEqual(len([n for n in self.nodes.values() if n["kind"] == "bridge"]), 21)
        self.assertEqual(len({s["color"] for s in self.graph["sectors"]}), 3)
        for race, root in skills.ROOTS.items():
            faction = [n for n in self.nodes.values() if n["race_id"] == race]
            self.assertEqual(len(faction), 13)
            self.assertEqual(len(self.adj[root]), 3)
            self.assertTrue(all(self.nodes[root]["size"] > n["size"] for n in faction if n["id"] != root))

    def test_all_nodes_connected_but_foreign_roots_are_a_long_journey(self):
        for root in skills.ROOTS.values():
            distances = self.distances(root)
            self.assertEqual(len(distances), 60)
            for other in skills.ROOTS.values():
                if other != root:
                    self.assertGreaterEqual(distances[other], 15)

    def test_nodes_and_connection_segments_preserve_empty_center(self):
        for node in self.nodes.values():
            self.assertGreaterEqual(math.hypot(node["x"], node["y"]) - node["size"], skills.EMPTY_RADIUS)
        for a, b in self.graph["edges"]:
            start, end = self.nodes[a], self.nodes[b]
            dx, dy = end["x"] - start["x"], end["y"] - start["y"]
            t = max(0, min(1, -(start["x"] * dx + start["y"] * dy) / (dx * dx + dy * dy)))
            self.assertGreaterEqual(math.hypot(start["x"] + t * dx, start["y"] + t * dy), skills.EMPTY_RADIUS)

    def test_own_signature_is_free_and_has_only_its_characteristic_effect(self):
        expected = {"zetans": ("first_volley", .35), "automatons": ("damage_reduction", .12),
                    "symbionts": ("regeneration", .35)}
        for race, (key, value) in expected.items():
            self.assertEqual(skills.unlocked_for(race, []), [skills.ROOTS[race]])
            bonuses = skills.bonuses(race, [])
            self.assertEqual(bonuses[key], value)
            self.assertEqual(sum(v != 0 for v in bonuses.values()), 1)
            self.assertEqual(skills.public_state(race, [], 0)["balance"], 0)
            with self.assertRaisesRegex(ValueError, "już odblokowana"):
                skills.quote_unlock(race, [], skills.ROOTS[race], 999)

    def test_purchase_requires_a_path_and_enough_swarm_crystals(self):
        with self.assertRaisesRegex(ValueError, "sąsiednią"):
            skills.quote_unlock("zetans", [], "automatons_root", 999)
        with self.assertRaisesRegex(ValueError, "Brakuje 1"):
            skills.quote_unlock("zetans", [], "zetans_0_0", 0)
        original = []
        quote = skills.quote_unlock("zetans", original, "zetans_0_0", 8)
        self.assertEqual(quote["balance_after"], 7)
        self.assertEqual(quote["cost"], 1)
        self.assertIn("zetans_0_0", quote["unlocks"])
        self.assertEqual(original, [])
        with self.assertRaisesRegex(ValueError, "już odblokowana"):
            skills.quote_unlock("zetans", quote["unlocks"], "zetans_0_0", 99)

    def test_foreign_signature_can_be_bought_after_following_a_real_path(self):
        start, goal = skills.ROOTS["zetans"], skills.ROOTS["automatons"]
        previous, queue = {start: None}, deque([start])
        while goal not in previous:
            node = queue.popleft()
            for neighbor in self.adj[node]:
                if neighbor not in previous:
                    previous[neighbor] = node
                    queue.append(neighbor)
        path, node = [], goal
        while previous[node] is not None:
            path.append(node)
            node = previous[node]
        unlocked, wallet = [], 999
        for node in reversed(path):
            result = skills.quote_unlock("zetans", unlocked, node, wallet)
            unlocked, wallet = result["unlocks"], result["balance_after"]
        self.assertEqual(len(path), 16)
        self.assertEqual(skills.bonuses("zetans", unlocked)["damage_reduction"], .12)
        self.assertEqual(skills.bonuses("zetans", unlocked)["first_volley"], .35)
        self.assertEqual(999 - wallet, sum(self.expected_cost(self.nodes[node]["cost"], count)
                                          for count, node in enumerate(reversed(path))))

    @staticmethod
    def expected_cost(base_cost, paid_count):
        """Independent exact-rational oracle, not the pricing implementation."""
        return math.ceil(Fraction(base_cost, 6) * Fraction(112, 100) ** paid_count)

    def test_every_purchase_raises_the_price_of_an_untouched_branch(self):
        for race in skills.ROOTS:
            before = skills.public_state(race, [], 100)
            target_id = race + "_1_0"
            before_target = next(n for n in before["nodes"] if n["id"] == target_id)
            first = skills.quote_unlock(race, [], race + "_0_0", 100)
            after = skills.public_state(race, first["unlocks"], first["balance_after"])
            after_target = next(n for n in after["nodes"] if n["id"] == target_id)
            self.assertEqual(before_target["cost"], 1)
            self.assertEqual(after_target["cost"], 2)
            self.assertEqual(after_target["base_cost"], 6)
            self.assertEqual(after["purchased_count"], 1)
            self.assertEqual(after["cost_multiplier"], 1.12)
            self.assertEqual(after["cost_rule"], {
                "base_divisor": 6, "growth_numerator": 112, "growth_denominator": 100,
                "rounding": "ceil", "scope": "all_paid_nodes", "own_root_free": True})

    def test_all_races_all_purchase_stages_quote_and_display_identical_exact_costs(self):
        for race in skills.ROOTS:
            unlocked, balance = [], 100_000
            for paid_count in range(60):
                public = skills.public_state(race, unlocked, balance)
                self.assertEqual(public["purchased_count"], paid_count)
                self.assertEqual(public["balance"], balance)
                for node in public["nodes"]:
                    self.assertEqual(node["base_cost"], self.nodes[node["id"]]["cost"])
                    if node["unlocked"]:
                        self.assertEqual(node["cost"], 0)
                        self.assertFalse(node["available"])
                        self.assertFalse(node["affordable"])
                        continue
                    expected = self.expected_cost(node["base_cost"], paid_count)
                    self.assertEqual(node["cost"], expected)
                    if node["available"]:
                        quote = skills.quote_unlock(race, unlocked, node["id"], expected)
                        self.assertEqual(quote["cost"], expected)
                        self.assertEqual(quote["balance_after"], 0)
                        with self.assertRaisesRegex(ValueError, "Brakuje 1"):
                            skills.quote_unlock(race, unlocked, node["id"], expected - 1)
                    else:
                        with self.assertRaisesRegex(ValueError, "sąsiednią"):
                            skills.quote_unlock(race, unlocked, node["id"], 100_000)
                choices = [node for node in public["nodes"] if node["available"]]
                if paid_count == 59:
                    self.assertEqual(choices, [])
                    self.assertEqual(len(unlocked), 60)
                    continue
                chosen = min(choices, key=lambda n: (n["cost"], n["id"]))
                quote = skills.quote_unlock(race, unlocked, chosen["id"], balance)
                unlocked, balance = quote["unlocks"], quote["balance_after"]

    def test_price_count_uses_unique_connected_saved_skills_only(self):
        for race in skills.ROOTS:
            other_race = next(other for other in skills.ROOTS if other != race)
            good = [race + "_0_0", race + "_0_1"]
            corrupt = good + good + [skills.ROOTS[other_race], "unknown", {}, None, 123,
                                    race + "_1_3"]
            original = copy.deepcopy(corrupt)
            saved = json.loads(json.dumps(corrupt))
            public = skills.public_state(race, saved, 999)
            self.assertEqual(public["purchased_count"], 2)
            self.assertEqual(public, skills.public_state(race, good, 999))
            quote = skills.quote_unlock(race, saved, race + "_1_0", 999)
            self.assertEqual(quote, skills.quote_unlock(race, good, race + "_1_0", 999))
            self.assertEqual(corrupt, original)
        unchosen = skills.public_state("", list(self.nodes), 99)
        self.assertEqual(unchosen["purchased_count"], 0)
        self.assertEqual(unchosen["cost_multiplier"], 1)
        self.assertFalse(any(n["available"] for n in unchosen["nodes"]))

    def test_foreign_roots_increase_global_count_and_prices_like_every_paid_skill(self):
        # All-node saves still count exactly one root as free. This also covers
        # migrated saves: old purchases keep their bonuses but current prices.
        for race in skills.ROOTS:
            completed = skills.public_state(race, list(self.nodes), 0)
            self.assertEqual(completed["purchased_count"], 59)
            self.assertEqual(len(completed["unlocked"]), 60)
            self.assertEqual(completed["cost_multiplier"], round(1.12 ** 59, 6))
            self.assertTrue(all(n["cost"] == 0 for n in completed["nodes"]))

    def test_late_purchase_prices_make_complete_wheel_expensive_in_any_order(self):
        for paid_count, cheapest in ((0, 1), (10, 4), (20, 10), (40, 94), (58, 716)):
            self.assertEqual(self.expected_cost(6, paid_count), cheapest)
        # Ignoring path restrictions gives conservative bounds: paired with
        # increasing multipliers, descending weights minimize the *unrounded*
        # sum and ascending weights maximize it. Rounding adds <59 in total.
        # Therefore even any optimal legal traversal costs over this floor.
        weights = [n["cost"] for n in self.nodes.values() if n["id"] != "zetans_root"]
        growth = [Fraction(112, 100) ** count for count in range(59)]
        lower = math.floor(sum(Fraction(base, 6) * multiplier for base, multiplier
                               in zip(sorted(weights, reverse=True), growth)))
        upper = math.ceil(sum(Fraction(base, 6) * multiplier for base, multiplier
                             in zip(sorted(weights), growth))) + 59
        self.assertGreater(lower, 8_000)
        self.assertLess(upper, 40_000)

    def test_corrupt_duplicate_or_disconnected_saved_ids_cannot_grant_bonuses(self):
        raw = ["zetans_0_0", "zetans_0_0", "automatons_root", "unknown", {}, 123]
        normalized = skills.unlocked_for("zetans", raw)
        self.assertEqual(normalized, ["zetans_root", "zetans_0_0"])
        self.assertEqual(skills.bonuses("zetans", raw)["production_crystal"], .08)
        self.assertEqual(skills.bonuses("zetans", raw)["damage_reduction"], 0)
        self.assertEqual(skills.unlocked_for("", list(self.nodes)), [])
        self.assertTrue(all(value == 0 for value in skills.bonuses("", list(self.nodes)).values()))
        self.assertEqual(skills.unlocked_for([], raw), [])

    def test_client_flags_agree_with_purchase_validation(self):
        public = skills.public_state("symbionts", [], 6)
        available = [n for n in public["nodes"] if n["available"]]
        self.assertEqual(len(available), 3)
        for node in public["nodes"]:
            if node["affordable"]:
                skills.quote_unlock("symbionts", [], node["id"], 6)
            elif not node["unlocked"]:
                with self.assertRaises(ValueError):
                    skills.quote_unlock("symbionts", [], node["id"], 6)
        empty = skills.public_state("symbionts", [], 0)
        self.assertEqual(len([n for n in empty["nodes"] if n["available"]]), 3)
        self.assertFalse(any(n["affordable"] for n in empty["nodes"]))

    def test_all_effects_are_positive_known_and_bounded(self):
        for node in self.nodes.values():
            self.assertGreater(node["cost"], 0)
            self.assertTrue(node["effects"])
            for key, value in node["effects"].items():
                self.assertIn(key, skills.BONUS_CAPS)
                self.assertGreater(value, 0)
        result = skills.bonuses("zetans", list(self.nodes))
        for key, value in result.items():
            self.assertLessEqual(value, skills.BONUS_CAPS[key])
        self.assertTrue(all(value > 0 for value in result.values()))

    def test_returned_graph_and_cached_bonuses_are_not_mutable_global_state(self):
        original = copy.deepcopy(skills.graph())
        public = skills.public_state("zetans", [], 100)
        public["nodes"][0]["effects"]["first_volley"] = 999
        public["edges"].clear()
        result = skills.bonuses("zetans", [])
        result["first_volley"] = 999
        self.assertEqual(skills.graph(), original)
        self.assertEqual(skills.bonuses("zetans", [])["first_volley"], .35)

    def test_unknown_skill_race_and_invalid_wallet_fail_cleanly(self):
        for race in ("", "bogus", None, []):
            with self.assertRaisesRegex(ValueError, "wybierz rasę"):
                skills.quote_unlock(race, [], "zetans_0_0", 99)
        for node in ("bogus", [], None):
            with self.assertRaisesRegex(ValueError, "takiej umiejętności"):
                skills.quote_unlock("zetans", [], node, 99)
        for wallet in (-1, 2.5, True, "12", None):
            with self.assertRaisesRegex(ValueError, "stan kryształów"):
                skills.quote_unlock("zetans", [], "zetans_0_0", wallet)


if __name__ == "__main__":
    unittest.main()
