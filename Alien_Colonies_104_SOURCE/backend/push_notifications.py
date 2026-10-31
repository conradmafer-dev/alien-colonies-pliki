"""Opt-in Android reports and return reminders; network I/O never holds the world lock."""
from __future__ import annotations
import hashlib
import json
import math
import os
import re
import time
import urllib.error
import urllib.request

try:
    from .i18n import render_text
except ImportError:
    from i18n import render_text

PACKAGE = "com.conradmafer.aliencolonies"
TOKEN = re.compile(r"[-A-Za-z0-9_:.]{40,4096}\Z")
RETURN_AFTER_SECONDS = 24 * 60 * 60
RETURN_TTL_SECONDS = 60 * 60
RETURN_PRESENCE_SECONDS = 120
RETURN_PREFIX = "return24:"
RETURN_COPY = {
    "en": ("Your empire awaits!",
           "Return to Alien Colonies. Grow your colonies and climb the Empire Rankings!"),
    "pl": ("Twoje imperium czeka!",
           "Wróć do Alien Colonies. Rozwijaj kolonie i pnij się w rankingu imperiów!"),
    "de": ("Dein Imperium wartet!",
           "Kehre zu Alien Colonies zurück. Baue deine Kolonien aus und steige in der Imperiumsrangliste auf!"),
    "es": ("¡Tu imperio te espera!",
           "Vuelve a Alien Colonies. ¡Desarrolla tus colonias y sube en la clasificación de imperios!"),
    "fr": ("Votre empire vous attend !",
           "Revenez sur Alien Colonies. Développez vos colonies et progressez dans le classement des empires !"),
}


def configuration():
    """Only public Android identifiers are returned to clients."""
    try:
        raw = json.loads(os.environ.get("ALIEN_FIREBASE_ANDROID_CONFIG_JSON", "{}"))
        if not isinstance(raw, dict):
            return {"configured": False}
        if "project_info" in raw:
            client = next(c for c in raw.get("client", []) if
                          c.get("client_info", {}).get("android_client_info", {}).get("package_name") == PACKAGE)
            info = raw["project_info"]
            raw = {"project_id": info["project_id"], "sender_id": str(info["project_number"]),
                   "app_id": client["client_info"]["mobilesdk_app_id"],
                   "api_key": client["api_key"][0]["current_key"]}
        account = json.loads(os.environ.get("ALIEN_FIREBASE_SERVICE_ACCOUNT_JSON", "{}"))
        if not isinstance(account, dict):
            return {"configured": False}
        public = {key: str(raw[key]) for key in ("project_id", "sender_id", "app_id", "api_key")}
        if account.get("project_id") != public["project_id"] or not account.get("private_key"):
            return {"configured": False}
        return {"configured": True, **public}
    except (ValueError, TypeError, KeyError, StopIteration):
        return {"configured": False}


def init_db(db):
    db.executescript("""
      CREATE TABLE IF NOT EXISTS push_devices(
        device_hash TEXT PRIMARY KEY, player_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        session_hash TEXT NOT NULL REFERENCES sessions(token_hash) ON DELETE CASCADE,
        token TEXT NOT NULL, language TEXT NOT NULL, subscribed_at REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS push_outbox(
        device_hash TEXT NOT NULL REFERENCES push_devices(device_hash) ON DELETE CASCADE,
        report_id TEXT NOT NULL, player_id TEXT NOT NULL, payload TEXT NOT NULL,
        queued_at REAL NOT NULL, next_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(device_hash,report_id));
      CREATE INDEX IF NOT EXISTS push_outbox_due ON push_outbox(next_at);
      CREATE TABLE IF NOT EXISTS push_return_reminders(
        player_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
        activity_at REAL NOT NULL, notification_id TEXT NOT NULL, queued_at REAL NOT NULL);
    """)


def register(world, player_id, session_token, body):
    if world.authenticate(session_token) != player_id:
        raise world.account_error_class("Nieprawidłowa sesja powiadomień.", 403)
    token = body.get("token")
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        raise world.account_error_class("Nieprawidłowy identyfikator powiadomień.", 400)
    language = str(body.get("language", "en")).split("-")[0]
    if language not in ("en", "pl", "de", "es", "fr"):
        language = "en"
    device_hash = hashlib.sha256(token.encode()).hexdigest()
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    # An app install belongs to one currently signed-in account. Old queued
    # reports must never follow a device to the next account.
    with world._atomic():
        previous = world.db.execute("SELECT player_id,session_hash FROM push_devices WHERE device_hash=?",
                                    (device_hash,)).fetchone()
        if previous != (player_id, session_hash):
            world.db.execute("DELETE FROM push_outbox WHERE device_hash=?", (device_hash,))
        world.db.execute("""INSERT INTO push_devices VALUES(?,?,?,?,?,?)
          ON CONFLICT(device_hash) DO UPDATE SET player_id=excluded.player_id,
          session_hash=excluded.session_hash,token=excluded.token,language=excluded.language,
          subscribed_at=excluded.subscribed_at""",
          (device_hash, player_id, session_hash, token, language, world.now))
    return {"ok": True, "registered": True, "push_configured": configuration()["configured"]}


