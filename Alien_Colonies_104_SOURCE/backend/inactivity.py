"""Account-wide resource production pause after seven real days without play.

Only verified sign-in, successful player commands and an explicit foreground
input signal update activity. State reads, observers, billing jobs and simulation
events never do. Callers settle the world before recording a player's return, so
the paused interval cannot become retroactive income.
"""
from __future__ import annotations

import math

try:
    from .push_notifications import cancel_return_reminder
except ImportError:
    from push_notifications import cancel_return_reminder


INACTIVE_AFTER_SECONDS = 7 * 24 * 60 * 60
ACTIVITY_HEADER = "X-AC-Player-Active"


def _timestamp(value):
    return (float(value) if type(value) in (int, float) and math.isfinite(value)
            and value >= 0 else None)


class InactivityMixin:
    def _ensure_activity_policy(self, data=None):
        data = self.data if data is None else data
        # Older releases did not track reliable activity. Grant one persisted
        # seven-day grace period on migration, never another on container restart.
        started = _timestamp(data.get("activity_policy_started_at"))
        if started is None:
            started = self.now
            data["activity_policy_started_at"] = started
        for player in data["players"].values():
            if _timestamp(player.get("last_active_at")) is None:
                player["last_active_at"] = started
        data["activity_schema_version"] = 1

    def _production_cutoff(self, player_id):
        player = self.data["players"].get(player_id)
        if player is None:  # Empty planets and the Khar NPC have no human account.
            return float("inf")
        last_active = _timestamp(player.get("last_active_at"))
        if last_active is None:
            last_active = self.data.get("activity_policy_started_at", self.now)
        return last_active + INACTIVE_AFTER_SECONDS

    def _production_status(self, player_id):
        self._player(player_id)
        cutoff = self._production_cutoff(player_id)
        paused = self.now >= cutoff
        return {"paused": paused, "reason": "inactivity" if paused else "active",
                "inactive_after_seconds": INACTIVE_AFTER_SECONDS,
                "last_active_at": cutoff - INACTIVE_AFTER_SECONDS,
                "stops_at": cutoff}

    def _touch_player_activity(self, player_id):
        """Inside an existing transaction, after settling the old time interval."""
        player = self._player(player_id)
        player["last_active_at"] = self.now
        cancel_return_reminder(self, player_id)

    def mark_player_activity(self, player_id):
        with self.lock, self._atomic():
            self._touch_player_activity(player_id)

    @staticmethod
    def _explicit_activity_header(values):
        # No client clock or player ID is accepted. Duplicate headers do not
        # become an activity signal through proxy concatenation.
        return values == ["1"]

