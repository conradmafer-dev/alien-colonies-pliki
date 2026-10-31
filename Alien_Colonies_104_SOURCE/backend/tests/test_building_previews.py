"""Contract of the existing read-only catalogue used by the new browser UI."""
import copy
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from i18n import language_scope


class BuildingPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.world = app.World(str(Path(self.temp.name) / 'preview.sqlite3'), 1)

    def tearDown(self):
        self.world.close()
        self.temp.cleanup()

    def colony(self, race):
        account = self.world.register('preview_' + race, 'LocalTest-89357')
        owner = account['state']['player']['id']
        planet_id = account['state']['planet_id']
        self.world.action(owner, {'type': 'choose_race', 'race_id': race, 'planet_id': planet_id})
        return owner, self.world.data['planets'][planet_id]

    def test_all_races_current_next_preview_is_read_only_and_uses_real_production(self):
        for race in ('symbionts', 'zetans', 'automatons'):
            with self.subTest(race=race), language_scope('pl'):
                owner, planet = self.colony(race)
                planet['buildings'].update(metal_mine=4, crystal_mine=4, refinery=4, power_plant=1)
                before = copy.deepcopy(self.world.data)
                items = self.world._catalog(owner, planet)['buildings']
                self.assertEqual(self.world.data, before)
                self.assertEqual(len(items), 14)
                for item in items:
                    for row in item['details']['metrics']:
                        self.assertTrue(math.isfinite(row['current']))
                        if row['next'] is not None:
                            self.assertTrue(math.isfinite(row['next']))
                    if item.get('production_resource'):
                        resource = item['production_resource']
                        future = {**planet, 'buildings': {**planet['buildings'], item['key']: item['level'] + 1}}
                        row = next(row for row in item['details']['metrics'] if row['key'] == 'colony_' + resource)
                        self.assertAlmostEqual(row['current'], self.world.production(planet)[resource], places=5)
                        self.assertAlmostEqual(row['next'], self.world.production(future)[resource], places=5)

    def test_cap_has_no_future_metrics_or_racial_effect(self):
        owner, planet = self.colony('symbionts')
        for key in planet['buildings']:
            planet['buildings'][key] = 5 if key in app.UNIQUE_BUILDINGS['symbionts'] else 12
        for item in self.world._catalog(owner, planet)['buildings']:
            self.assertEqual(item['level'], item['max_level'])
            self.assertFalse(item['enabled'])
            self.assertTrue(all(row['next'] is None for row in item['details']['metrics']))
            if item.get('building_effect'):
                self.assertIsNone(item['building_effect']['next'])

    def test_facility_level_three_really_provides_twenty_percent_speed(self):
        owner, planet = self.colony('zetans')
        planet['buildings'].update(lab=3, shipyard=3)
        for item in self.world._catalog(owner, planet)['buildings']:
            if item['key'] in ('lab', 'shipyard'):
                key = 'lab_speed_bonus' if item['key'] == 'lab' else 'shipyard_speed_bonus'
                row = next(row for row in item['details']['metrics'] if row['key'] == key)
                self.assertEqual(row['current'], 20)
                self.assertEqual(row['next'], 30)


if __name__ == '__main__':
    unittest.main()
