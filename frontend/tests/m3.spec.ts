import { test, expect } from './fixtures';

test('quality diagnostics collapse behind one status line and report honest scope', async ({ page }) => {
  await page.goto('/?hum_page=usage');
  await expect(page.locator('.hum-chart')).toHaveCount(4);
  await expect(page.getByLabel('数据质量详情')).not.toBeVisible();
  const summary = page.getByLabel('采集状态与数据质量').locator('summary');
  await summary.click();
  await expect(page.getByLabel('数据质量详情')).toBeVisible();
  await expect(page.getByLabel('数据质量详情')).toContainText('当前数据库');
  await expect(page.getByLabel('数据质量详情')).toContainText('尚无采集记录');
  await expect(page.getByLabel('数据质量详情')).toContainText('缓存未知');
  await expect(page.getByLabel('数据质量详情')).toContainText('辅助用量未采集，不计为零');
  await expect(page.getByLabel('数据质量详情')).toContainText('接收时间');
  await page.screenshot({ path: '../build/m3/quality.png', fullPage: true });
  await page.getByRole('button', { name: '刷新数据质量' }).click();
  await expect(page.getByLabel('数据质量详情')).toContainText('unavailable');
  await summary.click();
  await expect(page.getByLabel('数据质量详情')).not.toBeVisible();
});

test('timeline scrolls continuously through bounded reads and preserves earlier messages', async ({ page }) => {
  const offsets: number[] = [];
  await page.route('**/sessions/*/timeline?**', async (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get('offset'));
    offsets.push(offset);
    const result = await (await route.fetch()).json();
    result.data.messages = offset === 0 ? [
      { id: 'tools', kind: 'tools', text: '', tools: [{ id: 'unknown', name: 'unknown-tool', success: null, args: '[已隐藏]', result: '[已隐藏]' }] },
      ...Array.from({ length: 99 }, (_, index) => ({ id: `message-${index}`, kind: 'assistant', text: `模拟历史消息 ${index}`, tools: [] })),
    ] : [{ id: 'last', kind: 'assistant', text: '末尾消息', tools: [] }];
    result.data.pagination = { offset, limit: 100, has_more: offset === 0, returned: offset === 0 ? 100 : 1 };
    await route.fulfill({ json: result });
  });
  await page.goto('/?hum_page=sessions');
  await page.locator('.hum-row-link').first().click();
  await expect(page.getByRole('dialog')).toContainText('含未知状态');
  await expect(page.getByRole('dialog')).toContainText('成功 0 / 失败 0');
  await expect(page.getByRole('button', { name: /上一段消息|下一段消息/ })).toHaveCount(0);
  await expect(page.locator('.hum-message')).toHaveCount(99);
  const conversation = page.getByRole('region', { name: '对话记录' });
  await conversation.evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await expect(page.locator('.hum-message')).toHaveCount(100);
  await expect(conversation).toContainText('末尾消息');
  await expect(conversation).toContainText('模拟历史消息 0');
  await expect(page.locator('.hum-session-metadata')).toContainText('101 条');
  expect(offsets).toEqual([0, 100]);
  await page.screenshot({ path: '../build/m3/timeline-page.png', fullPage: true });
});

test('continuous loading retries failures without losing content or skipping offsets', async ({ page }) => {
  let failed = false;
  const offsets: number[] = [];
  await page.route('**/sessions/*/timeline?**', async (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get('offset'));
    offsets.push(offset);
    if (offset === 100 && !failed) {
      failed = true;
      await route.fulfill({ status: 503, json: { error: { code: 'SESSION_CONTENT_UNAVAILABLE', message: '测试读取失败', request_id: 'test' } } });
      return;
    }
    const result = await (await route.fetch()).json();
    result.data.messages = [{ id: String(offset), kind: 'assistant', text: offset ? '重试后追加' : '已加载消息保留', tools: [] }];
    result.data.pagination = { offset, limit: 100, has_more: offset === 0, returned: offset === 0 ? 100 : 1 };
    await route.fulfill({ json: result });
  });
  await page.goto('/?hum_page=sessions');
  await page.locator('.hum-row-link').first().click();
  const conversation = page.getByRole('region', { name: '对话记录' });
  await expect(conversation.getByRole('alert')).toContainText('测试读取失败');
  await expect(conversation).toContainText('已加载消息保留');
  await conversation.getByRole('button', { name: '重试', exact: true }).click();
  await expect(conversation).toContainText('重试后追加');
  await expect(conversation).toContainText('已加载消息保留');
  expect(offsets).toEqual([0, 100, 100]);
});

