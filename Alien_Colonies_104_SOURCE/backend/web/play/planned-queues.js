import {t, html, getLocale} from './i18n.js?v=0111';
import {storageBlocksCost} from './resource-storage.js?v=01218-storage';

const esc = (value = '') => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
const GROUPS = {build:'buildings', research:'research', ship:'ships', defense:'defenses'};
export const queueLane = kind => kind === 'defense' ? 'ship' : kind;
export const planningActive = state => state?.premium?.queue_planning_active === true;

export function projectNeedsQueue(state, kind) {
  const lane = queueLane(kind);
  if (plannedLaneOrders(state, lane).length) return true;
  if (lane === 'research' && state?.research_queue) return true;
  return (state?.queue || []).some(task => queueLane(task.kind) === lane);
}

// Preserve server order. Research has one shared empire lane; local lanes only
// show the selected colony. Ships and defenses share the shipyard lane.
export function plannedLaneOrders(state, lane) {
  return (state?.planned_orders || []).filter(order => queueLane(order.kind) === lane && (lane === 'research' || order.planet_id === state.planet_id));
}

export function canPlanProject(state, item, kind, busy = false) {
  if (busy || !planningActive(state) || !item || !Object.hasOwn(GROUPS, kind)) return false;
  if (['build','research'].includes(kind) && Number(item.level) >= Number(item.max_level)) return false;
  // Do not infer eligibility from translated reason text. The server exposes a
  // separate flag that considers hard requirements while ignoring a busy lane
  // and resources that can accrue before this planned order starts.
  const eligible = item.planning_enabled === true || item.plan_enabled === true;
  if (!eligible) return false;
  return plannedLaneOrders(state, queueLane(kind)).length < Number(state.limits?.queue_waiting ?? 10);
}

export function projectActionHtml(state, item, kind, busy = false, {normalLabel = '', className = '', detail = false} = {}) {
  const maximum = ['build','research'].includes(kind) && Number(item.level) >= Number(item.max_level);
  const queued = !maximum && projectNeedsQueue(state,kind);
  // An inactive subscription is explained only after the player chooses to
  // plan. Free projects still use the normal server eligibility flag.
  const planEligible = item.planning_eligible === true || item.planning_enabled === true || item.plan_enabled === true;
  const enabled = !busy && !maximum && (queued ? planningActive(state) ? canPlanProject(state,item,kind,busy) : planEligible : item.enabled === true);
  const label = maximum ? t('Maks. poziom') : queued ? t('Dodaj do kolejki') : normalLabel;
  const reason = storageBlocksCost(state, item.cost) ? t('Rozbuduj skarbiec: pojemność magazynu jest za mała')
    : queued ? planningActive(state) ? item.planning_reason : item.planning_eligibility_reason : item.reason;
  return html`<button type="button" class="button ${esc(className)}${enabled ? ' primary' : ' subtle'}" data-project-action data-key="${esc(item.key)}" data-kind="${esc(kind)}" data-normal-label="${esc(normalLabel)}" data-action-class="${esc(className)}" ${queued ? 'data-plan-project' : 'data-project'}="${esc(item.key)}"${detail ? ' data-detail-upgrade' : ''}${reason ? ` title="${esc(reason)}"` : ''}${enabled ? '' : ' disabled'}>${esc(label)}</button>`;
}

export function refreshProjectActions(root, state, busy = false) {
  for (const button of root?.querySelectorAll('[data-project-action]') || []) {
    const item = state?.catalog?.[GROUPS[button.dataset.kind]]?.find(entry => entry.key === button.dataset.key);
    if (!item) continue;
    const markup = projectActionHtml(state,item,button.dataset.kind,busy,{normalLabel:button.dataset.normalLabel,className:button.dataset.actionClass,detail:button.hasAttribute('data-detail-upgrade')});
    if (button.outerHTML !== markup) button.outerHTML = markup;
  }
}

export function subscriptionInfoHtml(state, {titleId = ''} = {}) {
  const premium = state?.premium || {};
  const expiry = Number(premium.expires_at || premium.queue_planning_expires_at || 0);
  const formatted = expiry > 0 ? new Date(expiry * 1000).toLocaleString(getLocale(), {day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}) : '';
  return html`<div class="queue-subscription-info"><p class="eyebrow">SUBSKRYPCJA</p><h2${titleId ? ` id="${esc(titleId)}"` : ''}>Planowanie kolejek</h2>
    <p>Zaplanuj kolejne budowy, partie statków i badania. Projekty rozpoczynają się automatycznie, gdy ich kolejka jest wolna i wymagania są spełnione. Koszt jest pobierany przy rozpoczęciu projektu.</p>
    ${planningActive(state) ? html`<p class="queue-entitlement active">${t('Planowanie jest aktywne')}${formatted ? ` · ${esc(formatted)}` : ''}</p>` : html`<p class="queue-entitlement">Planowanie wymaga aktywnej subskrypcji.</p>`}
    <p>Subskrypcję kupisz lub przywrócisz w aplikacji Alien Colonies na Androidzie. Działa także w przeglądarce po zalogowaniu do tego samego imperium. Cenę i warunki zobaczysz przed zakupem w Google Play.</p>
    <p class="fine-print">Po wygaśnięciu subskrypcji rozpoczęte projekty są kontynuowane, a zaplanowane czekają na wznowienie. Możesz je usunąć. Zwykła ręczna budowa, produkcja i badania pozostają dostępne.</p></div>`;
}

