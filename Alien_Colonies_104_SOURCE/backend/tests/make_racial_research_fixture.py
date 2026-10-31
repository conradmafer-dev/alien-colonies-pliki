"""Offline racial-research UI states produced by the real authoritative server.

Only local disposable worlds are changed. Research starts and finishes through
World.action/advance; prerequisite setup and maximum-level layout use fixtures.
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
from server.races import UNIQUE_RESEARCH  # noqa: E402


def snapshot(response):
    return deepcopy(response.get("state", response))


def make_fixture():
    result = {"races": {}}
    for race_id, definitions in UNIQUE_RESEARCH.items():
        with tempfile.TemporaryDirectory(prefix="alien-research-ui-") as directory:
            world = World(str(Path(directory) / "world.sqlite3"), speed=10, now=1_900_000_000)
            try:
                initial = snapshot(world.register("QA " + race_id, "offline-test-only-password"))
                owner, planet_id = initial["player"]["id"], initial["home_id"]
                chosen = snapshot(world.action(owner, {
                    "type": "choose_race", "race_id": race_id,
                    "request_id": "choose-research-ui-" + race_id,
                }))
                key = next(iter(definitions))
                planet = world.data["planets"][planet_id]
                planet["resources"] = dict.fromkeys(("metal", "crystal", "fuel"), 9_999_999)
                planet["buildings"]["lab"] = 3
                planet["buildings"]["shipyard"] = 2
                lab_only = snapshot(world.state(owner, planet_id))
                for required, level in definitions[key]["requirements"]:
                    planet["buildings"][required] = level
                ready = snapshot(world.state(owner, planet_id))
                active = None
                completed = None
                for level in (1, 2):
                    action = snapshot(world.action(owner, {
                        "type": "research", "key": key, "planet_id": planet_id,
                        "request_id": f"research-ui-{race_id}-{level}",
                    }))
                    task = action["queue"][0]
                    world.advance(task["started_at"] + task["seconds"] / 2)
                    if level == 1:
                        active = snapshot(world.state(owner, planet_id))
                    world.advance(task["ends_at"] + .01)
                    if level == 1:
                        completed = snapshot(world.state(owner, planet_id))
                improved = snapshot(world.state(owner, planet_id))
                world.data["players"][owner]["research"][key] = 5
                maximum = snapshot(world.state(owner, planet_id))
                result["races"][race_id] = {
                    "chosen": chosen, "lab_only": lab_only, "ready": ready,
                    "active": active, "completed": completed,
                    "improved": improved, "maximum": maximum, "key": key,
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
    print(f"Offline racial-research UI fixture: {args.output}")
