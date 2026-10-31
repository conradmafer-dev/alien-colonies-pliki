"""Exercise the actual Godot boot controller against fast and stalled HTTP."""
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="alien-boot95-") as work:
        work = Path(work)
        mode = work / "mode.txt"
        mode.write_text("empty")
        image = (ROOT / "client/assets/alien_colonies_icon.png").read_bytes()
        buffer = io.BytesIO()
        member = "client/assets/boot95_fixture.png"
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(member, image)
        pack = buffer.getvalue()

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                selected = mode.read_text()
                if self.path == "/play/content/test.zip":
                    time.sleep(4.2)
                    payload = pack
                else:
                    if selected == "slow":
                        time.sleep(4.5)
                    manifest = {"schema": 1, "min_client": 95, "max_client": 95, "packs": []}
                    if selected == "download":
                        manifest["packs"] = [{"id": "test", "url": origin + "/play/content/test.zip",
                            "size": len(pack), "sha256": hashlib.sha256(pack).hexdigest(),
                            "files": [{"path": member, "size": len(image),
                                       "sha256": hashlib.sha256(image).hexdigest()}]}]
                    payload = json.dumps({} if selected == "invalid" else manifest).encode()
                try:
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        origin = f"http://127.0.0.1:{server.server_port}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        config = work / "fixture.json"
        config.write_text(json.dumps({"origin": origin, "mode": str(mode)}))
        env = {**os.environ, "AC95_BOOT_FIXTURE": str(config)}
        result = subprocess.run([sys.argv[1], "--headless", "--path", str(ROOT),
                                 "res://tests/boot95.tscn"], env=env, timeout=45)
        server.shutdown()
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
