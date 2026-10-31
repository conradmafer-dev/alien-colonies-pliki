import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {galaxyLayout,ellipseLayout,hasRingTopology,galaxyConnections,shortestSystemRoute,orbitRadii} from '../galaxy-map.js';
import {createPlayerActivity,productionWindow} from '../player-activity.js';
import {reportDetailsHtml} from '../report-details.js';

const fixture = JSON.parse(process.env.AC_ROUTES_FIXTURE
  ? readFileSync(process.env.AC_ROUTES_FIXTURE)
  : gunzipSync(readFileSync(new URL('./fixtures/rings-navigation.json.gz',import.meta.url))));
const {systems,routes} = fixture;
test('every shortest route matches the authoritative server, including ties and wraparound',()=>{
  for(const expected of routes) {
    const actual=shortestSystemRoute(systems,expected.origin,expected.target);
    assert.deepEqual(actual.system_ids,expected.system_ids,`${expected.origin}→${expected.target}`);
    assert.deepEqual(actual.segments,expected.segments);
    assert.equal(actual.network_distance,expected.distance);
  }
});
test('three concentric rings share one ellipse and expose only real links',()=>{
  assert.equal(hasRingTopology(systems),true);
  for(const [width,height] of [[340,475],[720,530]]) {
    const points=galaxyLayout(systems,width,height);
    const outer=ellipseLayout(30,width,height);
    for(let i=0;i<30;i++)assert.ok(Math.hypot(points[i].x-outer[i].x,points[i].y-outer[i].y)<1e-9);
    assert.equal(new Set(points.map(p=>`${p.x},${p.y}`)).size,60);
    assert.ok(points.every(p=>p.x>20&&p.x<width-20&&p.y>20&&p.y<height-20));
    for(const s of systems.filter(s=>s.ring_order===0)) {
      const point=points[systems.indexOf(s)];
      assert.ok(Math.abs((height/2-point.y)/orbitRadii(width,height).ry-s.ring_radius)<1e-9);
    }
  }
  const links=galaxyConnections(systems);
  assert.equal(links.filter(e=>e.kind==='orbit').length,60);
  assert.equal(links.filter(e=>e.kind==='bridge').length,10);
  assert.equal(new Set(links.map(e=>[e.from_system_id,e.to_system_id].sort().join(':'))).size,70);
});
test('legacy and malformed worlds keep the one-ellipse fallback without invented routes',()=>{
  const old=systems.slice(0,30).map(({id})=>({id}));
  assert.deepEqual(galaxyLayout(old,340,475),ellipseLayout(30,340,475));
  assert.deepEqual(galaxyConnections(old),[]);
  assert.equal(shortestSystemRoute(old,'s1','s2'),null);
  assert.equal(shortestSystemRoute(systems,'s1','other-galaxy'),null);
  assert.equal(hasRingTopology([{...systems[0],ring_size:0}]),false);
});
test('only pending foreground activity can mark state reads; passive polling stays inactive',()=>{
  let clock=0;const activity=createPlayerActivity({now:()=>clock});
  const state={authenticated:true,visible:true,path:'/state?planet_id=p1'};
  for(const options of [{...state,visible:false},{...state,authenticated:false},{...state,path:'/chat'},{...state,method:'POST'}])assert.equal(activity.take(options),0);
  const launch=activity.take(state);assert.ok(launch);activity.acknowledge(launch);
  clock=70000;assert.equal(activity.take(state),0);
  activity.mark();const input=activity.take(state);assert.ok(input);activity.acknowledge(input);
  clock=140000;assert.equal(activity.take(state),0);
});
test('errors retry only after 60 seconds, and late success cannot consume newer input',()=>{
  let clock=0;const activity=createPlayerActivity({now:()=>clock});
  const options={authenticated:true,visible:true,path:'/state'};
  const sent=activity.take(options);activity.mark();
  clock=59999;assert.equal(activity.take(options),0);
  activity.acknowledge(sent);
  clock=60000;const next=activity.take(options);assert.ok(next>sent);
  clock=120000;const retry=activity.take(options);assert.equal(retry,next);
  activity.acknowledge(retry);clock=180000;assert.equal(activity.take(options),0);
  activity.reset();assert.ok(activity.take(options));
});
test('local resource estimates stop at the exact server cutoff, preserve stocks, and resume prospectively',()=>{
  const state={server_time:100,production_status:{paused:false,stops_at:130}};
  assert.deepEqual(productionWindow(state,120),{paused:false,elapsed:20});
  assert.deepEqual(productionWindow(state,140),{paused:true,elapsed:30});
  state.production_status.paused=true;
  assert.deepEqual(productionWindow(state,140),{paused:true,elapsed:0});
  state.server_time=140;state.production_status={paused:false,stops_at:604940};
  assert.deepEqual(productionWindow(state,150),{paused:false,elapsed:10});
  assert.deepEqual(productionWindow({server_time:100},120),{paused:false,elapsed:20});
});

test('whole-system report keeps dated owners, escaped names and no invented detailed intelligence',()=>{
  const report={title:'System scout',at:1000,system_scout:{system_id:'s1',system_name:'Helios',galaxy_id:'g1',scouted_at:900,counts:{own:1,player:1,alien:1,empty:1},planets:[{id:'p1',name:'Old colony',owner_type:'player',owner_name:'Old owner <script>'},{id:'p2',name:'Free',owner_type:'empty'}]}};
  const markup=reportDetailsHtml(report);
  assert.match(markup,/Old owner &lt;script&gt;/);
  assert.match(markup,/Wolna planeta/);
  assert.match(markup,/Właściciele z chwili zwiadu/);
  assert.doesNotMatch(markup,/<script>|report-intel-columns/);
  assert.match(markup,/Zwiad pojedynczej planety/);
  assert.equal((markup.match(/<li>/g)||[]).length,2);
});
