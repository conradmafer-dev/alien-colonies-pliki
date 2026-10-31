"""Run bounded Godot coalition replay UI against deterministic full-event fixtures."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SHIPS=('scout','cargo','colonizer','frigate','cruiser','interceptor','siege','freighter')
RACES=('zetans','automatons','symbionts')
DEFENSE={'zetans':'phase_sentinel','automatons':'iron_bastion','symbionts':'rooted_spore'}


def dense_record():
    record={'schema':1,'planet':{'name':'Verdant Prime','art_key':'worlds/planet_jungle'},
            'outcome':'unresolved','rounds':[],'participant_results':[],
            'damage_rule':'proportional_effective_hull'}
    for side,count in [('attacker',5),('defender',6)]:
        team={'name':'Coalition','race':'mixed','units':[],'initial':{},'losses':{},'participants':[]}
        for i in range(count):
            race=RACES[i%3];fid=f'{side}-{i}'
            owner=f'{side}-owner-{i}'
            name=['Orion','Lia','Andromeda commander with a very long player name','Nova','Cygnus','Delta'][i]
            participant={'formation_id':fid,'owner_id':owner,'owner_name':name,'race':race}
            team['participants'].append(participant)
            shipkeys=list(SHIPS)+([DEFENSE[race]] if side=='defender' and i==0 else [])
            for j,key in enumerate(shipkeys):
                unique=f'{fid}:{key}'
                unit={**participant,'key':unique,'unit_key':key,'name':f'{name} · {key.title()}',
                      'unit_name':key.title(),'hull':100+j*25,'attack':10+j,
                      'art_key':f'races/{race}/{key}','stationary':key not in SHIPS}
                team['units'].append(unit);team['initial'][unique]={'count':20,'wounds':0.0};team['losses'][unique]=6
            record['participant_results'].append({**participant,'side':side,
                'initial':dict.fromkeys(shipkeys,20),'survivors':dict.fromkeys(shipkeys,14),'losses':dict.fromkeys(shipkeys,6),
                'cargo':{'metal':1000+i*151,'crystal':300+i*37,'fuel':50+i*19} if side=='attacker' else {},
                'swarm_crystals':2 if side=='attacker' and i==2 else 0,'recovered_metal':85 if i==1 else 0})
        record[side]=team
    state={side:copy.deepcopy(record[side]['initial']) for side in ('attacker','defender')}
    for ri in range(6):
        r={'before':copy.deepcopy(state),'hits':{},'heals':{},'after_damage':{},'after':{},
           'salvos':{'attacker':3400,'defender':2800},'formation_salvos':{}}
        for side in ('attacker','defender'):
            r['formation_salvos'][side]={p['formation_id']:680 for p in record[side]['participants']}
            r['hits'][side]=[];r['heals'][side]=[]
            for unit in record[side]['units']:
                key=unit['key'];before=copy.deepcopy(state[side][key])
                after={'count':before['count']-1,'wounds':before['wounds']+20}
                r['hits'][side].append({'key':key,'before':before,'after':after,'destroyed':1,'damage':unit['hull']+20,'blocked':5})
                state[side][key]=copy.deepcopy(after)
            r['after_damage'][side]=copy.deepcopy(state[side])
            for unit in record[side]['units']:
                key=unit['key'];before=copy.deepcopy(state[side][key]);after={**before,'wounds':before['wounds']-10}
                r['heals'][side].append({'key':key,'before':before,'after':after,'healed':10})
                state[side][key]=copy.deepcopy(after)
            r['after'][side]=copy.deepcopy(state[side])
        record['rounds'].append(r)
    record['final']=copy.deepcopy(state)
    return record


def solo_record(dense):
    result=copy.deepcopy(dense);result.pop('participant_results');result.pop('damage_rule')
    for side in ('attacker','defender'):
        result[side]['units']=[unit for unit in result[side]['units'] if unit['formation_id']==f'{side}-0']
        result[side]['race']='zetans';result[side]['name']='Solo';result[side].pop('participants')
        for unit in result[side]['units']:
            for key in ('formation_id','owner_id','owner_name','race','unit_key'):unit.pop(key,None)
    for r in result['rounds']:
        r.pop('formation_salvos')
        for side in ('attacker','defender'):
            keys={unit['key'] for unit in result[side]['units']}
            for field in ('hits','heals'):r[field][side]=[event for event in r[field][side] if event['key'] in keys]
    return result


def actual_records():
    # The real operation fixture sends paid fleets, advances to impact and resolves
    # combat. The synthetic fixture above covers a worst-case six-round ledger.
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from tests.test_alliance_operations_0100 import OperationsTests
    from server.battle_replay import public
    from server.i18n import language_scope
    case=OperationsTests();case.setUp()
    try:
        _,_,record=case.battle()
        records={}
        for locale in ('pl','en','de','es','fr'):
            with language_scope(locale): records[locale]=public(record)
        return records
    finally: case.doCleanups()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('godot');parser.add_argument('--screenshots');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    dense=dense_record()
    with tempfile.TemporaryDirectory(prefix='alien-alliance-replay-ui-') as temp:
        directory=Path(temp);path=directory/'fixture.json'
        path.write_text(json.dumps({'dense':dense,'solo':solo_record(dense),'actual':actual_records()},ensure_ascii=False))
        cmd=[args.godot,'--path',str(root),'--audio-driver','Dummy']
        cmd+=['--display-driver','x11','--rendering-method','gl_compatibility'] if args.screenshots else ['--headless']
        cmd+=['tests/test_alliance_replay_ui_0100.tscn','--',str(path)]
        if args.screenshots:cmd.append(args.screenshots)
        return subprocess.run(cmd,env=dict(os.environ,XDG_DATA_HOME=str(directory/'userdata')),timeout=150).returncode

if __name__=='__main__':raise SystemExit(main())
