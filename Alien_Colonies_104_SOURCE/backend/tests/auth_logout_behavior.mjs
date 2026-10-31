import vm from 'node:vm';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const source = fs.readFileSync(path.join(root, 'web/play/game.js'), 'utf8');
const mirror = [path.resolve(root, '../android/railway/web/play/game.js'), path.resolve(root, '../../server/web/play/game.js')].find(candidate => fs.existsSync(candidate));
const reportArgument = process.argv.slice(2).find(argument => argument.startsWith('--report='));
const reportPath = reportArgument?.slice('--report='.length);
if (reportArgument && !reportPath) throw new Error('--report=PATH requires a non-empty path.');
const script = [
  source.slice(source.indexOf('function reportIdentity('), source.indexOf("window.addEventListener('storage'")),
  source.slice(source.indexOf('class ApiError '), source.indexOf('function requestId(')),
  source.slice(source.indexOf('function storeToken('), source.indexOf('function serverNow(')),
  source.slice(source.indexOf("$('#auth-login').addEventListener"), source.indexOf("$('#refresh').addEventListener")),
].join('\n');
const outcomes = [];

function setup() {
  const elements = new Map();
  const requests = [];
  const timers = new Map();
  const storage = new Map([['alien-colonies.session', 'token-A']]);
  const reports = new Map([
    ['alien-colonies.report-reads:https%3A%2F%2Fqa.example:A', '["report-A"]'],
    ['alien-colonies.report-reads:https%3A%2F%2Fqa.example:B', '["report-B"]'],
  ]);
  const events = [];
  let timerId = 0;
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      value: '', hidden: false, disabled: false, textContent: '', innerHTML: '', className: '',
      attrs: {}, listeners: {}, classes: new Set(),
      setAttribute(key, value) { this.attrs[key] = value; },
      addEventListener(type, handler) { this.listeners[type] = handler; },
      classList: {toggle(name, enabled) { events.push(['class', selector, name, enabled]); }},
    });
    return elements.get(selector);
  }
  const state = id => ({player: {id, name: `Commander ${id}`}, planet_id: `planet-${id}`, planet_galaxy_id: 'galaxy-1'});
  const env = {
    model: {token: 'token-A', epoch: 10, busy: false, register: false, state: state('A'), reportScope: '', reportReadIds: new Set(), tab: 'research', chat: {old: true}, alliance: {old: true}, uncertain: {old: true}, selectedSystems: {old: true}, galaxyViews: {old: true}, galaxyId: 'old', fleetTarget: 'old', detailPlanet: '', researchView: {old: true}},
    $: element,
    storageKey: 'alien-colonies.session',
    sessionStorage: {setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k)},
    localStorage: {getItem: k => reports.get(k) || null, setItem: (k, v) => reports.set(k, v)},
    location: {origin: 'https://qa.example'},
    document: {title: ''},
    AbortController,
    performance: {now: () => 1234},
    getLanguage: () => 'pl',
    t: value => value,
    html: (parts, ...values) => parts.map((part, index) => part + (values[index] ?? '')).join(''),
    esc: value => String(value),
    pendingQuietRender: {old: true},
    researchTreeController: {destroy: () => events.push(['destroy-research'])},
    galaxyMapController: {destroy: () => events.push(['destroy-galaxy'])},
    closeBuildingDetails: () => events.push(['close-building']),
    closeResearchDetails: () => events.push(['close-research']),
    renderBuildingDetails: () => events.push(['render-building']),
    renderResearchDetails: () => events.push(['render-research']),
    renderChrome: () => events.push(['render-chrome', env.model.busy]),
    renderMain: () => events.push(['render-main', env.model.busy]),
    schedulePoll: () => events.push(['schedule-poll']),
    setConnection: connected => events.push(['connection', connected]),
    pollTimer: 99,
    toastTimer: 98,
    setTimeout(handler, milliseconds) { const id = ++timerId; timers.set(id, {handler, milliseconds}); return id; },
    clearTimeout(id) { timers.delete(id); events.push(['clear-timer', id]); },
    fetch(path, args) {
      return new Promise((resolve, reject) => {
        const request = {path, args, resolve, reject, parsed: 0};
        args.signal.addEventListener('abort', () => { const error = new Error('aborted'); error.name = 'AbortError'; reject(error); });
        requests.push(request);
      });
    },
  };
  element('#auth-screen').hidden = true;
  element('#game-screen').hidden = false;
  element('#auth-error').hidden = true;
  element('#empire-name').value = 'Commander B';
  element('#password').value = 'sample password';
  vm.createContext(env);
  vm.runInContext(script, env);
  env.refreshReportScope();
  function respond(request, status, data = {ok: true}) {
    request.resolve({ok: status >= 200 && status < 300, status, json: async () => { request.parsed++; return data; }});
  }
  const flush = () => new Promise(resolve => setImmediate(resolve));
  const logout = () => element('#logout').listeners.click();
  const login = () => element('#auth-form').listeners.submit({preventDefault() {}});
  const snapshot = () => JSON.stringify({token: env.model.token, epoch: env.model.epoch, state: env.model.state, reportScope: env.model.reportScope, reads: [...env.model.reportReadIds], auth: element('#auth-screen').hidden, game: element('#game-screen').hidden, error: element('#auth-error').hidden, toast: element('#toast').innerHTML, busy: env.model.busy, title: env.document.title, events});
  return {env, elements, requests, timers, storage, events, state, respond, flush, logout, login, snapshot, element};
}

