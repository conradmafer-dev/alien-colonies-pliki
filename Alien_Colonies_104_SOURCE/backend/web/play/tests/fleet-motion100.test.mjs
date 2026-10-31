import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {flightPlan,flightProgress,flightSample,reportIconKind} from '../fleet-motion.js';
import {reportTypeIcon} from '../report-icons.js';
const contract=JSON.parse(readFileSync(new URL('./fixtures/fleet-motion100.json',import.meta.url)));
test('ship movement uses authoritative clock and unequal paid segment distances',()=>{
 const before=structuredClone(contract.fleet);
 for(const entry of contract.samples){
  const value=flightSample(contract.fleet,entry.now);
  assert.ok(Math.abs(value.progress-entry.progress)<1e-9);
  assert.equal(value.index,entry.index);assert.ok(Math.abs(value.fraction-entry.fraction)<1e-9);
 }
 assert.deepEqual(contract.fleet,before);
});
test('return reverses the actual path; early recall starts from its turnaround point',()=>{
 const f={...structuredClone(contract.fleet),status:'returning',started_at:1120,arrives_at:1240};
 assert.equal(flightPlan(f).segments[0].from_system_id,'s3');
 assert.equal(flightSample(f,1180).index,0);
 f.map_return_fraction=.5;
 const plan=flightPlan(f);assert.equal(plan.total,2);
 assert.ok(Math.abs(plan.segments[0].from_fraction-2/3)<1e-9);
 f.map_return_fraction=0;assert.equal(flightPlan(f).segments[0].from_system_id,'s1');
});
test('holding is stationary at the target, while tunnels and legacy flights keep their own modes',()=>{
 assert.equal(flightProgress({...contract.fleet,status:'holding'},1001),1);
 const tunnel=structuredClone(contract.fleet);tunnel.route.travel_mode='tunnel';
 assert.equal(flightPlan(tunnel).mode,'tunnel');assert.equal(flightPlan(tunnel).segments.length,1);
 assert.equal(flightPlan({...contract.fleet,route:{}}).segments[0].kind,'legacy');
 const inter=structuredClone(contract.fleet);inter.route.intergalactic=true;
 assert.equal(flightPlan(inter).mode,'intergalactic');
});
test('report types have distinct vector geometry and ignore arbitrary API markup',()=>{
 const kinds=['scout','battle','warning','transport','return','colonization','research','construction','defense','shipyard','skill','protection','empire','recycling'];
 const geometry=kinds.map(kind=>reportTypeIcon({kind}).replace(/class="[^"]+"|data-report-kind="[^"]+"/g,''));
 assert.equal(new Set(geometry).size,kinds.length);
 assert.equal(reportIconKind({system_scout:{}}),'scout');
 assert.equal(reportIconKind({kind:'invalid',battle_replay_available:true}),'battle');
 assert.ok(!reportTypeIcon({kind:'<script>alert(1)</script>'}).includes('<script>'));
});



test('mission cards retain their theme token on outbound, return and holding', async () => {
  const {fleetMarkerToken}=await import('../fleet-motion.js');
  for(const status of ['outbound','returning','holding']) {
    for(const mission of ['scout','transport','attack','colonize','alliance_defense']) {
      assert.equal(fleetMarkerToken({status,mission,art_key:'races/zetans/scout'}),'--teal');
      assert.equal(fleetMarkerToken({status,mission,art_key:'swarm/scout'}),'--gold');
    }
  }
});

