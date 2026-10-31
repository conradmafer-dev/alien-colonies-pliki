"""Existing mission paths retain ownership across new alliance transitions."""
import copy
import unittest
from server.main import World, GameError, blank_ships

class AllianceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.w = World(':memory:', now=1900000000, speed=1000)
        self.addCleanup(self.w.close)
        self.players = []
        for name in ('TransportOne', 'TransportTwo', 'TransportThree'):
            pid = self.w.register(name, 'transport-test-password')['state']['player']['id']
            self.w.action(pid, {'type':'choose_race', 'race_id':'zetans'})
            p = self.w._owned(pid)
            p['ships'] = {**blank_ships(), 'cargo':10, 'frigate':10}
            p['resources'] = dict.fromkeys(('metal','crystal','fuel'),100000000.)
            self.players.append(pid)
        self.a,self.b,self.c = self.players
        self.origin,self.target = self.w._owned(self.a),self.w._owned(self.b)
        self.w.alliance_action(self.a, {'action':'create','name':'Transport Alliance','tag':'TRA','request_id':'create-transports'})
        self.alliance = self.w._alliance_for(self.a)
        self.w._alliance_join(self.b,self.alliance,'member')
        self.w._alliance_join(self.c,self.alliance,'member')
        self.w._capture_planetary_intel(self.a,self.target)
        self.payload = {'type':'fleet','mission':'transport','planet_id':self.origin['id'],'target_id':self.target['id'],
                        'ships':{'cargo':2},'cargo':{'metal':120,'crystal':45,'fuel':10},'request_id':'cargo-alliance'}
    def dispatch(self):
        self.w.action(self.a,self.payload)
        return next(f for f in self.w.data['fleets'].values() if f['owner_id']==self.a)
    def arrive(self,f):
        self.w.now=f['arrives_at'];self.w._complete_fleet(f)
    def test_transport_credits_recipient_once_and_returns_own_ships(self):
        stocks=dict(self.target['resources']); ownships=dict(self.origin['ships'])
        f=self.dispatch();self.w.action(self.a,self.payload)
        self.assertEqual(sum(x['owner_id']==self.a for x in self.w.data['fleets'].values()),1)
        self.arrive(f)
        self.assertEqual(f['status'],'returning')
        for k,n in self.payload['cargo'].items():
            self.assertEqual(self.target['resources'][k],stocks[k]+n)
        self.arrive(f)
        self.assertEqual(self.origin['ships'],ownships)
        before=copy.deepcopy(self.w.data);self.w._complete_fleet(f);self.assertEqual(before,self.w.data)
    def test_departed_recipient_returns_cargo_to_sender(self):
        stocks=dict(self.target['resources']);before=dict(self.origin['resources'])
        f=self.dispatch();fuel=f['fuel_paid']
        self.w.alliance_action(self.b,{'action':'leave','request_id':'leave-transport'})
        self.arrive(f)
        self.assertEqual(self.target['resources'],stocks)
        self.assertEqual(f['cargo'],self.payload['cargo'])
        self.arrive(f)
        for k in before:
            self.assertEqual(self.origin['resources'][k],before[k]-(fuel if k=='fuel' else 0))
    def test_changed_recipient_cannot_redirect_cargo_even_to_another_ally(self):
        stocks=dict(self.target['resources']);f=self.dispatch()
        self.target['owner_id']=self.c
        self.arrive(f)
        self.assertEqual(self.target['resources'],stocks)
        self.assertEqual(f['cargo'],self.payload['cargo'])
    def test_alliance_fleet_name_and_incoming_warning_survive_fog(self):
        self.w._player(self.b)['protected_until']=0
        self.w.alliance_action(self.b,{'action':'leave','request_id':'leave-for-enemy'})
        self.w.now+=86401
        self.w._capture_planetary_intel(self.a,self.target)
        op=self.w.alliance_operation(self.a,{'action':'create','target_id':self.target['id'],'delay_seconds':600,'request_id':'create-attack-001'})
        result=self.w.alliance_operation(self.c,{'action':'join','operation_id':op['operation_id'],'planet_id':self.w._owned(self.c)['id'],'ships':{'frigate':2},'request_id':'join-attack-0001'})
        fleet=self.w.data['fleets'][result['fleet_id']]
        own=next(f for f in self.w.state(self.c)['fleets'] if f['id']==fleet['id'])
        self.assertEqual(own['target_name'],self.target['name'])
        warning=self.w.state(self.b)['incoming_attacks']
        self.assertTrue(any(f['id']==fleet['id'] for f in warning))

if __name__=='__main__':unittest.main()
