"""Exercise alliance management and dispatch UI against the actual authenticated API."""
import argparse
import json
import os
import socket
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from server.main import World, build_server, blank_ships, Handler
from server.i18n import language_scope

NOW = 1900000000

class LostReplyHandler(Handler):
    """Commit one chat message, then drop its response to exercise safe retry."""
    def _json(self, status, data):
        alliance = data.get('alliance') or {}
        chat = alliance.get('chat', [])
        if (status == 200 and self.command == 'POST' and self.path == '/api/alliance'
                and chat and chat[-1]['text'] == 'Joint operation · pl'
                and not getattr(self.server, 'dropped_chat_reply', False)):
            self.server.dropped_chat_reply = True
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        return super()._json(status, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('godot'); parser.add_argument('--screenshots')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='alien-alliance-ui-') as temporary:
        directory = Path(temporary)
        world = World(directory/'world.sqlite3', now=NOW, speed=1000)
        accounts = {}
        for key, name, race in [('leader','AllianceCaptain','zetans'),('member','AllianceEngineer','automatons'),('enemy','RivalEmperor','symbionts'),('solo','LoneVoyager','zetans')]:
            account=world.register(name,'alliance-ui-password')
            pid=account['state']['player']['id']
            world.action(pid, {'type':'choose_race','race_id':race})
            planet=world._owned(pid)
            planet['ships']={**blank_ships(),'frigate':40,'cruiser':20,'scout':10}
            planet['resources']={k:10**9 for k in ('metal','crystal','fuel')}
            world._player(pid)['protected_until']=0 if key in ('enemy','member') else NOW+86400
            accounts[key]={'id':pid,'token':account['token'],'planet_id':planet['id'],'name':name}
        sequence=0
        def act(key, action, **body):
            nonlocal sequence
            sequence+=1
            return world.alliance_action(accounts[key]['id'],dict(action=action,request_id='ui-fixture-'+str(sequence),**body))
        alliance=act('leader','create',name='Sentinels of Orion',tag='ORI',description='Guardians against the Swarm and rival empires.')['alliance']['id']
        act('leader','invite',player_id=accounts['member']['id'])
        act('member','accept_invite',alliance_id=alliance)
        world._capture_planetary_intel(accounts['leader']['id'],world._owned(accounts['enemy']['id']))
        world._save()
        fixture={'accounts':accounts,'states':{},'enemy':accounts['enemy']['planet_id']}
        for locale in ('pl','en','de','es','fr'):
            with language_scope(locale):
                fixture['states'][locale]={key:world.state(account['id']) for key,account in accounts.items()}
        (directory/'fixture.json').write_text(json.dumps(fixture,ensure_ascii=False))
        start=time.monotonic()
        world.advance=lambda *a,**k:setattr(world,"now",NOW+time.monotonic()-start)
        server=build_server(world,'127.0.0.1',0)
        server.RequestHandlerClass=LostReplyHandler
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        command=[args.godot,'--path',str(root),'--audio-driver','Dummy','--max-fps','60']
        command += ['--display-driver','x11','--rendering-method','gl_compatibility'] if args.screenshots else ['--headless']
        command += ['tests/test_alliance_ui_0100.tscn','--',str(directory/'fixture.json'),f'http://127.0.0.1:{server.server_address[1]}']
        if args.screenshots: command.append(args.screenshots)
        try: return subprocess.run(command,env=dict(os.environ,XDG_DATA_HOME=str(directory/'userdata')),timeout=150).returncode
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3);world.close()

if __name__=='__main__':raise SystemExit(main())
