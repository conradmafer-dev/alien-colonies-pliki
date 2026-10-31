"""Paid planning; free production lanes and authoritative timers stay unchanged.

Pending orders never reserve resources or have a completion deadline. Only the
head of each lane may start, after validating the current colony and catalog.
This module deliberately performs no network or billing calls during simulation.
"""
from __future__ import annotations

import math
import secrets
from collections import Counter

try:
    from .i18n import t
    from .production_timing import project_lane
    from .fleet_expansion import CAPITAL_ROLES
except ImportError:
    from i18n import t
    from production_timing import project_lane
    from fleet_expansion import CAPITAL_ROLES

GROUPS = {"build": "buildings", "ship": "ships", "defense": "defenses", "research": "research"}


def _finite_timestamp(value, default=0.0):
    return float(value) if type(value) in (int, float) and math.isfinite(value) and value >= 0 else default


class PlannedQueuesMixin:
    QUEUE_WAITING_LIMIT = 10

    def _queue_periods(self, player):
        subscription = player.get("subscription", {})
        if not isinstance(subscription, dict):
            return []
        periods = subscription.get("periods")
        if isinstance(periods, list):
            return sorted(((_finite_timestamp(period.get("starts_at")),
                            _finite_timestamp(period.get("expires_at")))
                           for period in periods if isinstance(period, dict)
                           and _finite_timestamp(period.get("expires_at")) > _finite_timestamp(period.get("starts_at"))),
                          key=lambda period: period[0])
        if subscription.get("enable_queue_planning") is not True:
            return []
        start = _finite_timestamp(subscription.get("starts_at"))
        end = _finite_timestamp(subscription.get("expires_at"))
        return [(start, end)] if end > start else []

    def _queue_entitlement(self, player):
        subscription = player.get("subscription", {})
        if not isinstance(subscription, dict):
            subscription = {}
        return {"queue_planning_active": any(start <= self.now < end for start, end in self._queue_periods(player)),
                "starts_at": _finite_timestamp(subscription.get("starts_at")),
                "expires_at": _finite_timestamp(subscription.get("expires_at")),
                "queue_waiting_limit": self.QUEUE_WAITING_LIMIT}

    @staticmethod
    def _planned_lane(order):
        lane = project_lane(order["kind"])
        return (lane, "" if lane == "research" else order["planet_id"])

    def _planned_heads(self, player):
        seen = set()
        for order in player.get("planned_orders", []):
            lane = self._planned_lane(order)
            if lane not in seen:
                seen.add(lane)
                yield order

    def _planned_lane_busy(self, player_id, planet, kind):
        lane = project_lane(kind)
        if lane == "research":
            return any(task["kind"] == "research" for owned in self.data["planets"].values()
                       if owned["owner_type"] == "player" and owned["owner_id"] == player_id for task in owned["queue"])
        return any(project_lane(task["kind"]) == lane for task in planet["queue"])

    def _planning_context(self, player_id, planet):
        player = self._player(player_id)
        pending = [order for order in player.get("planned_orders", [])
                   if order["kind"] == "research" or order["planet_id"] == planet["id"]]
        active = [task for owned in self.data["planets"].values() if owned["owner_id"] == player_id
                  for task in owned["queue"] if task["kind"] == "research" or owned["id"] == planet["id"]]
        return {"entitled": self._queue_entitlement(player)["queue_planning_active"],
                "lanes": Counter(project_lane(order["kind"]) for order in pending),
                "pending": Counter((order["kind"], order["key"]) for order in pending),
                "active": Counter((task["kind"], task["key"]) for task in active)}

    def _planning_permission(self, player_id, planet, group, entry, context=None, *, check_entitlement=True):
        """Client planning availability ignores busy lanes and current resources."""
        context = self._planning_context(player_id, planet) if context is None else context
        if check_entitlement and not context["entitled"]:
            return t("Planowanie kolejek wymaga aktywnej subskrypcji.")
        kind = {value: key for key, value in GROUPS.items()}[group]
        if context["lanes"][project_lane(kind)] >= self.QUEUE_WAITING_LIMIT:
            return t("Kolejka może zawierać najwyżej {0} oczekujących projektów.").format(self.QUEUE_WAITING_LIMIT)
        if any(not item["met"] for item in entry["requirements"]):
            return t("Najpierw spełnij wymagania projektu.")
        if group == "buildings" and entry.get("building_fields", {}).get("free", 0) < 1:
            return t("Brak wolnych slotów budowlanych na tej planecie.")
        if group in ("buildings", "research"):
            active = context["active"][(kind, entry["key"])]
            pending = context["pending"][(kind, entry["key"])]
            if entry["level"] + active + pending >= entry["max_level"]:
                return t("Osiągnięto maksymalny poziom projektu.")
        if group == "ships" and not self._race_id(player_id) and entry["key"] in ("interceptor", "siege", "freighter", *CAPITAL_ROLES):
            return t("Wybierz rasę imperium, aby odblokować zaawansowane okręty.")
        return ""

    def _planned_readiness(self, player_id, order):
        player = self._player(player_id)
        planet = self.data["planets"].get(order["planet_id"])
        if not planet or planet["owner_type"] != "player" or planet["owner_id"] != player_id:
            return None, None, "blocked", t("Planeta nie należy już do ciebie.")
        if _finite_timestamp(order.get("created_at")) > self.now:
            return planet, None, "waiting", t("Projekt oczekuje na swoją kolej.")
        if not self._queue_entitlement(player)["queue_planning_active"]:
            return planet, None, "paused_subscription", t("Planowanie kolejek wymaga aktywnej subskrypcji.")
        if self._planned_lane_busy(player_id, planet, order["kind"]):
            return planet, None, "waiting_lane", t("Projekt oczekuje na zakończenie poprzedniego projektu.")
        group = GROUPS[order["kind"]]
        entry = next(iter(self._catalog(player_id, planet, project_only=(group, order["key"]))[group]), None)
        if entry is None:
            return planet, None, "blocked", t("Nieznany projekt.")
        if not entry["enabled"] and entry["reason"] != t("Brakuje surowców."):
            status = "waiting_requirements" if any(not item["met"] for item in entry["requirements"]) else "blocked"
            return planet, entry, status, entry["reason"]
        cost = {key: amount * order["amount"] for key, amount in entry["cost"].items()}
        if any(planet["resources"][key] < amount for key, amount in cost.items()):
            if self.now >= self.data.get("economy85_from", 0):
                capacity = self.storage(planet)["capacity"]
                if any(amount > capacity[key] and planet["resources"][key] < amount
                       for key, amount in cost.items()):
                    return planet, entry, "blocked", t("Rozbuduj skarbiec: pojemność magazynu jest za mała.")
            return planet, entry, "waiting_resources", t("Brakuje surowców na całą partię.")
        return planet, entry, "ready", ""

    def _start_project(self, planet, kind, key, amount, entry, *, planned_order_id=None):
        """One authoritative start path shared by manual and planned orders."""
        cost = {resource: value * amount for resource, value in entry["cost"].items()}
        if any(planet["resources"][resource] < value for resource, value in cost.items()):
            raise self.planned_error_class(t("Brakuje surowców na całą partię."), 409)
        for resource, value in cost.items():
            planet["resources"][resource] -= value
        reduction = min(entry.get("batch_time_reduction_cap", 0), entry.get("batch_time_reduction_per_extra", 0) * (amount - 1))
        duration = max(1, math.ceil(entry["seconds"] * amount * (1 - reduction)))
        task = {"id": "q" + secrets.token_hex(8), "kind": kind, "key": key, "amount": amount,
                "level": entry["level"] + 1, "started_at": self.now, "paid_cost": dict(cost),
                "seconds": duration, "ends_at": self.now + duration,
                "facility_timing": dict(entry.get("facility_timing", {})),
                "construction_timing": dict(entry.get("construction_timing", {})),
                "crystal_refund": entry.get("crystal_refund", 0),
                "construction_refund": {resource: value * self._racial_research_level(planet["owner_id"], "recycling") // 20
                                        for resource, value in cost.items()} if kind in ("build", "ship", "defense") else {}}
        if planned_order_id is not None:
            task["planned_order_id"] = planned_order_id
        planet["queue"].append(task)
        return task

    def _start_planned_projects(self):
        for player_id, player in self.data["players"].items():
            if not player.get("planned_orders") or not self._queue_entitlement(player)["queue_planning_active"]:
                continue
            for order in list(self._planned_heads(player)):
                planet, entry, status, _ = self._planned_readiness(player_id, order)
                if status == "ready":
                    self._start_project(planet, order["kind"], order["key"], order["amount"], entry, planned_order_id=order["id"])
                    player["planned_orders"].remove(order)

    def _planning_wait_seconds(self, planet, cost, rates, *, at=None):
        """Forecast mining only when every missing resource can fit in storage.

        Delivered stock above capacity remains spendable. Historical intervals
        before the storage migration retain the old resource ceiling.
        """
        timestamp = self.now if at is None else at
        capacity = (self.storage(planet)["capacity"]
                    if timestamp >= self.data.get("economy85_from", 0)
                    else dict.fromkeys(cost, self.MAX_RESOURCE))
        wait = 0.0
        for resource, needed in cost.items():
            deficit = needed - planet["resources"][resource]
            if deficit <= 0:
                continue
            rate = rates.get(resource, 0)
            if rate <= 0 or needed > capacity[resource]:
                return None
            wait = max(wait, deficit * 3600 / rate)
        return wait

    def _planned_queue_deadlines(self, cursor, until):
        """Wake idle heads at their real affordability time, including offline play.

        Other existing completion/flight events interrupt this estimate and cause
        it to be recalculated with the changed stocks, facilities and production.
        Epoch boundaries prevent migration-era rates from being applied backwards.
        """
        deadlines = []
        epochs = [self.data.get(key, 0) for key in ("economy_slow_from", "planetary_from", "planet_traits_from",
                                                   "ogame_economy_from", "economy85_from")]
        future_epochs = [epoch for epoch in epochs if cursor < epoch <= until]
        for player_id, player in self.data["players"].items():
            if not player.get("planned_orders"):
                continue
            periods = self._queue_periods(player)
            deadlines.extend(start for start, end in periods if cursor < start <= until)
            current_end = max((end for start, end in periods if start <= cursor < end), default=None)
            if current_end is None:
                continue
            cutoff = self._production_cutoff(player_id)
            if cursor < cutoff <= until:
                # Re-evaluate at the exact stop, including a project that became
                # affordable precisely then, without forecasting paused income.
                deadlines.append(cutoff)
            for order in self._planned_heads(player):
                created = _finite_timestamp(order.get("created_at"))
                if cursor < created <= min(until, current_end):
                    deadlines.append(created)
                    continue
                planet, entry, status, _ = self._planned_readiness(player_id, order)
                if status != "waiting_resources":
                    continue
                rates = self.production(planet, traits_enabled=cursor >= epochs[2], terrain_enabled=cursor >= epochs[1],
                                        ogame_enabled=cursor >= epochs[3], economy85_enabled=cursor >= epochs[4], at=cursor)
                weight = 1 / self.ECONOMY_MULTIPLIER if cursor < epochs[0] else 1
                wait = self._planning_wait_seconds(planet,
                            {resource: unit_cost * order["amount"] for resource, unit_cost in entry["cost"].items()},
                            {resource: rate * weight for resource, rate in rates.items()}, at=cursor)
                deadlines.extend(future_epochs)
                if wait is None:
                    continue
                ready_at = cursor + wait + 0.000001
                if cursor < ready_at < current_end and ready_at <= min(until, cutoff):
                    deadlines.append(ready_at)
        return deadlines

    def _planned_action(self, player_id, planet, payload):
        player = self._player(player_id)
        orders = player.setdefault("planned_orders", [])
        action = payload["type"]
        if action == "plan_project":
            if not self._queue_entitlement(player)["queue_planning_active"]:
                raise self.planned_error_class(t("Planowanie kolejek wymaga aktywnej subskrypcji."), 403)
            kind, key = payload.get("kind"), payload.get("key")
            if not isinstance(kind, str) or kind not in GROUPS or not isinstance(key, str) or key not in self._specs(player_id, GROUPS[kind]):
                raise self.planned_error_class(t("Nieznany projekt."))
            amount = payload.get("amount", 1)
            if type(amount) is not int or not 1 <= amount <= (20 if kind in ("ship", "defense") else 1):
                raise self.planned_error_class(t("Nieprawidłowa liczba projektów."))
            order = {"id": "p" + secrets.token_hex(8), "kind": kind, "key": key, "amount": amount,
                     "planet_id": planet["id"], "created_at": self.now}
            lane = self._planned_lane(order)
            if sum(self._planned_lane(item) == lane for item in orders) >= self.QUEUE_WAITING_LIMIT:
                raise self.planned_error_class(t("Kolejka może zawierać najwyżej {0} oczekujących projektów.").format(self.QUEUE_WAITING_LIMIT), 409)
            if kind in ("build", "research"):
                group = GROUPS[kind]
                entry = next(iter(self._catalog(player_id, planet, project_only=(group, key))[group]), None)
                active = [task for owned in self.data["planets"].values()
                          if owned["owner_id"] == player_id and (kind == "research" or owned["id"] == planet["id"])
                          for task in owned["queue"] if task["kind"] == kind and task["key"] == key]
                pending_same = sum(item["kind"] == kind and item["key"] == key and self._planned_lane(item) == lane for item in orders)
                if entry is None or entry["level"] + len(active) + pending_same >= entry["max_level"]:
                    raise self.planned_error_class(t("Osiągnięto maksymalny poziom projektu."), 409)
            orders.append(order)
            self._start_planned_projects()
            return t("Dodano projekt do kolejki.")
        order_id = payload.get("order_id")
        order = next((item for item in orders if item["id"] == order_id), None)
        if not isinstance(order_id, str) or order is None:
            raise self.planned_error_class(t("Nie znaleziono oczekującego projektu."), 404)
        if action == "remove_planned_project":
            orders.remove(order)
            self._start_planned_projects()
            return t("Usunięto projekt z kolejki. Surowce nie były pobrane.")
        before_id = payload.get("before_order_id")
        before = next((item for item in orders if item["id"] == before_id), None) if before_id is not None else None
        if before_id is not None and (not isinstance(before_id, str) or before is None or self._planned_lane(before) != self._planned_lane(order)):
            raise self.planned_error_class(t("Możesz zmieniać kolejność tylko w tej samej kolejce."), 409)
        if before is not order:
            orders.remove(order)
            if before is None:
                orders.append(order)
            else:
                orders.insert(orders.index(before), order)
        self._start_planned_projects()
        return t("Zmieniono kolejność projektów.")

    def _public_planned_orders(self, player_id):
        player = self._player(player_id)
        heads = {order["id"] for order in self._planned_heads(player)}
        result = []
        for order in player.get("planned_orders", []):
            planet, entry, status, reason = self._planned_readiness(player_id, order)
            if order["id"] not in heads and status not in ("blocked", "paused_subscription"):
                status, reason = "waiting", t("Projekt oczekuje na swoją kolej.")
            group = GROUPS[order["kind"]]
            spec = self._specs(player_id, group).get(order["key"])
            item = {key: order[key] for key in ("id", "kind", "key", "amount", "planet_id", "created_at")}
            item.update(lane=project_lane(order["kind"]), name=t(spec[0]) if spec else order["key"],
                        planet_name=planet["name"] if planet else t("Utracona planeta"), status=status, reason=reason,
                        is_head=order["id"] in heads)
            if entry is not None:
                item["next_cost"] = {key: value * order["amount"] for key, value in entry["cost"].items()}
            result.append(item)
        return result

