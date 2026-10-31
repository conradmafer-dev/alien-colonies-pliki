"""Run the real Godot auth form against an isolated local HTTP server.

Usage: python -m tests.run_auth_ui_091 /path/to/godot [--screenshots /path/to/png]
Headless by default. A screenshot run needs an existing graphical display.
No production accounts or saved user sessions are read or written.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from server.main import World, build_server


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('godot')
    parser.add_argument('--screenshots')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='alien-auth-091-') as directory:
        world=World(Path(directory)/'world.sqlite3',speed=1,now=1900000000)
        world.register('Existing091','correct-test-password')
        server=build_server(world,'127.0.0.1',0)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        command=[args.godot,'--path',str(root),'--audio-driver','Dummy']
        command+=['--display-driver','x11','--rendering-method','gl_compatibility'] if args.screenshots else ['--headless']
        command+=['tests/test_auth_ui_091.tscn','--',f'http://127.0.0.1:{server.server_address[1]}']
        if args.screenshots:command.append(args.screenshots)
        env=dict(os.environ,XDG_DATA_HOME=str(Path(directory)/'userdata'))
        try:
            result=subprocess.run(command,env=env,timeout=100,check=False)
            assert len(world.data['players'])==2, 'Only the explicitly submitted new account may be created.'
            return result.returncode
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3);world.close()


if __name__=='__main__':
    raise SystemExit(main())
