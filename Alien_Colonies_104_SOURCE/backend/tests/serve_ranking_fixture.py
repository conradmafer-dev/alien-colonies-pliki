import copy,json,pathlib,sys,time,os
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import app

root=pathlib.Path(__file__).resolve().parents[2]
w=app.World(':memory:',now=time.time())
account=w.register('ZZZ Commander','local-fixture-password-only')
owner=account['state']['player']['id']
w.action(owner,{'type':'choose_race','race_id':'zetans'})
home=w._owned(owner)
home['name']='Very Long Colony Name For Header Fit'
home['ships']['scout']=8
template=copy.deepcopy(w._player(owner))
for i in range(61):
 pid=f'fixture-pilot-{i:03}'
 w.data['players'][pid]={**copy.deepcopy(template),'id':pid,'name':f'Commander {i:03}'}
 # Separate actual asset holders, rather than scoring operation summaries.
 w.data['fleets'][pid]={'id':pid,'owner_id':pid,'origin_id':home['id'],'target_id':home['id'],
   'ships':{'scout':100+i},'mission':'alliance_defense','status':'holding',
   'seconds':1000000,'arrives_at':w.now+1000000,'hold_until':w.now+1000000,
   'cargo':dict.fromkeys(app.RESOURCES,0),'swarm_crystals':0}
w.data['alien']['next_expansion_at']=w.now+1000000
w._save()
port=int(os.environ.get('RANKING_FIXTURE_PORT','18793'))
fixture={'token':account['token'],'url':f'http://127.0.0.1:{port}','state':w.state(owner)}
(root/'tests/fixtures').mkdir(exist_ok=True)
(root/'tests/fixtures/ranking92.json').write_text(json.dumps(fixture,ensure_ascii=False))
print('Local ranking fixture ready: 62 synthetic empires',flush=True)
if os.environ.get('RANKING_WEB_FIXTURE') == '1':
 import website
 website.install_website(hosted=False,origin=f'http://127.0.0.1:{port}')
app.build_server(w,'127.0.0.1',port).serve_forever()
