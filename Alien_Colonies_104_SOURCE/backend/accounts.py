"""Account lifecycle helpers for World, with no credentials in world snapshots.

World supplies its lock, _atomic transaction, GameError class and existing password
and session helpers. Every check and mutation occurs inside the same transaction.
"""
from __future__ import annotations

try:
    from .i18n import t
except ImportError:  # Flat Railway deployment.
    from i18n import t

import hashlib
import hmac
import json
import math
import secrets
import time


UNUSED_IDLE_SECONDS = 48 * 60 * 60
UNUSED_PREVIEW_SECONDS = 15 * 60
UNUSED_CONFIRMATION = "DELETE UNUSED ACCOUNTS"


def unused_account_reason(data, player_id, at, *, idle_seconds=UNUSED_IDLE_SECONDS):
    """Fail closed: zero ranking points alone never proves an unused empire.

    Return None only for an unchanged starter colony with no recorded development
    and at least the requested real idle interval (minimum 48 hours).
    This is read-only; operators may choose a stricter interval.
    """
    if type(idle_seconds) is not int or idle_seconds < UNUSED_IDLE_SECONDS:
        raise ValueError("Cleanup inactivity must be at least 48 hours.")
    player = data["players"].get(player_id)
    if not isinstance(player, dict) or player.get("id") != player_id:
        return "unknown_player"
    last = player.get("last_active_at")
    if (type(last) not in (int, float) or not math.isfinite(last)
            or not 0 <= last <= at):
        return "unknown_activity"
    if at - last < idle_seconds:
        return "recent_activity"
    review = player.get("review_invitation")
    if (not isinstance(review, dict)
            or type(review.get("completed_builds")) is not int
            or review["completed_builds"] != 0):
        return "completed_or_unknown_builds"
    research = player.get("research")
    if not isinstance(research, dict) or not research or any(type(v) is not int or v != 0 for v in research.values()):
        return "research"
    owned = [p for p in data["planets"].values() if p.get("owner_id") == player_id]
    if (len(owned) != 1 or owned[0].get("id") != player.get("home_id")
            or owned[0].get("owner_type") != "player"):
        return "colonies"
    planet = owned[0]
    for group in ("buildings", "ships", "defenses"):
        values = planet.get(group)
        if (not isinstance(values, dict) or (group != "defenses" and not values)
                or any(type(v) is not int or v != 0 for v in values.values())):
            return group
    if planet.get("queue") != [] or player.get("planned_orders") != []:
        return "queued_orders"
    if any(f.get("owner_id") == player_id for f in data["fleets"].values()):
        return "flying_fleets"
    race = player.get("race_id")
    nodes = player.get("skill_nodes")
    if (race not in ("", "zetans", "automatons", "symbionts")
            or not isinstance(nodes, list)
            or any(node != race + "_root" or not race for node in nodes)
            or player.get("swarm_crystals") != 0):
        return "skills_or_crystals"
    guide = player.get("onboarding", {})
    if not isinstance(guide, dict) or not isinstance(guide.get("completed", {}), dict) or any(guide.get("completed", {}).values()):
        return "past_progress"
    if (player.get("subscription") or player.get("alliance_id")
            or player.get("alliance_apply_after")
            or data.get("alliance_operation_requests", {}).get(player_id)):
        return "subscription_or_alliance"
    if any(player.get(key) for key in ("scout_intel", "system_intel", "planet_intel", "fleet_growth_credits")):
        return "past_exploration"
    mega = player.get("megastructure")
    if (not isinstance(mega, dict) or mega != {"origin_id": "", "dyson_stage": 0,
            "gate_level": 0, "energy": 0.0, "queue": None, "window": None}):
        return "megastructure"
    requests = player.get("requests")
    if not isinstance(requests, dict):
        return "unknown_commands"
    for record in requests.values():
        try:
            command = json.loads(record["fingerprint"])
            if command.get("type") not in ("choose_race", "skip_onboarding", "resume_onboarding", "subscription_prompt"):
                return "past_commands"
        except (KeyError, TypeError, ValueError, AttributeError):
            return "unknown_commands"
    return None


