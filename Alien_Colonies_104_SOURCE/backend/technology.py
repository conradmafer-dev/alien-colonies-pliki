"""Shared, level-gated technology graph. Existing research IDs remain unchanged.

Coordinates describe a portrait layout with at most three nodes in a row. Only
real research prerequisites become edges; building requirements stay in details.
The server owns requirements, costs, effects and unlocks, never the client.
"""
from __future__ import annotations


def tech(name, description, cost, seconds, row, column, requires=(), effect="", per_level=0.0, maximum=12, art="lab"):
    return {"spec": (name, description, cost, seconds), "row": row, "column": column,
            "requirements": requires, "effect": effect, "per_level": per_level,
            "max_level": maximum, "art": art}


RESEARCH = {
    "energy_technology": tech("Energetyka", "Zwiększa moc elektrowni o 6% na poziom.", (360, 500, 150), 300, 0, 0,
                              (("lab", 1),), "energy", .06, art="power_plant"),
    "computing": tech("Informatyka", "Zwiększa szybkość badań o 5% na poziom.", (400, 600, 200), 360, 0, 1,
                       (("lab", 1),), "research_speed", .05),
    "fusion_power": tech("Synteza jądrowa", "Zwiększa moc elektrowni o 4% na poziom.", (850, 900, 400), 600, 1, 0,
                          (("research", "energy_technology", 3), ("lab", 3)), "energy", .04, art="refinery"),
    "robotics": tech("Robotyka", "Automatyzacja przyspiesza budowę budynków: mnożnik szybkości wynosi 1 + poziom Robotyki.", (1000, 750, 300), 660, 1, 1,
                      (("research", "computing", 3), ("lab", 3)), "robotics_speed", 1.0, art="shipyard"),
    "superconductors": tech("Nadprzewodniki", "Zmniejsza zużycie energii przez kopalnie o 2% na poziom.", (1400, 2100, 700), 960, 2, 0,
                             (("research", "fusion_power", 3), ("research", "computing", 4), ("lab", 4)), "mining_energy_reduction", .02, art="crystal_mine"),
    "nanotechnology": tech("Nanotechnologia", "Wydobycie wszystkich zwykłych surowców +3% na poziom. Na poziomach 3, 6, 9 i 12 ponownie skraca o połowę czas budowy budynków, statków i obrony. Nie przyspiesza badań.", (2300, 1900, 900), 1200, 2, 1,
                            (("research", "robotics", 5), ("lab", 5)), "production_all", .03, art="metal_mine"),
    "hyperspace": tech("Fizyka nadprzestrzeni", "Zwiększa szybkość zwykłych lotów o 4% na poziom.", (1600, 2500, 1300), 1200, 2, 2,
                        (("research", "propulsion", 5), ("research", "computing", 4), ("lab", 5)), "flight_speed", .04, art="scout"),
    "stellar_collectors": tech("Kolektory gwiezdne", "Zwiększa moc elektrowni o 4% na poziom i prowadzi do inżynierii gwiezdnej.", (3500, 4200, 1600), 1800, 3, 0,
                                (("research", "superconductors", 6), ("lab", 6)), "energy", .04, art="power_plant"),
    "orbital_engineering": tech("Inżynieria orbitalna", "Zwiększa szybkość budowy statków i obrony o 4% na poziom.", (5000, 3500, 1800), 2100, 3, 1,
                                  (("research", "nanotechnology", 4), ("research", "propulsion", 6), ("lab", 6)), "ship_build_speed", .04, art="shipyard"),
    "graviton_control": tech("Kontrola grawitacji", "Zmniejsza zmienną część kosztu paliwa o 2% na poziom. Stała opłata międzygalaktyczna pozostaje.", (4000, 6500, 2400), 2400, 3, 2,
                               (("research", "hyperspace", 5), ("research", "energy_technology", 6), ("lab", 7)), "fuel_efficiency", .02, art="scout"),
    "stellar_engineering": tech("Inżynieria gwiezdna", "Zwiększa ładowanie i moc Sfery Dysona o 4% na poziom.", (8500, 11000, 4000), 3600, 5, 0,
                                  (("research", "stellar_collectors", 8), ("research", "fusion_power", 8), ("lab", 8)), "dyson_output", .04, art="power_plant"),
    "megastructures": tech("Megastruktury", "Każdy poziom zwiększa szybkość budowy megastruktur o 5% i pojemność ich magazynu energii o 8%.", (13000, 10000, 5000), 4200, 5, 1,
                           (("research", "orbital_engineering", 6), ("research", "nanotechnology", 6), ("lab", 8)), "mega_speed", .05, art="shipyard"),
    "spacetime_stability": tech("Stabilizacja czasoprzestrzeni", "Zmniejsza koszt otwarcia, podtrzymania i transferu przez tunel o 3% na poziom.", (10000, 16000, 7000), 4800, 5, 2,
                                 (("research", "graviton_control", 6), ("research", "computing", 8), ("lab", 8)), "tunnel_efficiency", .03, art="lab"),
    "dyson_design": tech("Projekt Sfery Dysona", "Odblokowuje cztery etapy budowy Sfery Dysona wokół gwiazdy kolonii.", (120000, 250000, 80000), 172800, 7, 0,
                         (("research", "stellar_engineering", 8), ("research", "megastructures", 8), ("lab", 10)), maximum=1, art="power_plant"),
    "wormhole_theory": tech("Teoria tuneli", "Odblokowuje budowę Tunelu czasoprzestrzennego przy ukończonej Sferze Dysona.", (200000, 400000, 160000), 259200, 8, 2,
                            (("research", "megastructures", 10), ("research", "spacetime_stability", 8), ("research", "dyson_design", 1), ("lab", 12)), maximum=1, art="lab"),
}

