/* Real Chromium regression: isolated backend fixture, actual artwork, native wheel input. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {spawnSync} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../..');
const out = path.resolve(process.env.AC_WEB_QA_DIR || '/tmp/alien-colonies-card-flow');
fs.mkdirSync(out, {recursive:true});
const fixtureRun = spawnSync('python', ['-c', `
import app,tempfile,time,json,pathlib,sys
from i18n import language_scope
out=pathlib.Path(sys.argv[1])
with tempfile.TemporaryDirectory() as tmp:
 w=app.World(str(pathlib.Path(tmp)/'card-flow.sqlite3'),1,now=time.time())
 a=w.register('CardFlowTest','LocalTestPass-0127')
 pid=a['state']['player']['id'];home=a['state']['planet_id']
 w.action(pid,{'type':'choose_race','race_id':'zetans','planet_id':home})
 p=w.data['planets'][home];p['ships']['scout']=7;p['ships']['cargo']=5;p['buildings']['observatory']=12
 for lang in ['en','pl','de']:
  with language_scope(lang):state=w.state(pid,home)
  (out/f'fixture-{lang}.json').write_text(json.dumps(state,ensure_ascii=False))
 w.data['players'][pid]['megastructure'].update(origin_id=home,dyson_stage=4,gate_level=1,energy=999999999)
 with language_scope('en'):state=w.state(pid,home)
 (out/'fixture-complete-en.json').write_text(json.dumps(state,ensure_ascii=False))
 w.close()
`, out], {cwd:path.dirname(root),encoding:'utf8'});
assert.equal(fixtureRun.status, 0, fixtureRun.stderr);
const mime = {'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.webp':'image/webp'};
const assetCache = new Map();
const server = http.createServer(async (req,res) => {
 const name = new URL(req.url, 'http://localhost').pathname;
 const file = path.resolve(root, '.' + (name.endsWith('/') ? name+'index.html' : name));
 if(!file.startsWith(root+'/')) return res.writeHead(403).end();
 if(fs.existsSync(file)) return res.writeHead(200, {'Content-Type':mime[path.extname(file)] || 'application/octet-stream'}).end(fs.readFileSync(file));
 if(name.startsWith('/assets/') || name.startsWith('/play/assets/')) {
  try {
   if(!assetCache.has(name)) assetCache.set(name, fetch('https://aliencolonies.com'+name).then(async r=>({status:r.status,type:r.headers.get('content-type'),bytes:Buffer.from(await r.arrayBuffer())})));
   const a = await assetCache.get(name);
   return res.writeHead(a.status, {'Content-Type':a.type || 'image/webp'}).end(a.bytes);
  } catch {}
 }
 res.writeHead(404).end();
});
let checks=0;
const failures=[], results=[];
function check(condition, label, evidence) {
 checks++;
 if(!condition) failures.push({label,evidence});
}
async function shell(page) {
 return page.evaluate(()=>({
  scrollTop:document.scrollingElement.scrollTop, scrollLeft:document.scrollingElement.scrollLeft,
  scrollHeight:document.scrollingElement.scrollHeight, scrollWidth:document.scrollingElement.scrollWidth,
  viewport:[innerWidth,innerHeight], mainScrollTop:document.querySelector('#main').scrollTop,
  rects:['.game-header','.resource-bar','#game-nav','#main'].map(selector=>({selector,...document.querySelector(selector).getBoundingClientRect().toJSON()}))
 }));
}
function sameShell(before,after,label) {
 check(before.scrollTop===after.scrollTop && before.scrollLeft===after.scrollLeft && before.mainScrollTop===after.mainScrollTop,
  `${label}: page and main do not scroll`, {before,after});
 check(before.rects.every((r,i)=>Math.abs(r.top-after.rects[i].top)<1 && Math.abs(r.bottom-after.rects[i].bottom)<1),
  `${label}: HUD and navigation stay fixed`, {before:before.rects,after:after.rects});
}
async function selectCard(page,key) {
 const card=page.locator(`[data-catalog-card="${key}"]`);
 await card.evaluate(el=>{
  const track=el.closest('[data-catalog-carousel]');
  track.scrollTo({left:track.scrollLeft+el.getBoundingClientRect().left-track.getBoundingClientRect().left-3,behavior:'instant'});
  (el.querySelector('[data-card-scroll]')||el).scrollTop=0;
  el.querySelector('img').loading='eager';
 });
 await page.waitForFunction(key=>{
  const c=document.querySelector(`[data-catalog-card="${key}"]`),i=c.querySelector('img');
  const r=c.getBoundingClientRect(),t=c.closest('[data-catalog-carousel]').getBoundingClientRect();
  return i.complete && i.naturalWidth>0 && r.left>=t.left-2 && r.left<t.right;
 },key,{timeout:20000});
 return card;
}
async function inspectCard(page,key,label,{short=false}={}) {
 const card=await selectCard(page,key);
 const m=await card.evaluate(el=>{
  const rect=e=>e.getBoundingClientRect().toJSON(), image=el.querySelector('img');
  const body=el.querySelector('[data-card-scroll]'),footer=el.querySelector('.construction-card-footer');
  const info=el.querySelector('.building-info,.project-info');
  const children=[...info.children].filter(e=>e.getBoundingClientRect().height>0);
  const gaps=children.slice(1).map((e,i)=>({from:children[i].className||children[i].tagName,to:e.className||e.tagName,gap:rect(e).top-rect(children[i]).bottom}));
  const scrollChildren=[...body.querySelectorAll('*')].filter(e=>/auto|scroll/.test(getComputedStyle(e).overflowY)&&e.scrollHeight>e.clientHeight+1).map(e=>e.className);
  const r=rect(el), last=children.at(-1),i=rect(image),art=rect(image.parentElement);
  return {key:el.dataset.catalogCard,card:r,body:rect(body),clientHeight:body.clientHeight,scrollHeight:body.scrollHeight,scrollTop:body.scrollTop,
   image:{...i,naturalWidth:image.naturalWidth,naturalHeight:image.naturalHeight,objectFit:getComputedStyle(image).objectFit},art,
   info:rect(info),scrollChildren,overflowY:getComputedStyle(body).overflowY,gaps,
   siblings:[...el.parentElement.querySelectorAll('[data-catalog-card]')].map(rect),
   contentBottom:last?rect(last).bottom:rect(info).bottom,track:rect(el.parentElement),requirementCount:el.querySelectorAll('.requirement').length,
   footer:footer?rect(footer):null,bodyCosts:body.querySelectorAll('.cost-list').length,bodyImages:body.querySelectorAll('img').length,
   actionCount:el.querySelectorAll('.project-action,[data-megabuild],[data-megacancel],[data-tunnel-open]').length,
   controls:footer?[...footer.querySelectorAll('.cost-list,input,button,.duration')].map(e=>({tag:e.tagName,text:e.textContent.trim(),...rect(e)})):[]};
 });
 check(m.image.naturalWidth>0,`${label}: real artwork loaded`,m.image);
 check(Math.abs(m.image.width/m.image.height-m.image.naturalWidth/m.image.naturalHeight)<.015 || m.image.objectFit==='contain',
  `${label}: full image preserves native proportions`,m.image);
 check(m.image.objectFit!=='cover' && m.image.top>=m.art.top-1 && m.image.bottom<=m.art.bottom+1 && m.image.left>=m.art.left-1 && m.image.right<=m.art.right+1,
  `${label}: full artwork fits without cropping`,{image:m.image,art:m.art});
 check(/auto|scroll/.test(m.overflowY) && m.scrollChildren.length===0,
  `${label}: text has one vertical scroll owner`,{overflowY:m.overflowY,scrollChildren:m.scrollChildren});
 check(m.bodyImages===0,`${label}: artwork remains outside the scrolling text`,m);
 check(m.gaps.every(g=>g.gap<=32 && g.gap>=-1),`${label}: content has natural spacing`,m.gaps);
 check(m.card.bottom<=m.track.bottom+1 && m.card.height>40,`${label}: card bounded by available viewport`,m);
 check(m.siblings.every(r=>Math.abs(r.height-m.card.height)<1 && Math.abs(r.bottom-m.card.bottom)<1),
  `${label}: every card has equal height and bottom alignment`,m.siblings);
 check(m.track.bottom-m.card.bottom<=15,`${label}: cards fill available carousel height`,m);
 if(m.info.height<=m.clientHeight+1) {
  check(Math.abs((m.info.top+m.info.bottom)-(m.body.top+m.body.bottom))<2,
   `${label}: short text is centered as a single compact block`,m);
 } else {
  check(Math.abs(m.info.top-m.body.top)<1,`${label}: overflowing text starts at the top`,m);
 }
 check((!m.actionCount || m.footer) && m.bodyCosts===0,`${label}: production actions and costs belong to the footer`,m);
 if(m.footer) {
  check(m.footer.top>=m.body.bottom-1 && m.footer.bottom<=m.card.bottom+1,`${label}: footer fits outside scrolling body`,m);
  check(m.controls.length>0 && m.controls.every(c=>c.top>=m.card.top-1 && c.bottom<=m.card.bottom+1 && c.left>=m.card.left-1 && c.right<=m.card.right+1),`${label}: costs, quantity and action are visible initially`,m.controls);
 }
 if(short) {
  check(m.scrollHeight<=m.clientHeight+1,`${label}: short fixture needs no text scrolling`,m);
 }
 const before=await shell(page);
 await page.mouse.move(Math.min(m.card.right-20,(m.card.left+m.card.right)/2),Math.min(m.body.bottom-5,m.body.top+Math.min(70,m.body.height/2)));
 await page.mouse.wheel(0,280);
 if(m.scrollHeight>m.clientHeight+2) {
  await page.waitForFunction(key=>document.querySelector(`[data-catalog-card="${key}"] [data-card-scroll]`).scrollTop>0,key,{timeout:2500}).catch(()=>{});
  const moved=await card.evaluate(el=>({top:el.querySelector('[data-card-scroll]').scrollTop,imageTop:el.querySelector('img').getBoundingClientRect().top}));
  check(moved.top>0,`${label}: native wheel scrolls the card body`,moved);
  check(Math.abs(moved.imageTop-m.image.top)<1,`${label}: artwork remains fixed while details scroll`,{before:m.image.top,after:moved.imageTop});
  await page.mouse.wheel(0,100000);
  await page.waitForFunction(key=>{const c=document.querySelector(`[data-catalog-card="${key}"] [data-card-scroll]`);return c.scrollTop>=c.scrollHeight-c.clientHeight-2;},key,{timeout:2500}).catch(()=>{});
  const end=await card.evaluate(el=>{const b=el.querySelector('[data-card-scroll]');return {scrollTop:b.scrollTop,max:b.scrollHeight-b.clientHeight,body:b.getBoundingClientRect().toJSON(),last:el.querySelector('.building-info,.project-info').lastElementChild.getBoundingClientRect().toJSON()};});
  check(end.scrollTop>=end.max-2 && end.last.bottom<=end.body.bottom+1,`${label}: last detail is reachable`,end);
  if(m.footer) {
   const footer=await card.locator('.construction-card-footer').boundingBox();
   check(Math.abs(footer.y-m.footer.y)<1 && Math.abs(footer.height-m.footer.height)<1,`${label}: footer remains fixed after body scrolling`,{before:m.footer,after:footer});
  }
  if(label.startsWith('390-') && ['titan','wormhole'].includes(key)) await page.screenshot({path:path.join(out,`${label}-body-bottom.png`)});
 }
 sameShell(before,await shell(page),label);
 const reqs=card.locator('.requirement');
 for(let n=0;n<await reqs.count();n++) {
  const visible=await reqs.nth(n).evaluate(el=>{
   const c=el.closest('[data-card-scroll]'),r=el.getBoundingClientRect(),p=c.getBoundingClientRect();
   c.scrollTop+=r.top-p.top-6;
   const next=el.getBoundingClientRect();return {visible:next.top>=p.top-1&&next.bottom<=p.bottom+1,text:el.textContent.trim(),rect:next.toJSON(),card:p.toJSON()};
  });
  check(visible.visible && visible.text.length>0,`${label}: requirement ${n+1} reachable and populated`,visible);
 }
 await card.evaluate(el=>el.querySelector('[data-card-scroll]').scrollTop=0);
 await page.screenshot({path:path.join(out,`${label.replace(/[^a-z0-9-]/gi,'-')}.png`)});
 return m;
}
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{}),args:['--no-sandbox']});
 try {
  const sizes=[[390,844,'en'],[360,740,'pl'],[1280,900,'en'],[844,390,'de']].filter(([w,h])=>!process.env.AC_WEB_QA_VIEWPORT || `${w}x${h}`===process.env.AC_WEB_QA_VIEWPORT);
  assert.ok(sizes.length,'AC_WEB_QA_VIEWPORT must match a supported viewport');
  for(const [width,height,lang] of sizes) {
   const state=JSON.parse(fs.readFileSync(path.join(out,`fixture-${lang}.json`)));
   const context=await browser.newContext({viewport:{width,height},hasTouch:width<900,isMobile:width<900});
   await context.route('**/api/**',async route=>{
    const name=new URL(route.request().url()).pathname;
    const data=['/api/action','/api/state'].includes(name)?{ok:true,state}:{ok:true,configured:false};
    await route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
   });
   const page=await context.newPage(),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(()=>{sessionStorage.setItem('alien-colonies.session','card-flow-test');sessionStorage.setItem('alien-colonies.tab','colony');});
   await page.goto(`${origin}/play/?lang=${lang}`);
   await page.locator('[data-catalog-card="dyson"]').waitFor();
   const prefix=`${width}-${height}-${lang}`,metrics=[];
   const s=await shell(page);
   check(s.scrollHeight<=height+1 && s.scrollWidth<=width+1,`${prefix}: page stays inside viewport`,s);
   metrics.push(await inspectCard(page,'metal_mine',`${prefix}-building`));
   metrics.push(await inspectCard(page,'observatory',`${prefix}-max-building`));
   metrics.push(await inspectCard(page,'dyson',`${prefix}-dyson`));
   metrics.push(await inspectCard(page,'wormhole',`${prefix}-wormhole`));
   if(width===1280) {
    Object.assign(state,JSON.parse(fs.readFileSync(path.join(out,'fixture-complete-en.json'))));
    await page.locator('#refresh').click();
    await page.waitForFunction(()=>document.querySelector('[data-catalog-card="dyson"] .building-level').textContent.includes('4 / 4'));
    metrics.push(await inspectCard(page,'dyson',`${prefix}-completed-dyson`,{short:true}));
    metrics.push(await inspectCard(page,'wormhole',`${prefix}-completed-wormhole`));
    Object.assign(state,JSON.parse(fs.readFileSync(path.join(out,`fixture-${lang}.json`))));
    await page.locator('#refresh').click();
   }
   await page.locator('#game-nav [data-tab="ships"]').click();
   metrics.push(await inspectCard(page,'scout',`${prefix}-scout`));
   metrics.push(await inspectCard(page,'titan',`${prefix}-titan`));
   if(width===390) {
    check((await page.locator('.fleet-navigation [data-tab="defenses"]').textContent()).trim()==='Defenses',`${prefix}: ship construction leads to Defenses in English`);
    const quantity=page.locator('[data-catalog-card="titan"] [data-batch]');
    await quantity.fill('7');
    const amountCosts=await page.locator('[data-catalog-card="titan"] .cost-list span').allTextContents();
    const titan=state.catalog.ships.find(s=>s.key==='titan');
    check(amountCosts.every((text,i)=>Number(text.replace(/[^0-9]/g,''))===7*Number(titan.cost[['metal','crystal','fuel'][i]]||0)),`${prefix}: quantity updates all footer costs`,amountCosts);
    const amountTime=await page.locator('[data-catalog-card="titan"] .construction-card-footer .duration').textContent();
    await page.locator('[data-catalog-card="titan"] [data-card-scroll]').evaluate(el=>el.scrollTop=150);
    await page.waitForTimeout(100);
    const priorTop=await page.locator('[data-catalog-card="titan"] [data-card-scroll]').evaluate(el=>el.scrollTop);
    await page.locator('#refresh').click();
    await page.waitForFunction(top=>Math.abs(document.querySelector('[data-catalog-card="titan"] [data-card-scroll]').scrollTop-top)<2,priorTop,{timeout:3000}).catch(()=>{});
    check(Math.abs(await page.locator('[data-catalog-card="titan"] [data-card-scroll]').evaluate(el=>el.scrollTop)-priorTop)<2,`${prefix}: polling refresh preserves the card reading position`);
    check(await quantity.inputValue()==='7',`${prefix}: manual refresh retains the selected quantity`);
    check(JSON.stringify(await page.locator('[data-catalog-card="titan"] .cost-list span').allTextContents())===JSON.stringify(amountCosts),`${prefix}: manual refresh retains multiplied footer costs`);
    check(await page.locator('[data-catalog-card="titan"] .construction-card-footer .duration').textContent()===amountTime,`${prefix}: manual refresh retains batch duration`);
   }
   await selectCard(page,'scout');
   const track=page.locator('[data-catalog-carousel="ships"]');
   const first=await track.evaluate(el=>({left:el.scrollLeft,rect:el.getBoundingClientRect().toJSON()}));
   await page.mouse.move(first.rect.left+70,first.rect.top+35);
   await page.mouse.wheel(560,0);
   await page.waitForFunction(()=>document.querySelector('[data-catalog-carousel="ships"]').scrollLeft>50,{}, {timeout:2500}).catch(()=>{});
   check(await track.evaluate(el=>el.scrollLeft)>first.left+50,`${prefix}: native horizontal carousel remains usable`);
   await page.locator('.fleet-navigation [data-tab="defenses"]').click();
   if(lang==='en') check((await page.locator('.fleet-navigation [data-tab="ships"]').textContent()).trim()==='Ships',`${prefix}: defense construction leads to Ships in English`);
   metrics.push(await inspectCard(page,state.catalog.defenses[0].key,`${prefix}-defense`));
   await page.locator('#game-nav [data-tab="research"]').click();
   const research=await page.locator('.tech-tree').evaluate(el=>({rows:getComputedStyle(el).gridTemplateRows.split(' ').length,height:el.clientHeight,scrollHeight:el.scrollHeight}));
   check(research.rows===3 && research.scrollHeight<=research.height+1,`${prefix}: research stays three rows`,research);
   check(errors.length===0,`${prefix}: no browser errors`,errors);
   results.push({width,height,lang,metrics,research});
   await context.close();
  }
 } finally {
  await browser.close();server.close();
  const suffix=process.env.AC_WEB_QA_VIEWPORT?`-${process.env.AC_WEB_QA_VIEWPORT}`:'';
  fs.writeFileSync(path.join(out,`card-flow${suffix}-results.json`),JSON.stringify({ok:!failures.length,checks,failures,results},null,2));
 }
 console.log(JSON.stringify({ok:!failures.length,checks,failures},null,2));
 if(failures.length) process.exitCode=1;
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
