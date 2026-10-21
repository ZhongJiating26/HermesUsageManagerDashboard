import { test, expect } from './fixtures';

test('review changes use local Material Symbols and hide explanatory notes until clicked', async ({ page }) => {
  const external: string[] = [];
  page.on('request', (request) => { if (/fonts\.(googleapis|gstatic)\.com/.test(request.url())) external.push(request.url()); });
  await page.goto('/?hum_page=models');
  await expect(page.locator('tbody tr').first()).toBeVisible();
  await expect(page.locator('.hum-scope, .hum-quality')).toHaveCount(0);
  const note = page.getByText('价格变更不回改历史请求费用。', { exact: false });
  await expect(note).not.toBeVisible();
  await page.getByLabel('模型设置说明').click();
  await expect(note).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(note).not.toBeVisible();
  await page.getByLabel('模型设置说明').press('Enter');
  await expect(note).toBeVisible();
  await page.getByRole('heading', { name: '模型设置', exact: true }).click();
  await expect(note).not.toBeVisible();
  await page.evaluate(() => document.fonts.load('22px "Hermes Usage Material Symbols"'));
  expect(await page.getByRole('navigation').locator('.hum-material-icon').first().evaluate((node) => getComputedStyle(node).fontFamily)).toContain('Hermes Usage Material Symbols');
  expect(await page.evaluate(() => document.fonts.check('22px "Hermes Usage Material Symbols"'))).toBe(true);
  expect(external).toEqual([]);
  await page.screenshot({ path: '../build/m1/review-models.png', fullPage: true });
  await page.goto('/?hum_page=requests');
  await expect(page.locator('tbody tr')).toHaveCount(20);
  await expect(page.getByRole('textbox')).toHaveCount(0);
  await expect(page.locator('.hum-content .hum-toolbar')).toHaveCount(0);
  await page.screenshot({ path: '../build/m1/review-requests.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByLabel('用量明细说明').click();
  const box = await page.locator('.hum-page-heading .hum-info-panel').boundingBox();
  expect(box?.x).toBeGreaterThanOrEqual(0);
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(390);
});

test('filter pills have no prefixed text and all pie values appear only on hover', async ({ page }) => {
  await page.goto('/?hum_page=usage');
  await expect(page.locator('.hum-chart')).toHaveCount(4);
  const prefix = await page.getByRole('combobox', { name: '部门筛选', exact: true }).locator('..').evaluate((element) => Array.from(element.childNodes).filter((node) => node.nodeType === Node.TEXT_NODE).map((node) => node.textContent).join('').trim());
  expect(prefix).toBe('');
  const style = await page.getByRole('combobox', { name: '部门筛选', exact: true }).evaluate((element) => ({ radius: getComputedStyle(element).borderRadius, tag: element.tagName }));
  expect(style).toEqual({ radius: '999px', tag: 'BUTTON' });
  for (const name of ['人员用量', '模型用量']) {
    const chart = page.locator('.hum-card').filter({ has: page.getByRole('heading', { name, exact: true }) }).locator('.hum-chart');
    await expect(chart).not.toContainText(/Tokens|%/);
    await chart.locator('svg path[fill="#6750a4"]').first().hover();
    await expect(chart).toContainText('M Token');
    await expect(chart).toContainText('%');
    await page.mouse.move(1, 1);
  }
  await page.screenshot({ path: '../build/m1/review-usage-pies.png', fullPage: true });
  await page.goto('/?hum_page=overview');
  await expect(page.locator('.hum-chart')).toHaveCount(6);
  for (const name of ['部门分布', '模型分布', '提供商分布']) {
    const chart = page.locator('.hum-card').filter({ has: page.getByRole('heading', { name, exact: true }) }).locator('.hum-chart');
    await expect(chart).not.toContainText(/Tokens|%/);
  }
  const card = page.locator('.hum-card').filter({ has: page.getByRole('heading', { name: '部门分布', exact: true }) });
  await card.getByRole('button', { name: '费用', exact: true }).click();
  const chart = card.locator('.hum-chart');
  await expect(chart).not.toContainText(/USD|%|\$/);
  await chart.locator('svg path[fill="#6750a4"]').first().hover();
  await expect(chart).toContainText('USD');
  await expect(chart).toContainText('%');
});
