import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fleetMapColor,FLEET_MAP_COLORS} from '../fleet-motion.js';
import {mountFleetOverlay} from '../fleet-map-overlay.js';

const colors={scout:'#91a8c8',transport:'#e4c17a',colonize:'#9be4ad',attack:'#ff9295',alliance_attack:'#ff9295',alliance_defense:'#bcabff'};

test('outbound arrows use legend colors and returning fleets use the return color',()=>{
  assert.deepEqual({...FLEET_MAP_COLORS},{...colors,returning:'#b6bdc8',expedition:'#d7a6ff'});
  for(const [mission,color] of Object.entries(colors)) {
    for(const art_key of ['races/zetans/scout','races/symbionts/scout','swarm/scout']) {
      assert.equal(fleetMapColor({mission,art_key,status:'outbound'}),color);
      assert.equal(fleetMapColor({mission,art_key,status:'holding'}),color);
      assert.equal(fleetMapColor({mission,art_key,status:'returning'}),'#b6bdc8');
    }
  }
});

test('canvas really paints the arrow and the route with the same semantic color',()=>{
  const previous={document:globalThis.document,raf:globalThis.requestAnimationFrame,caf:globalThis.cancelAnimationFrame,dpr:globalThis.devicePixelRatio};
  try {
    globalThis.requestAnimationFrame=()=>1;
    globalThis.cancelAnimationFrame=()=>{};
    globalThis.devicePixelRatio=1;
    const paints=[];
    const context=new Proxy({}, {get(target,key) {
      if(key==='fill')return ()=>paints.push(['fill',target.fillStyle]);
      if(key==='stroke')return ()=>paints.push(['stroke',target.strokeStyle]);
      return key in target ? target[key] : ()=>{};
    }});
    const canvas={getContext:()=>context,setAttribute(){},remove(){},style:{}};
    globalThis.document={createElement:()=>canvas};
    const viewport={append(){},isConnected:true};
    const systems=[{id:'s1'},{id:'s2'}];
    const positions=()=>new Map([['s1',{x:100,y:100}],['s2',{x:400,y:200}]]);
    for(const [mission,color] of Object.entries(colors)) {
      for(const status of ['outbound','returning']) {
        paints.length=0;
        const fleet={mission,status,started_at:1000,arrives_at:1100,seconds:100,origin_system_id:'s1',target_system_id:'s2',route:{segments:[{from_system_id:'s1',to_system_id:'s2',kind:'corridor',distance:1}]}};
        const overlay=mountFleetOverlay(viewport,{systems,positions,now:()=>1050,fleets:[fleet]});
        overlay.layout(720,640,{scale:1,x:0,y:0});
        const expected=status==='returning'?'#b6bdc8':color;
        assert.ok(paints.some(([kind,tint])=>kind==='stroke'&&tint===expected),mission+' route');
        assert.ok(paints.some(([kind,tint])=>kind==='fill'&&tint===expected),mission+' moving arrow');
        overlay.destroy();
      }
    }
  } finally {
    globalThis.document=previous.document;
    globalThis.requestAnimationFrame=previous.raf;
    globalThis.cancelAnimationFrame=previous.caf;
    globalThis.devicePixelRatio=previous.dpr;
  }
});

test('the visible legend takes all five swatches from the map color function',()=>{
  const source=readFileSync(new URL('../game.js',import.meta.url),'utf8');
  for(const mission of ['scout','transport','colonize','attack'])assert.ok(source.includes("fleetMapColor({mission:'"+mission+"'})"));
  assert.ok(source.includes("fleetMapColor({status:'returning'})"));
});
