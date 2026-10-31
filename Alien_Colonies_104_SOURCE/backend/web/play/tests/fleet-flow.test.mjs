import test from 'node:test';
import assert from 'node:assert/strict';
import {createFleetQuoteController, saveFleetDraft, validFleetQuote, fleetQuoteContext} from '../fleet-flow.js';

const good = {seconds:90,fuel_cost:12,capacity:1000,affordable:true};
const payload = (count = 1) => ({planet_id:'home',target_id:'target',mission:'scout',travel_mode:'normal',ships:{scout:count,cargo:2},cargo:{metal:17,crystal:8,fuel:0}});
const tick = () => new Promise(resolve => setImmediate(resolve));
function setup() {
  let draft = {scope:'session1:home:world1',payload:payload()}, timerId = 0;
  const timers = new Map(), calls = [], views = [], pending = [];
  const controller = createFleetQuoteController({read:() => draft,
    setTimer(fn) {timers.set(++timerId,fn); return timerId;},
    clearTimer(id) {timers.delete(id);},
    quote(body) {calls.push(body);return new Promise((resolve,reject) => pending.push({resolve,reject}));},
    onChange:view => views.push(view),
  });
  return {controller,calls,views,pending,timers,setDraft:value => draft=value,
    flush() {const work=[...timers.values()];timers.clear();for(const fn of work) void fn();},
    async resolve(index,result=good) {pending[index].resolve(result);await tick();}};
}

test('editing quantities coalesces into one server quote for the latest draft', async () => {
  const x=setup();x.controller.update();
  x.setDraft({scope:'session1:home:world1',payload:payload(3)});x.controller.update();
  x.setDraft({scope:'session1:home:world1',payload:payload(7)});x.controller.update();
  assert.equal(x.timers.size,1);assert.equal(x.calls.length,0);
  x.flush();assert.equal(x.calls.length,1);assert.equal(x.calls[0].ships.scout,7);
  assert.equal(x.controller.currentQuote(),null);
  await x.resolve(0);assert.equal(x.controller.currentQuote().payload.ships.scout,7);
});

test('completion provides a quote only; no request other than preview is made', async () => {
  const x=setup();x.controller.update();x.flush();await x.resolve(0);
  assert.equal(x.calls.length,1);assert.equal(x.views.at(-1).phase,'ready');
  assert.deepEqual(x.controller.currentQuote().result,good);
});

test('out-of-order response cannot replace newer quantities', async () => {
  const x=setup();x.controller.update();x.flush();
  x.setDraft({scope:'session1:home:world1',payload:payload(2)});x.controller.update();x.flush();
  await x.resolve(1,{...good,fuel_cost:24});
  await x.resolve(0);
  assert.equal(x.controller.currentQuote().payload.ships.scout,2);
  assert.equal(x.controller.currentQuote().result.fuel_cost,24);
});

test('A to B to A never revives the first A response', async () => {
  const x=setup();x.controller.update();x.flush();
  x.setDraft({scope:'session1:home:world1',payload:payload(2)});x.controller.update();x.flush();
  x.setDraft({scope:'session1:home:world1',payload:payload(1)});x.controller.update();x.flush();
  await x.resolve(0);await x.resolve(1);assert.equal(x.controller.currentQuote(),null);
  await x.resolve(2,{...good,fuel_cost:13});assert.equal(x.controller.currentQuote().result.fuel_cost,13);
});

test('logout, navigation and colony change discard timers and late replies', async () => {
  for (const next of [null,{scope:'session2:home:world1',payload:payload()},{scope:'session1:other:world1',payload:{...payload(),planet_id:'other'}}]) {
    const x=setup();x.controller.update();x.flush();
    x.setDraft(next);x.controller.cancel();await x.resolve(0);
    assert.equal(x.controller.currentQuote(),null);assert.equal(x.controller.snapshot().phase,'idle');
  }
});

test('changed world state invalidates a ready quote even before refresh is requested', async () => {
  const x=setup();x.controller.update();x.flush();await x.resolve(0);
  x.setDraft({scope:'session1:home:world2',payload:payload()});
  assert.equal(x.controller.currentQuote(),null);
  x.controller.update();x.flush();await x.resolve(1,{...good,seconds:45});
  assert.equal(x.controller.currentQuote().result.seconds,45);
});

