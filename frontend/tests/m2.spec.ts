import { test, expect } from './fixtures';

test('SQLite configuration survives refresh and records are not repriced', async ({ page }) => {
  await page.goto('/?hum_page=models');
  const before = await page.request.get('/api/plugins/hermes-usage-manager/overview/kpis?from=2026-10-09&to=2026-10-16');
  const original = (await before.json()).data.cost;
  const row = page.locator('tbody tr').filter({ has: page.getByRole('cell', { name: 'gpt-5', exact: true }) });
  await row.getByRole('button', { name: '编辑', exact: true }).click();
  await page.getByLabel('输入未命中单价').fill('9.123456');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(row).toContainText('$9.1235');
  await page.reload();
  await expect(row).toContainText('$9.1235');
  const after = await page.request.get('/api/plugins/hermes-usage-manager/overview/kpis?from=2026-10-09&to=2026-10-16');
  expect((await after.json()).data.cost).toBe(original);
});

test('Live mode uses business routes and rejects responses labelled Mock', async ({ page }) => {
  const called: string[] = [];
  page.on('request', (request) => { if (request.url().includes('/api/plugins/')) called.push(request.url()); });
  await page.route('**/health', async (route) => {
    const result = await (await route.fetch()).json();
    await route.fulfill({ json: { ...result, data_source: 'live' } });
  });
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('数据源不兼容');
  await expect(page.locator('.hum-chart')).toHaveCount(0);
  expect(called.some((url) => url.includes('/filters'))).toBe(true);
  expect(called.some((url) => url.includes('/preview/'))).toBe(false);
});

test('Live API contract can render without any mock fallback', async ({ page }) => {
  await page.route('**/api/plugins/hermes-usage-manager/**', async (route) => {
    const result = await (await route.fetch()).json();
    if (result.meta) result.meta.data_source = 'live';
    else result.data_source = 'live';
    await route.fulfill({ json: result });
  });
  await page.goto('/');
  await expect(page.locator('.hum-chart')).toHaveCount(6);
  await expect(page.getByText('实时数据', { exact: true })).toBeVisible();
  await page.screenshot({ path: '../build/m2/live-contract.png', fullPage: true });
});
