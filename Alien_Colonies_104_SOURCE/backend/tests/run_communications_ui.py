"""Launch Godot and the disposable server together in one local environment."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot',required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='alien-chat-ui-') as directory:
        temp=Path(directory)
        fixture=temp/'fixture.json'
        environment=dict(os.environ,XDG_DATA_HOME=str(temp/'userdata'),GODOT_SILENCE_ROOT_WARNING='1')
        server=subprocess.Popen([sys.executable,str(ROOT/'tests/serve_communications_fixture.py'),str(fixture)],
                                cwd=ROOT,env=environment,stdout=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if fixture.is_file():break
                if server.poll() is not None:raise RuntimeError('Fixture server failed.')
                time.sleep(.05)
            else:raise RuntimeError('Fixture server did not become ready.')
            result=subprocess.run([args.godot,'--headless','--path',str(ROOT),
                'res://tests/test_communications_078.tscn','--',str(fixture)],cwd=ROOT,env=environment,timeout=90)
            return result.returncode
        finally:
            server.terminate()
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)

if __name__=='__main__':raise SystemExit(main())
