"""Real Godot colony UI and HTTP actions against a disposable local world.
Usage: python -m tests.run_colony_ui_092 /path/to/godot [--screenshots DIR]
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from server.main import World, build_server
from server.i18n import language_scope

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('godot');parser.add_argument('--screenshots');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='alien-colony-092-') as d:
        directory=Path(d);world=World(directory/'world.sqlite3',now=1900000000)
        world.data['alien']['next_expansion_at']=1901000000
        fixture={}
        for race in ('zetans','automatons','symbionts'):
            account=world.register('Nexus '+race,'local-ui-test-password')
            pid=account['state']['player']['id'];p=world._owned(pid)
            world.action(pid,{'type':'choose_race','race_id':race})
            p['resources']={'metal':150000,'crystal':95000,'fuel':38000}
            p['buildings'].update(lab=2,shipyard=2)
            for kind,key,amount in [('ship','frigate',3),('build','metal_mine',1),('research','weapons',1)]:
                world.action(pid,{'type':kind,'key':key,'amount':amount})
            fixture[race]={'token':account['token'],'states':{}}
            for locale in ('en','pl','de','es','fr'):
                with language_scope(locale):fixture[race]['states'][locale]=world.state(pid)
        path=directory/'fixture.json';path.write_text(json.dumps(fixture,ensure_ascii=False))
        server=build_server(world,'127.0.0.1',0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        cmd=[args.godot,'--path',str(root),'--audio-driver','Dummy']
        cmd+=['--display-driver','x11','--rendering-method','gl_compatibility'] if args.screenshots else ['--headless']
        cmd+=['tests/test_colony_ui_092.tscn','--',str(path),f'http://127.0.0.1:{server.server_address[1]}']
        if args.screenshots:cmd.append(args.screenshots)
        try:return subprocess.run(cmd,env=dict(os.environ,XDG_DATA_HOME=str(directory/'userdata')),timeout=120).returncode
        finally:server.shutdown();server.server_close();thread.join(timeout=3);world.close()

if __name__=='__main__':raise SystemExit(main())
