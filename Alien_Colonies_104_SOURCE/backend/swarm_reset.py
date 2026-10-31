"""One-time NPC-only reset explicitly shipped with the 0.11.3 plague update.

The caller takes a verified permanent backup BEFORE opening the world transaction.
The marker lives in SQLite's snapshot, not in a container or an environment flag.
There is deliberately no HTTP reset endpoint and no player progression reset.
"""
from __future__ import annotations

import copy

try:
    from . import swarm
    from .alliance_operations import ACTIVE
    from .i18n import t
except ImportError:
    import swarm
    from alliance_operations import ACTIVE
    from i18n import t

RESET_TITLE = "Nowy początek Roju"
RESET_TEXT = "Stare kolonie i floty Roju zostały zresetowane. W każdej dostępnej galaktyce pozostało jedno małe gniazdo bez zapasów i floty. Rój stawia teraz na kolonizację, nie na twierdze. Twoje kolonie, badania, statki i zdobyte Kryształy Roju pozostają bez zmian. Wyślij nowy zwiad, aby poznać aktualny stan gniazd."
RETURN_TITLE = "Wyprawa zawrócona po resecie Roju"
RETURN_TEXT = "Cel wyprawy zmienił się podczas jednorazowego resetu Roju. Twoja flota wraca bez walki, zachowując statki i ładunek."


class SwarmResetMixin:
    def _apply_swarm_reset(self, backup=None):
        """Mutate only under World's atomic transaction; fail closed otherwise."""
        if self.data.get("swarm_reset_id") == swarm.RESET_ID:
            return False
        if not self._atomic_depth:
            raise RuntimeError("Swarm reset requires the world transaction")
        if self.db_path != ":memory:" and backup is None:
            raise RuntimeError("Swarm reset requires a verified pre-reset backup")
        planets = self.data["planets"]
        old_ids = {p["id"] for p in planets.values() if p.get("owner_id") == swarm.OWNER_ID}
        old_hives = {p["id"] for p in planets.values() if p.get("owner_id") == swarm.OWNER_ID
                     and p.get("swarm_kind") == "hive"}
        npc_fleets = [fid for fid, f in self.data["fleets"].items() if f["owner_id"] == swarm.OWNER_ID]
        for fid in npc_fleets:
            del self.data["fleets"][fid]
        for pid in old_ids:
            p = planets[pid]
            fresh = self._planet(pid, p["name"], p["system_id"], p["slot"])
            # Reset occupation and economy, never reroll a planet's finite surface
            # or rare trait. Keep identity for existing routes and scout reports.
            for key in ("galaxy_id", "environment", "rare_trait"):
                if key in p:
                    fresh[key] = copy.deepcopy(p[key])
            p.clear()
            p.update(fresh)
        reserved = {f["target_id"] for f in self.data["fleets"].values()
                    if f["mission"] == "colonize" and f["status"] == "outbound"}
        seeded = []
        galaxies = sorted(self._eligible_swarm_galaxies(),
                          key=lambda g: int(g[1:]) if g.startswith("g") and g[1:].isdigit() else 999)
        for galaxy in galaxies:
            candidates = [p for p in planets.values() if p["owner_type"] == "empty"
                          and p["id"] not in reserved and self._galaxy_id(p) == galaxy]
            if not candidates:
                continue  # A galaxy filled by players is never taken from them.
            preferred = f"s{15 + 30 * (int(galaxy[1:]) - 1)}p2" if galaxy[1:].isdigit() else ""
            p = min(candidates, key=lambda q: (q["id"] not in old_hives,
                        q["id"] != preferred, q["id"] not in old_ids, q["id"]))
            swarm.seed(p, self.now, hive=True)
            seeded.append(p["id"])
        changed = old_ids | set(seeded)
        returning_ids = {f["id"] for f in self.data["fleets"].values()
                         if f["owner_id"] in self.data["players"] and f["target_id"] in changed
                         and f["status"] != "returning" and f["mission"] in ("attack", "alliance_attack")}
        cancelled_ops = 0
        # Coalition fleets use their normal cancellation/return path too.
        for op in self.data.get("alliance_operations", {}).values():
            if op.get("target", {}).get("id") in changed and op.get("status") in ACTIVE:
                # _operation_cancel checks the authoritative ACTIVE status set.
                before = op["status"]
                self._operation_cancel(op)
                if before != op["status"]:
                    op["cancel_reason"] = "swarm_reset"
                    cancelled_ops += 1
        for f in list(self.data["fleets"].values()):
            if (f["owner_id"] in self.data["players"] and f["target_id"] in changed
                    and f["status"] != "returning"
                    and f["mission"] in ("attack", "alliance_attack")):
                self._operation_return(f, early=True)
        for fid in returning_ids:
            if fid in self.data["fleets"]:
                self._report(self.data["fleets"][fid]["owner_id"], t(RETURN_TITLE), t(RETURN_TEXT))
        for player_id, player in self.data["players"].items():
            for field in ("scout_intel", "planet_intel"):
                records = player.get(field, {})
                for pid in changed:
                    records.pop(pid, None)
            # Remove only reset targets from current system intel. Knowledge of
            # other planets and old reports is not erased or relabelled as fresh.
            for record in player.get("system_intel", {}).values():
                record["planets"] = [p for p in record.get("planets", []) if p.get("id") not in changed]
            # Trait discovery remains permanent. Its physical identity becomes
            # public reset knowledge, without revealing unobserved stock/ships.
            for pid in changed & set(player.get("trait_intel", {})):
                memory = player["trait_intel"][pid]
                memory["identity"] = self._planet_identity(planets[pid], trait_known=True, basic=True)
                memory["observed_at"] = self.now
            self._report(player_id, t(RESET_TITLE), t(RESET_TEXT), "swarm/colony")
        alien = self.data["alien"]
        for key in list(alien):
            if key.startswith("swarm_") or key == "next_expansion_at":
                del alien[key]
        alien.update(next_expansion_at=self.now + 120,
                     swarm_next_raid_at=self.now + swarm.RAID_INTERVAL_SECONDS,
                     swarm_next_colonization_by_galaxy={g: self.now + swarm.COLONY_MATURITY_SECONDS for g in galaxies},
                     swarm_activated_galaxies={g: {"activated_at": self.now} for g in galaxies})
        for pid in seeded:
            alien["swarm_activated_galaxies"][self._galaxy_id(planets[pid])].update(
                seeded_at=self.now, planet_id=pid)
        self.data.update(swarm_reset_id=swarm.RESET_ID, swarm_reset_at=self.now,
                         swarm_reset_backup=backup.name if backup else "memory-only",
                         swarm_reset_summary={"old_colonies": len(old_ids), "removed_npc_fleets": len(npc_fleets),
                            "seeded_planets": seeded, "returned_player_fleets": len(returning_ids),
                            "cancelled_alliance_operations": cancelled_ops})
        return True
