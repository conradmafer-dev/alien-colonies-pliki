import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {resourceSnapshot, storageBlocksCost} from '../resource-storage.js';
import {buildingSummary, buildingComparison, buildingNotes} from '../building-effects.js';
import {projectReason} from '../compact-ui.js';
import {projectActionHtml} from '../planned-queues.js';
import {productionWindow} from '../player-activity.js';
import {t, html, text} from '../i18n.js';

const state = (resources = {}, capacity = 10000) => ({resources:{metal:9990,crystal:0,fuel:0,...resources}, production:{metal:3600,crystal:360,fuel:0}, storage:{capacity:{metal:capacity,crystal:capacity,fuel:capacity},full:{metal:false,crystal:false,fuel:false},level:0,building_key:'living_vault'},server_time:100, energy:{supply:100,used:50},catalog:{},limits:{resource_cap:1e9}});
const item = (rest = {}) => ({key:'power_plant', level:2,max_level:12,details:{metrics:[]}, ...rest});
const game = fs.readFileSync(new URL('../game.js', import.meta.url),'utf8');
const renderSource = game.slice(game.indexOf('function renderResources()'),game.indexOf('function compactResource('));
function renderHud(value, now = 100) {
  const nodes = Object.fromEntries(['#resources','#storage-status','#production-status'].map(key => [key,{hidden:false,innerHTML:'',textContent:''}]));
  const context = vm.createContext({model:{state:value},$:key=>nodes[key],productionWindow,serverNow:()=>now,resourceNames:{metal:'Metal',crystal:'Kryształy',fuel:'Paliwo'},resourceSnapshot,t,html,text,fmt:value=>String(Math.floor(Number(value)||0)),compactResource:value=>String(Math.floor(Number(value)||0)),icon:()=>''});
  vm.runInContext(renderSource+';renderResources();',context);
  return nodes;
}

test('resource estimate stops at storage and warns exactly at the limit', () => {
  const value=state();
  assert.deepEqual(resourceSnapshot(value,'metal',9),{current:9999,capacity:10000,full:false});
  assert.deepEqual(resourceSnapshot(value,'metal',10),{current:10000,capacity:10000,full:true});
  assert.equal(resourceSnapshot(value,'metal',86400).current,10000);
  assert.equal(resourceSnapshot(value,'crystal',10).full,false);
});

test('delivered stock above capacity is preserved and resumes after spending', () => {
  assert.deepEqual(resourceSnapshot(state({metal:25000}),'metal',100),{current:25000,capacity:10000,full:true});
  assert.deepEqual(resourceSnapshot(state({metal:5000}),'metal',100),{current:5100,capacity:10000,full:false});
});

test('legacy state without storage keeps its resource ceiling and has no fake warning', () => {
  const value=state();delete value.storage;value.limits.resource_cap=20000;
  assert.deepEqual(resourceSnapshot(value,'metal',86400),{current:20000,capacity:null,full:false});
});

test('real HUD displays capacity without warning below cap, then warns only for full resource', () => {
  let nodes=renderHud(state(),109);
  assert.match(nodes['#resources'].innerHTML,/Limit 10000/);
  assert.equal(nodes['#storage-status'].hidden,true);
  assert.doesNotMatch(nodes['#resources'].innerHTML,/magazyn pełny/);
  nodes=renderHud(state(),110);
  assert.equal(nodes['#storage-status'].hidden,false);
  assert.equal(nodes['#storage-status'].textContent,'Magazyn pełny — rozbuduj skarbiec · Metal');
  assert.match(nodes['#resources'].innerHTML,/0 \/ godz\. · magazyn pełny/);
});

test('real HUD preserves over-cap deliveries and does not grow inactive production', () => {
  let nodes=renderHud(state({metal:25000}),200);
  assert.match(nodes['#resources'].innerHTML,/title="25000"/);
  const paused={...state({metal:9000}),production_status:{paused:true}};
  nodes=renderHud(paused,100000);
  assert.match(nodes['#resources'].innerHTML,/title="9000"/);
  assert.equal(nodes['#storage-status'].hidden,true);
  assert.equal(nodes['#production-status'].hidden,false);
});

test('capacity reason requires both an unaffordable cost and a capacity shortfall', () => {
  const value=state();
  assert.equal(storageBlocksCost(value,{metal:10000}),false);
  assert.equal(storageBlocksCost(value,{metal:10001}),true);
  assert.equal(storageBlocksCost(state({metal:25000}),{metal:20000}),false);
  assert.equal(storageBlocksCost(value,{metal:6000},2),true);
  assert.equal(projectReason({cost:{metal:10001},reason:'Brakuje surowców.'},value),'Rozbuduj skarbiec: pojemność magazynu jest za mała');
  assert.equal(projectReason({cost:{metal:9000},reason:'Kolejka zajęta.'},value),'Kolejka zajęta.');
});

test('storage warnings do not disable manual purchases funded by deliveries', () => {
  const value=state({metal:25000});
  const project={key:'metal_mine',level:1,max_level:12,cost:{metal:20000},enabled:true,reason:''};
  const markup=projectActionHtml(value,project,'build',false,{normalLabel:'Ulepsz'});
  assert.doesNotMatch(markup,/ disabled|pojemność magazynu/);
  assert.equal(projectReason(project,value),'');
});

test('power comparison uses nonlinear server values and excludes Dyson power', () => {
  const plant=item({energy_supply_current:48.4,energy_supply_next:79.86,energy_supply_per_level:999,details:{metrics:[{key:'energy_supply',current:1048.4,next:1079.86}]}});
  assert.equal(buildingSummary(plant),'Energia +48,4');
  assert.deepEqual(buildingComparison(plant),[{label:'Energia z budynku',current:'48,4',next:'79,86'}]);
  assert.equal(buildingComparison(plant,true)[1].current,'1048,4');
  assert.deepEqual(buildingComparison(item({energy_supply_per_level:999})),[]);
});

test('mine energy and vault capacity use current/next metrics with protection retained', () => {
  const mine=item({key:'metal_mine',production_resource:'metal',energy_per_level:999,details:{metrics:[{key:'mine_metal',current:100,next:120},{key:'energy_use',current:24.2,next:39.93}]}});
  assert.deepEqual(buildingComparison(mine)[1],{label:'Zużycie energii',current:'24,2',next:'39,93'});
  for(const key of ['phase_vault','living_vault','armored_vault']) {
    const vault=item({key,building_effect:{key:'protected_resources',current:1500,next:3000},details:{metrics:[{key:'storage_capacity',current:20000,next:40000,unit:'number'}]}});
    const rows=buildingComparison(vault);
    assert.equal(rows.length,2);
    assert.equal(rows[0].label,'Ochrona surowców');
    assert.equal(rows[1].label,'Pojemność magazynów');
    assert.equal(rows[1].current,'20 000');
    assert.equal(rows[1].next,'40 000');
  }
});

test('facility note describes level multiplier and queued timing without old +10% claim', () => {
  for(const key of ['lab','shipyard']) {
    const note=buildingNotes(item({key})).join(' ');
    assert.match(note,/1 \+ poziom/);
    assert.match(note,/przy starcie/);
    assert.doesNotMatch(note,/10 punktów/);
  }
});
