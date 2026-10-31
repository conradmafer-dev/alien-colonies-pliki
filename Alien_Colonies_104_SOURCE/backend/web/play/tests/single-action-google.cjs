/* Browser regression checks. All API and Google responses are local mocks. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require('playwright');

const root = path.resolve(__dirname,'../..');
const mime = {'.js':'text/javascript','.json':'application/json','.css':'text/css','.html':'text/html','.svg':'image/svg+xml','.webp':'image/webp'};
const server = http.createServer((req,res) => {
  const name = new URL(req.url,'http://localhost').pathname;
  const file = path.resolve(root,'.'+(name.endsWith('/') ? name+'index.html' : name));
  if (!file.startsWith(root+path.sep)) {res.writeHead(403).end();return;}
  try {res.setHeader('Content-Type',mime[path.extname(file)] || 'application/octet-stream');res.end(fs.readFileSync(file));}
  catch {res.writeHead(404).end();}
});
const item = (key,name) => ({key,name,description:'Project',level:1,max_level:20,enabled:true,planning_enabled:false,planning_eligible:true,cost:{metal:50,crystal:20,fuel:5},seconds:60,requirements:[],unlocks:[]});
const makeState = () => ({player:{id:'test-player',name:'Test Empire',race_id:'zetan',race_name:'Zetan',protected_until:0},planet_id:'planet-one',planet_name:'Test Colony',planet_galaxy_id:'g01',own_planets:[{id:'planet-one',name:'Test Colony'}],version:'test',server_time:Date.now()/1000,account:{},premium:{queue_planning_active:false},resources:{metal:1000,crystal:1000,fuel:1000},production:{metal:10,crystal:10,fuel:10},limits:{colonies:10,resource_cap:1e9,queue_waiting:10},fields:{free:20},energy:{supply:100,used:10,factor:1},race:{},environment:{},reports:[],queue:[],planned_orders:[],fleets:[],incoming_attacks:[],research_queue:null,catalog:{buildings:[item('metal_mine','Metal Mine'),item('laboratory','Laboratory')],research:[item('propulsion','Propulsion')],ships:[{...item('scout','Scout'),count:1}],defenses:[{...item('turret','Turret'),count:1}]},buildings:{metal_mine:1,laboratory:1},research:{propulsion:1},ships:{scout:1},galaxy:[],communications:{}});
let browser;
(async () => {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE ? {executablePath:process.env.CHROME_EXECUTABLE} : {}),args:['--no-sandbox','--disable-dev-shm-usage']});
  const context = await browser.newContext();
  let state = makeState(), config={configured:true,require_google_registration:true}, googleStatus='ready';
  const calls = [];
  await context.route('https://accounts.google.com/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Mock Google</title><p>Verified mock account</p>'}));
  await context.route('**/api/**',async route => {
    const request=route.request(), endpoint=new URL(request.url()).pathname;
    const body=request.postDataJSON();calls.push({endpoint,body,headers:request.headers()});
    let result;
    if(endpoint==='/api/auth/google/open') {await route.fulfill({contentType:'text/html',body:'<!doctype html><title>Mock OAuth</title><p>Verified mock account</p>'});return;}
    if(endpoint==='/api/auth/google/config') result={ok:true,...config};
    else if(endpoint==='/api/auth/google/start') result={ok:true,flow_id:'test-flow',poll_secret:'poll-secret-body-only',authorization_url:origin+'/api/auth/google/open?flow=test-flow&open=mock-open',expires_in:600,poll_after:3};
    else if(endpoint==='/api/auth/google/status') result={ok:true,status:googleStatus};
    else if(endpoint==='/api/auth/google/complete') result={ok:true,token:'mock-google-session',state};
    else if(endpoint==='/api/login') result={ok:true,token:'mock-password-session',state};
    else if(endpoint==='/api/state') result={ok:true,state};
    else if(endpoint==='/api/action') {
      if(body.type==='build' || body.type==='ship') {
        state.queue=[{id:'running-project',key:body.key,kind:body.type,level:2,amount:body.amount || 1,ends_at:Date.now()/1000+600,seconds:600}];
        const group=body.type==='build' ? 'buildings':'ships';state.catalog[group].forEach(item=>{item.enabled=false;});
      } else if(body.type==='plan_project') state.planned_orders.push({id:'planned-project',key:body.key,kind:body.kind,planet_id:state.planet_id,amount:body.amount,level:3,name:'Planned Project'});
      result={ok:true,state};
    } else if(endpoint==='/api/account/delete') result={ok:true,deleted:true};
    else if(endpoint==='/api/logout') result={ok:true};
    else throw Error('Unexpected API endpoint '+endpoint);
    await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
  });
  async function pageAt({signedIn=false,lang='pl'}={}) {
    const page=await context.newPage();
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.addInitScript(({signedIn})=>{
      if(signedIn) sessionStorage.setItem('alien-colonies.session','mock-password-session');
      const original=window.setTimeout;
      window.setTimeout=(handler,delay,...args)=>original(handler,delay>=2000&&delay<=5000 ? 10:delay,...args);
    },{signedIn});
    await page.goto(`${origin}/play/?lang=${lang}`);
    await page.waitForSelector(signedIn ? '#game-screen:not([hidden])':config.configured ? '#auth-google':'#auth-form');
    return {page,errors};
  }

  // Free project starts once; every item in that lane then has one queue action.
  let {page,errors}=await pageAt({signedIn:true});
  await page.click('[data-tab="buildings"]');
  assert.equal(await page.locator('[data-building-card] [data-project-action]').count(),2);
  assert.equal(await page.locator('[data-planned-queue]').count(),0);
  await page.click('[data-building-card="metal_mine"] [data-project-action]');
  await page.waitForSelector('[data-building-card="metal_mine"] [data-plan-project]');
  assert.equal(await page.locator('[data-building-card] [data-project-action]').count(),2);
  assert.equal(await page.locator('[data-building-card] [data-project]').count(),0);
  assert.match(await page.locator('[data-building-card="laboratory"] [data-project-action]').textContent(),/Dodaj do kolejki/);
  assert.doesNotMatch(await page.locator('[data-building-card]').first().textContent(),/Premium/);
  await page.click('[data-building-card="laboratory"] [data-project-action]');
  await page.waitForSelector('#queue-subscription-dialog[open]');
  assert.equal(calls.filter(call=>call.endpoint==='/api/action').length,1);
  await page.click('[data-close-queue-subscription]');
  await page.click('[data-tab="ships"]');
  assert.match(await page.locator('[data-project-action]').textContent(),/Produkuj/);
  await page.click('[data-project-action]');
  await page.waitForSelector('[data-plan-project]');
  await page.click('[data-tab="defenses"]');
  assert.match(await page.locator('[data-project-action]').textContent(),/Dodaj do kolejki/);
  assert.deepEqual(errors,[]);
  await page.close();

  // A focused amount survives a quiet snapshot, while its action label updates.
  state=makeState();
  ({page,errors}=await pageAt({signedIn:true}));
  await page.click('[data-tab="ships"]');
  await page.clock.install();
  await page.fill('[data-batch]','7');
  state.queue=[{id:'other-ship',kind:'defense',key:'turret',amount:1,ends_at:Date.now()/1000+600,seconds:600}];
  state.catalog.ships[0].enabled=false;
  await page.clock.fastForward(13000);
  await page.waitForSelector('[data-plan-project]');
  assert.equal(await page.locator('[data-batch]').inputValue(),'7');
  assert.equal(await page.locator('[data-project-action]').count(),1);
  assert.deepEqual(errors,[]);
  await page.close();

  // A premium queue button sends a planned order; empty upsell panels stay absent.
  state=makeState();state.premium.queue_planning_active=true;state.catalog.buildings.forEach(item=>{item.enabled=false;item.planning_enabled=true;});
  state.queue=[{id:'active',kind:'build',key:'metal_mine',level:2,ends_at:Date.now()/1000+600,seconds:600}];
  ({page,errors}=await pageAt({signedIn:true}));
  await page.click('[data-tab="buildings"]');
  await page.click('[data-building-card="laboratory"] [data-project-action]');
  await page.waitForSelector('[data-planned-queue]');
  assert.equal(calls.at(-1).body.type,'plan_project');
  assert.equal(await page.locator('[data-queue-subscription]').count(),0);
  assert.deepEqual(errors,[]);
  await page.close();

  // Google registration asks for a name only after verification, then claims via POST.
  state=makeState();googleStatus='needs_name';
  ({page,errors}=await pageAt());
  await page.click('#auth-register');
  assert.equal(await page.locator('#auth-form').isVisible(),false);
  await page.click('#auth-google');
  await page.waitForSelector('#google-name-dialog[open]');
  await page.fill('#google-empire-name','New Empire');
  await page.click('#google-name-submit');
  await page.waitForSelector('#game-screen:not([hidden])');
  const complete=calls.findLast(call=>call.endpoint==='/api/auth/google/complete');
  assert.equal(complete.body.name,'New Empire');
  assert.equal(complete.body.poll_secret,'poll-secret-body-only');
  assert.equal(new URL(page.url()).searchParams.has('token'),false);
  assert.deepEqual(errors,[]);
  await page.close();

  // Legacy login remains available with Google configured; explicit linking reauthenticates.
  googleStatus='ready';state=makeState();
  ({page,errors}=await pageAt());
  await page.fill('#empire-name','Test Empire');await page.fill('#password','mock-password');await page.click('#auth-submit');
  await page.waitForSelector('#game-screen:not([hidden])');
  await page.click('#open-settings');
  assert.equal(await page.locator('.queue-subscription-panel').count(),0);
  assert.equal(await page.locator('#google-link-password').isVisible(),true);
  await page.fill('#google-link-password','mock-password');await page.click('[data-google-link]');
  await page.waitForFunction(()=>document.querySelector('#google-flow-status').hidden);
  const link=calls.findLast(call=>call.endpoint==='/api/auth/google/start');
  assert.equal(link.body.mode,'link');assert.equal(link.body.password,'mock-password');assert.match(link.headers.authorization,/Bearer mock-password-session/);
  assert.equal(await page.locator('#account-delete-password').getAttribute('required'),'');
  assert.deepEqual(errors,[]);
  await page.close();

  // Google-only deletion has no password field and needs both typed name and confirmation.
  state=makeState();state.account={google_linked:true,password_login_enabled:false};
  ({page,errors}=await pageAt({signedIn:true}));
  await page.click('#open-settings');assert.equal(await page.locator('#account-delete-password').count(),0);
  const deletesBefore=calls.filter(call=>call.endpoint==='/api/account/delete').length;
  await page.fill('#account-delete-name','Wrong Empire');await page.click('#account-delete-form button[type="submit"]');
  assert.equal(calls.filter(call=>call.endpoint==='/api/account/delete').length,deletesBefore);
  await page.fill('#account-delete-name','Test Empire');await page.click('#account-delete-form button[type="submit"]');
  await page.waitForSelector('#confirm-dialog[open]');
  assert.equal(calls.filter(call=>call.endpoint==='/api/account/delete').length,deletesBefore);
  await page.click('#confirm-dialog button[value="confirm"]');await page.waitForSelector('#auth-screen:not([hidden])');
  const deletion=calls.findLast(call=>call.endpoint==='/api/account/delete');assert.deepEqual(deletion.body,{password:'',confirmation:'DELETE ACCOUNT'});
  assert.equal(await page.locator('#auth-google').isEnabled(),true);
  assert.deepEqual(errors,[]);
  await page.close();

  // Missing OAuth configuration retains legacy access. New labels exist in every locale.
  config={configured:false,require_google_registration:false};state=makeState();
  ({page,errors}=await pageAt());
  await page.waitForFunction(()=>document.querySelector('#google-auth-options').hidden);
  await page.click('#auth-register');assert.equal(await page.locator('#auth-form').isVisible(),true);
  assert.deepEqual(errors,[]);await page.close();
  for(const language of ['pl','en','de','es','fr']) {
    const catalog=JSON.parse(fs.readFileSync(path.join(root,'play/locales',language+'.json'),'utf8'));
    for(const key of ['Dodaj do kolejki','Kontynuuj przez Google','Wybierz nazwę imperium','Trwale usuń konto']) assert.ok(catalog[key],`${language} missing ${key}`);
  }
  assert.ok(calls.filter(call=>call.endpoint==='/api/auth/google/status').every(call=>call.body.poll_secret==='poll-secret-body-only'));
  console.log('PASS: single project actions, free/premium queues, shared lanes, quiet input preservation, Google creation/linking/legacy login, Google-only deletion, five locale catalogs.');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();server.close();});
