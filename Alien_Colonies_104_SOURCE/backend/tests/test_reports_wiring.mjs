// Runs the shipped game.js with the existing synthetic DOM fixture. The fixture
// stops before the queue assertions, so this adds coverage without copying or
// changing that harness. Native browser keyboard/layout behavior is not emulated.
import assert from 'node:assert/strict';
import fs from 'node:fs';

const harnessUrl = new URL('test_planned_queue_wiring.mjs', import.meta.url);
const repo = new URL('../web/play/', import.meta.url);
let fixture = fs.readFileSync(harnessUrl, 'utf8');
const stop = fixture.indexOf('const game=context.testGame, q=');
assert.ok(stop > 0, 'existing fixture exposes an explicit end-of-bootstrap marker');
fixture = fixture.slice(0, stop)
  .replace("const repo=new URL('../web/play/',import.meta.url);", `const repo=new URL(${JSON.stringify(repo.href)});`)
  .replace('model,loadState,renderMain,renderPlanetDetails', 'model,loadState,renderMain,renderPlanetDetails,openReportDetails,closeReportDetails,clearSession');
fixture += '\nexport {context, document, sandbox, makeState, win, intervals};\nexport function setObservedState(value){observedState=value;}\n';
const {context, document, sandbox, makeState, win, intervals, setObservedState} = await import(`data:text/javascript;base64,${Buffer.from(fixture).toString('base64')}`);
const game = context.testGame;
const q = selector => document.querySelector(selector);
const qa = selector => document.querySelectorAll(selector);
const click = async target => {
  assert.ok(target, 'click target exists');
  await document.dispatch('click', {target});
};
const flush = async () => { for (let i = 0; i < 4; i++) await new Promise(resolve => setImmediate(resolve)); };
const response = (data, status = 200) => ({ok:status >= 200 && status < 300, status, json:async () => data});
const deferred = () => {let resolve; const promise = new Promise(done => {resolve = done;}); return {promise, resolve};};
const baseFetch = sandbox.fetch;
const replayRequests = [];
let nextReplay;
sandbox.fetch = async (requested, options = {}) => {
  const url = new URL(requested, 'http://fixture.test');
  if (url.pathname === '/api/battle-replay') {
    replayRequests.push({url, options});
    assert.ok(nextReplay, 'battle response fixture is configured');
    return await nextReplay;
  }
  if (url.pathname === '/api/logout') return response({ok:true});
  return baseFetch(requested, options);
};

let observed = makeState();
const longText = 'Pierwsza linia\nDruga linia\n' + 'Koniec raportu '.repeat(40) + '<script>alert("report")</script><img src=x onerror="alert(1)">';
observed.reports = [
  {...observed.reports[0], id:'battle-one', battle_id:'private-battle-one', title:'Bitwa <script>title</script>', text:'Pełne podsumowanie pierwszej bitwy', art_key:'ship_scout'},
  {...observed.reports[1], id:'old-scout', title:'Historyczny zwiad <img src=x onerror=alert(1)>', text:longText, art_key:'ship_scout'},
  {id:'plain', at:700, title:'Ukończona budowa', text:'Cały tekst budowy\nDruga linia budowy'}
];
setObservedState(observed);
await game.loadState();
await click(q('[data-tab="reports"]'));
const scoutButton = q('[data-report="old-scout"]');
assert.ok(scoutButton, 'reports list exposes a report opening action');
assert.equal(scoutButton.tagName, 'BUTTON', 'report activation uses native keyboard semantics');
assert.equal(scoutButton.getAttribute('type'), 'button');
assert.equal(scoutButton.getAttribute('aria-haspopup'), 'dialog');
assert.ok(scoutButton.getAttribute('aria-label') || scoutButton.textContent.trim(), 'native button has an accessible name');
scoutButton.focus();
await click(scoutButton.closest('.report-card').querySelector('h2'));
assert.equal(q('#report-dialog').open, true);
assert.match(q('#report-detail-title').textContent, /Historyczny zwiad/);
assert.equal(q('.report-detail-text').textContent, longText, 'modal preserves the complete report including newlines');
assert.equal(qa('#report-dialog script').length, 0);
assert.equal(qa('#report-dialog [onerror]').length, 0);
assert.match(q('.report-scout-section').textContent, /Historyczna fregata/);
assert.doesNotMatch(q('.report-scout-section').textContent, /Nowa migawka/);
assert.match(q('.report-snapshot-note').textContent, /zwiad|raport|zapisany|Stan/i);
assert.equal(replayRequests.length, 0, 'non-battle reports do not request private replay data');
await q('#report-dialog').dispatch('cancel');
assert.equal(q('#report-dialog').open, false);
assert.equal(document.activeElement, scoutButton, 'cancel restores the opening report button');
await click(scoutButton.closest('.report-card').querySelector('.report-art'));
assert.equal(q('#report-dialog').open, true, 'report artwork opens the same details');

