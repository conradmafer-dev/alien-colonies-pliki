"""Additive six-galaxy topology and authoritative intergalactic navigation.

Galactic map coordinates are illustrative. Costs use fixed catalogue coordinates,
never client data, and are prepaid for BOTH legs, just like local travel in 0.5.1.
"""
from __future__ import annotations

import math

try:
    from .i18n import t
    from . import swarm, planetary, galaxy_topology
except ImportError:
    from i18n import t
    import swarm, planetary, galaxy_topology

SYSTEMS_PER_GALAXY = 30
JUMP_BASE_FUEL = 1_000_000
JUMP_FUEL_PER_MASS = 40_000
JUMP_SECONDS_PER_MLY = 21_600
CATALOG = (
    {"id": "g1", "name": "Aurora", "x": 0.0, "y": 0.0, "art_key": "galaxies/aurora",
     "description": "Błękitna galaktyka z jasnymi ramionami. Nowe imperia trafiają do kolejnej galaktyki, gdy zajęta jest co najmniej połowa planet poprzedniej."},
    {"id": "g2", "name": "Eclipse", "x": 1.0, "y": 0.0, "art_key": "galaxies/eclipse",
     "description": "Złote pasma pyłu otaczają ciemne jądro. Nowe imperia powstają wśród gwiazd."},
    {"id": "g3", "name": "Nexus", "x": -1.2, "y": 1.4, "art_key": "galaxies/nexus",
     "description": "Fioletowe ramiona i jasne jądro. Nowe układy czekają na kolonistów."},
    {"id": "g4", "name": "Omega", "x": 2.4, "y": 0.8, "art_key": "galaxies/omega",
     "description": "Czerwona spirala gwiazd. Wyprawa wymaga dużych rezerw paliwa."},
    {"id": "g5", "name": "Zephyr", "x": 0.0, "y": -3.0, "art_key": "galaxies/zephyr",
     "description": "Turkusowa galaktyka daleko od domu. Zaplanuj samodzielną kolonię."},
    {"id": "g6", "name": "Void", "x": 3.5, "y": -3.0, "art_key": "galaxies/void",
     "description": "Ciemne jądro na skraju znanej przestrzeni. Najdalsza wyprawa z Aurory."},
)
BY_ID = {g["id"]: g for g in CATALOG}


def separation(a: str, b: str) -> float:
    """Millions of fictional light-years; zero inside the same galaxy."""
    if a == b:
        return 0.0
    ga, gb = BY_ID[a], BY_ID[b]
    return max(1.0, math.hypot(ga["x"] - gb["x"], ga["y"] - gb["y"]))


