"""Google OIDC browser sign-in and one-use app handoff.

Google code exchange and signature verification never hold the simulation lock.
Poll proofs and game tokens never appear in URLs, HTML, logs or world snapshots.
Only a verified Google subject identifies an account; names/email never auto-link.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
from http.cookies import SimpleCookie
import json
import math
import os
import re
import secrets
import threading
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

try:
    from .i18n import t
except ImportError:
    from i18n import t


FLOW_TTL = 600
RECENT_GOOGLE_SECONDS = 300
COOKIE_NAME = "__Host-alien_google_flow"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")
NATIVE_HANDOFF = "app_link_v1"
NATIVE_CALLBACK = "com.conradmafer.aliencolonies://google-auth"
CLIENT_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+\.apps\.googleusercontent\.com\Z")
NATIVE_VERIFY_WORKERS = 4


class GoogleSignInError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status
        super().__init__(message)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _token(value):
    if not isinstance(value, str) or not TOKEN_PATTERN.fullmatch(value):
        raise GoogleSignInError(t("Logowanie Google wygasło. Spróbuj ponownie."), 410)
    return value


class GoogleOAuthProvider:
    """Server-only OAuth credentials and Google's maintained JWT verifier."""
    def __init__(self, client_id="", client_secret="", origin="https://aliencolonies.com"):
        self.client_id, self.client_secret = client_id, client_secret
        self.origin = origin.rstrip("/")
        self.redirect_uri = self.origin + "/api/auth/google/callback"
        self.ready = False
        self._requests = self._verify = None
        self._certificate_lock = threading.Lock()
        self._certificate_cache = None
        try:
            parsed = urlsplit(self.origin)
            valid_origin = (parsed.scheme == "https" and parsed.hostname
                            and not parsed.username and not parsed.password
                            and not parsed.path and not parsed.query and not parsed.fragment
                            and not any(ord(c) <= 32 or ord(c) == 127 for c in self.origin))
            valid_id = bool(CLIENT_ID_PATTERN.fullmatch(client_id))
            if valid_origin and valid_id and isinstance(client_secret, str) and 1 <= len(client_secret) <= 4096:
                import requests
                from google.oauth2.id_token import verify_oauth2_token
                self._requests, self._verify = requests, verify_oauth2_token
                self.ready = True
        except (ImportError, ValueError):
            pass  # Missing configuration/dependencies never prevent legacy login.

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("ALIEN_GOOGLE_CLIENT_ID", "").strip(),
                   os.environ.get("ALIEN_GOOGLE_CLIENT_SECRET", "").strip(),
                   os.environ.get("ALIEN_GOOGLE_ORIGIN", os.environ.get("SITE_ORIGIN", "https://aliencolonies.com")).strip())

    def authorization_url(self, flow):
        challenge = base64.urlsafe_b64encode(hashlib.sha256(flow["verifier"].encode("ascii")).digest()).decode("ascii").rstrip("=")
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": self.client_id, "redirect_uri": self.redirect_uri,
            "response_type": "code", "scope": "openid profile", "state": flow["state"],
            "nonce": flow["nonce"], "code_challenge": challenge,
            "code_challenge_method": "S256", "prompt": "select_account"})

    def exchange(self, code, flow):
        if not self.ready:
            raise GoogleSignInError(t("Logowanie Google nie jest jeszcze skonfigurowane."), 503)
        if not isinstance(code, str) or not 1 <= len(code) <= 4096:
            raise GoogleSignInError(t("Nie udało się potwierdzić logowania Google."), 401)
        try:
            response = self._requests.post("https://oauth2.googleapis.com/token", data={
                "code": code, "client_id": self.client_id, "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri, "grant_type": "authorization_code",
                "code_verifier": flow["verifier"]}, timeout=(3, 8))
            if response.status_code != 200 or len(response.content) > 65536:
                raise ValueError("OAuth exchange failed")
            payload = response.json()
            encoded = payload.get("id_token") if isinstance(payload, dict) else None
            if not isinstance(encoded, str) or not 32 <= len(encoded) <= 16384:
                raise ValueError("Missing ID token")
            # A bounded requests adapter prevents Google's certificate I/O from
            # using the library default 120-second timeout.
            from google.auth.transport.requests import Request
            session = self._requests.Session()
            request = Request(session=session)
            def bounded_request(*args, **kwargs):
                kwargs["timeout"] = 8
                return request(*args, **kwargs)
            try:
                claims = self._verify(encoded, bounded_request, audience=self.client_id)
            finally:
                session.close()
            return self.validate_claims(claims, flow["nonce"])
        except GoogleSignInError:
            raise
        except Exception:
            # Do not propagate provider errors: these may contain private codes,
            # credentials or JWTs. Clients may safely display the fixed message.
            raise GoogleSignInError(t("Nie udało się potwierdzić logowania Google. Spróbuj ponownie."), 401) from None

    def verify_native(self, encoded, flow):
        """Verify a Credential Manager JWT locally against Google's public keys.

        The ID token is never sent to tokeninfo or stored. Only Google's public
        certificates are fetched, with a bounded timeout and Cache-Control TTL.
        """
        if not self.ready:
            raise GoogleSignInError(t("Logowanie Google nie jest jeszcze skonfigurowane."), 503)
        try:
            if (not isinstance(encoded, str) or not 32 <= len(encoded) <= 16384
                    or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", encoded)):
                raise ValueError("Invalid ID token")
            claims = self._verify(encoded, self._native_certificates, audience=self.client_id)
            return self.validate_claims(claims, flow["nonce"], native=True,
                                        issued_after=flow["issued_at"] - 60)
        except GoogleSignInError:
            raise
        except Exception:
            raise GoogleSignInError(t("Nie udało się potwierdzić logowania Google. Spróbuj ponownie."), 401) from None

    def _native_certificates(self, url, method="GET", **kwargs):
        # google-auth's PEM endpoint is fixed. A JWT cannot choose a URL, request
        # headers or credentials. Cache only the successful, public certificate
        # response; neither JWTs nor claims are retained in this cache.
        if url != "https://www.googleapis.com/oauth2/v1/certs" or method != "GET":
            raise ValueError("Invalid certificate endpoint")
        with self._certificate_lock:
            cached = self._certificate_cache
            if cached and cached[0] > time.monotonic():
                return cached[1]
        from google.auth.transport.requests import Request
        session = self._requests.Session()
        try:
            response = Request(session=session)(url, method="GET", timeout=8)
            data = response.data
            if response.status != 200 or len(data) > 131072:
                raise ValueError("Invalid certificate response")
            certificates = json.loads(data.decode("utf-8"))
            if (not isinstance(certificates, dict) or not certificates or "keys" in certificates
                    or any(not isinstance(value, str) for value in certificates.values())):
                # Keep google-auth on its PEM verifier path. Its alternative
                # JWKS path would create its own network client and bypass this
                # adapter's timeout/cache, so do not accept a changed format.
                raise ValueError("Invalid certificate format")
            headers = {key.lower(): value for key, value in response.headers.items()}
            result = SimpleNamespace(status=200, data=data, headers=headers)
            cache_control = headers.get("cache-control", "")
            match = re.search(r"(?:^|,)\s*max-age=(\d+)(?:\s*,|\s*$)", cache_control, re.I)
            age = headers.get("age", "0")
            ttl = max(0, min(3600, int(match[1])) - (int(age) if age.isdecimal() else 3600)) if match else 0
            if ttl and not re.search(r"(?:^|,)\s*(?:no-store|no-cache)(?:\s*,|\s*$)", cache_control, re.I):
                with self._certificate_lock:
                    self._certificate_cache = (time.monotonic() + ttl, result)
            return result
        finally:
            session.close()

    def validate_claims(self, claims, nonce, *, native=False, issued_after=None):
        now = time.time()
        if not isinstance(claims, dict):
            raise ValueError("Invalid claims")
        subject, actual_nonce = claims.get("sub"), claims.get("nonce")
        expires, issued = claims.get("exp"), claims.get("iat")
        if (claims.get("aud") != self.client_id
                or claims.get("iss") not in ("https://accounts.google.com", "accounts.google.com")
                or not isinstance(subject, str) or not 1 <= len(subject) <= 255
                or any(ord(c) < 33 or ord(c) > 126 for c in subject)
                or not isinstance(actual_nonce, str) or not hmac.compare_digest(actual_nonce, nonce)
                or type(expires) not in (int, float) or not math.isfinite(expires) or expires <= now
                or type(issued) not in (int, float) or not math.isfinite(issued) or issued > now + 60
                or (issued_after is not None and (issued < issued_after or issued >= expires))
                or ("azp" in claims and (not isinstance(claims["azp"], str)
                    or not CLIENT_ID_PATTERN.fullmatch(claims["azp"])
                    or not native and claims["azp"] != self.client_id))):
            raise ValueError("Invalid claims")
        # For native hybrid apps, Google's signed azp can be the Android OAuth
        # client while aud is the web/server client in the same Google project.
        # aud, signature and the one-use server nonce remain mandatory. Never
        # use azp, email or a client-supplied profile as the account identity.
        return subject


class GoogleSignInService:
    def __init__(self, world, provider=None, *, clock=time.monotonic, require_registration=None):
        self.world, self.provider, self.clock = world, provider or GoogleOAuthProvider.from_env(), clock
        self.lock, self.flows = threading.RLock(), {}
        self.native_verify_slots = threading.BoundedSemaphore(NATIVE_VERIFY_WORKERS)
        raw = os.environ.get("ALIEN_REQUIRE_GOOGLE_REGISTRATION", "").strip().lower()
        policy = raw in ("1", "true", "yes") if raw else self.provider.ready
        self.require_registration = policy if require_registration is None else bool(require_registration)
        world.require_google_registration = self.require_registration

    def config(self):
        return {"ok": True, "configured": bool(self.provider.ready),
                "native_configured": bool(self.provider.ready and callable(getattr(self.provider, "verify_native", None))),
                "require_google_registration": self.require_registration}

    def _prune(self):
        now = self.clock()
        for key in list(self.flows):
            if self.flows[key]["expires"] <= now:
                del self.flows[key]

    def start(self, mode="login", *, player_id=None, session_hash=None, client="android", browser_cookie=None, handoff=None, native=False):
        if not self.provider.ready:
            raise GoogleSignInError(t("Logowanie Google nie jest jeszcze skonfigurowane."), 503)
        if mode not in ("login", "link") or mode == "link" and not player_id:
            raise GoogleSignInError(t("Nieprawidłowy tryb logowania Google."))
        if client not in ("web", "android"):
            raise GoogleSignInError(t("Nieprawidłowy klient logowania Google."))
        if handoff is not None and (handoff != NATIVE_HANDOFF or client != "android"):
            raise GoogleSignInError(t("Nieprawidłowy klient logowania Google."))
        if native and (client != "android" or handoff is not None
                       or not callable(getattr(self.provider, "verify_native", None))):
            raise GoogleSignInError(t("Nieprawidłowy klient logowania Google."))
        if client == "web":
            _token(browser_cookie)
        with self.lock:
            self._prune()
            if len(self.flows) >= 512:
                raise GoogleSignInError(t("Zbyt wiele prób logowania Google. Spróbuj później."), 429)
            flow_id, poll, opener = (secrets.token_urlsafe(32) for _ in range(3))
            verification_code = str(secrets.randbelow(900000) + 100000) if client == "android" and handoff is None and not native else None
            flow = {"id": flow_id, "poll_hash": digest(poll), "open_hash": digest(opener),
                    "expires": self.clock() + FLOW_TTL, "mode": mode,
                    "player_id": player_id, "session_hash": session_hash,
                    "status": "pending", "state": secrets.token_urlsafe(32),
                    "nonce": secrets.token_urlsafe(32), "verifier": secrets.token_urlsafe(48),
                    "cookie_hash": digest(browser_cookie) if browser_cookie else None,
                    "opened": False, "client": client, "confirmed": False,
                    "native": native, "issued_at": time.time(),
                    "handoff": handoff, "handoff_hash": None, "handoff_received": False,
                    "code_hash": digest(verification_code) if verification_code else None,
                    "code_attempts": 0, "confirm_csrf": secrets.token_urlsafe(32)}
            self.flows[flow_id] = flow
            if native:
                return {"ok": True, "flow_id": flow_id, "poll_secret": poll,
                        "nonce": flow["nonce"], "server_client_id": self.provider.client_id,
                        "expires_in": FLOW_TTL}
            return {"ok": True, "flow_id": flow_id, "poll_secret": poll,
                    "authorization_url": self.provider.origin + "/api/auth/google/open?" + urlencode({"flow": flow_id, "open": opener}),
                    "expires_in": FLOW_TTL, "poll_after": 3,
                    **({"handoff": NATIVE_HANDOFF} if handoff == NATIVE_HANDOFF else {}),
                    **({"verification_code": verification_code} if verification_code else {})}

    def native_verify(self, flow_id, poll_secret, id_token):
        with self.lock:
            flow = self._flow(flow_id, poll_secret)
            if not flow["native"] or flow["status"] != "pending":
                raise GoogleSignInError(t("Nieprawidłowe potwierdzenie logowania Google."), 409)
            if not self.native_verify_slots.acquire(blocking=False):
                raise GoogleSignInError(t("Zbyt wiele prób logowania Google. Spróbuj później."), 429)
            flow["status"] = "verifying"
            checked = dict(flow)
        # Provider I/O must never hold the auth or simulation lock. Concurrent
        # duplicate verification cannot reuse this one-attempt challenge.
        try:
            subject = self.provider.verify_native(id_token, checked)
            if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
                raise GoogleSignInError(t("Nie udało się potwierdzić logowania Google."), 401)
        except Exception:
            message = t("Nie udało się potwierdzić logowania Google. Spróbuj ponownie.")
            with self.lock:
                if self.flows.get(checked["id"]) is flow:
                    flow.update(status="error", error=message)
            raise GoogleSignInError(message, 401) from None
        finally:
            self.native_verify_slots.release()
        with self.lock:
            if self.flows.get(checked["id"]) is not flow or flow["expires"] <= self.clock():
                raise GoogleSignInError(t("Logowanie Google wygasło. Spróbuj ponownie."), 410)
            flow.update(status="ready", subject=subject)
            return self.status(flow_id, poll_secret)

    def _flow(self, flow_id, poll_secret):
        _token(flow_id), _token(poll_secret)
        self._prune()
        flow = self.flows.get(flow_id)
        if not flow or not hmac.compare_digest(flow["poll_hash"], digest(poll_secret)):
            raise GoogleSignInError(t("Logowanie Google wygasło. Spróbuj ponownie."), 410)
        if flow["status"] == "consumed":
            raise GoogleSignInError(t("To logowanie Google zostało już wykorzystane."), 410)
        return flow

    def open(self, flow_id, opener, browser_cookie=None):
        _token(flow_id), _token(opener)
        with self.lock:
            self._prune()
            flow = self.flows.get(flow_id)
            if not flow or flow["native"] or flow["opened"] or not hmac.compare_digest(flow["open_hash"], digest(opener)):
                raise GoogleSignInError(t("Logowanie Google wygasło. Spróbuj ponownie."), 410)
            if flow["client"] == "web":
                _token(browser_cookie)
                if not hmac.compare_digest(flow["cookie_hash"], digest(browser_cookie)):
                    raise GoogleSignInError(t("Otwórz logowanie Google w tej samej przeglądarce, w której uruchomiono grę."), 401)
                cookie = browser_cookie
            else:
                cookie = secrets.token_urlsafe(32)
            flow.update(opened=True, cookie_hash=digest(cookie))
            if flow["client"] == "android" and flow["handoff"] != NATIVE_HANDOFF:
                return None, cookie
            flow["confirmed"] = True
            return self.provider.authorization_url(flow), cookie

    def confirmation_document(self, flow_id, message=""):
        with self.lock:
            self._prune()
            flow = self.flows.get(_token(flow_id))
            if (not flow or not flow["opened"] or flow["status"] != "pending" or flow["confirmed"]
                    or flow["handoff"] == NATIVE_HANDOFF):
                raise GoogleSignInError(t("Logowanie Google wygasło. Spróbuj ponownie."), 410)
            return _confirmation_document(flow_id, flow["confirm_csrf"], message)

    def confirm(self, flow_id, cookie, csrf, code):
        _token(flow_id), _token(cookie), _token(csrf)
        with self.lock:
            self._prune()
            flow = self.flows.get(flow_id)
            if (not flow or flow["client"] != "android" or not flow["opened"]
                    or flow["status"] != "pending" or flow["confirmed"]
                    or flow["handoff"] == NATIVE_HANDOFF
                    or not hmac.compare_digest(flow["cookie_hash"], digest(cookie))
                    or not hmac.compare_digest(flow["confirm_csrf"], csrf)):
                raise GoogleSignInError(t("Nieprawidłowe potwierdzenie logowania Google."), 401)
            valid_code = isinstance(code, str) and bool(re.fullmatch(r"[0-9]{6}", code))
            if not valid_code or not hmac.compare_digest(flow["code_hash"], digest(code)):
                flow["code_attempts"] += 1
                if flow["code_attempts"] >= 5:
                    flow.update(status="error", error=t("Zbyt wiele błędnych kodów. Uruchom logowanie ponownie w grze."))
                    raise GoogleSignInError(flow["error"], 429)
                raise GoogleSignInError(t("Nieprawidłowy kod. Przepisz sześć cyfr pokazanych w aplikacji Alien Colonies."), 400)
            flow["confirmed"] = True
            return self.provider.authorization_url(flow)

    def callback(self, state, cookie, *, code=None, error=None):
        _token(state), _token(cookie)
        with self.lock:
            self._prune()
            flow = next((f for f in self.flows.values() if hmac.compare_digest(f["state"], state)), None)
            if (not flow or not flow["opened"] or not flow["confirmed"] or flow["status"] != "pending"
                    or not hmac.compare_digest(flow["cookie_hash"], digest(cookie))):
                raise GoogleSignInError(t("Nieprawidłowe potwierdzenie logowania Google."), 401)
            if error:
                flow.update(status="error", error=t("Logowanie Google zostało anulowane. Spróbuj ponownie."))
                return False
            flow["status"] = "verifying"
            checked = dict(flow)
        # Neither this lock nor the simulation lock surrounds network I/O.
        try:
            subject = self.provider.exchange(code, checked)
            if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
                raise GoogleSignInError(t("Nie udało się potwierdzić logowania Google."), 401)
        except GoogleSignInError as exc:
            with self.lock:
                if self.flows.get(checked["id"]) is flow:
                    flow.update(status="error", error=exc.message)
            return False
        with self.lock:
            if self.flows.get(checked["id"]) is not flow or flow["expires"] <= self.clock():
                raise GoogleSignInError(t("Logowanie Google wygasło. Spróbuj ponownie."), 410)
            flow.update(status="ready", subject=subject)
        return True

    def browser_handoff(self, state, cookie):
        """Deliver a one-use native proof only to the browser that completed OAuth.

        Neither polling nor /complete can reveal this proof. Forwarding an OAuth
        start URL to another person's browser therefore cannot let its initiator
        claim their account: their app must also receive this local return URI.
        The fixed custom scheme carries no game session, poll proof or identity.
        """
        _token(state), _token(cookie)
        with self.lock:
            self._prune()
            flow = next((f for f in self.flows.values() if hmac.compare_digest(f["state"], state)), None)
            if (not flow or not flow["opened"] or not flow["confirmed"]
                    or not hmac.compare_digest(flow["cookie_hash"], digest(cookie))):
                raise GoogleSignInError(t("Nieprawidłowe potwierdzenie logowania Google."), 401)
            if flow["handoff"] != NATIVE_HANDOFF:
                return None
            if flow["status"] not in ("ready", "error"):
                raise GoogleSignInError(t("Nieprawidłowe potwierdzenie logowania Google."), 401)
            if flow["handoff_hash"] or flow["handoff_received"]:
                raise GoogleSignInError(t("To logowanie Google zostało już wykorzystane."), 410)
            ticket = secrets.token_urlsafe(32)
            flow["handoff_hash"] = digest(ticket)
            return NATIVE_CALLBACK + "?" + urlencode({"flow_id": flow["id"], "handoff_ticket": ticket})

    def status(self, flow_id, poll_secret, *, handoff_ticket=None):
        with self.lock:
            flow = self._flow(flow_id, poll_secret)
            if flow["handoff"] == NATIVE_HANDOFF and not flow["handoff_received"]:
                # A missing or wrong native proof is retryable and cannot consume
                # a valid ticket. First validate the independent app poll proof
                # above, then compare only a fixed-size digest of the ticket.
                valid_ticket = (isinstance(handoff_ticket, str)
                                and TOKEN_PATTERN.fullmatch(handoff_ticket)
                                and flow["handoff_hash"]
                                and hmac.compare_digest(flow["handoff_hash"], digest(handoff_ticket)))
                if not valid_ticket:
                    return {"ok": True, "status": "pending"}
                flow.update(handoff_received=True, handoff_hash=None)
            status = flow["status"]
            if status == "ready" and flow["mode"] == "login":
                with self.world.lock:
                    linked = self.world.db.execute("SELECT 1 FROM google_accounts WHERE subject=?", (flow["subject"],)).fetchone()
                status = "ready" if linked else "needs_name"
            return {"ok": True, "status": "pending" if status == "verifying" else status,
                    **({"error": flow["error"]} if status == "error" else {})}

    def complete(self, flow_id, poll_secret, name=None):
        with self.lock:
            flow = self._flow(flow_id, poll_secret)
            if (flow["status"] != "ready"
                    or flow["handoff"] == NATIVE_HANDOFF and not flow["handoff_received"]):
                raise GoogleSignInError(t("Najpierw potwierdź logowanie w Google."), 409)
            result = self.world.google_complete(flow["subject"], name, mode=flow["mode"],
                                               link_player_id=flow["player_id"], session_hash=flow["session_hash"])
            flow["status"] = "consumed"
            return result


class GoogleAccountMixin:
    def _init_google_accounts(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS google_accounts (
                subject TEXT PRIMARY KEY, player_id TEXT UNIQUE NOT NULL REFERENCES accounts(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS google_sessions (
                token_hash TEXT PRIMARY KEY REFERENCES sessions(token_hash) ON DELETE CASCADE,
                authenticated_at REAL NOT NULL
            );
        """)

    def _google_recent_session(self, token, player_id):
        row = self.db.execute("""SELECT g.authenticated_at FROM google_sessions g JOIN sessions s USING(token_hash)
            WHERE g.token_hash=? AND s.player_id=? AND s.expires>?""",
            (digest(token), player_id, self.now)).fetchone()
        return bool(row and 0 <= self.now - row[0] <= RECENT_GOOGLE_SECONDS)

    def google_complete(self, subject, name=None, *, mode="login", link_player_id=None, session_hash=None):
        with self.lock, self._atomic():
            self.advance()
            existing = self.db.execute("SELECT player_id FROM google_accounts WHERE subject=?", (subject,)).fetchone()
            if mode == "link":
                proof = self.db.execute("SELECT 1 FROM sessions WHERE token_hash=? AND player_id=? AND expires>?",
                                        (session_hash, link_player_id, self.now)).fetchone()
                if not proof:
                    raise self.account_error_class(t("Zaloguj się ponownie przed połączeniem konta Google."), 401)
                if existing and existing[0] != link_player_id:
                    raise self.account_error_class(t("To konto Google jest już połączone z innym imperium."), 409)
                attached = self.db.execute("SELECT subject FROM google_accounts WHERE player_id=?", (link_player_id,)).fetchone()
                if attached and attached[0] != subject:
                    raise self.account_error_class(t("Imperium jest już połączone z innym kontem Google."), 409)
                player_id = link_player_id
            elif mode == "login":
                if existing:
                    player_id = existing[0]
                else:
                    # User-chosen empire name is validated by the existing signup
                    # rules. No guessed name or matching email can claim an empire.
                    result = self.register(name, secrets.token_urlsafe(48), _google_verified=True)
                    player_id = result["state"]["player"]["id"]
                    # Empty hash makes password authentication impossible until
                    # the owner explicitly sets a recovery password while signed in.
                    self.db.execute("UPDATE accounts SET password_hash='' WHERE id=?", (player_id,))
                    self.db.execute("DELETE FROM sessions WHERE player_id=?", (player_id,))
            else:
                raise self.account_error_class(t("Nieprawidłowy tryb logowania Google."), 400)
            self._player(player_id)
            if not existing:
                self.db.execute("INSERT INTO google_accounts(subject,player_id) VALUES(?,?)", (subject, player_id))
            token = self._session(player_id)
            self.db.execute("INSERT INTO google_sessions(token_hash,authenticated_at) VALUES(?,?)", (digest(token), self.now))
            self._save(commit=False)
            return {"ok": True, "token": token, "state": self.state(player_id),
                    "message": t("Połączono konto Google.") if mode == "link" else t("Zalogowano przez Google.")}


def serve_google_browser(handler):
    """Intercept only the two browser endpoints before Android version checks."""
    parsed = urlsplit(handler.path)
    if ((handler.command != "GET" or parsed.path not in ("/api/auth/google/open", "/api/auth/google/callback"))
            and (handler.command != "POST" or parsed.path != "/api/auth/google/confirm")):
        return False
    service = handler.server.google_signin
    handler.server.rate_limit(("google-browser", handler._client_ip()), auth=True)
    query = parse_qs(parsed.query, keep_blank_values=True)
    def one(key):
        values = query.get(key, [])
        return values[0] if len(values) == 1 else None
    cookie = None
    clear_cookie = False
    script_nonce = None
    try:
        cookies = SimpleCookie()
        cookies.load(handler.headers.get("Cookie", ""))
        current = cookies.get(COOKIE_NAME)
        browser_cookie = current.value if current else None
        if parsed.path.endswith("/open"):
            location, cookie = service.open(one("flow"), one("open"), browser_cookie)
            raw, status = (b"", 302) if location else (service.confirmation_document(one("flow")), 200)
        elif parsed.path.endswith("/confirm"):
            form = _confirmation_body(handler)
            flow_id = form.get("flow")
            try:
                location = service.confirm(flow_id, browser_cookie, form.get("csrf"), form.get("code"))
                raw, status = b"", 302
            except GoogleSignInError as exc:
                if exc.status != 400:
                    raise
                location, raw, status = None, service.confirmation_document(flow_id, exc.message), 400
        else:
            success = service.callback(one("state"), browser_cookie,
                                       code=one("code"), error=one("error"))
            clear_cookie = True
            message = t("Logowanie potwierdzone. Wróć do gry Alien Colonies.") if success else t("Logowanie nie zostało ukończone. Wróć do gry i spróbuj ponownie.")
            native_location = service.browser_handoff(one("state"), browser_cookie)
            if native_location:
                script_nonce = secrets.token_urlsafe(24)
                raw = _native_handoff_document(native_location, message, script_nonce)
            else:
                raw = _browser_document(message)
            location, status = None, 200
    except GoogleSignInError as exc:
        location, raw, status = None, _browser_document(exc.message), exc.status
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("X-Robots-Tag", "noindex, nofollow")
    # Chromium checks form-action against the final destination of a form's
    # redirect chain, including Google's account picker after a valid code.
    csp = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self' https://accounts.google.com; base-uri 'none'; frame-ancestors 'none'"
    if script_nonce:
        csp += "; script-src 'nonce-" + script_nonce + "'"
    handler.send_header("Content-Security-Policy", csp)
    if location:
        handler.send_header("Location", location)
    if cookie:
        handler.send_header("Set-Cookie", COOKIE_NAME + "=" + cookie + "; Path=/; Max-Age=600; Secure; HttpOnly; SameSite=Lax")
    elif clear_cookie:
        handler.send_header("Set-Cookie", COOKIE_NAME + "=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Lax")
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.wfile.write(raw)
    return True


def _browser_document(message):
    return ("<!doctype html><html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Alien Colonies</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;"
            "background:#07110d;color:#e7f3ea;font:18px system-ui;text-align:center}main{padding:24px;max-width:480px}"
            "h1{color:#73dec1;font-size:36px}</style><main><h1>Alien Colonies</h1><p>" + html.escape(str(message)) + "</p></main></html>").encode("utf-8")


def _native_handoff_document(location, message, nonce):
    """Automatic return plus a user gesture fallback for mobile browsers."""
    return ("<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Alien Colonies</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;"
            "background:#07110d;color:#e7f3ea;font:18px system-ui;text-align:center}main{padding:24px;max-width:480px}"
            "h1{color:#73dec1;font-size:36px}a{display:inline-block;margin:16px 0;background:#73dec1;color:#07110d;"
            "border-radius:12px;padding:16px 28px;text-decoration:none;font-weight:700}</style></head><body>"
            "<main><h1>Alien Colonies</h1><p>" + html.escape(str(message)) + "</p><a href='"
            + html.escape(location, quote=True) + "'>" + html.escape(str(t("‹ Wróć do gry"))) + "</a></main>"
            "<script nonce='" + html.escape(nonce, quote=True) + "'>window.location.replace("
            + json.dumps(location) + ");</script></body></html>").encode("utf-8")


def _confirmation_document(flow_id, csrf, message=""):
    title = t("Potwierdź logowanie w aplikacji")
    instruction = t("Przepisz sześciocyfrowy kod wyświetlony w aplikacji Alien Colonies na tym urządzeniu.")
    warning = t("Kod przepisuj tylko z własnej gry. Nie używaj kodu ani linku do logowania przesłanego przez inną osobę.")
    button = t("Przejdź do logowania Google")
    return ("<!doctype html><html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Alien Colonies</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;"
            "background:#07110d;color:#e7f3ea;font:18px system-ui;text-align:center}main{padding:24px;max-width:480px}"
            "h1{color:#73dec1;font-size:36px}input{display:block;margin:18px auto;padding:12px;text-align:center;"
            "font:28px monospace;max-width:180px}button{background:#73dec1;color:#07110d;border:0;border-radius:12px;padding:16px;font:inherit}"
            ".warning{color:#e9cf89}.error{color:#f1aaa1}</style><main><h1>Alien Colonies</h1><h2>" + html.escape(str(title)) + "</h2><p>"
            + html.escape(str(instruction)) + "</p><p class='warning'>" + html.escape(str(warning)) + "</p><p class='error'>"
            + html.escape(str(message)) + "</p><form action='/api/auth/google/confirm' method='post'>"
            "<input type='hidden' name='flow' value='" + html.escape(flow_id, quote=True) + "'>"
            "<input type='hidden' name='csrf' value='" + html.escape(csrf, quote=True) + "'>"
            "<input name='code' inputmode='numeric' pattern='[0-9]{6}' minlength='6' maxlength='6' autocomplete='off' required autofocus aria-label='6 digit code'>"
            "<button type='submit'>" + html.escape(str(button)) + "</button></form></main></html>").encode("utf-8")


def _confirmation_body(handler):
    length = handler.headers.get("Content-Length", "")
    if (handler.headers.get("Transfer-Encoding") or not re.fullmatch(r"[0-9]{1,4}", length)
            or int(length) > 1024 or not handler.headers.get("Content-Type", "").lower().startswith("application/x-www-form-urlencoded")):
        raise GoogleSignInError(t("Nieprawidłowe potwierdzenie logowania Google."), 400)
    try:
        body = handler.rfile.read(int(length)).decode("ascii")
        values = parse_qs(body, keep_blank_values=True, strict_parsing=True, max_num_fields=3)
        if set(values) != {"flow", "csrf", "code"} or any(len(value) != 1 for value in values.values()):
            raise ValueError("Invalid form")
        return {key: value[0] for key, value in values.items()}
    except (UnicodeError, ValueError):
        raise GoogleSignInError(t("Nieprawidłowe potwierdzenie logowania Google."), 400) from None
