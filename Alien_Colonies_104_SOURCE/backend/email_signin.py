"""Passwordless email login with proof-bound, one-use browser/app handoff.

Mail delivery never holds the simulation lock. A mailbox link alone cannot log
in the client that requested it: web requires its original HttpOnly cookie;
Android requires the separately delivered native ticket AND its poll secret.
Pending flows are deliberately in memory and fail closed after a restart.
"""
from __future__ import annotations

from collections import deque
import hashlib
import hmac
import html
from http.cookies import SimpleCookie
import json
import os
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

try:
    from .i18n import t
except ImportError:
    from i18n import t

FLOW_TTL = 15 * 60
RESEND_AFTER = 60
RECENT_EMAIL_SECONDS = 300
COOKIE_NAME = "__Host-alien_email_flow"
BROWSER_COOKIE_NAME = "__Host-alien_email_confirmation"
NATIVE_HANDOFF = "app_link_v1"
# The installed native bridge validates the exact expected flow before accepting
# this return. Clients cancel Google before assigning an email flow to it.
NATIVE_CALLBACK = "com.conradmafer.aliencolonies://google-auth"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")
MAX_FLOWS = 1024
MAX_RATE_KEYS = 4096
GENERIC_MESSAGE = "Jeśli ten adres może odbierać wiadomości, link logowania wkrótce dotrze."


class EmailSignInError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status
        super().__init__(message)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _token(value):
    if not isinstance(value, str) or not TOKEN_PATTERN.fullmatch(value):
        raise EmailSignInError(t("To logowanie e-mail wygasło. Poproś o nowy link."), 410)
    return value


def normalize_email(value):
    """One case-insensitive address per account; do not merge dots/plus aliases."""
    if not isinstance(value, str) or len(value) > 254:
        raise EmailSignInError(t("Wpisz poprawny adres e-mail."))
    value = value.strip()
    if value.count("@") != 1 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise EmailSignInError(t("Wpisz poprawny adres e-mail."))
    local, domain = value.rsplit("@", 1)
    try:
        domain = domain.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError):
        raise EmailSignInError(t("Wpisz poprawny adres e-mail.")) from None
    if (not 1 <= len(local) <= 64 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+", local)
            or local.startswith(".") or local.endswith(".") or ".." in local
            or len(domain) > 253 or "." not in domain
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
                   for part in domain.split("."))):
        raise EmailSignInError(t("Wpisz poprawny adres e-mail."))
    normalized = local.lower() + "@" + domain
    if len(normalized) > 254:
        raise EmailSignInError(t("Wpisz poprawny adres e-mail."))
    return normalized


def email_key(email):
    return digest("alien-email-v1:" + normalize_email(email))


def _valid_origin(value):
    try:
        parsed = urlsplit(value)
        return bool(parsed.scheme == "https" and parsed.hostname and not parsed.username
                    and not parsed.password and not parsed.path and not parsed.query
                    and not parsed.fragment and parsed.port in (None, 443)
                    and not any(ord(c) <= 32 or ord(c) == 127 for c in value))
    except (TypeError, ValueError):
        return False


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ResendEmailProvider:
    """Server-only credentials. No network activity during initialization."""
    def __init__(self, api_key="", sender="", origin="https://aliencolonies.com"):
        self.api_key, self.sender = api_key, sender
        self.origin = origin.rstrip("/")
        self.ready = False
        try:
            sender_address = sender
            if "<" in sender or ">" in sender:
                match = re.fullmatch(r"[A-Za-z0-9 ._-]{1,60} <([^<>]+)>", sender)
                sender_address = match[1] if match else ""
            normalize_email(sender_address)
            self.ready = bool(_valid_origin(self.origin) and isinstance(api_key, str)
                              and 8 <= len(api_key) <= 4096
                              and not any(ord(c) <= 32 or ord(c) == 127 for c in api_key))
        except (EmailSignInError, AttributeError, TypeError):
            pass

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("EMAIL_PROVIDER_API_KEY", "").strip(),
                   os.environ.get("EMAIL_FROM", "").strip(),
                   os.environ.get("SITE_ORIGIN", "https://aliencolonies.com").strip())

    def send(self, address, link, *, request_id):
        if not self.ready:
            raise EmailSignInError(t("Logowanie e-mailem nie jest jeszcze skonfigurowane."), 503)
        safe_link = html.escape(link, quote=True)
        text = ("Sign in to Alien Colonies\n\nOpen this link on the device and browser where you requested it:\n"
                + link + "\n\nThe link expires in 15 minutes and can be used once. "
                "Confirm only a sign-in you requested yourself. "
                "If you did not request it, ignore this email.\n")
        body = {"from": self.sender, "to": [address], "subject": "Your Alien Colonies sign-in link",
                "text": text, "html": "<h1>Sign in to Alien Colonies</h1><p>Open this link on the device and browser where you requested it.</p>"
                + '<p><a href="' + safe_link + '">Confirm my sign-in</a></p>'
                + "<p>This one-use link expires in 15 minutes. Confirm only a sign-in you requested yourself. "
                "If you did not request it, ignore this email.</p>"}
        request = Request("https://api.resend.com/emails", data=json.dumps(body).encode(), method="POST",
                          headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json",
                                   "Idempotency-Key": "alien-email-" + request_id})
        try:
            with build_opener(_NoRedirects()).open(request, timeout=8) as response:
                if not 200 <= response.status < 300 or len(response.read(65537)) > 65536:
                    raise ValueError("Mail provider rejected delivery")
        except Exception:
            # Provider exceptions can contain the key, recipient or link. Never
            # return/log their contents or include them in the world snapshot.
            raise EmailSignInError(t("Wysyłanie wiadomości jest chwilowo niedostępne. Spróbuj później."), 503) from None


