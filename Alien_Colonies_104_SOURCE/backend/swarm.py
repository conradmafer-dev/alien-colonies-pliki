"""Khar is a non-playable, budgeted insect swarm, not a fourth player faction.

Only infected worlds synthesize the rare crystals used by the skill wheel. The
ordinary economy's `crystal` resource remains separate from `swarm_crystals`.
"""
from __future__ import annotations

import math

try:
    from .i18n import t
    from . import defenses
except ImportError:  # Flat Railway deployment.
    from i18n import t
    import defenses


OWNER_ID = "khar"
FORTRESS_VERSION = 2  # Legacy schema only; never use this to trigger another reset.
RESET_ID = "khar-plague-0113-v1"  # Permanent database marker; keep in future releases.
MAX_COLONIES = 240
MAX_COLONIES_PER_GALAXY = 40
INITIAL_HIVES = 1  # Aurora only; later galaxies bootstrap on first player settlement.
BOOTSTRAP_CRYSTALS = 3
DAY_SECONDS = 24 * 3600
# Real-time safety gates. Resources, paid construction and flight are additional.
EXPANSION_TEMPO_ID = "slow-20261009"
EXPANSION_SECONDS = DAY_SECONDS  # At most one colonization launch per galaxy/day.
ORIGIN_EXPANSION_SECONDS = 2 * DAY_SECONDS
COLONY_MATURITY_SECONDS = DAY_SECONDS
ECONOMY_LEVEL_SECONDS = 36 * 3600
MAX_ECONOMY_LEVEL = 10
MAX_FACILITY_LEVEL = 6
ATTACK_SECONDS = DAY_SECONDS
RAID_INTERVAL_SECONDS = 2 * DAY_SECONDS
RAID_TARGET_INTERVAL_SECONDS = 4 * DAY_SECONDS
RAID_MIN_STOCK = 12_000
RAID_MIN_GAIN = 1_000
RAID_PARTY = {"frigate": 24, "cruiser": 2, "cargo": 4}
CRYSTAL_REGEN_SECONDS = 180 * 3600
MAX_BUILDING_LEVEL = 20
CRYSTAL_CAPS = {"outpost": 6, "hive": 6}
CRYSTAL_HOURLY = {"outpost": 1 / 180, "hive": 1 / 180}
RAID_CRYSTALS = {"outpost": 3, "hive": 3}
DESTRUCTION_CRYSTALS = 3  # One bonus per liberated outpost, shared by a coalition.
EXPANSION_ESCORT = {"frigate": 2}
RULES = {
    "production_multipliers": {"metal": .90, "crystal": .66, "fuel": .84},
    "energy_supply_per_level": 140,
    "energy_use_per_level": {"metal_mine": 18, "crystal_mine": 20, "refinery": 18},
    "first_volley_multiplier": 1.0, "regeneration_fraction": 0.10,
    "damage_reduction": 0.15,
}
BUILDINGS = {
    "metal_mine": ("Żerowisko żelaza", "Tysiące robotnic zeskrobują metal z powierzchni planety.", (90, 25, 0), 65),
    "crystal_mine": ("Komora krystalizacji", "Gromadzi zwykły kryształ; zakażona kolonia dodatkowo rodzi rzadkie Kryształy Roju.", (65, 45, 0), 70),
    "refinery": ("Trawieniec", "Rozkłada biomasę i skały na paliwo rojowych chmar.", (85, 35, 10), 70),
    "power_plant": ("Pulsujący odwłok", "Pulsująca tkanka dostarcza energię całemu gniazdu.", (70, 25, 10), 60),
    "shipyard": ("Wylęgarnia chmary", "Wykluwa obronne chmary i ciężkie królowe, zużywając zasoby ula.", (140, 75, 25), 90),
    "lab": ("Węzeł feromonowy", "Rozwija uzbrojenie chmary. Każdy poziom zwiększa jej siłę ataku o 15%.", (120, 65, 20), 100),
}
RESEARCH = {
    "propulsion": ("Prąd chmary", "Chitynowe żagle niosą chmarę przez próżnię.", (100, 80, 45), 120),
    "weapons": ("Żuwacz kwasowy", "Chmara rozrywa kadłuby żuwaczkami i kwasem.", (130, 65, 35), 120),
}
SHIPS = {
    "scout": ("Czułek", "Mały owadzi zwiadowca wyczuwający nowe żerowiska.", (25, 20, 5), 20, 1, 5, 5, .3, 2.5),
    "cargo": ("Nosiciel", "Pękaty organizm zbierający zasoby dla ula.", (75, 35, 15), 35, 2, 30, 700, 1, 1.5),
    "colonizer": ("Zarodnia", "Rozsiewa jajeczka i chitynowe gniazda na wolnej planecie.", (260, 120, 70), 80, 1, 45, 80, 2, 1.7),
    "frigate": ("Żuwacz", "Tani owad bojowy; pojedynczy jest słaby, cała chmara potrafi zalać obronę.", (60, 25, 10), 30, 8, 20, 20, .5, 1.8),
    "cruiser": ("Królowa szturmowa", "Ciężki organizm osłaniający żuwacze i niosący kwasowe komory.", (500, 250, 100), 150, 65, 200, 200, 4, 1.1),
}
# NPC-only rebalance. Player ship catalogs and production are untouched.
# The colony hull pays for the initial level-one infrastructure of a new nest.
for _key, _spec in list(SHIPS.items()):
    _cost_factor = 1.0 if _key == "colonizer" else 1.5
    SHIPS[_key] = (*_spec[:2], tuple(math.ceil(n * _cost_factor) for n in _spec[2]),
                   _spec[3], round(_spec[4] * .8, 3), round(_spec[5] * .8, 3), *_spec[6:])
