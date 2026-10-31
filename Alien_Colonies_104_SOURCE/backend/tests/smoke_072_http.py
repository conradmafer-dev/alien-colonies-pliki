"""Disposable flat Railway 0.7.2 HTTP check; no public server or credentials."""
from pathlib import Path
import json, sys, tempfile, threading, urllib.request, urllib.error
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'railway'))
import app

with tempfile.TemporaryDirectory(prefix='alien-072-http-') as directory:
 path=Path(directory)/'private_test.sqlite3'
 world=app.World(path,now=1_900_000_000)
 original=world.register('Local QA 072','Temporary-QA-Password-072!')
 token=original['token'];pid=original['state']['player']['id']
 world.action(pid,{'type':'choose_race','race_id':'automatons'})
 world._owned(pid)['resources']['metal']=999999
 world.data.pop('balance_reset_id');world.close()
 world=app.World(path,now=1_900_000_000,apply_balance_reset=True)
 assert world._owned(pid)['resources']['metal']==4000
 assert len(list((Path(directory)/'reset-backups').glob('*.sqlite3')))==1
 server=app.GameHTTPServer(('127.0.0.1',0),world)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 base=f'http://127.0.0.1:{server.server_address[1]}'
 try:
  for route in ('/health','/privacy','/delete-account'):
   with urllib.request.urlopen(base+route,timeout=8) as response:
    assert response.status==200; data=response.read()
    if route=='/health':assert json.loads(data)['version']==app.VERSION
   print(route,200)
  def post(route,payload,bearer=None):
   headers={'Content-Type':'application/json','Accept-Language':'en-US','X-PGR-Client-Version':'31'}
   if bearer:headers['Authorization']='Bearer '+bearer
   with urllib.request.urlopen(urllib.request.Request(base+route,json.dumps(payload).encode(),headers),timeout=8) as response:
    assert response.status==200
    return json.load(response)
  try:
   post('/api/action',{'type':'build','key':'metal_mine'},token)
   raise AssertionError('Pre-reset session remained valid')
  except urllib.error.HTTPError as e: assert e.code==401
  login=post('/api/login',{'name':'Local QA 072','password':'Temporary-QA-Password-072!'})
  token=login['token'];assert login['state']['player']['id']==pid
  assert login['state']['player']['race_id']=='automatons'
  wallet=login['state']['resources']
  started=post('/api/action',{'type':'defense','key':'iron_bastion','amount':1,'request_id':'qa-start'},token)
  task=started['state']['queue'][0];assert 'paid_cost' in task
  cancel={'type':'cancel_project','queue_id':task['id'],'request_id':'qa-cancel'}
  cancelled=post('/api/action',cancel,token)
  assert cancelled['state']['queue']==[]
  assert cancelled['state']['resources']==wallet
  assert cancelled['message'].startswith('Project cancelled.')
  replay=post('/api/action',cancel,token)
  assert replay['state']['resources']==wallet
  registered=post('/api/register',{'name':'Second QA 072','password':'Other-Temporary-QA-Password!'})
  assert len(registered['state']['galaxies'])==6
  print('Disk reset + backup, invalidated old session, preserved login/race, HTTP defense receipt/cancel/replay, registration: OK')
 finally:
  server.shutdown();server.server_close();thread.join(timeout=3);world.close()