async function check(name, run) {
  try { await run(); outcomes.push({name, passed: true}); }
  catch (error) { outcomes.push({name, passed: false, error: error.stack}); }
}

await check('logout clears local session and account scope immediately while revoke is pending', async () => {
  const a = setup();
  assert.equal(a.logout(), undefined);
  assert.equal(a.env.model.token, '');
  assert.equal(a.env.model.epoch, 11);
  assert.equal(a.env.model.state, null);
  assert.equal(a.env.model.busy, false);
  assert.equal(a.env.pendingQuietRender, false);
  assert.equal(a.env.model.reportScope, '');
  assert.equal(a.env.model.reportReadIds.size, 0);
  assert.equal(a.storage.has('alien-colonies.session'), false);
  assert.equal(a.element('#auth-screen').hidden, false);
  assert.equal(a.element('#game-screen').hidden, true);
  assert.equal(a.element('#password').value, '');
  assert.equal(a.requests.length, 1);
  assert.equal(a.requests[0].path, '/api/logout');
  assert.equal(a.requests[0].args.headers.Authorization, 'Bearer token-A');
  assert.equal(a.requests[0].args.keepalive, true);
  assert.equal(a.env.researchTreeController, null);
  assert.equal(a.env.galaxyMapController, null);
  assert.ok(a.events.some(event => event[0] === 'clear-timer' && event[1] === 99));
  a.respond(a.requests[0], 200);
  await a.flush();
});

for (const late of ['200', '401', '500', 'network-error', 'abort']) {
  await check(`new login while old revoke waits survives late ${late} without UI changes`, async () => {
    const a = setup();
    a.logout();
    const old = a.requests[0];
    a.element('#password').value = 'new password';
    const login = a.login();
    assert.equal(a.requests.length, 2);
    const auth = a.requests[1];
    assert.equal(auth.path, '/api/login');
    assert.equal(auth.args.headers.Authorization, undefined);
    assert.equal(a.env.model.busy, true);
    a.respond(auth, 200, {ok: true, token: 'token-B', state: a.state('B'), message: 'Welcome B'});
    await login;
    assert.equal(a.env.model.token, 'token-B');
    assert.equal(a.storage.get('alien-colonies.session'), 'token-B');
    assert.equal(a.env.model.state.player.id, 'B');
    assert.equal(a.env.model.reportScope, 'alien-colonies.report-reads:https%3A%2F%2Fqa.example:B');
    assert.deepEqual([...a.env.model.reportReadIds], ['report-B']);
    assert.equal(a.element('#auth-screen').hidden, true);
    assert.equal(a.element('#game-screen').hidden, false);
    assert.equal(a.element('#auth-submit').disabled, false);
    assert.equal(a.env.model.busy, false);
    assert.equal(a.events.filter(event => event[0] === 'render-chrome').length, 1);
    assert.equal(a.events.filter(event => event[0] === 'render-main').length, 1);
    assert.ok(a.events.filter(event => /^render-(chrome|main)$/.test(event[0])).every(event => event[1] === false));
    const snapshot = a.snapshot();
    if (late === 'network-error') old.reject(new Error('network unavailable'));
    else if (late === 'abort') [...a.timers.values()].find(timer => timer.milliseconds === 20000).handler();
    else a.respond(old, Number(late), {ok: late === '200', error: 'old session invalid', state: a.state('A')});
    await a.flush();
    // Timer cleanup is the only observable internal effect of old revocation.
    a.events.splice(a.events.findLastIndex(event => event[0] === 'clear-timer'), 1);
    assert.equal(a.snapshot(), snapshot);
    assert.equal(old.parsed, 0);
  });
}

