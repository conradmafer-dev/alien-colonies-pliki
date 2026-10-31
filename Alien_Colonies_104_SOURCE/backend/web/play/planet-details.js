import {t, html, getLocale} from './i18n.js?v=0111';
import {canAttemptColonization} from './colony-capture.js?v=20261017-colony-capture';

const esc = (value = '') => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
const number = (value, digits = 0) => Number(value).toLocaleString(getLocale(), {maximumFractionDigits:digits});
const present = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
const date = value => present(value) && Number(value) > 0 ? new Date(Number(value)*1000).toLocaleString(getLocale(), {year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '';

// Report payloads are historical. A newer battle observation on the map must
// never replace the last actual scouting report shown here.
export function planetInspection(state, planetId) {
  const system = state?.galaxy?.find(entry => entry.planets?.some(planet => planet.id === planetId));
  const planet = system?.planets?.find(entry => entry.id === planetId);
  if (!planet) return null;
  const report = (state.reports || []).filter(entry => entry.planet_scout?.id === planetId || entry.scout?.id === planetId)
    .reduce((latest, entry) => !latest || Number(entry.at || 0) > Number(latest.at || 0) ? entry : latest, null);
  const snapshot = report ? report.planet_scout || report.scout : planet.planet_scout || null;
  const swarm = report?.scout || (!report && planet.has_scout ? planet : null);
  const own = planet.owner_id === state.player?.id && !!state.player?.id;
  return {planet, system, report, snapshot, swarm, own, currentOwn:own && state.planet_id === planetId};
}

function dataGrid(entries) {
  return `<dl class="planet-detail-grid">${entries.filter(([,value]) => value !== undefined && value !== null && value !== '').map(([label,value]) => `<div><dt>${esc(t(label))}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl>`;
}

function quantities(title, entries, kind, catalog = []) {
  if (!Array.isArray(entries)) return '';
  return `<section class="planet-intel-group"><h4>${esc(t(title))}</h4>${entries.length ? `<ul class="planet-intel-list">${entries.map(entry => {
    const value = kind === 'building' ? entry.level : entry.count;
    const name = entry.name || catalog.find(item => item.key === entry.key)?.name || entry.key || t('Nieznane');
    return `<li><span>${esc(name)}${entry.inactive ? ` ${esc(t('(nieaktywny)'))}` : ''}</span>${present(value) ? `<strong>${kind === 'building' ? `${esc(t('Poziom'))} ` : ''}${esc(number(value))}</strong>` : ''}</li>`;
  }).join('')}</ul>` : `<p class="muted">${esc(t('Brak'))}</p>`}</section>`;
}

function stocks(resources) {
  if (!resources) return '';
  const entries = [['metal','Metal'],['crystal','Kryształy'],['fuel','Paliwo']].filter(([key]) => present(resources[key])).map(([key,label]) => [label,number(resources[key])]);
  return entries.length ? `<section class="planet-intel-group"><h4>${esc(t('Zasoby'))}</h4>${dataGrid(entries)}</section>` : '';
}

export function planetDetailsHtml(state, planetId, {art = ''} = {}) {
  const info = planetInspection(state, planetId);
  if (!info) return '';
  const {planet,system,report,snapshot,swarm,own,currentOwn} = info;
  const env = planet.environment || {};
  const owner = own ? t('Twoja kolonia') : planet.owner_type === 'empty' ? t('Wolna planeta') : planet.owner_name || t('Obca kolonia');
  const physical = [
    ['Typ planety',env.type_name],['Rozmiar',env.size_name],
    ['Pola',present(env.fields) ? number(env.fields) : undefined],
    ['Średnica',present(env.diameter_km) ? `${number(env.diameter_km)} km` : undefined],
    ['Orbita',present(env.orbit_au) ? `${number(env.orbit_au,2)} AU` : undefined],
    ['Temperatura',present(env.temperature_c) ? `${number(env.temperature_c)} °C` : undefined],
  ];
  const multipliers = env.multipliers ? [['metal','Metal'],['crystal','Kryształy'],['fuel','Paliwo']].filter(([key]) => present(env.multipliers[key])).map(([key,label]) => [label,`×${number(env.multipliers[key],2)}`]) : [];
  const trait = env.trait;
  const at = date(snapshot?.scouted_at || report?.at || swarm?.scouted_at);
  const liveBuildings = planet.building_visibility === 'live' ? quantities('Budynki · bieżąca obserwacja',planet.observed_buildings,'building',state.catalog?.buildings) : '';
  const scoutData = snapshot || swarm;
  const reportHeading = report ? t('Ostatni raport zwiadu') : scoutData ? t('Ostatnio poznany stan') : t('Zwiad');
  const historical = scoutData ? `<p class="planet-intel-note">${esc(t(report ? 'Dane z chwili zwiadu. Stan planety mógł się zmienić.' : 'Dane z chwili obserwacji. Stan planety mógł się zmienić.'))}</p>` : '';
  const swarmRows = swarm ? [
    ['Gniazdo Roju',swarm.swarm_kind_name],['Zagrożenie',swarm.swarm_threat],['Aktywność',swarm.swarm_activity],
    ['Kryształy Roju',present(swarm.swarm_crystals_stock) ? `${number(swarm.swarm_crystals_stock)}${present(swarm.swarm_crystals_capacity) ? ` / ${number(swarm.swarm_crystals_capacity)}` : ''}` : undefined],
  ] : [];
  const scoutHtml = scoutData ? `${stocks(snapshot?.resources ?? swarm?.resources)}${quantities('Statki',snapshot?.ships_display || swarm?.swarm_units,'unit',state.catalog?.ships)}${quantities('Obrona',snapshot?.defenses_display || swarm?.swarm_defenses,'unit',state.catalog?.defenses)}${quantities(report ? 'Budynki · podczas zwiadu' : 'Budynki · zapisany stan',snapshot?.observed_buildings || swarm?.swarm_buildings,'building',state.catalog?.buildings)}${swarmRows.some(([,value]) => value !== undefined && value !== null && value !== '') ? dataGrid(swarmRows) : ''}` : own ? html`<p class="muted">Brak archiwalnego raportu zwiadu tej planety.</p>` : html`<p class="muted">Brak danych zwiadu tej planety. Wyślij zwiadowcę, aby poznać jej zasoby, flotę i obronę.</p>`;
  return html`<header class="planet-detail-header">${art}<div><p class="eyebrow">INFORMACJE O PLANECIE</p><h2 id="planet-detail-title">${esc(planet.name)}</h2><p class="muted">${esc(system.name)} · ${esc(planet.id.toUpperCase())}</p></div></header>
    <section class="planet-detail-section"><h3>Informacje z mapy</h3>${dataGrid([['Właściciel',owner],['Cywilizacja',planet.race_name],...physical])}
    ${multipliers.length ? `<h4>${esc(t('Wydajność wydobycia'))}</h4>${dataGrid(multipliers)}` : ''}
    ${trait?.status === 'rare' ? `<div class="planet-trait"><strong>${esc(trait.name)}</strong>${trait.description ? `<p class="muted">${esc(trait.description)}</p>` : ''}</div>` : ''}
    ${planet.is_home_planet === true ? html`<p class="planet-intel-note">Planeta matka — nie można jej przejąć.</p>` : ''}${liveBuildings}</section>
    ${currentOwn ? `<section class="planet-detail-section"><h3>${esc(t('Bieżący stan kolonii'))}</h3>${stocks(state.resources)}</section>` : ''}
    <section class="planet-detail-section planet-scout-section"><div class="planet-scout-heading"><h3>${esc(reportHeading)}</h3>${at ? `<time>${esc(at)}</time>` : ''}</div>${historical}
    ${report ? `<article class="planet-scout-report">${report.title ? `<h4>${esc(report.title)}</h4>` : ''}${report.text ? `<p>${esc(report.text)}</p>` : ''}</article>` : ''}
    ${scoutHtml}</section>
    <div class="dialog-actions planet-detail-actions">${own ? html`<button type="button" class="button primary" data-planet="${esc(planet.id)}">Otwórz kolonię</button>` : html`<button type="button" class="button subtle" data-target="${esc(planet.id)}" data-mission="scout">Wyślij nowy zwiad</button>${canAttemptColonization(state,planet) ? html`<button type="button" class="button primary" data-target="${esc(planet.id)}" data-mission="colonize">${t(planet.owner_type === 'empty' ? 'Kolonizacja' : 'Przejęcie kolonii')}</button>` : ''}`}</div>`;
}

