import { test, expect } from './fixtures';

test('M Token display and extended presets keep counts separate and show sourced lifetime ranking', async ({ page }) => {
  await page.route('**/history/users?*', async (route) => {
    await route.fulfill({ json: { data: { available: true, source: 'hermes_session_model_usage', message: '测试历史汇总 · 与逐次采集分开展示', users: [
      { id: 'mao', name: '毛宁', tokens: 2240500936, api_calls: 7814, sessions: 52, unknown_rows: 0 },
      { id: 'zhong', name: '钟佳挺', tokens: 257578585, api_calls: 2518, sessions: 125, unknown_rows: 0 },
    ] }, meta: { data_source: 'mock', tz: 'Asia/Shanghai' } } });
  });
  await page.goto('/');
  await expect(page.locator('.hum-kpis')).toContainText('M Token');
  await page.locator('.hum-chart-data').first().locator('summary').click();
  await expect(page.locator('.hum-chart-data').first()).toContainText('M Token');
  const queries: URLSearchParams[] = [];
  page.on('request', (request) => { if (request.url().includes('/overview/summary?')) queries.push(new URL(request.url()).searchParams); });
  for (const [value, label, days] of [['90', '近 90 天', 90], ['180', '近半年', 180], ['365', '近一年', 365]] as const) {
    await page.getByRole('combobox', { name: '日期范围' }).click();
    await page.getByRole('listbox').getByRole('option', { name: label, exact: true }).click();
    await expect(page.getByRole('combobox', { name: '日期范围' })).toHaveAttribute('data-value', value);
    await expect.poll(() => {
      const q = queries[queries.length - 1];
      return q ? (new Date(q.get('to')!).getTime() - new Date(q.get('from')!).getTime()) / 86400000 : 0;
    }).toBe(days);
  }
  await page.getByRole('combobox', { name: '日期范围' }).click();
  await page.getByRole('listbox').getByRole('option', { name: '所有时间', exact: true }).click();
  await expect.poll(() => queries[queries.length - 1]?.get('all_time')).toBe('true');
  const history = page.getByRole('region', { name: 'Hermes 历史用量排行' });
  await expect(history).toContainText('与上方逐次采集统计分开展示');
  await history.getByText('查看历史排行数据', { exact: true }).click();
  await expect(history.locator('li').first()).toContainText('毛宁');
  await expect(history.locator('li').first()).toContainText('2,240.500936 M Token');
  await page.screenshot({ path: '../build/million-history.png', fullPage: true });
  await page.getByRole('combobox', { name: '日期范围' }).click();
  await page.getByRole('listbox').getByRole('option', { name: '近 7 天', exact: true }).click();
  await expect.poll(() => queries[queries.length - 1]?.has('all_time')).toBe(false);
  await expect(history).toHaveCount(0);
  const response = page.waitForResponse((r) => new URL(r.url()).pathname.endsWith('/requests') && r.status() === 200);
  await page.getByRole('navigation').getByRole('button', { name: '用量明细' }).click();
  const raw = (await (await response).json()).data as { input: number | null }[];
  await expect(page.locator('thead')).toContainText('M Token');
  const index = raw.findIndex((row) => row.input != null);
  expect(index).toBeGreaterThanOrEqual(0);
  const cell = page.locator('tbody tr').nth(index).locator('td').nth(4);
  await expect.poll(async () => Number((await cell.innerText()).replace(/,/g, ''))).toBe(raw[index].input! / 1_000_000);
});
