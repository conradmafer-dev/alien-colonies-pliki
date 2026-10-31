"""0.7.7: read-only mining modifier plus source contracts for optional UI detail.

These Python tests execute actual server code but NOT GDScript/GUI input.
For engine rendering/persistence run test_brief_descriptions_077.gd separately.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from server.main import World, RESOURCES, VERSION
from server.races import RACES
from server import planetary

ROOT = Path(__file__).resolve().parents[1]
BASE_MAIN_SHA256 = "4d06a815005a765754d1936c31aee5574073f2eaff585e5b43acce21d0f3b241"


class MineBonusMetadata(unittest.TestCase):
    def setUp(self):
        self.w = World(":memory:", now=2_000_000_000, speed=1)
        self.addCleanup(self.w.close)
        self.owner = self.w.register("Brief077", "Disposable-test-077!")["state"]["player"]["id"]
        self.w.action(self.owner, {"type": "choose_race", "race_id": "zetans"})
        self.p = self.w._owned(self.owner)

    def entry(self, key):
        return next(e for e in self.w._catalog(self.owner, self.p)["buildings"] if e["key"] == key)

    def set_race(self, race):
        self.w._player(self.owner)["race_id"] = race
        self.w._player(self.owner)["skill_nodes"] = []
        self.w._ensure_race_buildings(self.p)
        self.w._ensure_racial_research(self.w._player(self.owner))

    def test_bonus_is_actual_combined_modifier_for_all_races(self):
        for race in RACES:
            self.set_race(race)
            for k in self.w._specs(self.owner, "buildings"):
                self.p["buildings"][k] = 3
            for key in ("metal_mine", "crystal_mine", "refinery"):
                entry = self.entry(key)
                resource = entry["production_resource"]
                effects = self.w._building_effects(self.p)
                rules = self.w._rules(self.owner)
                expected = rules["production_multipliers"][resource] * (1 + effects.get("production_all", 0)) * (1 + effects.get("production_" + resource, 0)) * planetary.multipliers(self.p)[resource]
                self.assertAlmostEqual(entry["production_bonus_percent"], (expected - 1) * 100, places=5)

    def test_race_penalties_are_not_clamped_to_zero(self):
        for race, key, value in [("zetans", "metal_mine", -10), ("zetans", "crystal_mine", 25), ("symbionts", "crystal_mine", -15), ("automatons", "refinery", -20)]:
            self.set_race(race)
            self.assertAlmostEqual(self.entry(key)["production_bonus_percent"], ((1 + value / 100) * planetary.multipliers(self.p)[self.entry(key)["production_resource"]] - 1) * 100, places=5)

    def test_skill_bonuses_are_included(self):
        nodes = self.w.state(self.owner)["skill_tree"]["nodes"]
        self.w._player(self.owner)["skill_nodes"] = [n["id"] for n in nodes if n["race_id"] == "zetans"]
        bonus = self.w._bonuses(self.owner)["production_crystal"]
        self.assertGreater(bonus, 0)
        self.assertAlmostEqual(self.entry("crystal_mine")["production_bonus_percent"], (1.25 * (1 + bonus) * planetary.multipliers(self.p)["crystal"] - 1) * 100, places=5)

    def test_bonus_excludes_global_tempo(self):
        previous = self.entry("metal_mine")["production_bonus_percent"]
        for speed in (0.5, 1, 10):
            self.w.speed = speed
            self.assertEqual(self.entry("metal_mine")["production_bonus_percent"], previous)

    def test_bonus_excludes_power_shortage_but_output_does_not(self):
        self.p["buildings"].update(metal_mine=6, crystal_mine=6, refinery=6, power_plant=0)
        entry = self.entry("metal_mine")
        self.assertAlmostEqual(entry["production_bonus_percent"], (0.9 * planetary.multipliers(self.p)["metal"] - 1) * 100, places=5)
        output = next(m for m in entry["details"]["metrics"] if m["key"] == "mine_metal")
        self.assertEqual(output["current"], 0)
        self.p["buildings"]["power_plant"] = 12
        entry = self.entry("metal_mine")
        self.assertAlmostEqual(entry["production_bonus_percent"], (0.9 * planetary.multipliers(self.p)["metal"] - 1) * 100, places=5)
        self.assertGreater(next(m for m in entry["details"]["metrics"] if m["key"] == "mine_metal")["current"], 0)

    def test_next_output_still_matches_real_upgrade_with_energy(self):
        for race in RACES:
            self.set_race(race)
            self.p["buildings"].update(metal_mine=6, crystal_mine=6, refinery=6, power_plant=1)
            for key in ("metal_mine", "crystal_mine", "refinery"):
                e = self.entry(key)
                future = deepcopy(self.p)
                future["buildings"][key] += 1
                output = next(m for m in e["details"]["metrics"] if m["key"] == "mine_" + e["production_resource"])
                self.assertAlmostEqual(output["next"], future["buildings"][key] * e["production_per_level"] * self.w.energy(future)["factor"], places=5)

    def test_catalog_metadata_does_not_mutate_progress(self):
        before = deepcopy(self.w.data)
        for _ in range(2):
            self.w._catalog(self.owner, self.p)
        self.assertEqual(self.w.data, before)

    def test_bonus_only_on_resource_producers_and_json_is_finite(self):
        catalog = self.w._catalog(self.owner, self.p)
        for group, entries in catalog.items():
            for entry in entries:
                self.assertEqual("production_bonus_percent" in entry, group == "buildings" and "production_resource" in entry)
        json.dumps(catalog, allow_nan=False)


class BriefUIContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (ROOT / "client/scripts/main.gd").read_text()
        cls.ui = (ROOT / "client/scripts/compact_ui.gd").read_text()
        cls.details = (ROOT / "client/scripts/catalog_details.gd").read_text()
        cls.prefs = (ROOT / "client/scripts/ui_preferences.gd").read_text()

    def test_new_and_existing_installs_default_to_brief(self):
        self.assertIn("var detailed_descriptions: bool = false", self.main)
        self.assertIn("detailed: bool = false", self.details)
        self.assertIn("get_value(SECTION, DETAIL_KEY, false)", self.prefs)
        self.assertIn("value is bool else false", self.prefs)

    def test_setting_loaded_before_ui_and_persisted_separately(self):
        ready = self.main.split("func _ready()", 1)[1].split("func _notification", 1)[0]
        self.assertLess(ready.index("_load_ui_preferences()"), ready.index("_make_app()"))
        self.assertIn('"user://interface.cfg"', self.prefs)
        self.assertNotIn("session.cfg", self.prefs)
        self.assertNotIn("token", self.prefs)
        self.assertIn("return config.save(path)", self.prefs)

    def test_settings_toggle_connected_and_failure_rolls_back(self):
        self.assertIn("_add_description_setting(options_panel)", self.main)
        self.assertIn("toggled.connect(_on_detailed_descriptions_toggled)", self.main)
        self.assertIn("set_pressed_no_signal(detailed_descriptions)", self.main)
        handler = self.main.split("func _on_detailed_descriptions_toggled",1)[1].split("func ",1)[0]
        self.assertLess(handler.index("!= OK"), handler.index("detailed_descriptions = enabled"))
        self.assertIn("compact_ui.refresh_description_mode()", handler)

    def test_detail_open_and_poll_obey_saved_mode(self):
        self.assertIn("paragraphs(host, controls, host.detailed_descriptions)", self.ui)
        self.assertIn('JSON.stringify([controls.get("entry", {}), host.detailed_descriptions])', self.ui)
        self.assertIn('modal_scroll.set_deferred("scroll_vertical", scroll_y)', self.ui)

    def test_brief_path_does_not_emit_efficiency_colony_totals_or_examples(self):
        brief = self.details.split("static func _brief_metrics",1)[1].split("static func paragraphs",1)[0]
        for forbidden in ('"energy_efficiency"', '"colony_"', '"time_examples"', '"facility_time_reduction"', '"available_now"', '"milestones"', '"unlocks_next"'):
            self.assertNotIn(forbidden, brief)
        for required in ('"production_bonus_percent"', '"per_hour"', '"energy_use"', '"shipyard_speed_bonus"', '"lab_speed_bonus"'):
            self.assertIn(required, brief)

    def test_description_mode_never_hides_or_duplicates_requirements(self):
        req = self.details.split("# A requirement is rendered ONCE",1)[1]
        self.assertNotIn("if detailed", req)
        self.assertIn("seen.has(identity)",req)
        self.assertIn('not reason.begins_with(I18n.t("Wymaga:"))',req)
        self.assertEqual(self.details.count('sections.append(I18n.t("Wymagania")'),1)

    def test_full_mode_retains_original_metrics_and_unlock_information(self):
        body = self.details.split("static func paragraphs",1)[1]
        full = body.split("\tif detailed:\n",1)[1].split("\telse:\n",1)[0]
        for key in ("metrics", "time_examples", "notes", "available_now", "milestones"):
            self.assertIn('detail.get("'+key+'"' if key not in ("available_now",) else 'detail.has("available_now")',full)
        self.assertIn("sections.append_array(_brief_metrics", body)

    def test_basic_short_texts_are_localized_for_all_races(self):
        for code in ("en", "pl", "de", "es", "fr"):
            texts=json.loads((ROOT / f"localization/{code}.json").read_text())
            for key in ("Szczegółowe opisy", "Wydobywa metal.", "Wydobywa kryształy.", "Produkuje paliwo.", "Tempo produkcji: %s", "Tempo badań: %s"):
                self.assertTrue(texts[key])
                self.assertEqual(key.count("%s"), texts[key].count("%s"))
            self.assertEqual((ROOT / f"localization/{code}.json").read_bytes(), (ROOT / f"railway/{code}.json").read_bytes())

    @unittest.skipUnless(VERSION == "0.7.7", "Historical 0.7.7 UI-only source hash; later releases intentionally change gameplay.")
    def test_no_gameplay_diff_besides_read_only_metadata_and_version(self):
        data=(ROOT / "server/main.py").read_bytes()
        self.assertEqual(data,(ROOT / "railway/app.py").read_bytes())
        restored=data.decode().replace('VERSION = "0.7.7"','VERSION = "0.7.6"').replace("CLIENT_VERSION_CODE = 36","CLIENT_VERSION_CODE = 35")
        restored=restored.replace("                                    production_bonus_percent=round((multiplier - 1.0) * 100.0, 6),\n", "")
        self.assertEqual(hashlib.sha256(restored.encode()).hexdigest(),BASE_MAIN_SHA256)

    def test_unknown_or_unbuilt_facility_speed_is_not_invented(self):
        brief=self.details.split("static func _brief_metrics",1)[1].split("static func paragraphs",1)[0]
        self.assertIn('if metrics.has(speed_key)',brief)
        self.assertIn('if level > 0 else I18n.t("Niedostępne")',brief)
        self.assertIn('I18n.t("Tempo: brak danych z serwera.")',brief)
        self.assertNotIn('level - 1',brief)


if __name__ == "__main__":
    unittest.main(verbosity=2)
