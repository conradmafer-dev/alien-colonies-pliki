"""Build deterministic, local-only UI states; never contact the hosted world.

Run from the project root:
    python3 tests/make_ui_fixture.py /tmp/pogranicze-ui-fixture.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.world_fixture import LocalTestWorld as World


def make_fixture() -> dict:
    with tempfile.TemporaryDirectory(prefix="pogranicze-ui-") as directory:
        world = World(
            db_path=str(Path(directory) / "offline-world.sqlite3"),
            speed=10,
            now=1_900_000_000.0,
        )
        try:
            account = world.register("Konrad", "offline-test-only-password")
            initial = account.get("state", account)
            player = initial["player"]["id"]
            planet = initial["home_id"]
            snapshots = {"initial": initial}
            response = world.action(player, {
                "type": "build", "key": "metal_mine", "planet_id": planet,
            })
            busy = response.get("state", response)
            snapshots["building"] = busy
            deadline = busy["queue"][0]["ends_at"]
            world.advance(deadline + 0.01)
            response = world.state(player, planet)
            snapshots["completed"] = response.get("state", response)
            return snapshots
        finally:
            world.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(make_fixture(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Offline UI fixture: {args.output}")


if __name__ == "__main__":
    main()
