"""Local-only HTTPS browser fixture. Captures mail locally; never sends email."""
import argparse
import json
from pathlib import Path
import ssl
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import website
from email_signin import EmailSignInService

args = argparse.ArgumentParser()
args.add_argument('--cert', required=True)
args.add_argument('--key', required=True)
args.add_argument('--mail', required=True)
options = args.parse_args()

class FixtureHandler(website.WebsiteHandler):
    def do_GET(self):
        if self.path == '/__fixture/counts':
            with self.server.world.lock:
                count = len(self.server.world.data['players'])
            self._document(json.dumps({'players':count}).encode(), 'application/json', cache='no-store')
            return
        super().do_GET()

class CapturedMailProvider:
    ready = True
    origin = ''
    def send(self, address, link, *, request_id):
        Path(options.mail).write_text(link, encoding='utf-8')

app.Handler = FixtureHandler
world = app.World(':memory:')
server = app.build_server(world, '127.0.0.1', 0)
provider = CapturedMailProvider()
provider.origin = 'https://localhost:' + str(server.server_port)
server.website_origin = provider.origin
server.website_hosted = True
server.email_signin = EmailSignInService(world, provider)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(options.cert, options.key)
server.socket = context.wrap_socket(server.socket, server_side=True)
print(json.dumps({'origin':provider.origin}), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
    world.close()
