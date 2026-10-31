"""Player unit baselines for release 85.

Attack, actual hull points (OGame structural integrity / 10), and cargo use
the corresponding OGame hull as their economic baseline. Fuel coefficients use
the same hull baseline, while flight geography and speed are handled separately.
Alien Colonies keeps its racial traits and combat resolver.
No shield or rapid-fire mechanic is implied by these values. Khar NPC units
never pass through these player-only profiles.
"""
from __future__ import annotations

# attack, hull HP, cargo. The scout has one point of attack for the existing
# combat engine and five cargo units; it is not an OGame combat scout.
SHIP_BASES = {
    "scout": (1, 100, 5),
    "cargo": (5, 400, 5_000),
    "colonizer": (50, 3_000, 7_500),
    "frigate": (50, 400, 50),
    "cruiser": (400, 2_700, 800),
    "interceptor": (150, 1_000, 100),
    "freighter": (5, 1_200, 25_000),
    "siege": (1_000, 7_500, 500),
    "battleship": (1_000, 6_000, 1_500),
    "dreadnought": (2_000, 11_000, 2_000),
    "flagship": (2_800, 14_000, 10_000),
    "titan": (200_000, 900_000, 1_000_000),
}
RACE_FACTORS = {
    "zetans": (1.0, .90, 1.0),
    "automatons": (1.0, 1.10, 1.0),
    "symbionts": (.90, 1.05, 1.10),
}
BASE_FUEL = {
    "scout": 1, "cargo": 10, "colonizer": 1_000, "frigate": 20,
    "cruiser": 300, "interceptor": 75, "freighter": 50, "siege": 700,
    "battleship": 500, "dreadnought": 1_000, "flagship": 1_100, "titan": 1,
}
RACE_FUEL_FACTORS = {"zetans": .90, "symbionts": .90, "automatons": 1.10}
DEFENSE_BASES = {
    "phase_sentinel": (250, 800, 0),
    "iron_bastion": (1_100, 3_500, 0),
    "rooted_spore": (150, 800, 0),
}
WEAPONS_PER_LEVEL = .10
SWARM_WEAPONS_PER_LEVEL = .15


def ship_base(key, race_id):
    """Return faction-adjusted base values, before skills and research."""
    values = [round(value * factor, 6) for value, factor in
              zip(SHIP_BASES[key], RACE_FACTORS.get(race_id, (1.0, 1.0, 1.0)))]
    if key == "scout":
        values[0] = max(1.0, values[0])
    return tuple(values)


def ship_spec(key, race_id, original):
    """Keep names, identity, prices and existing flight speeds."""
    if key not in SHIP_BASES:
        return original
    values = list(original)
    values[4:7] = ship_base(key, race_id)
    values[7] = round(BASE_FUEL[key] * RACE_FUEL_FACTORS.get(race_id, 1.0), 6)
    return tuple(values)


def defense_spec(key, original):
    if key not in DEFENSE_BASES:
        return original
    values = list(original)
    values[4:7] = DEFENSE_BASES[key]
    return tuple(values)


def weapons_multiplier(level, *, is_swarm=False):
    return 1 + level * (SWARM_WEAPONS_PER_LEVEL if is_swarm else WEAPONS_PER_LEVEL)