await check('late authenticated 401 from old account cannot clear a new login', async () => {
  const a = setup();
  const old = a.env.api('/state').catch(error => error);
  a.logout();
  const login = a.login();
  a.respond(a.requests[2], 200, {ok: true, token: 'token-B', state: a.state('B')});
  await login;
  const snapshot = a.snapshot();
  a.respond(a.requests[0], 401, {ok: false, error: 'old session expired'});
  const error = await old;
  assert.equal(error.status, 401);
  a.events.splice(a.events.findLastIndex(event => event[0] === 'clear-timer'), 1);
  assert.equal(a.snapshot(), snapshot);
  a.respond(a.requests[1], 200);
  await a.flush();
});

await check('epoch guard protects a replacement session even if token happens to match', async () => {
  const a = setup();
  const request = a.env.api('/state').catch(error => error);
  a.env.model.epoch++;
  a.respond(a.requests[0], 401, {ok: false, error: 'stale'});
  await request;
  assert.equal(a.env.model.token, 'token-A');
  assert.equal(a.env.model.state.player.id, 'A');
  assert.equal(a.element('#auth-screen').hidden, true);
});

await check('401 for the current authenticated session still expires it visibly', async () => {
  const a = setup();
  const request = a.env.api('/state').catch(error => error);
  a.respond(a.requests[0], 401, {ok: false, error: 'expired'});
  const error = await request;
  assert.equal(error.status, 401);
  assert.equal(a.env.model.token, '');
  assert.equal(a.env.model.state, null);
  assert.equal(a.element('#auth-screen').hidden, false);
  assert.equal(a.element('#auth-error').hidden, false);
  assert.match(a.element('#auth-error').textContent, /Sesja wygasła/);
});

await check('login 401 does not expire or clear an unrelated authenticated model', async () => {
  const a = setup();
  const request = a.env.api('/login', {method: 'POST', authenticated: false, body: {name: 'invalid'}}).catch(error => error);
  a.respond(a.requests[0], 401, {ok: false, error: 'invalid password'});
  const error = await request;
  assert.equal(error.status, 401);
  assert.equal(a.env.model.token, 'token-A');
  assert.equal(a.env.model.state.player.id, 'A');
});

await check('failed login releases busy state and submit without rendering the game', async () => {
  const a = setup();
  a.env.clearSession();
  a.env.showAuth();
  const login = a.login();
  a.respond(a.requests[0], 401, {ok: false, error: 'invalid password'});
  await login;
  assert.equal(a.env.model.busy, false);
  assert.equal(a.element('#auth-submit').disabled, false);
  assert.equal(a.element('#auth-error').hidden, false);
  assert.equal(a.element('#auth-error').textContent, 'invalid password');
  assert.equal(a.events.filter(event => event[0] === 'render-main').length, 0);
});

await check('registration success renders playable controls once without a second state request', async () => {
  const a = setup();
  a.env.clearSession();
  a.env.model.register = true;
  const register = a.login();
  assert.equal(a.requests.length, 1);
  assert.equal(a.requests[0].path, '/api/register');
  a.respond(a.requests[0], 200, {ok: true, token: 'token-B', state: a.state('B')});
  await register;
  assert.equal(a.env.model.busy, false);
  assert.equal(a.env.model.tab, 'colony');
  assert.equal(a.events.filter(event => event[0] === 'render-chrome').length, 1);
  assert.equal(a.events.filter(event => event[0] === 'render-main').length, 1);
  assert.ok(a.events.filter(event => /^render-(chrome|main)$/.test(event[0])).every(event => event[1] === false));
  assert.equal(a.requests.length, 1);
});

await check('busy gameplay prevents logout and sends no revoke', async () => {
  const a = setup();
  a.env.model.busy = true;
  a.logout();
  assert.equal(a.env.model.token, 'token-A');
  assert.equal(a.requests.length, 0);
});

if (mirror) {
  await check('available web mirror exactly matches tested source', async () => {
    assert.equal(fs.readFileSync(mirror, 'utf8'), source);
  });
}

const report = {method: 'Actual product API, session, auth submit and logout handlers extracted into isolated VM. Minimal DOM/fetch/timer stand-ins, no production requests or credentials. Tests exercise delayed completion and account replacement, not browser performance.', mirrorChecked: Boolean(mirror), outcomes};
const output = JSON.stringify(report, null, 2);
if (reportPath) fs.writeFileSync(reportPath, output + '\n');
console.log(output);
if (outcomes.some(result => !result.passed)) process.exitCode = 1;
