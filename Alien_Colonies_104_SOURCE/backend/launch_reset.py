"""One-time, operator-authorized public-launch reset of all player accounts.

The permanent marker belongs to the SQLite snapshot. Never change this ID for
routine releases. There is no HTTP reset endpoint and no payment-provider call.
A verified, standalone database backup is mandatory before a disk-backed reset.
"""
from __future__ import annotations

import copy

try:
    from .balance_reset import verified_reset_backup
except ImportError:
    from balance_reset import verified_reset_backup


LAUNCH_RESET_ID = "new-beginning-20261019"

# Account foreign keys cascade except sessions, which must be removed first.
# Keep this check explicit: a future table must not accidentally retain private
# data when changing the account schema or a cascading relationship.
ACCOUNT_TABLES = (
    "accounts", "sessions", "google_accounts", "google_sessions", "email_accounts", "email_sessions",
    "account_recovery", "chat_messages", "chat_reads", "chat_blocks",
    "chat_reports", "chat_mutes", "chat_visibility",
)


class LaunchResetMixin:
    def _apply_launch_reset(self):
        """Delete the old world once, atomically with all authentication data."""
        with self.lock:
            if self.data.get("launch_reset_id") == LAUNCH_RESET_ID:
                return False
            if self._atomic_depth or self.db.in_transaction:
                raise RuntimeError("Launch reset backup requires a committed database")
            if self.db.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise RuntimeError("Launch reset requires enabled foreign keys")
            summary = {
                "removed_accounts": self.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
                "removed_players": len(self.data.get("players", {})),
                "removed_fleets": len(self.data.get("fleets", {})),
                "removed_swarm_colonies": sum(p.get("owner_id") == "khar"
                    for p in self.data.get("planets", {}).values()),
                "removed_chat_messages": self.db.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0],
                "removed_active_queue_entitlements": sum(
                    self._queue_entitlement(p)["queue_planning_active"]
                    for p in self.data.get("players", {}).values()),
            }
            # A failed backup must leave accounts, sessions and world untouched.
            backup = verified_reset_backup(self.db, self.db_path, reset_id=LAUNCH_RESET_ID)
            fresh = self._new_world()
            # The bulletin belongs to the server administration, not to any empire.
            # Preserve the newest published message and the editor draft/revision.
            bulletin = self.data.get("login_announcement")
            if isinstance(bulletin, dict):
                fresh["login_announcement"] = copy.deepcopy(bulletin)
            with self._atomic():
                self.db.execute("DELETE FROM sessions")
                self.db.execute("DELETE FROM accounts")
                for table in ACCOUNT_TABLES:
                    if self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]:
                        raise RuntimeError(f"Launch reset left account data in {table}")
                if self.db.execute("PRAGMA foreign_key_check").fetchall():
                    raise RuntimeError("Launch reset left invalid foreign keys")
                self.data.clear()
                self.data.update(fresh)
                self.data.update(launch_reset_id=LAUNCH_RESET_ID,
                                 launch_reset_at=self.now,
                                 launch_reset_backup=backup.name if backup else "memory-only",
                                 launch_reset_summary=summary)
                # _atomic persists both the new snapshot and SQL deletions in
                # one transaction and restores RAM if any write/commit fails.
            print("Alien Colonies: public-launch reset committed; "
                  f"removed accounts: {summary['removed_accounts']}; "
                  f"active queue entitlements: {summary['removed_active_queue_entitlements']}; "
                  f"backup: {backup if backup else 'test in-memory'}", flush=True)
            return True
