"""Frozen 0.9.3 combat oracle for checking replay instrumentation only."""
from server.main import *

class Combat093:
    @staticmethod
    def _damage(fleet, damage, wounds, specs=None, damage_reduction=0.0, type_reductions=None):
        # Small ships absorb damage first; surviving wounds persist between rounds.
        specs = SHIPS if specs is None else specs
        damage *= 1.0 - damage_reduction
        for key in sorted(specs, key=lambda k: (specs[k][5], k)):
            if fleet.get(key, 0) <= 0:
                continue
            hull = specs[key][5]
            remaining = fleet[key] * hull - wounds.get(key, 0)
            resistance = min(.95, max(0.0, (type_reductions or {}).get(key, 0.0)))
            absorbed = min(damage, remaining / (1.0 - resistance))
            hit = absorbed * (1.0 - resistance)
            total = wounds.get(key, 0) + hit
            killed = min(fleet[key], int(total // hull))
            fleet[key] -= killed
            wounds[key] = total - killed * hull if fleet[key] else 0
            damage -= absorbed
            if damage <= 0:
                break

    @staticmethod
    def _regenerate(fleet, wounds, fraction, type_fractions=None):
        # Heal only the partially wounded surviving ship, never resurrect losses.
        for key in wounds:
            wounds[key] = wounds[key] * (1.0 - min(1.0, max(fraction, (type_fractions or {}).get(key, 0)))) if fleet[key] > 0 else 0

    def _battle(self, f, target):
        attacking_before = dict(f["ships"])
        defending = {**target["ships"], **target.get("defenses", {})}
        defending_before = dict(defending)
        attacker = f["owner_id"]
        defender = target["owner_id"]
        rare_loot_eligible = (defender == "khar"
                              and (defending_before.get("frigate", 0) + defending_before.get("cruiser", 0) + sum(target.get("defenses", {}).values())) > 0
                              and (not target.get("swarm_loot_sealed", False) or self._swarm_ready(target)))
        aw = int(f.get("swarm_weapon_level", 0)) if attacker == "khar" else self._player(attacker)["research"]["weapons"]
        dw = self._swarm_weapon_level(target) if defender == "khar" else self._player(defender)["research"]["weapons"]
        specs_a, specs_d = self._specs(attacker, "ships"), self._specs(defender, "ships")
        static_specs = self._specs(defender, "defenses")
        specs_d = {**specs_d, **static_specs}
        rules_a, rules_d = self._rules(attacker), self._rules(defender)
        # An older already travelling fleet has no retroactive building bonus.
        effects_a = f.get("building_effects", {})
        effects_d = self._building_effects(target)
        # Ignore renewal_fraction even if a legacy fleet saved it at departure.
        regeneration_a = self._regeneration_fraction(rules_a)
        regeneration_d = self._regeneration_fraction(rules_d, defense_effects=effects_d)
        wounds_a, wounds_d = {}, {}
        anti_swarm_a = 1.0 + (self._bonuses(attacker).get("swarm_damage", 0) if defender == "khar" else 0)
        anti_swarm_d = 1.0 + (self._bonuses(defender).get("swarm_damage", 0) if attacker == "khar" else 0)
        siege_factors = {key: meta.get("swarm_attack_multiplier", 1.0) for key, meta in SHIP_TRAITS.items()} if defender == "khar" else {}
        rounds = 0
        for _ in range(6):
            if not sum(f["ships"].values()) or not sum(defending.values()):
                break
            rounds += 1
            attack = self._power(f["ships"], aw, specs_a, (rules_a["first_volley_multiplier"] if rounds == 1 else 1.0) * anti_swarm_a, type_multipliers=siege_factors)
            defense = self._power(defending, dw, specs_d, (rules_d["first_volley_multiplier"] * (1 + effects_d.get("defense_first_volley", 0)) if rounds == 1 else 1.0) * anti_swarm_d, type_multipliers=defenses.round_factors(rounds))
            self._damage(defending, attack, wounds_d, specs_d, rules_d["damage_reduction"],
                         {k: v.get("damage_reduction", 0) for k, v in defenses.TRAITS.items()})
            self._damage(f["ships"], defense, wounds_a, specs_a, rules_a["damage_reduction"])
            self._regenerate(f["ships"], wounds_a, regeneration_a)
            self._regenerate(defending, wounds_d, regeneration_d,
                             {k: v.get("regeneration_fraction", 0) for k, v in defenses.TRAITS.items()})
        target["ships"] = {k: defending.get(k, 0) for k in self._specs(defender, "ships")}
        target["defenses"] = {k: defending.get(k, 0) for k in static_specs}
        victory = sum(defending.values()) == 0 and sum(f["ships"].values()) > 0
        capacity = fleet_capacity(specs_a, f["ships"])
        f["cargo"] = dict.fromkeys(RESOURCES, 0)
        f["swarm_crystals"] = 0
        recovered_metal = 0
        eradicated = False
        if victory:
            if defender == "khar" and attacker in self.data["players"]:
                stage = swarm.kind(target)
                quota = math.floor(swarm.RAID_CRYSTALS[stage] * (1.0 + self._bonuses(attacker).get("swarm_loot", 0)))
                crystals = min(int(target.get("swarm_crystals", 0)), quota, capacity) if rare_loot_eligible else 0
                target["swarm_crystals"] = max(0.0, target.get("swarm_crystals", 0) - crystals)
                f["swarm_crystals"] = crystals
                capacity -= crystals
                # Preserve attrition between cooperating players' separate raids.
                # Only victory seals the reserve: partial losses never do. The
                # remainder cannot be collected by a free zero-round follow-up
                # or by repeatedly killing the first rebuilding ship.
                target["swarm_loot_sealed"] = True
                # Defeating the stationed fleet never cancels paid reconstruction,
                # damages the shipyard or renews a suppression timer. An empty
                # nest cannot keep producing rare loot while its defense is pinned.
                target["swarm_suppressed_until"] = 0
            destroyed_metal = sum(specs_d[key][2][0] * (count - defending.get(key, 0)) for key, count in defending_before.items() if count)
            recovered_metal = min(capacity, math.floor(round(destroyed_metal * effects_a.get("wreck_recovery_fraction", 0), 6)))
            f["cargo"]["metal"] = recovered_metal
            capacity -= recovered_metal
            available = self._lootable_resources(target)
            total = sum(available.values())
            if total:
                for k, v in available.items():
                    n = min(v, math.floor(capacity * v / total)) if total > capacity else v
                    f["cargo"][k] += n
                    target["resources"][k] -= n
        if eradicated:
            target.update(owner_id="", owner_type="empty", resources=dict.fromkeys(RESOURCES, 0.0),
                          buildings=dict.fromkeys(BUILDINGS, 0), ships=blank_ships(), queue=[])
            for key in tuple(target):
                if key.startswith("swarm_"):
                    del target[key]
        lost_a = join_text(", ", (t('{0} ×{1}').format(specs_a[k][0], n - f['ships'][k]) for k, n in attacking_before.items() if n > f['ships'][k])) or t('brak')
        lost_d = join_text(", ", (t('{0} ×{1}').format(specs_d[k][0], n - defending[k]) for k, n in defending_before.items() if n > defending[k])) or t('brak')
        outcome = t('Zwycięstwo') if victory else t('Klęska') if sum(f["ships"].values()) == 0 else t('Nierozstrzygnięta bitwa — odwrót')
        summary = t('{0}: {1}. Rundy: {2}. Straty atakującego: {3}. Straty obrońcy: {4}. Zdobycz: metal {5}, kryształy {6}, paliwo {7}. ').format(target['name'], outcome, rounds, lost_a, lost_d, f['cargo']['metal'], f['cargo']['crystal'], f['cargo']['fuel'])
        if recovered_metal:
            summary += t(' Recykler Wraków odzyskał {0} metalu; jest w ładowni i zostanie rozładowany po powrocie.').format(recovered_metal)
        if effects_d.get("defense_first_volley", 0):
            summary += t(' Cytadela Magnetyczna: pierwsza salwa obrońcy +{0}%.').format(round(effects_d['defense_first_volley'] * 100))
        if effects_d.get("renewal_fraction", 0):
            summary += t(' Gaj Odnowy — regeneracja obrony planety +{0} pkt proc.').format(round(effects_d['renewal_fraction'] * 100))
        if defender == "khar":
            if attacking_before.get("siege", 0):
                summary += t(' Okręty oblężnicze: atak przeciw obronie Roju +50%.')
            summary += t(' Kryształy Roju: {0} w ładowni; trafią do koła po powrocie floty.').format(f['swarm_crystals'])
            if eradicated:
                summary += t(' Przyczółek został zniszczony. Planeta jest wolna i można ją skolonizować.')
            elif victory:
                summary += t(' Obrona została przełamana. Gniazdo zachowuje budynki i odbudowuje flotę. Odnowa kryształów czeka na odbudowę obrony.')
        else:
            summary += t(' Budynki i własność planety pozostają bez zmian.')
        for label, owner_id, regeneration in ((t('Atakujący'), attacker, regeneration_a), (t('Obrońca'), defender, regeneration_d)):
            race_id = self._race_id(owner_id)
            if race_id:
                rules = self._rules(owner_id)
                effects = []
                if rules["first_volley_multiplier"] > 1:
                    effects.append(t('pierwsza salwa +{0}%').format(round((rules['first_volley_multiplier'] - 1) * 100)))
                if regeneration:
                    effects.append(t('regeneracja {0}% ran po rundzie').format(round(regeneration * 100)))
                if rules["damage_reduction"]:
                    effects.append(t('redukcja obrażeń {0}%').format(round(rules['damage_reduction'] * 100)))
                summary += t(' {0} — {1}: {2}; {3}.').format(label, t(RACES[race_id]['name']), t(RACES[race_id]['weapon_name']), join_text(", ", effects))
        self._report(attacker, t('Raport bitwy'), summary, "swarm/weapon" if defender == "khar" else "", f["swarm_crystals"])
        self._report(defender, t('Twoja kolonia została zaatakowana'), summary, "swarm/weapon" if attacker == "khar" else "")
        self._return(f)

