"""Immutable combat telemetry. Recording never rolls, resolves or changes combat.

Salvos are simultaneous: both powers are calculated from the opening state.
Within each receiving side the resolver assigns damage by hull, then key.
Healing happens only after both damage passes; destroyed units stay destroyed.
Full records live with the existing capped reports, fetched only when opened.
"""
from __future__ import annotations

import copy

try:
    from .i18n import store_text, render_text, t
    from .races import art_key
except ImportError:
    from i18n import store_text, render_text, t
    from races import art_key


def snapshot(fleet, wounds, keys):
    return {key: {"count": int(fleet.get(key, 0)), "wounds": float(wounds.get(key, 0))}
            for key in keys}


def side(world, owner, fleet, specs, static_keys=()):
    race = "swarm" if owner == "khar" else world._race_id(owner)
    units = []
    for key in sorted((key for key, count in fleet.items() if count),
                      key=lambda key: (specs[key][5], key)):
        spec = specs[key]
        art = ("swarm/" + key if race == "swarm" else
               art_key(race, key) if race else key)
        units.append({"key": key, "name_i18n": store_text(spec[0]),
                      "art_key": art, "hull": spec[5], "attack": spec[4],
                      "stationary": key in static_keys})
    return {"name": world.data["players"].get(owner, {}).get("name", ""),
            "race": race, "units": units,
            "initial": snapshot(fleet, {}, [u["key"] for u in units])}


def start(world, attacker, defender, attacking, defending, specs_a, specs_d, static, target):
    return {"schema": 1, "at": world.now,
            "planet": {"name": target["name"],
                       "art_key": "worlds/planet_" + target.get("environment", {}).get("type", "crater")},
            "attacker": side(world, attacker, attacking, specs_a),
            "defender": side(world, defender, defending, specs_d, static),
            "rounds": []}


def public(record):
    result = copy.deepcopy(record)
    swarm_name = str(t("Rój Khar"))
    for team in ("attacker", "defender"):
        if result[team].get("race") == "swarm":
            result[team]["name"] = swarm_name
        for participant in result[team].get("participants", []):
            if participant.get("race") == "swarm":
                participant["owner_name"] = swarm_name
        for unit in result[team]["units"]:
            unit["name"] = render_text(unit.pop("name_i18n"))
            if "unit_name_i18n" in unit:
                unit["unit_name"] = render_text(unit.pop("unit_name_i18n"))
            if unit.get("race") == "swarm":
                unit["owner_name"] = swarm_name
    for participant in result.get("participant_results", []):
        if participant.get("race") == "swarm":
            participant["owner_name"] = swarm_name
    return result