// A quiet poll may update the latest scout, remove an inaccessible map planet,
// or age the report out of the current list. An open archived report is stable.
observed.galaxy[0].planets = observed.galaxy[0].planets.filter(planet => planet.id !== 's1p2');
observed.reports = [{id:'new-scout', at:1100, title:'Nowy zwiad', text:'Nowszy tekst', planet_scout:{id:'s1p2', scouted_at:1100, ships_display:[{name:'Nowa migawka', count:99}]}}];
await game.loadState({quiet:true});
assert.equal(q('#report-dialog').open, true);
assert.equal(q('.report-detail-text').textContent, longText);
assert.match(q('.report-scout-section').textContent, /Historyczna fregata/);
assert.doesNotMatch(q('.report-scout-section').textContent, /Nowa migawka/);
assert.equal(game.model.reportDetail.report.id, 'old-scout');
await q('#report-dialog').dispatch('cancel');
assert.equal(q('#report-dialog').open, false);
assert.ok(document.activeElement?.isConnected, 'closing returns focus to a connected control when a poll replaced the source button');

// Colony previews use the same modal and preserve the complete report.
observed = makeState();
observed.reports[1].text = longText;
setObservedState(observed);
await game.loadState();
await click(q('[data-tab="colony"]'));
const preview = q('[data-report="scout"]');
assert.ok(preview, 'recent colony reports are actionable');
assert.equal(preview.tagName, 'BUTTON');
preview.focus();
await click(preview.querySelector('strong') || preview);
assert.equal(q('#report-dialog').open, true);
assert.equal(q('.report-detail-text').textContent, longText);
await q('#report-dialog').dispatch('click', {clientX:1, clientY:1});
assert.equal(q('#report-dialog').open, false);
assert.equal(document.activeElement, preview, 'backdrop close restores the opening control');
await click(preview);
await click(q('[data-close-report]'));
assert.equal(q('#report-dialog').open, false);
assert.equal(document.activeElement, preview, 'close button restores the opening control');

console.log(JSON.stringify({ok:true, checks:['actual game.js report activation','native report and preview buttons','complete multiline text and escaping','selected historical scout without map planet','quiet poll snapshot preservation','cancel/backdrop/close focus restoration']}));

