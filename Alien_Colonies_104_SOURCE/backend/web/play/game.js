import {reportTypeIcon} from './report-icons.js?v=103';
import {fleetMarkerToken,fleetMapColor} from './fleet-motion.js?v=103';
import { t, text, html, getLanguage, getLocale, LANGUAGES, setLanguage } from './i18n.js?v=0111';
import {researchLayout, researchStatus, mountResearchTree} from './research-tree.js?v=20261018-compact-ui';
import { artImage, hasArt, catalogArtKey, planetArtKey, colonyArtKey } from './art.js?v=103';
import { buildingSummary, buildingDescription, buildingComparison, buildingNotes } from './building-effects.js?v=01218-storage';
import {resourceSnapshot} from './resource-storage.js?v=01218-storage';
import { sortSystems, systemStatus, mountGalaxyMap, hasRingTopology, shortestSystemRoute } from './galaxy-map.js?v=20261027-update103';
import {createPlayerActivity, productionWindow} from './player-activity.js?v=20261017-integrated-galaxies';
import {planetInspection, planetDetailsHtml} from './planet-details.js?v=20261017-colony-capture';
import {COLONIZATION_WARNING} from './colony-capture.js?v=20261017-colony-capture';
import {planningActive, canPlanProject, projectNeedsQueue, projectActionHtml, plannedQueuesHtml, subscriptionInfoHtml, reorderPlannedPayload, refreshPlannedQueuePanels, refreshProjectActions} from './planned-queues.js?v=01218-storage';
import {reportDetailsHtml} from './report-details.js?v=20261017-integrated-galaxies';
import {beginGoogleFlow, completeGoogleFlow} from './google-auth.js?v=01219-auth-stage';
import {createEmailFlow} from './email-auth.js?v=01219-auth-stage';
import {catalogDescription} from './catalog-description.js?v=20261017-ship-research-descriptions';
import {createFleetQuoteController, saveFleetDraft, fleetQuoteContext} from './fleet-flow.js?v=103';
import {mountCatalogCarousels} from './catalog-carousel.js?v=20261018-equal-card-panels';

import {rankingHtml,refreshRankingReward} from './ranking.js?v=104';

import {uiText, projectReason, resetMissionDraft, protectedPlanet} from './compact-ui.js?v=01218-storage';

const $ = (selector) => document.querySelector(selector);
const esc = (value = '') => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
const fmt = (value) => Number(value || 0).toLocaleString(getLocale(), {maximumFractionDigits: 0});
const duration = (value) => {
  const seconds = Math.max(0, Math.ceil(Number(value) || 0));
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
  if (seconds < 86400) return text`${Math.floor(seconds / 3600)} godz. ${Math.floor(seconds % 3600 / 60)} min`;
  return text`${Math.floor(seconds / 86400)} dni ${Math.floor(seconds % 86400 / 3600)} godz.`;
};
const dateText = (timestamp) => new Date(Number(timestamp) * 1000).toLocaleString(getLocale(), {day:'numeric', month:'short', hour:'2-digit', minute:'2-digit'});
const icon = (name, size = 18) => {
  const paths = {
    colony:html(["<circle cx=\"12\" cy=\"12\" r=\"7\"/><ellipse cx=\"12\" cy=\"12\" rx=\"11\" ry=\"3\" transform=\"rotate(-25 12 12)\"/>"]),
    megastructures:html(["<circle cx=\"12\" cy=\"12\" r=\"4\"/><ellipse cx=\"12\" cy=\"12\" rx=\"10\" ry=\"7\"/><path d=\"M12 2v4M12 18v4M2 12h4M18 12h4\"/>"]),
    buildings:html(["<path d=\"M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6M9 10h.01M15 10h.01\"/>"]),
    research:html(["<path d=\"M9 3h6M10 3v6L4 19a1.3 1.3 0 0 0 1.1 2h13.8a1.3 1.3 0 0 0 1.1-2L14 9V3M8 14h8\"/>"]),
    ships:html(["<path d=\"m12 3 7 14-7-3-7 3 7-14ZM12 14v7M8 20l-2 1M16 20l2 1\"/>"]),
    fleets:html(["<path d=\"m7 3 4 9-4-2-4 2 4-9Zm10 6 4 9-4-2-4 2 4-9ZM7 10v7M17 16v5\"/>"]),
    defenses:html(["<path d=\"m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3ZM8 12l3 3 5-6\"/>"]),
    ranking:html(['<path d="M7 3h10v6c0 4-2 6-5 6s-5-2-5-6V3ZM7 5H3v3c0 3 2 4 5 4M17 5h4v3c0 3-2 4-5 4M12 15v6M8 21h8"/>']),
    settings:html(["<circle cx=\"12\" cy=\"12\" r=\"4\"/><path d=\"M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2\"/>"]),
    galaxy:html(["<circle cx=\"12\" cy=\"12\" r=\"2\"/><path d=\"M19 4c-1-2-6 0-10 4S3 17 5 19s7 0 11-4 6-9 3-11ZM5 4c-2 1 0 6 4 10s9 6 11 4 0-7-4-11S7 2 5 4Z\"/>"]),
    skills:html(["<path d=\"m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3Z\"/>"]),
    reports:html(["<path d=\"M7 3h10l3 3v15H4V3h3ZM8 9h8M8 13h8M8 17h5\"/>"]),
    chat:html(["<path d=\"M20 4H4v13h4v4l5-4h7V4ZM8 8h8M8 12h5\"/>"]),
    alliance:html(["<circle cx=\"9\" cy=\"8\" r=\"3\"/><path d=\"M3 20v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5\"/>"]),
    metal:html(["<path d=\"m12 3 9 5v9l-9 5-9-5V8l9-5ZM3 8l9 5 9-5M12 13v9\"/>"]),
    crystal:html(["<path d=\"m12 2 7 6-2 10-5 4-5-4L5 8l7-6ZM5 8h14M12 2l-3 6 3 14 3-14-3-6Z\"/>"]),
    fuel:html(["<path d=\"M12 2s7 8 7 13a7 7 0 0 1-14 0c0-5 7-13 7-13ZM8 15a4 4 0 0 0 4 4\"/>"]),
    energy:html(["<path d=\"m13 2-9 12h7l-1 8 10-13h-7l1-7Z\"/>"]),
  };
  return html`<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.colony}</svg>`;
};

const WEB_BUILD = '0.12.34';
const tabs = {
  ranking:[t('Ranking graczy'),t('Ranking graczy')],
  colony:[t('Przegląd kolonii'),t('Kolonia')], buildings:[t('Budynki'),t('Budynki')], research:[t('Badania'),t('Badania')],
  megastructures:[t('Projekty gwiezdne'),t('Projekty')], ships:[t('Stocznia'),t('Stocznia')], fleets:[t('Wysłane floty'),t('Floty')], defenses:[t('Obrona planetarna'),t('Obrona')], galaxy:[t('Galaktyka i floty'),t('Galaktyka')],
  skills:[t('Umiejętności cywilizacji'),t('Umiejętności')], reports:[t('Raporty'),t('Raporty')], chat:[t('Łączność'),t('Łączność')], alliance:[t('Sojusz'),t('Sojusz')], settings:[t('Ustawienia'),t('Ustawienia')],
};
const resourceNames = {metal:t('Metal'), crystal:t('Kryształy'), fuel:t('Paliwo')};
const missionNames = {scout:t('Zwiad'), transport:t('Transport'), expedition:t('Ekspedycja'), colonize:t('Kolonizacja'), attack:t('Atak'), alliance_attack:t('Atak sojuszu'), alliance_defense:t('Wsparcie sojusznika')};
const roleNames = {leader:t('Lider'), officer:t('Oficer'), member:t('Członek')};
const storageKey = 'alien-colonies.session';
let token = '';
try { token = sessionStorage.getItem(storageKey) || ''; } catch { /* Gameplay remains available without persistent browser storage. */ }
let savedTab='colony';
try { const value=sessionStorage.getItem('alien-colonies.tab'); if (tabs[value]) savedTab=value; } catch {}
const model = {token, state:null, tab:savedTab, register:false, busy:false, stateSequence:0, epoch:0, receivedAt:0, syncAt:0, chat:null, alliance:null, galaxyId:'', fleetTarget:'', fleetMission:'scout', fleetPreview:null, uncertain:null};
model.ranking = null;
model.rankingCategory = 'total';
model.rankingBusy = false;
model.rankingError = '';
model.rankingSequence = 0;

const playerActivity = createPlayerActivity();
for (const type of ['pointerdown','keydown','input']) document.addEventListener(type,event => {
  if (event.isTrusted && !event.repeat && !document.hidden) playerActivity.mark();
}, {capture:true,passive:true});
model.googleAuth = {configured:false,require_google_registration:false};
model.googlePending = null;
let googleAuthGeneration = 0;
let googleNameTimer = null;
model.emailAuth = {configured:false};
let emailOwnsBusy = false;
let emailUiTimer = null;
let emailDisplayedPhase = 'closed';
let emailAuthEpoch = 0;
let emailReauthPlayer = '';
const emailFlow = createEmailFlow(api, {
  onChange:renderEmailFlow,
  onAuthenticated(result) {
    // A delayed response may never replace a session accepted by another path.
    if (emailReauthPlayer) {
      if (model.epoch !== emailAuthEpoch || !model.token || model.state?.player?.id !== emailReauthPlayer || result.state?.player?.id !== emailReauthPlayer) {void revokeSession(result.token);return;}
      storeToken(result.token);model.epoch++;pendingQuietRender = false;model.busy = false;
      showGame(result.state);toast(t('Konto tego imperium zostało ponownie potwierdzone przez e-mail.'));
    } else {
      if (model.epoch !== emailAuthEpoch || model.token || model.state) {void revokeSession(result.token);return;}
      acceptGoogleLogin(result);
    }
  },
  onDiscardedSession(sessionToken) {void revokeSession(sessionToken);},
});
model.reportScope = '';
model.reportReadIds = new Set();
model.reportDetail = null;
let reportDetailRequest = 0;
let fleetPreviewRequest = 0;
let fleetFormGeneration = 0;
const fleetQuoteController = createFleetQuoteController({
  read:readFleetQuoteDraft,
  quote:payload => api('/preview', {method:'POST', body:{...payload, allow_unaffordable:true}}),
  onChange:renderFleetQuote,
});
let toastTimer;
let pollTimer;
let galaxyMapController = null;
let researchTreeController = null;
let catalogCarouselController = null;
let pendingQuietRender = false;
let interactionUntil = 0;
const activePointers = new Set();
const isUIInteracting = () => activePointers.size > 0 || performance.now() < interactionUntil;
// Listen in capture phase so every real control participates, including native selects.
document.addEventListener('pointerdown', event => { activePointers.add(event.pointerId); }, true);
for (const type of ['pointerup','pointercancel']) window.addEventListener(type,event=>{
  activePointers.delete(event.pointerId); interactionUntil=performance.now()+300;
},true);
window.addEventListener('blur',()=>{activePointers.clear();interactionUntil=performance.now()+300;});
window.addEventListener('scroll',()=>{interactionUntil=performance.now()+300;},{passive:true,capture:true});

model.researchView = {};
model.catalogViews = {};
model.researchDetail = "";
model.tunnelTarget = "";
model.fleetTravelMode = "normal";
model.fleetSystemId = '';
model.fleetDraft = null;
model.missionSelecting = false;
model.galaxyMode = 'map';
model.selectedSystems = {};
model.galaxyViews = {};
model.detailKey = '';
model.detailPlanet = '';
model.planetDetail = '';
model.planetDetailMarkup = '';
model.planetDetailTrigger = null;
model.detailedBuildings = false;
try { model.detailedBuildings = localStorage.getItem('alien-colonies.detailed-buildings') === '1'; } catch { /* Optional preference. */ }

function reportIdentity(report) {
  return String(report.id || JSON.stringify([report.at || 0, report.title || '', report.text || '']));
}

function storedReportReads(scope) {
  try {
    const ids = JSON.parse(localStorage.getItem(scope) || '[]');
    return Array.isArray(ids) ? ids.filter((id) => typeof id === 'string').slice(0, 256) : [];
  } catch { return []; }
}

function refreshReportScope(force = false) {
  const playerId = model.state?.player?.id;
  const scope = playerId ? `alien-colonies.report-reads:${encodeURIComponent(location.origin)}:${encodeURIComponent(playerId)}` : '';
  if (scope === model.reportScope && !force) return;
  model.reportScope = scope;
  model.reportReadIds = new Set(scope ? storedReportReads(scope) : []);
}

function unreadReportCount() {
  refreshReportScope();
  const ids = new Set((model.state?.reports || []).map(reportIdentity));
  return [...ids].filter((id) => !model.reportReadIds.has(id)).length;
}

function markReportsRead(identity = null) {
  refreshReportScope();
  if (!model.reportScope) return false;
  const currentIds = (model.state.reports || []).map(reportIdentity).filter(id => identity === null || id === identity);
  const changed = currentIds.some((id) => !model.reportReadIds.has(id));
  if (!changed) return false;
  // Merge other browser tabs' reads; bound old IDs beyond the server's 80 reports.
  model.reportReadIds = new Set([...new Set([...currentIds, ...model.reportReadIds, ...storedReportReads(model.reportScope)])].slice(0, 256));
  try { localStorage.setItem(model.reportScope, JSON.stringify([...model.reportReadIds])); } catch { /* Retain reads in this session when storage is unavailable. */ }
  return true;
}

window.addEventListener('storage', (event) => {
  if (model.state && (event.key === model.reportScope || event.key === null)) {
    refreshReportScope(true);
    renderChrome();
  }
});

class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.status = status; }
}

async function api(path, {method = 'GET', body, authenticated = true} = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  const sessionToken = authenticated ? model.token : '';
  const epoch = model.epoch;
  const activity = playerActivity.take({authenticated:!!sessionToken,visible:!document.hidden,method,path});
  try {
    const headers = {'Accept':'application/json', 'Accept-Language':getLanguage(), 'X-PGR-Client-Platform':'web'};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (sessionToken) headers.Authorization = `Bearer ${sessionToken}`;
    if (activity) headers['X-AC-Player-Active'] = '1';
    const response = await fetch(`/api${path}`, {method, headers, body:body === undefined ? undefined : JSON.stringify(body), credentials:'same-origin', cache:'no-store', signal:controller.signal});
    let data;
    try { data = await response.json(); } catch { throw new ApiError(t('Serwer nie zwrócił poprawnej odpowiedzi. Spróbuj ponownie później.'), response.ok ? 0 : response.status); }
    if (!response.ok || data.ok === false) {
      if (response.status === 401 && authenticated && sessionToken === model.token && epoch === model.epoch) {
        clearSession();
        showAuth();
        $('#auth-error').textContent = t('Sesja wygasła. Zaloguj się ponownie.');
        $('#auth-error').hidden = false;
      }
      throw new ApiError(data.error || t('Nie udało się wykonać tej operacji.'), response.status);
    }
    if (data.ok === true && sessionToken === model.token && epoch === model.epoch) playerActivity.acknowledge(activity);
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(error.name === 'AbortError' ? t('Serwer nie odpowiedział na czas. Sprawdź połączenie i spróbuj ponownie.') : t('Nie udało się połączyć z serwerem. Sprawdź połączenie i spróbuj ponownie.'));
  } finally { clearTimeout(timer); }
}

async function revokeSession(sessionToken) {
  if (!sessionToken) return;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    await fetch('/api/logout', {method:'POST', headers:{'Accept':'application/json', 'Accept-Language':getLanguage(), 'X-PGR-Client-Platform':'web', 'Content-Type':'application/json', 'Authorization':`Bearer ${sessionToken}`}, body:'{}', credentials:'same-origin', cache:'no-store', keepalive:true, signal:controller.signal});
  } catch { /* Local logout is complete; revocation must not affect a later session. */ }
  finally { clearTimeout(timer); }
}

function requestId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

function storeToken(value) {
  model.token = value;
  try { value ? sessionStorage.setItem(storageKey, value) : sessionStorage.removeItem(storageKey); } catch { /* Do not block game when storage is unavailable. */ }
}

function clearSession() {
  cancelGoogleName({focus:false});
  if (emailFlow.snapshot().phase !== 'closed') emailFlow.cancel();
  storeToken('');
  fleetQuoteController.cancel();
  model.fleetPreview = null;
  model.fleetDraft = null;
  playerActivity.reset();
  model.epoch++;
  pendingQuietRender = false;
  model.state = null;
  refreshReportScope();
  model.chat = null;
  model.alliance = null;
  model.ranking = null;
  model.rankingCategory = 'total';
  model.rankingBusy = false;
  model.rankingError = '';
  model.rankingSequence++;
  model.uncertain = null;
  model.selectedSystems = {};
  model.galaxyViews = {};
  model.galaxyId = '';
  model.fleetTarget = '';
  model.fleetSystemId = '';
  closeBuildingDetails(false);
  closeResearchDetails(false);
  closePlanetDetails(false);
  closeReportDetails(false);
  $('#queue-subscription-dialog')?.close();
  model.tunnelTarget=''; model.fleetTravelMode='normal'; model.researchView={};
  catalogCarouselController?.destroy(); catalogCarouselController=null; model.catalogViews={};
  researchTreeController?.destroy(); researchTreeController=null;
  galaxyMapController?.destroy();
  galaxyMapController = null;
  clearTimeout(pollTimer);
}

function toast(message, error = false, retry = false) {
  clearTimeout(toastTimer);
  const element = $('#toast');
  element.className = `toast${error ? ' error' : ''}`;
  element.innerHTML = html`<span>${esc(message)}</span>${retry ? html(["<button type=\"button\" data-retry>Sprawdź / ponów</button>"]) : ''}<button type="button" class="toast-close" aria-label="Zamknij powiadomienie" data-close-toast>×</button>`;
  element.hidden = false;
  if (!retry) toastTimer = setTimeout(() => { element.hidden = true; }, error ? 12000 : 6000);
}

function showAuth() {
  $('#auth-screen').hidden = false;
  $('#game-screen').hidden = true;
  $('#password').value = '';
  document.title = t('Graj w Alien Colonies — centrum dowodzenia');
  setAuthMode(model.register);
}

function syncAuthStage() {
  // Provider/name steps own the whole signed-out screen. Config refreshes and
  // language/UI renders cannot expose the previous login underneath them.
  const standalone = !model.state && (Boolean(model.googlePending) || emailFlow.snapshot().phase !== 'closed');
  $('#auth-screen').hidden = Boolean(model.state) || standalone;
  document.body.classList.toggle('auth-step-active', standalone);
}

function setAuthMode(register) {
  model.register = register;
  $('#auth-register').classList.toggle('active', register);
  $('#auth-login').classList.toggle('active', !register);
  $('#auth-register').setAttribute('aria-pressed', String(register));
  $('#auth-login').setAttribute('aria-pressed', String(!register));
  $('#auth-title').textContent = register ? t('Zacznij własną historię.') : t('Witaj, dowódco.');
  const verifiedRegistration = register && (model.googleAuth.require_google_registration || model.emailAuth.configured);
  const verifiedDescription = model.emailAuth.configured ? (model.googleAuth.configured ? t('Utwórz imperium po potwierdzeniu konta Google lub adresu e-mail.') : t('Utwórz imperium po potwierdzeniu adresu e-mail.')) : model.googleAuth.configured ? t('Utwórz imperium po zweryfikowaniu konta Google.') : t('Tworzenie nowych imperiów jest chwilowo niedostępne. Istniejące konta mogą się logować.');
  $('#auth-description').textContent = verifiedRegistration ? verifiedDescription : register ? t('Utwórz konto i postaw pierwszą kolonię.') : t('Zaloguj się, aby wrócić do swojego imperium.');
  $('#auth-form').hidden = verifiedRegistration;
  $('#email-auth-options').hidden = !model.emailAuth.configured;
  $('#auth-email').disabled = model.busy || !model.emailAuth.configured;
  $('#google-auth-options').hidden = !model.googleAuth.configured;
  $('#auth-google').disabled = model.busy;
  $('#auth-submit').innerHTML = register ? html(["Utwórz imperium <span aria-hidden=\"true\">→</span>"]) : html(["Wejdź do imperium <span aria-hidden=\"true\">→</span>"]);
  $('#password').autocomplete = register ? 'new-password' : 'current-password';
  $('#register-note').hidden = !register;
  $('#auth-error').hidden = true;
  syncAuthStage();
}

function googleFlowStatus(message = '') {
  $('#google-flow-status').textContent = message;
  $('#google-flow-status').hidden = !message;
  const status = $('#settings-google-status');
  if (status) {status.textContent = message;status.hidden = !message;}
}

