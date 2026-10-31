"""Real mission/action regressions for reversible player-colony ownership.

Fixtures create existing colonies; capture always uses a paid dispatch and the
normal arrival handler. No production ticks are skipped in the persistence test.
"""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app
import planetary
from i18n import language_scope

NOW = 2_000_000_000.0


class ColonyCaptureTests(unittest.TestCase):
    def setUp(self):
        self.language = language_scope("pl")
        self.language.__enter__()
        self.addCleanup(self.language.__exit__, None, None, None)
        self.w = app.World(":memory:", now=NOW)
        self.addCleanup(lambda: self.w.close())
        self.a = self.account("OriginalSettler", "zetans")
        self.b = self.account("OtherCivilization", "automatons")
        self.colony = self.existing_colony(self.a)

    def account(self, name, race):
        owner = self.w.register(name, "colony-capture-test-password")["state"]["player"]["id"]
        self.w.action(owner, {"type": "choose_race", "race_id": race})
        self.w._player(owner)["protected_until"] = 0
        home = self.w._owned(owner)
        home["resources"] = dict.fromkeys(app.RESOURCES, 1_000_000.)
        home["ships"].update(colonizer=10, scout=10, cargo=10, frigate=10)
        return owner

    def empty(self):
        return next(p for p in self.w.data["planets"].values()
                    if p["owner_type"] == "empty" and p["galaxy_id"] == "g1"
                    and planetary.fields(p)["total"] >= 86)

    def existing_colony(self, owner):
        p = self.empty()
        p.update(owner_type="player", owner_id=owner)
        p["buildings"] = dict.fromkeys(app.BUILDINGS, 3)
        p["resources"] = {"metal": 8000., "crystal": 7000., "fuel": 6000.}
        p["ships"] = dict.fromkeys(self.w._specs(owner, "ships"), 0)
        p["defenses"] = dict.fromkeys(self.w._specs(owner, "defenses"), 0)
        self.w._ensure_race_buildings(p)
        return p

    def payload(self, owner=None, target=None, **kwargs):
        owner = owner or self.b
        target = target or self.colony
        self.w._capture_planetary_intel(owner, target)
        data = {"type": "fleet", "mission": "colonize",
                "planet_id": self.w._owned(owner)["id"], "target_id": target["id"],
                "ships": {"colonizer": 1}, "cargo": {}}
        data.update(kwargs)
        return data

    def launch(self, owner=None, target=None, **kwargs):
        owner = owner or self.b
        before = set(self.w.data["fleets"])
        self.w.action(owner, self.payload(owner, target, **kwargs))
        added = set(self.w.data["fleets"]) - before
        self.assertEqual(len(added), 1)
        return self.w.data["fleets"][added.pop()]

    def arrive(self, fleet):
        self.w.now = max(self.w.now, fleet["arrives_at"])
        self.w._complete_fleet(fleet)

    def capture(self, owner=None, target=None, **kwargs):
        owner = owner or self.b
        target = target or self.colony
        flight = self.launch(owner, target, **kwargs)
        self.arrive(flight)
        self.assertEqual(target["owner_id"], owner)
        self.assertNotIn(flight["id"], self.w.data["fleets"])
        return flight

    def assert_rejected(self, target=None, **kwargs):
        payload = self.payload(target=target, **kwargs)
        before = copy.deepcopy(self.w.data)
        with self.assertRaises(app.GameError):
            self.w.preview(self.b, payload)
        with self.assertRaises(app.GameError):
            self.w.action(self.b, payload)
        self.assertEqual(self.w.data, before, "Rejected dispatch must not spend resources or ships")

    def assert_returned_unchanged(self, flight, target=None):
        target = target or self.colony
        before = copy.deepcopy(target)
        self.arrive(flight)
        self.assertEqual(target, before)
        self.assertEqual(flight["status"], "returning")
        self.assertEqual(flight["ships"]["colonizer"], 1)

    def join_alliance(self, first, second):
        self.w.alliance_action(first, {"action": "create", "name": "Capture Test Pact", "tag": "CTP",
                                      "request_id": "capture-test-create-pact"})
        alliance = self.w._alliance_for(first)
        self.w._alliance_join(second, alliance, "member")
        return alliance

    def support(self):
        helper = self.account("AlliedDefender", "symbionts")
        self.join_alliance(self.a, helper)
        flight = {"id": "capture-support", "owner_id": helper,
                  "origin_id": self.w._owned(helper)["id"], "target_id": self.colony["id"],
                  "race_id": "symbionts", "mission": "alliance_defense", "status": "holding",
                  "support_owner_id": self.a, "hold_until": self.w.now + 1_000_000,
                  "arrives_at": self.w.now + 1_000_000, "started_at": self.w.now,
                  "seconds": 1_000_000, "ships": {**app.blank_ships(), "frigate": 1},
                  "cargo": dict.fromkeys(app.RESOURCES, 0), "swarm_crystals": 0}
        self.w.data["fleets"][flight["id"]] = flight
        return flight

    def assert_warning(self, text):
        self.assertIn("przejęta przez inną cywilizację", str(text))

    def returning_defender(self, arrives_at):
        flight = {"id": "return-to-captured-colony", "owner_id": self.a,
                  "race_id": "zetans", "origin_id": self.colony["id"],
                  "target_id": self.w._owned(self.b)["id"], "mission": "scout", "status": "returning",
                  "ships": {**app.blank_ships(), "scout": 2},
                  "cargo": {"metal": 17, "crystal": 23, "fuel": 9}, "swarm_crystals": 3,
                  "started_at": self.w.now, "seconds": 100, "arrives_at": arrives_at}
        self.w.data["fleets"][flight["id"]] = flight
        return flight

    def test_unarmed_secondary_colony_is_captured_with_buildings_resources_and_traits_intact(self):
        self.colony["buildings"]["phase_matrix"] = 4
        before = copy.deepcopy(self.colony)
        cargo = {"metal": 100, "crystal": 20, "fuel": 5}
        flight = self.capture(ships={"colonizer": 1, "frigate": 2}, cargo=cargo)
        for key, level in before["buildings"].items():
            self.assertEqual(self.colony["buildings"][key], level)
        for resource in app.RESOURCES:
            self.assertEqual(self.colony["resources"][resource], before["resources"][resource] + cargo[resource])
        for key in set(before) - {"owner_id", "owner_type", "buildings", "ships", "resources", "defenses", "queue"}:
            self.assertEqual(self.colony[key], before[key], key)
        self.assertEqual(self.colony["ships"]["colonizer"], 0)
        self.assertEqual(self.colony["ships"]["frigate"], 2)
        before_replay = copy.deepcopy(self.w.data)
        self.w._complete_fleet(flight)
        self.assertEqual(self.w.data, before_replay, "Stale arrival must not capture or credit cargo twice")

    def test_homeworld_remains_protected_without_ships_or_defenses(self):
        home = self.w._owned(self.a)
        home["ships"] = dict.fromkeys(self.w._specs(self.a, "ships"), 0)
        home["defenses"] = {}
        self.assert_rejected(home)

    def test_homeworld_status_is_rechecked_on_arrival(self):
        flight = self.launch()
        self.w._player(self.a)["home_id"] = self.colony["id"]
        self.assert_returned_unchanged(flight)

    def test_any_stationed_ship_blocks_capture_including_noncombat_ships(self):
        for key in ("scout", "cargo", "colonizer", "frigate"):
            with self.subTest(ship=key):
                self.colony["ships"][key] = 1
                self.assert_rejected()
                self.colony["ships"][key] = 0

    def test_planetary_defense_blocks_dispatch(self):
        key = next(iter(self.w._specs(self.a, "defenses")))
        self.colony["defenses"][key] = 1
        self.assert_rejected()

    def test_allied_stationed_support_blocks_dispatch(self):
        self.support()
        self.assert_rejected()

    def test_static_defense_added_while_in_flight_aborts_capture(self):
        flight = self.launch()
        self.colony["defenses"][next(iter(self.w._specs(self.a, "defenses")))] = 1
        self.assert_returned_unchanged(flight)

    def test_ship_added_while_in_flight_aborts_capture(self):
        flight = self.launch()
        self.colony["ships"]["cargo"] = 1
        self.assert_returned_unchanged(flight)

    def test_allied_support_arriving_in_flight_aborts_capture(self):
        flight = self.launch()
        self.support()
        self.assert_returned_unchanged(flight)

    def test_same_owner_and_swarm_planets_cannot_be_colonized(self):
        own_colony = self.existing_colony(self.b)
        self.assert_rejected(own_colony)
        khar = next(p for p in self.w.data["planets"].values() if p["owner_id"] == "khar")
        self.assert_rejected(khar)

    def test_alliance_and_departure_truce_block_colonization(self):
        self.join_alliance(self.a, self.b)
        self.assert_rejected()
        self.w.alliance_action(self.b, {"action": "leave", "request_id": "capture-test-leave-pact"})
        self.assertTrue(self.w._alliance_attack_block(self.a, self.b))
        self.assert_rejected()

    def test_new_alliance_while_in_flight_aborts_capture(self):
        flight = self.launch()
        self.join_alliance(self.a, self.b)
        self.assert_returned_unchanged(flight)

    def test_starting_protection_is_checked_at_dispatch_and_arrival(self):
        self.w._player(self.a)["protected_until"] = self.w.now + 100_000
        self.assert_rejected()
        self.w._player(self.a)["protected_until"] = 0
        flight = self.launch()
        self.w._player(self.a)["protected_until"] = flight["arrives_at"] + 100
        self.assert_returned_unchanged(flight)

    def test_hostile_colonization_ends_attacker_protection(self):
        self.w._player(self.b)["protected_until"] = self.w.now + 100_000
        self.launch()
        self.assertLessEqual(self.w._player(self.b)["protected_until"], self.w.now)

    def test_fresh_colonization_preserves_attacker_starting_protection(self):
        until = self.w.now + 100_000
        self.w._player(self.b)["protected_until"] = until
        self.capture(target=self.empty())
        self.assertEqual(self.w._player(self.b)["protected_until"], until)

    def test_current_owner_is_revalidated_if_planet_changes_hands_in_flight(self):
        third = self.account("ThirdCivilization", "symbionts")
        flight = self.launch()
        self.colony["owner_id"] = third
        self.w._ensure_race_buildings(self.colony)
        self.w._player(third)["protected_until"] = flight["arrives_at"] + 100
        self.assert_returned_unchanged(flight)

    def test_unprotected_enemy_colony_can_still_be_taken_after_owner_changes(self):
        third = self.account("ThirdCivilization", "symbionts")
        flight = self.launch()
        self.colony["owner_id"] = third
        self.w._ensure_race_buildings(self.colony)
        self.arrive(flight)
        self.assertEqual(self.colony["owner_id"], self.b)
        self.assertTrue(any(self.colony["name"] in r["text"] for r in self.w._player(third)["reports"]))

    def test_colony_limit_including_pending_expeditions_is_enforced(self):
        while sum(p["owner_id"] == self.b for p in self.w.data["planets"].values()) < app.MAX_COLONIES - 1:
            self.existing_colony(self.b)
        self.launch(target=self.empty())
        self.assert_rejected()

    def test_colony_limit_is_rechecked_at_arrival(self):
        flight = self.launch()
        while sum(p["owner_id"] == self.b for p in self.w.data["planets"].values()) < app.MAX_COLONIES:
            self.existing_colony(self.b)
        self.assert_returned_unchanged(flight)

    def test_colonizer_required_even_for_unarmed_enemy_colony(self):
        self.assert_rejected(ships={"frigate": 1})

    def test_capture_never_applies_free_colony_start_levels(self):
        symbiont = self.account("NurseryInvader", "symbionts")
        self.w._owned(symbiont)["buildings"]["pioneer_nursery"] = 5
        self.colony["buildings"]["metal_mine"] = 0
        self.colony["buildings"]["crystal_mine"] = 2
        before = dict(self.colony["buildings"])
        quote = self.w.preview(symbiont, self.payload(symbiont))
        self.assertEqual(quote["colonization_kind"], "capture")
        self.assertNotIn("colony_start_level", quote)
        self.capture(symbiont)
        for key, level in before.items():
            self.assertEqual(self.colony["buildings"][key], level)

    def test_foreign_racial_buildings_retained_but_cannot_be_built_or_apply_effects(self):
        self.colony["buildings"]["phase_matrix"] = 5
        self.colony["buildings"]["echo_observatory"] = 4
        self.capture()
        self.assertEqual(self.colony["buildings"]["phase_matrix"], 5)
        effects = self.w._building_effects(self.colony)
        self.assertNotIn("mining_energy_reduction", effects)
        self.assertNotIn("scout_time_reduction", effects)
        keys = {entry["key"] for entry in self.w._catalog(self.b, self.colony)["buildings"]}
        self.assertNotIn("phase_matrix", keys)
        self.assertIn("serial_forge", keys)
        with self.assertRaises(app.GameError):
            self.w.action(self.b, {"type": "build", "planet_id": self.colony["id"], "key": "phase_matrix"})
        self.w.action(self.b, {"type": "build", "planet_id": self.colony["id"], "key": "serial_forge"})
        task = self.colony["queue"][0]
        self.w.now = task["ends_at"]
        self.w._complete_queue(self.colony)
        self.assertEqual(self.colony["buildings"]["serial_forge"], 1)
        self.assertGreater(self.w._building_effects(self.colony)["batch_time_reduction_per_extra"], 0)

    def test_repeated_recapture_restores_each_races_own_saved_levels(self):
        third = self.account("OrganicCivilization", "symbionts")
        self.colony["buildings"]["phase_matrix"] = 4
        self.capture(self.b)
        self.colony["buildings"]["serial_forge"] = 3
        self.capture(third)
        self.colony["buildings"]["world_root"] = 2
        self.capture(self.a)
        self.assertEqual(self.colony["buildings"]["phase_matrix"], 4)
        self.assertAlmostEqual(self.w._building_effects(self.colony)["mining_energy_reduction"], .24)
        self.assertNotIn("batch_time_reduction_per_extra", self.w._building_effects(self.colony))
        self.assertEqual(self.colony["buildings"]["serial_forge"], 3)
        self.assertEqual(self.colony["buildings"]["world_root"], 2)
        self.capture(self.b)
        self.assertAlmostEqual(self.w._building_effects(self.colony)["batch_time_reduction_per_extra"], .045)
        self.assertEqual(self.colony["buildings"]["phase_matrix"], 4)
        self.capture(third)
        self.assertAlmostEqual(self.w._building_effects(self.colony)["building_time_reduction"], .16)
        self.assertEqual(self.colony["buildings"]["serial_forge"], 3)
        self.assertEqual(self.colony["buildings"]["phase_matrix"], 4)

    def test_local_projects_and_plans_cancel_without_transferring_research_or_free_refunds(self):
        self.colony["resources"] = dict.fromkeys(app.RESOURCES, 100_000.)
        self.colony["buildings"]["synapse_archive"] = 5
        for kind, key in (("build", "metal_mine"), ("ship", "scout"), ("research", "propulsion")):
            self.w.action(self.a, {"type": kind, "key": key, "planet_id": self.colony["id"]})
        tasks = copy.deepcopy(self.colony["queue"])
        self.assertEqual(len(tasks), 3)
        for task in self.colony["queue"]:
            task["ends_at"] = self.w.now + 1_000_000
        self.w._player(self.a)["planned_orders"] = [
            {"id": "captured-plan", "kind": "build", "key": "metal_mine", "amount": 1,
             "planet_id": self.colony["id"], "created_at": self.w.now},
            {"id": "home-plan", "kind": "build", "key": "metal_mine", "amount": 1,
             "planet_id": self.w._owned(self.a)["id"], "created_at": self.w.now}]
        home_before = dict(self.w._owned(self.a)["resources"])
        stocks_before = dict(self.colony["resources"])
        levels_before = dict(self.colony["buildings"])
        research_before = copy.deepcopy(self.w._player(self.a)["research"])
        self.capture()
        self.assertEqual(self.colony["queue"], [])
        self.assertEqual(self.colony["resources"], stocks_before)
        for key, level in levels_before.items():
            self.assertEqual(self.colony["buildings"][key], level)
        self.assertEqual(self.w._player(self.a)["research"], research_before)
        self.assertEqual(self.w._player(self.a)["planned_orders"][0]["id"], "home-plan")
        self.assertEqual(len(self.w._player(self.a)["planned_orders"]), 1)
        for resource in app.RESOURCES:
            expected = home_before[resource] + sum(task["paid_cost"][resource] for task in tasks)
            self.assertEqual(self.w._owned(self.a)["resources"][resource], expected)
        self.w.now += 1_000_001
        self.w._complete_queue(self.colony)
        self.assertEqual(self.w._player(self.a)["research"], research_before)
        self.assertEqual(sum(self.colony["ships"].values()), 0)

    def test_legacy_queue_without_verified_cost_does_not_create_refund(self):
        self.colony["queue"] = [{"id": "legacy", "kind": "build", "key": "metal_mine", "amount": 1,
                                  "level": 4, "started_at": self.w.now, "seconds": 100_000,
                                  "ends_at": self.w.now + 100_000}]
        before = dict(self.w._owned(self.a)["resources"])
        self.capture()
        self.assertEqual(self.w._owned(self.a)["resources"], before)
        self.assertEqual(self.colony["queue"], [])

    def test_old_returning_fleet_returns_to_original_owner_home(self):
        flight = self.returning_defender(self.w.now + 100_000)
        self.capture()
        captured_before = copy.deepcopy(self.colony)
        home = self.w._owned(self.a)
        stocks_before = dict(home["resources"])
        ships_before = home["ships"]["scout"]
        crystals_before = self.w._player(self.a).get("swarm_crystals", 0)
        self.arrive(flight)
        self.assertEqual(self.colony, captured_before)
        self.assertEqual(flight["origin_id"], home["id"])
        self.assertIn(flight["id"], self.w.data["fleets"])
        self.arrive(flight)
        self.assertNotIn(flight["id"], self.w.data["fleets"])
        self.assertEqual(home["ships"]["scout"], ships_before + 2)
        for key, amount in flight["cargo"].items():
            self.assertEqual(home["resources"][key], stocks_before[key] + amount)
        self.assertEqual(self.w._player(self.a)["swarm_crystals"], crystals_before + 3)

    def test_already_due_returning_defender_blocks_dispatch_before_landing_is_processed(self):
        self.returning_defender(self.w.now)
        self.assert_rejected()

    def test_same_timestamp_returning_defender_blocks_capture_even_if_processed_second(self):
        flight = self.launch()
        defender = self.returning_defender(flight["arrives_at"])
        self.assert_returned_unchanged(flight)
        self.arrive(defender)
        self.assertEqual(self.colony["owner_id"], self.a)
        self.assertEqual(self.colony["ships"]["scout"], 2)

    def test_completed_megastructure_is_inactive_until_owner_recaptures_its_anchor(self):
        project = self.w._player(self.a)["megastructure"]
        project.update(origin_id=self.colony["id"], dyson_stage=4, gate_level=1, energy=100_000_000.)
        project["window"] = {"id": "capture-open-window", "target_id": self.w._owned(self.b)["id"],
                             "opened_at": self.w.now, "ready_at": self.w.now,
                             "closes_at": self.w.now + 100_000, "upkeep_per_second": 1_000_000}
        before_profile = self.w._mega_profile(self.w._player(self.a))
        self.assertGreater(before_profile["power"], 0)
        self.capture()
        self.assertIsNone(project["window"])
        self.assertEqual(project["dyson_stage"], 4)
        self.assertEqual(project["gate_level"], 1)
        self.assertEqual(self.w._mega_profile(self.w._player(self.a))["power"], 0)
        self.assertEqual(self.w._dyson_power(self.colony), 0)
        self.w._advance_megastructures(self.w.now, self.w.now + 100)
        self.assertEqual(project["energy"], 100_000_000.)
        self.capture(self.a)
        self.assertEqual(self.w._mega_profile(self.w._player(self.a)), before_profile)
        self.assertIsNone(project["window"], "Recapture must not reopen an old tunnel")
        self.assertEqual(project["energy"], 100_000_000.)

    def test_unfinished_megastructure_is_cancelled_and_paid_cost_refunded_to_old_home(self):
        project = self.w._player(self.a)["megastructure"]
        paid = {"metal": 4_000_000, "crystal": 2_500_000, "fuel": 750_000}
        project.update(origin_id=self.colony["id"], dyson_stage=3, energy=1000.,
                       queue={"id": "capture-dyson-queue", "key": "dyson", "name": "Ukończona Sfera Dysona",
                              "level": 4, "paid_cost": paid, "started_at": self.w.now,
                              "seconds": 1_000_000, "ends_at": self.w.now + 1_000_000})
        before = dict(self.w._owned(self.a)["resources"])
        self.capture()
        self.assertIsNone(project["queue"])
        for key in app.RESOURCES:
            self.assertEqual(self.w._owned(self.a)["resources"][key], before[key] + paid[key])
        self.w._complete_megastructures(self.w.now + 1_000_001)
        self.assertEqual(project["dyson_stage"], 3)
        self.assertEqual(project["energy"], 1000.)

    def test_lost_unfinished_first_foundation_can_be_restarted_on_homeworld(self):
        project = self.w._player(self.a)["megastructure"]
        project.update(origin_id=self.colony["id"], dyson_stage=0,
                       queue={"id": "capture-foundation", "key": "dyson", "name": "Fundament orbitalny",
                              "level": 1, "paid_cost": {"metal": 125_000, "crystal": 80_000, "fuel": 25_000},
                              "started_at": self.w.now, "seconds": 1_000_000,
                              "ends_at": self.w.now + 1_000_000})
        self.capture()
        self.assertEqual(project["origin_id"], "")
        self.assertIsNone(project["queue"])
        home = self.w._owned(self.a)
        home["buildings"].update(shipyard=8, power_plant=8)
        self.w._player(self.a)["research"]["dyson_design"] = 1
        self.w.action(self.a, {"type": "megabuild", "key": "dyson", "planet_id": home["id"]})
        self.assertEqual(project["origin_id"], home["id"])
        self.assertEqual(project["queue"]["level"], 1)

    def test_scout_snapshots_keep_home_marker_and_foreign_building_names_after_recapture(self):
        home = self.w._owned(self.a)
        home_scout = self.launch(target=home, mission="scout", ships={"scout": 1})
        self.arrive(home_scout)
        home_report = copy.deepcopy(self.w._player(self.b)["reports"][0])
        self.assertTrue(self.w._public_intel_report(home_report)["planet_scout"]["is_home_planet"])
        self.colony["buildings"]["phase_matrix"] = 4
        self.capture()
        scout = self.launch(self.a, mission="scout", ships={"scout": 1})
        self.arrive(scout)
        report = copy.deepcopy(self.w._player(self.a)["reports"][0])
        view = self.w._public_intel_report(report)["planet_scout"]
        self.assertFalse(view["is_home_planet"])
        self.assertEqual(view["owner_id"], self.b)
        observed = {item["key"]: item for item in view["observed_buildings"]}
        self.assertEqual(observed["phase_matrix"]["name"], "Matryca Fazowa")
        self.assertEqual(observed["phase_matrix"]["level"], 4)
        self.assertTrue(observed["phase_matrix"]["inactive"])
        self.capture(self.a)
        self.assertEqual(self.w._public_intel_report(report)["planet_scout"], view)
        self.assertTrue(self.w._public_intel_report(home_report)["planet_scout"]["is_home_planet"])

    def test_lost_selected_colony_falls_back_to_home_but_cannot_be_mutated(self):
        self.colony["buildings"]["phase_matrix"] = 4
        self.capture()
        old_view = self.w.state(self.a, self.colony["id"])
        self.assertEqual(old_view["planet_id"], self.w._owned(self.a)["id"])
        self.assertTrue(old_view["selected_planet_lost"])
        with self.assertRaises(app.GameError):
            self.w.action(self.a, {"type": "build", "planet_id": self.colony["id"], "key": "metal_mine"})
        new_view = self.w.state(self.b, self.colony["id"])
        self.assertTrue(new_view["colonization_capture"]["enabled"])
        inactive = {item["key"]: item for item in new_view["inactive_racial_buildings"]}
        self.assertEqual(inactive["phase_matrix"]["level"], 4)
        self.assertEqual(inactive["phase_matrix"]["race_id"], "zetans")

    def test_preview_launch_and_success_report_warn_for_fresh_and_captured_colonies(self):
        for target in (self.empty(), self.colony):
            with self.subTest(kind=target["owner_type"]):
                payload = self.payload(target=target)
                self.assert_warning(self.w.preview(self.b, payload)["message"])
                before = set(self.w.data["fleets"])
                result = self.w.action(self.b, payload)
                self.assert_warning(result["message"])
                flight = self.w.data["fleets"][(set(self.w.data["fleets"]) - before).pop()]
                self.arrive(flight)
                self.assert_warning(self.w._player(self.b)["reports"][0]["text"])

    def test_sqlite_restart_preserves_owner_foreign_buildings_and_ability_to_reclaim(self):
        self.colony["buildings"]["phase_matrix"] = 4
        self.w._player(self.a)["megastructure"].update(
            origin_id=self.colony["id"], dyson_stage=4, gate_level=1, energy=1_234_567.)
        self.capture()
        self.colony["buildings"]["serial_forge"] = 3
        colony_id = self.colony["id"]
        buildings_before = dict(self.colony["buildings"])
        self.w.data["last_update"] = self.w.now
        self.w._save()
        with tempfile.TemporaryDirectory() as temp:
            import sqlite3
            path = str(Path(temp) / "captured-world.sqlite3")
            connection = sqlite3.connect(path)
            try:
                self.w.db.backup(connection)
            finally:
                connection.close()
            restarted = app.World(path, now=self.w.now)
            original_world = self.w
            try:
                self.w = restarted
                self.colony = restarted.data["planets"][colony_id]
                self.assertEqual(self.colony["owner_id"], self.b)
                self.assertEqual(self.colony["buildings"], buildings_before)
                mega = self.w._player(self.a)["megastructure"]
                self.assertEqual((mega["dyson_stage"], mega["gate_level"], mega["energy"]), (4, 1, 1_234_567.))
                self.assertEqual(self.w._mega_profile(self.w._player(self.a))["charge_per_second"], 0)
                self.assertTrue(self.w.state(self.a)["megastructures"]["suspended"])
                self.capture(self.a)
                self.assertEqual(self.colony["buildings"]["phase_matrix"], 4)
                self.assertAlmostEqual(self.w._building_effects(self.colony)["mining_energy_reduction"], .24)
                self.assertEqual(self.colony["buildings"]["serial_forge"], 3)
                self.assertGreater(self.w._mega_profile(self.w._player(self.a))["charge_per_second"], 0)
                self.assertEqual(mega["energy"], 1_234_567.)
            finally:
                restarted.close()
                self.w = original_world


if __name__ == "__main__":
    unittest.main()
