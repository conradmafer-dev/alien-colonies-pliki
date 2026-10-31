"""Stable, additive six-ring galaxies and authoritative local navigation.

All original system/planet identities and physical records remain intact. The
lanes are public geography, not intelligence about planets or their owners.
"""
from __future__ import annotations

import heapq
import math
from collections import deque

try:
    from . import planetary
except ImportError:
    import planetary

SCHEMA = 4
# Indices 0, 1 and 2 are persistent identities, not radial positions.
RING_SIZES = (30, 20, 10, 40, 5, 50)
WORLD_RADII = (1.0, .67, .34, 4 / 3, .17, 5 / 3)
# Fit the larger galaxy to the existing map protocol, including Android 89.
# Physical x/y coordinates and all original system IDs remain unchanged.
RING_RADII = tuple(radius / max(WORLD_RADII) for radius in WORLD_RADII)
RADIAL_ORDER = (5, 3, 0, 1, 2, 4)
EXPANSION_NAMES = {
    3: "Alpheratz Ankaa Shedar Caph Mirfak Algol Almach Hamal Sheratan BatenKaitos Menkar Diphda Rana Zaurak Elnath Aldebaran Hassaleh Alhena Wasat Mekbuda Gomeisa Naos Suhail Avior Miaplacidus Alsephina Asterion CorCaroli Vindemiatrix Zubenelgenubi Zubeneschamali Rasalhague Sabik Unukalhai Kornephoros Albireo Tarazed Sualocin Rotanev Altais".split(),
    4: ('Alcyone', 'Asterope', 'Celaeno', 'Pleione', 'Taygeta'),
    5: "Achernar Adhara Algedi Algenib Alkes Alnilam Alnitak Alphard Alrakis Alrescha Alshain Alya Ancha Arneb Ascella Aspidiske Azha Botein Chara Dabih Diadem Edasich Errai Furud Gacrux Giausar Gienah Heze Homam KausAustralis Kochab Kurhah Markab Matar Meissa Mirzam Muscida Nashira Nekkar Nunki Peacock Phact Pherkad Rasalas Rastaban Ruchbah Sadalsuud Sargas Sceptrum Zaniah".split(),
}
ORBIT_DISTANCE = .6
BRIDGE_DISTANCE = 1.0
BRIDGE_COUNT = 5
INNER_NAMES = (
    'Atria', 'Altair', 'Alnair', 'Antares', 'Bellatrix', 'Capella', 'Deneb',
    'Enif', 'Fomalhaut', 'Hadar', 'Izar', 'Lesath', 'Maia', 'Menkent',
    'Mirach', 'Mizar', 'Procyon', 'Rigel', 'Sirius', 'Spica',
    'Acrux', 'Alcor', 'Arcturus', 'Canopus', 'Castor', 'Electra', 'Merope',
    'Pollux', 'Regulus', 'Sadr',
)


def system_key(system_id):
    value = str(system_id)
    return (int(value[1:]), value) if value.startswith('s') and value[1:].isdigit() else (10**30, value)


def ensure_rings(data, catalog, planet_factory):
    """Add missing rings without replacing planets, fleets or existing systems.

    Complete the original three-ring allocation across ALL galaxies first.
    This preserves s181..s360 even when migrating directly from schema one.
    """
    systems, planets = data['systems'], data['planets']
    existing_ids = {system['id'] for system in systems}
    if len(existing_ids) != len(systems):
        raise ValueError('Duplicate system identity in galaxy snapshot')
    number = max((system_key(sid)[0] for sid in existing_ids if sid[1:].isdigit()), default=0) + 1
    # Allocate each historical expansion across all galaxies before the next.
    # A fresh world and a direct migration retain the same original s1..s630.
    for ring_indices in ((0, 1, 2), (3, 4), (5,)):
        for galaxy in catalog:
            local = sorted((system for system in systems if system['galaxy_id'] == galaxy['id']),
                           key=lambda system: system_key(system['id']))
            for system in local:
                system.setdefault('ring_index', 0)
            for ring_index in ring_indices:
                expected_count = RING_SIZES[ring_index]
                ring = sorted((system for system in local if system['ring_index'] == ring_index),
                              key=lambda system: (system.get('ring_order', system_key(system['id'])[0]),
                                                  system_key(system['id'])))
                if ring_index:
                    for order in range(len(ring), expected_count):
                        while f's{number}' in existing_ids:
                            number += 1
                        sid = f's{number}'
                        number += 1
                        existing_ids.add(sid)
                        if ring_index < 3:
                            name_index = order + (RING_SIZES[1] if ring_index == 2 else 0)
                            suffix = INNER_NAMES[name_index]
                        else:
                            suffix = EXPANSION_NAMES[ring_index][order]
                        name = f"{galaxy['name']} {suffix}"
                        planet_ids = []
                        for slot in range(1, planetary.system_count(sid) + 1):
                            pid = f'{sid}p{slot}'
                            if pid in planets:
                                raise ValueError('Planet identity collision during galaxy expansion')
                            planet = planet_factory(pid, f'{name} {slot}', sid, slot)
                            planet['galaxy_id'] = galaxy['id']
                            planets[pid] = planet
                            planet_ids.append(pid)
                        angle = -math.pi / 2 + math.tau * order / expected_count
                        system = {'id': sid, 'name': name, 'galaxy_id': galaxy['id'],
                                  'x': 2.5 + 2.5 * WORLD_RADII[ring_index] * math.cos(angle),
                                  'y': 2.0 + 2.0 * WORLD_RADII[ring_index] * math.sin(angle),
                                  'planet_ids': planet_ids, 'ring_index': ring_index,
                                  'ring_order': order}
                        systems.append(system)
                        local.append(system)
                        ring.append(system)
                for order, system in enumerate(ring):
                    system.update(ring_order=order, ring_size=len(ring), ring_radius=RING_RADII[ring_index])
    data['galaxy_schema_version'] = SCHEMA


