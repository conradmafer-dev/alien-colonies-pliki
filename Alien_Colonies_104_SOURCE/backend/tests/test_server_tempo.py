"""Normal pacing is shared by new worlds and Railway/local entry points."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from server import main


class NormalTempoTests(unittest.TestCase):
    def test_default_world_matches_explicit_normal_production_and_queue_duration(self):
        normal = main.World(":memory:", now=1_900_000_000)
        explicit = main.World(":memory:", speed=1, now=1_900_000_000)
        accelerated = main.World(":memory:", speed=10, now=1_900_000_000)
        try:
            states = [w.register("TempoPilot", "test-password")["state"] for w in (normal, explicit, accelerated)]
            self.assertEqual(states[0]["speed"], 1)
            self.assertEqual(states[0]["production"], states[1]["production"])
            for key, value in states[0]["production"].items():
                self.assertAlmostEqual(states[2]["production"][key], value * 10)
            for i, world in enumerate((normal, explicit)):
                pid = states[i]["player"]["id"]
                world.action(pid, {"type": "choose_race", "race_id": "symbionts"})
                world.action(pid, {"type": "build", "key": "metal_mine"})
            queues = [w.state(states[i]["player"]["id"])["queue"][0] for i, w in enumerate((normal, explicit))]
            self.assertEqual(queues[0]["ends_at"], queues[1]["ends_at"])
        finally:
            for world in (normal, explicit, accelerated):
                world.close()

    def test_railway_and_local_configuration_default_to_one_with_explicit_override(self):
        path = Path(__file__).resolve().parents[1] / "railway" / "run.py"
        spec = importlib.util.spec_from_file_location("railway_tempo_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"app": main}):
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            production = {"RAILWAY_SERVICE_ID": "local-test", "RAILWAY_VOLUME_MOUNT_PATH": str(directory)}
            for local_data, env in ((directory, {}), (None, production)):
                argv = module.configuration(local_data, 8080, env)[1]
                self.assertEqual(argv[argv.index("--speed") + 1], "1")
                argv = module.configuration(local_data, 8080, {**env, "PGR_SPEED": "2"})[1]
                self.assertEqual(argv[argv.index("--speed") + 1], "2")


if __name__ == "__main__":
    unittest.main()
