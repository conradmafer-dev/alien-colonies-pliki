"""OGame 1x player-economy rules for Alien Colonies.

Costs and one-order times are frozen when an order begins. Swarm AI retains
its dedicated costs/timing in swarm.py / production_timing.py.
Since the version-85 epoch, player colonies also earn a passive 30 metal and
15 crystal per hour at universe speed 1 (defined in economy85.py).
"""
from __future__ import annotations

import math

RESOURCE_LIMIT = 9_000_000_000_000_000  # < 2**53, safe across JSON/Godot
RESOURCES = ("metal", "crystal", "fuel")

# Authentic OGame starting prices for directly equivalent facilities.
BUILDING_BASES = {
    "metal_mine": (60, 15, 0),
    "crystal_mine": (48, 24, 0),
    "refinery": (225, 75, 0),
    "power_plant": (75, 30, 0),
    "shipyard": (400, 200, 100),
    "lab": (200, 400, 200),
}
BUILDING_FACTORS = {"metal_mine": 1.5, "crystal_mine": 1.6,
                    "refinery": 1.5, "power_plant": 1.5}

# Closest OGame hull analogues. Faction art is retained; release-85 combat
# profiles live separately in fleet_balance85.py.
SHIP_BASES = {
    "scout": (0, 1_000, 0),
    "cargo": (2_000, 2_000, 0),
    "colonizer": (10_000, 20_000, 10_000),
    "frigate": (3_000, 1_000, 0),
    "cruiser": (20_000, 7_000, 2_000),
    "interceptor": (6_000, 4_000, 0),
    "freighter": (6_000, 6_000, 0),
    "siege": (50_000, 25_000, 15_000),
    "battleship": (45_000, 15_000, 0),
    "dreadnought": (60_000, 50_000, 15_000),
    "flagship": (85_000, 55_000, 20_000),
    "titan": (5_000_000, 4_000_000, 1_000_000),
}
DEFENSE_BASES = {"phase_sentinel": (6_000, 2_000, 0),
                 "iron_bastion": (20_000, 15_000, 2_000),
                 "rooted_spore": (2_000, 6_000, 0)}


def _checked_base(base):
    if len(base) != 3 or any(not isinstance(x, (int, float)) or x < 0 for x in base):
        raise ValueError("Invalid three-resource base cost")
    return base


def cost(group, key, original, level, *, resource_cap=RESOURCE_LIMIT):
    """Return authoritative total cost for NEXT level or ONE ship/defense.

    level is the currently completed level, so upgrading 1 -> 2 uses factor**1.
    OGame rounds each resource cost downward before payment.
    """
    if type(level) is not int or level < 0 or resource_cap < 1:
        raise ValueError("Invalid level or resource limit")
    if group == "buildings":
        base = BUILDING_BASES.get(key, original)
        factor = BUILDING_FACTORS.get(key, 2.0)
        quantities = [min(resource_cap + 1, int(math.floor(v * factor ** level)))
                      for v in _checked_base(base)]
    elif group == "research":
        quantities = [min(resource_cap + 1, int(math.floor(v * 2 ** level)))
                      for v in _checked_base(original)]
    elif group == "ships":
        quantities = SHIP_BASES.get(key, original)
    elif group == "defenses":
        quantities = DEFENSE_BASES.get(key, original)
    else:
        raise ValueError("Invalid project group")
    return dict(zip(RESOURCES, [int(v) for v in quantities]))


def facility_profile(buildings, group):
    """OGame facility multiplier for UI and construction timers."""
    key = "lab" if group == "research" else "shipyard" if group in ("ships", "defenses") else ""
    level = max(0, int(buildings.get(key, 0))) if key else 0
    multiplier = (1 + level) if key else 1
    return {"building_key": key, "level": level, "speed_multiplier": float(multiplier),
            "speed_bonus_percent": float(100 * (multiplier - 1)),
            "time_reduction_percent": round(100 * (1 - 1 / multiplier), 6)}


def project_timing(group, project_cost, buildings, server_speed=1.0,
                   skill_bonus=0.0, time_reduction=0.0, *, local_speed=1.0,
                   research_levels=None, target_level=None, rules_version=85):
    """Authoritative version-85 one-order time and its visible multipliers.

    Existing Robotics research serves as the construction automation level.
    Every third Nanotechnology level unlocks another production-time halving;
    its resource-production bonus remains independent. Research itself never
    receives either construction multiplier. Already queued work stores its
    completion timestamp and does not call this function again.
    """
    if group not in ("buildings", "research", "ships", "defenses"):
        raise ValueError("Invalid project group")
    if rules_version not in (84, 85):
        raise ValueError("Invalid timing rules version")
    for value in (server_speed, skill_bonus, time_reduction, local_speed):
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Non-finite timing parameter")
    if server_speed <= 0 or local_speed <= 0 or skill_bonus < 0 or not 0 <= time_reduction < 1:
        raise ValueError("Invalid timing multiplier")
    if target_level is not None and (type(target_level) is not int or target_level < 1):
        raise ValueError("Invalid target level")
    levels = research_levels or {}

    def completed_level(key):
        value = levels.get(key, 0)
        if type(value) is not int or value < 0:
            raise ValueError("Invalid timing research level")
        return min(12, value)

    robotics_level = completed_level("robotics")
    nanotechnology_level = completed_level("nanotechnology")
    robotics_multiplier = 1 + robotics_level if rules_version >= 85 and group == "buildings" else 1
    nanotechnology_stage = nanotechnology_level // 3 if rules_version >= 85 and group != "research" else 0
    nanotechnology_multiplier = 2 ** nanotechnology_stage
    early_bonus = max(4 - target_level / 2, 1) if rules_version >= 85 and group == "buildings" and target_level is not None else 1
    denom = (1000 if group == "research" else 2500)
    facility = facility_profile(buildings, group)["speed_multiplier"]
    metal_crystal = project_cost["metal"] + project_cost["crystal"]
    multiplier = (facility * robotics_multiplier * nanotechnology_multiplier
                  * early_bonus * server_speed * (1 + skill_bonus) * local_speed
                  / (1 - time_reduction))
    seconds = max(1, math.ceil(3600 * metal_crystal / denom / multiplier))
    if rules_version == 84:
        # Preserve the exact v84 operation order, including float/ceil edges,
        # when offline replay starts an unpaid order before the v85 epoch.
        seconds = max(1, math.ceil(3600 * metal_crystal / denom / facility / server_speed
                                  / (1 + skill_bonus) * (1 - time_reduction) / local_speed))
    return {"schema": 1, "rules_version": rules_version, "seconds": seconds,
            "robotics_level": robotics_level,
            "robotics_multiplier": robotics_multiplier,
            "nanotechnology_level": nanotechnology_level,
            "nanotechnology_stage": nanotechnology_stage,
            "nanotechnology_multiplier": nanotechnology_multiplier,
            "early_bonus": float(early_bonus), "facility_multiplier": facility,
            "server_speed": float(server_speed), "local_speed": float(local_speed),
            "skill_multiplier": 1.0 + skill_bonus, "time_reduction": float(time_reduction),
            "speed_multiplier": round(multiplier, 6)}


def project_seconds(group, project_cost, buildings, server_speed=1.0,
                    skill_bonus=0.0, time_reduction=0.0, *, local_speed=1.0,
                    research_levels=None, target_level=None, rules_version=85):
    """Compatibility wrapper for callers that need only the duration."""
    return project_timing(group, project_cost, buildings, server_speed,
                          skill_bonus, time_reduction, local_speed=local_speed,
                          research_levels=research_levels,
                          target_level=target_level, rules_version=rules_version)["seconds"]
