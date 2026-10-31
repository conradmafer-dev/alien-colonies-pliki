// Real browser + real isolated World/HTTP API. No production account or writes.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../../..'),out=process.env.AC_WEB_QA_DIR||'/tmp/ac103-browser';fs.mkdirSync(out,{recursive:true});
(async()=>{
 const child=spawn('python',['tests/serve_expedition103_fixture.py'],{cwd:root,stdio:['ignore','pipe','pipe']});
 let err='';child.stderr.on('data',b=>err+=b);
 const fixture=await new Promise((resolve,reject)=>{let s='';child.stdout.on('data',b=>{s+=b;const n=s.indexOf('\n');if(n>=0){try{resolve(JSON.parse(s.slice(0,n)))}catch(e){reject(e)}}});child.on('exit',c=>reject(Error('Fixture '+c+' '+err)));});
 let browser,checks=0;
 try {
  browser=await chromium.launch({executablePath:process.env.CHROME_EXECUTABLE,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote','--disable-gpu']});
  for(const [width,height,lang] of [[360,800,'en'],[390,844,'pl'],[1280,900,'de']]) {
   const ctx=await browser.newContext({viewport:{width,height},hasTouch:width<900,isMobile:width<900});
   const page=await ctx.newPage(),errors=[],calls=[];page.on('pageerror',e=>errors.push(e.message));
   page.on('request',r=>{if(r.url().includes('/api/preview')||r.url().includes('/api/action'))calls.push({url:r.url(),body:r.postDataJSON()});});
   await page.addInitScript(token=>{sessionStorage.setItem('alien-colonies.session',token);sessionStorage.setItem('alien-colonies.tab','fleets');},fixture.token);
   await page.goto(fixture.origin+'/play/?lang='+lang);
   await page.locator('[data-expedition-start]').waitFor();
   await page.locator('[data-expedition-start]').click();
   await page.locator('#expedition-hours').waitFor();
   assert.equal(await page.locator('#fleet-mission').inputValue(),'expedition');checks++;
   assert.equal(await page.locator('#expedition-hours option').count(),3);checks++;
   assert.equal(await page.locator('[data-change-destination]').count(),0);checks++;
   await page.locator('#expedition-hours').selectOption('3');
   await page.locator('[name="ship-cargo"]').fill('1');await page.locator('[name="ship-frigate"]').fill('4');
   await page.waitForFunction(()=>!document.querySelector('[data-launch-fleet]').disabled);
   const quote=calls.filter(c=>c.url.includes('/api/preview')).at(-1).body;
   assert.equal(quote.mission,'expedition');assert.equal(quote.expedition_hours,3);checks+=2;
   assert.ok(quote.ships.scout>=1&&quote.ships.cargo===1&&quote.ships.frigate===4);checks++;
   assert.ok((await page.locator('#fleet-preview').innerText()).includes('3 h'));checks++;
   const geo=await page.evaluate(()=>({w:innerWidth,doc:document.scrollingElement.scrollWidth,send:document.querySelector('[data-launch-fleet]').getBoundingClientRect().toJSON(),nav:document.querySelector('#game-nav').getBoundingClientRect().toJSON()}));
   assert.ok(geo.doc<=geo.w+1);assert.ok(geo.send.bottom<=geo.nav.top+1||geo.send.left>=geo.nav.right-1||geo.send.right<=geo.nav.left+1||geo.send.top>=geo.nav.bottom-1);checks+=2;
   await page.screenshot({path:path.join(out,`expedition-${width}-${lang}.png`)});
   await Promise.all([page.waitForResponse(r=>r.url().includes('/api/action')&&r.request().postDataJSON()?.type==='fleet'),page.locator('[data-launch-fleet]').click()]);
   await page.locator('#fleet-form').waitFor({state:'detached'});
   await page.locator('#game-nav [data-tab="ships"]').click();
   await page.locator('.fleet-active-button').click();
   await page.locator('[data-expedition-recall]').first().waitFor();
   const action=calls.filter(c=>c.body?.type==='fleet').at(-1).body;
   assert.equal(action.expedition_hours,3);assert.ok(action.request_id);checks+=2;
   await page.locator('[data-expedition-recall]').first().click();
   await page.waitForFunction(()=>!document.querySelector('[data-expedition-recall]'));
   const recall=calls.findLast(c=>c.body?.type==='recall_expedition').body;assert.ok(recall.fleet_id&&recall.request_id);checks++;
   assert.deepEqual(errors,[]);checks++;await ctx.close();
  }
  const result={result:'PASS',checks,scope:'Chromium and isolated real backend at three viewports/languages'};
  fs.writeFileSync(path.join(out,'expedition103-browser.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 } finally {if(browser)await browser.close();child.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
