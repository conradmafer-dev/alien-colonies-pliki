"""Local disposable server state for public-release UI; no hosted requests."""
from copy import deepcopy
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.world_fixture import LocalTestWorld as World


def make_fixture():
    world = World(':memory:', speed=1, now=1_900_000_000)
    try:
        result = {'races': {}}
        ids = []
        for race in ('zetans', 'automatons', 'symbionts'):
            registered = world.register('QA ' + race, 'offline-only-password')
            player = registered['state']['player']['id']
            world.action(player, {'type': 'choose_race', 'race_id': race, 'request_id': 'race-' + race})
            result['races'][race] = deepcopy(world.state(player))
            ids.append(player)
        defender, attacker = ids[:2]
        world.data['players'][defender]['protected_until'] = 0
        world.data['players'][attacker]['protected_until'] = 0
        target = world._owned(defender)
        world.action(attacker, {'type': 'fleet', 'mission': 'attack', 'target_id': target['id'],
                              'ships': {'frigate': 1}, 'request_id': 'ui-release-attack'})
        result['attack'] = deepcopy(world.state(defender))
        assert result['attack']['incoming_attacks']
        result['other'] = deepcopy(world.state(ids[2]))
        return result
    finally:
        world.close()


if __name__ == '__main__':
    path = Path(sys.argv[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(make_fixture(), ensure_ascii=False, indent=2), encoding='utf8')
    print('Offline release UI fixture:', path)