def unregister(world, player_id, session_token):
    if world.authenticate(session_token) != player_id:
        raise world.account_error_class("Nieprawidłowa sesja powiadomień.", 403)
    with world._atomic():
        world.db.execute("DELETE FROM push_devices WHERE player_id=? AND session_hash=?",
                         (player_id, hashlib.sha256(session_token.encode()).hexdigest()))
    return {"ok": True}


def enqueue_report(world, player_id, report):
    """Called inside the same transaction that commits the new game report."""
    rows = world.db.execute("""SELECT d.device_hash,d.language FROM push_devices d
      JOIN sessions s ON s.token_hash=d.session_hash
      WHERE d.player_id=? AND s.player_id=? AND s.expires>?""",
      (player_id, player_id, world.now)).fetchall()
    for device_hash, language in rows:
        translated = report.get("i18n", {})
        title = render_text(translated.get("title", report.get("title", "Alien Colonies")), language)
        body = render_text(translated.get("text", report.get("text", "")), language)
        body = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", body)).strip()
        original = str(report.get("title", "")).lower()
        kind = "attack" if any(word in original for word in ("atak", "nalot", "bombard", "inwaz")) else "report"
        payload = {"player_id": player_id, "report_id": str(report["id"]),
                   "title": title[:100], "body": body[:300], "kind": kind}
        world.db.execute("""INSERT OR IGNORE INTO push_outbox
          (device_hash,report_id,player_id,payload,queued_at,next_at) VALUES(?,?,?,?,?,?)""",
          (device_hash, str(report["id"]), player_id, json.dumps(payload, ensure_ascii=False), world.now, world.now))


def cancel_return_reminder(world, player_id):
    """A verified return resets the episode in the caller's world transaction."""
    row = world.db.execute("SELECT notification_id FROM push_return_reminders WHERE player_id=?",
                           (player_id,)).fetchone()
    if row:
        world.db.execute("DELETE FROM push_outbox WHERE player_id=? AND report_id=?", (player_id, row[0]))
        world.db.execute("DELETE FROM push_return_reminders WHERE player_id=?", (player_id,))


def _return_activity(world, player_id):
    value = world.data["players"].get(player_id, {}).get("last_active_at")
    return (float(value) if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None)


def _return_due(world, player_id, activity):
    presence = world._state_poll_presence.get(player_id)
    present = presence is not None and 0 <= time.monotonic() - presence < RETURN_PRESENCE_SECONDS
    return activity is not None and world.now >= activity + RETURN_AFTER_SECONDS and not present


def enqueue_return_reminders(world):
    """One durable episode per absent human account, fanned out to its opted-in devices.

    Only notification tables change, so a SQL transaction suffices: do not copy
    or rewrite the entire world snapshot on each sweep. A consumed episode stays
    recorded after delivery, expiry or failed retries until real player activity.
    """
    if not configuration()["configured"]:
        return 0
    queued = 0
    with world.lock:
        if world._atomic_depth or world.db.in_transaction:
            return 0
        with world.db:
            devices = world.db.execute("""SELECT d.device_hash,d.player_id,d.language FROM push_devices d
              JOIN sessions s ON s.token_hash=d.session_hash
              WHERE s.player_id=d.player_id AND s.expires>?""", (world.now,)).fetchall()
            by_player = {}
            for device_hash, player_id, language in devices:
                by_player.setdefault(player_id, []).append((device_hash, language))
            for player_id, targets in by_player.items():
                activity = _return_activity(world, player_id)
                if not _return_due(world, player_id, activity):
                    continue
                previous = world.db.execute("SELECT activity_at FROM push_return_reminders WHERE player_id=?",
                                            (player_id,)).fetchone()
                if previous and previous[0] == activity:
                    continue
                cancel_return_reminder(world, player_id)
                digest = hashlib.sha256((player_id + ":" + activity.hex()).encode()).hexdigest()[:32]
                notification_id = RETURN_PREFIX + digest
                world.db.execute("INSERT INTO push_return_reminders VALUES(?,?,?,?)",
                                 (player_id, activity, notification_id, world.now))
                for device_hash, language in targets:
                    title, body = RETURN_COPY.get(language, RETURN_COPY["en"])
                    payload = {"player_id": player_id, "report_id": notification_id,
                               "title": title, "body": body, "kind": "return_reminder"}
                    world.db.execute("""INSERT OR IGNORE INTO push_outbox
                      (device_hash,report_id,player_id,payload,queued_at,next_at) VALUES(?,?,?,?,?,?)""",
                      (device_hash, notification_id, player_id, json.dumps(payload, ensure_ascii=False),
                       world.now, world.now))
                queued += 1
    return queued


