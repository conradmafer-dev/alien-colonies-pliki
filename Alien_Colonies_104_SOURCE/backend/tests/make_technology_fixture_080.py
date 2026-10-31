"""Create synthetic early/late-game UI states; never connects to production."""
import json
import sys
from server import technology
from server.i18n import language_scope
from server.megastructures import empty_project
from tests.world_fixture import LocalTestWorld as World


def fixture():
    world = World(":memory:", now=1900000000)
    account = world.register("Andromeda", "test-password-123")
    pid = account["state"]["player"]["id"]
    world.action(pid, {"type": "choose_race", "race_id": "zetans"})
    player = world.data["players"][pid]
    planet = world.data["planets"][player["home_id"]]
    planet["resources"] = {"metal": 200000, "crystal": 175000, "fuel": 125000}
    planet["buildings"].update(lab=8, shipyard=8, power_plant=8, metal_mine=6, crystal_mine=6, refinery=5)
    player["research"].update(energy_technology=3, computing=4, propulsion=6, weapons=2, fusion_power=2, robotics=5, nanotechnology=4)
    planet["ships"].update(scout=10, frigate=12, cargo=8)
    result = {"early": {}, "late": {}, "open": {}}
    for locale in ("en", "pl", "de", "es", "fr"):
        with language_scope(locale):
            result["early"][locale] = world.state(pid)
    player["research"].update({key: meta["max_level"] for key, meta in technology.RESEARCH.items()})
    planet["buildings"].update(lab=12, shipyard=12, power_plant=12)
    project = empty_project()
    project.update(origin_id=planet["id"], dyson_stage=4, gate_level=1)
    player["megastructure"] = project
    project["energy"] = world._mega_profile(player)["capacity"]
    for locale in ("en", "pl", "de", "es", "fr"):
        with language_scope(locale):
            result["late"][locale] = world.state(pid)
    target = next(p for p in world.data["planets"].values() if p["owner_type"] == "empty" and p["galaxy_id"] == "g6")
    world.action(pid, {"type": "tunnel_open", "target_id": target["id"]})
    world.advance(project["window"]["ready_at"])
    for locale in ("en", "pl", "de", "es", "fr"):
        with language_scope(locale):
            result["open"][locale] = world.state(pid)
    result["target_id"] = target["id"]
    world.db.close()
    return result


if __name__ == "__main__":
    from pathlib import Path
    Path(sys.argv[1]).write_text(json.dumps(fixture(), ensure_ascii=False), encoding="utf-8")
