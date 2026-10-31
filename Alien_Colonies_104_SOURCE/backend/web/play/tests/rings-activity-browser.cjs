/* Actual Chromium, local API fixtures only; no production account or service. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {gunzipSync}=require('node:zlib');
const path=require('node:path');
const http=require('node:http');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..');
const fixture=JSON.parse(gunzipSync(fs.readFileSync(path.join(__dirname,'fixtures/rings-navigation.json.gz'))));
const output=path.resolve(process.env.AC_WEB_QA_DIR || '/tmp/alien-colonies-web68');
fs.mkdirSync(output,{recursive:true});
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.webp':'image/webp','.svg':'image/svg+xml'};
const server=http.createServer((req,res)=>{
  const name=new URL(req.url,'http://localhost').pathname;
  const file=path.resolve(root,'.'+(name.endsWith('/')?name+'index.html':name));
  if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
  try{res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file));}
  catch{res.writeHead(404).end();}
});
const item={key:'scout',name:'Scout',count:1,cost:{},seconds:60,requirements:[]};
const galaxy=structuredClone(fixture.systems).map(system=>({...system,scout_target_id:system.id+'-unknown',system_scout_target_id:system.id==='s1'?'home':system.id+'-unknown'}));
galaxy[0].visibility='colony';galaxy[0].planets=[{id:'home',system_id:'s1',name:'Nova',owner_id:'p1',owner_type:'player',environment:{}}];
const makeState=()=>({player:{id:'p1',name:'Test Empire',race_id:'zetan',race_name:'Zetan',protected_until:0},planet_id:'home',planet_name:'Nova',planet_galaxy_id:'g1',own_planets:[{id:'home',name:'Nova',system_id:'s1'}],version:'0.12.1',server_time:Date.now()/1000,account:{},resources:{metal:1000,crystal:1000,fuel:1000},production:{metal:10,crystal:10,fuel:10},production_status:{paused:false,stops_at:Date.now()/1000+604800},limits:{colonies:10,resource_cap:1e9},fields:{free:20},energy:{supply:100,used:10,factor:1},race:{},environment:{},reports:[],queue:[],planned_orders:[],fleets:[],incoming_attacks:[],research_queue:null,catalog:{buildings:[],research:[],ships:[item],defenses:[]},buildings:{},research:{},ships:{scout:1},galaxy,galaxies:{items:[{id:'g1',name:'Andromeda',art_key:'galaxy_01'}]},communications:{}});
let browser;
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin=`http://127.0.0.1:${server.address().port}`;
  browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
  let checks=0;
  for(const [width,height,lang] of [[1280,1000,'pl'],[360,800,'pl'],[360,800,'en'],[360,800,'de'],[360,800,'es'],[360,800,'fr']]) {
    const context=await browser.newContext({viewport:{width,height},hasTouch:width<500,isMobile:width<500});
    let state=makeState(),failNext=false;
    const calls=[],errors=[];
    await context.route('**/api/**',async route=>{
      const request=route.request(),endpoint=new URL(request.url()).pathname,headers=request.headers();
      calls.push({endpoint,headers,body:request.postDataJSON()});
      if(endpoint==='/api/state'&&failNext){failNext=false;await route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({ok:false,error:'Temporary test error'})});return;}
      let result={ok:true};
      if(endpoint==='/api/state')result={ok:true,state};
      else if(endpoint==='/api/auth/google/config'||endpoint==='/api/auth/email/config')result={ok:true,configured:false};
      else if(endpoint==='/api/preview') {
        const body=request.postDataJSON();const target=body.target_system_id || body.target_id.replace('-unknown','');
        const routeData=fixture.routes.find(r=>r.origin==='s1'&&r.target===target);
        result={ok:true,seconds:120,fuel_cost:12,capacity:100,affordable:true,message:'Route checked',route:{...routeData,navigation_schema:2,intergalactic:false}};
      } else throw Error('Unexpected API '+endpoint);
      await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
    });
    const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
    await page.addInitScript(()=>{
      sessionStorage.setItem('alien-colonies.session','local-test-token');
      sessionStorage.setItem('alien-colonies.tab','galaxy');
      let offset=0;const realNow=performance.now.bind(performance);
      performance.now=()=>realNow()+offset;window.__advance=ms=>offset+=ms;
      const original=setTimeout;window.setTimeout=(fn,delay,...args)=>{if(delay===12000){window.__poll=fn;return original(fn,3600000,...args);}return original(fn,delay,...args);};
    });
    await page.goto(`${origin}/play/?lang=${lang}`);
    await page.locator('.system-node').last().waitFor();
    assert.equal(await page.locator('.system-node').count(),60);checks++;
    assert.equal(await page.locator('.map-connection.bridge:not(.route)').count(),10);checks++;
    assert.equal(await page.locator('.map-connection.orbit:not(.route)').count(),60);checks++;
    assert.equal(calls.find(c=>c.endpoint==='/api/state').headers['x-ac-player-active'],'1');checks++;
    assert.equal(await page.locator('#system-detail [data-system-scout="s1"]').count(),1);checks++;
    await page.evaluate(async()=>{window.__advance(70000);await window.__poll();});
    assert.equal(calls.filter(c=>c.endpoint==='/api/state').at(-1).headers['x-ac-player-active'],undefined);checks++;
    // Programmatic page events cannot manufacture activity.
    await page.evaluate(async()=>{document.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId:91}));window.dispatchEvent(new PointerEvent('pointerup',{pointerId:91}));window.__advance(70000);await window.__poll();});
    assert.equal(calls.filter(c=>c.endpoint==='/api/state').at(-1).headers['x-ac-player-active'],undefined);checks++;
    const inner=fixture.systems.find(s=>s.ring_index===2).id;
    await page.locator(`[data-system="${inner}"]`).click();
    assert.equal(await page.locator(`[data-system="${inner}"]`).getAttribute('aria-pressed'),'true');checks++;
    assert.equal(await page.locator('.map-connection.route').count(),fixture.routes.find(r=>r.origin==='s1'&&r.target===inner).segments.length);checks++;
    await page.locator('#map-controls [data-map-zoom="in"]').click();
    assert.equal(await page.locator('[data-map-scale]').textContent(),'125%');checks++;
    // Zoomed systems retain a 44px tap area; map lines cannot intercept input.
    const hit=await page.locator(`[data-system="${inner}"]`).boundingBox();assert.ok(hit.width>=43);checks++;
    await page.locator(`[data-system="${inner}"]`).click();
    await page.locator('#galaxy-explorer').screenshot({path:path.join(output,`galaxy-${width}-${lang}.png`)});
    await page.evaluate(async()=>{await window.__poll();});
    assert.equal(calls.filter(c=>c.endpoint==='/api/state').at(-1).headers['x-ac-player-active'],'1');checks++;
    await page.locator(`#system-detail [data-target="${inner}-unknown"]`).click();
    await page.locator('#fleet-form button[type="submit"]').click();
    await page.locator('.fleet-network-route').waitFor();
    const expected=fixture.routes.find(r=>r.origin==='s1'&&r.target===inner);
    const request=calls.filter(c=>c.endpoint==='/api/preview').at(-1);
    assert.equal(request.body.scout_scope,'system');assert.equal(request.body.target_system_id,inner);checks+=2;
    assert.equal(request.headers['x-ac-player-active'],undefined);checks++;
    assert.equal(await page.locator('.fleet-network-route li').count(),expected.system_ids.length);checks++;
    await page.locator('#fleet-preview').screenshot({path:path.join(output,`route-${width}-${lang}.png`)});
    await page.locator('[data-close-fleet]').click();
    if(width===1280) {
      // Failed state synchronization must preserve dirty input for the next attempt.
      await page.evaluate(()=>window.__advance(70000));
      await page.locator('[data-system="s2"]').click();failNext=true;
      await page.evaluate(async()=>{await window.__poll();});
      assert.equal(calls.filter(c=>c.endpoint==='/api/state').at(-1).headers['x-ac-player-active'],'1');checks++;
      await page.evaluate(async()=>{window.__advance(70000);await window.__poll();});
      assert.equal(calls.filter(c=>c.endpoint==='/api/state').at(-1).headers['x-ac-player-active'],'1');checks++;
      const before=calls.length;
      await page.evaluate(async()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));window.__advance(70000);await window.__poll();});
      assert.equal(calls.length,before);checks++;
      await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));});
      await page.waitForFunction(()=>document.querySelector('#connection-status').textContent.includes('Połączono'));
      assert.equal(calls.filter(c=>c.endpoint==='/api/state').at(-1).headers['x-ac-player-active'],'1');checks++;
      // An idle snapshot can show the pause without any local resource growth.
      state.production={metal:0,crystal:0,fuel:0};state.production_status={paused:true,stops_at:1};
      await page.evaluate(async()=>{window.__advance(70000);await window.__poll();});
      await page.locator('#production-status').waitFor({state:'visible'});
      assert.equal(await page.locator('.resource-rate.warning').count(),3);checks++;
      await page.locator('#production-status').screenshot({path:path.join(output,'production-paused-pl.png')});
    }
    assert.deepEqual(errors,[]);checks++;
    await context.close();
  }
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify({ok:true,checks,languages:5,viewports:[[1280,1000],[360,800]],serverRoutes:fixture.routes.length},null,2));
  console.log(JSON.stringify({ok:true,checks,output}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();server.close();});
