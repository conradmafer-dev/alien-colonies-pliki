"""Local racial structures: authoritative actions, travel, settlement and combat."""
import copy
import math
from pathlib import Path
import tempfile
import unittest

from server.main import BUILDINGS, RESOURCES, GameError, blank_ships
from tests.world_fixture import LocalTestWorld as World
from server.races import RACES, UNIQUE_BUILDINGS
from server import skill_tree, swarm

START = 1_900_000_000.0


class UniqueBuildingScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'world.sqlite3')
        self.world = World(self.path, speed=10, now=START)
        self.player = self.world.register('Unique Builder', 'password-123')['state']['player']['id']
        self.world.data['alien']['next_expansion_at'] = START + 1_000_000

    def tearDown(self):
        self.world.close()
        self.tmp.cleanup()

    def choose(self, race):
        self.world.action(self.player, {'type': 'choose_race', 'race_id': race})
        return self.home()

    def home(self):
        return self.world._owned(self.player)

    def entry(self, key, group='buildings', planet=None):
        return next(item for item in self.world._catalog(self.player, planet or self.home())[group] if item['key'] == key)

    def richest(self):
        self.home()['resources'] = dict.fromkeys(RESOURCES, 1_000_000.0)

    def extra_colony(self):
        p = next(p for p in self.world.data['planets'].values() if p['owner_type'] == 'empty')
        p.update(owner_id=self.player, owner_type='player')
        p['buildings'] = dict.fromkeys(BUILDINGS, 1)
        self.world._ensure_race_buildings(p)
        return p

    def target(self, khar=False):
        target = next(p for p in self.world.data['planets'].values() if p['owner_type'] == 'empty')
        if khar:
            # A controlled low-defense legacy target isolates racial mechanics;
            # it is not evidence that the actual new fortresses are easy.
            swarm.seed(target, self.world.now, hive=False)
            target['ships'] = dict.fromkeys(swarm.SHIPS, 0)
        return target

    def launch(self, mission, target, ships):
        result = self.world.action(self.player, {'type': 'fleet', 'mission': mission, 'target_id': target['id'], 'ships': ships})
        fid = result['state']['fleets'][-1]['id']
        return self.world.data['fleets'][fid]

    def test_common_buildings_precede_six_own_exclusive_structures_at_zero(self):
        for race in RACES:
            with self.subTest(race=race):
                player = self.world.register('Catalog ' + race, 'password-123')['state']['player']['id']
                state = self.world.action(player, {'type': 'choose_race', 'race_id': race})['state']
                items = state['catalog']['buildings']
                self.assertEqual(len(items), 12)
                self.assertEqual([row['key'] for row in items[:6]], list(BUILDINGS))
                self.assertEqual([row['key'] for row in items[6:]], list(UNIQUE_BUILDINGS[race]))
                self.assertTrue(items[6]['enabled'])
                self.assertFalse(items[6]['requirements'])
                self.assertEqual(state['player']['swarm_crystals'], 0)
                for row in items[6:]:
                    self.assertEqual(row['level'], 0)
                    self.assertTrue(row['unique'])
                    self.assertEqual(row['max_level'], 5)
                    self.assertEqual(row['art_key'], f"races/{race}/{row['key']}")
                    self.assertNotEqual(row['effect_current'], row['effect_next'])
                for row in items[7:]:
                    self.assertFalse(row['enabled'])
                    expected = UNIQUE_BUILDINGS[race][row['key']]['requirements'][0]
                    self.assertEqual(row['requirements'][0]['level'], expected[-1])
                    if row in items[7:9]:
                        self.assertEqual(row['requirements'][0]['level'], 2)
                    self.assertFalse(row['requirements'][0]['met'])

    def test_actual_unique_purchase_respects_cost_timer_idempotency_and_level_cap(self):
        p = self.choose('zetans')
        initial = copy.deepcopy(p['resources'])
        entry = self.entry('phase_matrix')
        payload = {'type': 'build', 'key': 'phase_matrix', 'request_id': 'phase-once'}
        self.world.action(self.player, payload)
        for resource, amount in entry['cost'].items():
            self.assertEqual(p['resources'][resource], initial[resource] - amount)
        self.assertEqual(p['queue'][0]['seconds'], entry['seconds'])
        after = copy.deepcopy(self.world.data)
        self.world.action(self.player, payload)
        self.assertEqual(self.world.data, after)
        self.world._complete_queue(p)
        self.assertEqual(p['buildings']['phase_matrix'], 1)
        self.assertIn('Matryca Fazowa', self.world.state(self.player)['reports'][0]['text'])
        p['buildings']['phase_matrix'] = 5
        entry = self.entry('phase_matrix')
        self.assertFalse(entry['enabled'])
        self.assertIn('5', entry['reason'])
        self.assertEqual(entry['effect_next'], 'Maksymalny poziom.')
        with self.assertRaises(GameError):
            self.world.action(self.player, {'type': 'build', 'key': 'phase_matrix'})

    def test_foreign_structures_are_rejected_even_with_all_foreign_skill_roots(self):
        p = self.choose('zetans')
        self.world.data['players'][self.player]['skill_nodes'] = [node['id'] for node in skill_tree.graph()['nodes']]
        before = copy.deepcopy(self.world.data)
        for race in ('automatons', 'symbionts'):
            for key in UNIQUE_BUILDINGS[race]:
                with self.assertRaises(GameError):
                    self.world.action(self.player, {'type': 'build', 'key': key})
                self.assertEqual(self.world.data, before)
        # A foreign stale key cannot grant an economic effect either.
        p['buildings']['world_root'] = 5
        self.assertNotIn('building_time_reduction', self.world._building_effects(p))

    def test_prerequisites_are_server_enforced_then_unlock_at_actual_building_level(self):
        p = self.choose('zetans')
        before = copy.deepcopy(p)
        with self.assertRaises(GameError):
            self.world.action(self.player, {'type': 'build', 'key': 'echo_observatory'})
        self.assertEqual(p, before)
        p['buildings']['lab'] = 2
        entry = self.entry('echo_observatory')
        self.assertTrue(entry['requirements'][0]['met'])
        self.assertTrue(entry['enabled'])
        self.world.action(self.player, {'type': 'build', 'key': 'echo_observatory'})
        self.world._complete_queue(p)
        self.assertEqual(p['buildings']['echo_observatory'], 1)

    def test_old_colonies_migrate_without_free_levels_and_new_colonies_initialize_zero(self):
        p = self.choose('symbionts')
        old_colony = self.extra_colony()
        for key in UNIQUE_BUILDINGS['symbionts']:
            p['buildings'].pop(key)
            old_colony['buildings'].pop(key)
        p['buildings']['metal_mine'] = 4
        before = dict(p['resources'])
        self.world.close()
        self.world = World(self.path, speed=10, now=START)
        p = self.home()
        self.assertEqual(p['resources'], before)
        self.assertEqual(p['buildings']['metal_mine'], 4)
        for colony in (p, self.world.data['planets'][old_colony['id']]):
            self.assertTrue(all(colony['buildings'][key] == 0 for key in UNIQUE_BUILDINGS['symbionts']))
        target = self.target()
        fleet = self.launch('colonize', target, {'colonizer': 1})
        self.world._complete_fleet(fleet)
        self.assertTrue(all(target['buildings'][key] == 0 for key in UNIQUE_BUILDINGS['symbionts']))
        self.assertEqual(len(self.world.state(self.player, target['id'])['catalog']['buildings']), 12)

    def test_phase_matrix_changes_only_local_energy_and_real_production(self):
        p = self.choose('zetans')
        other = self.extra_colony()
        p['buildings']['metal_mine'] = 5
        before_energy = self.world.energy(p)
        before_production = self.world.production(p)
        other_before = self.world.energy(other)
        p['buildings']['phase_matrix'] = 5
        self.assertAlmostEqual(self.world.energy(p)['used'], before_energy['used'] * .7)
        self.assertGreater(self.world.production(p)['metal'], before_production['metal'])
        self.assertEqual(self.world.energy(other), other_before)
        self.assertAlmostEqual(self.entry('metal_mine')['energy_per_level'], 23 * .7)
        self.world._produce(3600)
        self.assertEqual(self.world.data['players'][self.player]['swarm_crystals'], 0)

    def test_echo_quote_launch_and_return_keep_launch_duration_after_upgrade(self):
        p = self.choose('zetans')
        target = self.target(True)
        payload = {'mission': 'scout', 'target_id': target['id'], 'ships': {'scout': 1}}
        baseline = self.world.preview(self.player, payload)
        p['buildings']['echo_observatory'] = 2
        quote = self.world.preview(self.player, payload)
        self.assertEqual(quote['seconds'], math.ceil(baseline['seconds'] * .84))
        self.assertEqual(quote['fuel_cost'], baseline['fuel_cost'])
        fleet = self.launch('scout', target, {'scout': 1})
        self.assertEqual(fleet['seconds'], quote['seconds'])
        p['buildings']['echo_observatory'] = 5
        self.world._complete_fleet(fleet)
        self.assertEqual(fleet['arrives_at'] - self.world.now, quote['seconds'])
        self.assertEqual(fleet['building_effects']['scout_time_reduction'], .16)

    def test_archive_refunds_paid_crystal_once_only_on_completion_using_purchase_level(self):
        p = self.choose('zetans')
        p['buildings']['synapse_archive'] = 2
        entry = self.entry('weapons', 'research')
        before = p['resources']['crystal']
        payload = {'type': 'research', 'key': 'weapons', 'request_id': 'research-once'}
        self.world.action(self.player, payload)
        self.assertEqual(p['resources']['crystal'], before - entry['cost']['crystal'])
        refund = math.floor(entry['cost']['crystal'] * .06)
        self.assertEqual(p['queue'][0]['crystal_refund'], refund)
        p['buildings']['synapse_archive'] = 5
        self.world._complete_queue(p)
        self.assertEqual(p['resources']['crystal'], before - entry['cost']['crystal'] + refund)
        self.assertEqual(self.world.data['players'][self.player]['swarm_crystals'], 0)
        self.assertIn(str(refund), self.world.state(self.player)['reports'][0]['text'])
        after = copy.deepcopy(self.world.data)
        self.world.action(self.player, payload)
        self.assertEqual(self.world.data, after)

    def test_old_research_queue_has_no_retroactive_archive_refund(self):
        p = self.choose('zetans')
        self.world.action(self.player, {'type': 'research', 'key': 'weapons'})
        p['queue'][0].pop('crystal_refund')
        p['buildings']['synapse_archive'] = 5
        before = p['resources']['crystal']
        self.world._complete_queue(p)
        self.assertEqual(p['resources']['crystal'], before)

    def test_serial_forge_batch_matches_catalog_contract_single_and_cap(self):
        p = self.choose('automatons')
        self.richest()
        p['buildings']['serial_forge'] = 5
        for amount in (1, 2, 5, 20):
            entry = self.entry('scout', 'ships')
            reduction = min(.30, .075 * (amount - 1))
            self.assertEqual(entry['batch_time_reduction_per_extra'], .075)
            before = p['resources']['metal']
            self.world.action(self.player, {'type': 'ship', 'key': 'scout', 'amount': amount})
            self.assertEqual(p['queue'][0]['seconds'], max(1, math.ceil(entry['seconds'] * amount * (1 - reduction))))
            self.assertEqual(p['resources']['metal'], before - entry['cost']['metal'] * amount)
            self.world._complete_queue(p)
        other = self.extra_colony()
        self.assertEqual(self.entry('scout', 'ships', other)['batch_time_reduction_per_extra'], 0)

    def test_world_root_speeds_all_local_buildings_at_every_buildable_level(self):
        p = self.choose('symbionts')
        other = self.extra_colony()
        self.richest()
        other_before = self.entry('metal_mine', planet=other)['seconds']
        research_before = self.entry('weapons', 'research')['seconds']
        ships_before = self.entry('scout', 'ships')['seconds']
        p['buildings']['world_root'] = 5
        for key, spec in self.world._specs(self.player, 'buildings').items():
            if key == 'world_root':
                continue
            original_level = p['buildings'][key]
            for level in ((0, 2, 3, 8, 11) if key in BUILDINGS else (0, 2, 4)):
                with self.subTest(key=key, level=level):
                    p['buildings'][key] = level
                    self.assertEqual(self.entry(key)['seconds'], math.ceil(spec[3] * 1.3 ** level / 10 * .6))
            # Isolate the Root: another leveled structure can now speed ships.
            p['buildings'][key] = original_level
        self.assertEqual(self.entry('metal_mine', planet=other)['seconds'], other_before)
        self.assertEqual(self.entry('weapons', 'research')['seconds'], research_before)
        self.assertEqual(self.entry('scout', 'ships')['seconds'], ships_before)
        p['buildings']['metal_mine'] = 8
        quoted_seconds = self.entry('metal_mine')['seconds']
        self.world.action(self.player, {'type': 'build', 'key': 'metal_mine'})
        self.assertEqual(p['queue'][0]['seconds'], quoted_seconds)
        self.world._complete_queue(p)
        self.assertEqual(p['buildings']['metal_mine'], 9)

    def test_world_root_own_upgrade_uses_completed_level_and_keeps_queued_time(self):
        p = self.choose('symbionts')
        self.richest()
        p['buildings']['world_root'] = 3
        seconds = math.ceil(UNIQUE_BUILDINGS['symbionts']['world_root']['spec'][3] * 1.3 ** 3 / 10 * .76)
        self.assertEqual(self.entry('world_root')['seconds'], seconds)
        payload = {'type': 'build', 'key': 'world_root', 'request_id': 'root-once'}
        self.world.action(self.player, payload)
        self.assertEqual(p['queue'][0]['seconds'], seconds)
        self.assertEqual(p['buildings']['world_root'], 3)
        self.world._complete_queue(p)
        self.assertEqual(p['buildings']['world_root'], 4)
        self.assertEqual(self.entry('world_root')['seconds'], math.ceil(240 * 1.3 ** 4 / 10 * .68))
        after = copy.deepcopy(self.world.data)
        self.world.action(self.player, payload)
        self.assertEqual(self.world.data, after)

    def test_pioneer_nursery_colony_head_start_snapshots_departure_and_survives_restart(self):
        p = self.choose('symbionts')
        target = self.target()
        payload = {'mission': 'colonize', 'target_id': target['id'], 'ships': {'colonizer': 1}}
        baseline = self.world.preview(self.player, payload)
        self.assertEqual(baseline['colony_start_level'], 1)
        scout_payload = {'mission': 'scout', 'target_id': target['id'], 'ships': {'scout': 1}}
        scout_before = self.world.preview(self.player, scout_payload)
        p['buildings']['pioneer_nursery'] = 2
        quote = self.world.preview(self.player, payload)
        self.assertEqual(quote['colony_start_level'], 3)
        self.assertIn('poziomie 3', quote['message'])
        self.assertEqual(quote['fuel_cost'], baseline['fuel_cost'])
        self.assertEqual(quote['seconds'], baseline['seconds'])
        self.assertEqual(self.world.preview(self.player, scout_payload), scout_before)
        before = p['resources']['fuel']
        fleet = self.launch('colonize', target, {'colonizer': 1})
        self.assertEqual(p['resources']['fuel'], before - quote['fuel_cost'])
        self.assertEqual(fleet['building_effects']['colony_start_building_bonus'], 2)
        self.assertNotIn('colonization_fuel_reduction', fleet['building_effects'])
        p['buildings']['pioneer_nursery'] = 5
        self.world.close()
        self.world = World(self.path, speed=10, now=START)
        target = self.world.data['planets'][target['id']]
        fleet = self.world.data['fleets'][fleet['id']]
        self.world._complete_fleet(fleet)
        for key in ('metal_mine', 'crystal_mine', 'refinery', 'power_plant'):
            self.assertEqual(target['buildings'][key], 3)
        self.assertEqual(target['buildings']['shipyard'], 0)
        self.assertEqual(target['buildings']['lab'], 0)
        self.assertTrue(all(target['buildings'][key] == 0 for key in UNIQUE_BUILDINGS['symbionts']))
        self.assertEqual(target['resources'], {'metal': 450., 'crystal': 250., 'fuel': 150.})
        self.assertEqual(target['ships'], blank_ships())
        self.assertIn('poziomie 3', self.world.state(self.player)['reports'][0]['text'])
        after = copy.deepcopy(self.world.data)
        self.world._complete_fleet(fleet)
        self.assertEqual(self.world.data, after)

    def test_nursery_level_one_and_five_start_economy_at_two_and_six(self):
        p = self.choose('symbionts')
        p['ships']['colonizer'] = 2
        for nursery_level, starting_level in ((1, 2), (5, 6)):
            p['buildings']['pioneer_nursery'] = nursery_level
            target = self.target()
            fleet = self.launch('colonize', target, {'colonizer': 1})
            self.world._complete_fleet(fleet)
            self.assertEqual(target['buildings']['metal_mine'], starting_level)

    def test_nursery_does_not_change_failed_colony_or_grant_retroactive_bonus(self):
        p = self.choose('symbionts')
        p['buildings']['pioneer_nursery'] = 5
        p['ships']['colonizer'] = 2
        target = self.target()
        fleet = self.launch('colonize', target, {'colonizer': 1})
        target.update(owner_id='khar', owner_type='alien')
        before = copy.deepcopy(target)
        self.world._complete_fleet(fleet)
        self.assertEqual(target, before)
        self.assertEqual(fleet['status'], 'returning')
        self.assertEqual(fleet['ships']['colonizer'], 1)
        self.world._complete_fleet(fleet)
        target = self.target()
        legacy = self.launch('colonize', target, {'colonizer': 1})
        legacy['building_effects'] = {'colonization_fuel_reduction': .5}
        self.world._complete_fleet(legacy)
        self.assertEqual(target['buildings']['metal_mine'], 1)

    def test_foreign_nursery_snapshot_cannot_grant_a_colony_head_start(self):
        self.choose('zetans')
        target = self.target()
        fleet = self.launch('colonize', target, {'colonizer': 1})
        fleet['building_effects'] = {'colony_start_building_bonus': 5}
        self.world._complete_fleet(fleet)
        self.assertEqual(target['buildings']['metal_mine'], 1)

    def test_nursery_snapshot_is_retained_if_origin_later_changes_owner(self):
        p = self.choose('symbionts')
        backup = self.extra_colony()
        p['buildings']['pioneer_nursery'] = 2
        target = self.target()
        payload = {'type': 'fleet', 'mission': 'colonize', 'target_id': target['id'],
                   'ships': {'colonizer': 1}, 'request_id': 'settlement-once'}
        response = self.world.action(self.player, payload)
        fleet = self.world.data['fleets'][response['state']['fleets'][-1]['id']]
        p.update(owner_type='empty', owner_id='', buildings=dict.fromkeys(BUILDINGS, 0))
        self.world._player(self.player)['home_id'] = backup['id']
        self.world._complete_fleet(fleet)
        self.assertEqual(target['buildings']['metal_mine'], 3)
        self.world.state(self.player)
        settled = copy.deepcopy(self.world.data)
        self.world.action(self.player, payload)
        self.assertEqual(self.world.data, settled)

    def test_citadel_boosts_only_local_defenders_opening_volley(self):
        self.choose('zetans')
        enemy = self.world.register('Defender', 'password-123')['state']['player']['id']
        self.world.action(enemy, {'type': 'choose_race', 'race_id': 'automatons'})
        p = self.world._owned(enemy)
        p['buildings']['magnetic_citadel'] = 5
        p['ships'] = blank_ships()
        p['ships']['frigate'] = 1
        self.world.data['players'][enemy]['protected_until'] = 0
        self.home()['ships']['cruiser'] = 1
        fleet = self.launch('attack', p, {'cruiser': 1})
        observed = []
        damage = self.world._damage
        def capture(ships, amount, wounds, specs, reduction, type_reductions=None):
            if ships is fleet['ships']:
                observed.append(amount)
            return damage(ships, amount, wounds, specs, reduction, type_reductions)
        self.world._damage = capture
        self.world._complete_fleet(fleet)
        self.assertAlmostEqual(observed[0], 31 * 1.6)
        self.assertTrue(all(amount <= 31 for amount in observed[1:]))
        self.assertIn('Cytadela Magnetyczna', self.world.state(self.player)['reports'][0]['text'])
        # A citadel on another owned colony does not alter this planet's defense.
        p['buildings']['magnetic_citadel'] = 0
        self.assertEqual(self.world._building_effects(p)['defense_first_volley'], 0)

    def test_recycler_reserves_hold_after_swarm_crystals_and_pays_only_at_return(self):
        p = self.choose('automatons')
        p['buildings']['wreck_recycler'] = 5
        target = self.target(True)
        target['ships'] = dict.fromkeys(swarm.SHIPS, 0)
        target['ships']['frigate'] = 1
        target['swarm_crystals'] = 3
        target['resources'] = dict.fromkeys(RESOURCES, 100_000.0)
        fleet = self.launch('attack', target, {'frigate': 3})
        before_metal = p['resources']['metal']
        self.world._complete_fleet(fleet)
        expected = math.floor(swarm.SHIPS['frigate'][2][0] * .25)
        self.assertEqual(p['resources']['metal'], before_metal)
        self.assertEqual(fleet['swarm_crystals'], 3)
        self.assertGreaterEqual(fleet['cargo']['metal'], expected)
        self.assertLessEqual(sum(fleet['cargo'].values()) + fleet['swarm_crystals'], 240)
        self.assertIn(f'odzyskał {expected}', self.world.state(self.player)['reports'][0]['text'])
        cargo = fleet['cargo']['metal']
        self.world._complete_fleet(fleet)
        self.assertEqual(p['resources']['metal'], before_metal + cargo)
        self.assertEqual(self.world.data['players'][self.player]['swarm_crystals'], 3)
        self.world._complete_fleet(fleet)
        self.assertEqual(p['resources']['metal'], before_metal + cargo)

    def test_recycler_snapshot_not_later_upgrade_and_legacy_fleet_no_bonus(self):
        p = self.choose('automatons')
        p['buildings']['wreck_recycler'] = 1
        target = self.target(True)
        target['ships'] = dict.fromkeys(swarm.SHIPS, 0)
        target['ships']['scout'] = 1
        target['swarm_crystals'] = 0
        target['resources'] = dict.fromkeys(RESOURCES, 0)
        fleet = self.launch('attack', target, {'frigate': 3})
        p['buildings']['wreck_recycler'] = 5
        self.world._complete_fleet(fleet)
        self.assertEqual(fleet['cargo']['metal'], math.floor(swarm.SHIPS['scout'][2][0] * .05))
        self.world._complete_fleet(fleet)
        second = self.target(True)
        second['ships'] = dict.fromkeys(swarm.SHIPS, 0)
        second['ships']['scout'] = 1
        second['swarm_crystals'] = 0
        second['resources'] = dict.fromkeys(RESOURCES, 0)
        legacy = self.launch('attack', second, {'frigate': 3})
        legacy.pop('building_effects')
        self.world._complete_fleet(legacy)
        self.assertEqual(legacy['cargo']['metal'], 0)

    def test_renewal_adds_regeneration_percentage_without_a_second_heal_or_resurrection(self):
        p = self.choose('symbionts')
        p['buildings']['renewal_grove'] = 5
        specs = RACES['symbionts']['ships']
        ships = blank_ships()
        ships['scout'] = 2
        wounds = {}
        self.world._damage(ships, 25, wounds, specs)
        self.assertEqual(ships['scout'], 1)
        fraction = self.world._regeneration_fraction(self.world._rules(self.player), defense_effects=self.world._building_effects(p))
        self.assertAlmostEqual(fraction, .45)
        entry = self.entry('scout', 'ships')
        self.assertAlmostEqual(entry['regeneration_fraction'], .35)
        self.assertAlmostEqual(entry['defense_regeneration_fraction'], .45)
        self.assertAlmostEqual(entry['defense_regeneration_bonus'], .10)
        other = self.extra_colony()
        other_entry = self.entry('scout', 'ships', other)
        self.assertAlmostEqual(other_entry['regeneration_fraction'], .35)
        self.assertAlmostEqual(other_entry['defense_regeneration_fraction'], .35)
        self.assertEqual(other_entry['defense_regeneration_bonus'], 0)
        self.world._regenerate(ships, wounds, fraction)
        self.assertAlmostEqual(wounds['scout'], 6 * .55)
        self.assertEqual(ships['scout'], 1)
        ships['scout'] = 0
        wounds['scout'] = 5
        self.world._regenerate(ships, wounds, fraction)
        self.assertEqual(wounds['scout'], 0)
        self.assertEqual(ships['scout'], 0)
        self.assertEqual(self.world._regeneration_fraction({'regeneration_fraction': .98}, defense_effects={'renewal_fraction': .10}), 1)
        self.assertEqual(self.world._regeneration_fraction({'regeneration_fraction': -.10}), 0)

    def test_renewal_real_battle_uses_current_defending_grove_never_outgoing_grove(self):
        p = self.choose('symbionts')
        p['buildings']['renewal_grove'] = 1
        enemy = self.world.register('Healing Enemy', 'password-123')['state']['player']['id']
        self.world.action(enemy, {'type': 'choose_race', 'race_id': 'symbionts'})
        target = self.world._owned(enemy)
        self.world.data['players'][enemy]['protected_until'] = 0
        target['ships'] = blank_ships()
        target['ships']['frigate'] = 1
        target['buildings']['renewal_grove'] = 3
        fleet = self.launch('attack', target, {'frigate': 1})
        self.assertNotIn('renewal_fraction', fleet['building_effects'])
        p['buildings']['renewal_grove'] = 5
        target['buildings']['renewal_grove'] = 4
        observed = []
        regenerate = self.world._regenerate
        def capture(ships, wounds, fraction, type_fractions=None):
            observed.append(('attacker' if ships is fleet['ships'] else 'defender', fraction, sum(wounds.values())))
            return regenerate(ships, wounds, fraction, type_fractions)
        self.world._regenerate = capture
        self.world._complete_fleet(fleet)
        self.assertTrue(observed)
        for side, fraction, _ in observed:
            self.assertAlmostEqual(fraction, .35 if side == 'attacker' else .43)
        self.assertAlmostEqual(observed[0][2], RACES['symbionts']['ships']['frigate'][4])
        report = self.world.state(self.player)['reports'][0]['text']
        self.assertIn('regeneracja 35%', report)
        self.assertIn('regeneracja 43%', report)
        self.assertIn('Gaj Odnowy', report)
        self.assertIn('regeneracja obrony planety +8 pkt proc.', report)
        # There is exactly one ordinary regeneration pass per side per round.
        self.assertEqual(len(observed), 12)

    def test_renewal_legacy_snapshot_after_restart_and_other_colony_do_not_heal_attackers(self):
        p = self.choose('symbionts')
        p['buildings']['renewal_grove'] = 5
        enemy = self.world.register('Legacy Enemy', 'password-123')['state']['player']['id']
        self.world.action(enemy, {'type': 'choose_race', 'race_id': 'symbionts'})
        target = self.world._owned(enemy)
        target['ships'] = blank_ships()
        target['ships']['frigate'] = 1
        self.world.data['players'][enemy]['protected_until'] = 0
        other = self.target()
        other.update(owner_id=enemy, owner_type='player', buildings=dict.fromkeys(BUILDINGS, 1))
        self.world._ensure_race_buildings(other)
        other['buildings']['renewal_grove'] = 5
        fleet = self.launch('attack', target, {'frigate': 1})
        fleet['building_effects']['renewal_fraction'] = .10  # Genuine pre-0.3.2 snapshot.
        fleet_id = fleet['id']
        self.world._save()
        self.world.close()
        self.world = World(self.path, speed=10, now=START)
        fleet = self.world.data['fleets'][fleet_id]
        self.assertEqual(fleet['building_effects']['renewal_fraction'], .10)
        observed = []
        regenerate = self.world._regenerate
        def capture(ships, wounds, fraction, type_fractions=None):
            observed.append(fraction)
            return regenerate(ships, wounds, fraction, type_fractions)
        self.world._regenerate = capture
        self.world._complete_fleet(fleet)
        self.assertEqual(len(observed), 12)
        self.assertTrue(all(abs(fraction - .35) < 1e-9 for fraction in observed))
        report = self.world.state(self.player)['reports'][0]['text']
        self.assertNotIn('Gaj Odnowy', report)

    def test_renewal_protects_stationed_ships_against_swarm_attack(self):
        p = self.choose('symbionts')
        p['buildings']['renewal_grove'] = 3
        p['ships'] = blank_ships()
        p['ships']['frigate'] = 1
        self.world.data['players'][self.player]['protected_until'] = 0
        origin = self.target(True)
        origin['resources']['fuel'] = 100_000
        # Full-galaxy, cooldown-expired fixture exercises the legal NPC attack.
        for target in self.world.data['planets'].values():
            if target['owner_type'] == 'empty':
                target.update(owner_type='player', owner_id=self.player)
        origin['swarm_next_attack_at'] = 0
        origin['ships'].update(swarm.defense_minimum(origin))
        origin['ships']['frigate'] += 1
        sent = dict.fromkeys(swarm.SHIPS, 0)
        sent['frigate'] = 1
        fleet = self.world._swarm_launch(origin, p, 'attack', sent)
        self.assertIsNotNone(fleet)
        observed = []
        regenerate = self.world._regenerate
        def capture(ships, wounds, fraction, type_fractions=None):
            observed.append(('attacker' if ships is fleet['ships'] else 'defender', fraction))
            return regenerate(ships, wounds, fraction, type_fractions)
        self.world._regenerate = capture
        self.world._complete_fleet(fleet)
        self.assertTrue(observed)
        for side, fraction in observed:
            self.assertAlmostEqual(fraction, .41 if side == 'defender' else swarm.RULES['regeneration_fraction'])
        self.assertEqual(len(observed) % 2, 0)
        self.assertIn('Gaj Odnowy — regeneracja obrony planety +6 pkt proc.', self.world.state(self.player)['reports'][0]['text'])


if __name__ == '__main__':
    unittest.main()
