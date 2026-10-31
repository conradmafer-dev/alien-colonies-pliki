"""Run actual Godot report clicks against a disposable authenticated HTTP server."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from server.main import World, build_server, blank_ships
from server.i18n import language_scope
from tests.test_battle_replay_094 import fixture, NOW


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('godot');parser.add_argument('--screenshots');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='alien-replay-ui-') as d:
        directory=Path(d);world=World(directory/'world.sqlite3',now=NOW)
        accounts,f,target=fixture(world)
        world._battle(f,target)
        player,token=accounts[0]
        first=copy.deepcopy(world._player(player)['reports'][0])
        # More formations: 8 ship types + static defense, NPC raid and empty defense.
        f['ships']={k:i+2 for i,k in enumerate(blank_ships())}
        target['ships']={k:i+2 for i,k in enumerate(blank_ships())}
        world._battle(f,target)
        dense=copy.deepcopy(world._player(player)['reports'][0])
        f['ships']={**blank_ships(),'cruiser':3};target['ships']=blank_ships();target['defenses']={}
        world._battle(f,target);empty=copy.deepcopy(world._player(player)['reports'][0])
        world._report(player,'Raport bitwy','Historical text report')
        old=copy.deepcopy(world._player(player)['reports'][0])
        world._player(player)['reports']=[first,dense,empty,old]
        data={'token':token,'states':{}}
        for locale in ('pl','en','de','es','fr'):
            with language_scope(locale):data['states'][locale]=world.state(player)
        (directory/'fixture.json').write_text(json.dumps(data,ensure_ascii=False))
        world.advance=lambda *a,**k:None
        server=build_server(world,'127.0.0.1',0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        cmd=[args.godot,'--path',str(root),'--audio-driver','Dummy']
        cmd+=['--display-driver','x11','--rendering-method','gl_compatibility'] if args.screenshots else ['--headless']
        cmd+=['tests/test_battle_ui_094.tscn','--',str(directory/'fixture.json'),f'http://127.0.0.1:{server.server_address[1]}']
        if args.screenshots:cmd.append(args.screenshots)
        try:return subprocess.run(cmd,env=dict(os.environ,XDG_DATA_HOME=str(directory/'userdata')),timeout=150).returncode
        finally:server.shutdown();server.server_close();thread.join(timeout=3);world.close()

if __name__=='__main__':raise SystemExit(main())
