"""Disposable local server for test_communications_078.tscn; no live accounts.
Usage: python tests/serve_communications_fixture.py /tmp/chat-fixture.json
"""
import json
from pathlib import Path
import signal
import sys
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.main import World,build_server
from server.i18n import language_scope


def main():
    output=Path(sys.argv[1])
    world=World(':memory:',now=time.time())
    world.data['alien']['next_expansion_at']=world.now+1000000
    with language_scope('en'):
        first=world.register('Chat Alpha','local-chat-only-123')
        second=world.register('Chat Beta','local-chat-only-123')
        a,b=first['state']['player']['id'],second['state']['player']['id']
        for account,race in [(a,'zetans'),(b,'symbionts')]:
            world.action(account,{'type':'choose_race','race_id':race,'request_id':'chat-race-'+account})
        world.now-=8
        world.chat_send(a,{'text':'Hello, galaxy!','request_id':'fixture-global-1'})
        world.now+=4
        world.chat_send(a,{'peer_id':b,'text':'Private trade proposal','request_id':'fixture-private-1'})
        world.now+=4
        server=build_server(world,port=0)
        output.write_text(json.dumps({'server_url':'http://127.0.0.1:'+str(server.server_address[1]),
            'token':second['token'],'peer_id':a,'peer_name':'Chat Alpha','state':world.state(b)},ensure_ascii=False))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    stopped=threading.Event()
    for signum in [signal.SIGINT,signal.SIGTERM]:
        signal.signal(signum,lambda *_:stopped.set())
    print(str(output),flush=True)
    stopped.wait()
    server.shutdown();server.server_close();thread.join(timeout=3);world.close()

if __name__=='__main__': main()