export function reorderPlannedPayload(state, orderId, direction) {
  const order = (state?.planned_orders || []).find(entry => entry.id === orderId);
  if (!order || !planningActive(state)) return null;
  const lane = queueLane(order.kind);
  if (lane !== 'research' && order.planet_id !== state.planet_id) return null;
  const orders = plannedLaneOrders(state, lane);
  const index = orders.findIndex(entry => entry.id === orderId);
  if (direction === 'up' && index > 0) return {type:'reorder_planned_project', order_id:orderId, planet_id:order.planet_id, before_order_id:orders[index - 1].id};
  if (direction === 'down' && index >= 0 && index < orders.length - 1) return {type:'reorder_planned_project', order_id:orderId, planet_id:order.planet_id, before_order_id:orders[index + 2]?.id || null};
  return null;
}

function orderHtml(state, order, index, orders, busy) {
  const item = state.catalog?.[GROUPS[order.kind]]?.find(entry => entry.key === order.key);
  const name = order.name || item?.name || order.key;
  const countable = ['ship','defense'].includes(order.kind);
  const detail = countable ? t('{0} szt.', Number(order.amount || 1)) : Number(order.level || order.target_level) > 0 ? t('Poziom {0}', Number(order.level || order.target_level)) : t('Kolejny poziom');
  const reason = order.waiting_reason || order.reason || (planningActive(state) ? t('Czeka na rozpoczęcie') : t('Czeka na wznowienie subskrypcji'));
  const reorderable = planningActive(state) && !busy;
  return html`<li class="planned-order"><span class="planned-order-number">${index + 1}</span><div class="planned-order-copy"><strong>${esc(name)}</strong><span class="muted">${esc(detail)}${order.kind === 'research' ? ` · ${esc(order.planet_name || order.planet_id)}` : ''}</span><span class="planned-order-reason">${esc(reason)}</span></div><div class="planned-order-actions"><button type="button" class="button small subtle" data-planned-up="${esc(order.id)}" aria-label="Przesuń wyżej: ${esc(name)}"${index === 0 || !reorderable ? ' disabled' : ''}>↑</button><button type="button" class="button small subtle" data-planned-down="${esc(order.id)}" aria-label="Przesuń niżej: ${esc(name)}"${index === orders.length - 1 || !reorderable ? ' disabled' : ''}>↓</button><button type="button" class="button small subtle" data-remove-planned="${esc(order.id)}"${busy ? ' disabled' : ''}>Usuń</button></div></li>`;
}

export function plannedQueuesHtml(state, {lanes = ['build','ship','research'], busy = false} = {}) {
  const occupied = lanes.filter(lane => plannedLaneOrders(state,lane).length);
  if (!occupied.length) return '';
  const names = {build:t('Budowa · aktywna kolonia'), ship:t('Statki i obrona · aktywna kolonia'), research:t('Badania · całe imperium')};
  const active = planningActive(state);
  const limit = Number(state?.limits?.queue_waiting ?? 10);
  return html`<section class="panel planned-queues-panel" data-planned-queue data-lanes="${esc(lanes.join(','))}"><div class="panel-heading"><h2>Zaplanowane projekty</h2></div>
    ${!active ? html`<p class="fine-print">Zaplanowane projekty czekają na wznowienie subskrypcji.</p>` : ''}
    ${occupied.map(lane => {const orders = plannedLaneOrders(state,lane); return html`<div class="planned-lane"><div class="planned-lane-heading"><h3>${names[lane]}</h3><span class="muted">${orders.length} / ${limit}</span></div><ol class="planned-orders">${orders.map((order,index) => orderHtml(state,order,index,orders,busy)).join('')}</ol></div>`;}).join('')}
    <p class="fine-print">Kolejność jest zachowana. Pierwszy projekt czeka na zasoby i wymagania; następne nie wyprzedzają go.</p></section>`;
}

// Quiet polling can refresh this isolated panel without replacing any focused
// catalog batch input, galaxy composer or dialog content.
export function refreshPlannedQueuePanels(root, state, options = {}) {
  for (const panel of root?.querySelectorAll('[data-planned-queue]') || []) {
    if (panel.contains(root.ownerDocument?.activeElement)) continue;
    const markup = plannedQueuesHtml(state, {...options, lanes:(panel.dataset.lanes || 'build,ship,research').split(',')});
    if (panel.outerHTML !== markup) panel.outerHTML = markup;
  }
}

