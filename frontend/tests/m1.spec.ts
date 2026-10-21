import type { Page } from '@playwright/test';
import { test, expect } from './fixtures';

async function select(page: Page, label: string, value: string) {
  await page.getByRole('combobox', { name: label, exact: true }).click();
  await page.getByRole('listbox').locator(`[role=option][data-value="${value}"]`).click();
}

async function navigate(page: Page, name: string) {
  await page.getByRole('navigation').getByRole('button', { name }).click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
}

test('charts follow filters, metrics and drill-down; all prototype pages render', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('.hum-chart')).toHaveCount(6);
  const departmentCard = page.locator('.hum-card').filter({ has: page.getByRole('heading', { name: '部门分布', exact: true }) });
  await departmentCard.getByRole('button', { name: '费用', exact: true }).click();
  await expect(departmentCard.getByText('仅已知价格的估算费用', { exact: false })).not.toBeVisible();
  await departmentCard.getByLabel('部门分布说明').click();
  await expect(departmentCard.getByText('仅已知价格的估算费用')).toBeVisible();
  await page.getByRole('heading', { name: '概览', exact: true }).click();
  await departmentCard.locator('.hum-chart-data>summary').click();
  await departmentCard.getByRole('button', { name: '研发部' }).click();
  await expect(page.getByRole('heading', { name: '用量明细', exact: true })).toBeVisible();
  await expect(page.getByRole('combobox', { name: '部门筛选', exact: true })).toHaveAttribute('data-value', 'd1');
  await expect(page.locator('tbody tr')).toHaveCount(20);
  await navigate(page, '使用分析');
  await select(page, '部门筛选', 'd2');
  await expect(page.locator('.hum-chart')).toHaveCount(4);
  await page.screenshot({ path: '../build/m1/usage.png', fullPage: true });
  await navigate(page, 'MCP 分析');
  await select(page, 'MCP 服务筛选', 'catalog');
  await expect(page.locator('.hum-chart')).toHaveCount(2);
  await page.locator('summary').filter({ hasText: '全部工具详情' }).click();
  await expect(page.locator('tbody tr')).toHaveCount(8);
  await select(page, 'MCP 服务筛选', '');
  await expect(page.locator('tbody tr')).toHaveCount(15);
  await page.locator('.hum-chart').last().locator('svg path[fill="#9980d0"]').first().hover();
  await expect(page.locator('.hum-chart').last()).toContainText('接口标识');
  await page.mouse.move(10, 10);
  await page.screenshot({ path: '../build/m1/mcp.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('request pagination, sort, unknown fields and modal without a search toolbar', async ({ page }) => {
  await page.goto('/?hum_page=requests');
  await expect(page.locator('tbody tr')).toHaveCount(20);
  const first = await page.locator('tbody tr').first().innerText();
  await page.getByRole('button', { name: '下一页' }).click();
  await expect(page.locator('.hum-page-number')).toContainText('2/');
  await expect(page.locator('tbody tr').first()).not.toHaveText(first);
  await select(page, '每页条数', '50');
  await expect(page.locator('tbody tr')).toHaveCount(50);
  await page.getByRole('button', { name: '输入 ↕' }).click();
  await select(page, '部门筛选', 'd1');
  await page.getByRole('combobox', { name: '人员筛选', exact: true }).click();
  await expect(page.getByRole('listbox').getByRole('option')).toHaveCount(5);
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '清除筛选' }).click();
  await expect(page.getByLabel('搜索请求或模型')).toHaveCount(0);
  await page.getByRole('button', { name: /请求时间/ }).click();
  await expect(page.locator('tbody tr')).toHaveCount(50);
  const failed = page.locator('tbody tr').filter({ has: page.locator('.hum-failed') }).first();
  await expect(failed).toContainText('—');
  await failed.locator('.hum-row-link').click();
  await expect(page.getByRole('dialog', { name: '请求详情' })).toBeVisible();
  await expect(page.getByRole('dialog')).toContainText('failed');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('tbody tr')).toHaveCount(50);
  await page.screenshot({ path: '../build/m1/requests.png', fullPage: true });
});

