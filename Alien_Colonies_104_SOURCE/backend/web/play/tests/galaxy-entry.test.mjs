import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {mountGalaxyMap} from '../galaxy-map.js';

const game = readFileSync(new URL('../game.js', import.meta.url), 'utf8');
function sourceBetween(start, end) { return game.slice(game.indexOf(start), game.indexOf(end)); }
function entryContext() {
  const state = {planet_id:'p2', own_planets:[{id:'p1',system_id:'s1'},{id:'p2',system_id:'s2'}],
    galaxy:[{id:'s1',galaxy_id:'g1',planets:[{id:'p1'}]},{id:'s2',galaxy_id:'g2',planets:[{id:'p2'}]}]};
  const model = {state, tab:'colony', busy:false, galaxyId:'g1', selectedSystems:{g1:'s1'},
    galaxyViews:{g1:{scale:1.7,x:33,y:-12},g2:{scale:3,x:-19,y:25}}};
  const elements = new Map();
  const context = vm.createContext({model, saveFleetDraft(){}, collectFleet:()=>null, cancelGoogleName(){}, tabs:{colony:true,galaxy:true}, closePlanetDetails(){},
    sessionStorage:{setItem(){}}, renderChrome(){}, renderMain(){}, window:{scrollTo(){}},
    emailFlow:{snapshot:()=>({phase:'closed'})}, acceptState:next=>{model.state=next;},
    $:selector=>{if(!elements.has(selector)) elements.set(selector,{});return elements.get(selector);},
    document:{body:{classList:{remove(){}}}}, t:value=>value, schedulePoll(){}});
  vm.runInContext(sourceBetween('function prepareGalaxyEntry() {','function galaxyExplorerHtml() {')
    + sourceBetween('async function switchTab(tab) {','async function loadChat(')
    + sourceBetween('function showGame(state) {','function acceptState(state) {'), context);
  return context;
}

test('each galaxy entry selects the active colony, including a colony in another galaxy', async () => {
  const context = entryContext(), {model} = context;
  await context.switchTab('galaxy');
  assert.equal(model.galaxyId,'g2');
  assert.equal(model.selectedSystems.g2,'s2');
  assert.equal(model.galaxyViews.g2.focusSystemId,'s2');
  assert.deepEqual(model.galaxyViews.g1,{scale:1.7,x:33,y:-12});
  delete model.galaxyViews.g2.focusSystemId; // The mounted map consumes this once.
  model.galaxyId='g1';
  await context.switchTab('colony');
  assert.equal(model.galaxyId,'g1');
  assert.equal(model.galaxyViews.g2.focusSystemId,undefined);
  await context.switchTab('galaxy');
  assert.equal(model.galaxyId,'g2');
  assert.equal(model.galaxyViews.g2.focusSystemId,'s2');
  model.state.planet_id='p1';
  await context.switchTab('galaxy');
  assert.equal(model.galaxyId,'g1');
  assert.equal(model.galaxyViews.g1.focusSystemId,'s1');
});

test('restored Galaxy tab focuses its active colony; other restored tabs remain unchanged', () => {
  const context=entryContext(), {model}=context;
  context.showGame(model.state);
  assert.equal(model.galaxyViews.g2.focusSystemId,undefined);
  model.tab='galaxy';
  context.showGame(model.state);
  assert.equal(model.galaxyId,'g2');
  assert.equal(model.galaxyViews.g2.focusSystemId,'s2');
});

test('missing owned-planet metadata falls back to actual planet membership, not the home planet', () => {
  const context=entryContext(), {model}=context;
  delete model.state.own_planets;
  context.prepareGalaxyEntry();
  assert.equal(model.galaxyId,'g2');
  assert.equal(model.galaxyViews.g2.focusSystemId,'s2');
  model.state.planet_id='missing';
  delete model.galaxyViews.g2.focusSystemId;
  context.prepareGalaxyEntry();
  assert.equal(model.galaxyViews.g2.focusSystemId,undefined);
});

class Element {
  constructor() {
    this.style={setProperty(){}}; this.dataset={}; this.listeners=new Map();
    this.classList={add(){},remove(){},toggle(){}};
  }
  setAttribute(){} replaceChildren(){} append(){} remove(){} before(){}
  querySelector(){return null;}
  addEventListener(type,callback){this.listeners.set(type,callback);}
  getBoundingClientRect(){return {left:0,top:0};}
  fire(type,event){this.listeners.get(type)?.(event);}
}
const systems = [30,20,10,40,5].flatMap((count,ring) => Array.from({length:count}, (_,order)=>({
  id:`r${ring}s${order}`, ring_index:ring, ring_order:order, ring_size:count,
  ring_radius:[.7,.49,.28,1,.14][ring], connections:[]})));