def inferred_id(system_id: str) -> str:
    # Keeps all original s1..s30 identities. Newly allocated systems stay numeric.
    number = int(system_id[1:]) if system_id.startswith("s") and system_id[1:].isdigit() else 1
    return "g" + str(max(1, (number - 1) // SYSTEMS_PER_GALAXY + 1))


class UniverseMixin:
    def _ensure_universe(self, data=None):
        """Never erase/reseed existing worlds, players, accounts, queues or fleets.

        Adding or viewing a galaxy never activates its swarm. Activation follows
        actual player settlement. Existing deadlines stay absolute.
        """
        data = self.data if data is None else data
        for system in data["systems"]:
            # The legacy numeric allocation still identifies the original six
            # galaxies. Newly added systems always persist an explicit galaxy.
            inferred = inferred_id(system["id"])
            system.setdefault("galaxy_id", inferred if inferred in BY_ID else "g1")
            for pid in system["planet_ids"]:
                data["planets"][pid].setdefault("galaxy_id", system["galaxy_id"])
        numeric = [int(s["id"][1:]) for s in data["systems"] if s["id"].startswith("s") and s["id"][1:].isdigit()]
        next_number = max(numeric, default=0) + 1
        home_names = [s["name"] for s in data["systems"] if s["galaxy_id"] == "g1"]
        for galaxy in CATALOG[1:]:
            if any(s["galaxy_id"] == galaxy["id"] for s in data["systems"]):
                continue
            new_systems = []
            for index in range(SYSTEMS_PER_GALAXY):
                sid = f"s{next_number}"
                next_number += 1
                suffix = home_names[index % len(home_names)] if home_names else str(index + 1)
                name = f"{galaxy['name']} {suffix}"
                planet_ids = []
                for slot in range(1, planetary.system_count(sid) + 1):
                    pid = f"{sid}p{slot}"
                    planet = self._planet(pid, f"{name} {slot}", sid, slot)
                    planet["galaxy_id"] = galaxy["id"]
                    data["planets"][pid] = planet
                    planet_ids.append(pid)
                new_systems.append({"id": sid, "name": name, "galaxy_id": galaxy["id"],
                                    "x": float(index % 6), "y": float(index // 6), "planet_ids": planet_ids})
            data["systems"].extend(new_systems)
        galaxy_topology.ensure_rings(data, CATALOG, self._planet)
        self._navigation_cache = None
        data["galaxies"] = [{"id": g["id"], "name": g["name"]} for g in CATALOG]

    def _eligible_swarm_galaxies(self, data=None):
        """Aurora plus galaxies settled by real players, never merely observed."""
        data = self.data if data is None else data
        players = data.get("players", {})
        return {"g1"} | {self._galaxy_id(p) for p in data["planets"].values()
                          if p.get("owner_type") == "player"
                          and p.get("owner_id") in players
                          and self._galaxy_id(p) in BY_ID}

    def _ensure_swarm_activation(self, data=None):
        """Bootstrap each inhabited galaxy once, without claiming reserved worlds.

        Records live in the persistent world snapshot. A missing/deleted nest
        never resets a completed record. When a full galaxy has no safe site,
        activation remains pending until an empty, unreserved planet is available.
        Existing nests are adopted without granting crystals or restarting clocks.
        """
        data = self.data if data is None else data
        alien = data["alien"]
        records = alien.setdefault("swarm_activated_galaxies", {})
        planets = data["planets"]
        # Adopt pre-existing nests once, including paid outposts left after a hive
        # was removed. Do not recreate a bootstrap merely because no hive remains.
        for planet in planets.values():
            if planet.get("owner_id") != swarm.OWNER_ID:
                continue
            galaxy = self._galaxy_id(planet)
            record = records.setdefault(galaxy, {"activated_at": self.now})
            if "seeded_at" not in record:
                record.update(seeded_at=planet.get("swarm_established_at", self.now),
                              planet_id=planet["id"])
        for galaxy in self._eligible_swarm_galaxies(data):
            records.setdefault(galaxy, {"activated_at": self.now})
        reserved = {f["target_id"] for f in data.get("fleets", {}).values()
                    if f.get("mission") == "colonize" and f.get("status") == "outbound"}
        seeded = []
        for galaxy in BY_ID:
            record = records.get(galaxy)
            if record is None or "seeded_at" in record:
                continue
            candidates = [p for p in planets.values()
                          if p.get("owner_type") == "empty" and not p.get("owner_id")
                          and p["id"] not in reserved and self._galaxy_id(p) == galaxy]
            if not candidates:
                continue
            preferred = f"s{15 + SYSTEMS_PER_GALAXY * (int(galaxy[1:]) - 1)}p2"
            planet = min(candidates, key=lambda p: (p["id"] != preferred, p["id"]))
            swarm.seed(planet, self.now, hive=True)
            record.update(seeded_at=self.now, planet_id=planet["id"])
            alien.setdefault("swarm_next_colonization_by_galaxy", {})[galaxy] = self.now + swarm.COLONY_MATURITY_SECONDS
            seeded.append(planet["id"])
        return seeded

    def _galaxy_id(self, planet):
        return planet.get("galaxy_id", inferred_id(planet["system_id"]))

    def _galaxy_navigation(self):
        # Systems are immutable after additive migrations. A replaced snapshot
        # or a rolled-back expansion changes the list identity/length; routine
        # action rollbacks restore equivalent immutable geography in place.
        systems = self.data["systems"]
        cached = getattr(self, "_navigation_cache", None)
        if cached is None or cached[0] is not systems or cached[1] != len(systems):
            cached = (systems, len(systems), galaxy_topology.Navigation(systems))
            self._navigation_cache = cached
        return cached[2]

    def _system_navigation_distance(self, origin, target):
        navigation = self._galaxy_navigation()
        if self._galaxy_id(origin) == self._galaxy_id(target):
            distance = navigation.route(origin["system_id"], target["system_id"])["distance"]
            if distance is None:
                raise ValueError("Disconnected local galaxy navigation")
        else:
            # Preserve the existing intergalactic travel-time geometry.
            first, second = navigation.systems[origin["system_id"]], navigation.systems[target["system_id"]]
            distance = math.hypot(first["x"] - second["x"], first["y"] - second["y"])
        return distance + abs(origin["slot"] - target["slot"]) * .08 + .1

    def _route_details(self, origin, target):
        a, b = self._galaxy_id(origin), self._galaxy_id(target)
        distance = separation(a, b)
        route = (self._galaxy_navigation().route(origin["system_id"], target["system_id"])
                 if a == b else {"system_ids": [], "segments": []})
        return {"intergalactic": a != b, "origin_galaxy_id": a, "target_galaxy_id": b,
                "origin_galaxy_name": BY_ID[a]["name"], "target_galaxy_name": BY_ID[b]["name"],
                "distance_mly": round(distance, 3), "round_trip_fuel": True,
                "fuel_model": ("ogame_lanes_v85" if origin["owner_id"] != swarm.OWNER_ID
                               and self.now >= self.data.get("economy85_from", 0) else "legacy"),
                "fuel_distance": round(self._fuel_distance(origin, target), 8),
                "navigation_schema": galaxy_topology.SCHEMA,
                "system_ids": route["system_ids"], "segments": route["segments"],
                "local_distance": round(self._system_navigation_distance(origin, target), 8)}

    def _public_galaxies(self, origin, player_id, public_systems=None):
        result = []
        for g in CATALOG:
            systems = [s for s in self.data["systems"] if s["galaxy_id"] == g["id"]]
            visible = [s for s in (public_systems or []) if s["galaxy_id"] == g["id"]]
            planets = [q for s in visible for q in s["planets"]]
            distance = separation(self._galaxy_id(origin), g["id"])
            result.append({"id": g["id"], "name": g["name"], "description": t(g["description"]),
                           "art_key": g["art_key"], "systems_count": len(systems), "planets_count": len(planets),
                           "known_systems": sum(s["visibility"] != "unknown" for s in visible), "information_scope": "known",
                           "own_colonies": sum(p["owner_id"] == player_id for p in planets),
                           "hives_count": sum(p["owner_id"] == swarm.OWNER_ID for p in planets),
                           "distance_mly": round(distance, 3),
                           # No fixed jump activation fee for player fleets.
                           "minimum_jump_fuel": 0,
                           "navigation_schema": galaxy_topology.SCHEMA,
                           "rings_count": len({s.get("ring_index", 0) for s in systems})})
        return result