class EmailSignInService:
    def __init__(self, world, provider=None, *, clock=time.monotonic):
        self.world = world
        self.provider = provider if provider is not None else ResendEmailProvider.from_env()
        self.clock = clock
        self.lock = threading.RLock()
        self.flows = {}
        self.rates = {}
        self.delivery_slots = threading.BoundedSemaphore(4)
        if self.provider.ready:
            # A configured verified method must not reopen unverified password signup.
            world.require_google_registration = True

    def config(self):
        return {"ok": True, "configured": bool(self.provider.ready)}

    def _prune(self):
        now = self.clock()
        for key, flow in list(self.flows.items()):
            if flow["expires"] <= now:
                del self.flows[key]
        for key, attempts in list(self.rates.items()):
            while attempts and attempts[0] <= now - 3600:
                attempts.popleft()
            if not attempts:
                del self.rates[key]

    def _limit(self, key, limits):
        """Check all windows before recording, with bounded attacker-key memory."""
        now = self.clock()
        attempts = self.rates.get(key)
        if attempts is None:
            if len(self.rates) >= MAX_RATE_KEYS:
                return False
            attempts = deque()
        if any(sum(at > now - seconds for at in attempts) >= limit for seconds, limit in limits):
            return False
        attempts.append(now)
        self.rates[key] = attempts
        return True

    def start(self, email, *, client="web", handoff=None, browser_cookie=None, ip=""):
        if not self.provider.ready:
            raise EmailSignInError(t("Logowanie e-mailem nie jest jeszcze skonfigurowane."), 503)
        address = normalize_email(email)
        if client not in ("web", "android") or (client == "android" and handoff != NATIVE_HANDOFF) or (client == "web" and handoff is not None):
            raise EmailSignInError(t("Ta aplikacja nie obsługuje linków logowania e-mail. Zaktualizuj aplikację."), 400)
        if client == "web":
            _token(browser_cookie)
        with self.lock:
            self._prune()
            if (len(self.flows) >= MAX_FLOWS
                    or not self._limit("ip:" + digest(str(ip)), [(900, 12)])
                    or not self._limit("global", [(60, 30), (3600, 300)])):
                raise EmailSignInError(t("Zbyt wiele prób logowania. Spróbuj później."), 429)
            can_send = self._limit("email:" + email_key(address), [(60, 1), (3600, 5)])
            flow_id, poll, mail_token = (secrets.token_urlsafe(32) for _ in range(3))
            flow = {"id": flow_id, "poll_hash": digest(poll), "mail_hash": digest(mail_token),
                    "email": address, "client": client, "handoff": handoff, "expires": self.clock() + FLOW_TTL,
                    "cookie_hash": digest(browser_cookie) if browser_cookie else None,
                    "confirmation_cookie_hash": None, "csrf_hash": None,
                    "handoff_hash": None, "status": "pending", "suppressed": not can_send}
            self.flows[flow_id] = flow
        if can_send:
            if not self.delivery_slots.acquire(blocking=False):
                with self.lock:
                    self.flows.pop(flow_id, None)
                raise EmailSignInError(t("Wysyłanie wiadomości jest chwilowo niedostępne. Spróbuj później."), 503)
            try:
                link = self.provider.origin + "/api/auth/email/open?" + urlencode({"flow": flow_id, "token": mail_token})
                self.provider.send(address, link, request_id=flow_id)
            except Exception:
                with self.lock:
                    self.flows.pop(flow_id, None)
                raise EmailSignInError(t("Wysyłanie wiadomości jest chwilowo niedostępne. Spróbuj później."), 503) from None
            finally:
                self.delivery_slots.release()
        return {"ok": True, "flow_id": flow_id, "poll_secret": poll, "expires_in": FLOW_TTL,
                "resend_after": RESEND_AFTER, "poll_after": 3, "message": t(GENERIC_MESSAGE),
                **({"handoff": NATIVE_HANDOFF} if client == "android" else {})}

    def _flow(self, flow_id, poll_secret, browser_cookie=None):
        _token(flow_id), _token(poll_secret)
        self._prune()
        flow = self.flows.get(flow_id)
        if not flow or flow["status"] == "consumed" or not hmac.compare_digest(flow["poll_hash"], digest(poll_secret)):
            raise EmailSignInError(t("To logowanie e-mail wygasło. Poproś o nowy link."), 410)
        if flow["client"] == "web":
            if (not isinstance(browser_cookie, str) or not TOKEN_PATTERN.fullmatch(browser_cookie)
                    or not hmac.compare_digest(flow["cookie_hash"], digest(browser_cookie))):
                raise EmailSignInError(t("Otwórz link e-mail w tej samej przeglądarce, w której o niego poproszono."), 403)
        return flow

    @staticmethod
    def _native_proof(flow, ticket):
        return (flow["client"] == "web" or bool(isinstance(ticket, str) and TOKEN_PATTERN.fullmatch(ticket)
                and flow["handoff_hash"] and hmac.compare_digest(flow["handoff_hash"], digest(ticket))))

    def open(self, flow_id, mail_token, browser_cookie=None):
        _token(flow_id), _token(mail_token)
        with self.lock:
            self._prune()
            flow = self.flows.get(flow_id)
            if (not flow or flow["status"] != "pending" or flow["suppressed"] or not flow["mail_hash"]
                    or not hmac.compare_digest(flow["mail_hash"], digest(mail_token))):
                raise EmailSignInError(t("To logowanie e-mail wygasło. Poproś o nowy link."), 410)
            if flow["client"] == "web":
                if (not isinstance(browser_cookie, str) or not TOKEN_PATTERN.fullmatch(browser_cookie)
                        or not hmac.compare_digest(flow["cookie_hash"], digest(browser_cookie))):
                    raise EmailSignInError(t("Otwórz link e-mail w tej samej przeglądarce, w której o niego poproszono."), 403)
                cookie = browser_cookie
            else:
                cookie = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(32)
            flow.update(confirmation_cookie_hash=digest(cookie), csrf_hash=digest(csrf))
            # A scanner GET can show a form but cannot authorize an account or
            # consume the mail token. A later real GET creates a fresh form.
            return _confirmation_document(flow_id, csrf, flow["client"]), cookie

    def confirm(self, flow_id, cookie, csrf):
        _token(flow_id), _token(cookie), _token(csrf)
        with self.lock:
            self._prune()
            flow = self.flows.get(flow_id)
            if (not flow or flow["status"] != "pending" or flow["suppressed"] or not flow["mail_hash"]
                    or not flow["confirmation_cookie_hash"] or not flow["csrf_hash"]
                    or not hmac.compare_digest(flow["confirmation_cookie_hash"], digest(cookie))
                    or not hmac.compare_digest(flow["csrf_hash"], digest(csrf))):
                raise EmailSignInError(t("To logowanie e-mail wygasło. Poproś o nowy link."), 410)
            flow.update(status="verified", mail_hash=None, csrf_hash=None, confirmation_cookie_hash=None)
            if flow["client"] == "android":
                ticket = secrets.token_urlsafe(32)
                flow["handoff_hash"] = digest(ticket)
                return NATIVE_CALLBACK + "?" + urlencode({"flow_id": flow_id, "handoff_ticket": ticket})
            return None

    def status(self, flow_id, poll_secret, *, browser_cookie=None, handoff_ticket=None):
        with self.lock:
            flow = self._flow(flow_id, poll_secret, browser_cookie)
            if flow["status"] != "verified" or not self._native_proof(flow, handoff_ticket):
                return {"ok": True, "status": "pending"}
            with self.world.lock:
                existing = self.world.db.execute("SELECT 1 FROM email_accounts WHERE email_key=?",
                                                 (email_key(flow["email"]),)).fetchone()
            return {"ok": True, "status": "ready" if existing else "needs_name"}

    def complete(self, flow_id, poll_secret, name=None, *, browser_cookie=None, handoff_ticket=None):
        with self.lock:
            flow = self._flow(flow_id, poll_secret, browser_cookie)
            if flow["status"] != "verified" or not self._native_proof(flow, handoff_ticket):
                raise EmailSignInError(t("Najpierw potwierdź link logowania w wiadomości e-mail."), 409)
            # Holding the flow lock through the atomic account/session transaction
            # ensures racing completions cannot mint multiple sessions/accounts.
            result = self.world.email_complete(flow["email"], name)
            flow.update(status="consumed", email="", handoff_hash=None, poll_hash="")
            return result


