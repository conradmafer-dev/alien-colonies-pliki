"""Deterministic local starting positions for pre-0.7.0 route/combat regressions.

Those scenarios intentionally test travel inside g1, not randomly costly jumps.
Only spawn selection is overridden. Production rates, AI, defenses, storage,
combat and reconnaissance use the real implementation. test_recon_defense_070
uses the original World and tests random placement across all six galaxies.
"""
from server.main import World

class LocalTestWorld(World):
    def _choose_start_planet(self, available):
        local = [p for p in available if self._galaxy_id(p) == "g1"] or available
        occupied = [p for p in self.data["planets"].values() if p["owner_type"] != "empty"]
        return max(local, key=lambda p: (min((self._distance(p, q) for q in occupied), default=0), -p["slot"]))
