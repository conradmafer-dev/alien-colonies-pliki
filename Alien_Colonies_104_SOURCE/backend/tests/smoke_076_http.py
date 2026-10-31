"""Local-only HTTP timing smoke test of the flat Railway deployment.

Creates an in-memory database and an ephemeral loopback listener. Does not read
live accounts, client sessions, the Railway Volume or any production URL.
"""
from pathlib import Path
import json
import sys
import threading
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'railway'))
import app


def run():
    world=app.World(':memory:',now=time.time())
    server=app.GameHTTPServer(('127.0.0.1',0),world)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f'http://127.0.0.1:{server.server_address[1]}'
    def req(route,payload=None,token=None):
        headers={'Accept-Language':'en','X-PGR-Client-Version':str(app.CLIENT_VERSION_CODE)}
        if token:headers['Authorization']='Bearer '+token
        if payload is not None:headers['Content-Type']='application/json'
        request=urllib.request.Request(base+route,None if payload is None else json.dumps(payload).encode(),headers)
        with urllib.request.urlopen(request,timeout=8) as response:
            assert response.status==200
            return json.load(response)
    checks={}
    try:
        checks['health']=req('/health')
        assert checks['health']['version']=='0.7.7'
        for race in ('zetans','automatons','symbionts'):
            account=req('/api/register',{'name':'QA076 '+race,'password':'Local-test-not-production-076!'})
            token=account['token'];owner=account['state']['player']['id']
            req('/api/action',{'type':'choose_race','race_id':race},token)
            with world.lock:
                home=world._owned(owner)
                home['buildings'].update(shipyard=5,lab=5)
                home['resources']={k:10000000 for k in app.RESOURCES}
            state=req('/api/state',token=token)['state']
            for key in ('shipyard','lab'):
                detail=next(row for row in state['catalog']['buildings'] if row['key']==key)['details']
                speed=next(row for row in detail['metrics'] if row['key'] in ('shipyard_speed_bonus','lab_speed_bonus'))
                assert speed['current']==40 and speed['next']==50
                assert detail['time_examples']
            scout=next(row for row in state['catalog']['ships'] if row['key']=='scout')
            result=req('/api/action',{'type':'ship','key':'scout','amount':2,'seconds':1},token)
            task=result['state']['queue'][0]
            assert task['seconds']==scout['seconds']*2
            assert task['facility_timing']['level']==5
            req('/api/action',{'type':'cancel_project','queue_id':task['id']},token)
            result=req('/api/action',{'type':'research','key':'propulsion'},token)
            task=result['state']['queue'][0]
            original_end=task['ends_at'];original_seconds=task['seconds']
            with world.lock:home['buildings']['lab']=12
            state=req('/api/state',token=token)['state']
            assert state['queue'][0]['ends_at']==original_end
            assert state['queue'][0]['seconds']==original_seconds
            current=next(row for row in state['catalog']['research'] if row['key']=='propulsion')
            assert current['seconds']<original_seconds
            checks[race]={'shipyard_level_5_scout_seconds':scout['seconds'],
                          'lab_level_5_propulsion_seconds':original_seconds,
                          'lab_level_12_new_propulsion_seconds':current['seconds'],
                          'paid_order_matches_quote':True,'active_timer_preserved':True}
        return checks
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3);world.close()

if __name__=='__main__':
    result=run()
    if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