function mount(view, width=340, height=475) {
  const viewport=new Element(), plane=new Element(), core=new Element(), controls=new Element();
  const nodes=systems.map(system=>{const node=new Element();node.dataset.system=system.id;return node;});
  viewport.clientWidth=width;viewport.clientHeight=height;
  viewport.querySelector=()=>plane;viewport.querySelectorAll=()=>nodes;
  plane.querySelector=()=>core;
  const controlNodes=new Map();
  controls.querySelector=selector=>{if(!controlNodes.has(selector))controlNodes.set(selector,new Element());return controlNodes.get(selector);};
  let onResize;
  globalThis.ResizeObserver=class{constructor(callback){onResize=callback;}observe(){}disconnect(){}};
  globalThis.document={createElementNS:()=>new Element()};
  globalThis.window=new Element();
  const controller=mountGalaxyMap(viewport,view,controls,{systems});
  return {viewport,plane,controls,nodes,controller,resize:()=>onResize(),
    click:value=>controls.fire('click',{target:{closest:()=>({dataset:{mapZoom:value}})}})};
}

function assertCentred(map, view, id) {
  const {clientWidth:width,clientHeight:height}=map.viewport;
  const node=map.nodes.find(node=>node.dataset.system===id);
  const x=width/2+(parseFloat(node.style.left)-width/2)*view.scale+view.x;
  const y=height/2+(parseFloat(node.style.top)-height/2)*view.scale+view.y;
  assert.ok(Math.abs(x-width/2)<1e-8, `${id}: centred x ${x}`);
  assert.ok(Math.abs(y-height/2)<1e-8, `${id}: centred y ${y}`);
}

test('opening centres all five rings at maximum 6x on phone and desktop, including outermost systems', () => {
  for(const [width,height] of [[340,475],[900,600]]) for(const system of systems) {
    const view={scale:1,x:0,y:0,focusSystemId:system.id};
    const map=mount(view,width,height);
    assert.equal(view.scale,6);
    assert.equal(view.focusSystemId,undefined);
    assertCentred(map,view,system.id);
    map.controller.destroy();
  }
});

test('untouched colony remains centred through portrait-to-landscape resizing and polling remount', () => {
  const view={scale:1,x:0,y:0,focusSystemId:'r0s3'};
  let map=mount(view,340,475);
  assertCentred(map,view,'r0s3');
  map.viewport.clientWidth=900;map.viewport.clientHeight=600;map.resize();
  assert.equal(view.scale,6);
  assertCentred(map,view,'r0s3');
  map.controller.destroy();
  map=mount(view,900,600);
  assertCentred(map,view,'r0s3');
  map.viewport.clientWidth=340;map.viewport.clientHeight=475;map.resize();
  assertCentred(map,view,'r0s3');
  map.controller.destroy();
});

test('initial zero-sized layout waits for dimensions, then consumes focus exactly once', () => {
  const view={scale:1,x:0,y:0,focusSystemId:'r2s3'}, map=mount(view,0,0);
  assert.equal(view.focusSystemId,'r2s3');
  map.viewport.clientWidth=340;map.viewport.clientHeight=475;map.resize();
  assert.equal(view.scale,6);
  assert.equal(view.focusSystemId,undefined);
  map.click('reset');
  map.resize();
  assert.deepEqual(view,{scale:1,x:0,y:0});
  map.controller.destroy();
});

test('manual dragging releases the entry anchor across resize and rerender', () => {
  const view={scale:1,x:0,y:0,focusSystemId:'r2s3'};
  let map=mount(view);
  map.viewport.fire('pointerdown',{button:0,pointerType:'mouse',pointerId:1,clientX:170,clientY:200});
  assert.equal(view.anchorSystemId,'r2s3');
  map.viewport.fire('pointermove',{pointerType:'mouse',pointerId:1,clientX:200,clientY:220});
  assert.equal(view.anchorSystemId,undefined);
  const manual={...view};
  map.viewport.clientWidth=900;map.viewport.clientHeight=600;map.resize();
  assert.deepEqual(view,manual);
  map.controller.destroy();
  map=mount(view,900,600);
  assert.deepEqual(view,manual);
  map.click('reset');
  assert.deepEqual(view,{scale:1,x:0,y:0});
  map.controller.destroy();
});

test('Fit all, manual zoom/pan and rerender preserve exploration until the next entry', () => {
  const view={scale:1,x:0,y:0,focusSystemId:'r2s3'};
  let map=mount(view);
  map.click('out');
  assert.equal(view.scale,6*.8);
  view.x=25;view.y=-20;
  map.resize();
  assert.equal(view.x,25);assert.equal(view.y,-20);
  map.controller.destroy();
  map=mount(view);
  assert.deepEqual(view,{scale:6*.8,x:25,y:-20});
  map.click('reset');
  assert.deepEqual(view,{scale:1,x:0,y:0});
  map.controller.destroy();
  view.focusSystemId='r2s3';
  map=mount(view);
  assert.equal(view.scale,6);
  map.controller.destroy();
});
