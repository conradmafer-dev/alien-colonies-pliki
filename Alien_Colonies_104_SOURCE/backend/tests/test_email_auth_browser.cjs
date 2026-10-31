/* Offline browser integration: all auth/mail requests are synthetic fixtures. */
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const http=require('node:http');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../web');
const evidence=path.resolve(process.env.EMAIL_TEST_EVIDENCE || path.join(__dirname,'../../alien-email-web-evidence'));
fs.mkdirSync(evidence,{recursive:true});
const mime={'.js':'text/javascript','.json':'application/json','.html':'text/html','.css':'text/css','.svg':'image/svg+xml','.webp':'image/webp','.jpg':'image/jpeg'};
const server=http.createServer((req,res)=>{const name=new URL(req.url,'http://localhost').pathname;const file=path.resolve(root,'.'+(name.endsWith('/')?name+'index.html':name));if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}try{res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');res.end(fs.readFileSync(file));}catch{res.writeHead(404).end();}});
const state=()=>({player:{id:'test-player',name:'Test Empire',race_id:'zetans',race_name:'Zetan',protected_until:0},planet_id:'one',planet_name:'Colony',own_planets:[{id:'one',name:'Colony'}],version:'test',server_time:Date.now()/1000,account:{email_linked:true,password_login_enabled:false},premium:{queue_planning_active:false},resources:{metal:4000,crystal:2600,fuel:1400},production:{metal:10,crystal:10,fuel:10},limits:{colonies:12,resource_cap:1e9,queue_waiting:10},fields:{free:20},energy:{supply:100,used:10,factor:1},race:{},environment:{},reports:[],queue:[],planned_orders:[],fleets:[],incoming_attacks:[],research_queue:null,catalog:{buildings:[],research:[],ships:[],defenses:[]},buildings:{},research:{},ships:{},galaxy:[],communications:{}});
let browser,checks=0;const reports=[];
const check=(condition,message)=>{assert.ok(condition,message);checks++;};
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE,args:['--no-sandbox','--disable-dev-shm-usage']});
 async function scenario({enabled=true,configDown=false,width=390,signedIn=false,lang='en'}={}) {
  const context=await browser.newContext({viewport:{width,height:900}});const calls=[],errors=[];
  const model={status:'pending',starts:0,completeStatus:200,completePlayer:'test-player',holdStatus:false,held:[],nameTaken:false};
  await context.addInitScript(({signedIn})=>{
   if(signedIn)sessionStorage.setItem('alien-colonies.session','existing-session');
   window.__emailClockOffset=0;const originalNow=Date.now;Date.now=()=>originalNow()+window.__emailClockOffset;
   const timeout=window.setTimeout;window.setTimeout=(f,ms,...args)=>timeout(f,ms>=2000&&ms<=10000?35:ms,...args);
  },{signedIn});
  await context.route('**/api/**',async route=>{
   const request=route.request(),endpoint=new URL(request.url()).pathname;let body;try{body=request.postDataJSON();}catch{}calls.push({endpoint,body,headers:request.headers(),url:request.url()});
   if(endpoint==='/api/auth/google/open'){await route.fulfill({contentType:'text/html',body:'<!doctype html><p>Mock Google account</p>'});return;}
   let out={ok:true},status=200;
   if(endpoint==='/api/auth/email/config'){out.configured=enabled;if(configDown){status=503;out={ok:false,error:'Provider unavailable'};}}
   else if(endpoint==='/api/auth/google/config')out={ok:true,configured:true,require_google_registration:true};
   else if(endpoint==='/api/auth/email/start')out={ok:true,flow_id:'flow-'+(++model.starts),poll_secret:'secret-'+model.starts,expires_in:900,resend_after:60,poll_after:3};
   else if(endpoint==='/api/auth/email/status') {if(model.holdStatus){model.held.push(route);return;}out.status=model.status;}
   else if(endpoint==='/api/auth/email/complete'){if(model.nameTaken){status=409;out={ok:false,error:'Name already taken'};}else{out={ok:true,token:'email-session',state:state()};out.state.player.id=model.completePlayer;if(body.name)out.state.player.name=body.name;}}
   else if(endpoint==='/api/auth/google/start')out={ok:true,flow_id:'google-flow',poll_secret:'google-secret',authorization_url:origin+'/api/auth/google/open?flow=google-flow',expires_in:600,poll_after:3};
   else if(endpoint==='/api/auth/google/status')out.status='ready';
   else if(endpoint==='/api/auth/google/complete')out={ok:true,token:'google-session',state:state()};
   else if(endpoint==='/api/state')out={ok:true,state:state()};
   else if(endpoint==='/api/account/logout-others')out={ok:true,message:'Other devices have been signed out.'};
   else if(endpoint==='/api/account/delete')out={ok:true,deleted:true};
   else if(endpoint==='/api/logout')out={ok:true};
   else throw Error('Unexpected endpoint: '+endpoint);
   await route.fulfill({status,contentType:'application/json',body:JSON.stringify(out)});
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+'/play/?lang='+lang);await page.waitForSelector(signedIn?'#game-screen:not([hidden])':'#google-auth-options:not([hidden])');
  if(enabled&&!configDown&&!signedIn)await page.waitForSelector('#email-auth-options:not([hidden])');
  else await page.waitForTimeout(100);
  return {page,context,calls,errors,model,async finish(){check(errors.length===0,'no browser exceptions: '+errors.join(';'));reports.push({width,lang,enabled,configDown,errors,calls:calls.map(x=>({endpoint:x.endpoint,method:typeof x.body==='object'?'POST':'GET'}))});await context.close();}};
 }
 // The provider flag never takes Google down.
 for(const configDown of [false,true]){
  const h=await scenario({enabled:false,configDown});check(await h.page.locator('#email-auth-options').isHidden(),'email is hidden while unavailable');await h.page.click('#auth-google');await h.page.waitForSelector('#game-screen:not([hidden])');check(h.calls.some(x=>x.endpoint==='/api/auth/google/complete'),'Google still signs in');await h.finish();
 }
 // Full new-account flow and screenshots at phone/desktop widths.
 for(const width of [390,1440]){
  const h=await scenario({width});await h.page.screenshot({path:path.join(evidence,`login-${width}.png`),fullPage:true});
  await h.page.click('#auth-email');await h.page.waitForSelector('#email-auth-dialog[open]');
  check(await h.page.locator('#email-address').evaluate(e=>e===document.activeElement),'email input receives focus');
  await h.page.fill('#email-address','new-pilot@example.com');await h.page.screenshot({path:path.join(evidence,`email-entry-${width}.png`),fullPage:true});await h.page.click('#email-send');await h.page.waitForSelector('#email-waiting:not([hidden])');
  check(await h.page.locator('#email-resend').isDisabled(),'resend starts with cooldown');check(!h.calls.some(x=>x.endpoint==='/api/auth/email/complete'),'pending mail does not create account');
  await h.page.screenshot({path:path.join(evidence,`email-waiting-${width}.png`),fullPage:true});
  h.model.status='needs_name';await h.page.waitForSelector('#email-name-form:not([hidden])');check(!h.calls.some(x=>x.endpoint==='/api/auth/email/complete'),'verification alone does not create account');
  await h.page.fill('#email-empire-name','New Empire');await h.page.screenshot({path:path.join(evidence,`email-name-${width}.png`),fullPage:true});
  h.model.nameTaken=true;await h.page.click('#email-name-submit');await h.page.waitForSelector('#email-auth-error:not([hidden])');check(await h.page.inputValue('#email-empire-name')==='New Empire','name conflict preserves entered name');
  h.model.nameTaken=false;await h.page.fill('#email-empire-name','New Empire Two');await h.page.click('#email-name-submit');await h.page.waitForSelector('#game-screen:not([hidden])');
  check(await h.page.locator('#player-name').textContent()==='New Empire Two','explicitly chosen empire accepted');
  check(await h.page.evaluate(()=>!Object.values(localStorage).some(x=>/secret-|email-session/.test(x))),'no flow/session proof in localStorage');
  check(h.calls.every(x=>!x.url.includes('secret-')),'proof never enters URL');await h.finish();
 }
 // Resend, cancellation and a late verified response cannot reopen the game.
 {
  const h=await scenario();await h.page.click('#auth-email');await h.page.fill('#email-address','pilot@example.com');await h.page.click('#email-send');await h.page.waitForSelector('#email-waiting:not([hidden])');
  await h.page.evaluate(()=>{window.__emailClockOffset=61000;});await h.page.waitForFunction(()=>!document.querySelector('#email-resend').disabled);await h.page.click('#email-resend');await h.page.waitForFunction(()=>document.querySelector('#email-waiting').hidden===false);check(h.model.starts===2,'resend requests a fresh challenge');
  h.model.holdStatus=true;await h.page.waitForTimeout(100);check(h.model.held.length>0,'status request captured');await h.page.click('#email-cancel');
  for(const route of h.model.held)await route.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,status:'ready'})});
  await h.page.waitForTimeout(100);check(await h.page.locator('#game-screen').isHidden(),'late cancelled status cannot log in');check(!h.calls.some(x=>x.endpoint==='/api/auth/email/complete'),'cancel prevents complete');check(await h.page.locator('#auth-google').isEnabled(),'Google reenabled after cancel');await h.finish();
 }
 // All five languages retain translated controls without horizontal overflow.
 for(const [lang,label] of Object.entries({en:'Continue with email',pl:'Kontynuuj przez e-mail',de:'Mit E-Mail fortfahren',es:'Continuar con correo electrónico',fr:'Continuer avec un e-mail'})){
  const h=await scenario({lang});check((await h.page.locator('#auth-email').textContent()).trim()===label,'localized email action '+lang);await h.page.click('#auth-email');check(await h.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no horizontal page scroll '+lang);check(await h.page.locator('#email-auth-dialog').evaluate(e=>e.scrollWidth<=e.clientWidth+1),'no horizontal dialog scroll '+lang);await h.finish();
 }
 // Email-only settings: no nonexistent password or unintended Google linking.
 {
  const h=await scenario({signedIn:true});await h.page.click('[data-tab="settings"]');
  check(await h.page.locator('#account-delete-password').count()===0,'email-only deletion has no password field');check(await h.page.locator('[data-google-link]').count()===0,'email account does not offer unintended Google linking');
  await h.page.click('[data-email-logout-others]');await h.page.waitForSelector('#email-account-status:not([hidden])');check(h.calls.some(x=>x.endpoint==='/api/account/logout-others'&&x.body.password===''),'logout other devices uses verified current session');
  await h.page.locator('[data-email-reauth]').first().click();await h.page.fill('#email-address','different@example.com');h.model.status='needs_name';await h.page.click('#email-send');await h.page.waitForSelector('#email-auth-error:not([hidden])');check(await h.page.locator('#email-name-form').isHidden(),'reauth cannot create an empire');
  h.model.status='ready';h.model.completePlayer='another-player';await h.page.fill('#email-address','wrong@example.com');await h.page.click('#email-send');await h.page.waitForSelector('#email-auth-error:not([hidden])');check(await h.page.locator('#player-name').textContent()==='Test Empire','wrong email retains existing player');check(h.calls.some(x=>x.endpoint==='/api/logout'&&x.headers.authorization==='Bearer email-session'),'wrong account session revoked');
  h.model.completePlayer='test-player';await h.page.fill('#email-address','correct@example.com');await h.page.click('#email-send');await h.page.waitForFunction(()=>!document.querySelector('#email-auth-dialog').open);check(await h.page.locator('#main [data-email-logout-others]').count()===1,'same account reauth returns to settings');
  await h.page.fill('#account-delete-name','Test Empire');await h.page.click('#account-delete-form button[type=submit]');await h.page.waitForSelector('#confirm-dialog[open]');await h.page.click('#confirm-dialog button[value=confirm]');await h.page.waitForSelector('#auth-screen:not([hidden])');
  check(h.calls.some(x=>x.endpoint==='/api/account/delete'&&x.body.password===''&&x.body.confirmation==='DELETE ACCOUNT'),'email account can explicitly delete using fresh verification');await h.finish();
 }
 const result={checks,failures:0,mode:'Offline Chromium browser; mocked API and mail, no production traffic',reports};fs.writeFileSync(path.join(evidence,'browser-results.json'),JSON.stringify(result,null,2)+'\n');console.log(`Email browser: ${checks} checks, 0 failures`);
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();server.close();});