function acceptGoogleLogin(result, mode = 'login') {
  if (!result?.token) throw new ApiError(t('Nie otrzymano sesji gry. Zaloguj się ponownie.'));
  storeToken(result.token);
  model.epoch++;
  pendingQuietRender = false;
  if (mode !== 'link') model.tab = 'colony';
  model.busy = false;
  googleFlowStatus();
  showGame(result.state);
  toast(result.message || (mode === 'link' ? t('Imperium połączono z Google.') : t('Witaj w swoim imperium.')));
}

async function signInWithGoogle(mode = 'login', password = '', {reauth = false} = {}) {
  if (model.busy || !model.googleAuth.configured) return;
  model.busy = true;
  $('#auth-google').disabled = true;
  $('#auth-submit').disabled = true;
  $('#auth-error').hidden = true;
  let awaitingName = false;
  const generation = ++googleAuthGeneration, epoch = model.epoch;
  const isCurrent = () => generation === googleAuthGeneration && epoch === model.epoch;
  const playerId = reauth ? model.state?.player?.id : '';
  try {
    const outcome = await beginGoogleFlow(api,{mode,password,isCurrent,onStatus:message => {if (isCurrent()) googleFlowStatus(message);}});
    if (!isCurrent()) {if (outcome.result?.token) void revokeSession(outcome.result.token);return;}
    if (reauth && (outcome.needsName || outcome.result?.state?.player?.id !== playerId)) {
      if (outcome.result?.token) void revokeSession(outcome.result.token);
      throw new ApiError(t('Wybierz konto Google połączone z tym imperium.'));
    }
    if (outcome.needsName) {
      if (outcome.expiresAt <= Date.now()) throw new ApiError(t('Logowanie przez Google wygasło. Spróbuj ponownie.'));
      model.googlePending = {...outcome,generation,epoch};
      awaitingName = true;
      $('#google-name-error').hidden = true;
      $('#google-empire-name').value = '';
      $('#google-name-submit').disabled = false;
      $('#google-empire-name').disabled = false;
      syncAuthStage();
      $('#google-name-dialog').showModal();
      $('#google-name-dialog').scrollTop = 0;
      $('#google-empire-name').focus();
      clearTimeout(googleNameTimer);
      googleNameTimer = setTimeout(() => {
        if (isCurrent() && model.googlePending?.generation === generation) cancelGoogleName({message:t('Logowanie przez Google wygasło. Spróbuj ponownie.')});
      }, Math.max(0, outcome.expiresAt - Date.now()));
    } else acceptGoogleLogin(outcome.result,reauth ? 'link' : mode);
  } catch (error) {
    if (!isCurrent()) return;
    if (mode === 'link' || reauth) toast(error.message,true);
    else {$('#auth-error').textContent = error.message;$('#auth-error').hidden = false;}
  } finally {
    if (!awaitingName && isCurrent()) {
      model.busy = false;
      $('#auth-google').disabled = false;
      $('#auth-submit').disabled = false;
      googleFlowStatus();
    }
  }
}

function cancelGoogleName({message = '', focus = true} = {}) {
  googleAuthGeneration++;
  clearTimeout(googleNameTimer);googleNameTimer = null;
  model.googlePending = null;
  model.busy = false;
  $('#google-name-dialog').close();
  $('#google-name-dialog').setAttribute('aria-busy','false');
  $('#auth-google').disabled = false;
  $('#auth-submit').disabled = false;
  $('#google-name-submit').disabled = false;
  $('#google-empire-name').disabled = false;
  googleFlowStatus();
  syncAuthStage();
  if (message && !model.state) {$('#auth-error').textContent = message;$('#auth-error').hidden = false;}
  if (focus && !model.state) $('#auth-google').focus();
}

async function submitGoogleName() {
  const pending = model.googlePending;
  if (!pending || $('#google-name-submit').disabled) return;
  const isCurrent = () => model.googlePending === pending && pending.generation === googleAuthGeneration && pending.epoch === model.epoch;
  if (pending.expiresAt <= Date.now()) {cancelGoogleName({message:t('Logowanie przez Google wygasło. Spróbuj ponownie.')});return;}
  $('#google-name-submit').disabled = true;
  $('#google-empire-name').disabled = true;
  $('#google-name-error').hidden = true;
  $('#google-name-dialog').setAttribute('aria-busy','true');
  try {
    const result = await completeGoogleFlow(api,pending.flow,$('#google-empire-name').value.trim());
    if (!isCurrent()) {if (result?.token) void revokeSession(result.token);return;}
    acceptGoogleLogin(result,pending.mode);
  } catch (error) {
    if (!isCurrent()) return;
    if ([401,403,404,410].includes(error.status)) {cancelGoogleName({message:error.message});return;}
    // Keep the verified stage and typed name for validation/network retries.
    $('#google-name-error').textContent = error.message;
    $('#google-name-error').hidden = false;
  } finally {
    if (isCurrent()) {
      $('#google-name-submit').disabled = false;
      $('#google-empire-name').disabled = false;
      $('#google-name-dialog').setAttribute('aria-busy','false');
      syncAuthStage();
    }
  }
}

async function loadGoogleAuthConfig() {
  try {
    const config = await api('/auth/google/config',{authenticated:false});
    model.googleAuth = {configured:config.configured === true,require_google_registration:config.require_google_registration === true};
    if (!model.token) setAuthMode(model.register);
    else if (model.state && model.tab === 'settings' && !model.busy) renderMain();
  } catch { /* An unavailable config endpoint cannot disable legacy sign-in. */ }
}

function renderEmailFlow(view) {
  const dialog = $('#email-auth-dialog');
  const active = view.phase !== 'closed';
  const transition = emailDisplayedPhase !== view.phase;
  if (active && !emailOwnsBusy) {emailOwnsBusy = true;model.busy = true;}
  else if (!active && emailOwnsBusy) {emailOwnsBusy = false;model.busy = false;}
  $('#auth-email').disabled = model.busy || !model.emailAuth.configured;
  $('#auth-google').disabled = model.busy;
  $('#auth-submit').disabled = model.busy;
  $('#auth-login').disabled = active;
  $('#auth-register').disabled = active;
  if (!active) {
    clearInterval(emailUiTimer);emailUiTimer = null;
    if (dialog.open) dialog.close();
    $('#email-address').value = '';
    $('#email-empire-name').value = '';
    $('#email-auth-error').textContent = '';
    $('#email-auth-error').hidden = true;
    emailDisplayedPhase = 'closed';
    syncAuthStage();
    return;
  }
  $('#email-auth-title').textContent = view.nameVerified ? t('Adres e-mail potwierdzony') : emailReauthPlayer ? t('Potwierdź konto przez e-mail') : t('Logowanie przez e-mail');
  syncAuthStage();
  if (!dialog.open) dialog.showModal();
  if (!emailUiTimer) emailUiTimer = setInterval(() => {emailFlow.checkExpiry();renderEmailFlow(emailFlow.snapshot());},1000);
  const submitting = view.phase === 'sending' || view.phase === 'completing';
  dialog.setAttribute('aria-busy',String(submitting));
  $('#email-address-form').hidden = !['email','sending'].includes(view.phase);
  $('#email-address').disabled = submitting;
  $('#email-send').disabled = submitting;
  $('#email-waiting').hidden = view.phase !== 'waiting';
  $('#email-name-form').hidden = !view.nameVerified;
  $('#email-name-submit').disabled = submitting;
  $('#email-empire-name').disabled = submitting;
  $('#email-destination').textContent = t('Link logowania wysłano na {0}.',view.email);
  $('#email-resend').disabled = !view.canResend;
  $('#email-check').disabled = view.phase !== 'waiting';
  $('#email-resend-time').textContent = view.resendSeconds ? t('Możesz wysłać nowy link za {0} s.',view.resendSeconds) : t('Nowy link zastąpi poprzedni.');
  $('#email-auth-status').textContent = view.phase === 'sending' ? t('Wysyłanie linku…') : view.phase === 'completing' ? t('Otwieranie imperium…') : view.phase === 'waiting' ? t('Oczekiwanie na potwierdzenie adresu e-mail…') : '';
  $('#email-auth-status').hidden = !$('#email-auth-status').textContent;
  $('#email-auth-error').textContent = view.error;
  $('#email-auth-error').hidden = !view.error;
  if (transition && view.phase === 'email') {dialog.scrollTop = 0;$('#email-address').focus();}
  if (transition && view.phase === 'name') {if (emailDisplayedPhase === 'waiting') $('#email-empire-name').value = '';dialog.scrollTop = 0;$('#email-empire-name').focus();}
  emailDisplayedPhase = view.phase;
}

async function loadEmailAuthConfig() {
  try {
    const config = await api('/auth/email/config',{authenticated:false});
    model.emailAuth.configured = config.configured === true;
    emailFlow.configure(model.emailAuth.configured);
    if (!model.token) setAuthMode(model.register);
    else if (model.state && model.tab === 'settings' && !model.busy) renderMain();
  } catch {
    // Provider setup is optional. Missing/offline configuration must not affect
    // Google or existing password sign-in and must not expose a dead button.
    model.emailAuth.configured = false;
    emailFlow.configure(false);
    $('#email-auth-options').hidden = true;
  }
}

function showGame(state) {
  cancelGoogleName({focus:false});
  if (emailFlow.snapshot().phase !== 'closed') emailFlow.cancel();
  acceptState(state);
  if (model.tab === 'galaxy') prepareGalaxyEntry();
  $('#auth-screen').hidden = true;
  $('#game-screen').hidden = false;
  document.body.classList.remove('auth-step-active');
  $('#password').value = '';
  document.title = `${state.player?.name || t('Imperium')} — Alien Colonies`;
  renderChrome();
  renderMain();
  schedulePoll();
  if (model.tab === 'ranking') void loadRanking();
}

function acceptState(state) {
  if (!state || !state.player || !state.planet_id) throw new ApiError(t('Niepełny stan gry. Odśwież stronę.'));
  const colonyChanged = model.state?.planet_id && model.state.planet_id !== state.planet_id;
  if (colonyChanged) { fleetQuoteController.cancel(); model.fleetPreview = null; model.fleetDraft = null; model.fleetTarget = ''; fleetPreviewRequest++; }
  model.state = state;
  if ($('#fleet-form') && !model.busy && !colonyChanged) fleetQuoteController.update();
  if (state.selected_planet_lost?.message) toast(state.selected_planet_lost.message, true);
  refreshReportScope();
  model.receivedAt = performance.now();
  model.syncAt = Date.now();
  if (!model.galaxyId) model.galaxyId = state.planet_galaxy_id || state.galaxy?.[0]?.galaxy_id || '';
  if (model.detailPlanet && model.detailPlanet !== state.planet_id) closeBuildingDetails(false);
  renderBuildingDetails();
  renderResearchDetails();
  setConnection(true);
}

function serverNow() { return Number(model.state?.server_time || Date.now()/1000) + (performance.now() - model.receivedAt) / 1000; }
function setConnection(connected) {
  $('#connection-status').classList.toggle('offline', !connected);
  $('#connection-status').innerHTML = html`<span class="status-dot"></span>${connected ? t('Połączono') : t('Brak połączenia')}`;
  $('#connection-status').title = connected ? t('Stan gry jest synchronizowany z serwerem.') : t('Ostatni pobrany stan gry. Ponów odświeżenie, aby wykonać nowe akcje.');
}

async function loadState({quiet = false, planetId} = {}) {
  if (!model.token) return;
  const sequence = ++model.stateSequence;
  if (!quiet) pendingQuietRender = false;
  const epoch = model.epoch;
  const selected = planetId || model.state?.planet_id || '';
  try {
    const response = await api(`/state${selected ? `?planet_id=${encodeURIComponent(selected)}` : ''}`);
    if (epoch !== model.epoch || sequence !== model.stateSequence) return;
    if (quiet && isUIInteracting()) {
      // Keep the entire snapshot pending: dialog/nav refreshes are also DOM writes.
      pendingQuietRender = {state:response.state, sequence, epoch};
      return response;
    }
    acceptState(response.state);
    renderChrome();
    const preserveForm = quiet && (isUIInteracting() || galaxyMapController?.isInteracting() || ['chat','alliance','ranking'].includes(model.tab) || model.tab === 'galaxy' && model.fleetTarget || $('#main').contains(document.activeElement) && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName));
    if (!preserveForm) renderMain();
    else {renderPlanetDetails();refreshPlannedQueuePanels($('#main'),model.state,{busy:model.busy});refreshProjectActions($('#main'),model.state,model.busy);}
    return response;
  } catch (error) {
    if (epoch !== model.epoch) return;
    setConnection(false);
    if (!quiet) toast(error.message, true);
    throw error;
  }
}

function schedulePoll() {
  clearTimeout(pollTimer);
  if (!model.token) return;
  pollTimer = setTimeout(async () => {
    if (!document.hidden && !model.busy) {
      try {
        await loadState({quiet:true});
        if (model.tab === 'chat') await loadChat(true);
      } catch { /* Connection status displays the polling failure. */ }
    }
    schedulePoll();
  }, 12000);
}

function renderChrome() {
  $('#open-ranking').innerHTML = icon('ranking',24);
  const state = model.state;
  if (!state) return;
  $('#player-name').textContent = state.player.name;
  $('#player-race').textContent = state.player.race_name || t('Cywilizacja oczekuje na wybór');
  const portrait = $('.commander-icon');
  const portraitKey = state.race?.portrait_art || '';
  if (portrait.dataset.art !== portraitKey) {
    portrait.innerHTML = artImage(portraitKey, {sizes:'48px', eager:true}) || '✧';
    portrait.dataset.art = portraitKey;
  }
  $('#server-version').textContent = text`Web ${WEB_BUILD} · ${t('Serwer')} ${state.version}`;
  const reportUnread = unreadReportCount();
  const navigation = [['colony',uiText('planet')],['galaxy',t('Galaktyka')],['ships',uiText('fleet')],['research',t('Badania')],['reports',t('Raporty')]];
  const navHtml = navigation.map(([key, label]) => {
    const unread = key === 'reports' ? reportUnread : key === 'ships' ? (state.fleets || []).length : key === 'chat' ? Number(state.communications?.unread || 0) : 0;
    const countLabel = unread ? key === 'reports' ? t('Nowe raporty: {0}', fmt(unread)) : key === 'ships' ? t('Aktywne misje: {0}', fmt(unread)) : '' : '';
    const active = model.tab === key || key === 'colony' && model.tab === 'buildings' || key === 'ships' && ['fleets','defenses'].includes(model.tab);
    return html`<button type="button" data-tab="${key}" class="nav-button${active ? ' active' : ''}"${active ? ' aria-current="page"' : ''}${countLabel ? html` aria-label="${esc(`${label} · ${countLabel}`)}" title="${esc(countLabel)}"` : ''}>${icon(key)}<span class="nav-label">${label}</span>${unread > 0 ? html`<span class="nav-count"${countLabel ? ' aria-hidden="true"' : ''}>${fmt(unread)}</span>` : ''}</button>`;
  }).join('');
  if ($('#game-nav').innerHTML !== navHtml) $('#game-nav').innerHTML = navHtml;
  $('#game-screen').dataset.view = model.tab;
  $('#view-title').textContent = tabs[model.tab][0];
  $('#view-eyebrow').textContent = model.tab === 'galaxy' ? t('POZA HORYZONTEM') : t('CENTRUM DOWODZENIA');
  const selector = $('#planet-select');
  const currentOptions = [...selector.options].map((option) => `${option.value}:${option.text}`).join('|');
  const nextOptions = (state.own_planets || []).map((planet) => `${planet.id}:${planet.name}`).join('|');
  if (currentOptions !== nextOptions) selector.innerHTML = (state.own_planets || []).map((planet) => html`<option value="${esc(planet.id)}">${esc(planet.name)}</option>`).join('');
  selector.value = state.planet_id;
  selector.disabled = model.busy;
  renderResources();
}

function renderResources() {
  const state = model.state;
  if (!state) return;
  const {paused,elapsed} = productionWindow(state,serverNow());
  // Local estimates are presentation only. Server eligibility controls every order.
  const fullNames = [];
  const tiles = Object.entries(resourceNames).map(([key, name]) => {
    const {current, capacity, full} = resourceSnapshot(state, key, elapsed);
    if (full) fullNames.push(name);
    const limit = capacity == null ? '' : html`<div class="resource-capacity" title="${t('Limit {0}', fmt(capacity))}">${t('Limit {0}', compactResource(capacity))}</div>`;
    const rate = full ? t('0 / godz. · magazyn pełny') : paused ? t('0 / godz. · nieaktywność') : text`+${fmt(state.production?.[key])} / godz.`;
    return html`<div class="resource-tile${full ? ' storage-full' : ''}"><span class="resource-icon">${icon(key,17)}</span><div><div class="resource-label">${name}</div><div class="resource-value" title="${fmt(current)}">${compactResource(current)}</div>${limit}<div class="resource-rate${paused || full ? ' warning' : ''}">${rate}</div></div></div>`;
  });
  const energy = state.energy || {};
  const balance = Number(energy.supply || 0) - Number(energy.used || 0);
  tiles.push(html`<div class="resource-tile"><span class="resource-icon">${icon('energy',17)}</span><div><div class="resource-label">Energia</div><div class="resource-value">${balance >= 0 ? '+' : ''}${compactResource(balance)}</div><div class="resource-rate${balance < 0 ? ' warning' : ''}">${fmt(energy.supply)} / ${fmt(energy.used)} użycia</div></div></div>`);
  $('#resources').innerHTML = tiles.join('');
  const storageNotice = $('#storage-status');
  if (storageNotice) {
    storageNotice.hidden = !fullNames.length;
    storageNotice.textContent = fullNames.length ? `${t('Magazyn pełny — rozbuduj skarbiec')} · ${fullNames.join(', ')}` : '';
  }
  const notice = $('#production-status');
  if (notice) {
    notice.hidden = !paused;
    const markup = html`<strong>Produkcja wstrzymana po 7 dniach nieaktywności.</strong><span>Surowce pozostają w magazynach. Wróć do gry, aby wznowić produkcję we wszystkich koloniach; przerwa nie zostanie odrobiona.</span><button type="button" class="button small primary" data-resume-production>Wznów produkcję</button>`;
    if (paused && notice.innerHTML !== markup) notice.innerHTML = markup;
  }
}

function compactResource(value) {
  const number=Number(value)||0;
  if (Math.abs(number)<1e6) return fmt(number);
  const divisor=Math.abs(number)>=1e9?1e9:1e6;
  const truncated=Math.trunc(number/divisor*100)/100;
  return `${truncated.toLocaleString(getLocale(),{maximumFractionDigits:2})} ${divisor===1e9?t('mld'):t('mln')}`;
}

function costHtml(cost = {}, multiplier = 1) {
  return html`<div class="cost-list">${Object.keys(resourceNames).map((key) => html`<span class="${Number(cost[key] || 0) * multiplier > Number(model.state.resources?.[key] || 0) ? 'shortfall' : ''}">${icon(key,12)} ${fmt(Number(cost[key] || 0) * multiplier)}</span>`).join('')}</div>`;
}

function queueHtml() {
  const state = model.state;
  const queue = [...(state.queue || [])];
  if (state.research_queue && state.research_queue.planet_id !== state.planet_id) queue.push(state.research_queue);
  if (!queue.length) return html(["<p class=\"empty-state\">Wszystkie projekty ukończone. Rozpocznij rozbudowę kolonii, badania lub produkcję w stoczni.</p>"]);
  return queue.map((task) => {
    const group = {build:'buildings', research:'research', ship:'ships', defense:'defenses'}[task.kind];
    const item = state.catalog?.[group]?.find((entry) => entry.key === task.key);
    const remaining = Math.max(0, Number(task.ends_at) - serverNow());
    const progress = Math.min(100, Math.max(0, 100 * (1 - remaining / Number(task.seconds || 1))));
    return html`<div class="queue-row"><div class="queue-item">${artImage(catalogArtKey(item, group), {className:'queue-art', sizes:'58px'})}<div class="queue-copy"><strong>${esc(item?.name || task.key)}</strong><span class="muted">${task.kind === 'ship' || task.kind === 'defense' ? text`${fmt(task.amount)} szt.` : text`Poziom ${fmt(task.level)}`}${task.planet_name ? ` · ${esc(task.planet_name)}` : ''}</span><div class="progress"><span data-progress="${esc(task.id)}" data-ends="${Number(task.ends_at)}" data-seconds="${Number(task.seconds || 1)}" style="width:${progress}%"></span></div></div></div><div class="queue-right"><span class="countdown" data-countdown="${Number(task.ends_at)}">${duration(remaining)}</span>${task.planet_id && task.planet_id !== state.planet_id ? '' : html`<button type="button" class="button small subtle" data-cancel="${esc(task.id)}">Anuluj</button>`}</div></div>`;
  }).join('');
}

