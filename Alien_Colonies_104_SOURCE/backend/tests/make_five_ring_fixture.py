"""Public geography only: test fixtures never read the production database."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import World

world = World(':memory:', now=1_900_000_000.0)
try:
    navigation = world._galaxy_navigation()
    local = [s for s in world.data['systems'] if s['galaxy_id'] == 'g1']
    systems = [{'id': s['id'], 'name': s['name'], 'galaxy_id': 'g1',
                'visibility': 'unknown', 'planets': [], **navigation.public_fields(s['id'])}
               for s in local]
    origins = [next(s['id'] for s in local if s['ring_index'] == ring and s['ring_order'] == 0)
               for ring in (0, 3, 4)]
    routes = [{'origin': origin, 'target': target['id'], **navigation.route(origin, target['id'])}
              for origin in origins for target in local]
    output = Path(sys.argv[1])
    output.write_text(json.dumps({'systems': systems, 'routes': routes}), encoding='utf-8')
    print(f'Public fixture: {len(systems)} systems, {len(routes)} authoritative routes')
finally:
    world.close()