class AccountManagementMixin:
    def account_rename(self, token, name, planet_id=None):
        """Rename a public empire and its login key in one existing transaction."""
        name, _ = self._credentials(name, "name-validation-only")
        with self.lock, self._atomic():
            player_id = self.authenticate(token)
            player = self._player(player_id)
            existing = self.db.execute(
                "SELECT id FROM accounts WHERE name_key=?", (name.casefold(),)).fetchone()
            if existing and existing[0] != player_id:
                raise self.account_error_class(t('Ta nazwa jest już zajęta.'), 409)
            # The selected colony is validated before changing either name.
            self._state_planet_selection(player_id, planet_id)
            self.db.execute("UPDATE accounts SET name_key=? WHERE id=?",
                            (name.casefold(), player_id))
            player["name"] = name
            self._touch_player_activity(player_id)
            self._save(commit=False)
            return {"ok": True, "name": name, "state": self.state(player_id, planet_id),
                    "message": t('Zmieniono nazwę imperium.')}

    def _init_account_management(self):
        # A separate table preserves the original four-column accounts schema.
        self.db.execute("""CREATE TABLE IF NOT EXISTS account_recovery (
            player_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
            code_hash TEXT NOT NULL
        )""")

    @staticmethod
    def _recovery_digest(code):
        if not isinstance(code, str) or len(code) > 128:
            return None
        normalized = code.strip().upper().replace("-", "").replace(" ", "")
        if (not normalized.startswith("AC") or len(normalized) != 50
                or any(c not in "0123456789ABCDEF" for c in normalized[2:])):
            return None
        return hashlib.sha256(("alien-colonies-recovery-v1:" + normalized).encode("ascii")).hexdigest()

    def account_status(self, player_id):
        with self.lock:
            self._player(player_id)
            exists = self.db.execute(
                "SELECT 1 FROM account_recovery WHERE player_id=?", (player_id,)).fetchone()
            result = {"recovery_code_enabled": bool(exists)}
            linked = self.db.execute("SELECT 1 FROM google_accounts WHERE player_id=?", (player_id,)).fetchone()
            if linked:
                row = self.db.execute("SELECT password_hash FROM accounts WHERE id=?", (player_id,)).fetchone()
                result.update(google_linked=True, password_login_enabled=bool(row and row[0]))
            email_linked = self.db.execute("SELECT 1 FROM email_accounts WHERE player_id=?", (player_id,)).fetchone()
            if email_linked:
                row = self.db.execute("SELECT password_hash FROM accounts WHERE id=?", (player_id,)).fetchone()
                result.update(email_linked=True, password_login_enabled=bool(row and row[0]))
            return result

    def _reauth_account(self, token, password):
        player_id = self.authenticate(token)
        row = self.db.execute(
            "SELECT salt,password_hash FROM accounts WHERE id=?", (player_id,)).fetchone()
        if row and not row[1]:
            recently_verified = self._google_recent_session(token, player_id) or self._email_recent_session(token, player_id)
            if password not in (None, "") or not recently_verified:
                if self.db.execute("SELECT 1 FROM email_accounts WHERE player_id=?", (player_id,)).fetchone():
                    raise self.account_error_class(t('Zaloguj się ponownie e-mailem, aby potwierdzić tę zmianę.'), 403)
                raise self.account_error_class(t('Zaloguj się ponownie przez Google, aby potwierdzić tę zmianę.'), 403)
            self._player(player_id)
            return player_id
        if (not row or not isinstance(password, str) or not 8 <= len(password) <= 128
                or not hmac.compare_digest(self._password_hash(password, row[0]), row[1])):
            raise self.account_error_class(t('Nieprawidłowe obecne hasło.'), 403)
        self._player(player_id)
        return player_id

    def account_recovery_code(self, token, password):
        with self.lock, self._atomic():
            player_id = self._reauth_account(token, password)
            secret = secrets.token_hex(24).upper()
            code = "AC-" + "-".join(secret[i:i + 8] for i in range(0, len(secret), 8))
            self.db.execute("""INSERT INTO account_recovery(player_id,code_hash) VALUES(?,?)
                ON CONFLICT(player_id) DO UPDATE SET code_hash=excluded.code_hash""",
                (player_id, self._recovery_digest(code)))
            self._touch_player_activity(player_id)
            self._save(commit=False)
            return {"ok": True, "recovery_code": code,
                    "message": t('Zapisz kod w bezpiecznym miejscu. Poprzedni kod przestał działać; ten zobaczysz tylko teraz.')}

    def _replace_account_password(self, player_id, new_password):
        salt = secrets.token_hex(16)
        password_hash = self._password_hash(new_password, salt)
        self.db.execute("UPDATE accounts SET salt=?,password_hash=? WHERE id=?",
                        (salt, password_hash, player_id))
        self.db.execute("DELETE FROM sessions WHERE player_id=?", (player_id,))
        self.db.execute("DELETE FROM account_recovery WHERE player_id=?", (player_id,))
        return self._session(player_id)

    def recover_account(self, name, recovery_code, new_password):
        # Validating the new password before any mutation also protects existing
        # passwords, sessions and the single-use code from an invalid request.
        name, new_password = self._credentials(name, new_password)
        digest = self._recovery_digest(recovery_code)
        with self.lock, self._atomic():
            row = self.db.execute("""SELECT a.id,r.code_hash FROM accounts a
                JOIN account_recovery r ON r.player_id=a.id WHERE a.name_key=?""",
                (name.casefold(),)).fetchone()
            matches = hmac.compare_digest(digest or ("0" * 64), row[1] if row else ("f" * 64))
            if not digest or not row or not matches:
                raise self.account_error_class(t('Nieprawidłowa nazwa lub kod odzyskiwania.'), 401)
            player_id = row[0]
            self._player(player_id)
            token = self._replace_account_password(player_id, new_password)
            self._save(commit=False)
            return {"ok": True, "token": token, "state": self.state(player_id),
                    "message": t('Odzyskano konto. Pozostałe sesje i użyty kod wygasły. W ustawieniach utwórz nowy kod.')}

    def account_password(self, token, password, new_password):
        with self.lock, self._atomic():
            player_id = self._reauth_account(token, password)
            _, new_password = self._credentials(self._player(player_id)["name"], new_password)
            new_token = self._replace_account_password(player_id, new_password)
            self._save(commit=False)
            return {"ok": True, "token": new_token, "state": self.state(player_id),
                    "message": t('Hasło zmienione. Pozostałe sesje i kod odzyskiwania wygasły. Utwórz nowy kod.')}

    def account_logout_others(self, token, password):
        with self.lock, self._atomic():
            player_id = self._reauth_account(token, password)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            self.db.execute("DELETE FROM sessions WHERE player_id=? AND token_hash<>?",
                            (player_id, token_hash))
            self._touch_player_activity(player_id)
            self._save(commit=False)
            return {"ok": True, "message": t('Wylogowano pozostałe urządzenia.')}

    def account_delete(self, token, password, confirmation):
        with self.lock, self._atomic():
            player_id = self._reauth_account(token, password)
            if confirmation not in ("DELETE ACCOUNT", "USUŃ KONTO"):
                raise self.account_error_class(t('Wpisz dokładnie {0}, aby potwierdzić usunięcie.').format('DELETE ACCOUNT'), 400)
            self._delete_account_data(player_id)
            self._save(commit=False)
            return {"ok": True, "deleted": True,
                    "message": t('Konto i jego imperium zostały usunięte z aktywnego świata.')}

    def _delete_account_data(self, player_id):
        """Shared deletion path; caller must hold the world transaction/lock."""
        self._alliance_account_delete(player_id)
        self.data.get("alliance_operation_requests", {}).pop(player_id, None)
        for planet_id, planet in list(self.data["planets"].items()):
            if planet["owner_id"] == player_id:
                # Keep the galaxy's physical location, discard all private
                # colony content, including newer racial/Swarm-specific keys.
                self.data["planets"][planet_id] = self._planet(
                    planet_id, planet["name"], planet["system_id"], planet["slot"])
                self.data["planets"][planet_id]["galaxy_id"] = planet["galaxy_id"]
                if "environment" in planet:
                    self.data["planets"][planet_id]["environment"] = dict(planet["environment"])
                if "rare_trait" in planet:
                    self.data["planets"][planet_id]["rare_trait"] = planet["rare_trait"]
        for fleet_id, fleet in list(self.data["fleets"].items()):
            if fleet["owner_id"] == player_id:
                del self.data["fleets"][fleet_id]
        # Other fleets remain the same real flights, with the same cargo and
        # deadlines. Existing settlement rules cancel attacks on empty targets
        # and allow scouts/colonizers to observe the newly free planet.
        self.data["players"].pop(player_id)
        self.db.execute("DELETE FROM sessions WHERE player_id=?", (player_id,))
        self.db.execute("DELETE FROM account_recovery WHERE player_id=?", (player_id,))
        self.db.execute("DELETE FROM chat_reads WHERE channel=?", (player_id,))
        self.db.execute("DELETE FROM accounts WHERE id=?", (player_id,))

    def _unused_account_reason(self, player_id, at, *, idle_seconds=UNUSED_IDLE_SECONDS):
        reason = unused_account_reason(self.data, player_id, at, idle_seconds=idle_seconds)
        if reason:
            return reason
        seen = self._state_poll_presence.get(player_id)
        if type(seen) in (int, float) and 0 <= time.monotonic() - seen <= 60:
            return "currently_online"
        if self.db.execute("SELECT 1 FROM chat_messages WHERE sender=? LIMIT 1", (player_id,)).fetchone():
            return "player_communications"
        return None

    def unused_accounts_preview(self, *, at=None, idle_seconds=UNUSED_IDLE_SECONDS):
        """Admin-only read: keep a short-lived, exact selection in server memory."""
        if type(idle_seconds) is not int or idle_seconds < UNUSED_IDLE_SECONDS:
            raise ValueError("Cleanup inactivity must be at least 48 hours.")
        at = time.time() if at is None else float(at)
        with self.lock:
            accounts = {row[0] for row in self.db.execute("SELECT id FROM accounts")}
            if accounts != set(self.data["players"]):
                raise self.account_error_class("Account/world mismatch; cleanup refused.", 409)
            candidates = []
            for pid in sorted(accounts):
                if self._unused_account_reason(pid, at, idle_seconds=idle_seconds) is None:
                    p = self.data["players"][pid]
                    candidates.append({"id": pid, "name": p["name"], "home_id": p["home_id"],
                                       "last_active_at": p["last_active_at"]})
            plans = {key: value for key, value in getattr(self, "_unused_previews", {}).items()
                     if value["expires_at"] > at}
            while len(plans) >= 8:
                plans.pop(next(iter(plans)))
            preview_id = secrets.token_urlsafe(24)
            plans[preview_id] = {"expires_at": at + UNUSED_PREVIEW_SECONDS,
                                 "idle_seconds": idle_seconds,
                                 "candidates": candidates}
            self._unused_previews = plans
            # Public response has no shared references to the guarded selection.
            return {"ok": True, "preview_id": preview_id, "as_of": at,
                    "expires_at": at + UNUSED_PREVIEW_SECONDS,
                    "idle_seconds": idle_seconds, "count": len(candidates),
                    "candidates": [dict(p) for p in candidates]}

    def unused_accounts_delete(self, payload, *, at=None, operation_id=None):
        """Explicit admin operation; normal startup, timers and previews never call it.

        An optional operator-only operation ID is committed with the deletion,
        making a separately invoked maintenance command safe to retry.
        """
        at = time.time() if at is None else float(at)
        if operation_id is not None and (not isinstance(operation_id, str)
                or not 1 <= len(operation_id) <= 80
                or any(not c.isascii() or not (c.isalnum() or c in "_.-") for c in operation_id)):
            raise ValueError("Invalid cleanup operation ID.")
        if not isinstance(payload, dict) or payload.get("confirmation") != UNUSED_CONFIRMATION:
            raise self.account_error_class("Explicit unused-account deletion confirmation required.", 400)
        preview_id = payload.get("preview_id")
        if not isinstance(preview_id, str):
            raise self.account_error_class("Fresh cleanup preview required.", 409)
        with self.lock:
            previous = self.data.get("unused_account_operations", {}).get(operation_id)
            if operation_id is not None and previous is not None:
                return {**previous, "already_completed": True}
            plan = getattr(self, "_unused_previews", {}).get(preview_id)
            if not plan or not at < plan["expires_at"]:
                raise self.account_error_class("Cleanup preview expired; request a fresh preview.", 409)
            candidates = plan["candidates"]
            idle_seconds = plan.get("idle_seconds", UNUSED_IDLE_SECONDS)
            if type(payload.get("count")) is not int or payload["count"] != len(candidates):
                raise self.account_error_class("Cleanup count does not match its preview.", 409)
            accounts = {row[0] for row in self.db.execute("SELECT id FROM accounts")}
            if (accounts != set(self.data["players"])
                    or self.db.execute("PRAGMA foreign_keys").fetchone() != (1,)):
                raise self.account_error_class("Account database is inconsistent; cleanup refused.", 409)
            for original in candidates:
                pid = original["id"]
                if (self._unused_account_reason(pid, at, idle_seconds=idle_seconds) is not None
                        or any(self.data["players"][pid].get(key) != value for key, value in original.items())):
                    raise self.account_error_class("A selected account changed; request a fresh preview.", 409)
            if not candidates:
                result = {"ok": True, "deleted": 0, "backup": None,
                          "idle_seconds": idle_seconds}
                if operation_id is not None:
                    with self._atomic():
                        self.data.setdefault("unused_account_operations", {})[operation_id] = result
                self._unused_previews.pop(preview_id)
                return dict(result)
            if self._atomic_depth or self.db.in_transaction:
                raise self.account_error_class("Cleanup needs a committed database.", 409)
            try:
                from .balance_reset import verified_reset_backup
            except ImportError:
                from balance_reset import verified_reset_backup
            # Flush the current in-memory world so the verified backup contains
            # precisely the state that will be changed. Do not rotate this copy.
            self._save()
            label = f"unused-{idle_seconds // 3600}h" if idle_seconds % 3600 == 0 else f"unused-{idle_seconds}s"
            backup = verified_reset_backup(self.db, self.db_path, reset_id=label)
            result = {"ok": True, "deleted": len(candidates),
                      "backup": backup.name if backup else "memory-only",
                      "idle_seconds": idle_seconds}
            with self._atomic():
                for original in candidates:
                    self._delete_account_data(original["id"])
                if self.db.execute("PRAGMA foreign_key_check").fetchall():
                    raise self.account_error_class("Cleanup left invalid account references.", 409)
                audit = self.data.setdefault("unused_account_cleanups", [])
                audit.append({"at": at, "count": len(candidates),
                              "idle_seconds": idle_seconds,
                              "operation_id": operation_id,
                              "backup": backup.name if backup else "memory-only"})
                del audit[:-32]
                if operation_id is not None:
                    self.data.setdefault("unused_account_operations", {})[operation_id] = dict(result)
            self._unused_previews.pop(preview_id)
            for original in candidates:
                self._state_poll_presence.pop(original["id"], None)
            return result