function raceHtml() {
  const state = model.state;
  if (state.player.race_id) return '';
  return html`<section class="panel"><div class="race-intro"><p class="eyebrow">PIERWSZA DECYZJA</p><h2>Wybierz swoją cywilizację</h2><p class="section-intro">Każda rasa ma własną gospodarkę, okręty i technologie. Ten wybór jest stały dla twojego imperium.</p></div><div class="race-grid">${(state.races || []).map((race) => html`<article class="race-card"><div class="race-portrait">${artImage(race.portrait_art, {sizes:'(max-width:850px) 85vw, 30vw', eager:true})}</div><div class="race-info"><h3>${esc(race.name)}</h3><p>${esc(race.description)}</p><p class="trait">${esc(race.trait)}</p><p class="tradeoff">${esc(race.tradeoff)}</p><button type="button" class="button primary" data-race="${esc(race.id)}" ${!state.race_choice_allowed || model.busy ? 'disabled' : ''}>Wybierz ${esc(race.name)}</button></div></article>`).join('')}</div>${!state.race_choice_allowed ? html`<p class="project-reason">${esc(state.race_choice_reason)}</p>` : ''}</section>`;
}

function overviewContentHtml() {
  const state = model.state;
  const planet = (state.own_planets || []).find((item) => item.id === state.planet_id) || {};
  const protection = Math.max(0, Number(state.player.protected_until) - serverNow());
  const environment = state.environment || {};
  const guide = state.onboarding || {};
  return html`${raceHtml()}${(state.incoming_attacks || []).length ? html`<div class="notice">${state.incoming_attacks.map((fleet) => html`<strong>${esc(fleet.mission === 'colonize' ? t('Przejęcie kolonii') : t('Atak'))}:</strong> Nadciąga ${esc(fleet.attacker_name)} → ${esc(fleet.target_name)}. Do celu: <span data-countdown="${Number(fleet.arrives_at)}">${duration(Number(fleet.arrives_at) - serverNow())}</span>.`).join(html(["<br>"]))}</div>` : ''}<div class="overview-grid"><section class="panel colony-banner">${artImage(colonyArtKey(state), {className:'colony-scene', sizes:'(max-width:620px) 100vw, 85vw', eager:true})}<div class="colony-copy"><p class="eyebrow">TWOJA KOLONIA</p><h2>${esc(state.planet_name)}</h2><p class="muted">${esc(environment.type_name || t('Planeta'))} · ${esc(planet.system_id || '')} · ${esc(state.planet_galaxy_id || '')}</p><div class="stat-pills"><span class="pill">${fmt(state.own_planets?.length)} / ${fmt(state.limits?.colonies)} kolonii</span><span class="pill">${fmt(state.fields?.free)} wolnych pól</span>${protection > 0 ? html(["<span class=\"pill gold\">Ochrona startowa</span>"]) : ''}</div><div class="form-actions"><button type="button" class="button small subtle" data-tab="buildings">Rozwijaj kolonię →</button></div></div><div class="colony-planet" aria-hidden="true">${artImage(planetArtKey({environment}), {sizes:'(max-width:620px) 72px, 112px', eager:true})}</div></section><section class="panel"><div class="panel-heading"><h2>Sytuacja imperium</h2>${icon('colony')}</div><dl class="data-grid"><div><dt>Floty w misji</dt><dd>${fmt(state.fleets?.length)} / 8</dd></div><div><dt>Statki w kolonii</dt><dd>${fmt(Object.values(state.ships || {}).reduce((sum, n) => sum + Number(n), 0))}</dd></div><div><dt>Kryształy Roju</dt><dd>${fmt(state.player.swarm_crystals)}</dd></div><div><dt>Sojusz</dt><dd>${esc(state.alliance?.tag || t('Brak'))}</dd></div><div><dt>Wydajność wydobycia</dt><dd>${fmt(Number(state.energy?.factor || 0) * 100)}%</dd></div><div><dt>Ochrona startowa</dt><dd>${protection ? html`<span data-countdown="${Number(state.player.protected_until)}">${duration(protection)}</span>` : t('Zakończona')}</dd></div></dl></section><section class="panel"><div class="panel-heading"><h2>Aktywne projekty</h2><span class="muted">Budowa · badania · stocznia</span></div>${queueHtml()}</section><section class="panel"><div class="panel-heading"><h2>Pierwsze kroki</h2><span class="muted">${fmt(guide.completed_count)} / ${fmt(guide.total || 5)}</span></div>${(guide.steps || []).map((step, index) => html`<div class="guide-step${step.done ? ' done' : ''}"><span class="step-number">${step.done ? '✓' : index + 1}</span><div><strong>${esc(step.title)}</strong><p>${esc(step.description)}</p></div></div>`).join('') || html(["<p class=\"empty-state\">Wybierz rasę i rozpocznij rozwój swojej kolonii.</p>"])}</section></div><section class="panel"><div class="panel-heading"><h2>Ostatnie raporty</h2><button type="button" data-tab="reports" class="button small subtle">Wszystkie raporty →</button></div>${(state.reports || []).slice(0,3).map((report) => html`<button type="button" class="list-row report-preview" data-report="${esc(reportIdentity(report))}" aria-haspopup="dialog">${reportTypeIcon(report,32)}<span><strong>${esc(report.title)}</strong><span class="muted">${esc(String(report.text || '').slice(0,200))}${String(report.text || '').length > 200 ? '…' : ''}</span></span><time class="muted">${esc(dateText(report.at))}</time></button>`).join('') || html(["<p class=\"empty-state\">Raporty zwiadu, rozwoju i walk pojawią się tutaj.</p>"])}</section>`;
}

function overviewHtml() {
  return overviewContentHtml() + plannedQueuesHtml(model.state,{busy:model.busy});
}

function buildingActionHtml(item, inDialog = false) {
  const normalLabel = `${Number(item.level) ? t('Ulepsz') : t('Zbuduj')} → ${fmt(Number(item.level) + 1)}`;
  return projectActionHtml(model.state,item,'build',model.busy,{normalLabel,className:'building-upgrade',detail:inDialog});
}

function catalogCarouselHtml(key, title, cards) {
  const id=`catalog-carousel-${key}`;
  return html`<section class="catalog-carousel-section" data-carousel-section="${esc(key)}"><div class="catalog-carousel-heading"><h2 id="${id}-title" class="sr-only">${esc(title)}</h2><div class="catalog-carousel-controls"><button type="button" class="icon-button" data-carousel-step="-1" aria-controls="${id}" aria-label="Poprzednia karta">‹</button><button type="button" class="icon-button" data-carousel-step="1" aria-controls="${id}" aria-label="Następna karta">›</button></div></div><div id="${id}" class="catalog-carousel-track" data-catalog-carousel="${esc(key)}" role="region" tabindex="0" aria-labelledby="${id}-title">${cards}</div></section>`;
}

function buildingCardHtml(item, category) {
  const maximum = Number(item.level) >= Number(item.max_level);
  const id = `building-${item.key}`;
  const comparison = buildingComparison(item, false);
  const requirements = item.requirements || [];
  return html`<article class="project-card building-card" data-building-card="${esc(item.key)}" data-catalog-card="${esc(item.key)}">
    <div class="building-art">${artImage(catalogArtKey(item, 'buildings'), {sizes:'(max-width:620px) 85vw, 340px'})}</div>
    <div class="construction-card-body" data-card-scroll><div class="building-info"><p class="building-category">${esc(category)}</p><h2 id="${esc(id)}">${esc(item.name)}</h2>
      <span class="building-level">Poziom ${fmt(item.level)}${maximum ? ` · ${t('Maksymalny poziom')}` : ''}</span>
      <p class="project-description">${esc(buildingDescription(item))}</p>
      ${comparison.length ? html`<div class="building-card-metrics"><div class="building-card-metrics-heading"><span>Efekt</span><span>${t('Teraz')}${maximum ? '' : html` → ${t('Następny')}`}</span></div><dl>${comparison.map(row=>html`<div><dt>${esc(row.label)}</dt><dd>${esc(row.current)}${maximum ? '' : html`<span> → ${esc(row.next)}</span>`}</dd></div>`).join('')}</dl></div>` : html`<p class="building-effect">${esc(buildingSummary(item))}</p>`}
      ${requirements.length && !maximum ? html`<div class="building-requirements"><h3>Wymagania</h3>${requirementsHtml(requirements)}</div>` : ''}
      ${projectReason(item, model.state) && !maximum ? html`<p class="building-reason">${esc(projectReason(item, model.state))}</p>` : ''}
    </div></div>
    <div class="construction-card-footer">
      ${maximum ? '' : costHtml(item.cost)}
      <div class="construction-footer-controls"><span class="duration">${maximum ? t('Rozbudowa ukończona') : duration(item.seconds)}</span><div class="project-action">${buildingActionHtml(item)}</div></div>
    </div>
  </article>`;
}

function colonyLandscapeHtml() {
  const state=model.state;
  return html`<section class="colony-landscape">${artImage(colonyArtKey(state),{className:'colony-landscape-art',sizes:'100vw',eager:true})}<div><strong>${esc(state.planet_name)}</strong><span>${esc(state.environment?.type_name || '')} · ${fmt(state.fields?.free)} ${uiText('freeFields')}</span></div></section>`;
}

function compactQueueHtml(lane) {
  const state=model.state;
  const queue=(state.queue || []).filter(task=>lane==='build'?task.kind==='build':lane==='ship'?['ship','defense'].includes(task.kind):task.kind==='research');
  if (lane==='research' && state.research_queue && !queue.some(task=>task.id===state.research_queue.id)) queue.push(state.research_queue);
  const planned=(state.planned_orders || []).filter(order=>lane==='research'?order.kind==='research':order.planet_id===state.planet_id&&(lane==='ship'?['ship','defense'].includes(order.kind):order.kind==='build'));
  if(!queue.length && !planned.length)return '';
  return html`<details class="compact-queue"><summary>${t('Aktywne projekty')} · ${queue.length}${planned.length?` + ${planned.length}`:''}</summary><div>${queueHtml()}${plannedQueuesHtml(state,{lanes:[lane],busy:model.busy})}</div></details>`;
}

function buildingsHtml() {
  const state=model.state, items=state.catalog?.buildings || [], inactive=state.inactive_racial_buildings || [];
  const ordered=[...items.filter(item=>!item.unique&&Number(item.level)>0),...items.filter(item=>!item.unique&&!Number(item.level)),...items.filter(item=>item.unique)];
  const cards=ordered.map(item=>buildingCardHtml(item,'')).join('')+stellarCardsHtml();
  return html`${!state.player.race_id?raceHtml():''}${colonyLandscapeHtml()}${compactQueueHtml('build')}${catalogCarouselHtml('buildings',t('Budynki kolonii'),cards)}
    ${inactive.length?html`<details class="compact-queue"><summary>${t('Nieaktywne budynki innych ras')} · ${inactive.length}</summary>${inactive.map(item=>html`<p>${esc(item.name)} · ${esc(item.race_name)} · ${fmt(item.level)}</p>`).join('')}</details>`:''}`;
}

function renderBuildingDetails() {
  const dialog = $('#building-dialog');
  if (!dialog || !model.detailKey || !model.state) return;
  const item = model.state.catalog?.buildings?.find((entry) => entry.key === model.detailKey);
  if (!item) { closeBuildingDetails(false); return; }
  const maximum = Number(item.level) >= Number(item.max_level);
  const rows = buildingComparison(item, model.detailedBuildings);
  const notes = buildingNotes(item, model.detailedBuildings);
  const requirements = item.requirements || [];
  const active = document.activeElement;
  const focusId = dialog.contains(active) ? active.id : '';
  $('#building-detail-content').innerHTML = html`<header class="building-detail-header"><div class="building-detail-art">${artImage(catalogArtKey(item, 'buildings'), {sizes:'150px', eager:true})}</div><div><p class="eyebrow">BUDYNEK KOLONII</p><h2 id="building-detail-title">${esc(item.name)}</h2><span class="muted">${esc(model.state.planet_name)} · Poziom ${fmt(item.level)}</span></div></header>
    <p class="building-detail-description">${esc(model.detailedBuildings ? item.description : buildingDescription(item))}</p>
    <div class="effect-comparison"><table><thead><tr><th scope="col">Efekt</th><th scope="col">Teraz<span>Poziom ${fmt(item.level)}</span></th>${maximum ? '' : html`<th scope="col">Następny<span>Poziom ${fmt(Number(item.level) + 1)}</span></th>`}</tr></thead><tbody>${rows.map((row) => html`<tr><th scope="row">${esc(row.label)}</th><td>${esc(row.current)}</td>${maximum ? '' : html`<td class="next-value">${esc(row.next)}</td>`}</tr>`).join('')}</tbody></table></div>
    ${notes.map((note) => html`<p class="building-detail-note">${esc(note)}</p>`).join('')}
    ${requirements.length && !maximum ? html`<div class="building-requirements"><h3>Wymagania</h3>${requirements.map((requirement) => html`<span class="requirement${requirement.met ? ' met' : ' missing'}">${requirement.met ? '✓' : '○'} ${esc(requirement.name)} · poz. ${fmt(requirement.level)}</span>`).join('')}</div>` : ''}
    <label class="detail-preference"><input type="checkbox" id="detailed-buildings"${model.detailedBuildings ? ' checked' : ''}> Szczegółowe opisy</label>
    <footer class="building-detail-footer"><div>${maximum ? html(["<span class=\"pill\">Maksymalny poziom</span>"]) : html`${costHtml(item.cost)}<span class="duration">Czas: ${duration(item.seconds)}</span>`}</div>${buildingActionHtml(item, true)}</footer>
    ${projectReason(item, model.state) && !maximum ? html`<p class="building-detail-reason">${esc(projectReason(item, model.state))}</p>` : ''}`;
  if (focusId) document.getElementById(focusId)?.focus({preventScroll:true});
}

function closeBuildingDetails(restoreFocus = true) {
  const key = model.detailKey;
  model.detailKey = '';
  model.detailPlanet = '';
  const dialog = $('#building-dialog');
  if (dialog?.open) dialog.close();
  if (restoreFocus && key) [...document.querySelectorAll('[data-building]')].find((button) => button.dataset.building === key)?.focus({preventScroll:true});
}

const effectLabel = (item, next = false) => {
  if (next && Number(item.level) >= Number(item.max_level)) return t('Maksymalny poziom');
  return item[next ? 'effect_next' : 'effect_current'] || t('Brak dodatkowego efektu');
};

function requirementsHtml(requirements = []) {
  return html`<div class="requirements-list">${requirements.map(req => {
    const current = req.current ?? (req.group === 'research' ? model.state.research?.[req.key] : req.group === 'buildings' ? model.state.buildings?.[req.key] : 0) ?? 0;
    const content=html`<span aria-hidden="true">${req.met ? '✓' : '○'}</span><span>${esc(req.name)}</span><span class="req-level">${fmt(current)}/${fmt(req.level)}</span>`;
    const attr=req.group==='research' ? `data-open-research="${esc(req.key)}"` : req.group==='megastructures' ? 'data-open-stellar' : '';
    return attr ? html`<button type="button" class="requirement${req.met?' met':''}" ${attr}>${content}</button>` : html`<span class="requirement${req.met?' met':''}">${content}</span>`;
  }).join('')}</div>`;
}

function researchHtml() {
  const state=model.state, items=state.catalog?.research || [], graph=researchLayout(items);
  const statuses={ready:t('Można badać'),waiting:t('Wymagania spełnione'),locked:uiText('locked'),learned:t('Zbadano'),complete:t('Ukończono'),active:t('Badanie trwa')};
  return html`${!state.player.race_id?raceHtml():''}${compactQueueHtml('research')}<section class="tech-map-panel"><div class="tech-tree-scroll" id="research-tree-scroll" aria-label="${esc(t('Badania'))}"><div class="tech-tree" style="--tech-columns:${Math.max(1,graph.columns)}"><svg class="tech-links" aria-hidden="true"></svg>${graph.nodes.map(({item,row,column})=>{
    const status=researchStatus(item,state.research_queue), description=catalogDescription(item);
    return html`<article class="tech-node ${status}" style="grid-row:${row+1};grid-column:${column+1}" data-research-node="${esc(item.key)}"><div class="tech-node-head">${artImage(catalogArtKey(item,'research'),{className:'tech-node-art',sizes:'64px'})}<span class="tech-node-level">${fmt(item.level)} / ${fmt(item.max_level)}</span></div><div class="tech-node-copy" tabindex="0"><strong class="tech-node-title">${esc(item.name)}</strong><p class="tech-node-description">${esc(description)}</p></div><button type="button" class="tech-node-action" data-research="${esc(item.key)}" aria-label="${esc(`${item.name}: ${uiText('details')}`)}">${statuses[status]} <span aria-hidden="true">›</span></button></article>`;
  }).join('')}</div></div></section>`;
}

function renderResearchDetails() {
  const dialog=$('#research-dialog');
  if (!model.researchDetail || !model.state) { if (dialog.open) dialog.close(); return; }
  const item=model.state.catalog?.research?.find(item=>item.key===model.researchDetail);
  if (!item) {closeResearchDetails(false);return;}
  const queue=model.state.research_queue?.key===item.key ? model.state.research_queue : null;
  const max=item.level>=item.max_level;
  const groupNames={ships:t('Stocznia'),research:t('Technologia'),megastructures:t('Projekt gwiezdny')};
  const relevant=(item.unlocks||[]).sort((a,b)=>a.level-b.level || (a.group==='ships'?-1:1));
  $('#research-detail-content').innerHTML=html`<p class="eyebrow">${item.unique?t('TECHNOLOGIA RASOWA'):t('BADANIA IMPERIUM')}</p><div class="research-detail-heading">${artImage(catalogArtKey(item,'research'),{sizes:'88px',eager:true})}<h2 id="research-detail-title">${esc(item.name)}</h2></div><p class="project-description">${esc(catalogDescription(item))}</p>
    <div class="research-levels"><div><span>Obecnie · poziom ${fmt(item.level)}</span><strong>${esc(effectLabel(item))}</strong></div><div class="next"><span>${max?t('Projekt ukończony'):text`Następnie · poziom ${fmt(Number(item.level)+1)}`}</span><strong>${esc(effectLabel(item,true))}</strong></div></div>
    ${!max?html`${costHtml(item.cost)}<span class="duration">Czas badania: ${duration(item.seconds)}</span>`:''}
    <h3>Wymagania</h3>${requirementsHtml(item.requirements)}
    ${relevant.length?html`<h3>Do czego prowadzi</h3><div class="tech-unlocks">${relevant.map(unlock=>{
      const attr=unlock.group==='research'?`data-open-research="${esc(unlock.key)}"`:unlock.group==='ships'?`data-open-ship="${esc(unlock.key)}"`:'data-open-stellar';
      return html`<button type="button" class="tech-unlock" ${attr}><span>${esc(unlock.name)}<small>${groupNames[unlock.group]}${unlock.other_requirements_met?t(' · pozostałe wymagania spełnione'):t(' · ma też inne wymagania')}</small></span><span class="level">${unlock.met?'✓ ':''}Poz. ${fmt(unlock.level)}</span></button>`;
    }).join('')}</div>`:''}
    ${queue?html`<p class="effect">Badanie trwa${queue.planet_name?` · ${esc(queue.planet_name)}`:''}. Pozostało <span data-countdown="${queue.ends_at}">${duration(queue.ends_at-serverNow())}</span>.</p>`:''}
    ${!max?html`<div class="dialog-project-action">${projectActionHtml(model.state,item,'research',model.busy,{normalLabel:text`Badaj poziom ${fmt(Number(item.level)+1)}`})}<button type="button" class="button subtle" data-locate-research="${esc(item.key)}">Pokaż w drzewie</button></div>`:''}
    ${projectReason(item, model.state)&&!queue?html`<p class="project-reason">${esc(projectReason(item, model.state))}</p>`:''}`;
}

function openResearchDetails(key) {
  if (!model.state?.catalog?.research?.some(item=>item.key===key)) return;
  closeBuildingDetails(false);
  model.researchDetail=key;
  renderResearchDetails();
  const dialog=$('#research-dialog');
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop=0;
}
function closeResearchDetails(restoreFocus=true) {
  const key=model.researchDetail;
  model.researchDetail='';
  const dialog=$('#research-dialog');
  if(dialog.open)dialog.close();
  if(restoreFocus&&key) document.querySelector(`[data-research="${CSS.escape(key)}"]`)?.focus({preventScroll:true});
}