class Navigation:
    """Cached weighted routes and hop ranges over immutable system geography."""
    def __init__(self, systems):
        self.systems = {system['id']: system for system in systems}
        self.edges = {sid: {} for sid in self.systems}
        self._routes = {}
        self._hops = {}
        groups = {}
        for system in systems:
            groups.setdefault(system['galaxy_id'], {}).setdefault(system.get('ring_index', 0), []).append(system)
        for rings in groups.values():
            for index, ring in rings.items():
                ring.sort(key=lambda system: (system.get('ring_order', system_key(system['id'])[0]),
                                               system_key(system['id'])))
                if len(ring) > 1:
                    for order, system in enumerate(ring):
                        self._connect(system['id'], ring[(order + 1) % len(ring)]['id'], 'orbit', ORBIT_DISTANCE)
            radial_order = [index for index in RADIAL_ORDER if index in rings]
            for outer_index, inner_index in zip(radial_order, radial_order[1:]):
                outer, inner = rings[outer_index], rings[inner_index]
                if not outer or not inner:
                    continue
                for spoke in range(BRIDGE_COUNT):
                    self._connect(outer[spoke * len(outer) // BRIDGE_COUNT]['id'],
                                  inner[spoke * len(inner) // BRIDGE_COUNT]['id'], 'bridge', BRIDGE_DISTANCE)

    def _connect(self, first, second, kind, distance):
        if first != second:
            self.edges[first][second] = (distance, kind)
            self.edges[second][first] = (distance, kind)

    def public_fields(self, system_id):
        system = self.systems[system_id]
        result = {key: system[key] for key in ('ring_index', 'ring_order', 'ring_size', 'ring_radius') if key in system}
        result['connections'] = [{'system_id': target, 'kind': kind, 'distance': distance}
                                 for target, (distance, kind) in sorted(self.edges[system_id].items(),
                                                                      key=lambda item: system_key(item[0]))]
        return result

    def _shortest_from(self, origin):
        if origin in self._routes:
            return self._routes[origin]
        distances, previous = {origin: 0.0}, {}
        heap = [(0.0, system_key(origin), origin)]
        while heap:
            distance, _, source = heapq.heappop(heap)
            if distance > distances[source]:
                continue
            for target, (weight, _) in sorted(self.edges[source].items(), key=lambda item: system_key(item[0])):
                # Exact tenths prevent platform-dependent float tie breaking.
                candidate = round(distance + weight, 8)
                if candidate < distances.get(target, math.inf):
                    distances[target], previous[target] = candidate, source
                    heapq.heappush(heap, (candidate, system_key(target), target))
        self._routes[origin] = (distances, previous)
        return distances, previous

    def route(self, origin, target):
        distances, previous = self._shortest_from(origin)
        if target not in distances:
            return {'system_ids': [], 'segments': [], 'distance': None}
        path = [target]
        while path[-1] != origin:
            path.append(previous[path[-1]])
        path.reverse()
        segments = [{'from_system_id': first, 'to_system_id': second,
                     'distance': self.edges[first][second][0], 'kind': self.edges[first][second][1]}
                    for first, second in zip(path, path[1:])]
        return {'system_ids': path, 'segments': segments, 'distance': distances[target]}

    def hop_distances(self, origin):
        if origin not in self._hops:
            distances, queue = {origin: 0}, deque([origin])
            while queue:
                source = queue.popleft()
                for target in sorted(self.edges[source], key=system_key):
                    if target not in distances:
                        distances[target] = distances[source] + 1
                        queue.append(target)
            self._hops[origin] = distances
        return self._hops[origin]
