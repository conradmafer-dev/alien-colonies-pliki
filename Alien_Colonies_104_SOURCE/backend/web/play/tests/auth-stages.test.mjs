/** Actual game.js auth functions with a small DOM adapter; no live provider/API. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {createEmailFlow} from '../email-auth.js';

const source = readFileSync(new URL('../game.js', import.meta.url), 'utf8');
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
};
const flush = async () => { for (let n = 0; n < 16; n++) await Promise.resolve(); };
const session = (token = 'new-session', id = 'new-player') => ({token, state:{player:{id, name:'New Empire'}, planet_id:'home'}});
const failure = status => Object.assign(new Error(`Auth failure ${status}`), {status});

function harness() {
  const elements = new Map(), calls = [], discarded = [], accepted = [], timers = new Map(), waits = [];
  let timerSequence = 0, clock = 1900000000000, emailStatus = 'needs_name';
  const model = {token:'', state:null, busy:false, epoch:0, register:false, tab:'colony',
    googleAuth:{configured:true, require_google_registration:true}, googlePending:null,
    emailAuth:{configured:true}};
  const document = {title:'', activeElement:null, body:{classList:{toggle(){}, add(){}, remove(){}}},
    documentElement:{classList:{toggle(){}, add(){}, remove(){}}}};
  function element(selector) {
    if (!elements.has(selector)) {
      const attrs = new Map(), classes = new Set();
      const el = {id:selector.replace(/^#/, ''), hidden:false, disabled:false, open:false,
        value:'', textContent:'', innerHTML:'', scrollTop:0, inert:false, isConnected:true,
        classList:{toggle(key, force) {const active = force ?? !classes.has(key); active ? classes.add(key) : classes.delete(key); return active;}, add(...keys) {keys.forEach(k => classes.add(k));}, remove(...keys) {keys.forEach(k => classes.delete(k));}, contains(key) {return classes.has(key);}},
        setAttribute(key, value) {attrs.set(key, String(value));}, getAttribute(key) {return attrs.get(key) ?? null;}, removeAttribute(key) {attrs.delete(key);},
        focus() {document.activeElement = el;}, showModal() {el.open = true;}, close() {el.open = false;},
        scrollIntoView() {calls.push(['scrollIntoView', selector]);}, addEventListener(){},
        querySelector(){return null;}, querySelectorAll(){return [];}};
      elements.set(selector, el);
    }
    return elements.get(selector);
  }
  document.querySelector = element;
  document.querySelectorAll = () => [];
  element('#game-screen').hidden = true;
  element('#google-name-error').hidden = true;
  element('#email-auth-error').hidden = true;
  const handlers = {
    begin:async () => ({needsName:true, mode:'login', flow:{flow_id:'google-1', poll_secret:'proof'}, expiresAt:clock + 600000}),
    complete:async () => session(),
    emailComplete:async () => session('email-session'),
    api:async endpoint => {
      if (endpoint.endsWith('/config')) return {configured:true, require_google_registration:true};
      if (endpoint.endsWith('/start')) return {flow_id:'email-1', poll_secret:'email-proof', expires_in:900, resend_after:60, poll_after:3};
      if (endpoint.endsWith('/status')) return {status:emailStatus};
      throw Error('Unexpected API: ' + endpoint);
    },
  };
  const timer = (callback, delay, interval = false) => {const id = ++timerSequence; timers.set(id, {callback, delay, interval}); return id;};
  const context = vm.createContext({
    $, document, model, Date:class extends Date {static now() {return clock;}},
    t:(text, ...values) => String(text).replace(/\{(\d+)\}/g, (_, i) => values[i] ?? ''),
    html:parts => parts.join(''), ApiError:class extends Error {},
    setTimeout:(callback, delay) => timer(callback, delay), clearTimeout:id => timers.delete(id),
    setInterval:(callback, delay) => timer(callback, delay, true), clearInterval:id => timers.delete(id),
    requestAnimationFrame:callback => callback(),
    window:{scrollTo(options) {calls.push(['scrollTo', options]);}},
    emailOwnsBusy:false, emailUiTimer:null, emailDisplayedPhase:'closed', emailAuthEpoch:0,
    emailReauthPlayer:'', googleAuthGeneration:0, googleNameTimer:null,
    pendingQuietRender:false,
    api:async (endpoint, options) => {
      calls.push(['api', endpoint, options]);
      if (endpoint === '/auth/email/complete') return handlers.emailComplete(endpoint, options);
      return handlers.api(endpoint, options);
    },
    beginGoogleFlow:(...args) => handlers.begin(...args),
    completeGoogleFlow:(...args) => handlers.complete(...args),
    revokeSession:async token => {discarded.push(token);},
    storeToken(value) {model.token = value;},
    acceptState(state) {model.state = state; accepted.push(state);},
    toast(message, isError) {calls.push(['toast', message, isError]);},
    renderMain(){}, renderChrome(){}, schedulePoll(){}, prepareGalaxyEntry(){},
  });
  function $(selector) {return element(selector);}
  const emailFlow = createEmailFlow(context.api, {
    now:() => clock, delay:() => new Promise(resolve => waits.push(resolve)),
    onChange:view => context.renderEmailFlow(view),
    onAuthenticated:result => context.acceptGoogleLogin(result),
    onDiscardedSession:token => discarded.push(token),
  });
  context.emailFlow = emailFlow;
  // This source block contains the production functions themselves. The adapter
  // supplies only browser surfaces/API promises, never the transition logic.
  const start = Math.min(...['function syncAuthStage(', 'function showAuth(']
    .map(marker => source.indexOf(marker)).filter(index => index >= 0));
  const end = source.indexOf('function acceptState(');
  assert.ok(start >= 0 && end > start, 'auth functions are available to the adapter');
  vm.runInContext(source.slice(start, end), context);
  context.setAuthMode(false);
  const verifiedGoogle = async () => {await context.signInWithGoogle(); assert.ok(model.googlePending);};
  const verifiedEmail = async () => {
    emailFlow.configure(true); emailFlow.open();
    await emailFlow.send('pilot@example.com');
    const poll = waits.shift(); assert.ok(poll); poll(); await flush();
    assert.equal(emailFlow.snapshot().phase, 'name');
  };
  return {context, model, $, handlers, calls, discarded, accepted, timers, emailFlow,
    verifiedGoogle, verifiedEmail, setEmailStatus(value) {emailStatus = value;},
    advanceClock(milliseconds) {clock += milliseconds;}, get clock() {return clock;}};
}

test('Google verification shows only the naming stage, focused and ready to create', async () => {
  const h = harness(); await h.verifiedGoogle();
  assert.equal(h.$('#auth-screen').hidden, true);
  assert.equal(h.$('#google-name-dialog').open, true);
  assert.equal(h.context.document.activeElement, h.$('#google-empire-name'));
  assert.equal(h.$('#google-name-submit').disabled, false);
  assert.equal(h.$('#game-screen').hidden, true);
});

test('late provider configuration and auth rerenders cannot restore login under Google naming', async () => {
  const h = harness(); await h.verifiedGoogle();
  h.$('#google-empire-name').value = 'Chosen Empire';
  h.context.setAuthMode(true);
  await h.context.loadGoogleAuthConfig(); await h.context.loadEmailAuthConfig();
  h.context.showAuth();
  assert.equal(h.$('#auth-screen').hidden, true);
  assert.equal(h.$('#google-name-dialog').open, true);
  assert.equal(h.$('#google-empire-name').value, 'Chosen Empire');
});

test('verified email hides login, email entry and waiting controls through name completion', async () => {
  const h = harness(); await h.verifiedEmail();
  const pending = deferred(); h.handlers.emailComplete = () => pending.promise;
  h.$('#email-empire-name').value = 'Chosen Empire';
  await h.context.loadGoogleAuthConfig(); await h.context.loadEmailAuthConfig();
  assert.equal(h.$('#email-empire-name').value, 'Chosen Empire');
  assert.equal(h.$('#auth-screen').hidden, true);
  const request = h.emailFlow.submitName('Chosen Empire');
  assert.equal(h.emailFlow.snapshot().phase, 'completing');
  assert.equal(h.$('#auth-screen').hidden, true);
  assert.equal(h.$('#email-address-form').hidden, true);
  assert.equal(h.$('#email-waiting').hidden, true);
  assert.equal(h.$('#email-name-form').hidden, false);
  assert.equal(h.$('#email-name-submit').disabled, true);
  assert.equal(h.$('#email-empire-name').value, 'Chosen Empire');
  assert.match(h.$('#email-auth-title').textContent, /potwierdz/i);
  h.context.setAuthMode(false); h.context.renderEmailFlow(h.emailFlow.snapshot());
  assert.equal(h.$('#auth-screen').hidden, true);
  assert.equal(h.$('#email-name-form').hidden, false);
  pending.reject(failure(409)); await request;
  assert.equal(h.emailFlow.snapshot().phase, 'name');
  assert.equal(h.$('#email-name-form').hidden, false);
  assert.equal(h.$('#email-name-submit').disabled, false);
  assert.equal(h.$('#email-empire-name').value, 'Chosen Empire');
  assert.equal(h.$('#email-auth-error').hidden, false);
  assert.equal(h.$('#auth-screen').hidden, true);
});

test('Google name conflict preserves the verified stage and entered name', async () => {
  const h = harness(); await h.verifiedGoogle();
  h.$('#google-empire-name').value = 'Already Used';
  h.handlers.complete = async () => {throw failure(409);};
  await h.context.submitGoogleName();
  assert.ok(h.model.googlePending);
  assert.equal(h.$('#google-name-dialog').open, true);
  assert.equal(h.$('#auth-screen').hidden, true);
  assert.equal(h.$('#google-empire-name').value, 'Already Used');
  assert.equal(h.$('#google-name-error').hidden, false);
  assert.equal(h.$('#google-name-submit').disabled, false);
});

test('expired or invalid Google proof returns to login rather than trapping the naming stage', async () => {
  for (const status of [401, 403, 404, 410]) {
    const h = harness(); await h.verifiedGoogle();
    h.$('#google-empire-name').value = 'New Empire';
    h.handlers.complete = async () => {throw failure(status);};
    await h.context.submitGoogleName();
    assert.equal(h.model.googlePending, null, String(status));
    assert.equal(h.$('#google-name-dialog').open, false, String(status));
    assert.equal(h.$('#auth-screen').hidden, false, String(status));
    assert.equal(h.$('#auth-error').hidden, false, String(status));
    assert.equal(h.model.busy, false, String(status));
  }
});

test('cancelling Google creation revokes a late session without disturbing a newer pending creation', async () => {
  const h = harness(); await h.verifiedGoogle();
  h.$('#google-empire-name').value = 'Old Empire';
  const old = deferred(); h.handlers.complete = () => old.promise;
  const oldRequest = h.context.submitGoogleName();
  h.context.cancelGoogleName();
  assert.equal(h.$('#auth-screen').hidden, false);
  h.handlers.begin = async () => ({needsName:true, mode:'login', flow:{flow_id:'google-2', poll_secret:'next-proof'}, expiresAt:h.clock + 600000});
  await h.verifiedGoogle();
  h.$('#google-empire-name').value = 'Current Empire';
  const current = deferred(); h.handlers.complete = () => current.promise;
  const currentRequest = h.context.submitGoogleName();
  old.resolve(session('late-session')); await oldRequest;
  assert.deepEqual(h.discarded, ['late-session']);
  assert.equal(h.model.token, '');
  assert.equal(h.model.googlePending.flow.flow_id, 'google-2');
  assert.equal(h.$('#google-name-submit').disabled, true);
  assert.equal(h.$('#google-empire-name').value, 'Current Empire');
  assert.equal(h.$('#auth-screen').hidden, true);
  current.resolve(session('current-session')); await currentRequest;
  assert.equal(h.model.token, 'current-session');
  assert.equal(h.$('#game-screen').hidden, false);
});

test('late Google verification from a cancelled start cannot replace a newer naming stage', async () => {
  const h = harness(), late = deferred(); h.handlers.begin = () => late.promise;
  const oldRequest = h.context.signInWithGoogle();
  h.context.cancelGoogleName();
  h.handlers.begin = async () => ({needsName:true, mode:'login', flow:{flow_id:'new-flow', poll_secret:'proof'}, expiresAt:h.clock + 600000});
  await h.verifiedGoogle();
  h.$('#google-empire-name').value = 'Current Name';
  late.resolve({needsName:true, mode:'login', flow:{flow_id:'old-flow', poll_secret:'old'}, expiresAt:h.clock + 600000});
  await oldRequest;
  assert.equal(h.model.googlePending.flow.flow_id, 'new-flow');
  assert.equal(h.$('#google-empire-name').value, 'Current Name');
  assert.equal(h.model.busy, true);
  assert.equal(h.$('#auth-screen').hidden, true);
});

test('late Google existing-account sessions are revoked after cancellation or session epoch change', async () => {
  for (const change of ['cancel', 'epoch']) {
    const h = harness(), late = deferred(); h.handlers.begin = () => late.promise;
    const request = h.context.signInWithGoogle();
    if (change === 'cancel') h.context.cancelGoogleName();
    else {h.model.epoch++; h.model.token = 'current-session'; h.model.state = session('unused', 'current-player').state;}
    late.resolve({result:session('late-session'), mode:'login'}); await request;
    assert.deepEqual(h.discarded, ['late-session'], change);
    assert.equal(h.accepted.length, 0, change);
    assert.notEqual(h.model.token, 'late-session', change);
  }
});

test('existing Google account goes directly to game without a naming dialog', async () => {
  const h = harness(); h.handlers.begin = async () => ({result:session(), mode:'login'});
  await h.context.signInWithGoogle();
  assert.equal(h.model.token, 'new-session');
  assert.equal(h.$('#google-name-dialog').open, false);
  assert.equal(h.$('#auth-screen').hidden, true);
  assert.equal(h.$('#game-screen').hidden, false);
});

test('email cancellation during creation revokes the late session and restores login', async () => {
  const h = harness(); await h.verifiedEmail();
  const late = deferred(); h.handlers.emailComplete = () => late.promise;
  const request = h.emailFlow.submitName('New Empire');
  h.emailFlow.cancel();
  late.resolve(session('late-email')); await request;
  assert.deepEqual(h.discarded, ['late-email']);
  assert.equal(h.model.token, '');
  assert.equal(h.$('#auth-screen').hidden, false);
  assert.equal(h.$('#email-auth-dialog').open, false);
  assert.equal(h.model.busy, false);
});

test('verified-email expiry leaves naming and allows a fresh email challenge', async () => {
  const h = harness(); await h.verifiedEmail();
  h.advanceClock(901000); h.emailFlow.checkExpiry();
  assert.equal(h.emailFlow.snapshot().phase, 'email');
  assert.equal(h.$('#email-name-form').hidden, true);
  assert.equal(h.$('#email-address-form').hidden, false);
  assert.equal(h.$('#email-auth-error').hidden, false);
  assert.equal(h.$('#email-send').disabled, false);
  assert.equal(h.$('#auth-screen').hidden, true);
  h.emailFlow.cancel();
  assert.equal(h.$('#auth-screen').hidden, false);
});

test('Google naming deadline returns to login and late rerenders keep it closed', async () => {
  const h = harness(); await h.verifiedGoogle();
  h.advanceClock(601000);
  for (const [id, entry] of [...h.timers]) {
    if (!entry.interval) {h.timers.delete(id); entry.callback();}
  }
  assert.equal(h.model.googlePending, null);
  assert.equal(h.$('#google-name-dialog').open, false);
  assert.equal(h.$('#auth-screen').hidden, false);
  assert.equal(h.$('#auth-error').hidden, false);
  await h.context.loadGoogleAuthConfig();
  assert.equal(h.$('#google-name-dialog').open, false);
  assert.equal(h.$('#auth-screen').hidden, false);
});
