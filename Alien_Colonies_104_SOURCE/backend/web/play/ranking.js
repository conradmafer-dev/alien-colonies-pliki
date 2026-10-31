import {t, html, getLocale} from './i18n.js?v=0111';
import {ART} from './art-manifest.js?v=103';

export const rankingCategories = {total:'Ogólny', buildings:'Budynki', research:'Badania', fleet:'Flota', defense:'Obrona'};
const esc = (value = '') => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const fmt = value => Number(value || 0).toLocaleString(getLocale(), {maximumFractionDigits:0});

const races = {zetans:['Zetanie','zetans'],automatons:['Automatony','automatons'],symbionts:['Symbionci','symbionts']};
const raceHtml = id => races[id] ? html`<span class="ranking-race ranking-race--${races[id][1]}">${t(races[id][0])}</span>` : '';

const phrase = (source, ...values) => { let index=0; return t(source).replace(/%s/g,()=>String(values[index++])); };
export function rankingRewardDisplay(reward, now=Number(reward?.as_of || 0)) {
  const active=reward?.active === true, interval=Number(reward?.interval_seconds || 0);
  const elapsed=active ? Math.max(0,now-Number(reward?.as_of || now)) : 0;
  const progress=Math.min(1,Math.max(0,Number(reward?.progress || 0)+(active&&interval>0?elapsed/interval:0)));
  const remaining=Math.max(0,Number(reward?.remaining_seconds || 0)-elapsed), minutes=Math.ceil(remaining/60);
  const clock=minutes>=1440 ? phrase('%sd %sh',Math.floor(minutes/1440),Math.floor(minutes/60)%24) : phrase('%sh %smin',Math.floor(minutes/60),minutes%60);
  return {progress,caption:active ? phrase('Premia · #%s · 1 / %s d',fmt(reward.position),fmt(reward.days_per_crystal)) : phrase('Premia · #%s · poza TOP 30',fmt(reward?.position)),
    status:`${Math.floor(progress*100)}% · ${active ? remaining>0?phrase('Następny: %s',clock):t('Sprawdzanie nagrody…') : t('Naliczanie wstrzymane')}`};
}
export function rankingRewardHtml(reward) {
  if(reward?.schema!==1)return '';
  const view=rankingRewardDisplay(reward);
  return html`<div class="ranking-reward" data-ranking-reward><div class="ranking-reward-line"><img class="ranking-reward-crystal" src="${ART['swarm/crystal'].small}" width="28" height="28" alt="${t('Kryształy Roju')}" data-art-key="swarm/crystal"><strong data-ranking-reward-caption>${esc(view.caption)}</strong><details class="ranking-reward-help"><summary aria-label="${t('Zasady nagród')}">?</summary><div class="ranking-reward-rules"><strong>${t('Premia za ranking ogólny')}</strong><p>${esc(t('1. miejsce: 1 kryształ / 3 doby\n2–3: 1 / 5 dób\n4–10: 1 / 7 dób\n11–30: 1 / 14 dni'))}</p><p>${t('Postęp nalicza się za czas utrzymywania pozycji, także poza grą. Zmiana miejsca zmienia tempo. Poza TOP 30 naliczanie jest wstrzymane, a postęp zachowany. Pełne kryształy trafiają automatycznie na konto i do raportów.')}</p></div></details></div><div class="ranking-reward-line"><progress data-ranking-reward-progress max="1" value="${view.progress}" aria-label="${t('Postęp premii rankingowej')}"></progress><span data-ranking-reward-status>${esc(view.status)}</span></div></div>`;
}
export function refreshRankingReward(root,reward,now) {
  const panel=root?.querySelector('[data-ranking-reward]');
  if(!panel||reward?.schema!==1)return;
  const view=rankingRewardDisplay(reward,now);
  panel.querySelector('[data-ranking-reward-caption]').textContent=view.caption;
  panel.querySelector('[data-ranking-reward-status]').textContent=view.status;
  panel.querySelector('[data-ranking-reward-progress]').value=view.progress;
}

export function rankingHtml(view, {category = 'total', busy = false, error = '', reward = null} = {}) {
  const own = view?.self;
  if(Number(view?.reward?.as_of || 0)>Number(reward?.as_of || 0))reward=view.reward;
  return html`<section class="panel ranking-own" aria-live="polite"><h2>${t('Twoja pozycja')}${own ? ` · #${fmt(own.position)} · ${fmt(own.score)} ${t('pkt')}` : ' · —'}</h2>${own ? html`<p class="muted">${['buildings','research','fleet','defense'].map(key => `${esc(t(rankingCategories[key]))}: ${fmt(own.scores[key])}`).join(' · ')}</p>` : ''}</section>
  ${rankingRewardHtml(reward)}
  <section class="panel ranking-panel" aria-busy="${busy}"><div class="ranking-toolbar"><label>${t('Kategoria rankingu')}<select id="ranking-category">${Object.entries(rankingCategories).map(([key,label]) => html`<option value="${key}"${category === key ? ' selected' : ''}>${t(label)}</option>`).join('')}</select></label><button type="button" class="button subtle" data-ranking-refresh${busy ? ' disabled' : ''}>${t('Odśwież')}</button></div>
  <p class="muted" role="status">${error ? esc(error) : busy ? t('Ładowanie rankingu…') : `${t('Gracze')}: ${fmt(view?.players_total)}`}</p>
  <table class="ranking-table"><thead><tr><th scope="col">#</th><th scope="col">${t('Gracz')}</th><th scope="col">${t('Punkty')}</th></tr></thead><tbody>${(view?.items || []).map(row => html`<tr${row.is_self ? ' class="ranking-self" data-ranking-self aria-current="true"' : ''}><td>${fmt(row.position)}</td><th scope="row">${esc(row.name)}${raceHtml(row.race_id)}</th><td>${fmt(row.score)}</td></tr>`).join('')}</tbody></table>
  <div class="ranking-pagination"><button type="button" class="button subtle" data-ranking-page="${Math.max(1,Number(view?.page || 1) - 1)}" aria-label="${t('Poprzednia strona')}"${busy || !view || view.page <= 1 ? ' disabled' : ''}>‹</button><span>${fmt(view?.page || 1)} / ${fmt(view?.pages || 1)}</span><button type="button" class="button" data-ranking-own${busy ? ' disabled' : ''}>${t('Moja pozycja')}</button><button type="button" class="button subtle" data-ranking-page="${Number(view?.page || 1) + 1}" aria-label="${t('Następna strona')}"${busy || !view || view.page >= view.pages ? ' disabled' : ''}>›</button></div></section>
  <section class="panel"><p class="muted">${t('1 punkt = 1000 surowców wartości ukończonych budynków, badań, floty i obrony. Floty w misji również się liczą. Zapasy i Kryształy Roju nie dają punktów.')}</p><p class="muted">${t('Punkty są zaokrąglane w dół po zsumowaniu wartości. Przy remisie decyduje nazwa gracza.')}</p></section>`;
}