function shipStatsHtml(item) {
  const nf=value=>Number(value||0).toLocaleString(getLocale(),{maximumFractionDigits:2});
  let special='';
  if(item.special_traits?.first_volley)special=text`Własna pierwsza salwa: ${fmt(item.effective_first_volley_attack)} ataku (łącznie ×${nf(item.first_volley_multiplier)}).`;
  if(item.special_traits?.regeneration_fraction)special=text`Regeneracja własnego ocalałego kadłuba: ${fmt(item.regeneration_fraction*100)}% ran po rundzie.`;
  if(item.special_traits?.damage_reduction)special=text`Łączna redukcja obrażeń tego okrętu: ${nf(item.damage_reduction*100)}%.`;
  return html`<dl class="ship-stats"><div><dt>Atak</dt><dd>${fmt(item.effective_attack??item.attack)}</dd></div><div><dt>Kadłub</dt><dd>${fmt(item.hull)}</dd></div><div><dt>Ładownia</dt><dd>${fmt(item.capacity)}</dd></div><div><dt>Prędkość</dt><dd>×${nf(item.effective_speed??item.speed)}</dd></div><div><dt>Współczynnik paliwa</dt><dd>${nf(item.effective_fuel??item.fuel)}</dd></div><div><dt>W kolonii</dt><dd>${fmt(item.count)}</dd></div></dl>${special?html`<p class="ship-special">${esc(special)}</p>`:''}`;
}

function stellarCardsHtml() {
  const state=model.state, mega=state.megastructures || {}, queue=mega.queue;
  const stage=Number(mega.dyson_stage || 0), gate=Number(mega.gate_level || 0), window=mega.window;
  const targets=(state.galaxy || []).flatMap(system=>(system.planets || []).map(planet=>({...planet,systemName:system.name}))).filter(planet=>planet.id!==mega.origin_id);
  if(!targets.some(planet=>planet.id===model.tunnelTarget))model.tunnelTarget=targets[0]?.id || '';
  return (mega.projects || []).map(project=>{
    const dyson=project.key==='dyson', complete=project.level>=project.max_level;
    const building=queue?.key===project.key;
    const title=uiText(dyson?'dyson':'wormhole');
    const origin=mega.origin_id&&!mega.is_origin?html`<button type="button" class="button small subtle" data-stellar-origin="${esc(mega.origin_id)}">${uiText('projectOrigin')}: ${esc(mega.origin_name)}</button>`:'';
    const tunnelBody=!dyson&&gate?window?html`<div class="tunnel-window"><strong>${esc(window.target_name)}</strong><p>${uiText('readyIn')} <span data-countdown="${window.ready_at}">${duration(window.ready_at-serverNow())}</span> · <span data-countdown="${window.closes_at}">${duration(window.closes_at-serverNow())}</span></p></div>`:html`<label for="tunnel-target">${t('Planeta docelowa (znane układy)')}</label><select id="tunnel-target">${targets.map(planet=>html`<option value="${esc(planet.id)}"${model.tunnelTarget===planet.id?' selected':''}>${esc(planet.systemName)} · ${esc(planet.name)}</option>`).join('')}</select>`:'';
    const tunnelFooter=!dyson&&gate?window?html`<div class="project-action"><button type="button" class="button primary" data-tunnel-fleet="${esc(window.target_id)}"${!mega.is_origin?' disabled':''}>${uiText('newMission')}</button><button type="button" class="button subtle" data-tunnel-close${!mega.is_origin?' disabled':''}>${t('Zamknij tunel')}</button></div>`:html`<p class="tunnel-energy-cost">${uiText('energy')}: ${fmt(mega.opening_required)}</p><div class="project-action"><button type="button" class="button primary" data-tunnel-open${stage<4||!mega.is_origin||!targets.length||Number(mega.energy)<Number(mega.opening_required)||model.busy?' disabled':''}>${uiText('openWormhole')}</button></div>`:'';
    const constructionFooter=building?html`<div class="construction-footer-controls"><span class="duration" data-countdown="${queue.ends_at}">${duration(queue.ends_at-serverNow())}</span><div class="project-action"><button type="button" class="button subtle" data-megacancel="${esc(queue.id)}"${!mega.is_origin?' disabled':''}>${t('Anuluj')}</button></div></div>`:!complete?html`${costHtml(project.cost)}<div class="construction-footer-controls"><span class="duration">${duration(project.seconds)}</span><div class="project-action"><button type="button" class="button primary" data-megabuild="${esc(project.key)}"${!project.enabled||model.busy?' disabled':''}>${uiText('startBuild')}</button></div></div>`:'';
    return html`<article class="project-card building-card megastructure-card" data-catalog-card="${esc(project.key)}">
      <div class="building-art">${artImage(`megastructures/${project.key}`,{sizes:'(max-width:620px) 85vw, 380px'})}</div>
      <div class="construction-card-body" data-card-scroll><div class="building-info"><h2>${title}</h2><span class="building-level">${dyson?`${uiText('stage')} ${stage} / 4`:gate?uiText('completed'):t('Poziom {0}',0)}</span><p class="project-description">${uiText(dyson?'dysonDescription':'wormholeDescription')}</p>${origin}${dyson?html`<p class="building-effect">${uiText('energy')}: <span data-mega-energy>${fmt(mega.energy)}</span> / ${fmt(mega.capacity)} · +${fmt(mega.charge_per_second)}/s</p>`:''}${!complete?html`<p class="muted">${esc(project.name)}</p>${requirementsHtml(project.requirements || [])}`:''}${!building&&!complete&&projectReason(project, model.state)?html`<p class="project-reason">${esc(projectReason(project, model.state))}</p>`:''}${tunnelBody}</div></div>
      ${constructionFooter||tunnelFooter?html`<div class="construction-card-footer">${constructionFooter}${tunnelFooter}</div>`:''}
    </article>`;
  }).join('');
}

function stellarHtml() { return buildingsHtml(); }

function fleetNavigationHtml(group) {
  if (group === 'mission' || group === 'picker') return html`<div class="fleet-navigation fleet-flow-navigation"><button type="button" class="button subtle" data-fleet-back>← Wstecz</button><strong>${group === 'picker' ? uiText('chooseTarget') : t('Przygotuj flotę')}</strong><button type="button" class="button fleet-active-button" data-tab="fleets">${icon('fleets')} <span>${uiText('activeMissions')} (${fmt(model.state.fleets?.length)})</span></button></div>`;
  const target=group==='ships'?'defenses':'ships';
  const label=group==='ships'?uiText('defenses'):group==='defenses'?uiText('ships'):uiText('construction');
  return html`<div class="fleet-navigation">${group === 'fleets' && model.fleetTarget ? html`<button type="button" class="button subtle" data-resume-fleet>← Wstecz</button>` : ''}<button type="button" class="button" data-new-mission>${uiText('newMission')}</button><button type="button" class="button" data-tab="${target}">${label}</button><button type="button" class="button fleet-active-button" data-tab="fleets" aria-label="${uiText('activeMissions')}">${icon('fleets')} <span>${fmt(model.state.fleets?.length)}</span></button></div>`;
}

function catalogHtml(group) {
  const state = model.state;
  if (group === 'buildings') return buildingsHtml();
  if (group === 'research') return researchHtml();
  const type = {buildings:'build', research:'research', ships:'ship', defenses:'defense'}[group];
  const countable = group === 'ships' || group === 'defenses';
  const descriptions = {
    buildings:t('Gospodarka zasila każdą wyprawę. Rozwijaj wydobycie i dbaj o bilans energii. W kolonii może trwać jeden projekt budowlany.'),
    research:t('Technologie działają w całym imperium. Rozwijaj laboratorium, aby odblokować kolejne projekty. Jedno badanie może trwać jednocześnie.'),
    ships:t('Przesuwaj karty w bok, aby porównać statki. Wybierz liczbę i rozpocznij produkcję.'),
    defenses:t('Umocnij kolonię przed atakiem. Obrona pozostaje na planecie i korzysta z tej samej kolejki produkcji co statki.'),
  };
  const cards = (state.catalog?.[group] || []).map((item) => html`<article class="project-card" data-ship-card="${group==='ships'?esc(item.key):''}" data-catalog-card="${esc(item.key)}">
    <div class="project-art">${artImage(catalogArtKey(item, group),group==='ships'?{sizes:'(max-width:620px) 85vw, 340px'}:{})}</div>
    <div class="construction-card-body" data-card-scroll><div class="project-info"><span class="building-level">${countable ? text`W kolonii: ${fmt(item.count ?? item.level)}` : text`Poziom ${fmt(item.level)} / ${fmt(item.max_level)}`}</span>${group==='ships'&&item.role_name?html`<span class="ship-tier${item.signature?' signature':item.endgame?' endgame':''}">${esc(item.role_name)}${item.signature?t(' · tylko twoja rasa'):''}</span>`:''}<h2>${esc(item.name)}</h2><p class="project-description">${esc(group==='ships'?catalogDescription(item):item.description)}</p>${item.effect_next ? html`<p class="effect">${esc(item.effect_next)}</p>` : ''}${group==='ships'?shipStatsHtml(item):''}${item.requirements?.length?html`<div class="ship-requirements"><h3>Wymagania produkcji</h3>${requirementsHtml(item.requirements)}</div>`:''}${projectReason(item, model.state) ? html`<p class="project-reason">${esc(projectReason(item, model.state))}</p>` : ''}</div></div>
    <div class="construction-card-footer">${costHtml(item.cost)}<div class="construction-footer-controls"><span class="duration">${duration(item.seconds)}</span><div class="project-action">${countable ? html`<input type="number" min="1" max="20" value="1" data-batch="${esc(item.key)}" aria-label="Liczba: ${esc(item.name)}">` : ''}${projectActionHtml(state,item,type,model.busy,{normalLabel:countable ? t('Produkuj') : group === 'research' ? t('Rozpocznij badanie') : Number(item.level) ? t('Ulepsz') : t('Zbuduj')})}</div></div></div>
  </article>`).join('');
  return html`${!state.player.race_id?raceHtml():''}${fleetNavigationHtml(group)}${compactQueueHtml('ship')}${catalogCarouselHtml(group,group==='ships'?uiText('ships'):uiText('defenses'),cards)}`;
}

function fleetDeadline(fleet) {
  const timestamp = Number(fleet.status === 'holding' ? fleet.hold_until : fleet.arrives_at);
  return Number.isFinite(timestamp) && timestamp > 0 ? timestamp : null;
}

function fleetCardHtml(fleet) {
  const returning = fleet.status === 'returning';
  const origin = fleet.origin_name || fleet.origin_id || '';
  const target = fleet.target_name || fleet.target_id || '';
  const status = {outbound:t('W drodze do celu'),returning:t('Powrót do kolonii'),holding:t('Dyżur obronny'),exploring:t('Poszukiwania')}[fleet.status] || t('Status nieznany');
  const deadline = fleetDeadline(fleet);
  const countdownLabel = fleet.status === 'exploring' ? t('Do końca poszukiwań') : fleet.status === 'holding' ? t('Do końca dyżuru') : returning ? t('Do powrotu') : t('Do celu');
  const shipNames = new Map((model.state.catalog?.ships || []).map((item) => [item.key, item.name]));
  const ships = Object.entries(fleet.ships || {}).filter(([, count]) => Number(count) > 0);
  const cargo = Object.entries(resourceNames).filter(([key]) => Number(fleet.cargo?.[key]) > 0).map(([key, name]) => html`<span>${esc(name)} <strong>${fmt(fleet.cargo[key])}</strong></span>`);
  if (Number(fleet.swarm_crystals) > 0) cargo.push(html`<span>Kryształy Roju <strong>${fmt(fleet.swarm_crystals)}</strong></span>`);
  const route = fleet.route;
  let routeHtml = '';
  if (route) {
    const fromGalaxy = route.origin_galaxy_name || route.origin_galaxy_id || '';
    const toGalaxy = route.target_galaxy_name || route.target_galaxy_id || '';
    const galaxyRoute = fromGalaxy && toGalaxy ? html`<span>${esc(returning ? toGalaxy : fromGalaxy)}${fromGalaxy !== toGalaxy ? html` → ${esc(returning ? fromGalaxy : toGalaxy)}` : ''}</span>` : '';
    const distance = route.intergalactic && Number.isFinite(Number(route.distance_mly)) ? html`<span>${esc(Number(route.distance_mly).toLocaleString(getLocale(), {maximumFractionDigits:3}))} mln lat świetlnych</span>` : '';
    routeHtml = html`<div class="fleet-route-meta"><span>${route.travel_mode === 'tunnel' || fleet.tunnel ? t('Tunel czasoprzestrzenny') : t('Zwykły lot · paliwo')}</span>${galaxyRoute}${distance}</div>`;
    if (!fleet.tunnel) routeHtml += fleetNetworkHtml(route,returning);
  }
  return html`<article class="active-fleet-card"><div class="active-fleet-heading"><div><h3>${esc(missionNames[fleet.mission] || fleet.mission)}</h3><p class="active-fleet-route"><span>${esc(returning ? target : origin)}</span><span aria-hidden="true" style="color:var(${fleetMarkerToken(fleet)})">→</span><span>${esc(returning ? origin : target)}</span></p></div><span class="pill">${esc(status)}</span></div><div class="active-fleet-timer"><span>${countdownLabel}</span>${deadline ? html`<strong class="countdown" data-countdown="${deadline}">${duration(deadline - serverNow())}</strong><time datetime="${new Date(deadline * 1000).toISOString()}">${esc(dateText(deadline))}</time>` : html(["<span class=\"muted\">Brak czasu zakończenia</span>"])}</div>${routeHtml}<div class="active-fleet-details"><div><h4>Skład floty</h4><div class="fleet-detail-values">${ships.map(([key, count]) => html`<span>${esc(shipNames.get(key) || key)} <strong>× ${fmt(count)}</strong></span>`).join('') || html(["<span class=\"muted\">Brak danych o składzie</span>"])}</div></div>${fleet.cargo || Number(fleet.swarm_crystals) > 0 ? html`<div><h4>Ładunek</h4><div class="fleet-detail-values">${cargo.join('') || html(["<span class=\"muted\">Brak ładunku</span>"])}</div></div>` : ''}</div>${fleet.mission === 'expedition' && fleet.can_recall ? html`<button type="button" class="button subtle" data-expedition-recall="${esc(fleet.id)}">Zawróć ekspedycję</button><p class="muted">Zawrócenie kończy wyprawę bez znalezisk. Zużyte paliwo nie jest zwracane.</p>` : ''}</article>`;
}

function fleetsHtml() {
  const fleets = [...(model.state.fleets || [])].sort((a, b) => (fleetDeadline(a) ?? Infinity) - (fleetDeadline(b) ?? Infinity));
  return html`<section class="panel active-fleets-panel"><div class="panel-heading"><h2>Aktywne floty</h2><div class="active-fleet-actions"><button type="button" class="button small" data-expedition-start>Ekspedycja</button><span class="muted">${fleets.filter(f=>f.mission!=='expedition').length} / 8 · ${t('Ekspedycje')}: ${Number(model.state.expeditions?.active || 0)} / ${Number(model.state.expeditions?.max_active || 0)}</span>${model.tab === 'fleets' ? html(["<button type=\"button\" class=\"button small subtle\" data-new-mission>Nowa misja →</button>"]) : html(["<button type=\"button\" class=\"button small subtle\" data-tab=\"fleets\">Podgląd flot →</button>"])}</div></div>${fleets.map(fleetCardHtml).join('') || html(["<p class=\"empty-state\">Flota czeka w kolonii. Wybierz układ lub znaną planetę i przygotuj pierwszą wyprawę.</p>"])}</section>`;
}

function fleetsPageHtml() {
  return html`${fleetNavigationHtml('fleets')}${fleetsHtml()}`;
}

function fleetTargetName() {
  if (model.fleetMission === 'expedition') return model.state.expeditions?.zone?.name || t('Nieznany sektor');
  const systems = model.state?.galaxy || [];
  const target = systems.flatMap(system => system.planets || []).find(planet => planet.id === model.fleetTarget);
  const system = systems.find(system => system.id === model.fleetSystemId || system.scout_target_id === model.fleetTarget || system.system_scout_target_id === model.fleetTarget);
  return model.fleetSystemId ? system?.name || model.fleetSystemId : target?.name || system?.name || model.fleetTarget;
}

function fleetSendCaption() {
  return t({expedition:'Wyślij ekspedycję',scout:'Wyślij zwiad', colonize:'Wyślij kolonizator', attack:'Wyślij atak', transport:'Wyślij transport'}[model.fleetMission] || 'Wyślij flotę');
}

function expeditionOptionsHtml() {
  const info = model.state.expeditions || {}, hours = model.fleetDraft?.expedition_hours || 1;
  return html`<label for="expedition-hours">Czas poszukiwań</label><select id="expedition-hours" name="expedition_hours">${[1,3,6].map(n=>html`<option value="${n}"${n===hours?' selected':''}>${n} h</option>`).join('')}</select><p class="muted">${t('Baza: poz. {0} · znaleziska +{1}% · ekspedycje {2}/{3}',Number(info.level||0),Number(info.reward_bonus_percent||0),Number(info.active||0),Number(info.max_active||0))}</p><p class="muted">Zwiadowca prowadzi poszukiwania. Transportowce zabierają znaleziska, a okręty bojowe chronią przed patrolem Roju.</p><p class="muted">Surowce 50% · statki 10% · pusto 20% · patrol 10% · opóźnienie 10%.</p><p class="muted">Zwycięstwo nad patrolem: 25% szansy na 1 Kryształ Roju. Znaleziska otrzymasz po powrocie.</p>`;
}

function fleetFormHtml() {
  if (!model.fleetTarget) return '';
  const state = model.state;
  const planets = (state.galaxy || []).flatMap(system => system.planets || []);
  const target = planets.find(planet => planet.id === model.fleetTarget);
  const availableShips = (state.catalog?.ships || []).filter(item => Number(state.ships?.[item.key]) > 0);
  const activeTunnel=state.megastructures?.is_origin&&state.megastructures?.window?.target_id===model.fleetTarget&&state.megastructures.window.closes_at>serverNow();
  const travelSelector=model.fleetMission === 'expedition' ? expeditionOptionsHtml() : html`<label for="fleet-travel-mode">Sposób podróży</label><select id="fleet-travel-mode" name="travel_mode"><option value="normal"${model.fleetTravelMode!=='tunnel'?' selected':''}>Zwykły lot · paliwo</option>${activeTunnel?html`<option value="tunnel"${model.fleetTravelMode==='tunnel'?' selected':''}>Tunel · energia Sfery Dysona</option>`:''}</select>`;
  const destinationArt = target ? artImage(planetArtKey(target), {className:'fleet-destination-art', sizes:'56px'}) : icon('galaxy',32);
  return html`<section class="panel fleet-composer" id="fleet-panel"><form id="fleet-form"><div class="fleet-edit-scroll"><div class="fleet-destination-card">${destinationArt}<div><span class="muted">${esc(state.planet_name)} →</span><strong>${esc(fleetTargetName())}</strong>${target ? html`<span class="muted">${target.owner_id === state.player.id ? t('Twoja kolonia') : target.owner_type === 'empty' ? t('Wolna planeta') : esc(target.owner_name || t('Obca kolonia'))}</span>` : ''}</div>${model.fleetMission === 'expedition' ? '' : html`<button type="button" class="button small subtle" data-change-destination>Zmień cel</button>`}</div><div class="fleet-intent"><div><label for="fleet-mission">Rodzaj misji</label><select id="fleet-mission" name="mission">${Object.entries(missionNames).filter(([key]) => model.fleetSystemId ? key === 'scout' : ['scout','transport','colonize','attack','expedition'].includes(key)).map(([key, label]) => html`<option value="${key}"${key === model.fleetMission ? ' selected' : ''}>${label}</option>`).join('')}</select></div><div>${travelSelector}</div></div><h3>Skład floty</h3><div class="fleet-fields fleet-ship-fields">${availableShips.map(ship => html`<div class="fleet-unit">${artImage(catalogArtKey(ship, 'ships'), {className:'fleet-unit-art', sizes:'72px'})}<div><label for="fleet-${esc(ship.key)}">${esc(ship.name)}</label><span class="muted">${fmt(state.ships[ship.key])} w kolonii</span></div><input id="fleet-${esc(ship.key)}" name="ship-${esc(ship.key)}" type="number" min="0" max="${Number(state.ships[ship.key])}" value="${Number(model.fleetDraft?.ships?.[ship.key] ?? (['scout','expedition'].includes(model.fleetMission) && ship.key === 'scout' || model.fleetMission === 'colonize' && ship.key === 'colonizer' ? 1 : 0))}" data-fleet-input aria-label="${esc(ship.name)} · Liczba statków"></div>`).join('') || html(["<p class=\"empty-state\">Brak statków w tej kolonii. Wyprodukuj je w stoczni.</p>"])}</div><div class="fleet-cargo"${['transport','colonize'].includes(model.fleetMission) ? '' : ' hidden'}><h3>Ładunek</h3><div class="fleet-fields">${Object.entries(resourceNames).map(([key,name]) => html`<div><label for="cargo-${key}">${name}</label><input id="cargo-${key}" name="cargo-${key}" type="number" min="0" max="1000000000" value="${Number(model.fleetDraft?.cargo?.[key] || 0)}" data-fleet-input></div>`).join('')}</div></div><div id="fleet-route-details"></div></div><div class="fleet-dock"><p class="fleet-dock-target"><span>${esc(state.planet_name)}</span><span aria-hidden="true">→</span><strong>${esc(fleetTargetName())}</strong></p><div id="fleet-preview" aria-live="polite" aria-atomic="true"><p class="loading">Obliczanie trasy…</p></div><button type="button" class="button primary fleet-send" data-launch-fleet disabled>${fleetSendCaption()}</button></div></form></section>`;
}


