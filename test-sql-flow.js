/**
 * E2E test for text2sql SQL flow:
 * 1. Login as atm_user (tenant_id=1) → generate SQL → verify tenant_id=1 injected
 * 2. Login as gtt_user (tenant_id=2) → generate SQL → verify tenant_id=2 injected
 * 3. Verify /suggest endpoint returns valid schema (no hallucinated table names)
 */
const { chromium } = require('playwright');

const BASE = 'http://localhost:8088';
const GOLDLAYER_VIEWS = [
  'delay_vw', 'congestion_rate_vw', 'punctuality_index_vw',
  'ridership_vw', 'number_of_trips_vw', 'number_of_stops_vw',
];

async function getToken(page, username, password) {
  const resp = await page.request.post(`${BASE}/api/v1/security/login`, {
    data: { username, password, provider: 'db' },
  });
  return (await resp.json()).access_token;
}

async function testUserFlow(browser, username, password, expectedTenantId) {
  console.log(`\n=== Testing ${username} (expected tenant_id=${expectedTenantId}) ===`);
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();

  const errors = [];
  const apiCalls = [];

  page.on('console', msg => {
    if (msg.type() === 'error' && !msg.text().includes('webpack-dev-server') && !msg.text().includes('Warning:')) {
      errors.push(msg.text().split('\n')[0]);
    }
  });
  page.on('response', resp => {
    if (resp.url().includes('/extensions/bi-ai/text2sql/')) {
      apiCalls.push({ url: resp.url(), status: resp.status() });
    }
  });

  // Login
  await page.goto(`${BASE}/login/`);
  await page.fill('#username', username);
  await page.fill('#password', password);
  await page.click('[type=submit]');
  await page.waitForURL('**/superset/welcome/**', { timeout: 15000 }).catch(() => {});

  // Go to SQL Lab
  await page.goto(`${BASE}/sqllab/`);
  await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(3000);

  // Check Ask AI panel visible
  const askAI = await page.locator('text=Ask AI').count();
  console.log(`  Ask AI panel: ${askAI > 0 ? '✅' : '❌'}`);

  // Select KPI Data (goldlayer) database
  const dbSelector = page.locator('[data-test="select-database"]').first();
  if (await dbSelector.count() > 0) {
    await dbSelector.click();
    await page.waitForTimeout(500);
    const goldlayerOption = page.locator('text=KPI Data (goldlayer)').first();
    if (await goldlayerOption.count() > 0) {
      await goldlayerOption.click();
      console.log(`  Database selected: ✅ KPI Data (goldlayer)`);
    } else {
      console.log(`  Database selected: ❌ KPI Data (goldlayer) not found in dropdown`);
    }
  }

  // Click example question in Ask AI panel
  const exampleBtn = page.locator('button', { hasText: 'Top 10 lines by average delay' }).first();
  if (await exampleBtn.count() > 0) {
    await exampleBtn.click();
    console.log(`  Example clicked: ✅`);
  }

  // Click Generate SQL
  const generateBtn = page.locator('button', { hasText: 'Generate SQL' }).first();
  if (await generateBtn.count() > 0) {
    await generateBtn.click();
    console.log(`  Generate SQL clicked: ✅`);

    // Wait for response (up to 30s for LLM)
    await page.waitForTimeout(500);
    const loadingGone = await page.waitForFunction(
      () => !document.querySelector('button')?.textContent?.includes('Generating'),
      { timeout: 30000 }
    ).catch(() => null);

    if (loadingGone) {
      // Check for success or error message
      const success = await page.locator('text=SQL generated').count();
      const errorBox = await page.locator('[style*="cf1322"]').count(); // red error color

      if (success > 0) {
        // Read the SQL in editor
        const editorContent = await page.evaluate(() => {
          const editor = document.querySelector('.ace_content');
          return editor ? editor.textContent : '';
        });

        const hasTenantFilter = editorContent.includes(`tenant_id = ${expectedTenantId}`) ||
                                editorContent.includes(`tenant_id=${expectedTenantId}`);
        const hasWrongTenant = editorContent.includes(`tenant_id = ${expectedTenantId === 1 ? 2 : 1}`);
        const hasGoldlayerView = GOLDLAYER_VIEWS.some(v => editorContent.toLowerCase().includes(v));

        console.log(`  SQL generated: ✅`);
        console.log(`  tenant_id=${expectedTenantId} injected: ${hasTenantFilter ? '✅' : '❌'}`);
        console.log(`  No wrong tenant leak: ${!hasWrongTenant ? '✅' : '❌ SECURITY ISSUE'}`);
        console.log(`  Uses goldlayer view: ${hasGoldlayerView ? '✅' : '⚠️  check table name'}`);
        if (!hasGoldlayerView) {
          console.log(`  Editor SQL preview: ${editorContent.slice(0, 200)}`);
        }
      } else if (errorBox > 0) {
        const errText = await page.locator('[style*="cf1322"]').first().textContent();
        console.log(`  Generate result: ❌ Error — ${errText?.slice(0, 100)}`);
      } else {
        console.log(`  Generate result: ⚠️  unknown state`);
      }
    } else {
      console.log(`  Generate result: ⚠️  timed out waiting for response`);
    }
  } else {
    console.log(`  Generate SQL btn: ❌ not found`);
  }

  // Test /suggest endpoint directly (schema check)
  const token = await getToken(page, username, password);
  const suggestResp = await page.request.post(`${BASE}/extensions/bi-ai/text2sql/generate`, {
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    data: { question: 'show average delay by line', database_id: 3 },
  }).catch(() => null);

  if (suggestResp) {
    const result = await suggestResp.json().catch(() => ({}));
    const sql = (result.sql || '').toLowerCase();
    const usesRealView = GOLDLAYER_VIEWS.some(v => sql.includes(v));
    const hasCorrectTenant = sql.includes(`tenant_id = ${expectedTenantId}`) || sql.includes(`tenant_id=${expectedTenantId}`);
    const status = suggestResp.status();
    console.log(`  API /generate status: ${status === 200 ? '✅' : '❌'} (${status})`);
    console.log(`  SQL uses real goldlayer view: ${usesRealView ? '✅' : '❌ hallucinated table'}`);
    console.log(`  tenant_id in SQL: ${hasCorrectTenant ? '✅' : '❌'}`);
    if (!usesRealView && result.sql) {
      console.log(`  SQL: ${result.sql.slice(0, 200)}`);
    }
  }

  await page.screenshot({ path: `/tmp/test-${username}.png` });
  console.log(`  Screenshot: /tmp/test-${username}.png`);

  await context.close();
  return errors.filter(e => !e.includes('webpack-dev-server'));
}

(async () => {
  const browser = await chromium.launch({ headless: true });

  const atmErrors = await testUserFlow(browser, 'atm_user', 'atm_pass123', 1);
  const gttErrors = await testUserFlow(browser, 'gtt_user', 'gtt_pass123', 2);

  console.log('\n=== SUMMARY ===');
  const allErrors = [...atmErrors, ...gttErrors];
  const criticalErrors = allErrors.filter(e =>
    e.includes('ChunkLoadError') || e.includes('Failed to initialize') || e.includes('tenant_id')
  );
  console.log(`Critical errors: ${criticalErrors.length === 0 ? '✅ None' : '❌ ' + criticalErrors.join(', ')}`);

  await browser.close();
  process.exit(criticalErrors.length > 0 ? 1 : 0);
})();
