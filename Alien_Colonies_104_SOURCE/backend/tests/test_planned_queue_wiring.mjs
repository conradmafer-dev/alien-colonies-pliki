// Executes the actual game.js handlers with a minimal DOM and synthetic API.
// This verifies wiring/focus/state preservation; it does not emulate layout or native keyboard behavior.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const own={id:'s1p1',name:'Home',system_id:'s1',galaxy_id:'g1',owner_id:'p1',owner_type:'player',visibility:'own',environment:{type:'ocean',type_name:'Oceaniczna',fields:88,planet_art:'worlds/planet_ocean'}};
const second={...own,id:'s2p1',name:'Second colony',system_id:'s2'};
const enemy={id:'s1p2',name:'Nest '+'A'.repeat(180),system_id:'s1',galaxy_id:'g1',owner_id:'khar',owner_type:'alien',owner_name:'Rój Khar',visibility:'scouted',has_scout:true,environment:{type:'ice',type_name:'Lodowa'},planet_scout:{id:'s1p2',scouted_at:900,resources:{metal:987654},ships_display:[{key:'frigate',name:'Nowa migawka',count:99}]}};
const empty={id:'s1p3',name:'Free',system_id:'s1',galaxy_id:'g1',owner_id:'',owner_type:'empty',visibility:'observed',environment:{type:'jungle',type_name:'Organiczna'}};
function state(planetId='s1p1') {
  const selected=planetId==='s2p1'?second:own;
  return {version:'0.11.3',server_time:1000,player:{id:'p1',name:'Fixture empire',race_id:'zetan',race_name:'Zetan',swarm_crystals:0},planet_id:selected.id,planet_name:selected.name,planet_galaxy_id:'g1',own_planets:[own,second],race:{},environment:selected.environment,resources:{metal:100000,crystal:10000,fuel:10000},production:{metal:10,crystal:10,fuel:10},ships:{scout:3,colonizer:1},defenses:{},energy:{supply:500,used:100,factor:1},fields:{total:88,used:4,free:84},buildings:{},catalog:{buildings:[],research:[],defenses:[],ships:[{key:'scout',name:'Zwiadowca',art_key:'ships/scout'},{key:'colonizer',name:'Kolonizator',art_key:'ships/colonizer'}]},galaxies:{items:[{id:'g1',name:'Fixture galaxy'}]},galaxy:[{id:'s1',name:'Alpha',galaxy_id:'g1',x:30,y:30,visibility:'scouted',scouted_at:950,planets:[own,enemy,empty]},{id:'s2',name:'Beta',galaxy_id:'g1',x:70,y:60,visibility:'colony',planets:[second]}],reports:[{id:'battle',at:990,title:'Raport bitwy',text:'Nowsza bitwa'},{id:'scout',at:800,title:'Zwiad historyczny',text:'Prawdziwy raport zwiadu',planet_scout:{id:'s1p2',scouted_at:800,owner_id:'khar',owner_type:'alien',resources:{metal:12345,crystal:1234,fuel:0},ships_display:[{key:'frigate',name:'Historyczna fregata',count:7}],defenses_display:[],observed_buildings:[{key:'shipyard',name:'Historyczna stocznia',level:2}]},scout:{id:'s1p2',scouted_at:800,swarm_crystals_stock:3,swarm_crystals_capacity:6,swarm_units:[{key:'frigate',name:'Historyczna fregata',count:7}],swarm_defenses:[],swarm_activity:'Rozbudowuje flotę'}}],fleets:[],limits:{colonies:8,resource_cap:1000000},communications:{unread:0},onboarding:{},alliance:{},race_choice_allowed:false};
}

