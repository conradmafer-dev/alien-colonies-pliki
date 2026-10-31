"""Loopback-only synthetic empires for the real browser ranking regression."""
import copy
import json
from pathlib import Path
import sys
import time
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import rankings
import website

website.install_website(hosted=False,origin="")
world=app.World(":memory:",now=time.time())
account=world.register("Reward Commander","local-ranking104-fixture-only")
owner=account["state"]["player"]["id"]
world.action(owner,{"type":"choose_race","race_id":"zetans"})
home=world._owned(owner)
template=copy.deepcopy(world._player(owner))
for index in range(30):
    pid=f"ranking104-fixture-{index:02}"
    world.data["players"][pid]={**copy.deepcopy(template),"id":pid,"name":f"Synthetic {index:02}"}
    world.data["fleets"][pid]={"id":pid,"owner_id":pid,"origin_id":home["id"],"target_id":home["id"],
        "ships":{"scout":1000+index*100},"mission":"alliance_defense","status":"holding",
        "seconds":10000000,"arrives_at":world.now+10000000,"hold_until":world.now+10000000,
        "cargo":dict.fromkeys(app.RESOURCES,0),"swarm_crystals":0}
world.data["alien"]["next_expansion_at"]=world.now+10000000

def configure(case):
    with world._atomic():
        world.advance()
        home["ships"]["scout"]={"first":100000,"fourth":2950,"paused":10,"payout":100000}[case]
        player=world._player(owner)
        player["ranking_reward_units"]=rankings.REWARD_UNIT-70_000 if case=="payout" else rankings.REWARD_UNIT*3//5
        player["swarm_crystals"]=0
        player["ranking_reward_total"]=0
        player["reports"]=[]

class FixtureHandler(website.WebsiteHandler):
    def do_GET(self):
        path=urlsplit(self.path)
        if path.path=="/fixture/reward":
            case=parse_qs(path.query).get("case",["first"])[0]
            if case not in {"first","fourth","paused","payout"}:
                self._json(400,{"ok":False});return
            configure(case)
            self._json(200,{"ok":True});return
        super().do_GET()

configure("first")
server=app.GameHTTPServer(("127.0.0.1",0),world)
server.RequestHandlerClass=FixtureHandler
print(json.dumps({"origin":f"http://127.0.0.1:{server.server_port}","token":account["token"]}),flush=True)
try:server.serve_forever()
finally:server.server_close();world.close()
