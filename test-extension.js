const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
  });

  const errors = [];
  const logs = [];

  const page = await context.newPage();

  page.on('console', msg => {
    const text = msg.text();
    if (msg.type() === 'error' && !text.includes('WebSocket') && !text.includes('scarf.sh')) {
      errors.push(text);
    }
    if (text.includes('Extensions initialized') || text.includes('text2sql') || text.includes('Ask AI')) {
      logs.push(`[${msg.type()}] ${text}`);
    }
  });

  page.on('response', resp => {
    const url = resp.url();
    if (url.includes('extensions')) {
      logs.push(`[HTTP ${resp.status()}] ${url}`);
    }
  });

  // Login
  await page.goto('http://localhost:8088/login/');
  await page.fill('#username', 'admin');
  await page.fill('#password', 'admin');
  await page.click('[type=submit]');
  await page.waitForURL('**/superset/welcome/**', { timeout: 15000 }).catch(() => {});
  console.log('Logged in, current URL:', page.url());

  // Go to SQL Lab
  await page.goto('http://localhost:8088/sqllab/');
  await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(3000);

  // Check for "Ask AI" panel in sidebar
  const askAI = await page.locator('text=Ask AI').count();
  console.log('\n=== RESULTS ===');
  console.log('Ask AI panel visible:', askAI > 0 ? '✅ YES' : '❌ NO');

  // Check extensions API
  const extResp = await page.request.get('http://localhost:8088/api/v1/extensions/', {
    headers: { 'Authorization': 'Bearer ' + await getToken(page) }
  }).catch(() => null);

  if (logs.length) {
    console.log('\nRelevant logs:');
    logs.forEach(l => console.log(' ', l));
  }

  if (errors.length) {
    console.log('\nErrors:');
    errors.forEach(e => console.log('  ❌', e));
  }

  // Take screenshot
  await page.screenshot({ path: '/tmp/sqllab-test.png', fullPage: false });
  console.log('\nScreenshot saved to /tmp/sqllab-test.png');

  await browser.close();
  process.exit(errors.some(e => e.includes('ChunkLoadError') || e.includes('Failed to initialize')) ? 1 : 0);
})();

async function getToken(page) {
  const resp = await page.request.post('http://localhost:8088/api/v1/security/login', {
    data: { username: 'admin', password: 'admin', provider: 'db' }
  });
  const json = await resp.json();
  return json.access_token;
}