const makeState=state;
const repo=new URL('../web/play/',import.meta.url);
const decode=value=>String(value).replace(/&(?:amp|lt|gt|quot|#39);/g,x=>({'&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&#39;':"'"}[x]));
let document;
class Element {
 constructor(tag,attrs={}) {this.tagName=tag.toUpperCase();this.attrs=attrs;this.children=[];this.parentElement=null;this.listeners=new Map();this.dataset={};this.style={setProperty(name,value){this[name]=value;}};this.scrollTop=0;this.clientWidth=680;this.clientHeight=500;this.scrollWidth=680;this.hidden=Object.hasOwn(attrs,'hidden');this.disabled=Object.hasOwn(attrs,'disabled');this.open=false;this._value=attrs.value;this._html='';this._text='';this.syncDataset();
  this.classList={contains:name=>this.className.split(/\s+/).includes(name),add:(...names)=>this.setAttribute('class',[...new Set([...this.className.split(/\s+/).filter(Boolean),...names])].join(' ')),remove:(...names)=>this.setAttribute('class',this.className.split(/\s+/).filter(name=>!names.includes(name)).join(' ')),toggle:(name,force)=>{const on=force??!this.classList.contains(name);on?this.classList.add(name):this.classList.remove(name);return on;}};
 }
 get className(){return this.attrs.class||'';}
 get id(){return this.attrs.id||'';}
 get isConnected(){let node=this;while(node.parentElement)node=node.parentElement;return node===document;}
 syncDataset(){for(const [key,value]of Object.entries(this.attrs))if(key.startsWith('data-'))this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=value;}
 setAttribute(name,value){this.attrs[name]=String(value);this.syncDataset();}
 getAttribute(name){return this.attrs[name]??null;}
 hasAttribute(name){return Object.hasOwn(this.attrs,name);}
 get innerHTML(){return this._html;}
 set innerHTML(value){if(document?.activeElement&&this.contains(document.activeElement))document.activeElement=document.body;for(const child of this.children)child.parentElement=null;this.children=[];this._text='';this._html=String(value);parse(String(value),this);}
 get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
 set textContent(value){this.children=[];this._text=String(value);this._html=String(value);}
 get options(){return this.querySelectorAll('option');}
 get text(){return this.textContent;}
 get value(){if(this._value!==undefined)return this._value;return this.tagName==='SELECT'?(this.options.find(option=>option.hasAttribute('selected'))||this.options[0])?.value||'':this.attrs.value||'';}
 set value(value){this._value=String(value);}
 matches(selector){return matches(this,selector);}
 closest(selector){let node=this;while(node){if(matches(node,selector))return node;node=node.parentElement;}return null;}
 contains(node){return node===this||this.children.some(child=>child.contains(node));}
 querySelectorAll(selector){const found=[];const visit=node=>{for(const child of node.children){if(matches(child,selector))found.push(child);visit(child);}};visit(this);return found;}
 querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
 addEventListener(type,handler){if(!this.listeners.has(type))this.listeners.set(type,[]);this.listeners.get(type).push(handler);}
 removeEventListener(type,handler){this.listeners.set(type,(this.listeners.get(type)||[]).filter(item=>item!==handler));}
 async dispatch(type,event={}) {event={target:this,currentTarget:this,preventDefault(){this.defaultPrevented=true;},...event};for(const handler of this.listeners.get(type)||[])await handler(event);return event;}
 focus(){document.activeElement=this;}
 showModal(){this.open=true;}
 close(){this.open=false;}
 scrollIntoView(){}
 getBoundingClientRect(){return {left:300,right:980,top:100,bottom:600,width:680,height:500};}
 setPointerCapture(){}
 releasePointerCapture(){}
 hasPointerCapture(){return false;}
}
function matches(node,selector) {
 if(selector.includes(','))return selector.split(',').some(part=>matches(node,part.trim()));
 const pieces=selector.trim().split(/\s+(?![^\[]*\])/);
 if(pieces.length>1){if(!matches(node,pieces.pop()))return false;let ancestor=node.parentElement;for(let i=pieces.length-1;i>=0;i--){while(ancestor&&!matches(ancestor,pieces[i]))ancestor=ancestor.parentElement;if(!ancestor)return false;ancestor=ancestor.parentElement;}return true;}
 const id=selector.match(/#([\w-]+)/)?.[1];if(id&&node.id!==id)return false;
 const tag=selector.match(/^[\w-]+/)?.[0];if(tag&&node.tagName!==tag.toUpperCase())return false;
 for(const [,name]of selector.matchAll(/\.([\w-]+)/g))if(!node.classList.contains(name))return false;
 for(const [,name,,value]of selector.matchAll(/\[([\w-]+)(?:=(['"]?)([^\]'"]*)\2)?\]/g)){if(!node.hasAttribute(name)||value!==undefined&&node.getAttribute(name)!==value)return false;}
 return true;
}
function parse(html,parent) {
 const stack=[parent], voids=new Set(['AREA','BASE','BR','COL','EMBED','HR','IMG','INPUT','LINK','META','PARAM','SOURCE','TRACK','WBR']);
 for(const token of html.match(/<!--[^]*?-->|<[^>]*>|[^<]+/g)||[]){
  if(token.startsWith('<!--')||token.startsWith('<!'))continue;
  if(token.startsWith('</')){const tag=token.match(/^<\/([\w-]+)/)?.[1]?.toUpperCase();for(let i=stack.length-1;i>0;i--)if(stack[i].tagName===tag){stack.splice(i);break;}continue;}
  if(token.startsWith('<')){const tag=token.match(/^<([\w-]+)/)?.[1];if(!tag)continue;const attrs={};const rest=token.slice(tag.length+1,-1).replace(/\/$/,'');for(const [,name,,value,single,bare]of rest.matchAll(/([^\s=]+)(?:\s*=\s*("([^"]*)"|'([^']*)'|([^\s]+)))?/g))attrs[name]=decode(value??single??bare??'');const el=new Element(tag,attrs);el.parentElement=stack.at(-1);el.parentElement.children.push(el);if(!voids.has(el.tagName)&&!token.endsWith('/>'))stack.push(el);continue;}
  stack.at(-1)._text+=decode(token);
 }
}
function store(initial={}) {const values=new Map(Object.entries(initial));return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,String(value)),removeItem:key=>values.delete(key)};}

// Cache i18n before DOM setup, keeping authored Polish text deterministic in Node.
await import(new URL('i18n.js?v=0111',repo));
document=new Element('document');
parse(fs.readFileSync(new URL('index.html',repo),'utf8'),document);
document.documentElement=document.querySelector('html');document.body=document.querySelector('body');document.activeElement=document.body;document.hidden=false;
globalThis.document=document;globalThis.HTMLImageElement=Element;
const imports={};let source=fs.readFileSync(new URL('game.js',repo),'utf8');
for(const [,names,relative]of source.matchAll(/import\s*\{([^}]+)\}\s*from\s*['"]([^'"]+)['"];?/g)) {const imported=await import(new URL(relative,repo));for(const name of names.split(',').map(name=>name.trim()))imports[name]=imported[name];}
source=source.replace(/import\s*\{[^}]+\}\s*from\s*['"][^'"]+['"];?/g,'');
let clock=0, sequence=0, observedState=makeState(), calls=0; const actions=[];
const timers=new Map(), intervals=[], win=new Element('window');win.scrollTo=()=>{};
const sandbox={...imports,crypto:globalThis.crypto,document,window:win,console,URL,URLSearchParams,AbortController,performance:{now:()=>clock},setTimeout:(fn,ms)=>{const id=++sequence;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id),setInterval:(fn,ms)=>{intervals.push({fn,ms});return intervals.length;},clearInterval(){},requestAnimationFrame:()=>0,cancelAnimationFrame(){},ResizeObserver:class {constructor(fn){this.fn=fn;}observe(){this.fn([{contentRect:{height:90}}]);}disconnect(){}},CSS:{escape:value=>value},HTMLImageElement:Element,location:{origin:'http://fixture.test',search:'?lang=pl'},sessionStorage:store({'alien-colonies.session':'fixture-token','alien-colonies.tab':'galaxy'}),localStorage:store(),fetch:async (requested,options={})=>{const url=new URL(requested,'http://fixture.test');if(url.pathname==='/site-config')return {ok:true,json:async()=>({development:true})};if(url.pathname==='/api/action'){const body=JSON.parse(options.body);actions.push(body);if(body.type==='plan_project')observedState.planned_orders.push({id:'new-plan',kind:body.kind,key:body.key,amount:body.amount,planet_id:body.planet_id,name:'Zwiadowca',planet_name:'Home',reason:'Czeka na zasoby.'});return {ok:true,status:200,json:async()=>({ok:true,state:structuredClone(observedState),message:'OK'})};}assert.equal(url.pathname,'/api/state');calls++;const next=structuredClone(observedState);const id=url.searchParams.get('planet_id');if(id){next.planet_id=id;next.planet_name=next.own_planets.find(p=>p.id===id)?.name||next.planet_name;}return {ok:true,status:200,json:async()=>({ok:true,state:next})};}};
const context=vm.createContext(sandbox);
globalThis.ResizeObserver=sandbox.ResizeObserver;globalThis.window=win;globalThis.requestAnimationFrame=sandbox.requestAnimationFrame;globalThis.cancelAnimationFrame=sandbox.cancelAnimationFrame;
await vm.runInContext(`(async()=>{${source}\nglobalThis.testGame={model,loadState,renderMain,renderPlanetDetails};})()`,context,{filename:'actual-game.js'});
const game=context.testGame, q=selector=>document.querySelector(selector);
const click=async target=>{assert.ok(target,'click target exists');await document.dispatch('click',{target});};
assert.equal(q('#game-screen').hidden,false,q('#auth-error').textContent);
const inspect=q('[data-inspect-planet="s1p2"]');assert.ok(inspect);assert.equal(inspect.tagName,'BUTTON');
await click(inspect.querySelector('strong'));
assert.equal(q('#planet-dialog').open,true);assert.match(q('#planet-detail-content').textContent,/Prawdziwy raport zwiadu/);assert.doesNotMatch(q('#planet-detail-content').textContent,/Nowa migawka/);
await q('#planet-dialog').dispatch('cancel');assert.equal(q('#planet-dialog').open,false);assert.equal(document.activeElement,inspect);
await click(inspect);await click(q('#planet-dialog [data-target="s1p2"]'));
assert.equal(q('#planet-dialog').open,false);assert.equal(q('#fleet-mission').value,'scout');
const ships=q('#fleet-scout'), cargo=q('#cargo-metal');assert.ok(ships);ships.value='2';cargo.value='42';
await click(q('[data-inspect-planet="s1p3"] .planet-thumb'));assert.equal(q('#planet-dialog').open,true);assert.match(q('#planet-detail-content').textContent,/Wolna planeta/);
await click(q('[data-close-planet-info]'));assert.equal(ships.value,'2');assert.equal(cargo.value,'42');
await click(q('[data-inspect-planet="s1p2"]'));q('#planet-dialog [data-target="s1p2"]').focus();
observedState.reports[1].text='Changed historical report';
await game.loadState({quiet:true});
assert.equal(q('#planet-dialog').open,true);assert.match(q('#planet-detail-content').textContent,/Changed historical report/);assert.equal(document.activeElement.dataset.target,'s1p2');assert.equal(q('#fleet-scout'),ships);assert.equal(ships.value,'2');assert.equal(cargo.value,'42');
observedState.reports[1].text='Deferred update';await document.dispatch('pointerdown',{pointerId:4});await game.loadState({quiet:true});assert.doesNotMatch(q('#planet-detail-content').textContent,/Deferred update/);await win.dispatch('pointerup',{pointerId:4});clock=1000;intervals.find(timer=>timer.ms===1000).fn();
assert.match(q('#planet-detail-content').textContent,/Deferred update/);assert.equal(document.activeElement.dataset.target,'s1p2');assert.equal(q('#fleet-scout'),ships);
await q('#planet-dialog').dispatch('click',{clientX:1,clientY:1});assert.equal(q('#planet-dialog').open,false);
await click(q('[data-system="s2"]'));await click(q('[data-inspect-planet="s2p1"]'));await click(q('#planet-dialog [data-planet="s2p1"]'));
assert.equal(game.model.state.planet_id,'s2p1');assert.equal(game.model.tab,'colony');assert.equal(q('#planet-dialog').open,false);
console.log(JSON.stringify({ok:true,checks:['actual game.js boot','name and thumbnail click wiring','cancel and backdrop','mission composer','own colony switch','quiet poll focus and fleet input preservation','deferred poll update'],stateCalls:calls}));

// Actual premium controls and action handlers with authoritative synthetic state.
observedState=makeState();
observedState.premium={queue_planning_active:true,expires_at:1800000000};
observedState.limits.queue_waiting=10;
observedState.planned_orders=[];
observedState.catalog.ships=[{key:'scout',name:'Zwiadowca',count:3,attack:2,hull:15,capacity:10,speed:1,fuel:1,cost:{metal:100,crystal:100,fuel:30},seconds:60,enabled:false,planning_enabled:true,reason:'Stocznia produkuje już statki lub obronę.',requirements:[]}];
observedState.catalog.buildings=[{key:'metal_mine',name:'Kopalnia metalu',level:1,max_level:12,cost:{metal:300,crystal:100,fuel:0},seconds:180,enabled:false,planning_enabled:true,reason:'Na tej planecie trwa już budowa.',requirements:[],details:{metrics:[]}}];
await game.loadState({planetId:'s1p1'});
await click(q('[data-tab="ships"]'));
assert.equal(q('[data-project="scout"]').disabled,true);
const plan=q('[data-plan-project="scout"]');assert.equal(plan.disabled,false);
const batch=q('[data-batch="scout"]');batch.value='17';batch.reportValidity=()=>true;
batch.focus();
observedState.planned_orders.push({id:'existing-plan',kind:'ship',key:'scout',amount:2,planet_id:'s1p1',name:'Zwiadowca',planet_name:'Home',reason:'Czeka na zasoby.'});
await game.loadState({quiet:true});
assert.equal(q('[data-batch="scout"]'),batch);assert.equal(batch.value,'17');
await click(plan);
assert.equal(actions.at(-1).type,'plan_project');assert.equal(actions.at(-1).kind,'ship');assert.equal(actions.at(-1).amount,17);
assert.ok(q('[data-remove-planned="new-plan"]'));
await click(q('[data-planned-up="new-plan"]'));
assert.equal(actions.at(-1).type,'reorder_planned_project');assert.equal(actions.at(-1).before_order_id,'existing-plan');
await click(q('[data-queue-subscription]'));assert.equal(q('#queue-subscription-dialog').open,true);assert.match(q('#queue-subscription-content').textContent,/Androidzie/);
await click(q('[data-close-queue-subscription]'));assert.equal(q('#queue-subscription-dialog').open,false);
await click(q('[data-tab="buildings"]'));
assert.equal(q('[data-project="metal_mine"]').disabled,true);assert.equal(q('[data-plan-project="metal_mine"]').disabled,false);
await click(q('[data-building="metal_mine"]'));assert.equal(q('#building-dialog').open,true);assert.equal(q('#building-dialog [data-plan-project="metal_mine"]').disabled,false);
await click(q('[data-close-building]'));
observedState.premium.queue_planning_active=false;await game.loadState();
assert.equal(q('[data-plan-project="metal_mine"]').disabled,true);
await click(q('[data-tab="ships"]'));assert.ok(q('[data-remove-planned="new-plan"]'));assert.equal(q('[data-planned-up="new-plan"]').disabled,true);
const pendingRemoval=click(q('[data-remove-planned="new-plan"]'));assert.equal(q('#confirm-dialog').open,true);q('#confirm-dialog').returnValue='confirm';await q('#confirm-dialog').dispatch('close');await pendingRemoval;assert.equal(actions.at(-1).type,'remove_planned_project');
console.log(JSON.stringify({ok:true,premiumChecks:['actual premium ship action including batch17','manual busy remains disabled','queue controls enabled only with authoritative eligibility','shared planned orders and reorder','Android-only offer modal','building card and dialog controls','expired plans visible and removable','quiet batch input preservation'],actionCalls:actions.length}));
