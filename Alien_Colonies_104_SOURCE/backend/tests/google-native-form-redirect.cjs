/* Chromium regression for the legacy Android confirmation form.
 * The form, headers and successful redirect are obtained from the real Python
 * HTTP handler with an isolated SQLite world and a fake OAuth provider.
 * Only Google's origin is mapped to a loopback server; no Google traffic,
 * production login or real credentials are used.
 * Run: node tests/google-native-form-redirect.cjs
 * Optional: CHROME_EXECUTABLE=/path/to/chromium PYTHON=python3
 */
const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require('playwright');

const fixtureCode = `
import json, re, sys
from urllib.parse import urlsplit
sys.path.insert(0, 'tests')
from test_google_signin import GoogleHTTPScenarios
case = GoogleHTTPScenarios()
case.setUp()
try:
    status, _, raw = case.request('/api/auth/google/start', {'mode':'login','client':'android'})
    assert status == 200, (status, raw)
    flow = json.loads(raw)
    opened = urlsplit(flow['authorization_url'])
    status, headers, raw = case.request(opened.path + '?' + opened.query)
    assert status == 200, (status, raw)
    document = raw.decode()
    csrf = re.search(r"name='csrf' value='([^']+)'", document).group(1)
    cookie = headers['Set-Cookie'].split(';', 1)[0]
    form = {'flow':flow['flow_id'],'csrf':csrf,'code':flow['verification_code']}
    confirmed, redirect, _ = case.request('/api/auth/google/confirm', form, form=True, headers={'Cookie':cookie})
    assert confirmed in (302, 303), (confirmed, redirect)
    fixture = {'html':document,'csp':headers['Content-Security-Policy'], 'form':form,
               'status':confirmed,'location':redirect['Location']}
    print('BROWSER_FIXTURE=' + json.dumps(fixture))
finally:
    case.tearDown()
`;

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${server.address().port}`));
  });
}
function close(server) { return new Promise(resolve => server.close(resolve)); }

let browser;
let source;
let destination;
(async () => {
  const fixtureResult = spawnSync(process.env.PYTHON || 'python3', ['-c', fixtureCode], {
    cwd:path.resolve(__dirname, '..'), encoding:'utf8', timeout:20000,
  });
  assert.equal(fixtureResult.status, 0, fixtureResult.stderr || fixtureResult.stdout);
  const line = fixtureResult.stdout.split('\n').find(line => line.startsWith('BROWSER_FIXTURE='));
  assert.ok(line, 'Real HTTP handler did not produce its browser fixture');
  const fixture = JSON.parse(line.slice('BROWSER_FIXTURE='.length));
  assert.equal(new URL(fixture.location).origin, 'https://accounts.google.com');

  let destinationHits = 0;
  let submissions = [];
  let policy;
  destination = http.createServer((req, res) => {
    destinationHits++;
    res.setHeader('Content-Type', 'text/html');
    res.end('<!doctype html><title>Mock Google</title><h1>Google reached</h1>');
  });
  const mockGoogle = await listen(destination);
  const redirectPath = new URL(fixture.location).pathname + new URL(fixture.location).search;
  source = http.createServer((req, res) => {
    if (req.url === '/api/auth/google/confirm') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        submissions.push(Object.fromEntries(new URLSearchParams(body)));
        res.writeHead(fixture.status, {Location:mockGoogle + redirectPath});
        res.end();
      });
      return;
    }
    res.writeHead(200, {'Content-Type':'text/html', 'Content-Security-Policy':policy});
    res.end(fixture.html);
  });
  const origin = await listen(source);
  browser = await chromium.launch({headless:true,
    ...(process.env.CHROME_EXECUTABLE ? {executablePath:process.env.CHROME_EXECUTABLE} : {}),
    args:['--no-sandbox', '--disable-dev-shm-usage'],
  });

  async function submit(csp) {
    policy = csp;
    submissions = [];
    destinationHits = 0;
    const page = await browser.newPage();
    const violations = [];
    await page.exposeFunction('recordPolicyViolation', event => violations.push(event));
    await page.addInitScript(() => document.addEventListener('securitypolicyviolation', event => {
      window.recordPolicyViolation({directive:event.effectiveDirective, blockedURI:event.blockedURI});
    }));
    await page.goto(origin + '/api/auth/google/open');
    await page.locator('input[name="code"]').fill(fixture.form.code);
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(200);
    const result = {violations, submissions:[...submissions], destinationHits, url:page.url()};
    await page.close();
    return result;
  }

  // A control reproduces the original production failure even with the exact
  // correct code: backend confirmation succeeds, but navigation is blocked.
  const oldPolicy = fixture.csp.replace(/form-action[^;]*/, "form-action 'self'");
  const broken = await submit(oldPolicy);
  assert.deepEqual(broken.submissions, [fixture.form]);
  assert.equal(broken.destinationHits, 0);
  assert.ok(broken.violations.some(event => event.directive === 'form-action'));

  // Keep the production policy unchanged except mapping the one allowed Google
  // origin to the local mock server. This fails if the deployed header regresses.
  const fixed = await submit(fixture.csp.replaceAll('https://accounts.google.com', mockGoogle));
  assert.deepEqual(fixed.submissions, [fixture.form]);
  assert.equal(fixed.destinationHits, 1, 'Correct confirmation was blocked before reaching Google');
  assert.equal(fixed.violations.length, 0);
  assert.equal(new URL(fixed.url).origin, mockGoogle);
  console.log('PASS: real legacy form submits once and follows OAuth redirect; old policy reproduces failure');
})().catch(error => {console.error(error); process.exitCode = 1;}).finally(async () => {
  if (browser) await browser.close();
  if (source) await close(source);
  if (destination) await close(destination);
});