test('slow preview survives repeated polls with growing resources and observation timestamps', async () => {
  const x=setup(), state={planet_id:'home',ships:{scout:7},resources:{metal:100,crystal:100,fuel:20},
    research:{propulsion:1},buildings:{observatory:1},catalog:{ships:[]},
    galaxy:[{id:'system',galaxy_id:'g1',observed_at:100,planets:[{id:'target',system_id:'system',owner_id:'other',owner_type:'player',last_scouted_at:50}]}]};
  const context=fleetQuoteContext(state,payload(),100);
  x.setDraft({scope:context,payload:payload(),stock:{...state.resources}});x.controller.update();x.flush();
  for(let poll=1;poll<=3;poll++) {
    state.server_time=100+poll*30;state.galaxy[0].observed_at=state.server_time;
    state.galaxy[0].planets[0].last_scouted_at=state.server_time;
    state.resources.fuel+=10;
    assert.equal(fleetQuoteContext(state,payload(),state.server_time),context);
    x.setDraft({scope:context,payload:payload(),stock:{...state.resources}});x.controller.update();x.flush();
  }
  assert.equal(x.calls.length,1);await x.resolve(0);assert.ok(x.controller.currentQuote());
  x.controller.update();x.flush();assert.equal(x.calls.length,1);
});

test('same draft gets a fresh server quote after spending, while cheap polls do not repeat it', async () => {
  const x=setup();x.setDraft({scope:'same-world',payload:payload(),stock:{fuel:100}});
  x.controller.update();x.flush();await x.resolve(0);
  x.setDraft({scope:'same-world',payload:payload(),stock:{fuel:120}});x.controller.update();x.flush();
  assert.equal(x.calls.length,1);
  x.setDraft({scope:'same-world',payload:payload(),stock:{fuel:1}});x.controller.update();x.flush();
  assert.equal(x.calls.length,2);assert.equal(x.controller.currentQuote(),null);
  await x.resolve(1,{...good,affordable:false,shortfall:{fuel:11}});
  x.setDraft({scope:'same-world',payload:payload(),stock:{fuel:30}});x.controller.update();x.flush();
  await x.resolve(2);assert.ok(x.controller.currentQuote());
});

test('resource spending during a slow preview cancels that quote and requires a fresh server result', async () => {
  const x=setup();x.setDraft({scope:'same-world',payload:payload(),stock:{fuel:100,dyson_energy:300}});
  x.controller.update();x.flush();
  x.setDraft({scope:'same-world',payload:payload(),stock:{fuel:1,dyson_energy:300}});
  x.controller.update();x.flush();assert.equal(x.calls.length,2);
  await x.resolve(0);assert.equal(x.controller.currentQuote(),null);assert.equal(x.controller.snapshot().phase,'loading');
  await x.resolve(1,{...good,affordable:false,shortfall:{fuel:11}});
  assert.equal(x.controller.currentQuote(),null);assert.equal(x.controller.snapshot().result.affordable,false);
});

test('Dyson energy spending invalidates a ready tunnel quote, including after a growth poll', async () => {
  const x=setup(), tunnel={...payload(),travel_mode:'tunnel'};
  x.setDraft({scope:'same-world',payload:tunnel,stock:{fuel:100,dyson_energy:300}});
  x.controller.update();x.flush();await x.resolve(0,{...good,fuel_cost:0,tunnel:{energy_cost:100}});
  x.setDraft({scope:'same-world',payload:tunnel,stock:{fuel:100,dyson_energy:400}});
  x.controller.update();assert.ok(x.controller.currentQuote());
  x.setDraft({scope:'same-world',payload:tunnel,stock:{fuel:100,dyson_energy:350}});
  assert.equal(x.controller.currentQuote(),null); // Safe even before the UI refresh calls update().
  x.controller.update();x.flush();assert.equal(x.calls.length,2);assert.equal(x.controller.currentQuote(),null);
  await x.resolve(1,{...good,fuel_cost:0,tunnel:{energy_cost:100}});assert.ok(x.controller.currentQuote());
});

