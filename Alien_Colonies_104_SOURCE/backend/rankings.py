"""Read-only empire valuations. No historical spending ledger or world migration.

One point is 1,000 metal + crystal + fuel at current catalogue prices.
Only completed, currently owned assets count; a queue is never an asset.
"""
from __future__ import annotations

from functools import lru_cache

try:
    from . import ogame_economy, megastructures
    from .races import UNIQUE_BUILDINGS
    from .i18n import t
except ImportError:
    import ogame_economy, megastructures
    from races import UNIQUE_BUILDINGS
    from i18n import t

UNIT = 1000
CATEGORIES = ("total", "buildings", "research", "fleet", "defense")
PAGE_SIZE = 50

# Exact shared denominator for 3, 5, 7 and 14 real days. Integer millisecond
# credits preserve fractions when a player moves between reward brackets.
REWARD_UNIT = 210 * 86400 * 1000
REWARD_TIERS = ((1, 1, 3), (2, 3, 5), (4, 10, 7), (11, 30, 14))


def _overall(rows):
    return sorted(rows, key=lambda row: (-row["scores"]["total"], row["name"].casefold(), row["player_id"]))


def _reward_days(position):
    return next((days for first, last, days in REWARD_TIERS if first <= position <= last), 0)


def ensure_rewards(world):
    """Start a new reward policy now, never pay for time before deployment."""
    if world.data.get("ranking_reward_schema") == 1:
        return
    world.data["ranking_reward_schema"] = 1
    world.data["ranking_reward_started_at"] = world.now
    world.data["ranking_reward_settled_ms"] = round(world.now * 1000)


