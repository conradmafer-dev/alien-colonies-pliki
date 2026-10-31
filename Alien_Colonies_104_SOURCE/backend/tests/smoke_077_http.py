"""Local-only HTTP check for brief description metadata; never contacts Railway."""
from pathlib import Path
import json
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'railway'))
import app


def run():
    world = app.World(':memory:', now=time.time())
    http = app.GameHTTPServer(('127.0.0.1', 0), world)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{http.server_address[1]}'

    def request(route, payload=None, token=None):
        headers = {'Accept-Language': 'en', 'X-PGR-Client-Version': str(app.CLIENT_VERSION_CODE)}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(base + route, None if payload is None else json.dumps(payload).encode(), headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            assert response.status == 200
            return json.load(response)

    result = {}
    try:
        result['health'] = request('/health')
        assert result['health'] == {'ok': True, 'version': '0.7.7'}
        result['races'] = {}
        for race in ('zetans', 'automatons', 'symbionts'):
            account = request('/api/register', {'name': 'Brief077 ' + race, 'password': 'Local-test-only-077!'})
            token = account['token']
            owner = account['state']['player']['id']
            request('/api/action', {'type': 'choose_race', 'race_id': race}, token)
            with world.lock:
                home = world._owned(owner)
                home['buildings'].update(shipyard=5, lab=5, metal_mine=3, crystal_mine=3, refinery=3, power_plant=12)
            state = request('/api/state', token=token)['state']
            catalog = {e['key']: e for e in state['catalog']['buildings']}
            sample = {}
            for key in ('metal_mine', 'crystal_mine', 'refinery'):
                e = catalog[key]
                assert isinstance(e['production_bonus_percent'], (int, float))
                rows = {m['key']: m for m in e['details']['metrics']}
                output = rows['mine_' + e['production_resource']]
                assert output['next'] > output['current']
                sample[key] = {'bonus_percent': e['production_bonus_percent'], 'current_per_hour': output['current'], 'next_per_hour': output['next'], 'energy_use': rows['energy_use']['current'], 'next_energy_use': rows['energy_use']['next']}
            for key in ('lab', 'shipyard'):
                row = next(m for m in catalog[key]['details']['metrics'] if m['key'] in ('shipyard_speed_bonus', 'lab_speed_bonus'))
                assert row['current'] == 40 and row['next'] == 50
                assert catalog[key]['details']['time_examples']
                assert catalog[key]['details']['milestones']
                sample[key] = {'speed_bonus_percent': row['current'], 'next_speed_bonus_percent': row['next'], 'full_details_still_available': True}
            result['races'][race] = sample
        result['no_live_server_used'] = True
        return result
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)
        world.close()


if __name__ == '__main__':
    result = run()
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
