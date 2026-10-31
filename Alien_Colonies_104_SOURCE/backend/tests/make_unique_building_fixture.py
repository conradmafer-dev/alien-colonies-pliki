"""Create offline UI snapshots from the actual racial-building server contract.

Inventory/building changes below are isolated fixture setup, never a live world.
Construction itself uses World.action and World.advance so progress is genuine.
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
from server.races import UNIQUE_BUILDINGS  # noqa: E402


def snapshot(response):
    return deepcopy(response.get("state", response))


def make_fixture():
    result = {"races": {}}
    for race_id, definitions in UNIQUE_BUILDINGS.items():
        with tempfile.TemporaryDirectory(prefix="alien-unique-ui-") as directory:
            world = World(str(Path(directory) / "world.sqlite3"), speed=1, now=1_900_000_000)
            try:
                initial = snapshot(world.register("QA " + race_id, "offline-test-only-password"))
                owner = initial["player"]["id"]
                planet_id = initial["home_id"]
                chosen = snapshot(world.action(owner, {
                    "type": "choose_race", "race_id": race_id,
                    "request_id": "choose-unique-ui-" + race_id,
                }))
                assert sum(bool(e.get("unique")) for e in chosen["catalog"]["buildings"]) == 3
                planet = world.data["planets"][planet_id]
                planet["resources"] = dict.fromkeys(("metal", "crystal", "fuel"), 999_999)
                planet["buildings"]["lab"] = 2
                planet["buildings"]["shipyard"] = 2
                ready = snapshot(world.state(owner, planet_id))
                first_key = next(iter(definitions))
                action = snapshot(world.action(owner, {
                    "type": "build", "key": first_key, "planet_id": planet_id,
                    "request_id": "build-unique-ui-" + race_id,
                }))
                task = action["queue"][0]
                world.advance(task["started_at"] + task["seconds"] / 2)
                active = snapshot(world.state(owner, planet_id))
                world.advance(task["ends_at"] + 0.01)
                for key in definitions:
                    planet["buildings"][key] = 2
                planet["ships"]["colonizer"] = 1
                improved = snapshot(world.state(owner, planet_id))
                colony_target = next(p["id"] for p in world.data["planets"].values()
                                     if p["owner_type"] == "empty")
                colony_payload = {"type": "fleet", "planet_id": planet_id,
                                  "mission": "colonize", "target_id": colony_target,
                                  "ships": {"colonizer": 1}}
                colony_preview = world.preview(owner, colony_payload)
                colony_upgraded = None
                if race_id == "symbionts":
                    planet["buildings"]["pioneer_nursery"] = 3
                    colony_upgraded = snapshot(world.state(owner, planet_id))
                    planet["buildings"]["pioneer_nursery"] = 2
                planet["buildings"][first_key] = 5
                maximum = snapshot(world.state(owner, planet_id))
                result["races"][race_id] = {
                    "chosen": chosen, "ready": ready, "active": active,
                    "improved": improved, "maximum": maximum, "first_key": first_key,
                    "colony_payload": colony_payload, "colony_preview": colony_preview,
                    "colony_upgraded": colony_upgraded,
                }
            finally:
                world.close()
    legacy = Path(__file__).with_name("fixtures") / "legacy_ui_0111.json"
    result["legacy"] = json.loads(legacy.read_text(encoding="utf-8"))["initial"]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(make_fixture(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Offline unique-building UI fixture: {args.output}")
