"""Read-only numeric previews and static UI contracts, 0.7.5.

The Python tests run the server. GDScript input/layout tests are separate and
must run in Godot; static source checks here are not engine execution.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from server.main import World, RESOURCES, ECONOMY_MULTIPLIER
from server.races import RACES, UNIQUE_BUILDINGS
from server.i18n import language_scope

ROOT = Path(__file__).resolve().parents[1]

class CatalogDetailPreviewTests(unittest.TestCase):
    def setUp(self):
        self.w = World(':memory:', now=2_000_000_000, speed=1)
        self.addCleanup(self.w.close)
        account = self.w.register('Detail075', 'Local-only-075!')
        self.owner = account['state']['player']['id']
        self.w.action(self.owner, {'type':'choose_race','race_id':'zetans'})
        self.p = self.w._owned(self.owner)

    def entry(self, key, group='buildings'):
        return next(e for e in self.w._catalog(self.owner, self.p)[group] if e['key'] == key)

    def rows(self, entry):
        return {m['key']: m for m in entry['details']['metrics']}

    def test_mine_current_and_next_match_real_server_production(self):
        for key, resource in [('metal_mine','metal'),('crystal_mine','crystal'),('refinery','fuel')]:
            for level in (0,1,6,11):
                with self.subTest(key=key, level=level):
                    self.p['buildings'][key] = level
                    e = self.entry(key); rows = self.rows(e)
                    future = deepcopy(self.p); future['buildings'][key] += 1
                    self.assertAlmostEqual(rows['colony_'+resource]['current'], self.w.production(self.p)[resource], places=5)
                    self.assertAlmostEqual(rows['colony_'+resource]['next'], self.w.production(future)[resource], places=5)
                    self.assertAlmostEqual(rows['mine_'+resource]['current'], level * e['production_per_level'] * self.w.energy(self.p)['factor'], places=5)
                    self.assertAlmostEqual(rows['mine_'+resource]['next'], (level+1) * e['production_per_level'] * self.w.energy(future)['factor'], places=5)

    def test_next_level_recalculates_energy_shortage_not_just_linear_gain(self):
        self.p['buildings'].update(metal_mine=5, crystal_mine=5, refinery=5, power_plant=1)
        e=self.entry('metal_mine'); rows=self.rows(e)
        self.assertLess(rows['energy_efficiency']['next'], rows['energy_efficiency']['current'])
        expected=(6 * e['production_per_level']) * rows['energy_efficiency']['next']/100
        self.assertAlmostEqual(rows['mine_metal']['next'], expected, places=4)

    def test_no_energy_means_no_production_even_after_mine_upgrade(self):
        self.p['buildings']['power_plant']=0
        rows=self.rows(self.entry('crystal_mine'))
        self.assertEqual(rows['mine_crystal']['current'],0)
        self.assertEqual(rows['mine_crystal']['next'],0)

    def test_fractional_production_is_preserved(self):
        self.p['buildings'].update(metal_mine=1,power_plant=12)
        value=self.rows(self.entry('metal_mine'))['mine_metal']['current']
        self.assertNotEqual(value, int(value))
        self.assertEqual(ECONOMY_MULTIPLIER,.1)

    def test_preview_does_not_change_planet_player_queue_or_rng_data(self):
        before=deepcopy(self.w.data)
        for _ in range(3):self.w._catalog(self.owner,self.p)
        self.assertEqual(before,self.w.data)

    def test_power_plant_preview_includes_energy_and_all_real_output(self):
        self.p['buildings'].update(metal_mine=10,crystal_mine=9,refinery=8,power_plant=1)
        rows=self.rows(self.entry('power_plant'))
        future=deepcopy(self.p);future['buildings']['power_plant']+=1
        self.assertEqual(rows['energy_supply']['next'],self.w.energy(future)['supply'])
        for resource in RESOURCES:
            self.assertAlmostEqual(rows['colony_'+resource]['next'],self.w.production(future)[resource],places=5)

    def test_shipyard_unlocks_are_based_on_real_requirements(self):
        self.p['buildings']['shipyard']=1
        e=self.entry('shipyard');d=e['details']
        cruiser=self.w._specs(self.owner,'ships')['cruiser'][0]
        self.assertNotIn(cruiser,d['available_now']);self.assertIn(cruiser,d['unlocks_next'])
        self.assertIn('shipyard_speed_rule',d['notes'])
        self.assertNotIn('shipyard_unlocks_only',d['notes'])
        self.assertTrue(any(m['name']==cruiser and m['level']==2 for m in d['milestones']))

    def test_other_unmet_prerequisites_are_not_claimed_as_unlocked(self):
        self.p['buildings']['shipyard']=5
        self.p['buildings']['lab']=0
        d=self.entry('shipyard')['details']
        future=deepcopy(self.p);future['buildings']['shipyard']=6
        valid=[]
        for group in ('ships','defenses'):
            for key,spec in self.w._specs(self.owner,group).items():
                if all(r['met'] for r in self.w._entry_requirements(self.owner,future,group,key)):valid.append(spec[0])
        for name in d['unlocks_next']:self.assertIn(name,valid)

    def test_lab_has_current_next_counts_and_speed_rule(self):
        self.p['buildings']['lab']=0
        e=self.entry('lab');d=e['details'];rows=self.rows(e)
        self.assertEqual(rows['research_projects']['current'],0)
        self.assertGreater(rows['research_projects']['next'],0)
        self.assertIn('lab_speed_rule',d['notes'])
        self.assertNotIn('lab_unlocks_only',d['notes'])

    def test_all_buildings_and_research_have_current_next_information(self):
        for race in RACES:
            self.w._player(self.owner)['race_id']=race
            self.w._ensure_race_buildings(self.p)
            self.w._ensure_racial_research(self.w._player(self.owner))
            catalog=self.w._catalog(self.owner,self.p)
            for group in ('buildings','research'):
                for entry in catalog[group]:
                    with self.subTest(race=race,key=entry['key']):
                        self.assertTrue(entry.get('effect_current') or entry['details']['metrics'])
                        if entry['level']<entry['max_level']:
                            self.assertTrue(entry.get('effect_next') or any(m['next'] is not None for m in entry['details']['metrics']))
                        self.assertTrue(entry['description'])

    def test_maximum_levels_do_not_advertise_an_extra_numeric_upgrade(self):
        for key in self.w._specs(self.owner,'buildings'):
            self.p['buildings'][key]=5 if key in UNIQUE_BUILDINGS['zetans'] else 12
        for e in self.w._catalog(self.owner,self.p)['buildings']:
            for metric in e['details']['metrics']:self.assertIsNone(metric['next'])
            self.assertFalse(e['enabled'])

    def test_unique_production_and_energy_previews_include_colony_modifiers(self):
        self.p['buildings'].update(phase_matrix=2,metal_mine=8,crystal_mine=8,refinery=8,power_plant=2)
        e=self.entry('phase_matrix');rows=self.rows(e)
        future=deepcopy(self.p);future['buildings']['phase_matrix']+=1
        for resource in RESOURCES:
            self.assertAlmostEqual(rows['colony_'+resource]['next'],self.w.production(future)[resource],places=5)

    def test_basic_research_previews_use_real_fifteen_percent_per_level(self):
        for key,label in [('weapons','fleet_attack_bonus'),('propulsion','fleet_speed_bonus')]:
            self.w._player(self.owner)['research'][key]=3
            row=self.rows(self.entry(key,'research'))[label]
            self.assertEqual((row['current'],row['next']),(45,60))

    def test_all_five_languages_serialize_unlock_names(self):
        names=[]
        for locale in ('en','pl','de','es','fr'):
            with language_scope(locale):
                payload=json.loads(json.dumps(self.entry('shipyard'),ensure_ascii=False))
            names.append(payload['details']['available_now'])
        self.assertNotEqual(names[0],names[1])
        self.assertTrue(all(names))

    def test_schema_contains_no_unserializable_or_infinite_values(self):
        json.dumps(self.w._catalog(self.owner,self.p),allow_nan=False)

class CatalogUIStaticContracts(unittest.TestCase):
    def test_flat_server_is_same_and_balance_reset_id_unchanged(self):
        self.assertEqual((ROOT/'server/main.py').read_bytes(),(ROOT/'railway/app.py').read_bytes())
        self.assertIn('slow-economy-072',(ROOT/'server/balance_reset.py').read_text())

    def test_every_card_surface_uses_scroll_cancellable_gesture(self):
        text=(ROOT/'client/scripts/compact_ui.gd').read_text()
        card=(ROOT/'client/scripts/catalog_card.gd').read_text()
        self.assertIn('panel.set_script(CatalogCardScript)',text)
        self.assertIn('[controls["action"], controls["amount"]]',text)
        self.assertIn('NOTIFICATION_SCROLL_BEGIN',card)
        self.assertIn('_excluded(point)',card)
        self.assertIn('valid_tap',card)

    def test_description_not_tied_to_hidden_legacy_label(self):
        text=(ROOT/'client/scripts/catalog_details.gd').read_text()
        self.assertIn('entry.get("description", "")',text)
        self.assertNotIn('controls["description"].visible',text)
        self.assertIn('not reason.begins_with(I18n.t("Wymaga:"))',text)
        self.assertIn('seen.has(identity)',text)

    def test_meta_paragraph_cost_precedes_description_and_requirements(self):
        text=(ROOT/'client/scripts/catalog_details.gd').read_text()
        self.assertLess(text.index('I18n.t("Koszt: %s")'),text.index('sections.append(description)'))
        self.assertLess(text.index('sections.append(description)'),text.index('I18n.t("Wymagania")'))

    def test_wallet_never_wraps_legacy_label_on_compact_path(self):
        main=(ROOT/'client/scripts/main.gd').read_text().split('func _refresh_skills()',1)[1].split('\n\nfunc ',1)[0]
        self.assertIn('compact_ui.update_wallet(amount, enabled)',main)
        compact=(ROOT/'client/scripts/compact_ui.gd').read_text()
        wallet=compact.split('func update_wallet(',1)[1].split('\n\nfunc ',1)[0]
        self.assertIn('autowrap_mode = TextServer.AUTOWRAP_OFF',wallet)
        self.assertIn('size_flags_vertical = Control.SIZE_SHRINK_CENTER',wallet)
        self.assertIn('tooltip_text = I18n.t(',wallet)
        self.assertNotIn('button.text = I18n.t(',wallet)

if __name__=='__main__': unittest.main(verbosity=2)
