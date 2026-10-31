"""Stationary defenses: separate from ships, cargo and all fleet operations.

Spec layout matches combat ship stats only for the damage resolver. Zero hold,
fuel and speed do NOT make them flyable: the fleet API whitelist is SHIPS only.
"""
from __future__ import annotations

DEFENSES = {
    "zetans": {
        "phase_sentinel": ("Strażnik fazowy", "Nieruchome działo plazmowe. Pierwsza salwa jest o 50% silniejsza.",
                           (500, 800, 200), 300, 100, 320, 0, 0, 0),
    },
    "automatons": {
        "iron_bastion": ("Żelazny bastion", "Ciężka bateria planetarna. Pancerz pochłania dodatkowe 25% obrażeń.",
                         (1000, 400, 200), 360, 65, 900, 0, 0, 0),
    },
    "symbionts": {
        "rooted_spore": ("Korzenna zarodnia", "Żywa bateria obronna. Leczy co najmniej 50% ran ocalałych jednostek po rundzie.",
                         (650, 650, 350), 330, 75, 550, 0, 0, 0),
    },
    "swarm": {
        "acid_spire": ("Kwasowa iglica", "Nieruchomy organ Roju. Każda kolejna salwa jest o 5% silniejsza, do +25%.",
                       (900, 600, 300), 300, 72, 336, 0, 0, 0),
    },
}
TRAITS = {
    "phase_sentinel": {"first_volley": 1.5},
    "iron_bastion": {"damage_reduction": .25},
    "rooted_spore": {"regeneration_fraction": .50},
    "acid_spire": {"ramp_per_round": .05, "ramp_cap": .25},
}
# Existing high-resolution illustrations are reused, not small UI thumbnails.
ART = {
    "phase_sentinel": "races/zetans/echo_observatory",
    "iron_bastion": "races/automatons/magnetic_citadel",
    "rooted_spore": "races/symbionts/renewal_grove",
    "acid_spire": "swarm/weapon",
}
KEYS = frozenset(key for entries in DEFENSES.values() for key in entries)


def specs_for(race_id):
    return DEFENSES.get(race_id, {})


def round_factors(round_number):
    result = {}
    for key, traits in TRAITS.items():
        first = traits.get("first_volley", 1.0) if round_number == 1 else 1.0
        ramp = min(traits.get("ramp_cap", 0.0), max(0, round_number - 1) * traits.get("ramp_per_round", 0.0))
        result[key] = first * (1.0 + ramp)
    return result


def swarm_target(planet):
    # Satellites invest in colony hulls, not fortress batteries.
    yards = max(0, int(planet.get("buildings", {}).get("shipyard", 0)))
    return min(3, yards // 3)
