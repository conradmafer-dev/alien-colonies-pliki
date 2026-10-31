"""Render actual client screens with server-produced, localized discovery states."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
from server.main import World
from server.i18n import language_scope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('godot'); parser.add_argument('--screenshots'); args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='alien-traits-ui-') as directory:
        directory = Path(directory)
        with patch('server.planet_traits.secrets.token_hex', return_value='ui-traits-095'):
            world = World(directory/'world.sqlite3', now=1900000000)
        try:
            world.data['alien']['next_expansion_at'] = world.now + 100000
            world._choose_start_planet = lambda planets: world.data['planets']['s1p1']
            account = world.register('Konrad', 'ui-traits-password')
            owner = account['state']['player']['id']; home = world._owned(owner)
            world.action(owner, {'type': 'choose_race', 'race_id': 'zetans'})
            home['rare_trait'] = 'ancient_archives'
            home['buildings'].update(lab=3, power_plant=4)
            home['resources'] = {'metal': 20000, 'crystal': 16000, 'fuel': 9000}
            home['ships']['scout'] = 10
            system = next(s for s in world.data['systems'] if s['id'] != 's1' and s['galaxy_id'] == home['galaxy_id'] and len(s['planet_ids']) >= 2)
            target, neighbour = [world.data['planets'][pid] for pid in system['planet_ids'][:2]]
            target['rare_trait'] = 'crystal_geodes'
            neighbour['rare_trait'] = 'fuel_reservoirs'
            fixture = {'target_id': target['id'], 'neighbour_id': neighbour['id'], 'system_id': system['id'], 'home_id': home['id'], 'states': {}}
            def capture(case):
                fixture['states'][case] = {}
                for locale in ('pl', 'en', 'de', 'es', 'fr'):
                    with language_scope(locale): fixture['states'][case][locale] = world.state(owner)
            capture('fresh')
            world.action(owner, {'type': 'fleet', 'mission': 'scout', 'target_id': target['id'], 'ships': {'scout': 1}})
            fleet = next(f for f in world.data['fleets'].values() if f['status'] == 'outbound')
            world.advance(fleet['arrives_at'])
            capture('scouted')
            # Observation from an owned colony in the same system reveals the neighbour.
            # Choose an existing home radius sufficient for this fixture.
            home['buildings']['observatory'] = 12
            world.advance(world.now); capture('observed')
            home['buildings']['observatory'] = 0
            world.advance(world.now+120); capture('remembered')
            world.action(owner, {'type': 'fleet', 'mission': 'scout', 'target_id': neighbour['id'], 'ships': {'scout': 1}})
            fleet = next(f for f in world.data['fleets'].values() if f['status'] == 'outbound')
            neighbour['rare_trait'] = ''
            world.advance(fleet['arrives_at']); capture('ordinary')
            # A real historical record before 0.9.5 remains unknown.
            legacy = copy.deepcopy(next(r for r in world._player(owner)['reports'] if 'planet_snapshot' in r))
            legacy['planet_snapshot']['identity'].pop('rare_trait', None)
            world._player(owner)['reports'].insert(0, legacy); capture('legacy')
            for trait_id in ('metal_veins', 'crystal_geodes', 'fuel_reservoirs', 'geothermal_sources', 'ancient_archives'):
                home['rare_trait'] = trait_id; capture(trait_id)
            path = directory/'fixture.json'; path.write_text(json.dumps(fixture, ensure_ascii=False))
            cmd = [args.godot, '--path', str(root), '--audio-driver', 'Dummy']
            cmd += ['--display-driver', 'x11', '--rendering-method', 'gl_compatibility'] if args.screenshots else ['--headless']
            cmd += ['tests/test_traits_ui_095.tscn', '--', str(path)]
            if args.screenshots: cmd.append(args.screenshots)
            return subprocess.run(cmd, env=dict(os.environ, XDG_DATA_HOME=str(directory/'userdata')), timeout=240).returncode
        finally: world.close()

if __name__ == '__main__': raise SystemExit(main())