RESEARCH.update({
    "capital_shipbuilding": tech("Konstrukcja okrętów liniowych", "Otwiera drogę do pancerników, drednotów i okrętów specjalnych. Szybkość budowy statków i obrony +3% na poziom.",
        (12000, 10000, 4000), 5400, 6, 0,
        (("research", "orbital_engineering", 4), ("research", "nanotechnology", 4), ("lab", 7)),
        "ship_build_speed", .03, art="shipyard"),
    "capital_weapons": tech("Uzbrojenie okrętów liniowych", "Atak pancerników, drednotów, okrętów specjalnych i tytanów +4% na poziom. Nie zmienia ataku małych jednostek.",
        (20000, 24000, 8500), 7200, 7, 1,
        (("research", "capital_shipbuilding", 3), ("research", "weapons", 6), ("research", "energy_technology", 6), ("lab", 8)),
        "capital_attack", .04, art="weapon"),
    "titan_core": tech("Rdzeń tytana", "Odblokowuje tytany i ośmiokrotnie zwiększa pojemność kondensatora Sfery Dysona, bez darmowej energii. Produkcja tytana wymaga ukończonej Sfery Dysona w kolonii budowy, stoczni 12 i zaawansowanego uzbrojenia.",
        (650000, 950000, 350000), 345600, 9, 1,
        (("research", "dyson_design", 1), ("research", "capital_weapons", 5), ("research", "graviton_control", 6), ("research", "megastructures", 8), ("lab", 10)),
        maximum=1, art="power_plant"),
})

EXISTING_LAYOUT = {"propulsion": (0, 2), "weapons": (1, 2),
                   "antigravity": (4, 0), "multiplication": (4, 0), "recycling": (4, 0),
                   "phase_hulls": (4, 1), "chitin_layers": (4, 1), "composite_armor": (4, 1),
                   "folding_cargo": (4, 2), "metabolic_drive": (4, 2), "modular_cargo": (4, 2),
                   "coherent_plasma": (6, 2), "corrosive_spores": (6, 2), "siege_algorithms": (6, 2),
                   "psionic_command": (8, 1), "brood_sovereignty": (8, 1), "siege_autonomy": (8, 1)}


def effects(levels):
    result = {}
    for key, meta in RESEARCH.items():
        level = levels.get(key, 0)
        level = max(0, min(meta["max_level"], level)) if type(level) is int else 0
        if meta["effect"]:
            effect = meta["effect"]
            result[effect] = round(result.get(effect, 0.0) + level * meta["per_level"], 6)
    result["energy_capacity"] = max(0, min(12, levels.get("megastructures", 0))) * .08
    return result


def layout(key):
    if key in RESEARCH:
        return {"row": RESEARCH[key]["row"], "column": RESEARCH[key]["column"]}
    row, column = EXISTING_LAYOUT.get(key, (8, 0))
    return {"row": row, "column": column}


def effect_summary(key, level):
    """Authoritative labeled preview, shared by clients instead of client-side formulas."""
    try:
        from .i18n import t
    except ImportError:
        from i18n import t
    meta = RESEARCH[key]
    level = max(0, min(meta["max_level"], int(level)))
    if not meta["effect"]:
        return t("Projekt odblokowany.") if level else t("Projekt jeszcze niedostępny.")
    if key == "robotics":
        return t("Szybkość budowy budynków ×{0}").format(level + 1)
    if key == "nanotechnology":
        return t("Wydobycie +{0}% · szybkość budowy budynków, statków i obrony ×{1}").format(3 * level, 2 ** (level // 3))
    labels = {"energy": "Moc elektrowni +{0}%", "research_speed": "Szybkość badań +{0}%",
              "build_speed": "Szybkość budowy +{0}%", "mining_energy_reduction": "Pobór energii kopalń −{0}%",
              "production_all": "Wydobycie +{0}%", "flight_speed": "Prędkość lotów +{0}%",
              "ship_build_speed": "Szybkość produkcji statków i obrony +{0}%",
              "fuel_efficiency": "Zmienny koszt paliwa −{0}%", "dyson_output": "Moc i ładowanie Sfery +{0}%",
              "tunnel_efficiency": "Zużycie energii tunelu −{0}%", "capital_attack": "Atak okrętów liniowych +{0}%"}
    value = round(level * meta["per_level"] * 100)
    if key == "megastructures":
        return t("Budowa megastruktur +{0}% · magazyn energii +{1}%").format(value, round(level * .08 * 100))
    return t(labels[meta["effect"]]).format(value)
