"""OGame-shaped player flight fuel, adapted to Alien Colonies' lane graph.

Reference: Gameforge Formula Thread v3, 'Deuterium Costs for Flights', and
https://forum.pl.ogame.gameforge.com/forum/thread/3135-wzory/
At full fleet speed the per-hull speed term simplifies to
(1 + sqrt(slowest_speed / hull_speed)) ** 2. Sum before rounding, then add
one unit once per fleet. This is the complete prepaid mission fuel charge,
not a per-leg charge. Actual Alien Colonies travel times remain unchanged.
"""
from __future__ import annotations

import math

MODEL = "ogame_lanes_v85"


def distance(*, galaxy_gap, same_system, slot_delta, lane_distance=0.0):
    """One existing map lane unit maps to one reference system step.

    Keep the ring graph and fractional intergalactic distances; never use
    database system numbers (allocated over time) as physical distances.
    """
    if galaxy_gap > 0:
        return 20_000 * galaxy_gap
    if same_system:
        return 1_000 + 5 * abs(slot_delta)
    return 2_700 + 95 * max(0.0, lane_distance)


def fuel_cost(specs, fleet, route_distance, fuel_factor=1.0):
    """Return an integer charge using authoritative, already modified specs.

    Racial, skill and technology discounts are already applied to spec[7].
    Only the launch planet's building discount is applied here. Common speed
    bonuses cancel in the ratio; universe speed never changes consumption.
    """
    active = [(specs[key], count) for key, count in fleet.items() if count > 0]
    if not active:
        raise ValueError("A flight requires at least one ship")
    slowest = min(spec[8] for spec, _ in active)
    if slowest <= 0 or route_distance < 0:
        raise ValueError("Invalid flight speed or distance")
    factor = max(0.0, min(1.0, float(fuel_factor)))
    burn = math.fsum(count * spec[7] * route_distance / 35_000
                     * (1 + math.sqrt(slowest / spec[8])) ** 2
                     for spec, count in active) * factor
    # ROUND half up, not Python's ties-to-even; +1 is per fleet, not per hull.
    return 1 + math.floor(burn + .5)
