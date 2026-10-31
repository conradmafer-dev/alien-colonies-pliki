"""Create local race UI snapshots with the real server; no HTTP or saved sessions.

Run from the project root:
    python3 tests/make_race_fixture.py /tmp/alien-colonies-races.json

Every race gets a separate temporary database.  Direct inventory changes below
are fixture setup only, making all five ship roles visible in one real mission.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.world_fixture import LocalTestWorld as World


RACE_IDS = ("zetans", "symbionts", "automatons")
SHIP_KEYS = ("scout", "cargo", "colonizer", "frigate", "cruiser")


def state_of(response: dict) -> dict:
    # Copy now: later server actions must not alter an earlier UI snapshot.
    return deepcopy(response.get("state", response))


def make_fixture() -> dict:
    snapshots: dict = {"races": {}}
    for race_id in RACE_IDS:
        with tempfile.TemporaryDirectory(prefix="alien-colonies-race-ui-") as directory:
            world = World(
                db_path=str(Path(directory) / "offline-world.sqlite3"),
                speed=10,
                now=1_900_000_000.0,
            )
            try:
                account = world.register("QA " + race_id, "offline-test-only-password")
                initial = state_of(account)
                player_id = initial["player"]["id"]
                planet_id = initial["home_id"]
                if race_id == RACE_IDS[0]:
                    snapshots["pending"] = initial
                    # Old accounts may have a running project when the race
                    # feature first arrives. Exercise the server's actual gate.
                    snapshots["blocked"] = state_of(world.action(player_id, {
                        "type": "build", "key": "metal_mine", "planet_id": planet_id,
                        "request_id": "fixture-before-race-feature",
                    }))
                    world.advance(snapshots["blocked"]["queue"][0]["ends_at"] + 0.01)
                    snapshots["pending"] = state_of(world.state(player_id, planet_id))

                chosen = state_of(world.action(player_id, {
                    "type": "choose_race", "race_id": race_id,
                    "request_id": "fixture-choose-" + race_id,
                }))
                assert chosen["player"]["race_id"] == race_id, "Server did not persist race choice"
                race_states = {"chosen": chosen}

                researching = state_of(world.action(player_id, {
                    "type": "research", "key": "weapons", "planet_id": planet_id,
                    "request_id": "fixture-weapons-" + race_id,
                }))
                world.advance(researching["queue"][0]["ends_at"] + 0.01)
                race_states["trained"] = state_of(world.state(player_id, planet_id))

                planet = world.data["planets"][planet_id]
                planet["resources"] = {"metal": 100_000, "crystal": 100_000, "fuel": 100_000}
                planet["ships"] = dict.fromkeys(SHIP_KEYS, 2)
                target = next(p for p in world.data["planets"].values() if p["owner_type"] == "empty")
                race_states["fleet"] = state_of(world.action(player_id, {
                    "type": "fleet", "planet_id": planet_id,
                    "mission": "scout", "target_id": target["id"],
                    "ships": dict.fromkeys(SHIP_KEYS, 1),
                    "request_id": "fixture-fleet-" + race_id,
                }))
                race_states["building"] = state_of(world.action(player_id, {
                    "type": "build", "key": "metal_mine", "planet_id": planet_id,
                    "request_id": "fixture-building-" + race_id,
                }))
                snapshots["races"][race_id] = race_states
            finally:
                world.close()

    # A server predating races has no race contract; it must still open its UI.
    legacy = deepcopy(snapshots["races"][RACE_IDS[0]]["chosen"])
    for key in ("races", "race", "race_choice_allowed", "race_choice_reason"):
        legacy.pop(key, None)
    legacy["player"].pop("race_id", None)
    for entries in legacy.get("catalog", {}).values():
        for entry in entries:
            entry.pop("art_key", None)
    snapshots["legacy"] = legacy
    return snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(make_fixture(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Offline race UI fixture: {args.output}")


if __name__ == "__main__":
    main()
