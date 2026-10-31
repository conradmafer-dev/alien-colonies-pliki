"""One optional, non-incentivized Google Play review invitation after five completed builds.

Progress is authoritative per empire, saved in the existing SQLite world snapshot.
Pre-release completions are not guessed from building levels. No review scores are
sent to the server and no user is rewarded for visiting Google Play.
"""
from __future__ import annotations

MILESTONE = 5
SNOOZE_EXTRA_BUILDS = 10
VALID_CHOICES = frozenset(("later", "dismiss", "open_store"))


def ensure(player):
    value = player.get("review_invitation")
    if not isinstance(value, dict):
        value = {"completed_builds": 0, "state": "waiting",
                 "next_at": MILESTONE}
        player["review_invitation"] = value
    return value


def record_completed_build(player):
    item = ensure(player)
    item["completed_builds"] = min(1_000_000, max(0, int(item.get("completed_builds", 0))) + 1)
    if item["completed_builds"] >= item.get("next_at", MILESTONE) and item.get("state") not in ("dismissed", "store_opened"):
        item["state"] = "ready"
    return item


def public(player):
    # Rendering a catalogue/state must not mutate a saved player snapshot.
    item = player.get("review_invitation")
    if not isinstance(item, dict):
        item = {"completed_builds": 0, "state": "waiting", "next_at": MILESTONE}
    return {"eligible": item.get("state") == "ready",
            "completed_builds": max(0, int(item.get("completed_builds", 0))),
            "milestone": MILESTONE,
            "disabled": item.get("state") in ("dismissed", "store_opened")}


def acknowledge(player, choice):
    if choice not in VALID_CHOICES:
        raise ValueError("Unknown review invitation choice")
    item = ensure(player)
    if item.get("completed_builds", 0) < MILESTONE:
        raise ValueError("The invitation milestone has not been reached")
    if item.get("state") in ("dismissed", "store_opened"):
        return item
    if choice == "later":
        item["next_at"] = max(int(item.get("completed_builds", 0)) + SNOOZE_EXTRA_BUILDS, MILESTONE + SNOOZE_EXTRA_BUILDS)
        item["state"] = "snoozed"
    elif choice == "dismiss":
        item["state"] = "dismissed"
    else:
        # Opening the Google Play listing does NOT prove a review was posted.
        item["state"] = "store_opened"
    return item
