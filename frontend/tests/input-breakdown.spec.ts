import { test, expect } from './fixtures';

for (const state of ['complete', 'missing', 'zero'] as const) {
  test(`overview groups input once and handles ${state} breakdown`, async ({ page }) => {
    await page.route('**/overview/summary?*', async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      Object.assign(body.data.kpis, state === 'zero'
        ? { input_total: 0, input: 0, cached: 0, cache_write: 0, output: 0, total_tokens: 0, unknown_input_breakdown: 0 }
        : { input_total: 49079, input: 3, cached: 48134, cache_write: 942, output: 49, total_tokens: 49128, unknown_input_breakdown: state === 'missing' ? 1 : 0 });
      await route.fulfill({ response, json: body });
    });
    await page.goto('/');
    const card = page.getByRole('region', { name: '输入输出用量' });
    await expect(card.getByText('输入总量', { exact: true })).toBeVisible();
    await expect(card.getByText('输出总量', { exact: true })).toBeVisible();
    await expect(card.getByText('输入输出合计：', { exact: false })).toContainText(state === 'zero' ? '0 M Token' : '0.049128 M Token');
    const totals = card.locator('.hum-token-total');
    await expect(totals.first()).toContainText(state === 'zero' ? '0 M Token' : '0.049079 M Token');
    await expect(totals.last()).toContainText(state === 'zero' ? '0 M Token' : '0.000049 M Token');
    await expect(card.getByText('输入（未命中缓存）', { exact: true })).toHaveCount(0);
    if (state === 'complete') {
      await expect(card.getByText('98.07%', { exact: true })).toBeVisible();
      await expect(card.getByText('1.92%', { exact: true })).toBeVisible();
      await expect(card.getByText('0.01%', { exact: true })).toBeVisible();
      await expect(card.getByRole('meter')).toHaveCount(3);
      await page.screenshot({ path: '../build/input-breakdown/overview-desktop.png', fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      await expect(card.getByText('输入总量', { exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({ path: '../build/input-breakdown/overview-mobile.png', fullPage: true });
    } else {
      await expect(card.getByText('占比未知', { exact: true })).toHaveCount(3);
      await expect(card.getByRole('meter')).toHaveCount(0);
    }
  });
}
