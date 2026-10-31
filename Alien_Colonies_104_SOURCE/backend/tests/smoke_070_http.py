"""Offline smoke of the flat Railway deployment. In-memory world, localhost only.
Run from any directory: python tests/smoke_070_http.py
Never reads production accounts, saved client sessions or a Railway Volume.
"""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import threading
import urllib.request

R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'railway'))
import app
from i18n import language_scope
w=app.World(':memory:',now=1_900_000_000)
s=app.GameHTTPServer(('127.0.0.1',0),w)
thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start()
base=f'http://127.0.0.1:{s.server_address[1]}'
try:
 for route in ('/health','/privacy','/delete-account'):
  with urllib.request.urlopen(base+route,timeout=8) as r:
   body=r.read(); assert r.status==200
   if route=='/health':assert json.loads(body)['version']==app.VERSION
   print(route,200)
 def post(route,payload,token=None):
  headers={'Content-Type':'application/json','Accept-Language':'en-US'}
  if token:headers['Authorization']='Bearer '+token
  req=urllib.request.Request(base+route,json.dumps(payload).encode(),headers=headers)
  with urllib.request.urlopen(req,timeout=8) as response:
   assert response.status==200
   return json.load(response)
 account=post('/api/register',{'name':'HTTP Local QA','password':'qa-only-not-a-production-account'})
 token=account['token'];pid=account['state']['player']['id']
 result=post('/api/action',{'type':'choose_race','race_id':'automatons'},token)
 assert result['state']['catalog']['defenses'][0]['key']=='iron_bastion'
 # Move simulated world time without delays; all data is in-memory, not live.
 with w.lock:
  home=w._owned(pid); home['buildings']['shipyard']=1
  home['resources']=dict.fromkeys(app.RESOURCES,1000000.0)
 result=post('/api/action',{'type':'defense','key':'iron_bastion','amount':1,'request_id':'http-static'},token)
 assert result['state']['queue'][0]['kind']=='defense'
 with w.lock:
  w._complete_queue(home)
  hive=next(p for p in w.data['planets'].values() if p['owner_id']=='khar' and p['galaxy_id']==home['galaxy_id'])
  assert not w._public_swarm_intel(pid,hive)['has_scout']
 result=post('/api/action',{'type':'fleet','mission':'scout','target_id':hive['id'],'ships':{'scout':1}},token)
 with w.lock:
  fleet=next(f for f in w.data['fleets'].values() if f['owner_id']==pid)
  w._complete_fleet(fleet)
 # Replayed idempotent action gives fresh HTTP state without purchasing twice.
 result=post('/api/action',{'type':'defense','key':'iron_bastion','amount':1,'request_id':'http-static'},token)
 assert result['state']['defenses']['iron_bastion']==1
 observation=next(r for r in result['state']['reports'] if 'scout' in r)
 assert observation['title']=='Scouting report'
 assert observation['scout']['has_scout']
 assert len(observation['scout']['swarm_buildings'])==6
 assert 'intel_snapshot' not in observation
 print('HTTP registration, English race/catalog, defense build, scout report JSON: OK')
finally:
 s.shutdown();s.server_close();thread.join(timeout=3);w.close()
