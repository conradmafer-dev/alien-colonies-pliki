"""One-shot, operator-authorized 0.7.2 economy reset, with a verified backup.

Legacy operator tool only: the normal launcher no longer opts in (0.11.3).
No HTTP endpoint can invoke this historical whole-player-progress reset.
Accounts, salts/password hashes, recovery codes and chosen races survive.
The permanent marker belongs to the database, not the container or env vars.
Do not change BALANCE_RESET_ID in subsequent releases.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time

try:
    from .i18n import t
except ImportError:
    from i18n import t

BALANCE_RESET_ID = "slow-economy-072"


def verified_reset_backup(connection: sqlite3.Connection, database_path: str, *, reset_id: str = BALANCE_RESET_ID) -> Path | None:
    """Make a durable standalone pre-reset SQLite copy outside rolling retention.

    Any error is fatal to the reset. The original DB is never deleted/replaced.
    ':memory:' is only used by tests and deliberately has no disk backup.
    """
    if database_path == ":memory:":
        return None
    directory = Path(database_path).resolve().parent / "reset-backups"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    destination = directory / f"before-{reset_id}-{stamp}-{secrets.token_hex(6)}.sqlite3"
    temporary = destination.with_suffix(".sqlite3.part")
    handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(handle)
    try:
        backup = sqlite3.connect(str(temporary))
        try:
            connection.backup(backup)
            backup.commit()
            if backup.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] != 0:
                raise sqlite3.DatabaseError("Reset backup WAL checkpoint failed")
            if backup.execute("PRAGMA journal_mode=DELETE").fetchone()[0] != "delete":
                raise sqlite3.DatabaseError("Reset backup is not standalone")
            if backup.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise sqlite3.DatabaseError("Reset backup verification failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall() or backup.execute("PRAGMA foreign_key_check").fetchall():
                raise sqlite3.DatabaseError("Reset backup has invalid foreign keys")
            schema = "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            if connection.execute(schema).fetchall() != backup.execute(schema).fetchall():
                raise sqlite3.DatabaseError("Reset backup schema mismatch")
            # Verify every full table, including Google identities/proofs, chat,
            # moderation data and future account tables. sqlite_sequence is
            # included so copied AUTOINCREMENT state is verified as well.
            for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                quoted = '"' + table.replace('"', '""') + '"'
                columns = connection.execute(f"PRAGMA table_info({quoted})").fetchall()
                order = ",".join(str(index + 1) for index in range(len(columns)))
                original = connection.execute(f"SELECT * FROM {quoted} ORDER BY {order}").fetchall()
                copied = backup.execute(f"SELECT * FROM {quoted} ORDER BY {order}").fetchall()
                if original != copied:
                    raise sqlite3.DatabaseError(f"Reset backup mismatch: {table}")
        finally:
            backup.close()
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        if os.name != "nt":
            descriptor = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return destination
    finally:
        for suffix in ("", "-wal", "-shm", "-journal"):
            Path(str(temporary) + suffix).unlink(missing_ok=True)


class BalanceResetMixin:
    def _apply_balance_reset(self):
        """Reset progress exactly once under World's transaction and lock."""
        with self.lock:
            if self.data.get("balance_reset_id") == BALANCE_RESET_ID:
                return False
            accounts = self.db.execute("SELECT id FROM accounts ORDER BY id").fetchall()
            old_players = copy.deepcopy(self.data.get("players", {}))
            if {row[0] for row in accounts} != set(old_players):
                raise RuntimeError("Reset przerwany: konta i zapis świata są niespójne. Baza nie została wyzerowana.")
            for player_id, player in old_players.items():
                if not isinstance(player, dict) or not isinstance(player.get("name"), str):
                    raise RuntimeError("Reset przerwany: brak danych konta. Baza nie została wyzerowana.")
            # Use the current date for new protection/queues, never simulate the
            # pre-reset idle interval against the new starter resources.
            self.now = max(self.now, float(self.data.get("last_update", self.now)))
            fresh = self._new_world()
            empty = [p for p in fresh["planets"].values() if p["owner_type"] == "empty"]
            if len(empty) < len(accounts):
                raise RuntimeError("Reset przerwany: za mało planet dla istniejących kont.")
            backup = verified_reset_backup(self.db, self.db_path)
            with self._atomic():
                self.data.clear()
                self.data.update(fresh)
                for (player_id,) in accounts:
                    previous = old_players[player_id]
                    planet = self._choose_start_planet(empty)
                    empty.remove(planet)
                    self._initialize_starter_colony(player_id, previous["name"], planet, previous.get("race_id", ""))
                    self._report(player_id, t('Nowy początek'),
                                 t('Balans świata został zresetowany. Konto i wybrana rasa pozostały. Rozwijaj nowe imperium.'))
                self.db.execute("DELETE FROM sessions")
                self.data["balance_reset_id"] = BALANCE_RESET_ID
                self.data["balance_reset_at"] = self.now
                self.data["balance_reset_accounts"] = len(accounts)
                self.data["balance_reset_backup"] = backup.name if backup else "memory-only"
                self._save(commit=False)
            print(f"Alien Colonies 0.7.2: jednorazowy reset postępów {len(accounts)} kont; "
                  f"konta zachowane; kopia: {backup if backup else 'test in-memory'}", flush=True)
            return True
