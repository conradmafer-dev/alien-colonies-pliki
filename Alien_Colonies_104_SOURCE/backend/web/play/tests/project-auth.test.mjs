import test from 'node:test';
import assert from 'node:assert/strict';
import {projectNeedsQueue,projectActionHtml,plannedQueuesHtml} from '../planned-queues.js';
import {beginGoogleFlow,completeGoogleFlow} from '../google-auth.js';
const state = () => ({planet_id:'one',queue:[],research_queue:null,planned_orders:[],premium:{queue_planning_active:false},limits:{queue_waiting:10},catalog:{buildings:[]}});
const item = () => ({key:'mine',level:1,max_level:20,enabled:true,planning_enabled:false,planning_eligible:true});

test('idle free lane has one normal action; busy lane replaces it with a clickable queue action',()=>{
 const s=state(),i=item();const normal=projectActionHtml(s,i,'build',false,{normalLabel:'Ulepsz'});
 assert.equal((normal.match(/<button/g)||[]).length,1);assert.match(normal,/data-project="mine"/);assert.doesNotMatch(normal,/data-plan-project|Premium/);
 s.queue=[{kind:'build',key:'mine'}];i.enabled=false;
 const queued=projectActionHtml(s,i,'build',false,{normalLabel:'Ulepsz'});
 assert.equal((queued.match(/<button/g)||[]).length,1);assert.match(queued,/data-plan-project="mine"/);assert.match(queued,/Dodaj do kolejki/);assert.doesNotMatch(queued,/ disabled|Premium/);
});
test('build lanes are local, research shared, ships and defenses share a lane',()=>{
 const s=state();s.queue=[{kind:'build',key:'mine'}];assert.equal(projectNeedsQueue(s,'ship'),false);
 s.queue=[{kind:'defense',key:'turret'}];assert.equal(projectNeedsQueue(s,'ship'),true);assert.equal(projectNeedsQueue(s,'defense'),true);assert.equal(projectNeedsQueue(s,'build'),false);
 s.research_queue={kind:'research',planet_id:'two'};assert.equal(projectNeedsQueue(s,'research'),true);
 s.queue=[];s.planned_orders=[{kind:'build',planet_id:'two'}];assert.equal(projectNeedsQueue(s,'build'),false);
 s.planned_orders.push({kind:'build',planet_id:'one'});assert.equal(projectNeedsQueue(s,'build'),true);
});
test('locked, maximum and submitting actions stay disabled without a premium callout',()=>{
 const s=state(),i=item();s.queue=[{kind:'build'}];i.planning_eligible=false;
 assert.match(projectActionHtml(s,i,'build'),/ disabled/);
 i.planning_eligible=true;assert.match(projectActionHtml(s,i,'build',true),/ disabled/);
 i.level=i.max_level;const max=projectActionHtml(s,i,'build');assert.match(max,/Maks. poziom/);assert.doesNotMatch(max,/data-plan-project/);
});
test('premium planning respects the server flag and waiting limit',()=>{
 const s=state(),i=item();s.premium.queue_planning_active=true;s.queue=[{kind:'build'}];
 assert.match(projectActionHtml(s,i,'build'),/ disabled/);
 i.planning_enabled=true;assert.doesNotMatch(projectActionHtml(s,i,'build'),/ disabled/);
 s.planned_orders=Array.from({length:10},()=>({kind:'build',planet_id:'one'}));assert.match(projectActionHtml(s,i,'build'),/ disabled/);
});
test('empty planning panels disappear; real orders retain management without an upsell button',()=>{
 const s=state();assert.equal(plannedQueuesHtml(s),'');s.planned_orders=[{id:'a',kind:'build',planet_id:'one',key:'mine',name:'Mine',level:2}];
 const panel=plannedQueuesHtml(s);assert.match(panel,/data-remove-planned="a"/);assert.doesNotMatch(panel,/data-queue-subscription|Premium|Brak zaplanowanych/);
 assert.equal(plannedQueuesHtml(s,{lanes:['research']}),'');
});
function flowHarness(status='ready') {
 const calls=[];const popup={closed:false,location:{replace(url){this.url=url;}},close(){this.closed=true;}};
 const api=async(endpoint,options)=>{calls.push({endpoint,...options});if(endpoint.endsWith('/start'))return {flow_id:'flow',poll_secret:'secret',authorization_url:'https://game.test/api/auth/google/open?flow=flow&open=one-use',expires_in:600,poll_after:3};if(endpoint.endsWith('/status'))return {status};return {token:'session',state:{player:{id:'player'}}};};
 return {calls,popup,api,options:{origin:'https://game.test',openWindow:()=>popup,delay:async()=>{}}};
}
test('Google existing login keeps secrets in POST bodies and opens only the same-origin initiation page',async()=>{
 const h=flowHarness();const outcome=await beginGoogleFlow(h.api,h.options);
 assert.equal(outcome.result.token,'session');assert.equal(h.calls[0].body.client,'web');assert.equal(h.calls[0].authenticated,false);
 assert.equal(h.calls.find(call=>call.endpoint.endsWith('/status')).body.poll_secret,'secret');assert.equal(h.calls.find(call=>call.endpoint.endsWith('/complete')).method,'POST');
 assert.doesNotMatch(h.popup.location.url,/secret|session/);assert.equal(h.popup.opener,null);assert.equal(h.popup.closed,true);
});
test('Google account linking explicitly reauthenticates the current session',async()=>{
 const h=flowHarness();await beginGoogleFlow(h.api,{...h.options,mode:'link',password:'current-password'});
 assert.equal(h.calls[0].authenticated,true);assert.deepEqual(h.calls[0].body,{mode:'link',client:'web',password:'current-password'});
});
test('new Google subject is not claimed before a chosen empire name',async()=>{
 const h=flowHarness('needs_name');const outcome=await beginGoogleFlow(h.api,h.options);
 assert.equal(outcome.needsName,true);assert.equal(h.calls.some(call=>call.endpoint.endsWith('/complete')),false);
 await completeGoogleFlow(h.api,outcome.flow,'New Empire');assert.equal(h.calls.at(-1).body.name,'New Empire');
});
test('popup blocking and a closed pending popup report failure without claiming a session',async()=>{
 await assert.rejects(beginGoogleFlow(async()=>{throw Error('must not call API');},{openWindow:()=>null}),/wyskakujące/);
 const h=flowHarness('pending');h.popup.closed=true;await assert.rejects(beginGoogleFlow(h.api,h.options),/anulowane/);
 assert.equal(h.calls.some(call=>call.endpoint.endsWith('/complete')),false);
});
test('unexpected external authorization URL is rejected before navigation',async()=>{
 const h=flowHarness();const api=async(endpoint,options)=>endpoint.endsWith('/start') ? {flow_id:'flow',poll_secret:'secret',authorization_url:'https://attacker.test/api/auth/google/open'}:h.api(endpoint,options);
 await assert.rejects(beginGoogleFlow(api,h.options),/rozpocząć/);assert.equal(h.popup.location.url,undefined);assert.equal(h.popup.closed,true);
});
test('Google cancellation after verification prevents a late ready response claiming a session',async()=>{
 const h=flowHarness();let current=true;
 const api=async(endpoint,options)=>{const response=await h.api(endpoint,options);if(endpoint.endsWith('/status'))current=false;return response;};
 await assert.rejects(beginGoogleFlow(api,{...h.options,isCurrent:()=>current}),error=>error.cancelled===true);
 assert.equal(h.calls.some(call=>call.endpoint.endsWith('/complete')),false);assert.equal(h.popup.closed,true);
});
test('Google verified-name result carries a bounded expiry for the separate name step',async()=>{
 const h=flowHarness('needs_name'),before=Date.now();const outcome=await beginGoogleFlow(h.api,h.options);
 assert.ok(outcome.expiresAt>=before+599000);assert.ok(outcome.expiresAt<=Date.now()+600000);
 assert.equal(h.calls.some(call=>call.endpoint.endsWith('/complete')),false);
});
