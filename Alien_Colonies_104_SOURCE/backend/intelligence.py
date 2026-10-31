"""Per-player, arrival-time reconnaissance snapshots. No live enemy telemetry.

Only a completed scout updates knowledge. Map, mission preview and report read
all reuse immutable observations. Reading them never advances AI or observation
age and old reports cannot overwrite a newer snapshot.
"""
from __future__ import annotations
import copy

try:
    from . import swarm, defenses
    from .i18n import t, public_report
    from . import report_kinds
except ImportError:
    import swarm, defenses
    from i18n import t, public_report
    import report_kinds

ACTIVITIES = {
    "stockpiling": "Gromadzi zasoby",
    "rebuilding": "Odbudowuje obronę",
    "fortifying": "Umacnia planetę",
    "developing": "Rozbudowuje kolonię",
    "building_fleet": "Rozbudowuje flotę",
    "preparing_expansion": "Przygotowuje ekspansję",
    "preparing_raid": "Przygotowuje najazd",
    "expanding": "Kolonizuje nowe światy",
    "raiding": "Prowadzi najazd",
    "returning": "Flota wraca do gniazda",
}


class IntelligenceMixin:
    def _swarm_activity_at(self, planet):
        # Travelling fleets are actual decisions, never predictions about a target.
        missions = [f for f in self.data["fleets"].values()
                    if f["owner_id"] == swarm.OWNER_ID and f["origin_id"] == planet["id"]]
        if any(f["status"] == "outbound" and f["mission"] == "attack" for f in missions):
            return "raiding"
        if any(f["status"] == "outbound" and f["mission"] == "colonize" for f in missions):
            return "expanding"
        if planet.get("queue"):
            planned = planet.get("swarm_activity", "")
            if planned in ACTIVITIES:
                return planned
            return {"build": "developing", "defense": "fortifying"}.get(planet["queue"][0]["kind"], "building_fleet")
        if any(f["status"] == "returning" for f in missions):
            return "returning"
        planned = planet.get("swarm_activity", "stockpiling")
        return planned if planned in ACTIVITIES else "stockpiling"

    def _capture_swarm_intel(self, player_id, planet):
        if planet["owner_id"] != swarm.OWNER_ID or player_id not in self.data["players"]:
            return None
        keys = ("id", "name", "owner_type", "owner_id", "galaxy_id", "system_id", "slot",
                "buildings", "resources", "ships", "defenses", "swarm_kind", "swarm_crystals",
                "swarm_loot_sealed", "swarm_established_at")
        snapshot = {key: copy.deepcopy(planet[key]) for key in keys if key in planet}
        snapshot.update(intel_schema=1, scouted_at=self.now,
                        activity_key=self._swarm_activity_at(planet),
                        crystal_regen_seconds=swarm.CRYSTAL_REGEN_SECONDS)
        player = self.data["players"][player_id]
        player.setdefault("scout_intel", {})[planet["id"]] = copy.deepcopy(snapshot)
        return snapshot

    def _render_swarm_intel(self, snapshot):
        at = float(snapshot["scouted_at"])
        result = swarm.public_planet(snapshot, at)
        result.update(scouted_at=at, has_scout=True,
                      swarm_activity=t(ACTIVITIES.get(snapshot.get("activity_key", ""), ACTIVITIES["stockpiling"])),
                      swarm_activity_key=snapshot.get("activity_key", "stockpiling"),
                      resources={k: int(v) for k, v in snapshot.get("resources", {}).items()})
        result["swarm_crystals_regen_seconds"] = snapshot.get("crystal_regen_seconds", swarm.CRYSTAL_REGEN_SECONDS)
        # Never show a live countdown computed from an old observation.
        result.pop("swarm_crystals_next_at", None)
        result["swarm_units"] = [{"key": key, "name": t(swarm.SHIPS[key][0]), "count": count,
                                  "art_key": "swarm/" + key}
                                 for key, count in snapshot.get("ships", {}).items() if key in swarm.SHIPS and count > 0]
        result["swarm_defenses"] = [{"key": key, "name": t(spec[0]), "count": snapshot.get("defenses", {}).get(key, 0),
                                     "art_key": defenses.ART[key]}
                                    for key, spec in defenses.specs_for("swarm").items()]
        return result

    def _public_swarm_intel(self, player_id, planet):
        # Identity/appearance only until this player has actually observed the hive.
        result = {"race_id": "swarm", "race_name": t("Rój Khar"),
                  "colony_art": "swarm/colony", "planet_art": "swarm/planet", "has_scout": False}
        snapshot = self.data["players"][player_id].get("scout_intel", {}).get(planet["id"])
        if snapshot and snapshot.get("owner_id") == swarm.OWNER_ID and snapshot.get("intel_schema") == 1:
            result.update(self._render_swarm_intel(snapshot))
        return result

    def _public_intel_report(self, report):
        result = public_report(report)
        # Classify original Polish titles and snapshots, before localization.
        result["kind"] = report_kinds.kind(report)
        replay = result.pop("battle_replay", None)
        if replay:
            result["battle_replay_available"] = True
        planet_snapshot = result.pop("planet_snapshot", None)
        if planet_snapshot:
            result["planet_scout"] = self._render_planet_scout(planet_snapshot)
        system_snapshot = result.pop("system_snapshot", None)
        if system_snapshot:
            result["system_scout"] = self._render_system_scout(system_snapshot)
        snapshot = result.pop("intel_snapshot", None)
        if snapshot and snapshot.get("intel_schema") == 1:
            result["scout"] = self._render_swarm_intel(snapshot)
        return result