class FcmSender:
    def __init__(self):
        self.credentials = None

    def send(self, token, data):
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        if self.credentials is None:
            info = json.loads(os.environ["ALIEN_FIREBASE_SERVICE_ACCOUNT_JSON"])
            self.credentials = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/firebase.messaging"])
        if not self.credentials.valid:
            self.credentials.refresh(Request())
        project = configuration()["project_id"]
        android = {"priority": "HIGH", "ttl": "86400s"}
        if data.get("kind") == "return_reminder":
            android = {"priority": "NORMAL", "ttl": str(RETURN_TTL_SECONDS) + "s",
                       "collapse_key": "alien-return-24h"}
        message = {"message": {"token": token, "data": data, "android": android}}
        # Data messages let the native receiver check the current signed-in
        # empire and deduplicate against notifications created during polling.
        request = urllib.request.Request(
            "https://fcm.googleapis.com/v1/projects/" + project + "/messages:send",
            data=json.dumps(message).encode(),
            headers={"Authorization": "Bearer " + self.credentials.token,
                     "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10):
                return "sent"
        except urllib.error.HTTPError as error:
            payload = error.read(16384)
            if error.code == 404 and b"UNREGISTERED" in payload:
                return "unregistered"
            return "retry"


def deliver_due(world, sender, limit=20):
    """Read committed outbox rows; send outside the lock; keep retry state durable."""
    if not configuration()["configured"]:
        return 0
    delivered = 0
    for _ in range(limit):
        with world.lock:
            if world._atomic_depth or world.db.in_transaction:
                return delivered
            world.db.execute("DELETE FROM push_outbox WHERE queued_at < ?", (world.now - 86400,))
            world.db.execute("DELETE FROM push_outbox WHERE report_id LIKE ? AND queued_at<=?",
                             (RETURN_PREFIX + "%", world.now - RETURN_TTL_SECONDS))
            row = world.db.execute("""SELECT o.device_hash,o.report_id,o.player_id,o.payload,o.attempts,d.token
              FROM push_outbox o JOIN push_devices d ON d.device_hash=o.device_hash
              JOIN sessions s ON s.token_hash=d.session_hash
              WHERE o.next_at<=? AND o.player_id=d.player_id AND s.player_id=d.player_id AND s.expires>?
              ORDER BY o.queued_at LIMIT 1""", (world.now, world.now)).fetchone()
            world.db.commit()
            if row is not None and row[1].startswith(RETURN_PREFIX):
                episode = world.db.execute("""SELECT activity_at FROM push_return_reminders
                  WHERE player_id=? AND notification_id=?""", (row[2], row[1])).fetchone()
                activity = _return_activity(world, row[2])
                if not episode or episode[0] != activity or not _return_due(world, row[2], activity):
                    world.db.execute("DELETE FROM push_outbox WHERE device_hash=? AND report_id=?", row[:2])
                    world.db.commit()
                    continue
        if row is None:
            break
        device_hash, report_id, player_id, payload, attempts, token = row
        try:
            outcome = sender.send(token, json.loads(payload))
        except Exception:
            outcome = "retry"
        with world.lock:
            if outcome == "unregistered":
                world.db.execute("DELETE FROM push_devices WHERE device_hash=? AND player_id=?",
                                 (device_hash, player_id))
            elif outcome == "sent" or attempts >= 7:
                world.db.execute("DELETE FROM push_outbox WHERE device_hash=? AND report_id=?",
                                 (device_hash, report_id))
                delivered += outcome == "sent"
            else:
                world.db.execute("""UPDATE push_outbox SET attempts=attempts+1,next_at=?
                  WHERE device_hash=? AND report_id=?""",
                  (world.now + min(3600, 30 * 2 ** attempts), device_hash, report_id))
            world.db.commit()
        if outcome == "retry":
            break
    return delivered


def run_sender(world, stop):
    sender = FcmSender()
    next_return_sweep = 0.0
    print("Android notifications: worker ready; return reminders after 24h, once per absence", flush=True)
    while not stop.wait(2):
        try:
            if time.monotonic() >= next_return_sweep:
                queued = enqueue_return_reminders(world)
                if queued:
                    print("Android return reminders: queued=" + str(queued), flush=True)
                next_return_sweep = time.monotonic() + 60
            deliver_due(world, sender)
        except Exception as error:
            # No messages, device identifiers or credentials in server logs.
            print("Android notifications: " + type(error).__name__, flush=True)


