import { test, expect } from '@playwright/test';

async function login(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page.getByLabel('管理员密码').fill('isolated-browser-password-2026');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '概览', exact: true })).toBeVisible();
}

test('independent entry logs in, renders Live UI without Hermes shell and logs out', async ({ page, request }) => {
  expect((await request.get('/api/plugins/hermes-usage-manager/health')).status()).toBe(401);
  await page.goto('/');
  await expect(page.getByLabel('管理员密码')).toBeVisible();
  await page.screenshot({ path: '../build/standalone-login.png', fullPage: true });
  await page.getByLabel('管理员密码').fill('invalid-password');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('密码不正确');
  await page.getByLabel('管理员密码').fill('isolated-browser-password-2026');
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await expect(page.getByRole('heading', { name: '概览', exact: true })).toBeVisible();
  await expect(page.getByText('实时数据', { exact: true })).toBeVisible();
  await page.screenshot({ path: '../build/standalone-desktop.png', fullPage: true });
  await expect(page.getByText('模拟数据 · 本地 Mock Host · 非真实 Hermes')).toHaveCount(0);
  await expect(page.locator('.hum-sidebar')).toHaveCount(1);
  await expect(page.getByText('插件管理', { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: '概览', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.cookie.includes('hum_session'))).toBe(false);
  await page.getByRole('button', { name: '退出登录' }).click();
  await expect(page.getByLabel('管理员密码')).toBeVisible();
  await expect(page.locator('.hum-sidebar')).toHaveCount(0);
});

test('collection status is one line with diagnostics collapsed by default', async ({ page }) => {
  await login(page);
  const quality = page.getByLabel('采集状态与数据质量', { exact: true });
  await expect(quality.locator('summary')).toContainText('当前范围');
  await expect(quality).not.toHaveAttribute('open');
  await expect(quality.getByRole('heading', { name: '采集与数据质量' })).not.toBeVisible();
  await quality.locator('summary').click();
  await expect(quality.getByRole('heading', { name: '采集与数据质量' })).toBeVisible();
  await expect(quality.getByText(/队列：待处理/)).toBeVisible();
  await quality.locator('summary').click();
  await expect(quality.getByRole('heading', { name: '采集与数据质量' })).not.toBeVisible();
  await page.screenshot({ path: '../build/standalone-quality-collapsed.png', fullPage: true });
});

test('standalone writes use CSRF and persist in the live database', async ({ page }) => {
  await login(page);
  const response = await page.evaluate(async () => {
    const session = await (await fetch('/api/auth/session')).json();
    return (await fetch('/api/plugins/hermes-usage-manager/people/departments', { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-hum-csrf': session.csrf }, body: JSON.stringify({ name: '独立入口验收部门' }) })).status;
  });
  expect(response).toBe(200);
  await page.getByRole('button', { name: '人员设置', exact: false }).click();
  await page.getByRole('tab', { name: '部门列表' }).click();
  await expect(page.getByRole('cell', { name: '独立入口验收部门', exact: true })).toBeVisible();
  const denied = await page.evaluate(async () => (await fetch('/api/plugins/hermes-usage-manager/people/departments', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'must-not-create' }) })).status);
  expect(denied).toBe(403);
});

test('an expired session returns to login without leaving dashboard data mounted', async ({ page, context }) => {
  await login(page);
  await context.clearCookies();
  await page.getByRole('button', { name: '模型设置', exact: false }).click();
  await expect(page.getByLabel('管理员密码')).toBeVisible();
  await expect(page.locator('.hum-sidebar')).toHaveCount(0);
});

test('all pages render at the independent port and mobile fits the viewport', async ({ page }) => {
  await login(page);
  for (const name of ['使用分析', 'MCP 分析', '用量明细', '对话审计', '人员设置', '模型设置']) {
    await page.getByRole('button', { name, exact: false }).click();
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
    await expect(page.getByText('加载失败', { exact: true })).toHaveCount(0);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '../build/standalone-mobile.png', fullPage: true });
});
