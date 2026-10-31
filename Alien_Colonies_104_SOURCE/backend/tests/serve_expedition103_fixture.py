"""Isolated loopback-only real backend used by the browser regression."""
import json,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import World,GameHTTPServer
from website import install_website

if __name__=='__main__':
 install_website(hosted=False,origin='')
 with tempfile.TemporaryDirectory() as tmp:
  w=World(str(Path(tmp)/'test.sqlite3'),now=time.time())
  account=w.register('ExpeditionBrowser103','fixture-password-103',_google_verified=True)
  pid=account['state']['player']['id'];w.action(pid,{'type':'choose_race','race_id':'zetans'})
  p=w._owned(pid);p['buildings'].update(expedition_base=6,shipyard=3,lab=4)
  p['ships'].update(scout=10,cargo=10,frigate=100);p['resources']=dict.fromkeys(('metal','crystal','fuel'),100000.)
  w.data['alien']['next_action']=w.now+100000;w._save()
  server=GameHTTPServer(('127.0.0.1',0),w)
  print(json.dumps({'origin':'http://127.0.0.1:'+str(server.server_address[1]),'token':account['token']}),flush=True)
  server.serve_forever()
