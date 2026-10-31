import test from 'node:test';
import assert from 'node:assert/strict';
import {createEmailFlow} from '../web/play/email-auth.js';

const deferred = () => {let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const flush = async () => {for(let i=0;i<12;i++) await Promise.resolve();};
function harness() {
  let clock=0, starts=0;
  const calls=[],waiters=[],changes=[],accepted=[],discarded=[];
  const handlers={status:async()=>({status:'pending'}),complete:async()=>({token:'game-session',state:{player:{id:'player'}}})};
  const api=async(path,options)=>{
    calls.push({path,...options});
    if(path.endsWith('/start')) return {flow_id:'flow-'+(++starts),poll_secret:'memory-secret-'+starts,expires_in:900,resend_after:60,poll_after:3};
    if(path.endsWith('/status')) return handlers.status(options);
    if(path.endsWith('/complete')) return handlers.complete(options);
    throw Error('unexpected route');
  };
  const controller=createEmailFlow(api,{now:()=>clock,delay:()=>new Promise(resolve=>waiters.push(resolve)),onChange:s=>changes.push(s),onAuthenticated:r=>accepted.push(r),onDiscardedSession:t=>discarded.push(t)});
  const step=async(seconds=3)=>{clock+=seconds*1000;const wake=waiters.shift();assert.ok(wake,'a poll is scheduled');wake();await flush();};
  return {controller,calls,handlers,changes,accepted,discarded,waiters,step,setClock:value=>{clock=value;},open(){controller.configure(true);controller.open();},completeCalls:()=>calls.filter(x=>x.path.endsWith('/complete'))};
}

test('feature stays unavailable without configured backend',async()=>{
  const h=harness();h.controller.open();await h.controller.send('pilot@example.com');assert.equal(h.calls.length,0);assert.equal(h.controller.snapshot().phase,'closed');
});
test('pending mail does not create or claim an empire and proofs only use POST bodies',async()=>{
  const h=harness();h.open();await h.controller.send('pilot@example.com');await h.step();
  assert.equal(h.controller.snapshot().phase,'waiting');assert.equal(h.completeCalls().length,0);assert.equal(h.accepted.length,0);
  assert.deepEqual(h.calls[0].body,{email:'pilot@example.com',client:'web'});
  for(const call of h.calls){assert.equal(call.method,'POST');assert.equal(call.authenticated,false);assert.doesNotMatch(call.path,/secret|\?/);}
  assert.deepEqual(h.calls[1].body,{flow_id:'flow-1',poll_secret:'memory-secret-1'});
  assert.equal('poll_secret' in h.controller.snapshot(),false);h.controller.cancel();
});
test('existing verified address claims the existing empire without asking for a new name',async()=>{
  const h=harness();h.handlers.status=async()=>({status:'ready'});h.open();await h.controller.send('pilot@example.com');await h.step();
  assert.equal(h.accepted.length,1);assert.equal(h.completeCalls().length,1);assert.equal('name' in h.completeCalls()[0].body,false);assert.equal(h.controller.snapshot().phase,'closed');
});
test('new verified address waits for an explicitly chosen empire name',async()=>{
  const h=harness();h.handlers.status=async()=>({status:'needs_name'});h.open();await h.controller.send('new@example.com');await h.step();
  assert.equal(h.controller.snapshot().phase,'name');assert.equal(h.completeCalls().length,0);
  await h.controller.submitName('ab');assert.equal(h.completeCalls().length,0);
  await h.controller.submitName('  New Empire  ');assert.equal(h.completeCalls()[0].body.name,'New Empire');assert.equal(h.accepted.length,1);
});
test('name conflict leaves the verified challenge available for another name',async()=>{
  const h=harness();h.handlers.status=async()=>({status:'needs_name'});h.open();await h.controller.send('new@example.com');await h.step();
  h.handlers.complete=async()=>{throw Object.assign(Error('Name taken'),{status:409});};await h.controller.submitName('Used name');assert.equal(h.controller.snapshot().phase,'name');assert.equal(h.controller.snapshot().error,'Name taken');
  h.handlers.complete=async()=>({token:'new-session',state:{player:{id:'new'}}});await h.controller.submitName('Other name');assert.equal(h.accepted.length,1);assert.equal(h.completeCalls()[1].body.poll_secret,'memory-secret-1');
});
test('cancelling while a status response is pending cannot sign in later',async()=>{
  const h=harness(),response=deferred();h.handlers.status=()=>response.promise;h.open();await h.controller.send('pilot@example.com');await h.step();h.controller.cancel();response.resolve({status:'ready'});await flush();
  assert.equal(h.completeCalls().length,0);assert.equal(h.accepted.length,0);assert.equal(h.controller.snapshot().phase,'closed');
});
test('a session minted after cancellation is revoked rather than adopted',async()=>{
  const h=harness(),response=deferred();h.handlers.status=async()=>({status:'ready'});h.handlers.complete=()=>response.promise;h.open();await h.controller.send('pilot@example.com');await h.step();assert.equal(h.controller.snapshot().phase,'completing');h.controller.cancel();response.resolve({token:'late-session',state:{player:{id:'old'}}});await flush();
  assert.deepEqual(h.discarded,['late-session']);assert.equal(h.accepted.length,0);
});
test('resend cooldown prevents repeat start and replacement ignores old status',async()=>{
  const h=harness(),response=deferred();h.handlers.status=()=>response.promise;h.open();await h.controller.send('pilot@example.com');await h.step();await h.controller.resend();assert.equal(h.calls.filter(x=>x.path.endsWith('/start')).length,1);
  h.setClock(61000);await h.controller.resend();assert.equal(h.calls.filter(x=>x.path.endsWith('/start')).length,2);response.resolve({status:'ready'});await flush();assert.equal(h.completeCalls().length,0);
  h.handlers.status=async()=>({status:'ready'});await h.step();assert.equal(h.completeCalls()[0].body.flow_id,'flow-2');assert.equal(h.accepted.length,1);
});
test('expiry returns to email entry and never claims a session',async()=>{
  const h=harness();h.open();await h.controller.send('pilot@example.com');await h.step(901);assert.equal(h.controller.snapshot().phase,'email');assert.equal(h.completeCalls().length,0);assert.match(h.controller.snapshot().error,/wygasł/);h.controller.cancel();
});
test('wrong original-browser cookie forces a fresh challenge',async()=>{
  const h=harness();h.handlers.status=async()=>{throw Object.assign(Error('Use the original browser'),{status:403});};h.open();await h.controller.send('pilot@example.com');await h.step();assert.equal(h.controller.snapshot().phase,'email');assert.equal(h.completeCalls().length,0);h.controller.cancel();
});
test('temporary network errors retry within the same bounded challenge',async()=>{
  const h=harness();let n=0;h.handlers.status=async()=>{if(!n++)throw Object.assign(Error('Offline'),{status:0});return {status:'ready'};};h.open();await h.controller.send('pilot@example.com');await h.step();assert.equal(h.controller.snapshot().phase,'waiting');assert.equal(h.controller.snapshot().error,'Offline');await h.step();assert.equal(h.accepted.length,1);
});
test('a transient complete error is retried without losing the verified flow',async()=>{
  const h=harness();let n=0;h.handlers.status=async()=>({status:'ready'});h.handlers.complete=async()=>{if(!n++)throw Error('Offline');return {token:'retry-session',state:{player:{id:'p'}}};};h.open();await h.controller.send('pilot@example.com');await h.step();assert.equal(h.controller.snapshot().phase,'waiting');await h.step();assert.equal(h.accepted.length,1);
});
test('disabling configuration invalidates pending work and clears address',async()=>{
  const h=harness();h.open();await h.controller.send('pilot@example.com');h.controller.configure(false);await h.step();assert.equal(h.controller.snapshot().phase,'closed');assert.equal(h.controller.snapshot().email,'');assert.equal(h.calls.length,1);
});

test('email reauthentication cannot create a new empire',async()=>{
  const h=harness();h.controller.configure(true);h.controller.open({expectedPlayerId:'current-player'});h.handlers.status=async()=>({status:'needs_name'});await h.controller.send('new@example.com');await h.step();assert.equal(h.controller.snapshot().phase,'email');assert.equal(h.completeCalls().length,0);assert.equal(h.accepted.length,0);h.controller.cancel();
});
test('email reauthentication revokes a different account and retains the current session',async()=>{
  const h=harness();h.controller.configure(true);h.controller.open({expectedPlayerId:'current-player'});h.handlers.status=async()=>({status:'ready'});await h.controller.send('wrong@example.com');await h.step();assert.equal(h.controller.snapshot().phase,'email');assert.deepEqual(h.discarded,['game-session']);assert.equal(h.accepted.length,0);h.controller.cancel();
});
test('matching email reauthentication returns a fresh verified session',async()=>{
  const h=harness();h.controller.configure(true);h.controller.open({expectedPlayerId:'player'});h.handlers.status=async()=>({status:'ready'});await h.controller.send('pilot@example.com');await h.step();assert.equal(h.accepted.length,1);assert.equal(h.discarded.length,0);
});

test('verified email name stage remains explicit while saving and after a conflict',async()=>{
  const h=harness(),response=deferred();h.handlers.status=async()=>({status:'needs_name'});
  h.open();await h.controller.send('new@example.com');await h.step();
  assert.equal(h.controller.snapshot().nameVerified,true);
  h.handlers.complete=()=>response.promise;
  const saved=h.controller.submitName('Taken Name');
  assert.equal(h.controller.snapshot().phase,'completing');
  assert.equal(h.controller.snapshot().nameVerified,true);
  response.reject(Object.assign(Error('Name taken'),{status:409}));await saved;
  assert.equal(h.controller.snapshot().phase,'name');assert.equal(h.controller.snapshot().nameVerified,true);
  h.controller.cancel();assert.equal(h.controller.snapshot().nameVerified,false);
});
test('verified name stage expires even after polling stopped',async()=>{
  const h=harness();h.handlers.status=async()=>({status:'needs_name'});
  h.open();await h.controller.send('new@example.com');await h.step();
  h.setClock(900000);assert.equal(h.controller.checkExpiry(),true);
  assert.equal(h.controller.snapshot().phase,'email');assert.equal(h.controller.snapshot().nameVerified,false);
  assert.match(h.controller.snapshot().error,/wygasł/);
  await h.controller.submitName('Too Late');assert.equal(h.completeCalls().length,0);
});
test('submitting an expired verified name cannot claim a session before the UI timer runs',async()=>{
  const h=harness();h.handlers.status=async()=>({status:'needs_name'});
  h.open();await h.controller.send('new@example.com');await h.step();h.setClock(901000);
  await h.controller.submitName('Too Late');assert.equal(h.completeCalls().length,0);
  assert.equal(h.controller.snapshot().phase,'email');assert.equal(h.controller.snapshot().nameVerified,false);
});
test('cancelling a name claim discards its late session and does not reset a fresh flow',async()=>{
  const h=harness(),response=deferred();h.handlers.status=async()=>({status:'needs_name'});
  h.open();await h.controller.send('new@example.com');await h.step();h.handlers.complete=()=>response.promise;
  const saved=h.controller.submitName('First Empire');h.controller.cancel();h.controller.open();
  await h.controller.send('second@example.com');
  response.resolve({token:'cancelled-name-session',state:{player:{id:'old'}}});await saved;
  assert.deepEqual(h.discarded,['cancelled-name-session']);assert.equal(h.accepted.length,0);
  assert.equal(h.controller.snapshot().phase,'waiting');assert.equal(h.controller.snapshot().email,'second@example.com');
  assert.equal(h.controller.snapshot().nameVerified,false);h.controller.cancel();
});
