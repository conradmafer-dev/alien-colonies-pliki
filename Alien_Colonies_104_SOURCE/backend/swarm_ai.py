"""Budgeted Khar plague: colonization first, small garrisons, slow strength growth.

No free ships, stock, or catch-up AI decisions. Every nest spends its own wallet,
uses normal queues, pays round-trip fuel and consumes a real colony ship.
The twenty-four-hour galaxy gate and forty-eight-hour source gate use real World.now.
New nests must be at least twenty-four hours old before launching a colonizer.
"""
from __future__ import annotations

import math
import secrets

try:
    from .i18n import t
    from . import swarm, defenses, production_timing, planetary
except ImportError:
    from i18n import t
    import swarm, defenses, production_timing, planetary

RESOURCES = ("metal", "crystal", "fuel")


class SwarmAIMixin:
    @staticmethod
    def _swarm_ready(planet):
        return swarm.ready(planet)

    @staticmethod
    def _swarm_weapon_level(planet):
        return swarm.weapon_level(planet)

    def _swarm_pending_colonies(self):
        return [f for f in self.data["fleets"].values()
                if f["owner_id"] == swarm.OWNER_ID and f["mission"] == "colonize"
                and f["status"] == "outbound"]

    def _swarm_colony_room(self, origin):
        planets = list(self.data["planets"].values())
        colonies = [p for p in planets if p["owner_id"] == swarm.OWNER_ID]
        pending = self._swarm_pending_colonies()
        galaxy = self._galaxy_id(origin)
        if len(colonies) + len(pending) >= swarm.MAX_COLONIES:
            return False
        local = sum(self._galaxy_id(p) == galaxy for p in colonies)
        local += sum(self._galaxy_id(self.data["planets"][f["target_id"]]) == galaxy for f in pending)
        return local < swarm.MAX_COLONIES_PER_GALAXY

    def _swarm_has_colony_commitment_room(self, origin):
        """Do not pay for dozens of surplus colony hulls at the infestation cap.

        Built/queued hulls reserve planning capacity, not a particular planet.
        Actual launch/arrival still use the independent authoritative cap checks.
        """
        galaxy = self._galaxy_id(origin)
        planets = list(self.data["planets"].values())
        colonies = [p for p in planets if p["owner_id"] == swarm.OWNER_ID]
        pending = self._swarm_pending_colonies()
        planned = [(self._galaxy_id(p), max(0, p["ships"].get("colonizer", 0))
                    + sum(q.get("amount", 1) for q in p["queue"]
                          if q["kind"] == "ship" and q["key"] == "colonizer")) for p in colonies]
        total = len(colonies) + len(pending) + sum(n for _, n in planned)
        local = (sum(self._galaxy_id(p) == galaxy for p in colonies)
                 + sum(self._galaxy_id(self.data["planets"][f["target_id"]]) == galaxy for f in pending)
                 + sum(n for g, n in planned if g == galaxy))
        return total < swarm.MAX_COLONIES and local < swarm.MAX_COLONIES_PER_GALAXY

    def _swarm_expansion_target(self, origin):
        """Do not compete with any already paid colony flight, including players'."""
        if not self._swarm_colony_room(origin):
            return None
        already_planned = (origin["ships"].get("colonizer", 0) > 0 or any(
            q["kind"] == "ship" and q["key"] == "colonizer" for q in origin["queue"]))
        if not already_planned and not self._swarm_has_colony_commitment_room(origin):
            return None
        if any(f["origin_id"] == origin["id"] for f in self._swarm_pending_colonies()):
            return None
        reserved = {f["target_id"] for f in self.data["fleets"].values()
                    if f["mission"] == "colonize" and f["status"] == "outbound"}
        galaxy = self._galaxy_id(origin)
        candidates = [p for p in self.data["planets"].values()
                      if p["owner_type"] == "empty" and p["id"] not in reserved
                      and self._galaxy_id(p) == galaxy]
        return min(candidates, key=lambda p: (self._distance(origin, p), p["id"])) if candidates else None

    def _swarm_expansion_due(self, origin):
        galaxy = self._galaxy_id(origin)
        gates = self.data["alien"].setdefault("swarm_next_colonization_by_galaxy", {})
        return (self.now >= gates.get(galaxy, 0)
                and self.now >= origin.get("swarm_next_colonization_at", 0)
                and self.now - origin.get("swarm_established_at", self.now) >= swarm.COLONY_MATURITY_SECONDS)

    def _swarm_launch(self, origin, target, mission, ships, *, raid=False):
        """Recheck ownership, reservations, age, caps, clocks, garrison and fuel."""
        if (origin.get("owner_id") != swarm.OWNER_ID or target["id"] == origin["id"]
                or mission not in ("colonize", "attack") or not isinstance(ships, dict)
                or set(ships) - set(swarm.SHIPS)
                or any(type(n) is not int or n < 0 for n in ships.values())):
            return None
        ships = {key: ships.get(key, 0) for key in swarm.SHIPS}
        if not sum(ships.values()) or any(n > origin["ships"].get(k, 0) for k, n in ships.items()):
            return None
        alien = self.data["alien"]
        if raid and mission != "attack":
            return None
        if mission == "colonize":
            if (not self._swarm_expansion_due(origin) or not self._swarm_colony_room(origin)
                    or target["owner_type"] != "empty" or ships["colonizer"] != 1
                    or self._galaxy_id(target) != self._galaxy_id(origin)
                    or any(f["origin_id"] == origin["id"] for f in self._swarm_pending_colonies())
                    or any(f["target_id"] == target["id"] and f["mission"] == "colonize"
                           and f["status"] == "outbound" for f in self.data["fleets"].values())
                    or any(ships[k] < n for k, n in swarm.EXPANSION_ESCORT.items())):
                return None
        elif raid:
            party = {key: swarm.RAID_PARTY.get(key, 0) for key in swarm.SHIPS}
            if (ships != party or self.now < alien.get("swarm_next_raid_at", self.now + swarm.RAID_INTERVAL_SECONDS)
                    or self._swarm_raid_score(origin, target, ships) <= 0
                    or any(f["owner_id"] == swarm.OWNER_ID and f["mission"] == "attack"
                           and f["status"] == "outbound" for f in self.data["fleets"].values())):
                return None
        else:
            if (any(p["owner_type"] == "empty" for p in self.data["planets"].values())
                    or target["owner_type"] != "player"
                    or self._player(target["owner_id"])["protected_until"] > self.now
                    or origin.get("swarm_next_attack_at", 0) > self.now):
                return None
        if any(origin["ships"].get(k, 0) - ships[k] < n
               for k, n in swarm.defense_minimum(origin).items()):
            return None
        seconds, fuel = self._flight_numbers(origin, target, ships)
        if origin["resources"]["fuel"] < fuel:
            return None
        origin["resources"]["fuel"] -= fuel
        for key, amount in ships.items():
            origin["ships"][key] -= amount
        fleet = {"id": "f" + secrets.token_hex(8), "owner_id": swarm.OWNER_ID,
                 "race_id": "swarm", "origin_id": origin["id"], "target_id": target["id"],
                 "mission": mission, "status": "outbound", "ships": ships,
                 "cargo": dict.fromkeys(RESOURCES, 0), "swarm_crystals": 0,
                 "swarm_weapon_level": self._swarm_weapon_level(origin),
                 "started_at": self.now, "seconds": seconds, "arrives_at": self.now + seconds,
                 "route": self._route_details(origin, target)}
        if raid:
            fleet["swarm_raid"] = True
        self.data["fleets"][fleet["id"]] = fleet
        origin["swarm_activity"] = "expanding" if mission == "colonize" else "raiding"
        if mission == "colonize":
            alien.setdefault("swarm_next_colonization_by_galaxy", {})[self._galaxy_id(origin)] = self.now + swarm.EXPANSION_SECONDS
            origin["swarm_next_colonization_at"] = self.now + swarm.ORIGIN_EXPANSION_SECONDS
        elif raid:
            alien["swarm_next_raid_at"] = self.now + swarm.RAID_INTERVAL_SECONDS
            self._player(target["owner_id"])["swarm_raid_protected_until"] = self.now + swarm.RAID_TARGET_INTERVAL_SECONDS
            origin["swarm_next_attack_at"] = self.now + swarm.ATTACK_SECONDS
        else:
            origin["swarm_next_attack_at"] = self.now + swarm.ATTACK_SECONDS
        return fleet

    def _swarm_raid_score(self, origin, target, ships):
        """Keep existing new-player protection and ordinary-resource-only raids."""
        if self._galaxy_id(origin) != self._galaxy_id(target) or target.get("owner_type") != "player":
            return 0
        player = self._player(target["owner_id"])
        if (player["protected_until"] > self.now
                or player.get("swarm_raid_protected_until", 0) > self.now):
            return 0
        if sum(target["resources"][key] for key in RESOURCES) < swarm.RAID_MIN_STOCK:
            return 0
        capacity = sum(swarm.SHIPS[key][6] * amount for key, amount in ships.items())
        _, fuel = self._flight_numbers(origin, target, ships)
        gain = min(capacity, sum(self._lootable_resources(target).values())) - 3 * fuel
        if gain < swarm.RAID_MIN_GAIN:
            return 0
        attack = self._power(ships, self._swarm_weapon_level(origin), swarm.SHIPS)
        defense = self._power({**target["ships"], **target.get("defenses", {})}, player["research"]["weapons"],
                              {**self._specs(target["owner_id"], "ships"), **self._specs(target["owner_id"], "defenses")})
        return gain if defense <= attack * 1.1 else 0

    def _swarm_queue(self, planet, kind, key, amount=1, *, reserve=None):
        """Pay before queueing. Optional earmarks protect the next colony budget."""
        if (planet.get("owner_id") != swarm.OWNER_ID or planet["queue"]
                or kind not in ("ship", "build", "defense") or type(amount) is not int
                or not 1 <= amount <= 1000):
            return False
        specs = swarm.SHIPS if kind == "ship" else defenses.DEFENSES["swarm"] if kind == "defense" else swarm.BUILDINGS
        if key not in specs:
            return False
        if kind in ("ship", "defense") and planet["buildings"]["shipyard"] < (2 if key == "cruiser" else 1):
            kind, key, amount, specs = "build", "shipyard", 1, swarm.BUILDINGS
        if kind == "build":
            amount = 1
        level = 0 if kind in ("ship", "defense") else planet["buildings"][key]
        if kind == "build" and (level >= swarm.MAX_BUILDING_LEVEL or planetary.fields(planet)["free"] < 1):
            return False
        spec = specs[key]
        costs = {k: math.ceil(value * 1.65 ** level) * amount for k, value in zip(RESOURCES, spec[2])}
        reserve = reserve or {}
        if any(planet["resources"][k] < cost + max(0, reserve.get(k, 0)) for k, cost in costs.items()):
            return False
        for resource, cost in costs.items():
            planet["resources"][resource] -= cost
        group = {"ship": "ships", "defense": "defenses", "build": "buildings"}[kind]
        duration = production_timing.project_seconds(spec[3], level, group, planet["buildings"], self.speed, amount=amount)
        planet["queue"].append({"id": "q" + secrets.token_hex(8), "kind": kind, "key": key,
                                "amount": amount, "level": level + 1, "started_at": self.now,
                                "seconds": duration,
                                "facility_timing": production_timing.facility_profile(planet["buildings"], group),
                                "ends_at": self.now + duration})
        return True

    def _swarm_train_to(self, planet, targets, *, reserve=None):
        reserve = reserve or {}
        candidates = sorted(targets, key=lambda key: (planet["ships"].get(key, 0) / max(1, targets[key]), key))
        for key in candidates:
            missing = targets[key] - planet["ships"].get(key, 0)
            if missing <= 0:
                continue
            batch = min(missing, 8 if key == "frigate" else 2)
            affordable = min((int(max(0, planet["resources"][r] - reserve.get(r, 0)) // cost)
                              for r, cost in zip(RESOURCES, swarm.SHIPS[key][2]) if cost), default=batch)
            if affordable > 0 and self._swarm_queue(planet, "ship", key, min(batch, affordable), reserve=reserve):
                return True
        return False

    def _swarm_train_defenses(self, planet, *, reserve=None):
        missing = defenses.swarm_target(planet) - planet.get("defenses", {}).get("acid_spire", 0)
        if missing > 0 and self._swarm_queue(planet, "defense", "acid_spire", 1, reserve=reserve):
            planet["swarm_activity"] = "fortifying"
            return True
        return False

    def _swarm_economy_candidates(self, planet):
        age = max(0, self.now - planet.get("swarm_established_at", self.now))
        mining = min(swarm.MAX_ECONOMY_LEVEL, 1 + int(age // swarm.ECONOMY_LEVEL_SECONDS))
        facility = min(swarm.MAX_FACILITY_LEVEL, 1 + int(age // (2 * swarm.ECONOMY_LEVEL_SECONDS)))
        buildings = planet["buildings"]
        if planetary.fields(planet)["free"] < 1:
            return []
        priorities = ("metal_mine", "crystal_mine", "refinery", "power_plant", "shipyard", "lab")
        goals = {k: facility if k in ("shipyard", "lab") else mining for k in priorities}
        candidates = [k for k in priorities if buildings[k] < goals[k]]
        candidates.sort(key=lambda k: (buildings[k] / goals[k], priorities.index(k)))
        if self.energy(planet)["factor"] < 1 and buildings["power_plant"] < swarm.MAX_ECONOMY_LEVEL:
            candidates = ["power_plant"] + [k for k in candidates if k != "power_plant"]
        return candidates

    def _swarm_economy_reserve(self, planet):
        candidates = self._swarm_economy_candidates(planet)
        if not candidates:
            return {}
        key = candidates[0]
        return {r: math.ceil(cost * 1.65 ** planet["buildings"][key])
                for r, cost in zip(RESOURCES, swarm.BUILDINGS[key][2])}

    def _swarm_grow_economy(self, planet, *, reserve=None):
        """One potential mining level per 36 h; facilities per 72 h, never free."""
        return any(self._swarm_queue(planet, "build", k, reserve=reserve)
                   for k in self._swarm_economy_candidates(planet))

    def _swarm_colony_reserve(self, planet, target):
        """Earmark (do not grant or subtract) one hull, a tiny escort and paid fuel."""
        wanted = {k: swarm.defense_minimum(planet).get(k, 0) + swarm.EXPANSION_ESCORT.get(k, 0)
                  for k in swarm.SHIPS}
        wanted["colonizer"] = 1
        reserved = dict.fromkeys(RESOURCES, 0)
        for key, count in wanted.items():
            missing = max(0, count - planet["ships"].get(key, 0))
            for resource, cost in zip(RESOURCES, swarm.SHIPS[key][2]):
                reserved[resource] += missing * cost
        expedition = {"colonizer": 1, **swarm.EXPANSION_ESCORT}
        _, fuel = self._flight_numbers(planet, target, expedition)
        reserved["fuel"] += fuel
        return reserved

    def _swarm_surplus_fleet(self, planet, *, reserve=None):
        """Garrison targets are not caps: spend surplus on real additional ships."""
        units = planet["ships"]
        if planet["buildings"]["shipyard"] >= 2 and units.get("cruiser", 0) * 16 < units.get("frigate", 0):
            if self._swarm_queue(planet, "ship", "cruiser", reserve=reserve):
                return True
            reserve = {r: (reserve or {}).get(r, 0) + cost
                       for r, cost in zip(RESOURCES, swarm.SHIPS["cruiser"][2])}
        return self._swarm_train_to(planet, {"frigate": units.get("frigate", 0) + 8}, reserve=reserve)

    def _ensure_swarm_expansion_tempo(self):
        """Extend old expansion clocks once; preserve paid work and existing nests."""
        if self.data.get("swarm_expansion_tempo") == swarm.EXPANSION_TEMPO_ID:
            return
        gates = self.data["alien"].setdefault("swarm_next_colonization_by_galaxy", {})
        for galaxy, deadline in gates.items():
            gates[galaxy] = max(deadline, self.now + swarm.EXPANSION_SECONDS)
        for planet in self.data["planets"].values():
            if planet["owner_id"] == swarm.OWNER_ID:
                galaxy = self._galaxy_id(planet)
                gates[galaxy] = max(gates.get(galaxy, 0), self.now + swarm.EXPANSION_SECONDS)
                planet["swarm_next_colonization_at"] = max(
                    planet.get("swarm_next_colonization_at", 0),
                    self.now + swarm.ORIGIN_EXPANSION_SECONDS)
        self.data["swarm_expansion_tempo"] = swarm.EXPANSION_TEMPO_ID

    def _alien_turn(self):
        self._ensure_swarm_activation()
        self._ensure_swarm_expansion_tempo()
        planets = list(self.data["planets"].values())
        colonies = sorted((p for p in planets if p["owner_id"] == swarm.OWNER_ID),
                          key=lambda p: (p.get("swarm_next_colonization_at", 0), p["id"]))
        alien = self.data["alien"]
        alien.setdefault("swarm_next_raid_at", self.now + swarm.RAID_INTERVAL_SECONDS)
        for planet in colonies:
            target = self._swarm_expansion_target(planet)
            # Launch a completed expedition even while another facility is building.
            if target and self._swarm_expansion_due(planet):
                if self._swarm_launch(planet, target, "colonize", {"colonizer": 1, **swarm.EXPANSION_ESCORT}):
                    target = None
            if planet["queue"]:
                continue
            planet["swarm_activity"] = "stockpiling"
            reserve = self._swarm_colony_reserve(planet, target) if target else {}
            if target:
                planet["swarm_activity"] = "preparing_expansion"
                # A paid colony hull has priority over a large garrison or a lab.
                if planet["ships"].get("colonizer", 0) < 1:
                    if self._swarm_queue(planet, "ship", "colonizer"):
                        continue
                else:
                    escort = {k: swarm.defense_minimum(planet).get(k, 0) + swarm.EXPANSION_ESCORT.get(k, 0)
                              for k in swarm.EXPANSION_ESCORT}
                    _, fuel = self._flight_numbers(planet, target, {"colonizer": 1, **swarm.EXPANSION_ESCORT})
                    if self._swarm_train_to(planet, escort, reserve={"fuel": fuel}):
                        continue
            # Use resources beyond the expansion earmark instead of doing nothing
            # at an arbitrary military cap. A poor nest saves for its colony hull.
            if self._swarm_grow_economy(planet, reserve=reserve):
                planet["swarm_activity"] = "developing"
                continue
            # Protect one next economic project from endless cheap-fleet spending.
            economic_reserve = self._swarm_economy_reserve(planet)
            reserve = {r: reserve.get(r, 0) + economic_reserve.get(r, 0) for r in RESOURCES}
            if self._swarm_train_to(planet, swarm.defense_targets(planet, self.now), reserve=reserve):
                planet["swarm_activity"] = "building_fleet"
                continue
            if self._swarm_train_defenses(planet, reserve=reserve):
                continue
            if not target and self.now >= alien["swarm_next_raid_at"]:
                attack_targets = [p for p in planets if self._swarm_raid_score(planet, p, swarm.RAID_PARTY) > 0]
                if attack_targets:
                    raid_target = max(attack_targets, key=lambda p: self._swarm_raid_score(planet, p, swarm.RAID_PARTY))
                    raid_units = {k: swarm.defense_minimum(planet).get(k, 0) + n for k, n in swarm.RAID_PARTY.items()}
                    if self._swarm_train_to(planet, raid_units):
                        planet["swarm_activity"] = "preparing_raid"
                        continue
                    fleet = self._swarm_launch(planet, raid_target, "attack", swarm.RAID_PARTY, raid=True)
                    if fleet:
                        self._report(raid_target["owner_id"], t('Najazd Roju po surowce'),
                            t('Transportowce Roju z eskortą lecą z {0} na {1} po zapasy. Przybędą za {2} s.').format(
                                planet['name'], raid_target['name'], fleet['seconds']), "swarm/weapon")
            if self._swarm_surplus_fleet(planet, reserve=reserve):
                planet["swarm_activity"] = "building_fleet"
