"""Offline, fictional-account fixture for Godot's six-galaxy UI test."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.world_fixture import LocalTestWorld as World
from server.i18n import language_scope

def main():
    destination=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'tests/fixtures/galaxies_060.json'
    world=World(':memory:',now=1_900_000_000)
    try:
        with language_scope('en'):
            initial=world.register('Offline UI test','not-a-production-password')['state']
            pid=initial['player']['id']
            state=world.action(pid,{'type':'choose_race','race_id':'zetans'})['state']
            payload={'type':'fleet','planet_id':state['planet_id'],'target_id':'s31p1',
                     'mission':'scout','ships':{'scout':1},'allow_unaffordable':True}
            quote=world.preview(pid,payload)
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(json.dumps({'pre_race':initial,'state':state,'quote':quote},ensure_ascii=False),encoding='utf-8')
            print('Wrote offline fixture:',destination)
    finally:world.close()

if __name__=='__main__':main()
