"""Shared authoritative production timers (player colonies and Khar hatcheries).

Facility level 1 is the existing starting speed. Each further completed level
adds 10 percentage points of speed, not an exponential discount. The factor is
local and is frozen when an order starts; no running timer is recalculated.
"""
from __future__ import annotations

import math

FACILITY_SPEED_PER_EXTRA_LEVEL = 0.10
# Khar buildings can reach 20; player catalog limits remain unchanged at 12.
FACILITY_LEVEL_LIMIT = 20
FACILITY_FOR_GROUP = {"ships": "shipyard", "defenses": "shipyard", "research": "lab"}


def project_lane(kind):
    """Buildings and the shipyard are local; research is empire-wide.

    Ships and defenses share shipyard capacity. Existing stored jobs need no
    migration: their kind already identifies the lane and timers stay intact.
    """
    return {"build": "build", "buildings": "build", "ship": "ship", "ships": "ship",
            "defense": "ship", "defenses": "ship", "research": "research"}[kind]


def facility_profile(buildings, group):
    """Return a read-only bonus breakdown; level zero grants no free bonus."""
    key = FACILITY_FOR_GROUP.get(group, "")
    level = buildings.get(key, 0) if key else 0
    level = max(0, min(FACILITY_LEVEL_LIMIT, level)) if type(level) is int else 0
    bonus = max(0, level - 1) * FACILITY_SPEED_PER_EXTRA_LEVEL
    multiplier = 1.0 + bonus
    return {"building_key": key, "level": level, "speed_multiplier": multiplier,
            "speed_bonus_percent": round(bonus * 100, 6),
            "time_reduction_percent": round((1.0 - 1.0 / multiplier) * 100, 6)}


def project_seconds(base_seconds, level, group, buildings, server_speed,
                    skill_bonus=0.0, time_reduction=0.0, amount=1, *, local_speed=1.0):
    """One project's timer before player batch bonuses, rounded only at the end.

    Khar passes its batch amount directly, preserving its existing batching rule.
    Players still use the catalog's rounded per-unit seconds and apply their
    existing quantity/batch discount exactly as in earlier releases.
    """
    if (not math.isfinite(server_speed) or server_speed <= 0
            or not math.isfinite(base_seconds) or base_seconds < 0
            or not math.isfinite(skill_bonus) or skill_bonus < 0
            or not math.isfinite(time_reduction) or not 0 <= time_reduction < 1
            or not math.isfinite(local_speed) or local_speed < 1
            or type(level) is not int or level < 0
            or type(amount) is not int or amount < 1):
        raise ValueError("Invalid internal production timing parameters")
    scale = 1 if group in ("ships", "defenses") else 1.3 ** level
    multiplier = facility_profile(buildings, group)["speed_multiplier"]
    return max(1, math.ceil(base_seconds * scale * amount / server_speed
                           / (1.0 + skill_bonus) * (1.0 - time_reduction) / multiplier / local_speed))
