import test from 'node:test';
import assert from 'node:assert/strict';
import {canPlanProject, plannedLaneOrders, plannedQueuesHtml, queueActionHtml, reorderPlannedPayload, refreshPlannedQueuePanels, subscriptionInfoHtml} from '../web/play/planned-queues.js';

const makeState = rest => ({planet_id:'home', premium:{queue_planning_active:true,expires_at:1800000000},limits:{queue_waiting:10},catalog:{buildings:[],ships:[],defenses:[],research:[]},planned_orders:[],...rest});
const makeOrder = (id,kind,planet_id='home',rest={}) => ({id,kind,planet_id,key:id,name:id,amount:1,planet_name:planet_id,...rest});

test('local construction and shared shipyard filter colonies while research keeps empire order', () => {
  const state = makeState({planned_orders:[makeOrder('b1','build'),makeOrder('b2','build','other'),makeOrder('s1','ship'),makeOrder('d1','defense'),makeOrder('s2','ship','other'),makeOrder('r1','research','other'),makeOrder('r2','research')]});
  assert.deepEqual(plannedLaneOrders(state,'build').map(order=>order.id),['b1']);
  assert.deepEqual(plannedLaneOrders(state,'ship').map(order=>order.id),['s1','d1']);
  assert.deepEqual(plannedLaneOrders(state,'research').map(order=>order.id),['r1','r2']);
  assert.match(plannedQueuesHtml(state,{lanes:['research']}),/other/);
});

test('busy manual lane can accept a valid planned order without enabling hard locked projects', () => {
  const state = makeState();
  const item = {key:'mine',level:1,max_level:12,enabled:false,reason:'Na tej planecie trwa już budowa.',planning_enabled:true};
  assert.equal(canPlanProject(state,item,'build'),true);
  assert.doesNotMatch(queueActionHtml(state,item,'build'),/ disabled/);
  assert.equal(canPlanProject(state,{...item,planning_enabled:false},'build'),false);
  assert.equal(canPlanProject(state,{...item,planning_enabled:undefined},'build'),false);
  assert.equal(canPlanProject(state,{...item,level:12},'build'),false);
  assert.equal(canPlanProject(state,item,'build',true),false);
  assert.equal(canPlanProject(makeState({premium:{queue_planning_active:false}}),item,'build'),false);
});

test('waiting cap includes both ship and defense orders, not another colony', () => {
  const state = makeState({limits:{queue_waiting:2},planned_orders:[makeOrder('s1','ship'),makeOrder('d1','defense'),makeOrder('s2','ship','other')]});
  assert.equal(canPlanProject(state,{key:'scout',planning_enabled:true},'ship'),false);
  state.planet_id='other';
  assert.equal(canPlanProject(state,{key:'scout',planning_enabled:true},'ship'),true);
});

test('reordering uses next position in its lane and originating research colony', () => {
  const state = makeState({planned_orders:[makeOrder('b1','build'),makeOrder('r1','research','other'),makeOrder('r2','research'),makeOrder('r3','research','third')]});
  assert.deepEqual(reorderPlannedPayload(state,'r1','down'),{type:'reorder_planned_project',order_id:'r1',planet_id:'other',before_order_id:'r3'});
  assert.deepEqual(reorderPlannedPayload(state,'r2','up'),{type:'reorder_planned_project',order_id:'r2',planet_id:'home',before_order_id:'r1'});
  assert.deepEqual(reorderPlannedPayload(state,'r2','down'),{type:'reorder_planned_project',order_id:'r2',planet_id:'home',before_order_id:null});
  assert.equal(reorderPlannedPayload(state,'r1','up'),null);
  assert.equal(reorderPlannedPayload(state,'r3','down'),null);
  state.premium.queue_planning_active=false;
  assert.equal(reorderPlannedPayload(state,'r2','up'),null);
});

test('expired subscription preserves visible plans and removal but disables reordering', () => {
  const state = makeState({premium:{queue_planning_active:false},planned_orders:[makeOrder('b1','build','home',{reason:'Subskrypcja wygasła.'}),makeOrder('b2','build')]});
  const markup = plannedQueuesHtml(state,{lanes:['build']});
  assert.match(markup,/Subskrypcja wygasła\./);
  assert.match(markup,/data-remove-planned="b1">Usuń/);
  assert.match(markup,/data-planned-down="b1"[^>]* disabled/);
  assert.match(subscriptionInfoHtml(state),/rozpoczęte projekty są kontynuowane/);
  assert.match(subscriptionInfoHtml(state),/Androidzie/);
  assert.doesNotMatch(subscriptionInfoHtml(state),/href=|4[,.]99|Stripe|PayPal/);
});

test('planned names, colony names, reasons and IDs are escaped', () => {
  const state = makeState({planned_orders:[makeOrder('bad" onclick="x','research','other',{name:'<img src=x onerror=x>',planet_name:'<script>planet</script>',reason:'<script>waiting</script>'})]});
  const markup = plannedQueuesHtml(state,{lanes:['research']});
  assert.match(markup,/&lt;img src=x onerror=x&gt;/);
  assert.match(markup,/&lt;script&gt;waiting&lt;\/script&gt;/);
  assert.doesNotMatch(markup,/<script>|<img src=x|id="bad" onclick=/);
});

test('quiet queue refresh only changes the queue panel and preserves active batch input', () => {
  const state = makeState({planned_orders:[makeOrder('s1','ship')]});
  const input={value:'17',tagName:'INPUT'},document={activeElement:input};
  let writes=0,markup='old';
  const panel={dataset:{lanes:'ship'},contains:node=>false,get outerHTML(){return markup;},set outerHTML(value){writes++;markup=value;}};
  const main={ownerDocument:document,querySelectorAll:selector=>{assert.equal(selector,'[data-planned-queue]');return [panel];}};
  refreshPlannedQueuePanels(main,state);
  assert.equal(writes,1);
  assert.match(markup,/data-remove-planned="s1"/);
  assert.equal(document.activeElement,input);
  assert.equal(input.value,'17');
  refreshPlannedQueuePanels(main,state);
  assert.equal(writes,1);
  document.activeElement={tagName:'BUTTON'};
  panel.contains=()=>true;
  state.planned_orders.push(makeOrder('s2','ship'));
  refreshPlannedQueuePanels(main,state);
  assert.equal(writes,1,'focused queue control is preserved until interaction finishes');
});
