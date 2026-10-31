/* Chromium regression: isolated local world and intercepted API; public artwork only. */
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), http=require('node:http');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..'), out=path.resolve(process.env.AC_WEB_QA_DIR || '/tmp/alien-colonies-compact-ui');
fs.mkdirSync(out,{recursive:true});
const {spawnSync}=require('node:child_process');
const fixtureRun=spawnSync('python',['-c',`
import app,tempfile,time,json,pathlib,sys
from i18n import language_scope
out=pathlib.Path(sys.argv[1])
with tempfile.TemporaryDirectory() as tmp:
 w=app.World(str(pathlib.Path(tmp)/'ui.sqlite3'),1,now=time.time())
 a=w.register('CompactUITest','LocalTestPass-0126')
 pid=a['state']['player']['id'];home=a['state']['planet_id']
 w.action(pid,{'type':'choose_race','race_id':'zetans','planet_id':home})
 p=w.data['planets'][home];p['ships']['scout']=7;p['ships']['cargo']=5;p['buildings']['observatory']=12
 for lang in ['en','pl','de','es','fr']:
  with language_scope(lang):state=w.state(pid,home)
  (out/f'fixture-{lang}.json').write_text(json.dumps(state,ensure_ascii=False))
 w.close()
`,out],{cwd:path.dirname(root),encoding:'utf8'});
assert.equal(fixtureRun.status,0,fixtureRun.stderr);
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.webp':'image/webp'};
const assetCache=new Map();
const server=http.createServer(async(req,res)=>{
 const name=new URL(req.url,'http://localhost').pathname;
 let file=path.resolve(root,'.'+(name.endsWith('/')?name+'index.html':name));
 if(!file.startsWith(root+'/')){res.writeHead(403).end();return;}
 if(fs.existsSync(file)){res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file));return;}
 if(name.startsWith('/assets/')){
  try {if(!assetCache.has(name))assetCache.set(name,fetch('https://aliencolonies.com'+name).then(async r=>({status:r.status,type:r.headers.get('content-type'),bytes:Buffer.from(await r.arrayBuffer())})));const a=await assetCache.get(name);res.writeHead(a.status,{'Content-Type':a.type||'image/webp'}).end(a.bytes);return;}catch{}
 }
 res.writeHead(404).end();
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{}),args:['--no-sandbox']});
 let checks=0;const results=[];
 try{
  for(const [width,height,lang] of [[390,844,'en'],[360,740,'pl'],[1280,900,'en'],[844,390,'de']]){
   const calls=[]; const state=JSON.parse(fs.readFileSync(path.join(out,`fixture-${lang}.json`)));
   const ctx=await browser.newContext({viewport:{width,height},hasTouch:width<900,isMobile:width<900});
   await ctx.route('**/api/**',async route=>{const name=new URL(route.request().url()).pathname;calls.push({path:name,body:route.request().postDataJSON()});let result={ok:true,configured:false};if(name==='/api/action')result={ok:true,state};if(name==='/api/state')result={ok:true,state};await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});});
   const page=await ctx.newPage(), errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(()=>{sessionStorage.setItem('alien-colonies.session','local-ui-test');sessionStorage.setItem('alien-colonies.tab','colony');});
   await page.goto(`${origin}/play/?lang=${lang}`);await page.locator('[data-catalog-card="dyson"]').waitFor();
   assert.equal(await page.locator('#game-nav .nav-button').count(),5);checks++;
   const pageGeometry=await page.evaluate(()=>({scroll:document.scrollingElement.scrollHeight,height:innerHeight,width:innerWidth,bodyWidth:document.scrollingElement.scrollWidth,main:document.querySelector('#main').getBoundingClientRect().toJSON(),nav:document.querySelector('#game-nav').getBoundingClientRect().toJSON()}));
   assert.ok(pageGeometry.scroll<=height+1&&pageGeometry.bodyWidth<=width+1,JSON.stringify(pageGeometry));checks++;
   await page.waitForFunction(()=>[...document.querySelectorAll('img')].filter(i=>{const r=i.getBoundingClientRect();return r.left>=0&&r.left<innerWidth&&r.top<innerHeight&&r.bottom>0;}).every(i=>i.complete),{},{timeout:15000}).catch(()=>{});await page.screenshot({path:path.join(out,`buildings-${width}-${height}-${lang}.png`)});
   assert.equal(await page.locator('.colony-landscape').count(),1);checks++;
   await page.locator('[data-catalog-card="dyson"]').evaluate(el=>el.scrollIntoView({block:'nearest',inline:'start'}));
   await page.waitForFunction(()=>[...document.querySelectorAll('img')].filter(i=>{const r=i.getBoundingClientRect();return r.left>=0&&r.left<innerWidth&&r.top<innerHeight&&r.bottom>0;}).every(i=>i.complete),{},{timeout:15000}).catch(()=>{});await page.screenshot({path:path.join(out,`dyson-${width}-${height}-${lang}.png`)});
   assert.equal(await page.locator('[data-catalog-card="dyson"] img').getAttribute('data-art-key'),'megastructures/dyson');checks++;assert.ok(await page.locator('[data-catalog-card="dyson"] img').evaluate(i=>i.naturalWidth>0));
   await page.locator('#game-nav [data-tab="ships"]').click();
   assert.ok(await page.locator('[data-catalog-carousel="ships"]').count());checks++;
   assert.equal(await page.locator('[data-catalog-carousel="defenses"]').count(),0);checks++;
   await page.waitForFunction(()=>[...document.querySelectorAll('img')].filter(i=>{const r=i.getBoundingClientRect();return r.left>=0&&r.left<innerWidth&&r.top<innerHeight&&r.bottom>0;}).every(i=>i.complete),{},{timeout:15000}).catch(()=>{});await page.screenshot({path:path.join(out,`ships-${width}-${height}-${lang}.png`)});
   await page.locator('.fleet-navigation [data-tab="defenses"]').click();
   assert.equal(await page.locator('[data-catalog-carousel="defenses"]').count(),1);checks++;
   await page.locator('.fleet-navigation [data-tab="ships"]').click();
   await page.locator('.fleet-navigation [data-new-mission]').click();
   await page.locator('[data-map-scale]').waitFor();
   assert.equal(await page.locator('[data-map-scale]').textContent(),'240%');checks++;
   const homeSystem=state.own_planets.find(p=>p.id===state.planet_id).system_id;
   assert.equal(await page.locator('.system-node.selected').getAttribute('data-system'),homeSystem);checks++;
   const targetSystem=state.galaxy.find(s=>s.id!==homeSystem&&s.planets?.some(p=>p.owner_id!==state.player.id));
   const target=targetSystem.planets.find(p=>p.owner_id!==state.player.id);
   // Invoke a real button click after map centering, independent of world position.
   await page.locator(`[data-system="${targetSystem.id}"]`).evaluate(el=>el.click());
   assert.equal(await page.locator('.galaxy-picker').count(),0);checks++;
   assert.ok((await page.locator('#system-detail .planet-identity-copy').allTextContents()).every(x=>x.trim().length>5));checks++;
   await page.waitForFunction(()=>[...document.querySelectorAll('img')].filter(i=>{const r=i.getBoundingClientRect();return r.left>=0&&r.left<innerWidth&&r.top<innerHeight&&r.bottom>0;}).every(i=>i.complete),{},{timeout:15000}).catch(()=>{});await page.screenshot({path:path.join(out,`system-${width}-${height}-${lang}.png`)});
   await page.locator(`[data-target="${target.id}"]:not([data-system-scout])`).click();
   await page.locator('#fleet-scout').fill('4');await page.locator('#cargo-metal').fill('123');
   await page.locator('[data-change-destination]').click();
   assert.ok((await page.locator('#system-detail h2').textContent()).includes(targetSystem.name));checks++;
   await page.locator(`[data-target="${target.id}"]:not([data-system-scout])`).click();
   assert.equal(await page.locator('#fleet-scout').inputValue(),'4');assert.equal(await page.locator('#cargo-metal').inputValue(),'123');checks+=2;
   await page.locator('.fleet-navigation [data-new-mission]').click();
   assert.equal(await page.locator('.system-node.selected').getAttribute('data-system'),homeSystem);checks++;
   await page.locator(`[data-system="${targetSystem.id}"]`).evaluate(el=>el.click());
   await page.locator(`[data-target="${target.id}"]:not([data-system-scout])`).click();
   assert.equal(await page.locator('#fleet-scout').inputValue(),target.owner_type==='empty'?'0':'1');assert.equal(await page.locator('#cargo-metal').inputValue(),'0');checks+=2;
   await page.locator('#game-nav [data-tab="research"]').click();
   assert.equal(await page.locator('.tech-node-description').count(),state.catalog.research.length);checks++;
   assert.equal(await page.locator('[data-tab="megastructures"]').count(),0);checks++;
   const tree=await page.locator('.tech-tree').evaluate(el=>({height:el.clientHeight,scroll:el.scrollHeight,width:el.clientWidth,columns:getComputedStyle(el).gridTemplateColumns,rows:getComputedStyle(el).gridTemplateRows}));
   assert.equal(tree.rows.split(' ').length,3);checks++;
   assert.ok(tree.scroll<=tree.height+1,JSON.stringify(tree));checks++;
   await page.waitForFunction(()=>[...document.querySelectorAll('img')].filter(i=>{const r=i.getBoundingClientRect();return r.left>=0&&r.left<innerWidth&&r.top<innerHeight&&r.bottom>0;}).every(i=>i.complete),{},{timeout:15000}).catch(()=>{});await page.screenshot({path:path.join(out,`research-${width}-${height}-${lang}.png`)});
   await page.locator('.tech-node-action').first().click();await page.locator('#research-dialog').waitFor({state:'visible'});checks++;
   await page.locator('[data-close-research]').click();
   await page.locator('#game-nav [data-tab="colony"]').click();
   await page.locator('[data-catalog-card="wormhole"]').evaluate(el=>el.scrollIntoView({block:'nearest',inline:'end'}));
   await page.waitForFunction(()=>document.querySelector('[data-catalog-card="wormhole"] img').complete);
   assert.ok(await page.locator('[data-catalog-card="wormhole"] img').evaluate(i=>i.naturalWidth>0));checks++;
   if(width===390){
    Object.assign(state.megastructures,{dyson_stage:4,gate_level:1,is_origin:true,origin_id:state.planet_id,energy:999999999,capacity:999999999});
    for(const project of state.megastructures.projects)project.level=project.max_level;
    await page.locator('#refresh').click();
    await page.locator('[data-catalog-card="wormhole"]').evaluate(el=>el.scrollIntoView({block:'nearest',inline:'end'}));
    await page.locator('[data-tunnel-open]').scrollIntoViewIfNeeded();
    assert.ok(await page.locator('[data-tunnel-open]').isEnabled());checks++;
    await page.screenshot({path:path.join(out,'wormhole-open-390-en.png')});
    const selected=await page.locator('#tunnel-target').inputValue();
    await page.locator('[data-tunnel-open]').click();
    await page.locator('#confirm-dialog button[value="confirm"]').click();
    await page.waitForTimeout(200);
    assert.ok(calls.some(c=>c.path==='/api/action'&&c.body.type==='tunnel_open'&&c.body.target_id===selected));checks++;
   }
   assert.deepEqual(errors,[]);checks++;
   results.push({width,height,lang,checks,pageGeometry,tree});await ctx.close();
  }
  fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({ok:true,checks,results},null,2));console.log(JSON.stringify({ok:true,checks,results}));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
