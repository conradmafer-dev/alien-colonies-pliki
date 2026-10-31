"""Synthetic server-authored observation states for the real Godot UI."""
import json
import sys
from pathlib import Path
from server.main import World
from server.i18n import language_scope

class FixtureWorld(World):
    def _choose_start_planet(self, available):
        wanted=next(s for s in self.data['systems'] if s['galaxy_id']=='g1' and len(s['planet_ids'])==5)
        return next((p for p in available if p['id'] in wanted['planet_ids']),available[0])

def fixture():
    w=FixtureWorld(':memory:',now=1900000000)
    s=w.register('Andromeda','test-password-123')['state'];pid=s['player']['id'];p=w.data['planets'][s['home_id']]
    w.action(pid,{'type':'choose_race','race_id':'zetans'})
    p['resources']={'metal':200000,'crystal':175000,'fuel':125000}
    p['buildings'].update(lab=4,shipyard=4,power_plant=6,metal_mine=5,crystal_mine=4,refinery=3)
    local=[s for s in w.data['systems'] if s['galaxy_id']=='g1'];i=next(i for i,s in enumerate(local) if s['id']==p['system_id'])
    nearby=local[(i+1)%30]
    target=w.data['planets'][nearby['planet_ids'][0]]
    bob=w.register('Orion','test-password-456')['state']['player']['id']
    w.action(bob,{'type':'choose_race','race_id':'automatons'})
    target.update(owner_id=bob,owner_type='player')
    w._ensure_race_buildings(target)
    target['buildings'].update(metal_mine=7,crystal_mine=4,power_plant=5,lab=3)
    target['resources'].update(metal=34000,crystal=15000,fuel=12000)
    result={'home_system':p['system_id'],'target_system':target['system_id'],'target_id':target['id'],
            'unknown_system':local[(i+12)%30]['id']}
    def save(name):
        result[name]={}
        for locale in ('en','pl','de','es','fr'):
            with language_scope(locale):result[name][locale]=w.state(pid)
    save('fresh')
    p['buildings']['observatory']=1;save('basic')
    p['buildings']['observatory']=8;save('advanced')
    target['buildings']['metal_mine']=8;save('advanced_changed')
    w._capture_planetary_intel(pid,target)
    p['buildings']['observatory']=0;save('scouted')
    p['environment']['fields']=sum(p['buildings'].values());save('full')
    w.close()
    return result

if __name__=='__main__':Path(sys.argv[1]).write_text(json.dumps(fixture(),ensure_ascii=False),encoding='utf-8')
