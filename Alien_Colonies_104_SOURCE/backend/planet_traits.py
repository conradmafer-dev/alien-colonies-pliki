"""Immutable, biome-compatible rarities. Raw trait IDs never imply discovery."""
from __future__ import annotations
import hashlib
import secrets

try:
    from .i18n import t
except ImportError:
    from i18n import t

CHANCE_PER_THOUSAND = 150
TRAITS = {
    "metal_veins": {
        "name": "Głębokie żyły metalu",
        "description": "Bogate złoża zwiększają wydobycie metalu na tej planecie o 30%.",
        "biomes": ("volcanic", "obsidian", "rust", "desert", "crater"),
        "bonuses": {"metal": .30},
    },
    "crystal_geodes": {
        "name": "Kryształowe geody",
        "description": "Olbrzymie geody zwiększają wydobycie kryształu na tej planecie o 30%.",
        "biomes": ("obsidian", "crater", "amethyst", "twilight", "ice"),
        "bonuses": {"crystal": .30},
    },
    "fuel_reservoirs": {
        "name": "Złoża węglowodorów",
        "description": "Podziemne zbiorniki zwiększają wydobycie paliwa na tej planecie o 30%.",
        "biomes": ("ocean", "jungle", "coral", "storm", "ice"),
        "bonuses": {"fuel": .30},
    },
    "geothermal_sources": {
        "name": "Źródła geotermalne",
        "description": "Elektrownie na tej planecie wytwarzają o 25% więcej energii. Sfera Dysona pozostaje niezależnym źródłem.",
        "biomes": ("volcanic", "obsidian", "ocean", "jungle", "coral", "storm"),
        "bonuses": {"power": .25},
    },
    "ancient_archives": {
        "name": "Pradawne archiwa",
        "description": "Badania rozpoczęte na tej planecie postępują o 15% szybciej. Bonus łączy się z poziomem laboratorium.",
        "biomes": ("rust", "desert", "crater", "ocean", "jungle", "coral", "amethyst", "twilight", "ice"),
        "bonuses": {"research_speed": .15},
    },
}


def _stable(key):
    return int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), "big")


def generate(planet, seed):
    if _stable(seed + ":rare-trait-chance:" + planet["id"]) % 1000 >= CHANCE_PER_THOUSAND:
        return ""
    choices = [key for key, trait in TRAITS.items() if planet["environment"]["type"] in trait["biomes"]]
    return choices[_stable(seed + ":rare-trait-kind:" + planet["id"]) % len(choices)] if choices else ""


def ensure(data, now):
    if "planet_traits_seed" not in data:
        data["planet_traits_seed"] = secrets.token_hex(24)
    for planet in data["planets"].values():
        # An explicit empty string is a surveyed ordinary world, not a reroll.
        if "rare_trait" not in planet:
            planet["rare_trait"] = generate(planet, data["planet_traits_seed"])
    data.setdefault("planet_traits_from", now)
    data["planet_traits_schema"] = 1


def multiplier(planet, bonus):
    return 1.0 + TRAITS.get(planet.get("rare_trait", ""), {}).get("bonuses", {}).get(bonus, 0)


def public(planet):
    # Missing key means unknown (including reports made before this feature).
    if "rare_trait" not in planet:
        return {"status": "unknown"}
    key = planet["rare_trait"]
    if key not in TRAITS:
        return {"status": "none"}
    trait = TRAITS[key]
    return {"status": "rare", "id": key, "name": t(trait["name"]),
            "description": t(trait["description"]), "bonuses": dict(trait["bonuses"])}