const replay = {
  attacker:{name:'Koalicja', units:[
    {key:'fleet-a:frigate', name:'Fregata A', unit_name:'Fregata A', owner_name:'Sojusznik A'},
    {key:'fleet-b:frigate', name:'Fregata B', unit_name:'Fregata B', owner_name:'Sojusznik B'}
  ], initial:{'fleet-a:frigate':{count:5,wounds:3},'fleet-b:frigate':{count:2,wounds:0}}, losses:{'fleet-a:frigate':2,'fleet-b:frigate':0}},
  defender:{name:'Rój', units:[{key:'swarm:guardian',name:'Strażnik'}], initial:{'swarm:guardian':{count:4,wounds:0}}, losses:{'swarm:guardian':4}},
  final:{attacker:{'fleet-a:frigate':{count:3,wounds:1},'fleet-b:frigate':{count:2,wounds:0}}, defender:{'swarm:guardian':{count:0,wounds:0}}},
  rounds:[{number:1,
    before:{attacker:{'fleet-a:frigate':{count:5,wounds:3},'fleet-b:frigate':{count:2,wounds:0}}, defender:{'swarm:guardian':{count:4,wounds:0}}},
    after_damage:{attacker:{'fleet-a:frigate':{count:3,wounds:8},'fleet-b:frigate':{count:2,wounds:0}}, defender:{'swarm:guardian':{count:0,wounds:0}}},
    heals:{attacker:[{key:'fleet-a:frigate',healed:7,before:{count:3,wounds:8},after:{count:3,wounds:1}}],defender:[]},
    after:{attacker:{'fleet-a:frigate':{count:3,wounds:1},'fleet-b:frigate':{count:2,wounds:0}},defender:{'swarm:guardian':{count:0,wounds:0}}},
    salvos:{attacker:30,defender:20}
  }],
  outcome:'attacker_wins', planet:{name:'Historyczne gniazdo'}, cargo:{metal:12,crystal:3,fuel:2},
  swarm_crystals:2, swarm_eradicated:true, swarm_destruction_bonus:1,
  participant_results:[{owner_name:'Sojusznik A',cargo:{metal:8},swarm_crystals:1},{owner_name:'Sojusznik B',cargo:{metal:4},swarm_crystals:1}]
};
observed = makeState();
observed.reports = [
  {id:'battle-one', at:990, title:'Bitwa pierwsza', text:'Podsumowanie bitwy\nPełna druga linia', battle_replay_available:true, art_key:'ship_scout'},
  {id:'plain', at:900, title:'Budowa', text:'Podsumowanie budowy bez bitwy'},
  {at:800, title:'Stary raport bez ID', text:'Pełen historyczny tekst bez ID'}
];
setObservedState(observed);
await game.loadState();
await click(q('[data-tab="reports"]'));
const battleButton = q('[data-report="battle-one"]');
nextReplay = deferred();
const firstRequest = nextReplay;
nextReplay = firstRequest.promise;
await click(battleButton.closest('.report-card').querySelector('h2'));
assert.equal(q('#report-dialog').open, true, 'modal opens before replay data arrives');
assert.equal(q('.report-detail-text').textContent, observed.reports[0].text);
assert.match(q('.report-battle-section').textContent, /Pobieranie/);
assert.equal(replayRequests.at(-1).url.searchParams.get('report_id'), 'battle-one');
assert.equal(replayRequests.at(-1).options.headers.Authorization, 'Bearer fixture-token');
assert.equal(replayRequests.at(-1).options.headers['X-PGR-Client-Platform'], 'web');
assert.equal(replayRequests.at(-1).options.cache, 'no-store');
firstRequest.resolve(response({ok:true,replay}));
await flush();
assert.equal(qa('.report-round').length, 1);
assert.equal(q('.report-round').hasAttribute('open'), true, 'first round is directly readable');
assert.match(q('.report-round summary').textContent, /Runda 1/);
assert.match(q('.report-round').textContent, /Fregata A/);
assert.match(q('.report-round').textContent, /Fregata B/);
assert.match(q('.report-round').textContent, /Sojusznik A/);
assert.match(q('.report-round').textContent, /Sojusznik B/);
assert.match(q('.report-round').textContent, /\+7/);
const forceRow = qa('.report-forces-table tbody tr').find(row => row.textContent.includes('Fregata A'));
assert.deepEqual(forceRow.querySelectorAll('td').map(cell => cell.querySelector('strong')?.textContent || cell.textContent), ['5','3','2']);
const roundRow = qa('.report-round-table tbody tr').find(row => row.textContent.includes('Fregata A'));
assert.deepEqual(roundRow.querySelectorAll('td').map(cell => cell.querySelector('strong')?.textContent || cell.textContent), ['5','3','+7','3']);
assert.match(q('.report-battle-section').textContent, /Gniazdo Roju zostało zniszczone/);
assert.match(q('.report-reward-sharing').textContent, /Sojusznik A/);
assert.equal(q('.report-detail-text').textContent, observed.reports[0].text, 'replay rendering keeps the complete written summary');
await click(q('[data-close-report]'));

// A legacy report without an ID still opens through its stable fallback key.
const legacyButton = qa('[data-report]').find(button => button.dataset.report.includes('Stary raport bez ID'));
await click(legacyButton);
assert.equal(q('.report-detail-text').textContent, observed.reports[2].text);
assert.equal(replayRequests.length, 1);
await click(q('[data-close-report]'));

// Replay failures leave the summary readable and offer an authenticated retry.
nextReplay = Promise.resolve(response({ok:false,error:'Tymczasowy błąd <img src=x onerror=alert(1)>'}, 503));
await click(battleButton);
await flush();
assert.equal(q('.report-detail-text').textContent, observed.reports[0].text);
assert.match(q('.report-replay-error').textContent, /Tymczasowy błąd/);
assert.equal(qa('#report-dialog [onerror]').length, 0);
assert.ok(q('[data-retry-report]'));
nextReplay = Promise.resolve(response({ok:true,replay}));
await click(q('[data-retry-report]'));
await flush();
assert.equal(qa('.report-round').length, 1);
assert.equal(q('[data-retry-report]'), null);
await click(q('[data-close-report]'));

// Both a closed dialog and a different report invalidate late replay responses.
const closedRequest = deferred();
nextReplay = closedRequest.promise;
await click(battleButton);
await click(q('[data-close-report]'));
closedRequest.resolve(response({ok:true,replay}));
await flush();
assert.equal(q('#report-dialog').open, false);
assert.equal(game.model.reportDetail, null);
assert.equal(q('#report-detail-content').textContent, '');
const replacedRequest = deferred();
nextReplay = replacedRequest.promise;
await click(battleButton);
game.openReportDetails('plain', q('[data-report="plain"]'));
replacedRequest.resolve(response({ok:true,replay}));
await flush();
assert.equal(game.model.reportDetail.report.id, 'plain');
assert.equal(q('.report-detail-text').textContent, observed.reports[1].text);
assert.equal(q('.report-battle-section'), null);
await click(q('[data-close-report]'));