class EmailAccountMixin:
    def _init_email_accounts(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS email_accounts (
                email_key TEXT PRIMARY KEY,
                player_id TEXT UNIQUE NOT NULL REFERENCES accounts(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS email_sessions (
                token_hash TEXT PRIMARY KEY REFERENCES sessions(token_hash) ON DELETE CASCADE,
                authenticated_at REAL NOT NULL
            );
        """)

    def _email_recent_session(self, token, player_id):
        row = self.db.execute("""SELECT e.authenticated_at FROM email_sessions e JOIN sessions s USING(token_hash)
            WHERE e.token_hash=? AND s.player_id=? AND s.expires>?""", (digest(token), player_id, self.now)).fetchone()
        return bool(row and 0 <= self.now - row[0] <= RECENT_EMAIL_SECONDS)

    def email_complete(self, verified_email, name=None):
        key = email_key(verified_email)
        with self.lock, self._atomic():
            self.advance()
            existing = self.db.execute("SELECT player_id FROM email_accounts WHERE email_key=?", (key,)).fetchone()
            if existing:
                player_id = existing[0]
            else:
                # A verified address never claims an existing Google/password
                # account by matching its name, and creates nothing without a name.
                result = self.register(name, secrets.token_urlsafe(48), _email_verified=True)
                player_id = result["state"]["player"]["id"]
                self.db.execute("UPDATE accounts SET password_hash='' WHERE id=?", (player_id,))
                self.db.execute("DELETE FROM sessions WHERE player_id=?", (player_id,))
                self.db.execute("INSERT INTO email_accounts(email_key,player_id) VALUES(?,?)", (key, player_id))
            self._player(player_id)
            token = self._session(player_id)
            self.db.execute("INSERT INTO email_sessions(token_hash,authenticated_at) VALUES(?,?)", (digest(token), self.now))
            return {"ok": True, "token": token, "state": self.state(player_id), "message": t("Zalogowano przez e-mail.")}


def _cookie(handler, name):
    try:
        jar = SimpleCookie()
        jar.load(handler.headers.get("Cookie", ""))
        return jar[name].value if name in jar else None
    except Exception:
        return None


def _set_cookie(name, value):
    return name + "=" + value + "; Path=/; Max-Age=" + str(FLOW_TTL) + "; Secure; HttpOnly; SameSite=Lax"


def _check_origin(handler, service, *, required=False):
    origin = handler.headers.get("Origin")
    if (required and origin is None) or (origin is not None and origin != service.provider.origin):
        raise EmailSignInError(t("To potwierdzenie logowania jest nieprawidłowe. Poproś o nowy link."), 403)


def handle_email_api(handler, path):
    service = handler.server.email_signin
    identity = handler._client_ip()
    if handler.command == "GET" and path == "/api/auth/email/config":
        handler.server.rate_limit(("email-config", identity))
        return service.config()
    if handler.command != "POST" or path not in ("/api/auth/email/start", "/api/auth/email/status", "/api/auth/email/complete"):
        raise EmailSignInError(t("Nie znaleziono adresu logowania e-mail."), 404)
    _check_origin(handler, service)
    handler.server.rate_limit(("email-api", identity), auth=not path.endswith("/status"))
    body = handler._body()
    if path.endswith("/start"):
        client = body.get("client", "web")
        browser_cookie = secrets.token_urlsafe(32) if client == "web" else None
        result = service.start(body.get("email"), client=client, handoff=body.get("handoff"),
                               browser_cookie=browser_cookie, ip=identity)
        if browser_cookie:
            handler._email_start_cookie = _set_cookie(COOKIE_NAME, browser_cookie)
        return result
    proof = {"browser_cookie": _cookie(handler, COOKIE_NAME), "handoff_ticket": body.get("handoff_ticket")}
    if path.endswith("/status"):
        return service.status(body.get("flow_id"), body.get("poll_secret"), **proof)
    return service.complete(body.get("flow_id"), body.get("poll_secret"), body.get("name"), **proof)


def _page(title, body):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow"><title>' + html.escape(title)
            + ' — Alien Colonies</title><style>body{font-family:system-ui;background:#071016;color:#edf8f4;'
            'max-width:520px;margin:10vh auto;padding:24px;line-height:1.6}a,button{display:inline-block;'
            'background:#78e2c0;color:#07231b;border:0;border-radius:8px;padding:14px 20px;font:inherit;'
            'font-weight:650;text-decoration:none;cursor:pointer}p{color:#c5d8d2}</style></head><body>'
            '<h1>' + html.escape(title) + '</h1>' + body + '</body></html>')


def _confirmation_document(flow_id, csrf, client):
    instructions = ("Confirm only a sign-in you requested on this phone. After confirming, return to the Alien Colonies app."
                    if client == "android" else "Confirm only a sign-in you requested in this browser. After confirming, return to your original game tab.")
    return _page("Confirm your sign-in", "<p>" + instructions + "</p>"
                 '<form method="post" action="/api/auth/email/confirm">'
                 '<input type="hidden" name="flow_id" value="' + html.escape(flow_id, quote=True) + '">'
                 '<input type="hidden" name="csrf" value="' + html.escape(csrf, quote=True) + '">'
                 '<button type="submit">Confirm my sign-in</button></form>'
                 '<p>If you did not request this link, close this page. No account has been signed in.</p>')


def _browser_response(handler, status, document, cookie=None):
    raw = document.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Cache-Control", "no-store")
    # Preserve the form POST's Origin in Chromium, without exposing the mail
    # token's path/query through Referer. no-referrer makes that Origin opaque.
    handler.send_header("Referrer-Policy", "strict-origin")
    handler.send_header("X-Robots-Tag", "noindex, nofollow")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
    handler.send_header("Connection", "close")
    if cookie:
        handler.send_header("Set-Cookie", cookie)
    handler.end_headers()
    handler.wfile.write(raw)


def serve_email_browser(handler):
    parsed = urlsplit(handler.path)
    if ((handler.command != "GET" or parsed.path != "/api/auth/email/open")
            and (handler.command != "POST" or parsed.path != "/api/auth/email/confirm")):
        return False
    service = handler.server.email_signin
    try:
        handler.server.rate_limit(("email-browser", handler._client_ip()))
        if not service.provider.ready:
            raise EmailSignInError(t("Logowanie e-mailem nie jest jeszcze skonfigurowane."), 503)
        if handler.command == "GET":
            query = parse_qs(parsed.query, max_num_fields=4)
            if set(query) != {"flow", "token"} or any(len(values) != 1 for values in query.values()):
                raise EmailSignInError(t("To logowanie e-mail wygasło. Poproś o nowy link."), 410)
            document, cookie = service.open(query["flow"][0], query["token"][0], _cookie(handler, COOKIE_NAME))
            _browser_response(handler, 200, document, _set_cookie(BROWSER_COOKIE_NAME, cookie))
        else:
            _check_origin(handler, service, required=True)
            length = handler.headers.get("Content-Length", "")
            if (handler.headers.get("Transfer-Encoding") or not re.fullmatch(r"[0-9]{1,4}", length)
                    or not 1 <= int(length) <= 4096
                    or handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded"):
                raise EmailSignInError(t("To potwierdzenie logowania jest nieprawidłowe. Poproś o nowy link."), 400)
            form = parse_qs(handler.rfile.read(int(length)).decode("utf-8"), max_num_fields=4)
            if set(form) != {"flow_id", "csrf"} or any(len(values) != 1 for values in form.values()):
                raise EmailSignInError(t("To potwierdzenie logowania jest nieprawidłowe. Poproś o nowy link."), 400)
            callback = service.confirm(form["flow_id"][0], _cookie(handler, BROWSER_COOKIE_NAME), form["csrf"][0])
            if callback:
                document = _page("Email confirmed", '<p>Return to the Alien Colonies app on this phone to finish signing in.</p><a href="'
                                 + html.escape(callback, quote=True) + '">Return to game</a>')
            else:
                document = _page("Email confirmed", '<p>Return to the original Alien Colonies tab. It will finish signing you in or ask for your new empire name.</p><p>You can close this confirmation tab.</p>')
            _browser_response(handler, 200, document)
    except EmailSignInError as error:
        _browser_response(handler, error.status, _page("Unable to confirm sign-in", "<p>" + html.escape(error.message) + "</p>"))
    except (ValueError, UnicodeError):
        _browser_response(handler, 400, _page("Unable to confirm sign-in", "<p>Request a new sign-in link from the game.</p>"))
    return True