const visibilityNames = {unknown:t('Poza zasięgiem'), observed:t('Bieżąca obserwacja'), scouted:t('Stan z ostatniego zwiadu'), remembered:t('Stan ostatniej obserwacji'), colony:t('Własny układ')};
function galaxyGroups() {
  const state = model.state;
  const groups = new Map();
  for (const galaxy of state.galaxies?.items || (Array.isArray(state.galaxies) ? state.galaxies : [])) groups.set(galaxy.id || galaxy.galaxy_id, galaxy);
  for (const system of state.galaxy || []) if (!groups.has(system.galaxy_id)) groups.set(system.galaxy_id, {id:system.galaxy_id, name:system.galaxy_id});
  return groups;
}

function selectedSystem(systems) {
  const own = model.state.own_planets?.find((planet) => planet.id === model.state.planet_id);
  const selected = systems.find((system) => system.id === model.selectedSystems[model.galaxyId])
    || systems.find((system) => system.id === own?.system_id)
    || systems.find((system) => system.visibility !== 'unknown') || systems[0];
  if (selected) model.selectedSystems[model.galaxyId] = selected.id;
  return selected;
}

function ringName(index) {
  return [t('Pierścień środkowy') + ' (2/5)', t('Pierścień środkowy') + ' (3/5)',
    t('Pierścień środkowy') + ' (4/5)', t('Pierścień zewnętrzny'), t('Pierścień wewnętrzny')][index] || '';
}

function displayedMapRoute() {
  const systems = (model.state?.galaxy || []).filter(system => system.galaxy_id === model.galaxyId);
  const selected = model.selectedSystems[model.galaxyId];
  const quote = model.fleetPreview?.result;
  if (quote?.tunnel || quote?.route?.intergalactic) return null;
  if (quote && (quote.route?.system_ids || []).at(-1) === selected) {
    return quote.tunnel ? null : quote.route;
  }
  const origin = model.state?.own_planets?.find(planet => planet.id === model.state.planet_id)?.system_id;
  return shortestSystemRoute(systems,origin,selected);
}

function mapRouteText(route) {
  if (!route?.segments?.length) return '';
  return t('Trasa od aktywnej kolonii: {0} połączeń, {1} przejść między pierścieniami.',route.segments.length,route.segments.filter(edge => edge.kind === 'bridge').length);
}

function refreshMapRoute() {
  const route = displayedMapRoute();
  galaxyMapController?.setRoute(route);
  if ($('#map-route-status')) $('#map-route-status').textContent = mapRouteText(route);
}

function fleetNetworkHtml(route, returning = false) {
  if (route?.intergalactic || route?.travel_mode === 'tunnel' || !route?.system_ids?.length) return '';
  const systems = new Map((model.state.galaxy || []).map(system => [system.id,system]));
  const ids = returning ? [...route.system_ids].reverse() : route.system_ids;
  return html`<div class="fleet-network-route"><strong>Układy na trasie</strong><ol aria-label="Układy na trasie">${ids.map(id => html`<li>${esc(systems.get(id)?.name || id)} <small>${esc(id)}</small></li>`).join('')}</ol></div>`;
}

function systemDetailsHtml(system) {
  if (!system) return html(["<p class=\"empty-state\">Brak układów do wyświetlenia.</p>"]);
  const state = model.state;
  const snapshot = ['scouted','remembered'].includes(system.visibility);
  const at = system.visibility === 'remembered' ? system.observed_at : system.scouted_at;
  const bridges = (system.connections || []).filter(edge => edge.kind === 'bridge');
  const scoutAction = system.system_scout_target_id
    ? html`<div class="system-scout"><p class="muted">Zwiad odświeży planety, ich właścicieli i czas obserwacji całego układu.</p><button type="button" class="button primary" data-target="${esc(system.system_scout_target_id)}" data-system-scout="${esc(system.id)}" data-mission="scout">Zbadaj cały układ →</button></div>`
    : system.scout_target_id ? html`<div class="system-scout"><p class="muted">Współrzędne pozwalają wysłać zwiad.</p><button type="button" class="button primary" data-target="${esc(system.scout_target_id)}" data-mission="scout">Wyślij zwiad →</button></div>` : '';
  return html`<p class="eyebrow">WYBRANY UKŁAD · ${esc(system.id.toUpperCase())}</p><h2>${esc(system.name)}</h2>
    <p class="system-meta">${esc(visibilityNames[system.visibility] || system.visibility)}${snapshot && at ? ` · ${esc(dateText(at))}` : ''}</p>
    ${Number.isInteger(system.ring_index) ? html`<p class="system-ring">${ringName(system.ring_index)} · ${system.ring_order + 1} / ${system.ring_size}</p>` : ''}
    ${bridges.length ? html`<div class="system-bridges"><span>Przejścia do innych pierścieni</span>${bridges.map(edge => html`<button type="button" class="button small subtle" data-connected-system="${esc(edge.system_id)}">${esc((state.galaxy || []).find(entry => entry.id === edge.system_id)?.name || edge.system_id)} →</button>`).join('')}</div>` : ''}
    ${snapshot ? html(["<p class=\"system-intel-note\">Właściciele i zawartość układu mogły się zmienić. Nowy zwiad odświeży informacje.</p>"]) : ''}
    <div class="system-planets">${(system.planets || []).map((planet) => html`<div class="planet-row"><button type="button" class="planet-identity planet-inspect" data-inspect-planet="${esc(planet.id)}" aria-haspopup="dialog" aria-label="${esc(text`Informacje o planecie: ${planet.name}`)}" title="Informacje o planecie i ostatni zwiad">${artImage(planetArtKey(planet), {className:'planet-thumb', sizes:'48px'})}<span class="planet-identity-copy"><strong><span class="planet-dot ${esc(planet.owner_type)}"></span>${esc(planet.name)}${protectedPlanet(planet,serverNow())?html` <span class="protected-badge">${uiText('protected')}</span>`:''}</strong><span class="muted">${planet.owner_id === state.player.id ? t('Twoja kolonia') : planet.owner_type === 'empty' ? t('Wolna planeta') : esc(planet.owner_name || t('Obca kolonia'))}${planet.environment?.type_name ? ` · ${esc(planet.environment.type_name)}` : ''}</span></span><span class="planet-inspect-arrow" aria-hidden="true">↗</span></button>${planet.owner_id === state.player.id && !model.missionSelecting ? html`<button type="button" class="button small subtle" data-planet="${esc(planet.id)}">Otwórz</button>` : html`<button type="button" class="button small subtle" data-target="${esc(planet.id)}" data-mission="${planet.owner_type === 'empty' ? 'colonize' : 'scout'}">Wyprawa</button>`}</div>`).join('')}</div>
    ${system.visibility === 'unknown' ? html(["<div class=\"unknown-system-message\"><span aria-hidden=\"true\">✧</span><h3>Nieznany sygnał</h3><p>Wyślij zwiadowcę, aby poznać planety i ich właścicieli.</p></div>"]) : ''}
    ${scoutAction}`;
}

function renderPlanetDetails() {
  if (!model.planetDetail) return;
  const info = planetInspection(model.state, model.planetDetail);
  if (!info) { closePlanetDetails(); return; }
  const content = $('#planet-detail-content');
  const markup = planetDetailsHtml(model.state, model.planetDetail, {art:artImage(planetArtKey(info.planet), {className:'planet-detail-thumb',sizes:'80px'})});
  if (markup === model.planetDetailMarkup) return;
  const dialog = $('#planet-dialog');
  const scroll = dialog.scrollTop;
  const focused = content.contains(document.activeElement) ? document.activeElement : null;
  const action = focused?.dataset?.target || focused?.dataset?.planet;
  const mission = focused?.dataset?.mission;
  content.innerHTML = markup;
  model.planetDetailMarkup = markup;
  if (action) ([...content.querySelectorAll('button')].find(button => (button.dataset.target || button.dataset.planet) === action && button.dataset.mission === mission) || dialog.querySelector('[data-close-planet-info]')).focus({preventScroll:true});
  dialog.scrollTop = scroll;
}

function openPlanetDetails(id, trigger) {
  if (!planetInspection(model.state, id)) return;
  model.planetDetail = id;
  model.planetDetailMarkup = '';
  model.planetDetailTrigger = trigger;
  renderPlanetDetails();
  const dialog = $('#planet-dialog');
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;
  dialog.querySelector('[data-close-planet-info]').focus({preventScroll:true});
}

function closePlanetDetails(restoreFocus = true) {
  const id = model.planetDetail;
  const trigger = model.planetDetailTrigger;
  model.planetDetail = '';
  model.planetDetailMarkup = '';
  model.planetDetailTrigger = null;
  if ($('#planet-dialog').open) $('#planet-dialog').close();
  if (restoreFocus && id) (trigger?.isConnected ? trigger : document.querySelector(`[data-inspect-planet="${CSS.escape(id)}"]`))?.focus({preventScroll:true});
}

function selectSystem(id) {
  const system=(model.state.galaxy || []).find(item=>item.id===id&&item.galaxy_id===model.galaxyId);
  if(!system)return;
  model.selectedSystems[model.galaxyId]=id;
  model.galaxyMode='system';
  renderMain();
}

function changeGalaxy(id) {
  if (!galaxyGroups().has(id)) return;
  model.galaxyId = id;
  model.galaxyMode = 'map';
  const focus = selectedSystem(sortSystems((model.state.galaxy || []).filter(system => system.galaxy_id === id)));
  if (focus) {
    model.galaxyViews[id] ||= {scale:1,x:0,y:0};
    model.galaxyViews[id].focusSystemId = focus.id;
  }
  // Only replace the map. Never erase ship amounts or cargo in an open fleet form.
  galaxyMapController?.destroy();
  $('#galaxy-explorer').outerHTML = galaxyExplorerHtml();
  mountMap();
}

function prepareGalaxyEntry() {
  const state = model.state;
  const own = state?.own_planets?.find(planet => planet.id === state.planet_id);
  const systems = state?.galaxy || [];
  const system = systems.find(item => item.id === own?.system_id)
    || systems.find(item => (item.planets || []).some(planet => planet.id === state.planet_id));
  if (!system) return;
  model.galaxyId = system.galaxy_id;
  model.selectedSystems[system.galaxy_id] = system.id;
  const view = model.galaxyViews[system.galaxy_id] ||= {scale:1, x:0, y:0};
  // Focus after layout; polling and galaxy browsing retain manual zoom/pan.
  view.focusSystemId = system.id;
}

function galaxyExplorerHtml() {
  const state = model.state;
  const groups = galaxyGroups();
  if (!groups.has(model.galaxyId)) model.galaxyId = groups.keys().next().value || '';
  const galaxy = groups.get(model.galaxyId) || {};
  const systems = sortSystems((state.galaxy || []).filter((system) => system.galaxy_id === model.galaxyId));
  const selected = selectedSystem(systems);
  if(model.galaxyMode==='system')return html`<section id="galaxy-explorer" class="galaxy-explorer system-view"><div class="system-toolbar"><button type="button" class="button small subtle" data-show-map>← ${uiText('map')}</button></div><aside id="system-detail" class="system-detail">${systemDetailsHtml(selected)}</aside></section>`;
  const known = systems.filter((system) => system.visibility !== 'unknown').length;
  const networkLegend = hasRingTopology(systems) ? html`<div class="galaxy-legend galaxy-network-legend"><span><i class="connection-key" aria-hidden="true"></i>Przejście między pierścieniami</span><span><i class="connection-key route" aria-hidden="true"></i>Wybrana trasa</span></div>` : '';
  return html`<section id="galaxy-explorer" class="galaxy-explorer"><div class="galaxy-navigation"><div class="galaxy-picker"><button type="button" class="icon-button" data-galaxy-step="-1" aria-label="Poprzednia galaktyka">‹</button><label class="sr-only" for="galaxy-select">Obserwowana galaktyka</label><select id="galaxy-select">${[...groups].map(([id, entry]) => html`<option value="${esc(id)}"${id === model.galaxyId ? ' selected' : ''}>${esc(entry.name || id)}</option>`).join('')}</select><button type="button" class="icon-button" data-galaxy-step="1" aria-label="Następna galaktyka">›</button><span class="galaxy-count">${systems.length} układów · ${known} poznanych</span></div><div class="map-controls" id="map-controls"><button type="button" class="icon-button" data-map-zoom="out" aria-label="Oddal mapę">−</button><span data-map-scale aria-label="Powiększenie mapy">100%</span><button type="button" class="icon-button" data-map-zoom="in" aria-label="Przybliż mapę">+</button><button type="button" class="button small subtle" data-map-zoom="reset">Cała mapa</button></div></div>
    <div class="galaxy-layout"><div class="galaxy-map-shell"><div id="galaxy-map" class="galaxy-map" tabindex="0" role="region" aria-label="Mapa galaktyki ${esc(galaxy.name || '')}. Kliknij układ. Plus i minus zmieniają powiększenie, Home przywraca całą mapę."><div class="galaxy-plane">${artImage(galaxy.art_key, {className:'galaxy-map-art', sizes:'(max-width:620px) 100vw, 75vw', eager:true})}<div class="galaxy-shade" aria-hidden="true"></div><div class="galaxy-orbit" aria-hidden="true"></div><div class="galaxy-core" aria-hidden="true"><span>GALAKTYKA</span><strong>${esc(galaxy.name || '')}</strong><small>${esc(model.galaxyId.toUpperCase())}</small></div>${systems.map((system) => {
      const status = systemStatus(system, state.player.id);
      const name = `${system.name} · ${visibilityNames[system.visibility] || system.visibility}`;
      return html`<button type="button" class="system-node ${status}${selected?.id === system.id ? ' selected' : ''}" data-system="${esc(system.id)}" aria-label="${esc(name)}" aria-pressed="${selected?.id === system.id}" aria-controls="system-detail" title="${esc(name)}"><span class="system-star" aria-hidden="true">${status === 'own' ? '◆' : status === 'swarm' ? '✦' : '●'}</span><span class="node-label" aria-hidden="true">${esc(system.id.replace(/^s/, '').padStart(2,'0'))}</span><span class="node-name" aria-hidden="true">${esc(system.name)}</span></button>`;
    }).join('')}</div></div><div class="galaxy-legend"><span class="own">◆ Własny</span><span class="known">● Poznany</span><span class="inhabited">● Obce kolonie</span><span class="swarm">✦ Rój</span><span class="unknown">○ Nieznany</span></div>${networkLegend}<div class="galaxy-legend fleet-legend"><span style="color:${fleetMapColor({mission:'expedition'})}">▶ ${missionNames.expedition}</span><span style="color:${fleetMapColor({mission:'scout'})}">▶ ${missionNames.scout}</span><span style="color:${fleetMapColor({mission:'transport'})}">▶ ${missionNames.transport}</span><span style="color:${fleetMapColor({mission:'colonize'})}">▶ ${missionNames.colonize}</span><span style="color:${fleetMapColor({mission:'attack'})}">▶ ${missionNames.attack}</span><span style="color:${fleetMapColor({status:'returning'})}">▶ ${t('Powrót')}</span></div><p id="map-route-status" class="map-route-status" aria-live="polite"></p></div>
    </div></section>`;
}

function mountMap() {
  if (!$('#galaxy-map')) return;
  const view = model.galaxyViews[model.galaxyId] ||= {scale:1, x:0, y:0};
  const systems = sortSystems((model.state.galaxy || []).filter(system => system.galaxy_id === model.galaxyId));
  galaxyMapController = mountGalaxyMap($('#galaxy-map'), view, $('#map-controls'),{systems,route:displayedMapRoute(),fleets:model.state.fleets || [],now:serverNow,galaxyId:model.galaxyId});
  refreshMapRoute();
}

function galaxyHtml() {
  if(model.fleetTarget&&!model.missionSelecting)return html`${fleetNavigationHtml('mission')}${fleetFormHtml()}`;
  return html`${model.missionSelecting ? fleetNavigationHtml('picker') : ''}${galaxyExplorerHtml()}`;
}

async function beginNewMission() {
  closePlanetDetails(false);
  resetMissionDraft(model);
  fleetPreviewRequest++;
  await switchTab('galaxy');
}

function changeMissionDestination() {
  saveFleetDraft(model,collectFleet(false));
  fleetQuoteController.cancel();
  const target=(model.state.galaxy || []).find(system=>system.id===model.fleetSystemId||system.scout_target_id===model.fleetTarget||system.system_scout_target_id===model.fleetTarget||(system.planets||[]).some(planet=>planet.id===model.fleetTarget));
  model.missionSelecting=true;
  model.fleetPreview=null;
  fleetPreviewRequest++;
  if(target){model.galaxyId=target.galaxy_id;model.selectedSystems[target.galaxy_id]=target.id;model.galaxyViews[target.galaxy_id] ||= {scale:1,x:0,y:0};model.galaxyViews[target.galaxy_id].focusSystemId=target.id;model.galaxyMode='map';}
  else {prepareGalaxyEntry();model.galaxyMode='map';}
  renderMain();
}

function skillsHtml() {
  const tree = model.state.skill_tree || {};
  const nodes = (tree.nodes || []).filter((node) => node.unlocked || node.available);
  return html`${raceHtml()}<div class="notice teal">${fmt(tree.balance)} Kryształów Roju · Rozwijaj umiejętności sąsiadujące z odblokowanymi węzłami. Każdy zakup podnosi koszt pozostałych umiejętności.</div><p class="section-intro">Kryształy Roju zdobywasz w wyprawach bojowych przeciw Rojowi Khar. Poniżej znajdziesz odblokowane umiejętności i dostępne kierunki rozwoju.</p><div class="skills-grid">${nodes.map((node) => html`<article class="skill-card${node.unlocked ? ' unlocked' : ''}">${hasArt(node.art_key) ? artImage(node.art_key, {className:'skill-art', sizes:'72px'}) : ''}<p class="eyebrow">${node.unlocked ? t('ODBLOKOWANO') : t('DOSTĘPNY KIERUNEK')}</p><h2>${esc(node.name)}</h2><p>${esc(node.description)}</p>${node.unlocked ? html(["<span class=\"pill\">Aktywna umiejętność ✓</span>"]) : html`<button type="button" class="button${node.affordable ? ' primary' : ' subtle'}" data-skill="${esc(node.id)}"${!node.affordable || model.busy ? ' disabled' : ''}>Rozwiń · ${fmt(node.cost)} kryształów</button>${!node.affordable ? html(["<p class=\"project-reason\">Brakuje Kryształów Roju.</p>"]) : ''}`}</article>`).join('') || html(["<p class=\"empty-state\">Wybierz rasę, aby otworzyć drzewo umiejętności.</p>"])}</div>`;
}

function renderReportDetails() {
  const detail = model.reportDetail;
  if (!detail) return;
  const dialog = $('#report-dialog');
  const scroll = dialog.scrollTop;
  $('#report-detail-content').innerHTML = reportDetailsHtml(detail.report, {
    art:artImage(detail.report.art_key, {className:'report-detail-thumb',sizes:'(max-width:620px) 68px, 100px'}),
    replay:detail.replay, replayStatus:detail.replayStatus, replayError:detail.replayError,
  });
  dialog.scrollTop = scroll;
}

async function loadReportReplay(detail = model.reportDetail) {
  if (!detail || !detail.report.battle_replay_available || !detail.report.id) return;
  const request = ++reportDetailRequest;
  const epoch = model.epoch;
  detail.replayStatus = 'loading';
  detail.replayError = '';
  renderReportDetails();
  const current = () => request === reportDetailRequest && epoch === model.epoch && model.reportDetail === detail;
  try {
    const response = await api(`/battle-replay?report_id=${encodeURIComponent(detail.report.id)}`);
    if (!current()) return;
    if (!response.replay) throw new ApiError(t('Brak szczegółów bitwy.'));
    detail.replay = response.replay;
    detail.replayStatus = 'ready';
  } catch (error) {
    if (!current()) return;
    detail.replayStatus = 'error';
    detail.replayError = error.message;
  }
  if (current()) renderReportDetails();
}

