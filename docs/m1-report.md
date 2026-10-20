# M1 阶段报告

模型定价修订：增加可编辑的生效日期区间、同模型启用区间重叠校验，以及按对话调用日期计算的“待设置价格”缺口列表。未配置、日期未覆盖与已停用会分别标注；补价预填缺口日期并刷新列表。仍仅在 M1 Mock 服务内实现，真实价格引擎与数据库未接入。最新完整测试为后端 13 passed、浏览器 18 passed（21.9 秒）、bundle 3 passed，合计 34；类型检查与 lint 通过。新增截图 `build/m1/prices-pending.png`、`prices-ranges.png` 已视觉核对。

第二轮页面批注修订：筛选下拉框去除前置小字，统一胶囊圆角与自绘下拉箭头，保留无障碍名称；所有饼图仅常驻显示名称，Tokens/费用数值和百分比通过悬停显示。`playwright test review.spec.ts` 2 项通过，覆盖 5 个饼图的常驻标注和 Tokens/费用 Tooltip；本轮未修改后端。

页面批注修订（2026-10-15，仍属 M1）：移除请求/会话表独立搜索栏，保留图表联动筛选；导航采用本地子集化 Google Material Symbols 字体（4,984 bytes，Apache-2.0）；页面/图表说明改为标题旁 information 图标点击展开，保留明显 Mock 标签与实际错误。增加键盘/外部点击关闭、字体本地加载与无 Google 运行时请求、390px 提示框边界测试。原有 14 项浏览器回归通过，新增 1 项验收用例修正共享 fixture 数量假设后单独通过；3 项 bundle 测试、类型检查及 lint 通过。本次未修改后端业务。修订后 JS 934,046 bytes、CSS 13,414 bytes。补充截图为 `build/m1/review-models.png` 与 `review-requests.png`。以下保留首轮交付记录。

Milestone:

M1：React 页面还原与 Mock 交互，版本 0.2.0。按用户明确选择开始 M1；本阶段不实施 M2 SQLite、M3 采集或 M4 远端部署。

已完成:

- 9 张原型对应的概览、使用分析、MCP 分析、用量明细、对话审计和人员设置三页；会话详情与模型设置按规格补充设计。保留原生 Dashboard 单 Tab、宿主 React 与 IIFE 加载方式。
- 浅紫 Material 3 布局、局部样式、独立导航、日期/部门/人员/服务筛选、清除、搜索、排序、20/50/100 分页、请求详情与会话工具两层折叠。
- ECharts 双轴趋势、堆叠柱、分布饼图、用户排行、MCP 面积趋势与 15 工具 dataZoom 排行；费用/Tokens 切换、Tooltip、点击筛选、可读数据列表。
- Mock 部门新建/编辑/删除与含成员阻止、人员映射新增编辑、双列表选择/全选/搜索和确认迁移；迁移不改历史快照。模拟价格生效版本保存，保留历史版本。
- 同一批虚构 fixtures 驱动 Mock API；查询、聚合、分页在开发后端执行，前端使用 Zod 校验响应。不存真实数据、不改 Hermes 人员或模型配置。
- 空结果、加载、403/503、畸形响应、重试与取消请求；模拟管理员/审计员/部门角色；390px 窄屏导航和表格横向滚动。
- Live 状态只显示业务未接入，不调用模拟接口、不展示虚构统计。Mock API、fixtures 和服务器均不进入原生安装包。
- 图表 ResizeObserver、click listener 与 ECharts 实例卸载清理；依赖许可随预构建产物交付。

新建/修改文件:

| 范围 | 文件 |
|---|---|
| 原生插件 | `plugin.yaml`、`pyproject.toml`、`dashboard/manifest.json`、`dashboard/plugin_api.py`：版本 0.2.0 / M1，仍仅 health；Hook 保持 M0 观察占位 |
| 前端入口/布局 | `frontend/src/App.tsx`、`Dashboard.tsx`、`theme.css` |
| 页面 | `frontend/src/pages/AnalyticsPage.tsx`、`RecordsPage.tsx`、`PeoplePage.tsx`、`ModelsPage.tsx` |
| 公共层 | `frontend/src/components/EChart.tsx`、`chart-options.ts`、`common.tsx`、`services/preview.ts`、`services/api.ts` |
| Mock | `dev/fixtures.py`、`dev/preview_api.py`、`dev/mock_api.py`、`frontend/mock/index.html`、`host.tsx` |
| 构建/依赖 | `frontend/package.json`、`pnpm-lock.yaml`、`scripts/build.mjs`、`scripts/check-bundle.mjs` |
| 测试 | `tests/test_m0.py`、`tests/test_m1_preview.py`、`frontend/tests/bundle.test.mjs`、`host.spec.ts`、`m1.spec.ts` |
| 打包 | `scripts/package_m1.py`；历史 `package_m0.py` 增加版本保护，避免错打 M0 包 |
| 文档 | `README.md` 状态说明、`CHANGELOG.md`、`docs/development.md`、`docs/compatibility.md`、`docs/m1-design.md`、本报告 |
| 预构建 | `dashboard/dist/index.js`、`style.css`、`index.js.LEGAL.txt`、`THIRD_PARTY_NOTICES.txt` |

