import { test, expect } from './fixtures';

test('prices support date ranges, edit existing entries, and resolve unpriced conversation models', async ({ page }) => {
  await page.goto('/?hum_page=models');
  const configured = page.locator('tbody tr').filter({ has: page.getByRole('cell', { name: 'claude-sonnet-4', exact: true }) }).first();
  await configured.getByRole('button', { name: '编辑', exact: true }).click();
  await expect(page.getByRole('dialog', { name: '编辑价格' })).toBeVisible();
  await page.getByLabel('输入未命中单价').fill('1.75');
  await page.getByLabel('生效结束日期').fill('2026-10-14');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(configured).toContainText('$1.75');
  await expect(configured).toContainText('2026-10-14');
  await page.getByRole('tab', { name: /待设置价格/ }).click();
  const unpriced = page.locator('tbody tr').filter({ has: page.getByRole('cell', { name: 'unpriced-demo', exact: true }) });
  await expect(unpriced).toHaveCount(1);
  await expect(unpriced).toContainText('未设置价格');
  const gaps = page.locator('tbody tr').filter({ has: page.getByRole('cell', { name: 'claude-sonnet-4', exact: true }) });
  await expect(gaps).toHaveCount(2);
  await expect(gaps.last()).toContainText('2026-10-15');
  await page.screenshot({ path: '../build/m1/prices-pending.png', fullPage: true });
  await unpriced.getByRole('button', { name: '设置价格', exact: true }).click();
  await expect(page.getByLabel('模型 ID')).toHaveValue('unpriced-demo');
  await expect(page.getByLabel('生效开始日期')).toHaveValue('2026-09-16');
  await expect(page.getByLabel('生效结束日期')).toHaveValue('2026-10-15');
  await page.getByLabel('输入未命中单价').fill('0.5');
  await page.getByLabel('输出单价').fill('1');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(unpriced).toHaveCount(0);
  await expect(page.getByRole('status')).toContainText('已补算生效日期内可计价的历史缺失费用');
  await page.getByRole('tab', { name: /已设置价格/ }).click();
  await expect(page.locator('tbody tr').filter({ has: page.getByRole('cell', { name: 'unpriced-demo', exact: true }) })).toHaveCount(1);
  await page.screenshot({ path: '../build/m1/prices-ranges.png', fullPage: true });
});

test('price form rejects reversed dates and overlapping enabled intervals', async ({ page }) => {
  await page.goto('/?hum_page=models');
  const row = page.locator('tbody tr').filter({ has: page.getByRole('cell', { name: 'deepseek-chat', exact: true }) }).first();
  await row.getByRole('button', { name: '新增版本', exact: true }).click();
  await page.getByLabel('生效开始日期').fill('2026-10-10');
  await page.getByLabel('生效结束日期').fill('2026-10-09');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('结束日期不能早于');
  await page.getByLabel('生效结束日期').fill('2026-10-12');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('区间不能重叠');
  await expect(page.getByRole('dialog')).toBeVisible();
});
