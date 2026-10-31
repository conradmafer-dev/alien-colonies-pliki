"""Generate five-language client fixtures using disposable authoritative worlds.

No network, hosted server or real accounts. Serialize inside language_scope so
LocalizedText retains exactly the viewer's HTTP-visible strings.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.world_fixture import LocalTestWorld as World
from server.races import UNIQUE_BUILDINGS, UNIQUE_RESEARCH
from server.i18n import SUPPORTED, language_scope


def freeze(value):
    return json.loads(json.dumps(value.get("state", value), ensure_ascii=False))


def make_fixture():
    result = {"locales": {language: {} for language in SUPPORTED}, "source_names": {}, "source_skills": {}}
    for race in ("zetans", "symbionts", "automatons"):
        with tempfile.TemporaryDirectory(prefix="alien-localized-ui-") as directory:
            world = World(str(Path(directory) / "world.sqlite3"), speed=1, now=1_900_000_000)
            try:
                initial = freeze(world.register("Konto", "offline-localization-only"))
                owner, planet_id = initial["player"]["id"], initial["home_id"]
                world.action(owner, {"type": "choose_race", "race_id": race, "request_id": "localized-" + race})
                planet = world.data["planets"][planet_id]
                planet["name"] = "Rój"
                locked_data = deepcopy(world.data)
                player = world.data["players"][owner]
                planet["resources"] = {key: 100_000_000 for key in ("metal", "crystal", "fuel")}
                for key in world._specs(owner, "buildings"):
                    planet["buildings"][key] = 4 if key in UNIQUE_BUILDINGS[race] else 8
                for key in world._specs(owner, "research"):
                    player["research"][key] = 4 if key in UNIQUE_RESEARCH[race] else 8
                for key in world._specs(owner, "ships"):
                    planet["ships"][key] = 7
                ready_data = deepcopy(world.data)
                with language_scope("pl"):
                    ready = freeze(world.state(owner, planet_id))
                result["source_names"][race] = {
                    kind: {entry["key"]: entry["name"] for entry in ready["catalog"][kind]}
                    for kind in ("buildings", "research", "ships")
                }
                result["source_skills"][race] = {node["id"]: node["name"] for node in ready["skill_tree"]["nodes"]}
                for entry in ready["catalog"]["buildings"]:
                    planet["buildings"][entry["key"]] = entry["max_level"]
                for entry in ready["catalog"]["research"]:
                    player["research"][entry["key"]] = entry["max_level"]
                maximum_data = deepcopy(world.data)
                for language in SUPPORTED:
                    states = {}
                    with language_scope(language):
                        for label, snapshot in (("locked", locked_data), ("ready", ready_data), ("maximum", maximum_data)):
                            world.data = deepcopy(snapshot)
                            states[label] = freeze(world.state(owner, planet_id))
                    result["locales"][language][race] = states
            finally:
                world.close()
    return result


if __name__ == "__main__":
    destination = Path(sys.argv[1])
    destination.parent.mkdir(parents=True, exist_ok=True)
    fixture = make_fixture()
    destination.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
    print(f"{destination}: {len(fixture['locales'])} languages × 3 races × 3 progression states")
