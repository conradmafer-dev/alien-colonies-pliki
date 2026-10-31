import {t, html, getLocale} from './i18n.js?v=0111';

const esc = (value = '') => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
const present = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
const number = value => Number(value).toLocaleString(getLocale(), {maximumFractionDigits:0});
const date = value => {
  if (!present(value) || Number(value) <= 0) return '';
  const timestamp = new Date(Number(value) * 1000);
  return Number.isFinite(timestamp.getTime()) ? timestamp.toLocaleString(getLocale(), {year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '';
};
const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};

function dataGrid(entries) {
  const rows = entries.filter(([,value]) => value !== undefined && value !== null && value !== '');
  return rows.length ? `<dl class="report-detail-grid">${rows.map(([label,value]) => `<div><dt>${esc(t(label))}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl>` : '';
}

function resourcesHtml(resources, title = 'Zasoby') {
  const stock = object(resources);
  const rows = [['metal','Metal'],['crystal','Kryształy'],['fuel','Paliwo']].filter(([key]) => present(stock[key])).map(([key,label]) => [label,number(stock[key])]);
  return rows.length ? `<section class="report-intel-group"><h4>${esc(t(title))}</h4>${dataGrid(rows)}</section>` : '';
}

function quantitiesHtml(title, entries, kind = 'unit', fallback) {
  const values = Array.isArray(entries) ? entries : fallback && typeof fallback === 'object' ? Object.entries(fallback).map(([key,count]) => ({key,count})) : null;
  if (!values) return '';
  return `<section class="report-intel-group"><h4>${esc(t(title))}</h4>${values.length ? `<ul class="report-intel-list">${values.map(entry => `<li><span>${esc(entry.name || entry.key || t('Nieznane'))}</span>${present(kind === 'building' ? entry.level : entry.count) ? `<strong>${kind === 'building' ? `${esc(t('Poziom'))} ` : ''}${esc(number(kind === 'building' ? entry.level : entry.count))}</strong>` : ''}</li>`).join('')}</ul>` : `<p class="muted">${esc(t('Brak'))}</p>`}</section>`;
}

// Only the selected report is accepted here. Its immutable snapshot remains
// readable when a planet is hidden, changes owners, or has a newer scout report.
function scoutHtml(report) {
  const snapshot = report.planet_scout;
  const swarm = report.scout;
  if (!snapshot && !swarm) return '';
  const at = date(snapshot?.scouted_at || swarm?.scouted_at || report.at);
  const owner = snapshot?.owner_type === 'empty' ? t('Wolna planeta') : snapshot?.owner_name;
  const coordinates = [snapshot?.galaxy_id,snapshot?.system_id,snapshot?.slot].filter(value => value !== undefined && value !== null && value !== '').join(' · ');
  const swarmRows = swarm ? [
    ['Gniazdo Roju',swarm.swarm_kind_name],['Zagrożenie',swarm.swarm_threat],['Aktywność',swarm.swarm_activity],
    ['Kryształy Roju',present(swarm.swarm_crystals_stock) ? `${number(swarm.swarm_crystals_stock)}${present(swarm.swarm_crystals_capacity) ? ` / ${number(swarm.swarm_crystals_capacity)}` : ''}` : undefined],
    ['Kryształy gotowe do zdobycia',present(swarm.swarm_crystals_ready) ? number(swarm.swarm_crystals_ready) : undefined],
    ['Odnawiające się kryształy',present(swarm.swarm_crystals_regenerating) ? number(swarm.swarm_crystals_regenerating) : undefined],
  ] : [];
  return `<section class="report-detail-section report-scout-section"><div class="report-section-heading"><h3>${esc(t('Zapis zwiadu'))}</h3>${at ? `<time>${esc(at)}</time>` : ''}</div>
    <p class="report-snapshot-note">${esc(t('Dane z chwili zwiadu. Stan planety mógł się zmienić.'))}</p>
    ${dataGrid([['Planeta',snapshot?.name],['Współrzędne',coordinates || snapshot?.id],['Właściciel',owner],['Cywilizacja',snapshot?.race_name || swarm?.race_name]])}
    <div class="report-intel-columns">${resourcesHtml(snapshot?.resources || swarm?.resources)}${quantitiesHtml('Statki',snapshot?.ships_display || swarm?.swarm_units,'unit',snapshot?.ships)}${quantitiesHtml('Obrona',snapshot?.defenses_display || swarm?.swarm_defenses,'unit',snapshot?.defenses)}${quantitiesHtml('Budynki · podczas zwiadu',snapshot?.observed_buildings || swarm?.swarm_buildings,'building')}</div>
    ${dataGrid(swarmRows)}${swarm?.swarm_crystals_hint ? `<p class="muted">${esc(swarm.swarm_crystals_hint)}</p>` : ''}</section>`;
}

function systemScoutHtml(report) {
  const snapshot = report.system_scout;
  if (!snapshot || !Array.isArray(snapshot.planets)) return '';
  const counts = snapshot.counts || {};
  const at = date(snapshot.scouted_at || report.at);
  return `<section class="report-detail-section report-system-scout"><div class="report-section-heading"><h3>${esc(t('Zwiad całego układu'))}</h3>${at ? `<time>${esc(at)}</time>` : ''}</div>
    <p class="report-snapshot-note">${esc(t('Właściciele z chwili zwiadu. Aby sprawdzić zmiany, ponownie zbadaj cały układ.'))}</p>
    ${dataGrid([['Układ',snapshot.system_name || snapshot.system_id],['Współrzędne',[snapshot.galaxy_id,snapshot.system_id].filter(Boolean).join(' · ')],['Własne planety',present(counts.own) ? number(counts.own) : undefined],['Kolonie graczy',present(counts.player) ? number(counts.player) : undefined],['Obce cywilizacje',present(counts.alien) ? number(counts.alien) : undefined],['Wolne planety',present(counts.empty) ? number(counts.empty) : undefined]])}
    <ul class="report-intel-list">${snapshot.planets.map(planet => `<li><span>${esc(planet.name || planet.id)} <small>${esc(planet.id || '')}</small></span><strong>${esc(planet.owner_type === 'empty' ? t('Wolna planeta') : planet.owner_name || t('Nieznane'))}</strong></li>`).join('')}</ul>
    <p class="muted">${esc(t('Zwiad pojedynczej planety pozwala poznać jej zasoby i siły.'))}</p></section>`;
}

function unitRows(side, ...states) {
  const units = new Map((Array.isArray(side?.units) ? side.units : []).map(unit => [String(unit.key),unit]));
  for (const state of states) for (const key of Object.keys(object(state))) if (!units.has(key)) units.set(key,{key,name:key});
  return [...units.values()];
}

function forceHtml(value) {
  // Counts, wounds, losses, and healing are all authoritative server values.
  // The UI does not infer a new battle result or reproduce combat formulas.
  if (!value || !present(typeof value === 'object' ? value.count : value)) return '<span class="muted">—</span>';
  const count = typeof value === 'object' ? value.count : value;
  const wounds = typeof value === 'object' ? value.wounds : undefined;
  return `<strong>${esc(number(count))}</strong>${present(wounds) && Number(wounds) > 0 ? `<small>${esc(t('Uszkodzenia kadłuba: {0}',number(wounds)))}</small>` : ''}`;
}

function unitLabel(unit) {
  return `<span>${esc(unit.unit_name || unit.name || unit.key)}${unit.owner_name ? `<small>${esc(unit.owner_name)}</small>` : ''}</span>`;
}

function participantsHtml(side) {
  const participants = Array.isArray(side?.participants) ? side.participants : [];
  return participants.length ? `<ul class="report-participants">${participants.map(participant => `<li>${esc(participant.owner_name || participant.owner_id || t('Nieznane'))}</li>`).join('')}</ul>` : '';
}

function forcesHtml(replay, name, label) {
  const side = replay[name] || {};
  const final = object(replay.final?.[name]);
  const initial = object(side.initial);
  const losses = object(side.losses);
  const rows = unitRows(side,initial,final,losses);
  return `<section class="report-force-group"><h4>${esc(t(label))}${side.name ? ` · ${esc(side.name)}` : ''}</h4>${participantsHtml(side)}${rows.length ? `<div class="report-table-scroll" tabindex="0" aria-label="${esc(t('Siły i straty'))}"><table class="report-forces-table"><thead><tr><th scope="col">${esc(t('Jednostka'))}</th><th scope="col">${esc(t('Stan początkowy'))}</th><th scope="col">${esc(t('Stan końcowy'))}</th><th scope="col">${esc(t('Straty'))}</th></tr></thead><tbody>${rows.map(unit => `<tr><th scope="row">${unitLabel(unit)}</th><td>${forceHtml(initial[unit.key])}</td><td>${forceHtml(final[unit.key])}</td><td>${present(losses[unit.key]) ? esc(number(losses[unit.key])) : '—'}</td></tr>`).join('')}</tbody></table></div>` : `<p class="muted">${esc(t('Brak danych o składzie'))}</p>`}</section>`;
}

function roundSideHtml(round, replay, name, label) {
  const side = replay[name] || {};
  const before = object(round.before?.[name]);
  const afterDamage = object(round.after_damage?.[name]);
  const after = object(round.after?.[name]);
  const heals = Array.isArray(round.heals?.[name]) ? round.heals[name] : [];
  const rows = unitRows(side,before,afterDamage,after).filter(unit => [before,afterDamage,after].some(state => Number(state[unit.key]?.count ?? state[unit.key] ?? 0) > 0) || heals.some(heal => heal.key === unit.key));
  const salvo = round.salvos?.[name];
  return `<section class="report-round-side"><h5>${esc(t(label))}${present(salvo) ? `<span class="muted">${esc(t('Siła salwy: {0}',number(salvo)))}</span>` : ''}</h5>${rows.length ? `<div class="report-table-scroll" tabindex="0" aria-label="${esc(t('Przebieg rundy'))}"><table class="report-round-table"><thead><tr><th scope="col">${esc(t('Jednostka'))}</th><th scope="col">${esc(t('Przed rundą'))}</th><th scope="col">${esc(t('Po salwie'))}</th><th scope="col">${esc(t('Regeneracja'))}</th><th scope="col">${esc(t('Po rundzie'))}</th></tr></thead><tbody>${rows.map(unit => {
    const healing = heals.filter(heal => heal.key === unit.key && present(heal.healed)).map(heal => number(heal.healed)).join(' + ');
    return `<tr><th scope="row">${unitLabel(unit)}</th><td>${forceHtml(before[unit.key])}</td><td>${forceHtml(afterDamage[unit.key])}</td><td>${healing ? `+${esc(healing)}` : '—'}</td><td>${forceHtml(after[unit.key])}</td></tr>`;
  }).join('')}</tbody></table></div>` : `<p class="muted">${esc(t('Brak'))}</p>`}</section>`;
}

function battleHtml(report, replay, replayStatus, replayError) {
  if (!report.battle_replay_available && !replay && !replayStatus && !replayError) return '';
  if (!replay) return `<section class="report-detail-section report-battle-section"><h3>${esc(t('Przebieg bitwy'))}</h3>${replayStatus === 'loading' ? `<p class="muted" role="status">${esc(t('Pobieranie przebiegu bitwy…'))}</p>` : `<p class="report-replay-error" role="status">${esc(replayError || t('Nie udało się pobrać przebiegu bitwy. Podsumowanie raportu pozostaje dostępne.'))}</p><button type="button" class="button subtle" data-retry-report="${esc(report.id)}">${esc(t('Spróbuj ponownie'))}</button>`}</section>`;
  const outcomes = {attacker_wins:'Zwycięstwo atakujących',attacker_destroyed:'Flota atakujących zniszczona',retreat:'Odwrót'};
  const rounds = Array.isArray(replay.rounds) ? replay.rounds : [];
  const crystals = present(replay.swarm_crystals) ? replay.swarm_crystals : report.swarm_crystals;
  const participantResults = Array.isArray(replay.participant_results) ? replay.participant_results : [];
  return `<section class="report-detail-section report-battle-section"><h3>${esc(t('Przebieg bitwy'))}</h3>
    ${dataGrid([['Wynik bitwy',outcomes[replay.outcome] ? t(outcomes[replay.outcome]) : undefined],['Planeta',replay.planet?.name]])}
    ${replay.swarm_eradicated ? `<p class="report-battle-outcome">${esc(t('Gniazdo Roju zostało zniszczone.'))}</p>` : ''}
    ${forcesHtml(replay,'attacker','Atakujący')}${forcesHtml(replay,'defender','Obrońca')}
    <div class="report-loot">${resourcesHtml(replay.cargo,'Łup')}${dataGrid([['Zdobyte Kryształy Roju',present(crystals) ? number(crystals) : undefined],['Premia za zniszczenie gniazda',present(replay.swarm_destruction_bonus) && Number(replay.swarm_destruction_bonus) > 0 ? number(replay.swarm_destruction_bonus) : undefined]])}</div>
    ${participantResults.length > 1 ? `<details class="report-reward-sharing"><summary>${esc(t('Podział łupu'))}</summary>${participantResults.map(result => `<section class="report-participant-reward"><h4>${esc(result.owner_name || result.owner_id || t('Nieznane'))}</h4>${resourcesHtml(result.cargo,'Łup')}${dataGrid([['Zdobyte Kryształy Roju',present(result.swarm_crystals) ? number(result.swarm_crystals) : undefined],['Odzyskany metal',present(result.recovered_metal) && Number(result.recovered_metal) > 0 ? number(result.recovered_metal) : undefined]])}</section>`).join('')}</details>` : ''}
    ${rounds.length ? `<section class="report-rounds"><h4>${esc(t('Rundy bitwy'))}</h4><p class="muted report-rounds-note">${esc(t('Przebieg zapisany przez serwer. Regeneracja następuje po salwach obu stron.'))}</p>${rounds.map((round,index) => `<details class="report-round"${index === 0 ? ' open' : ''}><summary>${esc(t('Runda {0}',present(round.number) ? number(round.number) : number(index + 1)))}</summary>${roundSideHtml(round,replay,'attacker','Atakujący')}${roundSideHtml(round,replay,'defender','Obrońca')}</details>`).join('')}</section>` : ''}</section>`;
}

export function reportDetailsHtml(report, {art = '', replay = null, replayStatus = '', replayError = ''} = {}) {
  if (!report || typeof report !== 'object') return '';
  const at = date(report.at);
  const hasReplay = !!report.battle_replay_available || !!replay || !!replayStatus || !!replayError;
  return html`<header class="report-detail-header">${art}<div><p class="eyebrow">SZCZEGÓŁY RAPORTU</p><h2 id="report-detail-title">${esc(report.title || t('Raport'))}</h2>${at ? `<time>${esc(at)}</time>` : ''}</div></header>
    ${report.text ? `<article class="report-detail-body"><p class="report-detail-text">${esc(report.text)}</p></article>` : ''}
    ${systemScoutHtml(report)}${scoutHtml(report)}${battleHtml(report,replay,replayStatus,replayError)}
    ${!hasReplay && present(report.swarm_crystals) && Number(report.swarm_crystals) > 0 ? dataGrid([['Zdobyte Kryształy Roju',number(report.swarm_crystals)]]) : ''}`;
}
