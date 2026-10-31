"""Test real localhost GET/POST while scrolling, using extracted Android assets.

No production account or network service is used. Run after extracting the AAB
and overlaying tests/network98.* plus backend/tests/fixtures/android_0112.json.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--android-assets", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / "backend/tests/fixtures/android_0112.json").read_text())["zetans"]["en"]
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.respond("Network state")

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.respond("Network action")

        def respond(self, name):
            state = dict(fixture)
            state["player"] = dict(fixture["player"], name=name)
            state["network_stress"] = [{"id": i, "text": "Read-only integration fixture " * 5} for i in range(3000)]
            body = json.dumps({"ok": True, "state": state, "message": "Local test only"}).encode()
            requests.append({"method": self.command, "path": self.path,
                             "version": self.headers.get("X-PGR-Client-Version")})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="ac98-network-") as directory:
            env = dict(os.environ, XDG_CONFIG_HOME=str(Path(directory) / "config"),
                       XDG_DATA_HOME=str(Path(directory) / "data"))
            assets = args.android_assets.resolve()
            cmd = [str(args.godot.resolve()), "--headless", "--path", str(assets), "--main-pack",
                   str(assets / "assets.sparsepck"), "res://tests/network98.tscn", "--",
                   "http://127.0.0.1:" + str(server.server_port)]
            try:
                result = subprocess.run(cmd, env=env, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, timeout=25)
            except subprocess.TimeoutExpired as error:
                print((error.stdout or b"").decode(), flush=True)
                raise
            print(result.stdout.decode(), flush=True)
            assert result.returncode == 0, result.returncode
            assert requests == [{"method": "GET", "path": "/api/state", "version": "98"},
                                {"method": "POST", "path": "/api/action", "version": "98"}], requests
            print("LOCAL_REQUESTS_VERIFIED", json.dumps(requests), flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
