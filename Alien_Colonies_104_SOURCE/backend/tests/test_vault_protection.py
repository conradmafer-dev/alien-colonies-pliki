"""Vault protection must keep growing and match authoritative catalog previews."""
import copy
import json
from pathlib import Path
import unittest

import app
import economy85
import races
from i18n import language_scope

NOW = 1_900_000_000.0


class VaultProtectionTests(unittest.TestCase):
    def setUp(self):
        self.world = app.World(":memory:", now=NOW)
        self.addCleanup(self.world.close)
        self.owner = self.world.register("Vault Defender", "private-test-password")["state"]["player"]["id"]
        self.player = self.world._player(self.owner)
        self.planet = self.world._owned(self.owner)
        self.planet["rare_trait"] = ""
        self.world.data["alien"]["next_expansion_at"] = NOW + 365 * 86400

    def choose(self, race):
        self.player["race_id"] = race
        self.world._ensure_race_buildings(self.planet)
        return economy85.VAULTS[race]

    def test_protection_and_catalog_continue_above_level_five_for_all_races(self):
        for race in economy85.VAULTS:
            key = self.choose(race)
            for level in (0, 1, 4, 5, 6, 10, 20):
                with self.subTest(race=race, level=level):
                    self.planet["buildings"][key] = level
                    snapshot = copy.deepcopy(self.planet)
                    item = self.world._catalog(self.owner, self.planet, project_only=("buildings", key))["buildings"][0]
                    self.assertEqual(self.world._building_effects(self.planet)["protected_resources"], 1500 * level)
                    self.assertEqual(item["building_effect"]["current"], 1500 * level)
                    self.assertEqual(item["building_effect"]["next"], 1500 * (level + 1))
                    self.assertIn(str(1500 * level), item["effect_current"])
                    self.assertIn(str(1500 * (level + 1)), item["effect_next"])
                    self.assertEqual(self.planet, snapshot)

    def test_loot_is_taken_only_above_each_resources_growing_protection(self):
        for race in economy85.VAULTS:
            key = self.choose(race)
            for level in (5, 6, 10, 20):
                with self.subTest(race=race, level=level):
                    self.planet["buildings"][key] = level
                    protection = 1500 * level
                    self.planet["resources"] = {"metal": protection - 1., "crystal": float(protection), "fuel": protection + 10000.}
                    self.assertEqual(self.world._lootable_resources(self.planet), {"metal": 0, "crystal": 0, "fuel": 3500})

    def test_actual_attack_respects_level_ten_vault_for_all_races(self):
        attacker = self.world.register("Vault Attacker", "private-test-password")["state"]["player"]["id"]
        self.world.action(attacker, {"type": "choose_race", "race_id": "zetans"})
        origin = self.world._owned(attacker)
        self.player["protected_until"] = 0
        for race in economy85.VAULTS:
            with self.subTest(race=race):
                key = self.choose(race)
                self.planet["buildings"][key] = 10
                self.planet["ships"] = app.blank_ships()
                self.planet["defenses"] = dict.fromkeys(self.planet.get("defenses", {}), 0)
                self.planet["resources"] = {"metal": 14999., "crystal": 15000., "fuel": 25000.}
                origin["resources"] = dict.fromkeys(app.RESOURCES, float(app.MAX_RESOURCE))
                origin["ships"].update(interceptor=1, freighter=1)
                self.world._capture_planetary_intel(attacker, self.planet)
                self.world.action(attacker, {"type": "fleet", "mission": "attack", "target_id": self.planet["id"],
                                             "ships": {"interceptor": 1, "freighter": 1}})
                fleet = next(f for f in self.world.data["fleets"].values()
                             if f["owner_id"] == attacker and f["status"] == "outbound")
                self.world._complete_fleet(fleet)
                self.assertEqual(fleet["cargo"], {"metal": 0, "crystal": 0, "fuel": 3500})
                self.assertEqual(self.planet["resources"], {"metal": 14999., "crystal": 15000., "fuel": 21500.})

    def test_paid_upgrade_from_five_to_six_increases_real_protection(self):
        key = self.choose("symbionts")
        self.planet["buildings"].update(lab=2, living_vault=5)
        self.planet["resources"] = dict.fromkeys(app.RESOURCES, float(app.MAX_RESOURCE))
        self.world.action(self.owner, {"type": "build", "key": key})
        self.world._complete_queue(self.planet)
        self.assertEqual(self.planet["buildings"][key], 6)
        self.assertEqual(self.world._building_effects(self.planet)["protected_resources"], 9000)
        item = self.world._catalog(self.owner, self.planet, project_only=("buildings", key))["buildings"][0]
        self.assertEqual(item["building_effect"]["next"], 10500)

    def test_foreign_vault_does_not_add_to_owners_protection(self):
        key = self.choose("zetans")
        self.planet["buildings"].update(phase_vault=10, living_vault=40, armored_vault=20)
        self.assertEqual(self.world._building_effects(self.planet)["protected_resources"], 15000)

    def test_other_building_effects_keep_their_existing_caps(self):
        for race, buildings in races.UNIQUE_BUILDINGS.items():
            self.choose(race)
            for key, meta in buildings.items():
                if meta["effect"] == "protected_resources":
                    continue
                with self.subTest(race=race, building=key):
                    self.planet["buildings"][key] = 20
                    self.assertEqual(self.world._building_effects(self.planet)[meta["effect"]], meta["cap"])

    def test_catalog_copy_and_numbers_are_localized_in_every_language(self):
        key = self.choose("symbionts")
        self.planet["buildings"][key] = 10
        for language in ("pl", "en", "de", "es", "fr"):
            with self.subTest(language=language), language_scope(language):
                item = self.world._catalog(self.owner, self.planet, project_only=("buildings", key))["buildings"][0]
                source = races.UNIQUE_BUILDINGS["symbionts"][key]["spec"][1]
                catalog = json.loads((Path(app.__file__).parent / (language + ".json")).read_text())
                self.assertEqual(item["description"], catalog[source])
                self.assertIn("1500", item["description"])
                self.assertIn("15000", item["effect_current"])
                self.assertIn("16500", item["effect_next"])
                self.assertNotIn("7500", item["description"])


if __name__ == "__main__":
    unittest.main()

