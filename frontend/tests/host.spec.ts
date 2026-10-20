import { test, expect } from './fixtures';

test('production IIFE renders, requests health, and remounts using host React', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const response = page.waitForResponse('**/api/plugins/hermes-usage-manager/health');
  await page.goto('/');
  expect((await (await response).json()).data_source).toBe('mock');
  await expect(page.getByRole('heading', { name: '概览', exact: true })).toBeVisible();
  await expect(page.getByText('模拟数据', { exact: true })).toBeVisible();
  await expect(page.locator('.hum-chart')).toHaveCount(6);
  await expect(page.locator('#mock-root')).toHaveAttribute('data-registrations', '1');
  await page.getByRole('button', { name: '卸载插件' }).click();
  await expect(page.locator('.hum-root')).toHaveCount(0);
  await page.getByRole('button', { name: '挂载插件' }).click();
  await expect(page.locator('.hum-chart')).toHaveCount(6);
  await page.screenshot({ path: '../build/m1/overview.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.locator('.hum-root').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('API error and malformed data stay visible; retry works without mock fallback', async ({ page }) => {
  await page.route('**/api/plugins/hermes-usage-manager/health', (route) => route.fulfill({ status: 503, body: '{}' }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('503');
  await expect(page.getByText('API 连接正常')).toHaveCount(0);
  await page.unroute('**/api/plugins/hermes-usage-manager/health');
  await page.route('**/api/plugins/hermes-usage-manager/health', (route) => route.fulfill({ json: { status: 'ok' } }));
  await page.getByRole('button', { name: '重新检查' }).click();
  await expect(page.getByRole('alert')).toContainText('响应格式不兼容');
  await page.unroute('**/api/plugins/hermes-usage-manager/health');
  await page.getByRole('button', { name: '重新检查' }).click();
  await expect(page.getByRole('heading', { name: '概览', exact: true })).toBeVisible();
});

test('pending health request is aborted when host removes the tab', async ({ page }) => {
  await page.route('**/api/plugins/hermes-usage-manager/health', () => {});
  await page.goto('/');
  await expect(page.getByRole('status')).toBeVisible();
  const aborted = page.waitForEvent('requestfailed', { predicate: (request) => request.url().endsWith('/health') });
  await page.getByRole('button', { name: '卸载插件' }).click();
  await aborted;
  await expect(page.locator('.hum-root')).toHaveCount(0);
});