del _key, _spec, _cost_factor

DESCRIPTION = "Rój rozprzestrzenia się przez małe, słabo bronione gniazda. Najpierw opłaca kolonizatory i zajmuje wolne planety. Jego wydobycie jest niższe, a flota droższa. Główny ul zaczyna z 3 Kryształami Roju. Kolejne gniazda powstają z opłaconych kolonizatorów, bez darmowych statków i Kryształów Roju. Poza pierwszą galaktyką Rój budzi się dopiero po założeniu tam pierwszej kolonii gracza. Zwiad ujawnia ostatni znany stan gniazda. Możesz zniszczyć przyczółki Roju: pokonaj całą ich flotę i obronę, zachowując przynajmniej jeden atakujący statek. Uwolnioną planetę można zasiedlić kolonizatorem. Główny ul każdej galaktyki przetrwa atak, zachowa budynki i odbuduje flotę z własnych zasobów; jego planety nie można skolonizować. Zniszczenie przyczółka daje do 3 dodatkowych Kryształów Roju, zależnie od miejsca w ładowniach. W ataku sojuszniczym jest to jedna wspólna premia. Łup i premię otrzymasz po powrocie ocalałej floty."


def kind(planet):
    return "hive" if planet.get("swarm_kind") == "hive" else "outpost"


def seed(planet, now, hive=False):
    """A tiny starting nest, never a free fortress or a free colonizer.

    Bootstrap: one nest per activated galaxy, level-one facilities, three rare
    crystals, ZERO ordinary wallet, fleet or static defenses. Subsequent seeds
    use an actually paid, consumed colony ship and start without rare crystals;
    their real escort lands separately in World._land.
    """
    planet.update(owner_type="alien", owner_id=OWNER_ID,
                  swarm_kind="hive" if hive else "outpost",
                  swarm_crystals=float(BOOTSTRAP_CRYSTALS if hive else 0), swarm_established_at=now,
                  swarm_next_attack_at=now + ATTACK_SECONDS,
                  swarm_next_colonization_at=now + COLONY_MATURITY_SECONDS,
                  swarm_suppressed_until=0, swarm_loot_sealed=False,
                  swarm_activity="preparing_expansion")
    planet["buildings"] = dict.fromkeys(BUILDINGS, 1)
    planet["resources"] = {"metal": 0.0, "crystal": 0.0, "fuel": 0.0}
    planet["ships"] = dict.fromkeys(SHIPS, 0)
    planet["queue"] = []
    planet["defenses"] = {"acid_spire": 0}



