import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {createFleetQuoteController, saveFleetDraft, fleetQuoteContext} from '../fleet-flow.js';
import {resetMissionDraft} from '../compact-ui.js';

const source = readFileSync(new URL('../game.js',import.meta.url),'utf8');
const between = (a,b) => source.slice(source.indexOf(a),source.indexOf(b));
const tick = () => new Promise(resolve => setImmediate(resolve));
function setup() {
  const fields = Object.fromEntries([['mission','scout'],['travel_mode','normal'],['ship-scout','1'],['ship-cargo','0'],['cargo-metal','0'],['cargo-crystal','0'],['cargo-fuel','0']].map(([key,value]) => [key,{value}]));
  const preview={innerHTML:'',setAttribute(){}}, details={innerHTML:''}, send={disabled:true,textContent:''};
  const form = {elements:{...fields,namedItem:key => fields[key]},reportValidity:() => true,
    checkValidity:() => Object.entries(fields).every(([key,input]) => !key.startsWith('ship-') || Number(input.value) >= 0 && Number(input.value) <= 10),
    querySelector:selector => ({'#fleet-preview':preview,'[data-launch-fleet]':send,'#fleet-route-details':details}[selector]),
  };
  let visible = true, timer = 0, actionResolve;
  const timers=new Map(), quotes=[], actions=[], pending=[];
  const model={galaxyViews:{},selectedSystems:{},state:{planet_id:'home',planet_name:'Home',player:{id:'me',protected_until:5000},resources:{metal:1000,crystal:1000,fuel:1000},
    ships:{scout:10,cargo:10},catalog:{ships:[{key:'scout'},{key:'cargo'}]},galaxy:[{id:'home-system',galaxy_id:'g2',planets:[{id:'home'}]},{id:'system',galaxy_id:'g1',planets:[{id:'target',system_id:'system',owner_type:'player',owner_id:'other'}]}]},
    token:'session1',epoch:1,tab:'galaxy',fleetTarget:'target',fleetSystemId:'',fleetMission:'scout',fleetTravelMode:'normal',missionSelecting:false,busy:false,uncertain:null};
  const context=vm.createContext({model,fleetFormGeneration:1,fleetPreviewRequest:0,resourceNames:{metal:'Metal',crystal:'Crystal',fuel:'Fuel'},
    saveFleetDraft,fleetQuoteContext,resetMissionDraft,COLONIZATION_WARNING:'Capture risk',
    $:selector => selector==='#fleet-form' && visible ? form : null,
    t:(value,...args) => String(value).replace(/\{(\d+)\}/g,(_,n) => args[n]),
    html:(strings,...values) => strings.map((part,index) => part+(values[index] ?? '')).join(''),
    esc:value => String(value ?? ''),fmt:value => String(value),duration:value => `${value}s`,serverNow:() => 1000,
    refreshMapRoute(){},fleetNetworkHtml:() => '',renderChrome(){},renderMain(){visible=false;},
    gameAction(payload) {actions.push(payload);model.busy=true;return new Promise(resolve => {actionResolve=resolve;});},
  });
  vm.runInContext(between('function fleetSendCaption() {','function fleetFormHtml() {')
    +between('function prepareGalaxyEntry() {','function galaxyExplorerHtml() {')
    +between('function changeMissionDestination() {','function skillsHtml() {')
    +between('function collectFleet(validate = true) {',"$('#auth-email').addEventListener"),context);
  context.fleetQuoteController=createFleetQuoteController({read:() => context.readFleetQuoteDraft(),
    quote:payload => {quotes.push(payload);return new Promise(resolve => pending.push(resolve));},
    onChange:view => context.renderFleetQuote(view),
    setTimer(fn) {timers.set(++timer,fn);return timer;},clearTimer:id => timers.delete(id),
  });
  return {context,model,fields,form,send,preview,quotes,actions,
    flush() {const work=[...timers.values()];timers.clear();for(const fn of work) void fn();},
    async quote(index,result={seconds:90,fuel_cost:12,capacity:1000,affordable:true}) {pending[index](result);await tick();},
    hide() {visible=false;context.fleetQuoteController.cancel();},
    finishAction() {model.busy=false;actionResolve({ok:true});},
  };
}

