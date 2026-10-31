"""Stable orbital environments and finite surface building fields."""
from __future__ import annotations
import hashlib
import copy

try:
    from .i18n import t
    from . import planet_traits
except ImportError:
    from i18n import t
    import planet_traits

# Existing artwork now has authoritative physical/gameplay meaning.
TYPES = {
    'volcanic': ('Ognista', (1.50, 1.00, .50)),
    'obsidian': ('Obsydianowa', (1.15, 1.45, .40)),
    'rust': ('Metaliczna', (1.65, .85, .50)),
    'desert': ('Pustynna', (1.30, 1.10, .60)),
    'crater': ('Skalista', (1.45, .95, .60)),
    'ocean': ('Oceaniczna', (.85, .90, 1.25)),
    'jungle': ('Organiczna', (.75, .90, 1.35)),
    'coral': ('Koralowa', (.80, 1.15, 1.05)),
    'amethyst': ('Krystaliczna', (.65, 1.70, .65)),
    'twilight': ('Zmierzchowa', (.90, 1.30, .80)),
    'storm': ('Burzowa', (.85, 1.10, 1.05)),
    'ice': ('Lodowa', (.75, .80, 1.45)),
}
ZONES = {1: ('volcanic', 'obsidian'), 2: ('rust', 'desert', 'crater'),
         3: ('ocean', 'jungle', 'coral'), 4: ('amethyst', 'twilight', 'storm'),
         5: ('ice', 'ice', 'storm')}
SIZES = (('Mała', 48, 64), ('Średnia', 66, 84), ('Duża', 86, 104), ('Olbrzymia', 106, 120))
RESOURCES = ('metal', 'crystal', 'fuel')
OBSERVATORY_SPEC = ('Obserwatorium', 'Ujawnia właścicieli, typy i rzadkie cechy planet w sąsiednich układach własnej galaktyki. Wyższe poziomy ujawniają pobliskie budynki.', (800, 1200, 300), 600)


def stable(key):
    return int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), 'big')


def system_count(sid):
    count = 1 + stable('planet-count:' + sid) % 5
    # Keep the established six seed-hive coordinates, including p2.
    if sid[1:].isdigit() and (int(sid[1:]) - 15) % 30 == 0:
        count = max(2, count)
    return count


def profile(pid, rank, count):
    sid = pid.split('p')[0]
    zones = sorted(sorted(range(1, 6), key=lambda n: stable(f'orbits:{sid}:{n}'))[:count])
    zone = zones[min(rank, len(zones) - 1)]
    choices = ZONES[zone]
    kind = choices[stable('biome:' + pid) % len(choices)]
    index = stable('size:' + pid) % len(SIZES)
    _, low, high = SIZES[index]
    fields = low + 2 * (stable('fields:' + pid) % ((high - low) // 2 + 1))
    return {'schema': 1, 'type': kind, 'size_class': index, 'fields': fields * 3,
            'fields_expansion85': 1,
            'diameter_km': 6000 + fields * 110,
            'orbit_au': round((.35, .75, 1.15, 2.2, 4.5)[zone-1] * (1 + (stable('orbit:' + pid) % 17 - 8) / 100), 3),
            'temperature_c': (350, 140, 20, -75, -160)[zone-1] + stable('heat:' + pid) % 21 - 10}


def multipliers(planet, traits_enabled=True):
    kind = planet.get('environment', {}).get('type')
    values = TYPES[kind][1] if kind in TYPES else (1.0, 1.0, 1.0)
    return {key: value * (planet_traits.multiplier(planet, key) if traits_enabled else 1)
            for key, value in zip(RESOURCES, values)}


def fields(planet):
    used = sum(max(0, n) for n in planet['buildings'].values())
    reserved = sum(max(0, q.get('level', 0) - planet['buildings'].get(q.get('key'), 0))
                   for q in planet.get('queue', []) if q.get('kind') == 'build')
    total = planet.get('environment', {}).get('fields', 120)
    return {'total': total, 'used': used, 'reserved': reserved, 'free': max(0, total-used-reserved)}


def expand_fields85(planet):
    """Triple old surface capacity once, preserving levels and paid reservations."""
    environment = planet.get('environment')
    if not isinstance(environment, dict) or environment.get('fields_expansion85') == 1:
        return False
    occupied = fields(planet)
    environment['fields'] = max(int(occupied['total']) * 3,
                                occupied['used'] + occupied['reserved'])
    environment['fields_expansion85'] = 1
    return True


def public_environment(planet):
    result = copy.deepcopy(planet.get('environment', {}))
    if not result:
        return result
    kind = result['type']
    result.update(type_name=t(TYPES[kind][0]), planet_art='worlds/planet_' + kind,
                  colony_art='worlds/colony_' + kind, trait=planet_traits.public(planet))
    if 'fields' in result:
        result.update(size_name=t(SIZES[result['size_class']][0]), multipliers=multipliers(planet))
    return result


class PlanetaryMixin:
    def _ensure_planetary(self, data=None):
        data = self.data if data is None else data
        migrating = data.get('planetary_schema', 0) < 1
        if migrating:
            protected = {f[k] for f in data['fleets'].values() for k in ('origin_id', 'target_id')}
            for player in data['players'].values():
                protected.add(player['home_id'])
                protected.update(player.get('scout_intel', {}))
                protected.update(player.get('planet_intel', {}))
                for snapshot in player.get('system_intel', {}).values():
                    protected.update(q['id'] for q in snapshot.get('planets', []))
            for system in data['systems']:
                target = system_count(system['id'])
                for pid in reversed(list(system['planet_ids'])):
                    if len(system['planet_ids']) <= target:
                        break
                    p = data['planets'][pid]
                    if (pid not in protected and p['owner_type'] == 'empty' and not p['queue']
                            and not any(p['resources'].values()) and not any(p['ships'].values())
                            and not any(p['buildings'].values()) and not any(p.get('defenses', {}).values())):
                        system['planet_ids'].remove(pid)
                        del data['planets'][pid]
                for slot in range(1, 6):
                    if len(system['planet_ids']) >= target:
                        break
                    pid = f"{system['id']}p{slot}"
                    if pid not in data['planets']:
                        data['planets'][pid] = self._planet(pid, f"{system['name']} {slot}", system['id'], slot)
                        data['planets'][pid]['galaxy_id'] = system['galaxy_id']
                        system['planet_ids'].append(pid)
                system['planet_ids'].sort(key=lambda pid: data['planets'][pid]['slot'])
        for system in data['systems']:
            for rank, pid in enumerate(system['planet_ids']):
                planet = data['planets'][pid]
                if 'environment' not in planet:
                    planet['environment'] = profile(pid, rank, len(system['planet_ids']))
                    if planet['owner_type'] != 'empty':
                        occupied = fields(planet)
                        # Existing levels and paid queue orders must remain valid.
                        minimum = occupied['used'] + occupied['reserved'] + (8 if data['players'] else 0)
                        planet['environment']['fields'] = max(planet['environment']['fields'], minimum)
                if planet['owner_id'] != 'khar':
                    planet['buildings'].setdefault('observatory', 0)
                    planet['buildings'].setdefault('expedition_base', 0)
                expand_fields85(planet)
        data.setdefault('planetary_from', self.now)
        data['planetary_schema'] = 1
