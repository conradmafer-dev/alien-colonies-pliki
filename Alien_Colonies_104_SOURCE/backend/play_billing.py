"""Server-owned Google Play queue subscription verification.

Google's response, never an Android receipt's expiry or paid flag, is the
authority. Network work can run outside World.lock with check_purchase(); apply
the returned snapshot under the world's atomic mutation lock. Purchase tokens
and OAuth credentials must never be included in public state or request logs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import json
import math
import os
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

PACKAGE_NAME = "com.conradmafer.aliencolonies"
PRODUCT_ID = "queue_planner"
# New purchases use weekly; existing monthly subscribers retain their plan.
BASE_PLAN_ID = "weekly"
LEGACY_BASE_PLAN_ID = "monthly"
SUPPORTED_BASE_PLAN_IDS = frozenset({BASE_PLAN_ID, LEGACY_BASE_PLAN_ID})
OAUTH_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
API_ROOT = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
ENTITLED_STATES = frozenset({"SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD", "SUBSCRIPTION_STATE_CANCELED"})
REFRESH_SECONDS = 300
RETRY_SECONDS = 60


class BillingError(ValueError):
    """Safe error text/code, deliberately omitting tokens and upstream bodies."""
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def account_id(player_id):
    """Exactly 64 non-PII characters for BillingFlowParams.setObfuscatedAccountId."""
    return hashlib.sha256(("alien-colonies:" + str(player_id)).encode("utf-8")).hexdigest()


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        return 0.0
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            return 0.0
        number = instant.timestamp()
        return number if math.isfinite(number) and number > 0 else 0.0
    except (ValueError, OverflowError):
        return 0.0


def _number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value >= 0 else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _validate_token(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 4096 or any(ord(c) <= 32 or ord(c) >= 127 for c in value):
        raise BillingError("invalid_token", "Nieprawidłowy token zakupu.")
    return value


class GooglePlayProvider:
    """Official google-auth OAuth plus the documented subscriptionsv2 REST API."""
    def __init__(self, credentials=None, package_name=PACKAGE_NAME):
        self.credentials, self.package_name = credentials, package_name
        self.ready = credentials is not None and package_name == PACKAGE_NAME
        self._auth_lock = threading.Lock()

    @classmethod
    def from_env(cls):
        # Optional import keeps non-billing local development dependency-free.
        raw = os.environ.get("ALIEN_PLAY_SERVICE_ACCOUNT_JSON", "")
        path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not raw and not path:
            return cls()
        try:
            from google.oauth2 import service_account
            if raw:
                info = json.loads(raw)
                if not isinstance(info, dict) or info.get("type") != "service_account" or info.get("token_uri") != "https://oauth2.googleapis.com/token":
                    return cls()
                credentials = service_account.Credentials.from_service_account_info(info, scopes=[OAUTH_SCOPE])
            else:
                with open(path, encoding="utf-8") as source:
                    info = json.load(source)
                if not isinstance(info, dict) or info.get("type") != "service_account" or info.get("token_uri") != "https://oauth2.googleapis.com/token":
                    return cls()
                credentials = service_account.Credentials.from_service_account_info(info, scopes=[OAUTH_SCOPE])
            return cls(credentials)
        except Exception:
            # A broken configuration must not crash the whole multiplayer game.
            return cls()

    def _bearer(self):
        if not self.ready:
            raise BillingError("billing_unavailable", "Płatności nie są jeszcze skonfigurowane na serwerze.", 503)
        with self._auth_lock:
            if not self.credentials.valid:
                try:
                    from google.auth.transport.requests import Request as AuthRequest
                    request = AuthRequest()
                    def bounded_request(*args, **kwargs):
                        kwargs["timeout"] = 8
                        return request(*args, **kwargs)
                    self.credentials.refresh(bounded_request)
                except Exception:
                    raise BillingError("billing_temporarily_unavailable", "Nie można teraz potwierdzić zakupu w Google Play. Spróbuj ponownie.", 503) from None
            return self.credentials.token

    def _request(self, path, body=None):
        request = Request(API_ROOT + quote(self.package_name, safe="") + path,
                          data=None if body is None else json.dumps(body).encode("utf-8"),
                          headers={"Authorization": "Bearer " + self._bearer(), "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urlopen(request, timeout=8) as response:
                payload = response.read(131073)
            if len(payload) > 131072:
                raise BillingError("invalid_provider_response", "Nieprawidłowa odpowiedź Google Play.", 502)
            return json.loads(payload) if payload else {}
        except HTTPError as error:
            if error.code in (400, 404, 410):
                raise BillingError("purchase_not_found", "Google Play nie potwierdziło tej subskrypcji.", 400) from None
            raise BillingError("billing_temporarily_unavailable", "Nie można teraz potwierdzić zakupu w Google Play. Spróbuj ponownie.", 503) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise BillingError("billing_temporarily_unavailable", "Nie można teraz potwierdzić zakupu w Google Play. Spróbuj ponownie.", 503) from None

    def get_subscription(self, token):
        return self._request("/purchases/subscriptionsv2/tokens/" + quote(_validate_token(token), safe=""))

    def acknowledge(self, token):
        self._request("/purchases/subscriptions/" + PRODUCT_ID + "/tokens/" + quote(_validate_token(token), safe="") + ":acknowledge", {})


@dataclass(frozen=True, repr=False)
class VerifiedPurchase:
    player_id: str
    purchase_token: str
    purchase_hash: str
    state: str
    expiry: float
    google_start: float
    verified_at: float
    linked_hash: str
    acknowledged: bool
    base_plan_id: str


class BillingVerifier:
    def __init__(self, provider=None, clock=time.time):
        self.provider = provider if provider is not None else GooglePlayProvider.from_env()
        self.clock = clock
        self._lock = threading.RLock()
        self._retry_after = {}

    @classmethod
    def from_env(cls):
        return cls()

    @property
    def ready(self):
        return bool(getattr(self.provider, "ready", False))

    def check_purchase(self, player_id, purchase_token):
        """Network-only phase: verify and acknowledge, but do not mutate game data."""
        token = _validate_token(purchase_token)
        if not self.ready or getattr(self.provider, "package_name", PACKAGE_NAME) != PACKAGE_NAME:
            raise BillingError("billing_unavailable", "Płatności nie są jeszcze skonfigurowane na serwerze.", 503)
        # Order snapshots by request start, not completion. A slow older ACTIVE
        # lookup must not overwrite a newer refund/hold lookup that finished
        # first while the older HTTP response was still travelling.
        verification_started = float(self.clock())
        purchase = self.provider.get_subscription(token)
        if not isinstance(purchase, dict):
            raise BillingError("invalid_provider_response", "Nieprawidłowa odpowiedź Google Play.", 502)
        # The real API scopes the token to the immutable package path. This also
        # rejects an unexpected package in injected provider fixtures.
        if purchase.get("packageName", PACKAGE_NAME) != PACKAGE_NAME:
            raise BillingError("wrong_package", "Zakup dotyczy innej aplikacji.")
        identifiers = purchase.get("externalAccountIdentifiers") or {}
        if not isinstance(identifiers, dict):
            raise BillingError("invalid_provider_response", "Nieprawidłowa odpowiedź Google Play.", 502)
        provided_account = identifiers.get("obfuscatedExternalAccountId", "")
        if not provided_account:
            context = purchase.get("outOfAppPurchaseContext") or {}
            old_identifiers = context.get("expiredExternalAccountIdentifiers") if isinstance(context, dict) else {}
            provided_account = old_identifiers.get("obfuscatedExternalAccountId", "") if isinstance(old_identifiers, dict) else ""
        if not isinstance(provided_account, str) or not hmac.compare_digest(provided_account, account_id(player_id)):
            raise BillingError("wrong_account", "Subskrypcja jest przypisana do innego konta gry.", 403)
        items = purchase.get("lineItems")
        if not isinstance(items, list):
            raise BillingError("wrong_product", "Zakup nie zawiera planera kolejek.")
        matching = [item for item in items if isinstance(item, dict) and item.get("productId") == PRODUCT_ID and isinstance(item.get("offerDetails"), dict) and isinstance(item["offerDetails"].get("basePlanId"), str) and item["offerDetails"]["basePlanId"] in SUPPORTED_BASE_PLAN_IDS]
        if len(matching) != 1:
            raise BillingError("wrong_product", "Zakup nie zawiera planera kolejek.")
        base_plan_id = matching[0]["offerDetails"]["basePlanId"]
        expiry, start = _timestamp(matching[0].get("expiryTime")), _timestamp(purchase.get("startTime"))
        state = purchase.get("subscriptionState", "SUBSCRIPTION_STATE_UNSPECIFIED")
        if not isinstance(state, str):
            raise BillingError("invalid_provider_response", "Nieprawidłowa odpowiedź Google Play.", 502)
        if state in ("SUBSCRIPTION_STATE_PENDING", "SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED"):
            raise BillingError("purchase_pending", "Zakup oczekuje na potwierdzenie płatności w Google Play.", 409)
        if not expiry or not start or expiry <= start:
            raise BillingError("invalid_provider_response", "Google Play nie zwróciło poprawnego okresu subskrypcji.", 502)
        now = float(self.clock())
        acknowledged = purchase.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"
        entitled = state in ENTITLED_STATES and start <= now < expiry
        if entitled and not acknowledged:
            if purchase.get("acknowledgementState") != "ACKNOWLEDGEMENT_STATE_PENDING":
                raise BillingError("invalid_provider_response", "Nieprawidłowy stan potwierdzenia subskrypcji.", 502)
            self.provider.acknowledge(token)
            acknowledged = True
        linked = purchase.get("linkedPurchaseToken", "")
        if linked and (not isinstance(linked, str) or len(linked) > 4096):
            raise BillingError("invalid_provider_response", "Nieprawidłowa odpowiedź Google Play.", 502)
        return VerifiedPurchase(str(player_id), token, token_hash(token), str(state), expiry, start, verification_started, token_hash(linked) if linked else "", acknowledged, base_plan_id)

    def _assert_ownership(self, player, verified, players):
        owner_id = str(player.get("id", ""))
        if not owner_id or owner_id != verified.player_id:
            raise BillingError("wrong_account", "Subskrypcja jest przypisana do innego konta gry.", 403)
        for other in players.values():
            sub = other.get("subscription") or {}
            owned = set(sub.get("_play_token_history", []))
            if sub.get("_play_token_hash"):
                owned.add(sub["_play_token_hash"])
            if str(other.get("id")) != owner_id and (verified.purchase_hash in owned or (verified.linked_hash and verified.linked_hash in owned)):
                raise BillingError("token_already_used", "Subskrypcja jest już przypisana do innego konta gry.", 409)
        sub = player.get("subscription") or {}
        current = sub.get("_play_token_hash")
        if current and current != verified.purchase_hash and verified.purchase_hash in sub.get("_play_token_history", []):
            raise BillingError("subscription_replaced", "Ten zakup został zastąpiony nowszą subskrypcją.", 409)

    def apply_purchase(self, player, verified, players):
        """Apply under World._atomic() after network verification completes.

        Store raw tokens only in private saved data so renewals can be checked
        from web sessions too. Keep ownership hashes even for replaced tokens.
        """
        with self._lock:
            self._assert_ownership(player, verified, players)
            now = float(self.clock())
            previous = player.get("subscription") or {}
            if verified.verified_at < _number(previous.get("_verified_at")):
                raise BillingError("stale_verification", "Zachowano nowszy stan subskrypcji. Odśwież status.", 409)
            current = previous.get("_play_token_hash")
            entitled = verified.state in ENTITLED_STATES and verified.acknowledged and verified.google_start <= now < verified.expiry
            if not entitled and current and current != verified.purchase_hash and _number(previous.get("expires_at")) > now and previous.get("enable_queue_planning"):
                raise BillingError("inactive_purchase", "Ten zakup nie jest aktywny. Zachowano bieżącą subskrypcję.", 409)
            periods = []
            for period in previous.get("periods", []):
                if isinstance(period, dict):
                    begin, end = _number(period.get("starts_at")), _number(period.get("expires_at"))
                    if begin and end > begin:
                        periods.append({"starts_at": begin, "expires_at": end})
            if not periods and previous.get("enable_queue_planning") and _number(previous.get("starts_at")):
                periods.append({"starts_at": _number(previous.get("starts_at")), "expires_at": _number(previous.get("expires_at"))})
            if entitled:
                # A verified extension before the old period expires is
                # continuous. Recovery after an unknown gap starts now: never
                # retroactively automate unpaid time using a later purchase.
                if periods and periods[-1]["expires_at"] >= now and (current == verified.purchase_hash or verified.linked_hash == current):
                    periods[-1]["expires_at"] = verified.expiry
                    begins = periods[-1]["starts_at"]
                else:
                    begins = max(now, verified.google_start)
                    periods.append({"starts_at": begins, "expires_at": verified.expiry})
            else:
                begins = _number(previous.get("starts_at"))
                cutoff = min(verified.expiry, now)
                for period in periods:
                    if period["expires_at"] > cutoff:
                        period["expires_at"] = max(period["starts_at"], cutoff)
            history = set(previous.get("_play_token_history", []))
            history.add(verified.purchase_hash)
            if verified.linked_hash:
                history.add(verified.linked_hash)
            player["subscription"] = {
                "provider": "google_play", "product_id": PRODUCT_ID, "base_plan_id": verified.base_plan_id,
                "enable_queue_planning": bool(entitled), "starts_at": begins,
                "expires_at": verified.expiry if entitled else min(verified.expiry, now),
                "periods": periods[-24:], "_play_token": verified.purchase_token,
                "_play_token_hash": verified.purchase_hash, "_play_token_history": sorted(history),
                "_play_state": verified.state, "_verified_at": verified.verified_at,
                "_acknowledged": verified.acknowledged,
            }
            self._retry_after.pop(verified.player_id, None)
            return self.public_entitlement(player)

    def verify_purchase(self, player, purchase_token, players):
        return self.apply_purchase(player, self.check_purchase(player["id"], purchase_token), players)

    def is_refresh_due(self, player, force=False):
        sub = player.get("subscription") or {}
        now = float(self.clock())
        if not sub.get("_play_token") or not self.ready:
            return False
        return bool(force or (now >= self._retry_after.get(str(player.get("id")), 0) and now - _number(sub.get("_verified_at")) >= REFRESH_SECONDS))

    def refresh_player(self, player, players, force=False):
        """Convenience for a lock-safe caller; prefer two phases in live HTTP.

        A temporary Google outage cannot create or extend access. A previously
        verified paid period remains usable only up to its known expiry.
        """
        if not self.is_refresh_due(player, force):
            return False
        token = player["subscription"]["_play_token"]
        check_started = float(self.clock())
        try:
            verified = self.check_purchase(player["id"], token)
            self.apply_purchase(player, verified, players)
            return True
        except BillingError as error:
            self._retry_after[str(player["id"])] = float(self.clock()) + RETRY_SECONDS
            if error.code in {"purchase_not_found", "wrong_account", "wrong_product", "wrong_package"}:
                if player.get("subscription", {}).get("_play_token") != token:
                    return False
                return self.invalidate_player(player, checked_started=check_started)
            return False

    def invalidate_player(self, player, checked_started=None):
        """Terminal provider rejection stops future starts; preserve past time."""
        now = float(self.clock())
        sub = player.get("subscription") or {}
        if checked_started is not None and _number(sub.get("_verified_at")) > checked_started:
            return False
        sub["enable_queue_planning"] = False
        sub["expires_at"] = min(_number(sub.get("expires_at")), now)
        for period in sub.get("periods", []):
            if isinstance(period, dict) and _number(period.get("expires_at")) > now:
                period["expires_at"] = max(_number(period.get("starts_at")), now)
        sub["_verified_at"] = now
        sub["_play_state"] = "SUBSCRIPTION_STATE_EXPIRED"
        player["subscription"] = sub
        return True

    def public_entitlement(self, player):
        """Explicit allow-list: never publish receipts, token hashes, or orders."""
        now = float(self.clock())
        sub = player.get("subscription") or {}
        begin, end = _number(sub.get("starts_at")), _number(sub.get("expires_at"))
        active = bool(sub.get("enable_queue_planning") and begin <= now < end)
        # Records saved by the previous verifier already contain monthly.
        # Preserve older Google records too; weekly is only the new-purchase default.
        base_plan_id = sub.get("base_plan_id") or (LEGACY_BASE_PLAN_ID if sub.get("_play_token") else BASE_PLAN_ID)
        return {"queue_planning_active": active, "starts_at": begin, "expires_at": end,
                "product_id": PRODUCT_ID, "base_plan_id": base_plan_id,
                "supported_base_plan_ids": sorted(SUPPORTED_BASE_PLAN_IDS),
                "billing_account_id": account_id(player.get("id", "")),
                "provider_ready": self.ready, "subscription_state": str(sub.get("_play_state", ""))}
