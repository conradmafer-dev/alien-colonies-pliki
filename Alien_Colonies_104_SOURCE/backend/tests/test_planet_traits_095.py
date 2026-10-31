"""Trait discovery, authoritative bonuses, immutable history and safe migration."""
import copy
import json
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from server import planet_traits, planetary, production_timing
from server.main import World
from server.i18n import language_scope

NOW = 1_900_000_000
PASSWORD = 'trait-test-password'


class PlanetTraitTests(unittest.TestCase):
    def setUp(self):
        with patch('server.planet_traits.secrets.token_hex', return_value='test-universe-095'):
            self.w = World(':memory:', now=NOW, speed=1)
        self.addCleanup(self.w.close)
        self.w.data['alien']['next_expansion_at'] = NOW + 100000
        # A fixed home removes randomness from discovery/range tests.
        self.w._choose_start_planet = lambda available: self.w.data['planets']['s1p1']
        self.account = self.w.register('Traits095', PASSWORD)
        self.owner = self.account['state']['player']['id']
        self.home = self.w._owned(self.owner)
        self.w.action(self.owner, {'type': 'choose_race', 'race_id': 'zetans'})
        self.home['rare_trait'] = ''
        self.home['resources'] = dict.fromkeys(('metal', 'crystal', 'fuel'), 10000000)
        self.home['ships']['scout'] = 30
        self.home['buildings'].update(lab=3, power_plant=8)

    def target(self, sid='s3'):
        system = next(s for s in self.w.data['systems'] if s['id'] == sid)
        return self.w.data['planets'][system['planet_ids'][0]]

    def view(self, planet, state=None):
        state = state or self.w.state(self.owner)
        return next((p for s in state['galaxy'] for p in s['planets'] if p['id'] == planet['id']), None)

    def scout(self, target):
        self.w.action(self.owner, {'type': 'fleet', 'mission': 'scout', 'target_id': target['id'], 'ships': {'scout': 1}})
        fleet = next(f for f in self.w.data['fleets'].values() if f['mission'] == 'scout' and f['status'] == 'outbound')
        self.w.advance(fleet['arrives_at'])

    def test_generation_is_rare_biome_compatible_and_stable_without_public_seed(self):
        planets = list(self.w.data['planets'].values())
        rare = [p for p in planets if p['rare_trait']]
        self.assertTrue(.10 < len(rare) / len(planets) < .20)
        self.assertEqual({p['rare_trait'] for p in rare}, set(planet_traits.TRAITS))
        for p in rare:
            self.assertIn(p['environment']['type'], planet_traits.TRAITS[p['rare_trait']]['biomes'])
        old = {p['id']: p['rare_trait'] for p in planets}
        planet_traits.ensure(self.w.data, NOW + 500)
        self.assertEqual(old, {p['id']: p['rare_trait'] for p in planets})
        self.assertEqual(self.w.data['planet_traits_from'], NOW)
        wire = json.dumps(self.w.state(self.owner))
        self.assertNotIn('planet_traits_seed', wire)
        self.assertNotIn('rare_trait', wire)
        self.assertNotIn(self.w.data['planet_traits_seed'], wire)

    def test_resource_traits_apply_once_to_income_catalog_and_stocks(self):
        for resource, key in [('metal', 'metal_veins'), ('crystal', 'crystal_geodes'), ('fuel', 'fuel_reservoirs')]:
            self.home['rare_trait'] = ''
            old = self.w.production(self.home)
            self.home['rare_trait'] = key
            new = self.w.production(self.home)
            for k in old:
                self.assertAlmostEqual(new[k], old[k] * (1.3 if k == resource else 1))
            item = next(x for x in self.w._catalog(self.owner, self.home)['buildings'] if x.get('production_resource') == resource)
            actual = next(m['current'] for m in item['details']['metrics'] if m['key'] == 'colony_' + resource)
            self.assertAlmostEqual(actual, new[resource], places=5)
            before = copy.deepcopy(self.home['resources'])
            self.w.advance(self.w.now + 3600)
            for k in old:
                self.assertAlmostEqual(self.home['resources'][k] - before[k], new[k], places=5)

    def test_geothermal_applies_only_to_local_power_and_improves_energy_limited_income(self):
        self.home['buildings'].update(power_plant=1, metal_mine=8, crystal_mine=8, refinery=8)
        old_energy, old_rates = self.w.energy(self.home), self.w.production(self.home)
        self.home['rare_trait'] = 'geothermal_sources'
        self.assertAlmostEqual(self.w.energy(self.home)['supply'], 1.25 * old_energy['supply'])
        for key, rate in self.w.production(self.home).items():
            self.assertAlmostEqual(rate, old_rates[key] * 1.25)
        with patch.object(self.w, '_dyson_power', return_value=500000):
            self.assertEqual(self.w.energy(self.home)['supply'], 500000 + 1.25 * old_energy['supply'])
        item = next(x for x in self.w._catalog(self.owner, self.home)['buildings'] if x['key'] == 'power_plant')
        self.assertEqual(item['energy_supply_per_level'], 1.25 * old_energy['supply'])
        self.assertEqual(self.w.energy(self.home, traits_enabled=False), old_energy)

    def test_archives_speed_actual_local_research_with_single_rounding_and_preserve_running_jobs(self):
        def quote(group, key):
            return next(x for x in self.w._catalog(self.owner, self.home)[group] if x['key'] == key)
        baseline = {g: quote(g, k)['seconds'] for g, k in [('buildings', 'metal_mine'), ('ships', 'scout'), ('research', 'propulsion')]}
        self.home['rare_trait'] = 'ancient_archives'
        for group, key in [('buildings', 'metal_mine'), ('ships', 'scout')]:
            self.assertEqual(quote(group, key)['seconds'], baseline[group])
        entry = quote('research', 'propulsion')
        expected = production_timing.project_seconds(self.w._specs(self.owner, 'research')['propulsion'][3], 0,
            'research', self.home['buildings'], 1, local_speed=1.15)
        self.assertEqual(entry['seconds'], expected)
        self.assertEqual(entry['planet_trait']['id'], 'ancient_archives')
        self.w.action(self.owner, {'type': 'research', 'key': 'propulsion', 'seconds': 1, 'local_speed': 999})
        task = copy.deepcopy(self.home['queue'][0])
        self.assertEqual(task['ends_at'] - self.w.now, expected)
        other = self.target(); other.update(owner_id=self.owner, owner_type='player')
        other['buildings'] = dict(self.home['buildings']); other['rare_trait'] = ''
        self.assertEqual(self.w._project_seconds(self.owner, other, 'research', 'propulsion', 0), baseline['research'])
        self.home['buildings']['lab'] = 12
        planet_traits.ensure(self.w.data, self.w.now)
        self.assertEqual(self.home['queue'][0], task)
        self.w.advance(task['ends_at'])
        self.assertEqual(self.w._player(self.owner)['research']['propulsion'], 1)

    def test_scout_reveals_only_target_on_arrival_neighbours_and_other_players_stay_unknown(self):
        system = next(s for s in self.w.data['systems'] if s['galaxy_id'] == self.home['galaxy_id'] and len(s['planet_ids']) >= 2 and s['id'] != self.home['system_id'])
        target, neighbour = [self.w.data['planets'][pid] for pid in system['planet_ids'][:2]]
        target['rare_trait'], neighbour['rare_trait'] = 'crystal_geodes', 'metal_veins'
        self.w.action(self.owner, {'type': 'fleet', 'mission': 'scout', 'target_id': target['id'], 'ships': {'scout': 1}})
        self.assertIsNone(self.view(target))
        fleet = next(f for f in self.w.data['fleets'].values() if f['status'] == 'outbound')
        self.w.advance(fleet['arrives_at'] - 1)
        self.assertIsNone(self.view(target))
        self.w.advance(fleet['arrives_at'])
        seen = self.view(target)
        self.assertEqual(seen['environment']['trait']['id'], 'crystal_geodes')
        self.assertEqual(seen['planet_scout']['environment']['trait']['id'], 'crystal_geodes')
        self.assertEqual(self.view(neighbour)['environment']['trait'], {'status': 'unknown'})
        self.assertEqual(self.view(neighbour)['environment']['multipliers'], planetary.multipliers(neighbour, False))
        report = next(r for r in self.w.state(self.owner)['reports'] if 'planet_scout' in r)
        self.assertEqual(report['planet_scout']['environment']['trait']['id'], 'crystal_geodes')
        self.w._choose_start_planet = lambda available: self.w.data['planets']['s10p1']
        other = self.w.register('Unaware095', PASSWORD)['state']
        self.assertNotIn(target['id'], [p['id'] for s in other['galaxy'] for p in s['planets']])

    def test_observatories_combine_local_ranges_without_revealing_remote_galaxies(self):
        nearby, far = self.target('s2'), self.target('s5')
        nearby['rare_trait'], far['rare_trait'] = 'geothermal_sources', 'fuel_reservoirs'
        remote = next(p for p in self.w.data['planets'].values() if p['galaxy_id'] != self.home['galaxy_id'])
        remote['rare_trait'] = 'ancient_archives'
        self.home['buildings']['observatory'] = 1
        self.w.advance(self.w.now)
        self.assertEqual(self.view(nearby)['environment']['trait']['id'], 'geothermal_sources')
        self.assertNotIn('fields', self.view(nearby)['environment'])
        for key in ('observed_buildings', 'ships', 'resources', 'defenses'):
            self.assertNotIn(key, self.view(nearby))
        self.assertIsNone(self.view(far)); self.assertIsNone(self.view(remote))
        colony = self.target('s6'); colony.update(owner_id=self.owner, owner_type='player')
        colony['buildings']['observatory'] = 1
        self.w.advance(self.w.now)
        self.assertEqual(self.view(far)['environment']['trait']['id'], 'fuel_reservoirs')
        self.assertIsNone(self.view(remote))
        self.home['buildings']['observatory'] = 12
        self.w.advance(self.w.now)
        self.assertIsNone(self.view(remote))
        self.w._capture_planetary_intel(self.owner, remote)
        self.assertEqual(self.view(remote)['environment']['trait']['id'], 'ancient_archives')

    def test_observatory_order_reveals_only_after_completion(self):
        target = self.target('s2'); target['rare_trait'] = 'metal_veins'
        self.w.action(self.owner, {'type': 'build', 'key': 'observatory'})
        self.assertIsNone(self.view(target))
        self.w.advance(self.home['queue'][0]['ends_at'])
        self.assertEqual(self.view(target)['environment']['trait']['id'], 'metal_veins')

    def test_ordinary_world_and_unknown_world_are_distinct(self):
        target = self.target(); target['rare_trait'] = ''
        self.scout(target)
        self.assertEqual(self.view(target)['environment']['trait'], {'status': 'none'})
        self.assertEqual(self.w.state(self.owner)['environment']['trait'], {'status': 'none'})

    def test_discovery_survives_sensor_loss_and_restart_without_live_owner_or_building_leak(self):
        target = self.target('s2'); target['rare_trait'] = 'metal_veins'
        self.home['buildings']['observatory'] = 1; self.w.advance(self.w.now)
        original = copy.deepcopy(self.view(target))
        self.home['buildings']['observatory'] = 0
        target['buildings']['metal_mine'] = 12
        # An unrelated owner is required; do not make the inspected colony ours.
        self.w._choose_start_planet = lambda available: self.w.data['planets']['s10p1']
        stranger = self.w.register('Foreign095', PASSWORD)['state']['player']['id']
        target.update(owner_type='player', owner_id=stranger)
        self.w.advance(self.w.now + 50)
        remembered = self.view(target)
        self.assertEqual(remembered['visibility'], 'remembered')
        self.assertEqual(remembered['owner_id'], original['owner_id'])
        self.assertNotIn('observed_buildings', remembered)
        self.assertNotIn('fields', remembered['environment'])
        self.assertEqual(remembered['environment']['trait']['id'], 'metal_veins')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'saved.sqlite3'
            db = sqlite3.connect(path); self.w.db.backup(db); db.close()
            restored = World(path, now=self.w.now)
            try:
                v = next(p for s in restored.state(self.owner)['galaxy'] for p in s['planets'] if p['id'] == target['id'])
                self.assertEqual(v, remembered)
                self.assertEqual(restored.data['planet_traits_seed'], self.w.data['planet_traits_seed'])
            finally: restored.close()

    def test_colonization_and_account_deletion_do_not_reroll_traits(self):
        target = self.target(); target['rare_trait'] = 'ancient_archives'
        self.w._capture_planetary_intel(self.owner, target)
        self.w.action(self.owner, {'type': 'fleet', 'mission': 'colonize', 'target_id': target['id'], 'ships': {'colonizer': 1}})
        fleet = next(f for f in self.w.data['fleets'].values() if f['mission'] == 'colonize')
        self.w.advance(fleet['arrives_at'])
        self.assertEqual(target['owner_id'], self.owner)
        self.assertEqual(target['rare_trait'], 'ancient_archives')
        self.w.account_delete(self.account['token'], PASSWORD, 'DELETE ACCOUNT')
        self.assertEqual(self.w.data['planets'][target['id']]['rare_trait'], 'ancient_archives')
        planet_traits.ensure(self.w.data, self.w.now)
        self.assertEqual(self.w.data['planets'][target['id']]['rare_trait'], 'ancient_archives')

    def test_reports_remain_frozen_and_legacy_reports_never_gain_unrecorded_traits(self):
        target = self.target(); target['rare_trait'] = 'fuel_reservoirs'
        self.scout(target)
        report = next(r for r in self.w._player(self.owner)['reports'] if 'planet_snapshot' in r)
        snapshot = copy.deepcopy(report['planet_snapshot'])
        legacy = copy.deepcopy(snapshot); legacy['identity'].pop('rare_trait')
        self.assertEqual(self.w._render_planet_scout(legacy)['environment']['trait'], {'status': 'unknown'})
        target['rare_trait'] = 'ancient_archives'  # An admin edit must not rewrite history.
        self.w._capture_planetary_intel(self.owner, target)
        self.assertEqual(report['planet_snapshot'], snapshot)
        self.assertEqual(self.w._render_planet_scout(snapshot)['environment']['trait']['id'], 'fuel_reservoirs')
        for language in ('pl', 'en', 'de', 'es', 'fr'):
            with language_scope(language):
                rendered = self.w._render_planet_scout(snapshot)['environment']['trait']
                self.assertTrue(rendered['name']); self.assertIn('30', rendered['description'])

    def test_migration_keeps_stocks_and_deadlines_and_no_retroactive_bonus(self):
        self.home['buildings'].update(power_plant=1, metal_mine=8, crystal_mine=8, refinery=8)
        old_rates = self.w.production(self.home)
        before = copy.deepcopy(self.home['resources'])
        self.w.action(self.owner, {'type': 'research', 'key': 'propulsion'})
        before = copy.deepcopy(self.home['resources'])
        task = copy.deepcopy(self.home['queue'][0])
        # Construct a genuine pre-feature persisted snapshot, with no private keys.
        for key in ('planet_traits_schema', 'planet_traits_from', 'planet_traits_seed'):
            self.w.data.pop(key)
        for p in self.w.data['planets'].values(): p.pop('rare_trait')
        for player in self.w.data['players'].values(): player.pop('trait_intel', None)
        self.w._save()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'legacy.sqlite3'
            db = sqlite3.connect(path); self.w.db.backup(db); db.close()
            with patch('server.planet_traits.generate', return_value='geothermal_sources'):
                restored = World(path, now=NOW + 60)
            try:
                p = restored.data['planets'][self.home['id']]
                self.assertEqual(p['queue'], [task])
                self.assertEqual(restored.data['planet_traits_from'], NOW + 60)
                for resource in before:
                    self.assertAlmostEqual(p['resources'][resource], before[resource] + old_rates[resource]/60, places=6)
                restored.advance(NOW + 120)
                for resource in before:
                    self.assertAlmostEqual(p['resources'][resource], before[resource] + old_rates[resource]*2.25/60, places=6)
                self.assertTrue(list((Path(folder)/'backups').glob('*.sqlite3')))
                self.assertEqual(p['queue'], [task])
            finally: restored.close()

    def test_split_offline_interval_honours_economy_terrain_and_trait_epochs(self):
        self.home['rare_trait'] = 'metal_veins'
        self.home['environment']['type'] = 'rust'
        self.w.data.update(economy_slow_from=NOW+100, planetary_from=NOW+200, planet_traits_from=NOW+300)
        stock = self.home['resources']['metal']
        base = self.w.production(self.home, traits_enabled=False, terrain_enabled=False)['metal']
        self.w.advance(NOW+400)
        expected = base * (1000 + 100 + 165 + 214.5) / 3600
        self.assertAlmostEqual(self.home['resources']['metal'] - stock, expected, places=6)


if __name__ == '__main__': unittest.main()
