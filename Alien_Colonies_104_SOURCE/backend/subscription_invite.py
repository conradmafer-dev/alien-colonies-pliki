"""Reserve one optional trial invitation after ten completed building projects.

The existing review counter records every completed build or upgrade across the
empire. Reuse that event history rather than inferring progress from building
levels (which can change through colonization or capture).

This module only gates the invitation's milestone and one-time display. The
client must separately verify a currently available seven-day Google Play trial
before claiming or displaying it. A claim never grants paid gameplay benefits.
"""
from __future__ import annotations

MILESTONE = 10


def _completed_builds(player):
    progress = player.get("review_invitation")
    count = progress.get("completed_builds", 0) if isinstance(progress, dict) else 0
    return max(0, count) if type(count) is int else 0


def public(player, *, active=False):
    """Read-only state; a pending client matches its nonce to claim_request_id."""
    item = player.get("subscription_invitation")
    claim_id = item.get("claim_request_id", "") if isinstance(item, dict) else ""
    claim_id = claim_id if isinstance(claim_id, str) else ""
    completed = _completed_builds(player)
    return {"eligible": completed >= MILESTONE and not claim_id and not active,
            "completed_builds": completed, "milestone": MILESTONE,
            "shown": bool(claim_id),
            # Cached action retries also render current entitlement. Do not
            # authorize a stale pending invitation after a purchase activates.
            "claim_request_id": "" if active else claim_id}


def claim(player, request_id, *, now, active=False):
    """Called under the world's atomic lock before the client opens its modal.

The first eligible request reserves the only display. A competing device sees
the winner's different nonce and must not open a second modal. Retries keep the
same nonce even after the generic action idempotency cache has been trimmed.
An interruption after committing may skip the prompt; it must never show twice.
"""
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
        raise ValueError("A unique invitation request id is required")
    if active or _completed_builds(player) < MILESTONE:
        raise ValueError("The subscription invitation is not available")
    item = player.get("subscription_invitation")
    if isinstance(item, dict) and item.get("claim_request_id"):
        return item
    item = {"claim_request_id": request_id, "shown_at": now}
    player["subscription_invitation"] = item
    return item