test('continuous loading rejects nonadvancing source instead of requesting forever', async ({ page }) => {
  const offsets: number[] = [];
  await page.route('**/sessions/*/timeline?**', async (route) => {
    offsets.push(Number(new URL(route.request().url()).searchParams.get('offset')));
    const result = await (await route.fetch()).json();
    result.data.messages = [];
    result.data.pagination = { offset: 0, limit: 100, has_more: true, returned: 0 };
    await route.fulfill({ json: result });
  });
  await page.goto('/?hum_page=sessions');
  await page.locator('.hum-row-link').first().click();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('会话加载进度异常');
  expect(offsets).toEqual([0]);
});

test('adjacent tool groups stay together across automatic reads', async ({ page }) => {
  await page.route('**/sessions/*/timeline?**', async (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get('offset'));
    const result = await (await route.fetch()).json();
    result.data.messages = [{ id: `tools-${offset}`, kind: 'tools', text: '', tools: [{ id: `tool-${offset}`, name: `测试工具-${offset}`, success: true, args: '[已隐藏]', result: '[已隐藏]' }] }];
    result.data.pagination = { offset, limit: 100, has_more: offset === 0, returned: offset === 0 ? 100 : 1 };
    await route.fulfill({ json: result });
  });
  await page.goto('/?hum_page=sessions');
  await page.locator('.hum-row-link').first().click();
  await expect(page.locator('.hum-session-metadata')).toContainText('101 条');
  await expect(page.locator('.hum-tool-group')).toHaveCount(1);
  await expect(page.locator('.hum-tool-group>summary')).toContainText('2 次');
  await page.locator('.hum-tool-group>summary').click();
  await expect(page.locator('.hum-tool-item')).toHaveCount(2);
});

test('automatic reads stop at the safe viewing limit with explicit incomplete status', async ({ page }) => {
  const offsets: number[] = [];
  await page.route('**/sessions/*/timeline?**', async (route) => {
    const url = new URL(route.request().url());
    const offset = Number(url.searchParams.get('offset'));
    offsets.push(offset);
    expect(url.searchParams.get('limit')).toBe('100');
    const result = await (await route.fetch()).json();
    result.data.messages = [];
    result.data.pagination = { offset, limit: 100, has_more: true, returned: 100 };
    await route.fulfill({ json: result });
  });
  await page.goto('/?hum_page=sessions');
  await page.locator('.hum-row-link').first().click();
  await expect(page.getByRole('dialog').getByRole('status')).toContainText('后续内容尚未加载', { timeout: 20000 });
  expect(offsets).toEqual(Array.from({ length: 50 }, (_, index) => index * 100));
  await expect(page.getByRole('button', { name: /上一段消息|下一段消息/ })).toHaveCount(0);
});

test('missing real content is explicit instead of fabricated transcript', async ({ page }) => {
  await page.route('**/sessions/*/timeline?**', (route) => route.fulfill({ status: 503, json: { error: { code: 'SESSION_CONTENT_UNAVAILABLE', message: '会话正文源未启用', request_id: 'test-only' } } }));
  await page.goto('/?hum_page=sessions');
  await page.locator('.hum-row-link').first().click();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('会话正文源未启用');
  await expect(page.locator('.hum-message')).toHaveCount(0);
});
