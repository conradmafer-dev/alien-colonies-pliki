"""Capture skill-wheel UI states with an explicitly prepared veteran fleet.

Run from the project root:
    python3 tests/make_progression_fixture.py /tmp/progression-fixture.json

The QA fixture grants combat ships and ordinary fuel after registration so it
can exercise rare-currency delivery without simulating weeks of construction.
It never grants rare crystals or skills, deletes defenders, or freezes NPC AI.
This is not evidence that a starter fleet can raid a fortress: that failure is
covered independently by test_progression_playthrough.py.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.main import GameError  # noqa: E402
from tests.world_fixture import LocalTestWorld as World


START = 1_900_000_000.0
RACES = ("zetans", "automatons", "symbionts")


def state_of(response):
    return deepcopy(response.get("state", response))


def advance_live(world, destination):
    """Advance through both scheduled events and every normal NPC decision.

    A single one-hour ``advance`` would intentionally skip offline NPC decisions;
    this helper instead models a continuously running server without real sleep.
    """
    steps = 0
    while world.now < destination:
        deadlines = [destination, world.data["alien"]["next_expansion_at"]]
        deadlines.extend(p["queue"][0]["ends_at"] for p in world.data["planets"].values() if p["queue"])
        deadlines.extend(f["arrives_at"] for f in world.data["fleets"].values())
        target = min(deadline for deadline in deadlines if deadline > world.now)
        world.advance(target)
        steps += 1
        if steps > 100_000:
            raise RuntimeError("Normal simulation failed to reach its next event.")
    return steps


def first_hunt(world, race_id, aged_seconds=0):
    """Play a prepared veteran raid and first purchase, returning snapshots."""
    age_steps = advance_live(world, world.now + aged_seconds)
    account = world.register("QA " + race_id, "offline-test-only-password")
    pending = state_of(account)
    player_id = pending["player"]["id"]
    chosen = state_of(world.action(player_id, {
        "type": "choose_race", "race_id": race_id,
        "request_id": "progression-race-" + race_id,
    }))
    # Explicit QA setup: a veteran fleet large enough to defeat the real hive.
    # The stock and all defenders remain authoritative and unmodified.
    home = world._owned(player_id)
    home["ships"]["frigate"] = 2500
    home["resources"]["fuel"] = 10_000_000.0
    chosen = state_of(world.state(player_id))
    candidates = []
    for system in chosen["galaxy"]:
        for planet in system["planets"]:
            if planet.get("owner_id") != "khar":
                continue
            payload = {"type": "fleet", "planet_id": chosen["home_id"], "mission": "attack",
                       "target_id": planet["id"], "ships": {"frigate": 2500},
                       "request_id": "progression-raid-" + race_id}
            try:
                preview = world.preview(player_id, payload)
            except GameError:
                continue
            if preview["fuel_cost"] <= chosen["resources"]["fuel"]:
                candidates.append((preview["seconds"], preview["fuel_cost"], planet["id"], payload, preview))
    if not candidates:
        threats = [(p["id"], p.get("swarm_kind"), p.get("swarm_threat"))
                   for s in chosen["galaxy"] for p in s["planets"] if p["owner_id"] == "khar"]
        raise RuntimeError(f"{race_id} after {aged_seconds}s: no reachable hive. Public Swarm: {threats}")
    _, _, target_id, payload, preview = min(candidates)
    defenders_before = dict(world.data["planets"][target_id]["ships"])
    rare_stock_before = world.data["planets"][target_id].get("swarm_crystals", 0)
    launched_at = world.now
    outbound = state_of(world.action(player_id, payload))
    fleet = next(f for f in outbound["fleets"] if f["target_id"] == target_id and f["mission"] == "attack")
    fleet_id = fleet["id"]
    advance_live(world, fleet["arrives_at"])
    returning = state_of(world.state(player_id))
    returning_fleet = next((f for f in returning["fleets"] if f["id"] == fleet_id), None)
    if returning_fleet is None or returning_fleet["status"] != "returning":
        raise RuntimeError(f"{race_id} after {aged_seconds}s: prepared veteran raid did not return. Reports: {returning['reports'][:2]}")
    in_transit_reward = returning_fleet.get("swarm_crystals", 0)
    advance_live(world, returning_fleet["arrives_at"])
    earned = state_of(world.state(player_id))
    first_node = next(n for n in earned["skill_tree"]["nodes"]
                      if n["race_id"] == race_id and n["available"] and n["affordable"])
    purchase_payload = {"type": "unlock_skill", "node_id": first_node["id"],
                        "request_id": "progression-skill-" + race_id}
    try:
        purchased = state_of(world.action(player_id, purchase_payload))
    except GameError as error:
        raise RuntimeError(f"{race_id} after {aged_seconds}s: prepared veteran raid cannot fund first skill. "
                           f"Reward={in_transit_reward}, wallet={earned['player'].get('swarm_crystals')}, "
                           f"reports={earned['reports'][:2]}") from error
    measurements = {
        "race_id": race_id, "aged_seconds": aged_seconds, "age_simulation_steps": age_steps,
        "swarm_colonies_at_registration": chosen["alien"]["colonies_count"],
        "reachable_hives": len(candidates), "target_id": target_id,
        "qa_prepared_veteran_fleet": True,
        "defenders_before": defenders_before, "rare_stock_before": rare_stock_before,
        "starting_fuel": chosen["resources"]["fuel"], "fuel_cost": preview["fuel_cost"],
        "outbound_seconds": preview["seconds"], "whole_mission_seconds": world.now - launched_at,
        "returning_reward": in_transit_reward,
        "wallet_before_return": returning["player"].get("swarm_crystals", 0),
        "wallet_after_return": earned["player"].get("swarm_crystals", 0),
        "wallet_after_purchase": purchased["player"].get("swarm_crystals", 0),
        "surviving_frigates": earned["ships"]["frigate"],
        "first_node_id": first_node["id"], "first_node_name": first_node["name"],
        "first_node_cost": first_node["cost"], "first_node_effects": first_node["effects"],
        "production_before": earned["production"], "production_after": purchased["production"],
    }
    return {"pending": pending, "chosen": chosen, "outbound": outbound, "returning": returning,
            "earned": earned, "purchased": purchased, "selected_node_id": first_node["id"],
            "target_id": target_id, "player_id": player_id, "purchase_payload": purchase_payload,
            "measurements": measurements}


def make_fixture(include_aged=True):
    result = {"races": {}, "aged": {}}
    for age in ((0, 3600) if include_aged else (0,)):
        for race in RACES:
            with tempfile.TemporaryDirectory(prefix="alien-colonies-progression-") as directory:
                world = World(str(Path(directory) / "world.sqlite3"), speed=10, now=START)
                try:
                    snapshots = first_hunt(world, race, age)
                    result["aged" if age else "races"][race] = snapshots
                    if not age and race == RACES[0]:
                        result["pending"] = snapshots["pending"]
                finally:
                    world.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fresh-only", action="store_true")
    args = parser.parse_args()
    fixture = make_fixture(not args.fresh_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({category: {race: states["measurements"] for race, states in fixture[category].items()}
                      for category in ("races", "aged")}, ensure_ascii=False, indent=2))
    print(f"Progression fixture: {args.output}")


if __name__ == "__main__":
    main()
