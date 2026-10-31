"""Persistent staged Dyson construction and temporary wormhole windows.

All mutations are invoked inside World's existing atomic transaction. Time is
integrated analytically, including offline intervals and window exhaustion.
Transfers prepay an isolated return pulse; closing a window cannot strand ships.
"""
from __future__ import annotations

import copy
import math
import secrets

try:
    from .i18n import t
    from . import technology
except ImportError:
    from i18n import t
    import technology

RESOURCES = ("metal", "crystal", "fuel")
STAGES = (
    ("Fundament orbitalny", (125000, 80000, 25000), 21600),
    ("Pierścień kolektorów", (500000, 300000, 100000), 64800),
    ("Sieć kolektorów", (1500000, 900000, 250000), 172800),
    ("Ukończona Sfera Dysona", (4000000, 2500000, 750000), 432000),
)
GATE = ("Tunel czasoprzestrzenny", (2500000, 4000000, 1200000), 259200)
CAPACITY = (0, 25000000, 100000000, 350000000, 1200000000)
CHARGE = (0, 400, 1500, 6000, 20000)
POWER = (0, 2000, 10000, 40000, 120000)
WINDOW_SECONDS = 300
STABILIZE_SECONDS = 60
TRANSIT_SECONDS = 120  # Never scaled by server speed; defenders get real warning.
OPEN_ENERGY = 50000000
UPKEEP_PER_SECOND = 1000000
TRANSFER_PER_MASS = 250000
RETURN_PULSE_ENERGY = 85000000


def empty_project():
    return {"origin_id": "", "dyson_stage": 0, "gate_level": 0,
            "energy": 0.0, "queue": None, "window": None}


