"""Version 85 energy curves and production storage, without world mutation."""
from __future__ import annotations

import math

try:
    from . import ogame_economy
except ImportError:
    import ogame_economy

RESOURCES = ("metal", "crystal", "fuel")
# Colony income per hour at universe speed 1, independent of mines and bonuses.
PASSIVE_PRODUCTION = {"metal": 30.0, "crystal": 15.0, "fuel": 0.0}
VAULTS = {"zetans": "phase_vault", "symbionts": "living_vault",
          "automatons": "armored_vault"}
MINE_ENERGY = {"metal_mine": 10.0, "crystal_mine": 10.0, "refinery": 20.0}
LEGACY_NEUTRAL_USE = {"metal_mine": 20.0, "crystal_mine": 25.0, "refinery": 25.0}


def curve(level):
    level = max(0, int(level))
    return level * 1.1 ** level


def power_supply(level, rules, power_bonus=1.0):
    # The old rule's 100 is the neutral reference, preserving faction,
    # technology and skill multipliers already included by World._rules.
    return 20.0 * curve(level) * rules["energy_supply_per_level"] / 100.0 * power_bonus


def mine_use(key, level, rules, reduction=1.0):
    return (MINE_ENERGY[key] * curve(level)
            * rules["energy_use_per_level"][key] / LEGACY_NEUTRAL_USE[key] * reduction)


def storage_capacity(level, resource_limit):
    """OGame storage curve, safely bounded by the existing JSON resource cap."""
    level = max(0, int(level))
    exponent = 20.0 * level / 33.0
    if exponent >= math.log((resource_limit / 5000.0 + 1.0) / 2.5):
        return int(resource_limit)
    return min(int(resource_limit), math.floor(2.5 * math.exp(exponent)) * 5000)


def vault_capacity(level, key, base, resource_limit):
    """Preserve the base curve while always allowing the next vault upgrade.

    Faction vault costs grow by two, faster than the storage exponential.
    At very high levels this floor prevents a colony from becoming unable to
    mine enough for its next upgrade. It grants no resources or building levels.
    """
    capacity = storage_capacity(level, resource_limit)
    if key and base is not None:
        next_cost = ogame_economy.cost("buildings", key, base, int(level),
                                     resource_cap=resource_limit)
        capacity = max(capacity, min(int(resource_limit), max(next_cost.values())))
    return capacity


def storage(planet, race_id, resource_limit, *, vault_base=None):
    key = VAULTS.get(race_id, "")
    level = max(0, int(planet.get("buildings", {}).get(key, 0))) if key else 0
    capacity = vault_capacity(level, key, vault_base, resource_limit)
    return {"building_key": key, "level": level,
            "capacity": {resource: capacity for resource in RESOURCES},
            "full": {resource: planet.get("resources", {}).get(resource, 0) >= capacity
                     for resource in RESOURCES}}