function openReportDetails(identity, trigger) {
  const report = model.state?.reports?.find(entry => reportIdentity(entry) === identity);
  if (!report) return;
  model.reportDetail = {identity, report:JSON.parse(JSON.stringify(report)), trigger, replay:null, replayStatus:'', replayError:''};
  renderReportDetails();
  const dialog = $('#report-dialog');
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;
  dialog.querySelector('[data-close-report]').focus({preventScroll:true});
  if (markReportsRead(identity)) renderChrome();
  void loadReportReplay(model.reportDetail);
}

function closeReportDetails(restoreFocus = true) {
  const detail = model.reportDetail;
  model.reportDetail = null;
  reportDetailRequest++;
  const dialog = $('#report-dialog');
  if (dialog.open) dialog.close();
  $('#report-detail-content').innerHTML = '';
  if (restoreFocus && detail) {
    const trigger = detail.trigger?.isConnected ? detail.trigger : [...document.querySelectorAll('[data-report]')].find(button => button.dataset.report === detail.identity);
    (trigger || $('#main')).focus({preventScroll:true});
  }
}

function reportsHtml() {
  return html`<p class="section-intro">Dziennik twojego imperium: ukończone projekty, odkrycia zwiadowców i wyniki wypraw.</p>${(model.state.reports || []).map((report) => html`<article class="report-card">${reportTypeIcon(report,48)}<div class="report-copy"><h2>${esc(report.title)}</h2><time datetime="${new Date(Number(report.at) * 1000).toISOString()}">${esc(dateText(report.at))}</time><p>${esc(report.text)}</p><span class="report-open-hint" aria-hidden="true">${esc(t('Otwórz raport'))} ↗</span></div><button type="button" class="report-open" data-report="${esc(reportIdentity(report))}" aria-haspopup="dialog" aria-label="${esc(t('Otwórz raport'))}: ${esc(report.title)}"></button></article>`).join('') || html(["<section class=\"panel\"><p class=\"empty-state\">Twoje imperium jeszcze nie ma raportów.</p></section>"])}`;
}

function messagesHtml(messages) {
  return (messages || []).map((message) => html`<article class="chat-message${message.sender_id === model.state.player.id ? ' self' : ''}"><div class="chat-meta"><strong>${esc(message.sender_name)}</strong><time>${esc(dateText(message.at))}</time></div><p>${esc(message.text)}</p></article>`).join('');
}

function chatHtml() {
  if (!model.chat) return html(["<section class=\"panel\"><p class=\"loading\">Łączenie z kanałem ogólnym…</p></section>"]);
  if (model.chat.error) return html`<section class="panel"><p class="form-error">${esc(model.chat.error)}</p><button type="button" class="button subtle" data-load-chat>Spróbuj ponownie</button></section>`;
  const canSend = model.chat.permissions?.can_send !== false;
  return html`<p class="section-intro">Porozmawiaj z innymi dowódcami. Wiadomości na kanale ogólnym są widoczne dla zalogowanych graczy.</p><section class="panel"><div class="panel-heading"><h2>Kanał ogólny</h2><button type="button" class="button small subtle" data-load-chat>Odśwież</button></div><div id="chat-feed" class="chat-feed">${messagesHtml(model.chat.messages) || html(["<p class=\"empty-state\">Cisza w eterze. Wyślij pierwszą wiadomość.</p>"])}</div><form id="chat-form" class="chat-form"><label class="skip-link" for="chat-message">Wiadomość na kanale ogólnym</label><textarea id="chat-message" name="text" rows="2" maxlength="500" placeholder="Napisz do innych dowódców…" required${canSend ? '' : ' disabled'}></textarea><button type="submit" class="button primary"${!canSend || model.busy ? ' disabled' : ''}>Wyślij →</button></form>${!canSend ? html(["<p class=\"project-reason\">Wysyłanie wiadomości jest obecnie zablokowane przez serwer.</p>"]) : html(["<p class=\"fine-print\">Do 500 znaków. Szanuj innych graczy i nie publikuj danych osobowych.</p>"])}</section>`;
}

function allianceHtml() {
  const view = model.alliance;
  if (!view) return html(["<section class=\"panel\"><p class=\"loading\">Pobieranie danych sojuszy…</p></section>"]);
  if (view.error) return html`<section class="panel"><p class="form-error">${esc(view.error)}</p><button type="button" class="button subtle" data-load-alliance>Spróbuj ponownie</button></section>`;
  const alliance = view.alliance;
  const pending = new Set((view.applications || []).map((item) => item.alliance_id));
  const cooldown = Number(view.cooldown_until) > serverNow();
  const manager = alliance && ['leader','officer'].includes(alliance.role);
  return html`<p class="section-intro">Znajdź sojuszników, utwórz własny sojusz i rozmawiaj na prywatnym kanale. Sojusz może liczyć do 20 imperiów.</p>${cooldown ? html(["<div class=\"notice\">Po opuszczeniu sojuszu obowiązuje 24-godzinna przerwa przed kolejnym dołączeniem.</div>"]) : ''}${(view.invitations || []).map((invite) => html`<div class="notice teal">Zaproszenie: <strong>[${esc(invite.tag)}] ${esc(invite.name)}</strong><div class="form-actions"><button type="button" class="button small primary" data-alliance-action="accept_invite" data-alliance-id="${esc(invite.alliance_id)}">Przyjmij</button><button type="button" class="button small subtle" data-alliance-action="decline_invite" data-alliance-id="${esc(invite.alliance_id)}">Odrzuć</button></div></div>`).join('')}<div class="alliance-grid">${alliance ? html`<section class="panel"><div class="panel-heading"><h2>[${esc(alliance.tag)}] ${esc(alliance.name)}</h2><span class="pill">${esc(roleNames[alliance.role])}</span></div><p class="section-intro">${esc(alliance.description)}</p><h3>Członkowie · ${fmt(alliance.members_count)} / 20</h3>${(alliance.members || []).map((member) => html`<div class="member-row"><span>${esc(member.name)}</span><span class="muted">${esc(roleNames[member.role])}</span></div>`).join('')}${manager ? html`<form id="alliance-invite-form"><label for="invite-name">Zaproś imperium</label><input id="invite-name" name="player_name" minlength="3" maxlength="20" required placeholder="Nazwa imperium"><div class="form-actions"><button type="submit" class="button small primary">Wyślij zaproszenie</button></div></form>${(alliance.applications || []).length ? html`<h3 style="margin-top:25px">Podania</h3>${alliance.applications.map((application) => html`<div class="member-row"><div>${esc(application.player_name)}<span class="muted">${esc(application.text)}</span></div><div class="member-actions"><button type="button" class="button small primary" data-alliance-action="approve_application" data-player-id="${esc(application.player_id)}">Przyjmij</button><button type="button" class="button small subtle" data-alliance-action="reject_application" data-player-id="${esc(application.player_id)}">Odrzuć</button></div></div>`).join('')}` : ''}` : ''}<div class="form-actions"><button type="button" class="button small subtle danger" data-alliance-leave>Opuść sojusz</button></div><p class="fine-print">Po odejściu obowiązuje 24-godzinny rozejm i przerwa przed dołączeniem do kolejnego sojuszu. Lider z innymi członkami musi najpierw przekazać przywództwo.</p></section><section class="panel"><div class="panel-heading"><h2>Prywatny kanał sojuszu</h2><button type="button" class="button small subtle" data-load-alliance>Odśwież</button></div><div class="chat-feed">${messagesHtml(alliance.chat) || html(["<p class=\"empty-state\">Zaplanujcie pierwszą wspólną wyprawę.</p>"])}</div><form id="alliance-chat-form" class="chat-form"><label class="skip-link" for="alliance-message">Wiadomość do sojuszu</label><textarea id="alliance-message" name="text" rows="2" maxlength="500" placeholder="Napisz do sojuszników…" required></textarea><button type="submit" class="button primary">Wyślij →</button></form></section>` : html`<section class="panel"><h2>Utwórz własny sojusz</h2><form id="alliance-create-form"><label for="alliance-name">Nazwa sojuszu</label><input id="alliance-name" name="name" minlength="3" maxlength="32" required placeholder="Nazwa sojuszu"><label for="alliance-tag">Tag · 3–5 liter lub cyfr</label><input id="alliance-tag" name="tag" minlength="3" maxlength="5" pattern="[A-Za-z0-9]{3,5}" required placeholder="TAG"><label for="alliance-description">Opis</label><textarea id="alliance-description" name="description" maxlength="500" placeholder="Co łączy wasze imperia?"></textarea><div class="form-actions"><button type="submit" class="button primary"${cooldown ? ' disabled' : ''}>Utwórz sojusz</button></div></form></section>`}<section class="panel"><div class="panel-heading"><h2>Katalog sojuszy</h2><button type="button" class="button small subtle" data-load-alliance>Odśwież</button></div>${(view.directory || []).map((item) => html`<article class="alliance-card"><h3>[${esc(item.tag)}] ${esc(item.name)}</h3><p>${esc(item.description)}</p><p>${fmt(item.members_count)} / ${fmt(item.max_members)} członków · ${esc(item.leader_name)}</p>${!alliance ? html`<button type="button" class="button small subtle" data-alliance-action="${pending.has(item.id) ? 'withdraw_application' : 'apply'}" data-alliance-id="${esc(item.id)}"${cooldown || item.members_count >= item.max_members && !pending.has(item.id) ? ' disabled' : ''}>${pending.has(item.id) ? t('Wycofaj podanie') : t('Wyślij podanie')}</button>` : ''}</article>`).join('') || html(["<p class=\"empty-state\">Nie ma jeszcze żadnych sojuszy. Pierwszy może należeć do ciebie.</p>"])}</section></div>`;
}

function settingsHtml() {
  return html`<section class="panel"><div class="settings-links">${['skills','chat','alliance','ranking'].map(key=>html`<button type="button" class="button" data-tab="${key}">${icon(key)} ${tabs[key][1]}</button>`).join('')}</div></section><section class="panel settings-panel"><p class="eyebrow">USTAWIENIA GRACZA</p><h2>Język i wygląd</h2>
    <label for="settings-language">Język / Language</label><select id="settings-language" data-language-select>${languageOptions()}</select>
    <p class="fine-print">Wybór jest zapamiętywany w tej przeglądarce. Zmiana języka odświeża stronę i nie zmienia postępów imperium.</p>
    <label class="settings-toggle"><input type="checkbox" id="settings-detailed" ${model.detailedBuildings?'checked':''}>Szczegółowe opisy budynków</label>
    <p class="fine-print">Rozszerzone dane są widoczne w oknie budynku. Kafelki pozostają krótkie.</p>
    <label class="settings-toggle"><input type="checkbox" id="settings-motion" ${document.documentElement.classList.contains('reduce-motion')?'checked':''}>Ogranicz animacje</label>
    <p class="fine-print">Wyłącza pulsowanie i płynne przejścia. Nie wpływa na mechanikę gry.</p>
    <div class="release-info"><span>Alien Colonies</span><strong>Web ${WEB_BUILD}</strong><span>Serwer ${esc(model.state.version)}</span></div>
  </section>${empireNameSettingsHtml()}${googleAccountSettingsHtml()}${emailAccountSettingsHtml()}${accountDeletionHtml()}`;
}

function empireNameSettingsHtml() {
  return html`<section class="panel"><h2>${t('Zmień nazwę imperium')}</h2><form id="empire-rename-form"><label for="empire-rename-name">${t('Nowa nazwa imperium')}</label><input id="empire-rename-name" name="empire-name" value="${esc(model.state.player.name)}" minlength="3" maxlength="20" autocomplete="off" required><p class="fine-print">${t('Nazwa musi mieć 3–20 znaków: litery, cyfry, spacje, _ lub -.')}</p><button type="submit" class="button"${model.busy ? ' disabled' : ''}>${t('Zapisz')}</button></form></section>`;
}

function googleAccountSettingsHtml() {
  const account = model.state?.account || {};
  if (account.google_linked) return html`<section class="panel google-account-panel"><h2>Konto Google</h2><p class="muted">Twoje imperium jest połączone z Google. Możesz logować się przyciskiem „Kontynuuj przez Google”.</p></section>`;
  if (account.email_linked && account.password_login_enabled === false) return '';
  if (!model.googleAuth.configured) return '';
  const needsPassword = account.password_login_enabled !== false;
  return html`<section class="panel google-account-panel"><h2>Konto Google</h2><p class="muted">Połącz to imperium z Google, aby logować się bez wpisywania hasła. Zachowasz kolonie i postępy.</p>${needsPassword ? html`<label for="google-link-password">Obecne hasło imperium</label><input id="google-link-password" type="password" autocomplete="current-password" required maxlength="128">` : ''}<button type="button" class="button google-button" data-google-link${model.busy ? ' disabled' : ''}><span class="google-symbol" aria-hidden="true">G</span>Połącz z Google</button><p id="settings-google-status" class="fine-print" role="status" aria-live="polite" hidden></p></section>`;
}

function emailAccountSettingsHtml() {
  const account = model.state?.account || {};
  if (!account.email_linked) return '';
  const needsPassword = account.password_login_enabled !== false;
  return html`<section class="panel email-account-panel"><h2>Konto e-mail</h2><p class="muted">To imperium korzysta z potwierdzonego adresu e-mail. Możesz logować się jednorazowym linkiem.</p>${model.emailAuth.configured ? html`<button type="button" class="button subtle" data-email-reauth${model.busy ? ' disabled' : ''}>Potwierdź konto przez e-mail</button>` : html`<p class="fine-print">Logowanie przez e-mail jest chwilowo niedostępne.</p>`}<p class="fine-print">Wylogowanie pozostałych urządzeń wymaga niedawnego potwierdzenia konta. Bieżąca sesja pozostanie aktywna.</p>${needsPassword ? html`<label for="email-other-password">Obecne hasło imperium</label><input id="email-other-password" type="password" autocomplete="current-password" minlength="8" maxlength="128" required>` : ''}<button type="button" class="button subtle" data-email-logout-others${model.busy ? ' disabled' : ''}>Wyloguj pozostałe urządzenia</button><p id="email-account-status" class="fine-print" role="status" aria-live="polite" hidden></p></section>`;
}

function accountDeletionHtml() {
  const account = model.state.account || {};
  const passwordless = account.password_login_enabled === false && (account.google_linked === true || account.email_linked === true);
  const emailOnly = passwordless && account.email_linked === true && account.google_linked !== true;
  const reauth = !passwordless ? '' : emailOnly ? html`<p class="fine-print">Usunięcie wymaga niedawnego logowania przez e-mail. Jeśli minęło ponad 5 minut, potwierdź konto ponownie.</p>${model.emailAuth.configured ? html`<button type="button" class="button subtle" data-email-reauth${model.busy ? ' disabled' : ''}>Potwierdź konto przez e-mail</button>` : ''}` : html`<p class="fine-print">Usunięcie wymaga niedawnego logowania przez Google. Jeśli minęło ponad 5 minut, potwierdź konto ponownie.</p><button type="button" class="button subtle" data-google-reauth${model.busy ? ' disabled' : ''}>Potwierdź konto przez Google</button>`;
  return html`<section class="panel account-delete-panel"><h2>Usuń konto</h2><p class="project-reason">Usunięcie jest trwałe. Utracisz imperium, kolonie, floty i postępy.</p>${reauth}<form id="account-delete-form">${passwordless ? '' : html`<label for="account-delete-password">Obecne hasło imperium</label><input id="account-delete-password" type="password" autocomplete="current-password" minlength="8" maxlength="128" required>`}<label for="account-delete-name">Wpisz nazwę imperium, aby potwierdzić</label><input id="account-delete-name" autocomplete="off" maxlength="20" required><p class="fine-print" data-no-translate>${esc(model.state.player.name)}</p><p id="account-delete-error" class="form-error" role="alert" hidden></p><button type="submit" class="button danger"${model.busy ? ' disabled' : ''}>Trwale usuń konto</button></form></section>`;
}
function languageOptions() {
  return Object.entries(LANGUAGES).map(([code,name])=>html`<option value="${code}"${code===getLanguage()?' selected':''}>${name}</option>`).join('');
}
async function changeLanguage(code) {
  if(code===getLanguage() || !LANGUAGES[code]) return;
  try { await setLanguage(code); const url=new URL(location.href); url.searchParams.set('lang',code); location.replace(url.href); }
  catch(error) { toast(error.message,true); }
}

function destroyMainView() {
  galaxyMapController?.destroy();
  galaxyMapController = null;
  researchTreeController?.destroy();researchTreeController=null;
  catalogCarouselController?.destroy();catalogCarouselController=null;
}

function renderMain() {
  if (!model.state) return;
  const renderers = {ranking:() => rankingHtml(model.ranking,{category:model.rankingCategory,busy:model.rankingBusy,error:model.rankingError,reward:model.state?.ranking_reward}), settings:settingsHtml, colony:buildingsHtml, buildings:() => catalogHtml('buildings'), research:researchHtml, megastructures:stellarHtml, ships:() => catalogHtml('ships'), fleets:fleetsPageHtml, defenses:() => catalogHtml('defenses'), galaxy:galaxyHtml, skills:skillsHtml, reports:reportsHtml, chat:chatHtml, alliance:allianceHtml};
  saveFleetDraft(model, collectFleet(false));
  fleetQuoteController.cancel();
  fleetFormGeneration++;
  destroyMainView();
  const focusedResearch=document.activeElement?.dataset?.research;
  const focusedSystem = document.activeElement?.dataset?.system;
  $('#main').innerHTML = renderers[model.tab]();
  if (model.tab === 'overview' && model.state.production_status) $('#main').insertAdjacentHTML('beforeend',html`<p class="production-policy">Po 7 dniach bez aktywności produkcja metalu, kryształów i paliwa zatrzymuje się we wszystkich koloniach. Powrót do gry ją wznawia, bez odrabiania przerwy.</p>`);
  if (model.tab === 'reports' && !document.hidden && markReportsRead()) renderChrome();
  if (model.tab === 'galaxy') { mountMap(); if (focusedSystem) [...document.querySelectorAll('[data-system]')].find((node) => node.dataset.system === focusedSystem)?.focus({preventScroll:true}); }
  if(model.tab==='research'){researchTreeController=mountResearchTree($('#research-tree-scroll'),researchLayout(model.state.catalog.research),{view:model.researchView,onView:view=>model.researchView=view});if(focusedResearch)document.querySelector(`[data-research="${CSS.escape(focusedResearch)}"]`)?.focus({preventScroll:true});}
  if (['colony','buildings','ships','defenses','megastructures'].includes(model.tab)) catalogCarouselController=mountCatalogCarousels($('#main'),model.catalogViews[model.state.planet_id] ||= {},{onBatch:updateBatchPreview});
  renderBuildingDetails();renderResearchDetails();renderPlanetDetails();
  if (model.busy) $('#main').querySelectorAll('button').forEach((button) => { button.disabled = true; });
  if (model.tab === 'chat' && $('#chat-feed')) $('#chat-feed').scrollTop = $('#chat-feed').scrollHeight;
  if ($('#fleet-form')) fleetQuoteController.update();
}

async function openNavigationTab(tab) {
  if (!model.state || !tabs[tab] || model.busy) return;
  // Controllers save on destroy. Reset afterwards so cleanup cannot restore
  // the old position, including when the active navigation tab is clicked.
  destroyMainView();
  if (tab === 'research') model.researchView = {};
  if (['colony','buildings','ships','defenses'].includes(tab)) {
    const view = model.catalogViews[model.state.planet_id]?.[tab==='colony'?'buildings':tab];
    if (view) {
      view.left = 0;
      delete view.anchor;
      delete view.offset;
      delete view.scrollTops;
      // Keep entered production quantities when returning to the first card.
    }
  }
  if (tab === 'galaxy') {
    model.galaxyMode = 'map';
    model.missionSelecting = false;
    model.fleetDraft = null;
    model.fleetTarget = '';
    model.fleetSystemId = '';
    model.fleetMission = 'scout';
    model.fleetTravelMode = 'normal';
  }
  closeBuildingDetails(false);
  closeResearchDetails(false);
  closeReportDetails(false);
  await switchTab(tab);
}

async function switchTab(tab) {
  if (!tabs[tab] || model.busy) return;
  saveFleetDraft(model, collectFleet(false));
  closePlanetDetails(false);
  if (tab === 'galaxy') prepareGalaxyEntry();
  model.tab = tab;
  try { sessionStorage.setItem('alien-colonies.tab',tab); } catch {}
  model.fleetPreview = null;
  renderChrome();
  renderMain();
  $('#main').scrollTop=0;
  window.scrollTo({top:0, left:0, behavior:'instant'});
  if (tab === 'chat') await loadChat();
  if (tab === 'alliance') await loadAlliance();
  if (tab === 'ranking') await loadRanking();
}

