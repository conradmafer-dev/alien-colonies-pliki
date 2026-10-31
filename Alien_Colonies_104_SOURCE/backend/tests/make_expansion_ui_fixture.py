"""Generate 0.5.0 UI catalogs through disposable local World instances only."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.world_fixture import LocalTestWorld as World
from server.races import UNIQUE_BUILDINGS, UNIQUE_RESEARCH


def snapshot(response):
    return deepcopy(response.get("state", response))


def make_fixture():
    result = {"races": {}}
    for race in ("zetans", "symbionts", "automatons"):
        with tempfile.TemporaryDirectory(prefix="alien-expansion-ui-") as directory:
            world = World(str(Path(directory) / "world.sqlite3"), speed=1, now=1_900_000_000)
            try:
                initial = snapshot(world.register("QA " + race, "offline-test-only-password"))
                owner, planet_id = initial["player"]["id"], initial["home_id"]
                locked = snapshot(world.action(owner, {"type": "choose_race", "race_id": race, "request_id": "expansion-" + race}))
                planet = world.data["planets"][planet_id]
                player = world.data["players"][owner]
                planet["resources"] = {key: 100_000_000 for key in ("metal", "crystal", "fuel")}
                for key in world._specs(owner, "buildings"):
                    planet["buildings"][key] = 4 if key in UNIQUE_BUILDINGS[race] else 8
                for key in world._specs(owner, "research"):
                    player["research"][key] = 4 if key in UNIQUE_RESEARCH[race] else 8
                for key in world._specs(owner, "ships"):
                    planet["ships"][key] = 7
                ready = snapshot(world.state(owner, planet_id))
                for entry in ready["catalog"]["buildings"]:
                    planet["buildings"][entry["key"]] = entry["max_level"]
                for entry in ready["catalog"]["research"]:
                    player["research"][entry["key"]] = entry["max_level"]
                maximum = snapshot(world.state(owner, planet_id))
                result["races"][race] = {"locked": locked, "ready": ready, "maximum": maximum}
            finally:
                world.close()
    return result


if __name__ == "__main__":
    path = Path(sys.argv[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(make_fixture(), ensure_ascii=False), encoding="utf-8")
    print(path)