class MegastructureMixin:
    def _technology_effects(self, owner_id):
        return technology.effects(self.data["players"].get(owner_id, {}).get("research", {}))

    def _mega_origin_owned(self, player):
        origin_id = player.get("megastructure", {}).get("origin_id")
        origin = self.data["planets"].get(origin_id, {})
        return bool(origin_id and origin.get("owner_type") == "player"
                    and origin.get("owner_id") == player.get("id"))

    def _mega_profile(self, player):
        project = player.get("megastructure", {})
        stage = max(0, min(4, project.get("dyson_stage", 0)))
        effects = technology.effects(player.get("research", {}))
        # Heavy hulls must fit a prepaid two-way transfer at endgame. This
        # unlock expands storage, never the stored energy or charging speed.
        capacitor = 8 if player.get("research", {}).get("titan_core", 0) >= 1 else 1
        active = self._mega_origin_owned(player)
        return {"capacity": CAPACITY[stage] * (1 + effects.get("energy_capacity", 0)) * capacitor,
                "charge_per_second": CHARGE[stage] * (1 + effects.get("dyson_output", 0)) if active else 0,
                "power": POWER[stage] * (1 + effects.get("dyson_output", 0)) if active else 0}

    def _dyson_power(self, planet):
        player = self.data["players"].get(planet["owner_id"], {})
        return self._mega_profile(player)["power"] if player.get("megastructure", {}).get("origin_id") == planet["id"] else 0

    def _advance_megastructures(self, start, end):
        if end <= start:
            return
        for player in self.data["players"].values():
            project = player.get("megastructure")
            if not project:
                continue
            if not self._mega_origin_owned(player):
                # Completed stages and stored energy remain with their builder.
                # A lost colony supplies nothing until it is recaptured, and an
                # old tunnel can never resume automatically after occupation.
                project["window"] = None
                continue
            profile = self._mega_profile(player)
            cap, charge = profile["capacity"], profile["charge_per_second"]
            energy = min(cap, max(0.0, project["energy"]))
            window = project.get("window")
            cursor = start
            if window:
                active_start = max(start, window["opened_at"])
                active_end = min(end, window["closes_at"])
                if active_start > cursor:
                    energy = min(cap, energy + charge * (min(active_start, end) - cursor))
                    cursor = min(active_start, end)
                if active_end > cursor:
                    duration = active_end - cursor
                    net_drain = window["upkeep_per_second"] - charge
                    if net_drain > 0 and energy < net_drain * duration:
                        # A future loss of supply may exhaust the window. Existing
                        # fleets keep their already paid return reservation.
                        active_end = cursor + energy / net_drain
                        window["closes_at"] = active_end
                        energy = 0.0
                    else:
                        energy = min(cap, max(0.0, energy - net_drain * duration))
                    cursor = active_end
                if window["closes_at"] <= end:
                    project["window"] = None
            energy = min(cap, max(0.0, energy + charge * (end - cursor)))
            project["energy"] = round(energy, 6)

    def _mega_deadlines(self):
        return [p["megastructure"]["queue"]["ends_at"] for p in self.data["players"].values()
                if p.get("megastructure", {}).get("queue")]

    def _complete_megastructures(self, now):
        for player in self.data["players"].values():
            project = player.get("megastructure", {})
            queue = project.get("queue")
            if not queue or queue["ends_at"] > now:
                continue
            origin = self.data["planets"].get(project["origin_id"])
            if not origin or origin["owner_id"] != player["id"]:
                project["queue"] = None
                continue
            if queue["key"] == "dyson":
                project["dyson_stage"] = queue["level"]
            else:
                project["gate_level"] = 1
            project["queue"] = None
            self._report(player["id"], t("Ukończono megastrukturę"),
                         t("{0}: {1}.").format(origin["name"], t(queue["name"])))

    def _mega_requirements(self, player_id, planet, key):
        requirements = [("research", "dyson_design", 1), ("buildings", "shipyard", 8), ("buildings", "power_plant", 8)] if key == "dyson" else [
            ("research", "wormhole_theory", 1), ("buildings", "shipyard", 10), ("buildings", "lab", 12)]
        result = []
        for group, name, minimum in requirements:
            levels = planet["buildings"] if group == "buildings" else self._player(player_id)["research"]
            result.append({"group": group, "key": name, "name": self._specs(player_id, group)[name][0],
                           "level": minimum, "current": levels.get(name, 0), "met": levels.get(name, 0) >= minimum})
        if key == "wormhole":
            player = self._player(player_id)
            stage = player.get("megastructure", {}).get("dyson_stage", 0) if self._mega_origin_owned(player) else 0
            result.append({"group": "megastructures", "key": "dyson", "name": t("Sfera Dysona"),
                           "level": 4, "current": stage, "met": stage >= 4})
        return result

    def _mega_state(self, player_id, planet):
        player = self._player(player_id)
        project = player.get("megastructure", empty_project())
        profile = self._mega_profile(player)
        origin = self.data["planets"].get(project["origin_id"], {})
        result = copy.deepcopy(project)
        result.update(profile, origin_name=origin.get("name", ""),
                      window_seconds=WINDOW_SECONDS, stabilization_seconds=STABILIZE_SECONDS,
                      transit_seconds=TRANSIT_SECONDS, projects=[])
        effect = self._technology_effects(player_id)
        factor = 1 - effect.get("tunnel_efficiency", 0)
        result["opening_energy"] = math.ceil(OPEN_ENERGY * factor)
        result["upkeep_per_second"] = math.ceil(UPKEEP_PER_SECOND * factor)
        result["opening_required"] = math.ceil(result["opening_energy"] + max(0, result["upkeep_per_second"] - profile["charge_per_second"]) * (STABILIZE_SECONDS + WINDOW_SECONDS))
        result["suspended"] = bool(project["origin_id"]) and not self._mega_origin_owned(player)
        result["is_origin"] = not result["suspended"] and project["origin_id"] == planet["id"]
        if result.get("window"):
            target = self.data["planets"].get(result["window"]["target_id"], {})
            result["window"]["target_name"] = target.get("name", "") if target and self._known_planet(player_id, target) else t("Nieznany cel zwiadu")
        for key in ("dyson", "wormhole"):
            level = project["dyson_stage"] if key == "dyson" else project["gate_level"]
            maximum = 4 if key == "dyson" else 1
            name, values, base_seconds = STAGES[min(level, 3)] if key == "dyson" else GATE
            cost = dict(zip(RESOURCES, values))
            seconds = max(1, math.ceil(base_seconds / self.speed / (1 + effect.get("mega_speed", 0))))
            requirements = self._mega_requirements(player_id, planet, key)
            reason = ""
            if result["suspended"]:
                reason = t("Odzyskaj kolonię będącą centrum projektu.")
            elif level >= maximum:
                reason = t("Projekt ukończony.")
            elif project.get("queue"):
                reason = t("Budowa megastruktury już trwa.")
            elif project["origin_id"] and not result["is_origin"]:
                reason = t("Centrum projektu: {0}.").format(origin.get("name", ""))
            elif not all(r["met"] for r in requirements):
                reason = t("Nie spełniono wymagań projektu.")
            elif any(planet["resources"][r] < n for r, n in cost.items()):
                reason = t("Brakuje surowców.")
            result["projects"].append({"key": key, "name": t(name), "level": level,
                                      "max_level": maximum, "cost": cost, "seconds": seconds,
                                      "requirements": requirements, "enabled": not reason, "reason": reason})
        return result

    def _mega_action(self, player_id, planet, payload):
        player = self._player(player_id)
        project = player.setdefault("megastructure", empty_project())
        action = payload["type"]
        if project["origin_id"] and not self._mega_origin_owned(player):
            raise self.account_error_class(t("Odzyskaj kolonię będącą centrum projektu."), 409)
        if action == "megabuild":
            key = payload.get("key")
            entry = next((p for p in self._mega_state(player_id, planet)["projects"] if p["key"] == key), None)
            if entry is None or not entry["enabled"]:
                raise self.account_error_class(entry["reason"] if entry else t("Nieznany projekt."), 409)
            project["origin_id"] = planet["id"]
            for resource, amount in entry["cost"].items():
                planet["resources"][resource] -= amount
            name = STAGES[entry["level"]][0] if key == "dyson" else GATE[0]
            project["queue"] = {"id": "mega_" + secrets.token_hex(8), "key": key, "name": name,
                                "level": entry["level"] + 1, "paid_cost": dict(entry["cost"]),
                                "seconds": entry["seconds"], "started_at": self.now, "ends_at": self.now + entry["seconds"]}
            return t("Rozpoczęto budowę megastruktury.")
        if project["origin_id"] != planet["id"]:
            raise self.account_error_class(t("Wybierz kolonię będącą centrum projektu."), 409)
        if action == "megacancel":
            queue = project.get("queue")
            if not queue or payload.get("queue_id") != queue["id"] or queue["ends_at"] <= self.now:
                raise self.account_error_class(t("Ten projekt nie jest już aktywny."), 409)
            for resource, amount in queue["paid_cost"].items():
                planet["resources"][resource] = min(1000000000, planet["resources"][resource] + amount)
            project["queue"] = None
            if project["dyson_stage"] == 0:
                project["origin_id"] = ""
            return t("Anulowano budowę megastruktury. Zwrócono wpłacone surowce.")
        if action == "tunnel_close":
            project["window"] = None
            return t("Zamknięto tunel. Wysłane floty zachowują opłacony powrót.")
        if action != "tunnel_open":
            raise self.account_error_class(t("Nieznane polecenie."))
        if project["dyson_stage"] < 4 or project["gate_level"] < 1:
            raise self.account_error_class(t("Wymagana ukończona Sfera Dysona i zbudowany tunel."), 409)
        if project.get("window") and project["window"]["closes_at"] > self.now:
            raise self.account_error_class(t("Tunel jest już otwarty. Najpierw zamknij bieżące połączenie."), 409)
        target = payload.get("target_id")
        if not isinstance(target, str) or target not in self.data["planets"] or target == planet["id"]:
            raise self.account_error_class(t("Wybierz inną planetę docelową."))
        info = self._mega_state(player_id, planet)
        if project["energy"] < info["opening_required"]:
            raise self.account_error_class(t("Brakuje energii na otwarcie i pełne okno transportowe."), 409)
        project["energy"] -= info["opening_energy"]
        project["window"] = {"id": "tunnel_" + secrets.token_hex(8), "target_id": target,
                             "opened_at": self.now, "ready_at": self.now + STABILIZE_SECONDS,
                             "closes_at": self.now + STABILIZE_SECONDS + WINDOW_SECONDS,
                             "upkeep_per_second": info["upkeep_per_second"]}
        return t("Tunel stabilizuje się przez 60 s. Potem pozostanie otwarty przez 5 minut.")

    def _tunnel_quote(self, player_id, origin, target, ships, cargo, require_affordable=True):
        player = self._player(player_id)
        project = player.get("megastructure", {})
        window = project.get("window")
        if (not self._mega_origin_owned(player) or project.get("origin_id") != origin["id"] or project.get("dyson_stage", 0) < 4
                or project.get("gate_level", 0) < 1 or not window
                or window["target_id"] != target["id"] or not window["ready_at"] <= self.now < window["closes_at"]):
            raise self.account_error_class(t("Brak gotowego tunelu do wybranego celu."), 409)
        # Hull mass uses unmodified race specs. Combat/fuel bonuses never make a
        # fleet artificially lighter. Cargo also has a real transfer cost.
        race = self._race_id(player_id)
        try:
            from .races import RACES
        except ImportError:
            from races import RACES
        raw_specs = RACES[race]["ships"] if race else self._specs(player_id, "ships")
        mass = sum(raw_specs[key][5] * count / 10 for key, count in ships.items() if count) + sum(cargo.values()) / 1000
        factor = 1 - self._technology_effects(player_id).get("tunnel_efficiency", 0)
        one_way = math.ceil(mass * TRANSFER_PER_MASS * factor)
        reserved_return = math.ceil(one_way + RETURN_PULSE_ENERGY * factor)
        total = one_way + reserved_return
        profile = self._mega_profile(player)
        keep_alive = math.ceil(max(0, window["upkeep_per_second"] - profile["charge_per_second"]) * (window["closes_at"] - self.now))
        available = max(0, math.floor(project["energy"] - keep_alive))
        shortfall = max(0, total - available)
        if require_affordable and shortfall:
            raise self.account_error_class(t("Brakuje energii na transfer, podtrzymanie i rezerwę powrotu."), 409)
        return {"window_id": window["id"], "energy_cost": total, "return_reserved": reserved_return,
                "energy_shortfall": shortfall, "affordable": not shortfall, "seconds": TRANSIT_SECONDS,
                "closes_at": window["closes_at"], "mass": round(mass, 3)}
