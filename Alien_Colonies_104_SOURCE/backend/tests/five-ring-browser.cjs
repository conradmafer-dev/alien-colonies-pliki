/* Chromium with public local geography; no accounts or production requests. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../web');
const fixture = JSON.parse(fs.readFileSync(process.env.AC_FIVE_RING_FIXTURE));
const output = process.env.AC_FIVE_RING_QA || '/tmp/ac-five-ring-qa';
fs.mkdirSync(output, {recursive:true});
const mime = {'.html':'text/html','.js':'text/javascript','.css':'text/css','.webp':'image/webp'};
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://localhost').pathname;
  if (name === '/') {res.setHeader('Content-Type','text/html');res.end('<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/play/map-buildings.css"><style>body{margin:0;background:#050c15;color:white}#map{height:530px}button{color:white;background:#192435}</style><div id="controls"><button data-map-zoom="out">−</button><span data-map-scale></span><button data-map-zoom="in">+</button><button data-map-zoom="reset">Home</button></div><div id="map" class="galaxy-map"><div class="galaxy-plane"><img class="galaxy-map-art" src="/assets/art/galaxies/aurora.1280.f6a893668a12.webp"><div class="galaxy-core"><strong>Aurora</strong></div></div></div>');return;}
  const file = path.resolve(root, '.' + name);
  if (!file.startsWith(root + path.sep)) {res.writeHead(403).end();return;}
  try {res.setHeader('Content-Type',mime[path.extname(file)] || 'application/octet-stream');res.end(fs.readFileSync(file));}
  catch {res.writeHead(404).end();}
});
let browser;
(async () => {
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  browser = await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{}),args:['--no-sandbox']});
  for (const [width,height] of [[360,800],[800,360],[1280,900]]) {
    const page = await browser.newPage({viewport:{width,height},hasTouch:width < 500});
    const errors = [];
    page.on('pageerror',e => errors.push(e.message));
    await page.goto('http://127.0.0.1:' + server.address().port);
    await page.evaluate(async fixture => {
      const {mountGalaxyMap} = await import('/play/galaxy-map.js');
      const map = document.querySelector('#map'), plane = map.querySelector('.galaxy-plane');
      if (innerHeight < 500) map.style.height = '320px';
      for (const s of fixture.systems) {
        const node = document.createElement('button');
        node.className = 'system-node unknown';node.dataset.system = s.id;
        node.innerHTML = '<span class="system-star">✦</span><span class="node-label">' + s.id.slice(1) + '</span>';
        plane.append(node);
      }
      window.fixture = fixture;window.mountMap = mountGalaxyMap;
      const outer = fixture.systems.find(s => s.ring_index === 3 && s.ring_order === 0);
      window.mapView = {scale:1,x:0,y:0,focusSystemId:outer.id};
      window.mapController = mountGalaxyMap(map,mapView,document.querySelector('#controls'),{systems:fixture.systems});
    },fixture);
    assert.equal(await page.locator('.system-node').count(),fixture.systems.length);
    assert.equal(await page.locator('.map-connection.bridge').count(),25);
    assert.equal(await page.locator('.map-connection.orbit').count(),fixture.systems.length);
    assert.equal(await page.locator('.expanded-ring-map').count(),1);
    assert.equal(await page.locator('[data-map-scale]').textContent(),'600%');
    const artTransform = await page.locator('.galaxy-map-art').evaluate(el => getComputedStyle(el).transform);
    assert.equal(artTransform,'none');
    // Check actual loaded textures, including Aurora's visibly off-frame core.
    for (const name of ['aurora','nexus','omega','zephyr','eclipse','void']) {
      const asset = fs.readdirSync(path.join(root,'assets/art/galaxies')).find(f => f.startsWith(name+'.1280.') && f.endsWith('.webp'));
      assert.ok(asset);
      await page.locator('.galaxy-map-art').evaluate(async (el,src) => {
        el.src=src;await el.decode();await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      },'/assets/art/galaxies/'+asset);
      const error = await page.evaluate(async name => {
        const {GALAXY_CORES}=await import('/play/galaxy-map.js');
        const plane=document.querySelector('.galaxy-plane'),art=plane.querySelector('.galaxy-map-art');
        const [x,y]=GALAXY_CORES[name];
        return {x:Math.abs(parseFloat(art.style.left)+parseFloat(art.style.width)*x-plane.clientWidth/2),
          y:Math.abs(parseFloat(art.style.top)+parseFloat(art.style.height)*y-plane.clientHeight/2)};
      },name);
      assert.ok(error.x < .01 && error.y < .01, name+' core aligns');
    }
    await page.locator('[data-map-zoom="reset"]').click();
    assert.equal(await page.locator('[data-map-scale]').textContent(),'100%');
    for (let i=0;i<12;i++) {
      const button=page.locator('[data-map-zoom="in"]');if(await button.isEnabled())await button.click();
    }
    assert.equal(await page.locator('[data-map-scale]').textContent(),'600%');
    await page.evaluate(() => {
      const inner = fixture.systems.find(s => s.ring_index === 4 && s.ring_order === 0);
      mapController.destroy();
      mapView = {scale:1,x:0,y:0,focusSystemId:inner.id};
      mapController = mountMap(document.querySelector('#map'),mapView,document.querySelector('#controls'),{systems:fixture.systems});
    });
    const result=await page.evaluate(() => {
      const inner=fixture.systems.find(s=>s.ring_index===4 && s.ring_order===0);
      const map=document.querySelector('#map').getBoundingClientRect(),star=document.querySelector('[data-system="'+inner.id+'"]').getBoundingClientRect();
      return {dx:Math.abs(star.x+star.width/2-(map.x+map.width/2)),dy:Math.abs(star.y+star.height/2-(map.y+map.height/2)),width:star.width,id:inner.id};
    });
    assert.ok(result.dx<1 && result.dy<1 && result.width>=43);
    await page.locator('[data-system="'+result.id+'"]').click();
    await page.locator('#map').screenshot({path:path.join(output,'five-rings-'+width+'.png')});
    assert.deepEqual(errors,[]);
    await page.close();
  }
  console.log('Chromium: five rings, current links, aligned art, 600% zoom, centre focus, touch targets; 3 viewports PASS');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();server.close();});