async function loadRanking(page = 1, aroundMe = false) {
  if (!model.token) return;
  const epoch = model.epoch, sequence = ++model.rankingSequence, category = model.rankingCategory;
  model.rankingBusy = true;
  model.rankingError = '';
  const renderRanking = () => {
    const open = Boolean(document.querySelector('.ranking-reward-help')?.open);
    renderMain();
    const help = document.querySelector('.ranking-reward-help');
    if (help && open) help.open = true;
  };
  if (model.tab === 'ranking') renderRanking();
  try {
    const result = await api(`/ranking?category=${encodeURIComponent(category)}&page=${page}&around_me=${aroundMe ? 1 : 0}`);
    if (epoch !== model.epoch || sequence !== model.rankingSequence) return;
    model.ranking = result;
  } catch (error) {
    if (epoch !== model.epoch || sequence !== model.rankingSequence) return;
    model.rankingError = t('Nie udało się pobrać rankingu. Naciśnij odśwież, aby spróbować ponownie.');
  }
  if (epoch !== model.epoch || sequence !== model.rankingSequence) return;
  model.rankingBusy = false;
  if (model.tab === 'ranking') {
    renderRanking();
    if (aroundMe) document.querySelector('[data-ranking-self]')?.scrollIntoView({block:'center',behavior:'smooth'});
  }
}

async function loadChat(quiet = false) {
  const epoch = model.epoch;
  try {
    const feed = await api('/chat');
    if (epoch !== model.epoch) return;
    model.chat = feed;
    if (model.tab === 'chat') {
      if (quiet && $('#chat-feed')) {
        const atBottom = $('#chat-feed').scrollTop + $('#chat-feed').clientHeight >= $('#chat-feed').scrollHeight - 30;
        $('#chat-feed').innerHTML = messagesHtml(feed.messages) || html(["<p class=\"empty-state\">Cisza w eterze. Wyślij pierwszą wiadomość.</p>"]);
        if (atBottom) $('#chat-feed').scrollTop = $('#chat-feed').scrollHeight;
      } else renderMain();
      const lastId = feed.messages?.at(-1)?.id;
      if (lastId) {
        const read = await api('/chat/read', {method:'POST', body:{peer_id:'', last_id:lastId}});
        if (model.state && epoch === model.epoch) { model.state.communications = read.summary; renderChrome(); }
      }
    }
  } catch (error) {
    if (epoch !== model.epoch || quiet) return;
    model.chat = {error:error.message};
    if (model.tab === 'chat') renderMain();
  }
}

async function loadAlliance() {
  const epoch = model.epoch;
  try {
    const response = await api('/alliance');
    if (epoch !== model.epoch) return;
    model.alliance = response;
  } catch (error) {
    if (epoch !== model.epoch) return;
    model.alliance = {error:error.message};
  }
  if (model.tab === 'alliance' && epoch === model.epoch) renderMain();
}

async function confirmAction(title, message) {
  const dialog = $('#confirm-dialog');
  $('#confirm-title').textContent = title;
  $('#confirm-text').textContent = message;
  dialog.returnValue = 'cancel';
  dialog.showModal();
  return new Promise((resolve) => dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), {once:true}));
}

async function mutate(path, payload, {retry = false} = {}) {
  if (model.busy || !model.token) return;
  const body = retry ? payload : {...payload, request_id:requestId()};
  const epoch = model.epoch;
  let acknowledged = false;
  model.busy = true;
  renderBuildingDetails();renderResearchDetails();
  model.stateSequence++;
  $('#main').querySelectorAll('button, input, textarea, select').forEach((element) => { element.dataset.wasDisabled = element.disabled ? '1' : '0'; element.disabled = true; });
  $('#planet-select').disabled = true;
  try {
    const response = await api(path, {method:'POST', body});
    if (epoch !== model.epoch) return;
    acknowledged = true;
    model.uncertain = null;
    if (response.state) acceptState(response.state);
    if (path === '/alliance') {
      model.alliance = response;
      // Refresh the compact alliance badge without delaying acknowledgement.
      if (model.state) model.state.alliance = response.alliance || {name:'',tag:'',id:''};
    }
    if (path === '/chat/send') {
      // Leave text intact on failures; clear only after an acknowledged send.
      if ($('#chat-message')) $('#chat-message').value = '';
    }
    toast(response.message || (path === '/chat/send' ? t('Wiadomość wysłana.') : t('Zapisano zmiany.')));
    if (path === '/chat/send') await loadChat();
    return response;
  } catch (error) {
    if (epoch !== model.epoch) return;
    if (!error.status) {
      model.uncertain = {path, body};
      toast(text`${error.message} Nie ponawiaj zamówienia ręcznie; użyj przycisku obok, aby sprawdzić stan i bezpiecznie ponowić.`, true, true);
    } else toast(error.message, true);
  } finally {
    model.busy = false;
    if (!model.state) $('#auth-google').disabled = false;
    if (epoch === model.epoch && model.state) {
      $('#main').querySelectorAll('[data-was-disabled]').forEach((element) => { element.disabled = element.dataset.wasDisabled === '1'; delete element.dataset.wasDisabled; });
      renderChrome();
      renderBuildingDetails();renderResearchDetails();
      // Preserve unsuccessful messages and forms for correction.
      if (acknowledged) {
        if (path === '/action') model.fleetPreview = null;
        renderMain();
      }
    }
  }
}

function gameAction(payload) { return mutate('/action', {planet_id:model.state.planet_id, ...payload}); }

function openQueueSubscription() {
  $('#queue-subscription-content').innerHTML = subscriptionInfoHtml(model.state,{titleId:'queue-subscription-title'});
  const dialog = $('#queue-subscription-dialog');
  if (!dialog.open) dialog.showModal();
}

function collectFleet(validate = true) {
  const form = $('#fleet-form');
  if (!form || (validate && !form.reportValidity())) return null;
  const ships = {};
  const cargo = {};
  const mission = form.elements.mission.value;
  for (const item of model.state.catalog?.ships || []) ships[item.key] = Number(form.elements.namedItem(`ship-${item.key}`)?.value || 0);
  for (const key of Object.keys(resourceNames)) cargo[key] = ['transport','colonize'].includes(mission) ? Number(form.elements.namedItem(`cargo-${key}`)?.value || 0) : 0;
  const scope = mission === 'scout' && model.fleetSystemId ? {scout_scope:'system',target_system_id:model.fleetSystemId} : {};
  return {planet_id:model.state.planet_id, target_id:model.fleetTarget, mission, ships, cargo, travel_mode:mission==='expedition'?'normal':form.elements.travel_mode?.value||'normal',...(mission==='expedition'?{expedition_hours:Number(form.elements.expedition_hours?.value || 1)}:{}),...scope};
}

function readFleetQuoteDraft() {
  const form = $('#fleet-form');
  if (!form || !model.state || !model.token || model.tab !== 'galaxy' || model.missionSelecting) return null;
  const payload = collectFleet(false);
  const state = model.state;
  const scope = JSON.stringify([model.epoch, fleetFormGeneration, fleetQuoteContext(state,payload,serverNow())]);
  const stock = {...state.resources,dyson_energy:Number(state.megastructures?.energy || 0)};
  if (model.busy) return {scope,payload,reason:t('Poczekaj na zakończenie operacji…')};
  if (model.uncertain) return {scope,payload,reason:t('Najpierw sprawdź wynik poprzedniego rozkazu.')};
  if (!form.checkValidity()) return {scope,payload,reason:t('Popraw liczbę statków lub ładunek.')};
  if (payload.mission === 'expedition') {
    const info = state.expeditions || {};
    if (Number(info.level || 0) < 1) return {scope,payload,reason:t('Zbuduj bazę ekspedycyjną na planecie startowej.')};
    if (Number(info.active) >= Number(info.max_active)) return {scope,payload,reason:t('Wszystkie miejsca na ekspedycje są zajęte. Rozbuduj bazę albo poczekaj na powrót floty.')};
    if (!(payload.ships.scout > 0)) return {scope,payload,reason:t('Ekspedycja wymaga przynajmniej jednego zwiadowcy.')};
  }
  if (!Object.values(payload.ships).some(count => count > 0)) return {scope,payload,reason:t('Wybierz co najmniej jeden statek.')};
  return {scope,payload,stock};
}

function clearFleetPreview() {
  fleetPreviewRequest++;
  saveFleetDraft(model, collectFleet(false));
  fleetQuoteController.update();
  refreshMapRoute();
}

function fleetQuoteWarnings(payload, result = {}) {
  const warnings = [];
  if (payload.mission === 'colonize') warnings.push(result.colonization_warning || t(COLONIZATION_WARNING));
  const target = (model.state.galaxy || []).flatMap(system => system.planets || []).find(planet => planet.id === payload.target_id);
  if (payload.mission === 'attack' && target?.owner_type === 'player' && Number(model.state.player.protected_until) > serverNow()) warnings.push(t('Atak na gracza kończy twoją ochronę startową.'));
  return warnings;
}

function renderFleetQuote(view) {
  const form = $('#fleet-form');
  if (!form) return;
  const previewBox = form.querySelector('#fleet-preview');
  const send = form.querySelector('[data-launch-fleet]');
  const details = form.querySelector('#fleet-route-details');
  if (!previewBox || !send) return;
  model.fleetPreview = null;
  send.disabled = true;
  send.textContent = view.phase === 'loading' || view.phase === 'waiting' ? t('Obliczanie…') : fleetSendCaption();
  previewBox.setAttribute('aria-busy', String(view.phase === 'loading' || view.phase === 'waiting'));
  if (details) details.innerHTML = '';
  if (view.phase === 'invalid') {
    previewBox.innerHTML = html`<p class="fleet-draft-reason">${esc(view.reason)}</p>`;
    return;
  }
  if (view.phase === 'waiting' || view.phase === 'loading') {
    previewBox.innerHTML = html(["<p class=\"loading\">Obliczanie trasy…</p>"]);
    return;
  }
  if (view.phase === 'error') {
    previewBox.innerHTML = html`<p class="form-error" role="alert">${esc(t(view.error.message))}</p><button type="button" class="button small subtle" data-retry-fleet-quote>Ponów obliczenie</button>`;
    return;
  }
  if (view.phase !== 'ready') return;
  const {payload,result} = view;
  model.fleetPreview = {payload,result};
  const shortfall = Object.entries(result.shortfall || {}).filter(([,value]) => Number(value) > 0).map(([key,value]) => `${resourceNames[key] || key}: ${fmt(value)}`);
  if (Number(result.tunnel?.energy_shortfall) > 0) shortfall.push(`${t('Energia')}: ${fmt(result.tunnel.energy_shortfall)}`);
  const capacity = Number(result.capacity || 0);
  const cargo = Object.values(payload.cargo).reduce((sum,value) => sum + Number(value), 0);
  const warnings = fleetQuoteWarnings(payload,result);
  const failed = result.affordable === false;
  previewBox.innerHTML = html`<div class="fleet-quote-metrics"><div><span>Czas do celu</span><strong>${duration(result.seconds)}</strong></div><div><span>${result.tunnel ? t('Energia transferu i powrotu') : t('Paliwo w obie strony')}</span><strong${failed ? ' class="shortfall"' : ''}>${fmt(result.tunnel?.energy_cost ?? result.fuel_cost)}</strong></div><div><span>Ładunek</span><strong>${fmt(cargo)} / ${fmt(capacity)}</strong></div></div>${result.expedition ? html`<p>${t('Poszukiwania: {0} h',result.expedition.search_hours)} · ${t('Przewidywany powrót: {0}',dateText(result.return_at))}</p>` : ''}${failed ? html`<p class="form-error" role="alert">${shortfall.length ? t('Brakuje: {0}',shortfall.join(' · ')) : esc(result.message || t('Brak zasobów na tę wyprawę.'))}</p>` : ''}${warnings.map(warning => html`<p class="fleet-warning" role="note">${esc(warning)}</p>`).join('')}`;
  if (details) details.innerHTML = result.route && !result.tunnel ? fleetNetworkHtml(result.route) : '';
  send.disabled = failed || model.busy || Boolean(model.uncertain);
  refreshMapRoute();
}

async function launchFleet() {
  if (model.busy || model.uncertain) return;
  const form = $('#fleet-form');
  if (!form || !form.reportValidity()) return;
  const quote = fleetQuoteController.currentQuote();
  if (!quote) { clearFleetPreview(); return; }
  // Explicit click only. Quote completion never calls this action.
  fleetQuoteController.cancel();
  form.querySelector('[data-launch-fleet]').disabled = true;
  const result = await gameAction({...quote.payload, type:'fleet'});
  if (result) {
    resetMissionDraft(model);
    model.missionSelecting = false;
    model.tab = 'galaxy';
    model.galaxyMode = 'map';
    prepareGalaxyEntry();
    renderChrome();
    renderMain();
  } else if (!model.uncertain && $('#fleet-form')) fleetQuoteController.update();
}

$('#auth-email').addEventListener('click', () => {
  if (model.busy || model.token || !model.emailAuth.configured) return;
  emailAuthEpoch = model.epoch;emailReauthPlayer = '';
  $('#auth-error').hidden = true;
  emailFlow.open();
});
$('#email-address-form').addEventListener('submit', event => {event.preventDefault();void emailFlow.send($('#email-address').value);});
$('#email-name-form').addEventListener('submit', event => {event.preventDefault();void emailFlow.submitName($('#email-empire-name').value);});
$('#email-resend').addEventListener('click', () => {void emailFlow.resend();});
$('#email-check').addEventListener('click', () => {emailFlow.checkAgain();});
$('#email-cancel').addEventListener('click', () => {emailFlow.cancel();});
$('#email-auth-dialog').addEventListener('cancel', event => {event.preventDefault();emailFlow.cancel();});
window.addEventListener('pagehide', () => {emailFlow.cancel();cancelGoogleName({focus:false});});

$('#auth-login').addEventListener('click', () => setAuthMode(false));
$('#auth-register').addEventListener('click', () => setAuthMode(true));
$('#auth-google').addEventListener('click', () => {void signInWithGoogle();});
$('#google-name-form').addEventListener('submit', event => {event.preventDefault();void submitGoogleName();});
$('#google-name-dialog').addEventListener('cancel', event => {event.preventDefault();cancelGoogleName();});
$('#auth-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (model.busy) return;
  model.busy = true;
  $('#auth-submit').disabled = true;
  $('#auth-error').hidden = true;
  try {
    const result = await api(model.register ? '/register' : '/login', {method:'POST', body:{name:$('#empire-name').value.trim(), password:$('#password').value}, authenticated:false});
    if (!result.token) throw new ApiError(t('Nie otrzymano sesji gry. Zaloguj się ponownie.'));
    storeToken(result.token);
    model.epoch++;
    pendingQuietRender = false;
    model.tab = 'colony';
    model.busy = false;
    showGame(result.state);
    toast(result.message || t('Witaj w swoim imperium.'));
  } catch (error) {
    $('#auth-error').textContent = error.message;
    $('#auth-error').hidden = false;
  } finally {
    model.busy = false;
    $('#auth-submit').disabled = false;
  }
});

$('#logout').addEventListener('click', () => {
  if (model.busy) return;
  const sessionToken = model.token;
  clearSession();
  showAuth();
  setAuthMode(model.register);
  toast(t('Wylogowano z imperium.'));
  void revokeSession(sessionToken);
});
$('#open-ranking').addEventListener('click', () => switchTab('ranking'));

$('#refresh').addEventListener('click', async () => {
  if (model.busy) return;
  try { await loadState(); if (model.tab === 'alliance') await loadAlliance(); if (model.tab === 'chat') await loadChat(); if (model.tab === 'ranking') await loadRanking(model.ranking?.page || 1); toast(t('Stan imperium odświeżony.')); } catch { /* Detailed error already displayed. */ }
});
$('#planet-select').addEventListener('change', async (event) => {
  fleetQuoteController.cancel();
  model.fleetTarget = '';
  model.fleetDraft = null;
  model.fleetPreview = null;
  try { await loadState({planetId:event.target.value}); } catch { if (model.state) $('#planet-select').value = model.state.planet_id; }
});