执行测试与结果:

本机使用 Node 24.19.0、pnpm 11.25.0、工作区 Python 3.12.14；沿用已安装 Chromium。包脚本可从 frontend 用 pnpm 或 npm 执行；本机 PATH 无 npm，实际使用 pnpm 或对应可执行文件。

| 命令 | 结果 |
|---|---|
| `pnpm add echarts@6.0.0 zod@4.1.12` | 成功，锁定精确版本 |
| frontend：`tsc --noEmit` | 通过，strict TypeScript |
| frontend：`eslint src mock tests scripts playwright.config.ts` | 通过 |
| frontend：`node scripts/build.mjs` | PASS：单 IIFE、无未解析 imports、模块图无 React/ReactDOM |
| frontend：`node --test tests/bundle.test.mjs` | 3 passed |
| 根目录：`.venv/Scripts/python.exe -m pytest -q` | 11 passed，1 条已有 Starlette/httpx 弃用提示 |
| frontend：`playwright test`（HUM_PYTHON 指向工作区 Python） | 14 passed，最新完整运行 18.4 秒 |
| 根目录：`python scripts/package_m1.py` | 生成 `build/hermes-usage-manager-0.2.0-m1.zip` |
| 根目录：`python -m zipfile -t build/hermes-usage-manager-0.2.0-m1.zip` | 压缩包完整性通过 |

合计 28 项自动化测试通过。正式 JS 931,956 bytes，CSS 11,752 bytes；第三方 notices 16,496 bytes，JS legal notices 1,116 bytes。没有打包 React、ReactDOM 或 react/jsx-runtime；打包 ECharts/Zod 是有意的产品依赖。

浏览器覆盖：普通 script 一次注册；health 错误/畸形格式与恢复；接口取消；6 个概览图表；部门筛选与图表到明细联动；费用切换；MCP 服务、15 工具与完整 Tooltip；请求分页/排序/搜索/null；自定义日期校验/空态；8 次工具调用完整展开；配置写入/冲突/禁止删除/迁移；历史价格版本；角色拒绝、503/403/加载场景；Live 无 Mock 请求；刷新/后退；ECharts observer 数量从 6 到 4，再卸载到 0；390px 布局不产生内容容器溢出。

截图对照：`build/m1/` 共 12 张（overview、usage、mcp、requests、sessions、session-detail、people-users、people-departments、people-assignment、models、mobile-overview、mobile-requests）。已逐张视觉检查，与 9 张原型按相同信息架构对照；额外截图是补充设计和移动端，不声称来自原始原型。

尚未验证项:

- M1 0.2.0 尚未部署到用户远端 Hermes；已知远端成功截图属于 M0 0.1.0。本轮未连接或操作该服务器。
- 真实业务 API、SQLite、真实身份/RBAC、采集、真实会话 Adapter 与访问审计未实现，归属 M2/M3。
- 当前模拟会话为纯文本安全渲染；完整 Markdown 富文本、真实原文读取及 unavailable 源数据适配留待会话数据阶段。
- 图表和交互已在 Chromium 验证，其他浏览器尚未单独验收。

风险/需要确认:

本地 Mock 以固定基准日 2026-10-15 演示，所有价格、用量与人员均为虚构。设置改动只存在开发服务内存，重启重置。模拟角色 header 不能用于生产授权。正式安装包不带模拟 API；安装后会显示真实业务未接入，而不是这些示例统计。页面最终视觉仍需用户验收。

下一步建议:

本地运行 `frontend` 下 `pnpm run dev`，打开 `http://127.0.0.1:8765/` 验收各页面与顶部模拟场景。确认 M1 后再按单独指令开始 M2。**本轮到 M1 停止，不自动开发后续阶段。**