test('unannounced spending just before a response cannot be rebased into a ready quote', async () => {
  const x=setup();x.setDraft({scope:'same-world',payload:payload(),stock:{fuel:100,dyson_energy:300}});
  x.controller.update();x.flush();
  x.setDraft({scope:'same-world',payload:payload(),stock:{fuel:1,dyson_energy:300}});
  await x.resolve(0);assert.equal(x.controller.currentQuote(),null);assert.equal(x.controller.snapshot().phase,'waiting');
  x.flush();assert.equal(x.calls.length,2);
  await x.resolve(1,{...good,affordable:false});assert.equal(x.controller.currentQuote(),null);
});

test('unaffordable preview remains disabled, and a polled fuel change can recover it', async () => {
  const x=setup();x.controller.update();x.flush();
  await x.resolve(0,{...good,affordable:false,shortfall:{fuel:10}});
  assert.equal(x.controller.currentQuote(),null);
  x.setDraft({scope:'session1:home:world2:more-fuel',payload:payload()});
  x.controller.update();x.flush();await x.resolve(1);
  assert.equal(x.controller.currentQuote().result.affordable,true);
});

test('delivery during an unaffordable slow quote is not swallowed by rebasing', async () => {
  const x=setup();x.setDraft({scope:'same-world',payload:payload(),stock:{fuel:1}});
  x.controller.update();x.flush();
  x.setDraft({scope:'same-world',payload:payload(),stock:{fuel:100}});
  x.controller.update();x.flush();assert.equal(x.calls.length,1);
  await x.resolve(0,{...good,affordable:false,shortfall:{fuel:11}});
  assert.equal(x.controller.currentQuote(),null);
  // No new production is needed: this poll has exactly the delivered stock.
  x.controller.update();x.flush();assert.equal(x.calls.length,2);
  await x.resolve(1);assert.ok(x.controller.currentQuote());
});

test('invalid or empty drafts do not call the server', () => {
  const x=setup();x.setDraft({scope:'session1',payload:payload(0),reason:'Select a ship'});
  x.controller.update();x.flush();assert.equal(x.calls.length,0);
  assert.equal(x.views.at(-1).reason,'Select a ship');
});

test('missing, negative and nonfinite quote numbers cannot enable dispatch', async () => {
  for (const result of [null,{}, {...good,seconds:undefined},{...good,fuel_cost:undefined},{...good,capacity:undefined},
    {...good,seconds:-1},{...good,fuel_cost:NaN},{...good,capacity:Infinity},{...good,tunnel:{energy_cost:-1}}, {...good,affordable:undefined}]) {
    assert.equal(validFleetQuote(result),false);
    const x=setup();x.controller.update();x.flush();await x.resolve(0,result);
    assert.equal(x.controller.snapshot().phase,'error');assert.equal(x.controller.currentQuote(),null);
  }
});

test('server failure stays disabled and only a fresh update recovers', async () => {
  const x=setup();x.controller.update();x.flush();x.pending[0].reject(new Error('offline'));await tick();
  assert.equal(x.controller.snapshot().phase,'error');assert.equal(x.controller.currentQuote(),null);
  x.controller.update();x.flush();await x.resolve(1);assert.ok(x.controller.currentQuote());
});

test('destination navigation keeps the full composition and cargo without shared mutation', () => {
  const model={state:{planet_id:'home'},fleetTarget:'target',missionSelecting:false};
  const draft=payload(7);saveFleetDraft(model,draft);
  model.missionSelecting=true;model.fleetTarget='other-target';
  assert.equal(model.fleetDraft.ships.scout,7);assert.deepEqual(model.fleetDraft.cargo,{metal:17,crystal:8,fuel:0});
  assert.equal(model.fleetMission,'scout');assert.equal(model.fleetTravelMode,'normal');
  draft.ships.scout=99;assert.equal(model.fleetDraft.ships.scout,7);
  saveFleetDraft(model,{...payload(2),planet_id:'other'});assert.equal(model.fleetDraft.ships.scout,7);
  saveFleetDraft(model,{...payload(1),target_id:''});assert.equal(model.fleetDraft.ships.scout,7);
});