document.addEventListener('click', async (event) => {
  const target = event.target.closest('button') || event.target.closest('.report-card')?.querySelector('[data-report]');
  if (!target || target.disabled) return;
  if (target.hasAttribute('data-ranking-refresh')) { await loadRanking(model.ranking?.page || 1); return; }
  if (target.hasAttribute('data-ranking-own')) { await loadRanking(1,true); return; }
  if (target.hasAttribute('data-ranking-page')) { await loadRanking(Number(target.dataset.rankingPage)); return; }
  if (target.hasAttribute('data-resume-production')) {try { await loadState(); } catch {} return;}
  if (target.hasAttribute('data-close-toast')) { $('#toast').hidden = true; return; }
  if (target.hasAttribute('data-cancel-google-name')) {cancelGoogleName();return;}
  if (target.hasAttribute('data-retry') && model.uncertain) {
    const pending = model.uncertain;
    try { await loadState(); await mutate(pending.path, pending.body, {retry:true}); } catch { /* Retain the same request id and retry affordance. */ }
    return;
  }
  if (target.hasAttribute('data-close-research')) {closeResearchDetails();return;}
  if (target.hasAttribute('data-close-building')) { closeBuildingDetails(); return; }
  if (target.hasAttribute('data-close-planet-info')) { closePlanetDetails(); return; }
  if (target.hasAttribute('data-close-report')) { closeReportDetails(); return; }
  if (target.hasAttribute('data-report') && model.state) { openReportDetails(target.dataset.report, target); return; }
  if (target.hasAttribute('data-retry-report') && model.reportDetail) { void loadReportReplay(); return; }
  if (target.hasAttribute('data-close-queue-subscription')) { $('#queue-subscription-dialog').close(); return; }
  if (!model.state || model.busy) return;
  if (target.hasAttribute('data-email-reauth')) {
    if (model.busy || !model.state?.account?.email_linked || !model.emailAuth.configured) return;
    emailAuthEpoch = model.epoch;emailReauthPlayer = model.state.player.id;
    emailFlow.open({expectedPlayerId:emailReauthPlayer});return;
  }
  if (target.hasAttribute('data-email-logout-others')) {
    if (model.busy || !model.state?.account?.email_linked) return;
    const passwordInput = $('#email-other-password');
    if (passwordInput && !passwordInput.reportValidity()) return;
    const epoch = model.epoch;model.busy = true;target.disabled = true;
    const status = $('#email-account-status');status.hidden = true;
    try {
      const result = await api('/account/logout-others',{method:'POST',body:{password:passwordInput?.value || ''}});
      if (epoch === model.epoch) {status.textContent = result.message || t('Wylogowano pozostałe urządzenia.');status.hidden = false;}
    } catch (error) {if (epoch === model.epoch) {status.textContent = error.message;status.hidden = false;}}
    finally {if (epoch === model.epoch) {model.busy = false;if (target.isConnected) target.disabled = false;if (passwordInput?.isConnected) passwordInput.value = '';}}
    return;
  }
  if (target.hasAttribute('data-google-reauth')) {await signInWithGoogle('login','',{reauth:true});return;}
  if (target.hasAttribute('data-google-link')) {
    const input = $('#google-link-password');
    if (input && !input.reportValidity()) return;
    const password = input?.value || '';
    if (input) input.value = '';
    await signInWithGoogle('link',password);
    return;
  }
  if (target.hasAttribute('data-queue-subscription')) { openQueueSubscription(); return; }
  if (target.dataset.planProject) {
    if (!planningActive(model.state)) {openQueueSubscription();return;}
    const group={build:'buildings',research:'research',ship:'ships',defense:'defenses'}[target.dataset.kind];
    const item=model.state.catalog?.[group]?.find(entry=>entry.key===target.dataset.planProject);
    if (!canPlanProject(model.state,item,target.dataset.kind,model.busy)) {toast(item?.planning_reason || t('Odśwież stan gry przed zaplanowaniem projektu.'),true);return;}
    const amountInput=target.closest('.project-card')?.querySelector('[data-batch]');
    if (amountInput && !amountInput.reportValidity()) return;
    await gameAction({type:'plan_project',kind:target.dataset.kind,key:item.key,amount:amountInput ? Number(amountInput.value) : 1});
    return;
  }
  if (target.dataset.removePlanned) {
    const order=model.state.planned_orders?.find(entry=>entry.id===target.dataset.removePlanned);
    if (order && await confirmAction(t('Usunąć zaplanowany projekt?'),t('Projekt nie zostanie rozpoczęty. Koszt nie został jeszcze pobrany.'))) await gameAction({type:'remove_planned_project',planet_id:order.planet_id,order_id:order.id});
    return;
  }
  if (target.dataset.plannedUp || target.dataset.plannedDown) {
    const payload=reorderPlannedPayload(model.state,target.dataset.plannedUp || target.dataset.plannedDown,target.dataset.plannedUp ? 'up' : 'down');
    if (payload) await gameAction(payload);
    return;
  }
  if (target.dataset.inspectPlanet) { openPlanetDetails(target.dataset.inspectPlanet, target); return; }
  if (target.dataset.research || target.dataset.openResearch) {openResearchDetails(target.dataset.research||target.dataset.openResearch);return;}
  if (target.dataset.locateResearch) {
    closeResearchDetails(false);await switchTab('research');
    const node=document.querySelector(`[data-research="${CSS.escape(target.dataset.locateResearch)}"]`);
    node?.scrollIntoView({block:'nearest',inline:'center',behavior:'smooth'});node?.focus({preventScroll:true});return;
  }
  if (target.dataset.openShip) {
    closeResearchDetails(false);await switchTab('ships');
    document.querySelector(`[data-ship-card="${CSS.escape(target.dataset.openShip)}"]`)?.scrollIntoView({block:'center',inline:'center',behavior:'smooth'});return;
  }
  if(target.hasAttribute('data-open-stellar')){closeResearchDetails(false);await switchTab('buildings');document.querySelector('[data-catalog-card="dyson"]')?.scrollIntoView({block:'nearest',inline:'center'});return;}
  if(target.dataset.stellarOrigin){model.tab='buildings';try{await loadState({planetId:target.dataset.stellarOrigin});}catch{}return;}
  if(target.dataset.megabuild){
    const project=model.state.megastructures?.projects?.find(entry=>entry.key===target.dataset.megabuild);
    if(project&&await confirmAction(text`Rozpocząć: ${project.name}?`,t('Koszt zostanie pobrany z aktywnej kolonii. Pierwszy etap ustala centrum projektu. Budowa nie blokuje zwykłych budynków ani badań.')))await gameAction({type:'megabuild',key:project.key});return;
  }
  if(target.dataset.megacancel){if(await confirmAction(t('Anulować megastrukturę?'),t('Trwający etap zostanie przerwany, a zapisany koszt zwrócony. Ukończone etapy pozostaną.')))await gameAction({type:'megacancel',queue_id:target.dataset.megacancel});return;}
  if(target.hasAttribute('data-tunnel-open')){if(model.tunnelTarget&&await confirmAction(t('Otworzyć tunel?'),t('Energia otwarcia zostanie zużyta od razu. Następnie tunel pobiera energię podtrzymania. Transfer floty wymaga dodatkowej energii.')))await gameAction({type:'tunnel_open',target_id:model.tunnelTarget});return;}
  if(target.hasAttribute('data-tunnel-close')){if(await confirmAction(t('Zamknąć tunel?'),t('Wysłane floty zachowają opłacony powrót. Zużyta energia nie zostanie zwrócona.')))await gameAction({type:'tunnel_close'});return;}
  if(target.dataset.tunnelFleet){
    resetMissionDraft(model);model.missionSelecting=false;model.fleetTarget=target.dataset.tunnelFleet;model.fleetMission='scout';model.fleetTravelMode='tunnel';model.fleetPreview=null;
    await switchTab('galaxy');$('#fleet-panel')?.scrollIntoView({block:'start',behavior:'smooth'});return;
  }
  if(target.hasAttribute('data-expedition-start')) {
    resetMissionDraft(model);
    model.fleetMission='expedition';model.fleetTarget=model.state.expeditions?.zone?.id || '';
    model.missionSelecting=false;
    await switchTab('galaxy');return;
  }
  if(target.dataset.expeditionRecall) {
    await gameAction({type:'recall_expedition',fleet_id:target.dataset.expeditionRecall});return;
  }
  if(target.hasAttribute('data-new-mission')){await beginNewMission();return;}
  if(target.hasAttribute('data-resume-fleet')) { model.missionSelecting=false; await switchTab('galaxy'); return; }
  if(target.hasAttribute('data-change-destination')){changeMissionDestination();return;}
  if(target.hasAttribute('data-fleet-back')) {
    if (!model.missionSelecting) changeMissionDestination();
    else if (model.fleetTarget) { model.missionSelecting=false; renderMain(); }
    else await switchTab('ships');
    return;
  }
  if(target.hasAttribute('data-show-map')){model.galaxyMode='map';renderMain();return;}
  if (target.dataset.system) { selectSystem(target.dataset.system); return; }
  if (target.dataset.connectedSystem) { selectSystem(target.dataset.connectedSystem); return; }
  if (target.dataset.galaxyStep) {
    const ids = [...galaxyGroups().keys()];
    changeGalaxy(ids[(ids.indexOf(model.galaxyId) + Number(target.dataset.galaxyStep) + ids.length) % ids.length]);
    return;
  }
  if (target.hasAttribute('data-open-settings')) { await switchTab('settings'); return; }
  if (target.dataset.tab) {
    if (target.closest('#game-nav')) await openNavigationTab(target.dataset.tab);
    else await switchTab(target.dataset.tab);
    return;
  }
  if (target.dataset.race) {
    const race = model.state.races.find((item) => item.id === target.dataset.race);
    if (race && await confirmAction(text`Wybrać rasę ${race.name}?`, t('Wybór rasy jest stały dla tego imperium. Jej gospodarka, okręty i technologie będą podstawą twojej strategii.'))) await gameAction({type:'choose_race', race_id:race.id});
    return;
  }
  if (target.dataset.project) {
    if (projectNeedsQueue(model.state,target.dataset.kind)) {
      // A quiet refresh can preserve a focused batch field across lane changes.
      refreshProjectActions($('#main'),model.state,model.busy);
      toast(t('Kolejka się zmieniła. Wybierz ponownie przycisk projektu.'));
      return;
    }
    const amountInput = target.closest('.project-card')?.querySelector('[data-batch]');
    if (amountInput && !amountInput.reportValidity()) return;
    await gameAction({type:target.dataset.kind, key:target.dataset.project, amount:amountInput ? Number(amountInput.value) : 1});
    return;
  }
  if (target.dataset.cancel) {
    if (await confirmAction(t('Anulować projekt?'), t('Projekt zostanie przerwany. Serwer zwróci zapisany koszt projektu, zgodnie z zasadami gry.'))) await gameAction({type:'cancel_project', queue_id:target.dataset.cancel});
    return;
  }
  if (target.dataset.skill) { await gameAction({type:'unlock_skill', node_id:target.dataset.skill}); return; }
  if (target.dataset.planet) { closePlanetDetails(false); model.fleetTarget = ''; model.fleetPreview = null; model.tab = 'colony'; try { await loadState({planetId:target.dataset.planet}); } catch { /* State error already shown. */ } return; }
  if (target.dataset.target) {
    closePlanetDetails(false);
    model.missionSelecting = false;
    model.fleetTarget = target.dataset.target;
    model.fleetSystemId = target.dataset.systemScout || '';
    model.fleetMission = model.fleetDraft && !target.dataset.systemScout ? model.fleetMission : target.dataset.mission || 'scout';
    model.fleetTravelMode='normal';
    model.fleetPreview = null;
    if (model.fleetDraft && model.fleetMission === 'scout' && !Number(model.fleetDraft.ships?.scout)) model.fleetDraft.ships.scout = Number(model.state.ships?.scout) > 0 ? 1 : 0;
    if (model.fleetDraft && model.fleetMission === 'colonize' && !Number(model.fleetDraft.ships?.colonizer)) model.fleetDraft.ships.colonizer = Number(model.state.ships?.colonizer) > 0 ? 1 : 0;
    renderMain();
    $('#fleet-panel')?.scrollIntoView({behavior:'smooth',block:'start'});
    return;
  }
  if (target.hasAttribute('data-close-fleet')) { resetMissionDraft(model);model.missionSelecting=false;await switchTab('ships');return; }
  if (target.hasAttribute('data-launch-fleet')) { await launchFleet(); return; }
  if (target.hasAttribute('data-retry-fleet-quote')) { clearFleetPreview(); return; }
  if (target.hasAttribute('data-load-chat')) { await loadChat(); return; }
  if (target.hasAttribute('data-load-alliance')) { await loadAlliance(); return; }
  if (target.dataset.allianceAction) {
    await mutate('/alliance', {action:target.dataset.allianceAction, ...(target.dataset.allianceId ? {alliance_id:target.dataset.allianceId} : {}), ...(target.dataset.playerId ? {player_id:target.dataset.playerId} : {})});
    return;
  }
  if (target.hasAttribute('data-alliance-leave') && await confirmAction(t('Opuścić sojusz?'), t('Po opuszczeniu sojuszu obowiązuje 24-godzinny rozejm z dotychczasowymi sojusznikami i przerwa przed dołączeniem do nowego sojuszu.'))) await mutate('/alliance', {action:'leave'});
});

$('#main').addEventListener('change', (event) => {
  if (event.target.id === 'ranking-category') { model.rankingCategory=event.target.value; model.ranking=null; void loadRanking(); }
  if (event.target.matches('[data-language-select]')) changeLanguage(event.target.value);
  if (event.target.id==='settings-detailed') { model.detailedBuildings=event.target.checked; try { localStorage.setItem('alien-colonies.detailed-buildings',model.detailedBuildings?'1':'0'); } catch {} }
  if (event.target.id==='settings-motion') { document.documentElement.classList.toggle('reduce-motion',event.target.checked); try { localStorage.setItem('alien-colonies.reduce-motion',event.target.checked?'1':'0'); } catch {} }
  if (event.target.id === 'galaxy-select') changeGalaxy(event.target.value);
  if (event.target.id === 'tunnel-target') model.tunnelTarget=event.target.value;
  if (event.target.id === 'fleet-travel-mode') model.fleetTravelMode=event.target.value;
  if (event.target.id === 'fleet-mission') {
    const previousMission = model.fleetMission;
    saveFleetDraft(model,collectFleet(false));
    model.fleetMission = event.target.value;
    if (model.fleetMission === 'expedition') {
      model.fleetTarget=model.state.expeditions?.zone?.id || '';
      model.fleetSystemId='';model.fleetTravelMode='normal';
      if (model.fleetDraft) {model.fleetDraft.target_id=model.fleetTarget;model.fleetDraft.expedition_hours ||= 1;model.fleetDraft.ships.scout=Math.max(Number(model.fleetDraft.ships.scout || 0),Number(model.state.ships?.scout)>0?1:0);}
      renderMain();return;
    }
    if (previousMission === 'expedition') {model.fleetTarget='';model.missionSelecting=true;renderMain();return;}
    const cargo = $('#fleet-form')?.querySelector('.fleet-cargo');
    if (cargo) cargo.hidden = !['transport','colonize'].includes(model.fleetMission);
    const key = {scout:'scout',colonize:'colonizer'}[model.fleetMission];
    const input = key && $('#fleet-form')?.elements.namedItem(`ship-${key}`);
    if (input && Number(input.value) < 1 && Number(model.state.ships?.[key]) > 0) input.value = '1';
  }
  if (event.target.closest('#fleet-form')) clearFleetPreview();
});
function updateBatchPreview(input) {
  const item = model.state.catalog?.[model.tab]?.find((entry) => entry.key === input.dataset.batch);
  const card = input.closest('.project-card');
  if (!item || !card) return;
  const amount = Math.max(1, Number(input.value || 1));
  card.querySelector('.cost-list').outerHTML = costHtml(item.cost, amount);
  const cost = Object.fromEntries(Object.entries(item.cost || {}).map(([key, value]) => [key, Number(value) * amount]));
  const reason = projectReason({...item, cost}, model.state);
  let reasonNode = card.querySelector('.project-reason');
  if (!reasonNode && reason) {
    reasonNode = document.createElement('p');
    reasonNode.className = 'project-reason';
    card.querySelector('.project-info').append(reasonNode);
  }
  if (reasonNode) {reasonNode.textContent = reason; reasonNode.hidden = !reason;}

  const reduction = Math.min(Number(item.batch_time_reduction_cap || 0), Number(item.batch_time_reduction_per_extra || 0) * (amount - 1));
  card.querySelector('.duration').textContent = text`Czas partii: ${duration(Math.ceil(Number(item.seconds) * amount * (1 - reduction)))}`;
}

$('#main').addEventListener('input', (event) => {
  if (event.target.closest('#fleet-form')) clearFleetPreview();
  if (event.target.hasAttribute('data-batch')) updateBatchPreview(event.target);
});
$('#main').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.target;
  if (model.busy) return;
  if (form.id === 'empire-rename-form') {
    event.preventDefault();
    if (model.busy || !model.token) return;
    const session = model.token;
    const name = form.querySelector('#empire-rename-name').value.trim();
    const button = form.querySelector('button[type="submit"]');
    model.busy = true;
    button.disabled = true;
    try {
      const result = await api('/account/rename', {method:'POST',body:{name,planet_id:model.state.planet_id}});
      if (session !== model.token) return;
      model.ranking = null;
      model.busy = false;
      showGame(result.state);
      toast(result.message || t('Zmieniono nazwę imperium.'));
    } catch (error) {
      if (session === model.token) toast(error.message, true);
    } finally {
      model.busy = false;
      if (button.isConnected) button.disabled = false;
    }
    return;
  }
  if (form.id === 'account-delete-form') {
    const error = $('#account-delete-error');
    error.hidden = true;
    if ($('#account-delete-name').value !== model.state.player.name) {
      error.textContent = t('Wpisz dokładną nazwę swojego imperium.');
      error.hidden = false;
      return;
    }
    if (!await confirmAction(t('Trwale usunąć konto?'),t('Imperium, kolonie, floty i postępy zostaną usunięte. Tej operacji nie można cofnąć.'))) return;
    const password = $('#account-delete-password')?.value || '';
    const epoch = model.epoch;
    model.busy = true;
    form.querySelectorAll('button,input').forEach(element => {element.disabled = true;});
    try {
      const result = await api('/account/delete',{method:'POST',body:{password,confirmation:'DELETE ACCOUNT'}});
      if (epoch !== model.epoch) return;
      if (result.deleted !== true) throw new ApiError(t('Nie udało się wykonać tej operacji.'));
      model.busy = false;
      clearSession();
      showAuth();
      toast(result.message || t('Konto i jego imperium zostały usunięte z aktywnego świata.'));
    } catch (failure) {
      if (epoch === model.epoch && error.isConnected) {error.textContent = failure.message;error.hidden = false;}
    } finally {
      model.busy = false;
      if (!model.state) {$('#auth-google').disabled = false;$('#auth-submit').disabled = false;}
      if (form.isConnected) form.querySelectorAll('button,input').forEach(element => {element.disabled = false;});
    }
    return;
  }
  if (form.id === 'fleet-form') { return; }
  if (form.id === 'chat-form') { await mutate('/chat/send', {peer_id:'', text:form.elements.text.value}); return; }
  if (form.id === 'alliance-chat-form') { await mutate('/alliance', {action:'chat_send', text:form.elements.text.value}); return; }
  if (form.id === 'alliance-create-form') { await mutate('/alliance', {action:'create', name:form.elements.name.value, tag:form.elements.tag.value, description:form.elements.description.value}); return; }
  if (form.id === 'alliance-invite-form') { await mutate('/alliance', {action:'invite', player_name:form.elements.player_name.value}); }
});

setInterval(() => {
  if (!model.state || document.hidden) return;
  if (pendingQuietRender && !isUIInteracting() && !model.busy) {
    const pending=pendingQuietRender;pendingQuietRender=false;
    if (pending.epoch===model.epoch && pending.sequence===model.stateSequence) {
      acceptState(pending.state);renderChrome();
      const editing=$('#main').contains(document.activeElement) && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
      if (!editing && !['chat','alliance','settings','ranking'].includes(model.tab) && !(model.tab==='galaxy' && model.fleetTarget)) renderMain();
      else {renderPlanetDetails();refreshPlannedQueuePanels($('#main'),model.state,{busy:model.busy});refreshProjectActions($('#main'),model.state,model.busy);}
    }
  }
  renderResources();
  if(model.tab==='ranking'){
    const reward=Number(model.ranking?.reward?.as_of || 0)>Number(model.state.ranking_reward?.as_of || 0)?model.ranking.reward:model.state.ranking_reward;
    refreshRankingReward($('#main'),reward,serverNow());
  }
  const mega=model.state.megastructures;if(mega){const elapsed=Math.max(0,serverNow()-model.state.server_time);const drain=mega.window?Math.max(0,Math.min(serverNow(),mega.window.closes_at)-Math.max(model.state.server_time,mega.window.opened_at))*mega.window.upkeep_per_second:0;const value=Math.max(0,Math.min(mega.capacity,mega.energy+mega.charge_per_second*elapsed-drain));document.querySelectorAll('[data-mega-energy]').forEach(el=>el.textContent=fmt(value));}
  document.querySelectorAll('[data-countdown]').forEach((element) => { element.textContent = duration(Number(element.dataset.countdown) - serverNow()); });
  document.querySelectorAll('[data-progress]').forEach((element) => { element.style.width = `${Math.min(100, Math.max(0, 100 * (1 - (Number(element.dataset.ends) - serverNow()) / Number(element.dataset.seconds))))}%`; });
}, 1000);

let pageWasHidden = document.hidden;
document.addEventListener('visibilitychange', () => {
  if (pageWasHidden && !document.hidden) playerActivity.mark();
  pageWasHidden = document.hidden;
  if (!document.hidden && model.token && !model.busy) loadState({quiet:true}).catch(() => {});
});

fetch('/site-config', {cache:'no-store', credentials:'same-origin'}).then((response) => response.ok ? response.json() : null).then((config) => {
  if (typeof config?.development !== 'boolean') return;
  document.querySelectorAll('[data-world-badge]').forEach((element) => {
    element.textContent = config.development ? t('Świat testowy') : t('Wspólny świat z Androidem');
    element.classList.toggle('test-world', config.development);
    element.hidden = false;
  });
}).catch(() => {});
setAuthMode(new URLSearchParams(location.search).has('register'));
void loadGoogleAuthConfig();
void loadEmailAuthConfig();
if (model.token) {
  $('#auth-submit').disabled = true;
  $('#auth-description').textContent = t('Przywracanie sesji imperium…');
  try {
    const response = await api('/state');
    showGame(response.state);
  } catch (error) {
    if (error.status === 401) clearSession();
    showAuth();
    setAuthMode(model.register);
    $('#auth-error').textContent = error.status === 401 ? t('Sesja wygasła. Zaloguj się ponownie.') : error.message;
    $('#auth-error').hidden = false;
  } finally { $('#auth-submit').disabled = false; }
}

$('#building-dialog').addEventListener('cancel', (event) => { event.preventDefault(); closeBuildingDetails(); });
$('#building-dialog').addEventListener('click', (event) => {
  if (event.target !== event.currentTarget) return;
  const box = event.currentTarget.getBoundingClientRect();
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) closeBuildingDetails();
});
$('#building-dialog').addEventListener('change', (event) => {
  if (event.target.id !== 'detailed-buildings') return;
  model.detailedBuildings = event.target.checked;
  try { localStorage.setItem('alien-colonies.detailed-buildings', model.detailedBuildings ? '1' : '0'); } catch { /* Optional preference. */ }
  renderBuildingDetails();
});

$('#research-dialog').addEventListener('cancel',event=>{event.preventDefault();closeResearchDetails();});
$('#research-dialog').addEventListener('click',event=>{if(event.target===$('#research-dialog')){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)closeResearchDetails();}});
$('#planet-dialog').addEventListener('cancel', event => {event.preventDefault();closePlanetDetails();});
$('#planet-dialog').addEventListener('click', event => {
  if (event.target !== event.currentTarget) return;
  const box = event.currentTarget.getBoundingClientRect();
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) closePlanetDetails();
});
$('#queue-subscription-dialog').addEventListener('click', event => {
  if (event.target !== event.currentTarget) return;
  const box=event.currentTarget.getBoundingClientRect();
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) event.currentTarget.close();
});
$('#report-dialog').addEventListener('cancel', event => {event.preventDefault();closeReportDetails();});
$('#report-dialog').addEventListener('click', event => {
  if (event.target !== event.currentTarget) return;
  const box = event.currentTarget.getBoundingClientRect();
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) closeReportDetails();
});
const resourceObserver=new ResizeObserver(entries=>{document.documentElement.style.setProperty('--resource-hud-height',`${entries[0].contentRect.height}px`);});
resourceObserver.observe($('#resources'));

$('#open-settings').addEventListener('click',()=>switchTab('settings'));
$('#auth-language').innerHTML=languageOptions();
$('#auth-language').addEventListener('change',e=>changeLanguage(e.target.value));





