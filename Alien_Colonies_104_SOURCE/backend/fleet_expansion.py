"""0.11.0 capital fleet catalogue, shared by combat, production and coalition fleets.

Tuple format: name, description, (metal, crystal, fuel), seconds, attack, hull,
hold, fuel factor, speed. Signature traits apply to that hull only, not the fleet.
Existing ship IDs and all saved counts/queues remain valid.
"""
from __future__ import annotations

CAPITAL_ROLES = ('battleship', 'dreadnought', 'flagship', 'titan')
COMBAT_ROLES = ('frigate', 'cruiser', 'interceptor', 'siege', *CAPITAL_ROLES)
SHIP_ORDER = ('scout', 'cargo', 'colonizer', 'frigate', 'cruiser', 'interceptor',
              'freighter', 'siege', *CAPITAL_ROLES)
ROLE_NAMES = {'battleship': 'Pancernik', 'dreadnought': 'Drednot',
              'flagship': 'Okręt specjalny rasy', 'titan': 'Tytan'}

SHIPS = {
    'zetans': {
        'battleship': ('Strażnik Horyzontu', 'Liniowy pancernik fazowy. Silna salwa i mobilność kosztem lżejszego kadłuba.',
                       (14000, 11500, 3800), 3300, 850, 2450, 600, 55, .8),
        'dreadnought': ('Kataklizm', 'Ciężka platforma plazmowa do długich kampanii. Wymaga licznej eskorty.',
                        (70000, 82000, 22000), 18000, 3800, 10000, 1800, 210, .48),
        'flagship': ('Pryzmat Osobliwości', 'Tylko Zetanie. Własna pierwsza salwa ×1,6, dodatkowo do premii rasy. Nie wzmacnia innych okrętów.',
                     (180000, 280000, 85000), 54000, 9500, 22000, 3500, 420, .65),
        'titan': ('Arka Zenitu', 'Tytan zasilany rdzeniem gwiezdnym. Budowa wymaga ukończonej Sfery Dysona w tej kolonii. Potężny, ale kosztowny i powolny.',
                  (1200000, 1600000, 550000), 259200, 48000, 140000, 15000, 2300, .3),
    },
    'symbionts': {
        'battleship': ('Behemot', 'Żywy pancernik o grubym kadłubie. Regeneracja pomaga przetrwać kolejne rundy.',
                       (14000, 7800, 6500), 4290, 700, 4100, 850, 44, .55),
        'dreadnought': ('Trawiciel Gwiazd', 'Ogromny organizm bojowy. Wytrzymały, lecz wolniejszy od mniejszych łowców.',
                        (74000, 50000, 45000), 23400, 3200, 18000, 2600, 160, .34),
        'flagship': ('Matriarcha', 'Tylko Symbionci. Po rundzie leczy 60% ran własnego ocalałego kadłuba. Nie wskrzesza strat ani nie leczy innych okrętów.',
                     (190000, 140000, 160000), 70200, 7500, 40000, 5000, 330, .38),
        'titan': ('Prarodzic', 'Tytaniczny organizm próżniowy. Hodowla wymaga ukończonej Sfery Dysona w tej kolonii. Ogromna wytrzymałość okupiona kosztem i powolnością.',
                  (1300000, 900000, 950000), 336960, 40000, 230000, 22000, 1800, .2),
    },
    'automatons': {
        'battleship': ('Dominator', 'Ciężki pancernik kinetyczny. Pancerz i siła ognia kosztem wysokiego spalania.',
                       (20500, 8500, 4900), 3000, 880, 4650, 750, 82, .5),
        'dreadnought': ('Egzekutor', 'Drednot z baterią akceleratorów. Wolna, paliwożerna maszyna do przełamywania frontu.',
                        (110000, 50000, 28000), 16200, 4000, 20000, 2200, 320, .3),
        'flagship': ('Bastion Omega', 'Tylko Automatony. Własny pancerz redukuje pozostałe obrażenia o 20% po premii rasy. Nie chroni innych okrętów.',
                     (300000, 135000, 100000), 48600, 9000, 46000, 4200, 600, .3),
        'titan': ('Kolos Wieczności', 'Tytan przemysłowej cywilizacji. Budowa wymaga ukończonej Sfery Dysona w tej kolonii. Olbrzymi pancerz i działa, bardzo duże spalanie.',
                  (1900000, 850000, 650000), 233280, 50000, 270000, 18000, 3600, .18),
    },
}

# No late-game hull is silently made available to a race-less account.
NEUTRAL_SHIPS = {
    key: (ROLE_NAMES[key], 'Wybierz rasę, aby poznać wariant tego okrętu.', *SHIPS['zetans'][key][2:])
    for key in CAPITAL_ROLES
}

COMMON_REQUIREMENTS = {
    'battleship': (('shipyard', 7), ('research', 'capital_shipbuilding', 2),
                   ('research', 'weapons', 5), ('research', 'hyperspace', 3)),
    'dreadnought': (('shipyard', 9), ('research', 'capital_shipbuilding', 5),
                    ('research', 'capital_weapons', 3), ('research', 'hyperspace', 5)),
    'titan': (('shipyard', 12), ('research', 'titan_core', 1),
              ('research', 'capital_shipbuilding', 8), ('research', 'capital_weapons', 6),
              ('megastructures', 'dyson', 4)),
}

SIGNATURES = {
    'zetans': ('psionic_command', 'Dowodzenie psioniczne', 'coherent_plasma', 'quantum_foundry'),
    'symbionts': ('brood_sovereignty', 'Suwerenność roju', 'corrosive_spores', 'brood_chamber'),
    'automatons': ('siege_autonomy', 'Autonomia oblężnicza', 'siege_algorithms', 'assembly_hub'),
}
RESEARCH = {}
REQUIREMENTS = {}
for race, (key, name, weapon, facility) in SIGNATURES.items():
    RESEARCH[race] = {key: {
        'spec': (name, 'Odblokowuje okręt specjalny: ' + SHIPS[race]['flagship'][0] + '.',
                 (110000, 145000, 55000), 72000),
        'requirements': (('lab', 9), ('research', 'capital_shipbuilding', 5),
                         ('research', 'capital_weapons', 3), ('research', weapon, 3)),
        'max_level': 1,
    }}
    REQUIREMENTS[race] = {**COMMON_REQUIREMENTS,
        'flagship': (('shipyard', 10), (facility, 4), ('research', key, 1),
                     ('research', 'hyperspace', 6))}

RACIAL_TRAITS = {
    'zetans': {'flagship': {'first_volley': 1.6}},
    'symbionts': {'flagship': {'regeneration_fraction': .60}},
    'automatons': {'flagship': {'damage_reduction': .20}},
}

def traits(race_id):
    """Read-only traits; callers must not mutate the returned mapping."""
    return RACIAL_TRAITS.get(race_id, {})


def round_factors(race_id, round_no):
    return {key: values.get('first_volley', 1.0) if round_no == 1 else 1.0
            for key, values in traits(race_id).items()}