def accrue_rewards(world, until):
    """Settle the previous ranking BEFORE assets change at a world event.

    Called inside the world's atomic advance, including offline replay. Merely
    reading ranking/state never grants currency or changes saved progress.
    """
    ensure_rewards(world)
    end = round(until * 1000)
    start = world.data["ranking_reward_settled_ms"]
    if end <= start:
        return
    elapsed = end - start
    for position, row in enumerate(_overall(_rows(world)), 1):
        days = _reward_days(position)
        if not days:
            break
        player = world.data["players"][row["player_id"]]
        credit = int(player.get("ranking_reward_units", 0)) + elapsed * (210 // days)
        earned, player["ranking_reward_units"] = divmod(credit, REWARD_UNIT)
        if earned:
            player["swarm_crystals"] = int(player.get("swarm_crystals", 0)) + earned
            player["ranking_reward_total"] = int(player.get("ranking_reward_total", 0)) + earned
            world._report(row["player_id"], t("Premia rankingowa"),
                t("Zdobyte Kryształy Roju: {0}. Nagroda została dopisana automatycznie za czas utrzymywania premiowanej pozycji w rankingu ogólnym.").format(earned),
                "swarm/crystal", earned, report_kind="ranking")
    world.data["ranking_reward_settled_ms"] = end


def reward_state(world, player_id, *, rows=None):
    """Only the authenticated owner's fractional progress; all other rows stay public aggregates."""
    ordered = _overall(_rows(world) if rows is None else rows)
    position = next((index for index, row in enumerate(ordered, 1) if row["player_id"] == player_id), 0)
    days = _reward_days(position)
    player = world.data["players"][player_id]
    credit = int(player.get("ranking_reward_units", 0))
    per_second = (210 // days) * 1000 if days else 0
    remaining = (REWARD_UNIT - credit + per_second - 1) // per_second if days else None
    return {"schema": 1, "category": "total", "position": position,
            "active": bool(days), "days_per_crystal": days,
            "interval_seconds": days * 86400, "progress_units": credit,
            "progress_unit": REWARD_UNIT, "progress": credit / REWARD_UNIT,
            "remaining_seconds": remaining, "as_of": world.now,
            "earned_total": int(player.get("ranking_reward_total", 0)),
            "art_key": "swarm/crystal",
            "tiers": [{"first": first, "last": last, "days": days} for first, last, days in REWARD_TIERS]}


@lru_cache(maxsize=4096)
def _level_value(group, key, base, completed):
    return sum(sum(ogame_economy.cost(group, key, base, level).values())
               for level in range(completed))


def _count_value(group, quantities, specs):
    return sum(max(0, int(count)) * sum(ogame_economy.cost(group, key, specs[key][2], 0).values())
               for key, count in quantities.items() if key in specs and count)


def _levels_value(group, levels, specs):
    return sum(_level_value(group, key, tuple(specs[key][2]), max(0, int(level)))
               for key, level in levels.items() if key in specs and level)


def _rows(world):
    """Called with world.lock held; visit every colony and travelling fleet once."""
    values, catalogues = {}, {}
    for owner, player in world.data["players"].items():
        if owner == "khar":
            continue
        specs = {group: world._specs(owner, group)
                 for group in ("buildings", "research", "ships", "defenses")}
        # Conquered foreign structures still exist even while their racial
        # effects are inactive. Preserve their own catalogue valuation.
        for buildings in UNIQUE_BUILDINGS.values():
            for key, meta in buildings.items():
                specs["buildings"].setdefault(key, meta["spec"])
        catalogues[owner] = specs
        project = player.get("megastructure", {})
        # Completed megastructures remain their builder's property in the
        # existing game, including dormant projects at a temporarily lost origin.
        stage = max(0, min(len(megastructures.STAGES), int(project.get("dyson_stage", 0))))
        mega = sum(sum(cost) for _, cost, _ in megastructures.STAGES[:stage])
        if project.get("gate_level", 0):
            mega += sum(megastructures.GATE[1])
        values[owner] = {"buildings": mega,
                         "research": _levels_value("research", player.get("research", {}), specs["research"]),
                         "fleet": 0, "defense": 0}
    for planet in world.data["planets"].values():
        owner = planet.get("owner_id")
        if planet.get("owner_type") != "player" or owner not in values:
            continue
        value, specs = values[owner], catalogues[owner]
        value["buildings"] += _levels_value("buildings", planet.get("buildings", {}), specs["buildings"])
        value["fleet"] += _count_value("ships", planet.get("ships", {}), specs["ships"])
        value["defense"] += _count_value("defenses", planet.get("defenses", {}), specs["defenses"])
    # Includes solo missions, alliance operations, returning and stationed
    # support. Operation participants are references to these fleets, not assets.
    for fleet in world.data["fleets"].values():
        owner = fleet.get("owner_id")
        if owner in values:
            values[owner]["fleet"] += _count_value("ships", fleet.get("ships", {}), catalogues[owner]["ships"])
    rows = []
    for owner, value in values.items():
        player = world.data["players"][owner]
        # Round the total only after summing every asset, never per unit or level.
        scores = {key: amount // UNIT for key, amount in value.items()}
        scores["total"] = sum(value.values()) // UNIT
        rows.append({"player_id": owner, "name": player["name"],
                     "race_id": world._race_id(owner), "scores": scores})
    return rows


def view(world, player_id, category="total", page=1, around_me=False):
    """Return public aggregate scores only, never private empire/session details."""
    with world.lock:
        world._player(player_id)
        if category not in CATEGORIES or type(page) is not int or not 1 <= page <= 1_000_000:
            raise world.account_error_class(t("Nieprawidłowe parametry rankingu."), 400)
        rows = _rows(world)
        rows.sort(key=lambda row: (-row["scores"][category], row["name"].casefold(), row["player_id"]))
        own = None
        for position, row in enumerate(rows, 1):
            row.update(position=position, score=row["scores"][category], is_self=row["player_id"] == player_id)
            if row["is_self"]:
                own = row
        pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = (own["position"] - 1) // PAGE_SIZE + 1 if around_me and own else min(page, pages)
        start = (page - 1) * PAGE_SIZE
        return {"ok": True, "schema": 1, "server_time": world.now, "unit": UNIT,
                "category": category, "page": page, "pages": pages,
                "page_size": PAGE_SIZE, "players_total": len(rows),
                "self": own, "items": rows[start:start + PAGE_SIZE],
                "reward": reward_state(world, player_id, rows=rows)}