test('real fleet DOM adapter automatically quotes, shows cost and enables its sole launch action', async () => {
  const x=setup();x.context.clearFleetPreview();assert.equal(x.send.disabled,true);
  x.flush();assert.equal(x.quotes.length,1);assert.equal(x.actions.length,0);
  await x.quote(0);assert.equal(x.send.disabled,false);
  assert.match(x.preview.innerHTML,/90s/);assert.match(x.preview.innerHTML,/12/);
  assert.equal(x.actions.length,0);
  const launch=x.context.launchFleet();const duplicate=x.context.launchFleet();
  assert.equal(x.actions.length,1);assert.equal(x.actions[0].ships.scout,1);
  assert.equal(x.actions[0].type,'fleet');assert.equal(x.send.disabled,true);
  x.finishAction();await Promise.all([launch,duplicate]);assert.equal(x.model.tab,'galaxy');
  assert.equal(x.model.galaxyMode,'map');assert.equal(x.model.galaxyId,'g2');
  assert.equal(x.model.galaxyViews.g2.scale,1);assert.equal(x.model.galaxyViews.g2.focusSystemId,'home-system');
});

test('changed real ship input disables dispatch until its newest server quote is received', async () => {
  const x=setup();x.context.clearFleetPreview();x.flush();await x.quote(0);
  x.fields['ship-scout'].value='5';x.context.clearFleetPreview();
  assert.equal(x.send.disabled,true);await x.context.launchFleet();assert.equal(x.actions.length,0);
  x.flush();assert.equal(x.quotes.at(-1).ships.scout,5);
  await x.quote(1,{seconds:45,fuel_cost:40,capacity:5000,affordable:true});
  assert.equal(x.send.disabled,false);assert.match(x.preview.innerHTML,/45s/);
});

test('exact shortfalls stay beside the disabled launch button', async () => {
  const x=setup();x.context.clearFleetPreview();x.flush();
  await x.quote(0,{seconds:90,fuel_cost:12,capacity:1000,affordable:false,shortfall:{metal:5,crystal:0,fuel:8}});
  assert.equal(x.send.disabled,true);assert.match(x.preview.innerHTML,/Metal: 5/);assert.match(x.preview.innerHTML,/Fuel: 8/);
  await x.context.launchFleet();assert.equal(x.actions.length,0);
});

test('navigation and logout cannot revive a late quote or dispatch', async () => {
  const x=setup();x.context.clearFleetPreview();x.flush();x.hide();
  x.model.token='';x.model.epoch++;await x.quote(0);
  assert.equal(x.model.fleetPreview,null);await x.context.launchFleet();assert.equal(x.actions.length,0);
});

test('attack and colony consequences appear inline before the launch click', async () => {
  const x=setup();x.fields.mission.value='attack';x.model.fleetMission='attack';x.context.clearFleetPreview();x.flush();await x.quote(0);
  assert.match(x.preview.innerHTML,/Atak na gracza kończy twoją ochronę startową/);
  x.fields.mission.value='colonize';x.model.fleetMission='colonize';x.context.clearFleetPreview();x.flush();
  await x.quote(1,{seconds:90,fuel_cost:12,capacity:1000,affordable:true,colonization_warning:'New colony can be captured'});
  assert.match(x.preview.innerHTML,/New colony can be captured/);assert.equal(x.actions.length,0);
});


test('changing a selected destination opens its galaxy map and preserves ship/cargo inputs', () => {
  const x=setup();x.fields.mission.value='transport';x.model.fleetMission='transport';x.fields['ship-scout'].value='4';x.fields['cargo-metal'].value='17';
  x.model.galaxyMode='system';x.context.changeMissionDestination();
  assert.equal(x.model.galaxyMode,'map');assert.equal(x.model.missionSelecting,true);
  assert.equal(x.model.galaxyId,'g1');assert.equal(x.model.galaxyViews.g1.focusSystemId,'system');
  assert.equal(x.model.fleetTarget,'target');assert.equal(x.model.fleetDraft.ships.scout,4);
  assert.equal(x.model.fleetDraft.cargo.metal,17);assert.equal(x.actions.length,0);
});

test('change destination without a selected planet opens the home galaxy map', () => {
  const x=setup();x.model.fleetTarget='';x.model.galaxyMode='system';
  x.context.changeMissionDestination();
  assert.equal(x.model.galaxyMode,'map');assert.equal(x.model.galaxyId,'g2');
  assert.equal(x.model.galaxyViews.g2.focusSystemId,'home-system');assert.equal(x.actions.length,0);
});