test('custom date validates, empty state does not draw zero charts', async ({ page }) => {
  await page.goto('/');
  await select(page, '日期范围', 'custom');
  await page.getByLabel('开始日期').fill('2026-10-20');
  await page.getByLabel('结束日期').fill('2026-10-15');
  await page.getByRole('button', { name: '应用', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('有效的日期范围');
  await page.getByLabel('开始日期').fill('2025-01-01');
  await page.getByLabel('结束日期').fill('2025-01-02');
  await page.getByRole('button', { name: '应用', exact: true }).click();
  await expect(page.getByText('当前筛选范围暂无数据')).toBeVisible();
  await expect(page.locator('.hum-chart')).toHaveCount(0);
  await page.getByRole('button', { name: '清除筛选' }).click();
  await expect(page.locator('.hum-chart')).toHaveCount(6);
});

test('session detail retains all eight tool calls with nested expansion', async ({ page }) => {
  await page.goto('/?hum_page=sessions');
  await expect(page.locator('tbody tr')).toHaveCount(20);
  await page.screenshot({ path: '../build/m1/sessions.png', fullPage: true });
  await page.locator('.hum-row-link').first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.locator('.hum-tool-group>summary').click();
  await expect(page.locator('.hum-tool-group>summary')).toContainText('工具调用 8 次');
  await expect(page.locator('.hum-tool-group>summary')).toContainText('成功 7 / 失败 1');
  await expect(page.locator('.hum-tool-group details')).toHaveCount(8);
  await page.locator('.hum-tool-group details').first().locator('summary').click();
  await expect(page.getByText('模拟结果：虚构商品趋势摘要。', { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: '../build/m1/session-detail.png', fullPage: true });
});

test('department create/edit/delete and blocked deletion show server feedback', async ({ page }) => {
  await page.goto('/?hum_page=people');
  await expect(page.locator('tbody tr')).toHaveCount(12);
  await page.screenshot({ path: '../build/m1/people-users.png', fullPage: true });
  await page.getByRole('tab', { name: '部门列表' }).click();
  await page.screenshot({ path: '../build/m1/people-departments.png', fullPage: true });
  await page.getByRole('button', { name: '删除部门 研发部', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: '确认', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('请先迁移成员');
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await page.getByRole('button', { name: '新建部门' }).click();
  await page.getByRole('dialog').getByLabel('名称', { exact: true }).fill('演示新部门');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.getByRole('cell', { name: '演示新部门', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '编辑部门 演示新部门', exact: true }).click();
  await page.getByRole('dialog').getByLabel('名称', { exact: true }).fill('演示已改名');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.getByRole('cell', { name: '演示已改名', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '删除部门 演示已改名', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: '确认', exact: true }).click();
  await expect(page.getByRole('cell', { name: '演示已改名', exact: true })).toHaveCount(0);
});

test('assignment confirms migration, prevents same-department moves; user mapping edits', async ({ page }) => {
  await page.goto('/?hum_page=people');
  await page.getByRole('tab', { name: '部门分配' }).click();
  await select(page, '左侧部门', 'd1');
  await select(page, '右侧部门', 'd2');
  await page.screenshot({ path: '../build/m1/people-assignment.png', fullPage: true });
  const leftList = page.locator('.hum-assignment-side').first();
  const person = await leftList.locator('.hum-person').first().locator('span').innerText();
  await leftList.locator('.hum-person').first().getByRole('checkbox').check();
  await page.getByRole('button', { name: '移到右侧 (1)' }).click();
  await expect(page.getByRole('dialog')).toContainText('1 人迁移到');
  await page.getByRole('button', { name: '确认', exact: true }).click();
  await expect(page.locator('.hum-assignment-side').last().getByText(person, { exact: true })).toBeVisible();
  await select(page, '右侧部门', 'd1');
  await expect(page.getByRole('button', { name: /移到右侧/ })).toBeDisabled();
  await page.getByRole('tab', { name: '用户列表' }).click();
  await page.getByLabel('搜索用户', { exact: true }).fill(person);
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await page.getByRole('button', { name: `编辑用户 ${person}`, exact: true }).click();
  await page.getByLabel('名称', { exact: true }).fill(`${person}（测试）`);
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.locator('tbody')).toContainText(`${person}（测试）`);
});

test('prices add a new effective version and preserve original', async ({ page }) => {
  await page.goto('/?hum_page=models');
  await expect(page.locator('tbody tr')).toHaveCount(5);
  await page.screenshot({ path: '../build/m1/models.png', fullPage: true });
  await page.locator('tbody tr').first().getByRole('button', { name: '新增版本', exact: true }).click();
  await page.getByLabel('生效开始日期').fill('2026-10-16');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.locator('tbody tr')).toHaveCount(6);
  await expect(page.locator('tbody')).toContainText('2026-10-01');
  await expect(page.locator('tbody')).toContainText('2026-10-16');
});

test('custom dropdowns support unassigned departments, keyboard and both migration directions', async ({ page }) => {
  await page.goto('/?hum_page=people');
  await page.getByRole('button', { name: '新增映射' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('名称', { exact: true }).fill('未分配测试成员');
  await dialog.getByLabel('Open ID').fill('unassigned-browser-test');
  const department = dialog.getByRole('combobox', { name: '主部门' });
  await expect(department).toHaveText('未分配部门');
  await department.focus();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('listbox')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeVisible();
  await expect(department).toBeFocused();
  await dialog.getByRole('button', { name: '保存', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await select(page, '人员部门筛选', '');
  await expect(page.locator('tbody')).toContainText('未分配测试成员');
  await page.getByRole('tab', { name: '部门分配' }).click();
  const left = page.locator('.hum-assignment-side').first();
  const right = page.locator('.hum-assignment-side').last();
  await expect(page.getByRole('combobox', { name: '左侧部门' })).toHaveText('未分配部门');
  await left.locator('.hum-person').filter({ hasText: '未分配测试成员' }).getByRole('checkbox').check();
  await page.getByRole('button', { name: '移到右侧 (1)' }).click();
  await page.getByRole('dialog').getByRole('button', { name: '确认', exact: true }).click();
  await expect(right).toContainText('未分配测试成员');
  await expect(left).not.toContainText('未分配测试成员');
  await right.locator('.hum-person').filter({ hasText: '未分配测试成员' }).getByRole('checkbox').check();
  await page.getByRole('button', { name: '← 移到左侧 (1)' }).click();
  await expect(page.getByRole('dialog')).toContainText('未分配部门');
  await page.getByRole('dialog').getByRole('button', { name: '确认', exact: true }).click();
  await expect(left).toContainText('未分配测试成员');
  await page.reload();
  await page.getByRole('tab', { name: '部门分配' }).click();
  await expect(page.locator('.hum-assignment-side').first()).toContainText('未分配测试成员');
  await expect(page.locator('.hum-root select')).toHaveCount(0);
  await page.getByRole('combobox', { name: '左侧部门' }).click();
  await expect(page.getByRole('option', { name: '未分配部门', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('listbox')).toBeVisible();
  await page.screenshot({ path: '../build/unassigned-dropdown.png', animations: 'disabled' });
  await page.getByRole('heading').first().click();
  await expect(page.getByRole('listbox')).not.toBeVisible();
});

test('error, empty, denied and slow scenarios are explicit', async ({ page }) => {
  await page.goto('/?scenario=error');
  await expect(page.getByRole('alert')).toContainText('503');
  await page.getByRole('button', { name: '重试', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('503');
  await page.goto('/?scenario=forbidden');
  await expect(page.getByRole('alert')).toContainText('无权访问');
  await page.goto('/?scenario=empty');
  await expect(page.getByText('当前筛选范围暂无数据')).toBeVisible();
  await expect(page.locator('.hum-chart')).toHaveCount(0);
  await page.goto('/?scenario=slow');
  await expect(page.getByRole('status', { name: '加载中' })).toBeVisible();
  await expect(page.locator('.hum-chart')).toHaveCount(6);
  await page.goto('/?role=department&hum_page=sessions');
  await expect(page.getByRole('alert')).toContainText('无权访问此页面');
  await expect(page.getByRole('navigation').getByRole('button', { name: '人员设置' })).toBeDisabled();
});

test('live health never invokes preview endpoints or displays fixture analytics', async ({ page }) => {
  const previewCalls: string[] = [];
  page.on('request', (request) => { if (request.url().includes('/api/plugins/') && !request.url().endsWith('/health')) previewCalls.push(request.url()); });
  await page.route('**/health', async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    await route.fulfill({ json: { ...payload, data_source: 'live', capabilities: { ...payload.capabilities, business_api: false } } });
  });
  await page.goto('/');
  await expect(page.getByText('业务数据尚未接入', { exact: true })).toBeVisible();
  await navigate(page, '使用分析');
  await expect(page.getByText('业务数据尚未接入', { exact: true })).toBeVisible();
  await expect(page.locator('.hum-chart')).toHaveCount(0);
  expect(previewCalls).toEqual([]);
});

test('navigation restores on refresh/back and charts disconnect observers on unmount', async ({ page }) => {
  await page.addInitScript(() => {
    const global = window as typeof window & { humObservers: Set<ResizeObserver> };
    global.humObservers = new Set();
    const Native = window.ResizeObserver;
    window.ResizeObserver = class extends Native {
      constructor(callback: ResizeObserverCallback) { super(callback); global.humObservers.add(this); }
      disconnect() { global.humObservers.delete(this); super.disconnect(); }
    };
  });
  await page.goto('/');
  await expect(page.locator('.hum-chart')).toHaveCount(6);
  await navigate(page, '使用分析');
  await expect(page.locator('.hum-chart')).toHaveCount(4);
  expect(await page.evaluate(() => (window as typeof window & { humObservers: Set<ResizeObserver> }).humObservers.size)).toBe(4);
  await page.reload();
  await expect(page.getByRole('heading', { name: '使用分析', exact: true })).toBeVisible();
  await navigate(page, '用量明细');
  await page.goBack();
  await expect(page.getByRole('heading', { name: '使用分析', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '卸载插件', exact: true }).click();
  await expect(page.locator('.hum-root')).toHaveCount(0);
  expect(await page.evaluate(() => (window as typeof window & { humObservers: Set<ResizeObserver> }).humObservers.size)).toBe(0);
});

test('mobile drawer, charts and scrollable tables stay within host container', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.locator('.hum-chart')).toHaveCount(6);
  await page.screenshot({ path: '../build/m1/mobile-overview.png', fullPage: true });
  await page.getByRole('button', { name: '打开导航', exact: true }).click();
  await navigate(page, '用量明细');
  await expect(page.locator('tbody tr')).toHaveCount(20);
  expect(await page.locator('.hum-content').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: '../build/m1/mobile-requests.png', fullPage: true });
});
