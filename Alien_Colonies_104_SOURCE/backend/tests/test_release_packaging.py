"""Verify Docker's source allowlist in an isolated directory (not a Docker build)."""
import http.client
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ReleasePackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.stage=Path(self.temp.name)/'app';self.stage.mkdir()
        for line in (ROOT/'Dockerfile').read_text().splitlines():
            if not line.startswith('COPY '):continue
            parts=shlex.split(line)[1:];target=self.stage/parts[-1]
            target.mkdir(parents=True,exist_ok=True)
            for source in parts[:-1]:
                source=ROOT/source
                if source.is_dir():shutil.copytree(source,target,dirs_exist_ok=True)
                else:shutil.copy2(source,target/source.name)
        self.env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','RAILWAY_SERVICE_ID','RAILWAY_VOLUME_MOUNT_PATH','PORT')}
        self.env['PYTHONDONTWRITEBYTECODE']='1'

    def tearDown(self):self.temp.cleanup()

    def test_docker_allowlist_contains_new_module_and_all_runtime_imports(self):
        self.assertTrue((self.stage/'fleet_expansion.py').is_file())
        code="import app, start_web, website, fleet_expansion; assert app.VERSION=='0.11.3'; assert len(fleet_expansion.CAPITAL_ROLES)==4"
        result=subprocess.run([sys.executable,'-c',code],cwd=self.stage,env=self.env,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_real_entrypoint_starts_and_serves_new_assets_from_staged_release(self):
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        log=open(Path(self.temp.name)/'startup.log','w+')
        process=subprocess.Popen([sys.executable,'start_web.py','--local-data',str(Path(self.temp.name)/'data'),'--port',str(port)],
                                 cwd=self.stage,env=self.env,stdout=log,stderr=subprocess.STDOUT)
        try:
            def read(path):
                conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
                try:
                    conn.request('GET',path);r=conn.getresponse();return r.status,r.read()
                finally:conn.close()
            for _ in range(50):
                if process.poll() is not None:break
                try:
                    status,body=read('/health')
                    if status==200:break
                except OSError:pass
                time.sleep(.1)
            else:self.fail('entrypoint did not become healthy')
            self.assertIsNone(process.poll())
            self.assertEqual(json.loads(read('/health')[1])['version'],'0.11.3')
            for path in ('/play/','/play/progression.css','/play/research-tree.js','/play/game.js'):
                self.assertEqual(read(path)[0],200,path)
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            log.close()
