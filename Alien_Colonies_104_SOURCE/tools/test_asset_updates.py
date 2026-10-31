"""Run texture updater regression with real ZIPs and a local HTTP server."""
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="alien-assets-") as directory:
        directory = Path(directory)
        manifest_path, count_path = directory / "manifest.json", directory / "counts.json"
        counts = {}
        count_path.write_text("{}")
        members = {"client/assets/alien_colonies_icon.png": (ROOT / "client/assets/alien_colonies_icon.png").read_bytes(),
                   "client/assets/alien_colonies_icon.png.import": (ROOT / "client/assets/alien_colonies_icon.png.import").read_bytes()}
        for target in re.findall(r'"res://([^"\n]+\.ctex)"', members["client/assets/alien_colonies_icon.png.import"].decode()):
            members[target] = (ROOT / target).read_bytes()

        def make_pack(extra=False):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, data in members.items():
                    archive.writestr(name, data)
                if extra:
                    archive.writestr("client/scripts/unsafe.gd", "extends Node\n")
            return buffer.getvalue()

        payloads = {"valid": make_pack(), "extra": make_pack(True)}

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                counts[self.path] = counts.get(self.path, 0) + 1
                count_path.write_text(json.dumps(counts))
                data = manifest_path.read_bytes() if self.path.endswith("manifest.json") else payloads[self.path.rsplit("/", 1)[1].split(".")[0]]
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        origin = f"http://127.0.0.1:{server.server_port}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        packs = {name: {"id": name, "url": origin + f"/play/content/{name}.zip", "size": len(data),
                       "sha256": hashlib.sha256(data).hexdigest(),
                       "files": [{"path": path, "size": len(value), "sha256": hashlib.sha256(value).hexdigest()}
                                 for path, value in members.items()]} for name, data in payloads.items()}
        fixture = directory / "fixture.json"
        fixture.write_text(json.dumps({"origin": origin, "manifest": str(manifest_path), "counts": str(count_path), "packs": packs}))
        result = subprocess.run([sys.argv[1], "--headless", "--path", str(ROOT), "res://tests/asset_updates93.tscn"],
                                env={**os.environ, "AC93_ASSET_FIXTURE": str(fixture)}, timeout=45)
        server.shutdown()
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