// Account cleanup also clears report contents and prevents old responses from
// displaying private battle data after logout.
const loggedOutRequest = deferred();
nextReplay = loggedOutRequest.promise;
await click(battleButton);
await q('#logout').dispatch('click');
loggedOutRequest.resolve(response({ok:true,replay}));
await flush();
assert.equal(game.model.token, '');
assert.equal(game.model.state, null);
assert.equal(game.model.reportDetail, null);
assert.equal(q('#report-dialog').open, false);
assert.equal(q('#report-detail-content').textContent, '');
assert.equal(q('#auth-screen').hidden, false);

console.log(JSON.stringify({ok:true, checks:['authenticated asynchronous battle fetch','source combat counts and coalition names','round damage and regeneration','legacy reports without IDs','error summary and retry','late response after close or replacement','logout removes private report and invalidates response'], replayRequests:replayRequests.length}));

const {reportDetailsHtml} = await import(new URL('report-details.js?v=20261006-report-details', repo));
const unsafeReplay = structuredClone(replay);
unsafeReplay.attacker.name = '<svg onload=alert(1)>';
unsafeReplay.attacker.units[0].owner_name = '<img src=x onerror=alert(1)>';
unsafeReplay.attacker.units[0].unit_name = '<script>unit</script>';
unsafeReplay.participant_results[0].owner_name = '<iframe src=javascript:alert(1)>';
unsafeReplay.planet.name = '<a href=javascript:alert(1)>Planet</a>';
const unsafeMarkup = reportDetailsHtml({title:'<script>title</script>',text:longText,battle_replay_available:true}, {replay:unsafeReplay});
assert.doesNotMatch(unsafeMarkup, /<(?:script|svg|iframe|img|a)\b/i, 'untrusted title, summary, planet and coalition names never become HTML');
assert.match(unsafeMarkup, /&lt;svg/);
assert.match(unsafeMarkup, /&lt;iframe/);
assert.match(unsafeMarkup, /&lt;script/);

// Every authored label added by the renderer is available in all five locales,
// with interpolation placeholders preserved. Dynamic player/report text is not
// translated. These checks are data validation rather than a simulated browser.
const renderer = fs.readFileSync(new URL('report-details.js', repo), 'utf8');
const keys = new Set([...renderer.matchAll(/\bt\('([^']+)'/g)].map(match => match[1]));
for (const match of renderer.matchAll(/\[\s*'([^']+)'\s*,/g)) if (!['metal','crystal','fuel'].includes(match[1])) keys.add(match[1]);
for (const match of renderer.matchAll(/\['(?:metal|crystal|fuel)','([^']+)'\]/g)) keys.add(match[1]);
for (const match of renderer.matchAll(/quantitiesHtml\('([^']+)'/g)) keys.add(match[1]);
for (const match of renderer.matchAll(/(?:resourcesHtml|forcesHtml|roundSideHtml)\([^\n)]*?'([^']+)'\)/g)) keys.add(match[1]);
for (const match of renderer.match(/const outcomes = \{([^}]+)\}/)?.[1]?.matchAll(/:'([^']+)'/g) || []) keys.add(match[1]);
keys.add('SZCZEGÓŁY RAPORTU');
const indexedKeys = new Set(JSON.parse(fs.readFileSync(new URL('locale-keys.json', repo), 'utf8')));
for (const key of keys) assert.ok(indexedKeys.has(key), `renderer localization missing from locale key index: ${key}`);
for (const language of ['pl','en','de','es','fr']) {
  const catalog = JSON.parse(fs.readFileSync(new URL(`locales/${language}.json`, repo), 'utf8'));
  for (const key of keys) {
    assert.equal(typeof catalog[key], 'string', `${language}: missing renderer localization ${key}`);
    const placeholders = value => [...String(value).matchAll(/\{\d+\}/g)].map(match => match[0]).sort();
    assert.deepEqual(placeholders(catalog[key]), placeholders(key), `${language}: interpolation mismatch ${key}`);
  }
}
assert.match(fs.readFileSync(new URL('report-details.css', repo), 'utf8'), /\.report-detail-text\s*\{[^}]*white-space:\s*pre-wrap/, 'multiline report text uses authored line breaks');
console.log(JSON.stringify({ok:true, localizationKeys:keys.size, locales:5}));
