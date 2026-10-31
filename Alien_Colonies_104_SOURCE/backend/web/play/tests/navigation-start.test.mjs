import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const game = readFileSync(new URL('../game.js', import.meta.url), 'utf8');
const section = (start, end) => game.slice(game.indexOf(start), game.indexOf(end));
const tabNames = ['colony','buildings','research','megastructures','ships','fleets','defenses','galaxy','skills','reports','chat','alliance','settings'];
function setup() {
  const model = {
    state:{planet_id:'p2',own_planets:[{id:'p2',system_id:'s2'}],galaxy:[{id:'s2',galaxy_id:'g2',planets:[{id:'p2'}]}]},
    busy:false,tab:'ships',researchView:{left:555,top:90},
    catalogViews:{p2:{ships:{left:640,anchor:'cruiser',offset:20,batches:{scout:'7'},scrollTops:{scout:210}},buildings:{left:960,anchor:'lab',offset:0}},p1:{ships:{left:320,batches:{scout:'2'}}}},
    fleetTarget:'far-planet',fleetSystemId:'far-system',fleetMission:'attack',fleetTravelMode:'tunnel',fleetPreview:{quote:true},
    galaxyId:'g1',selectedSystems:{g1:'s1'},galaxyViews:{g1:{scale:3,x:10,y:10},g2:{scale:1.2,x:20,y:30}},
  };
  const main = {scrollTop:430};
  const calls = [], context = vm.createContext({saveFleetDraft(){},collectFleet:()=>null,$:selector=>selector==='#main'?main:null,model,tabs:Object.fromEntries(tabNames.map(tab=>[tab,true])),
    galaxyMapController:null,researchTreeController:null,catalogCarouselController:null,
    sessionStorage:{setItem(key,value){calls.push(['store',key,value]);}},
    window:{scrollTo(options){calls.push(['scroll',options.top,options.left]);}},
    closeBuildingDetails(value){calls.push(['close-building',value]);},
    closeResearchDetails(value){calls.push(['close-research',value]);},
    closeReportDetails(value){calls.push(['close-report',value]);},
    closePlanetDetails(value){calls.push(['close-planet',value]);},
    renderChrome(){},loadChat:async()=>{},loadAlliance:async()=>{},
    renderMain(){context.destroyMainView();calls.push(['render',model.tab,JSON.parse(JSON.stringify(model))]);},
    document:{addEventListener(type,callback){if(type==='click') context.click=callback;}},
  });
  vm.runInContext(section('function destroyMainView() {','function renderMain() {')
    +section('async function openNavigationTab(tab) {','async function loadChat(')
    +section('function prepareGalaxyEntry() {','function galaxyExplorerHtml() {')
    +section("document.addEventListener('click', async (event) => {","$('#main').addEventListener('change'"),context);
  const click = (tab, navigation=true) => {
    const target={dataset:{tab},hasAttribute:()=>false,closest:selector=>selector==='#game-nav'&&navigation?{}:null};
    return context.click({target:{closest:selector=>selector==='button'?target:null}});
  };
  return {context,model,calls,click,main};
}

test('each main navigation item resets the page even when it is already active', async () => {
  for (const tab of tabNames) {
    const {model,calls,click,main}=setup();
    model.tab=tab;
    await click(tab);
    assert.equal(model.tab,tab);
    assert.equal(main.scrollTop,0,`${tab}: viewport starts at the top`);
    assert.equal(calls.filter(call=>call[0]==='render').length,1,tab);
    assert.deepEqual(calls.at(-1),['scroll',0,0],`${tab}: page starts at the top`);
    assert.ok(calls.some(call=>call[0]==='close-research'&&call[1]===false));
  }
});

test('ship navigation resets the saved anchor after cleanup and keeps latest amounts and other colony views', async () => {
  const {context,model,calls,click}=setup();
  context.catalogCarouselController={destroy(){
    calls.push(['destroy-carousel']);
    Object.assign(model.catalogViews.p2.ships,{left:1000,anchor:'titan',offset:40,batches:{scout:'9',cargo:'3'},scrollTops:{scout:230}});
  }};
  await click('ships');
  assert.equal(calls.filter(call=>call[0]==='destroy-carousel').length,1);
  assert.deepEqual(model.catalogViews.p2.ships,{left:0,batches:{scout:'9',cargo:'3'}});
  assert.deepEqual(model.catalogViews.p2.buildings,{left:960,anchor:'lab',offset:0});
  assert.deepEqual(model.catalogViews.p1.ships,{left:320,batches:{scout:'2'}});
  const rendered=calls.find(call=>call[0]==='render')[2];
  assert.deepEqual(rendered.catalogViews.p2.ships,{left:0,batches:{scout:'9',cargo:'3'}});
  await click('buildings');
  assert.deepEqual(model.catalogViews.p2.buildings,{left:0});
});

test('research navigation clears both scroll axes after the old tree saves its position', async () => {
  const {context,model,calls,click}=setup();
  context.researchTreeController={destroy(){model.researchView={left:980,top:140};}};
  await click('research');
  assert.equal(Number(model.researchView.left)||0,0);
  assert.equal(Number(model.researchView.top)||0,0);
  const rendered=calls.find(call=>call[0]==='render')[2];
  assert.deepEqual(rendered.researchView,{});
});

test('galaxy navigation returns to active colony and closes the previous expedition subview', async () => {
  const {model,click}=setup();
  await click('galaxy');
  assert.equal(model.galaxyId,'g2');
  assert.equal(model.selectedSystems.g2,'s2');
  assert.equal(model.galaxyViews.g2.focusSystemId,'s2');
  assert.deepEqual(model.galaxyViews.g1,{scale:3,x:10,y:10});
  assert.equal(model.fleetTarget,'');
  assert.equal(model.fleetSystemId,'');
  assert.equal(model.fleetMission,'scout');
  assert.equal(model.fleetTravelMode,'normal');
  assert.equal(model.fleetPreview,null);
});

test('content links and ordinary rerenders preserve saved research and catalog positions', async () => {
  const {context,model,calls,click}=setup();
  await click('research',false);
  assert.deepEqual(model.researchView,{left:555,top:90});
  await click('ships',false);
  assert.deepEqual(model.catalogViews.p2.ships,{left:640,anchor:'cruiser',offset:20,batches:{scout:'7'},scrollTops:{scout:210}});
  context.renderMain();
  assert.deepEqual(model.researchView,{left:555,top:90});
  assert.equal(calls.some(call=>call[0]==='close-research'),false);
});

test('busy, signed-out and invalid navigation requests do not clear user state', async () => {
  const {context,model,calls}=setup();
  model.busy=true;await context.openNavigationTab('ships');
  model.busy=false;await context.openNavigationTab('missing');
  model.state=null;await context.openNavigationTab('research');
  assert.equal(calls.length,0);
  assert.equal(model.catalogViews.p2.ships.left,640);
  assert.equal(model.researchView.left,555);
});
