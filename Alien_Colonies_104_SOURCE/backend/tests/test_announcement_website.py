"""The public website must hand the announcement editor to the game handler."""
from pathlib import Path
import subprocess
import sys
import unittest


class AnnouncementEditorWebsite(unittest.TestCase):
    def test_real_website_route_not_404_and_unindexed(self):
        script = r"""
import http.client
import threading
import app
import website

website.install_website(hosted=False, origin="")
world = app.World(":memory:", now=1920000000.0)
server = app.build_server(world, "127.0.0.1", 0)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    for path in ("/admin/announcement", "/admin/announcement/"):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=4)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            body = response.read()
            assert response.status == 200, (path, response.status, body[:400])
            assert b'noindex,nofollow' in body, path
            assert b'id="publish"' in body and b'id="save"' in body
        finally:
            conn.close()
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=4)
    try:
        conn.request("GET", "/api/public/announcement")
        response = conn.getresponse()
        body = response.read()
        assert response.status == 200 and b'"visible":false' in body, body
    finally:
        conn.close()
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=4)
    world.close()
"""
        run = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=25)
        self.assertEqual(run.returncode,0,run.stderr)


if __name__ == "__main__":
    unittest.main()