def weapon_level(planet):
    return max(0, min(MAX_BUILDING_LEVEL, int(planet.get("buildings", {}).get("lab", 0))))


def defense_targets(planet, now=None):
    """Modest desired garrisons, not a hard cap on future paid fleet production."""
    yards = max(1, min(MAX_FACILITY_LEVEL, int(planet.get("buildings", {}).get("shipyard", 1))))
    age = max(0, (float(now or planet.get("swarm_established_at", 0))
                  - float(planet.get("swarm_established_at", 0))) / DAY_SECONDS)
    return {"frigate": 8 + 4 * (yards - 1) + 2 * min(7, int(age)),
            "cruiser": 0 if yards < 2 else 1 + (yards - 2) // 2}


def defense_minimum(planet):
    # A launch leaves a few defenders, not hundreds of mandatory escorts.
    yards = max(1, min(MAX_FACILITY_LEVEL, int(planet.get("buildings", {}).get("shipyard", 1))))
    return {"frigate": 2 + (yards - 1) // 2, "cruiser": 0}


def ready(planet):
    return (planet.get("owner_id") == OWNER_ID
            and planet.get("buildings", {}).get("shipyard", 0) >= 1
            and all(planet.get("ships", {}).get(key, 0) >= amount
                    for key, amount in defense_minimum(planet).items()))


def public_planet(planet, now=None):
    stage = kind(planet)
    units = planet.get("ships", {})
    power = sum(SHIPS[key][4] * value for key, value in units.items() if key in SHIPS)
    power += sum(defenses.DEFENSES["swarm"][key][4] * value for key, value in planet.get("defenses", {}).items() if key in defenses.DEFENSES["swarm"])
    power *= 1 + .15 * weapon_level(planet)
    defended = ready(planet)
    threat = (t('Odbudowa obrony') if not defended else t('Ekstremalna') if power >= 20_000
              else t('Bardzo wysoka') if power >= 5_000 else t('Wysoka') if power >= 1_000
              else t('Umiarkowana') if power >= 200 else t('Niska'))
    cap = CRYSTAL_CAPS[stage]
    stock_value = max(0.0, min(float(cap), float(planet.get("swarm_crystals", 0))))
    stock = int(stock_value)
    regenerating = defended and stock_value < cap
    next_at = (float(now) + (1 - (stock_value - stock)) * CRYSTAL_REGEN_SECONDS
               if regenerating and now is not None else 0)
    hint = t('Kryształy Roju: {0}/{1}').format(stock, cap)
    if not defended:
        hint += t(' · odnowa wstrzymana do odbudowy obrony')
    elif stock < cap:
        hint += t(" · +1 co {0} godz.").format(CRYSTAL_REGEN_SECONDS // 3600)
    return {"race_id": "swarm", "race_name": t('Rój Khar'), "colony_art": "swarm/colony",
            "planet_art": "swarm/planet", "swarm_kind": stage,
            "swarm_kind_name": t('Gniazdo macierzyste') if stage == "hive" else t('Młode gniazdo'),
            "swarm_threat": threat, "swarm_threat_high": power >= 1_000, "swarm_crystals_hint": hint,
            "swarm_crystals_stock": stock, "swarm_crystals_capacity": cap,
            "swarm_crystals_ready": defended, "swarm_crystals_regenerating": regenerating,
            "swarm_crystals_loot_available": (stock > 0 and (units.get("frigate", 0) + units.get("cruiser", 0) + sum(planet.get("defenses", {}).values())) > 0
                                              and (not planet.get("swarm_loot_sealed", False) or defended)),
            "swarm_crystals_next_at": next_at,
            "swarm_crystals_regen_seconds": CRYSTAL_REGEN_SECONDS,
            "swarm_weapon_level": weapon_level(planet),
            "swarm_buildings": [{"key": key, "name": t(spec[0]), "level": planet["buildings"].get(key, 0),
                                 "art_key": "swarm/" + key} for key, spec in BUILDINGS.items()
                                if planet["buildings"].get(key, 0) > 0]}
