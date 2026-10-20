# M1 页面与 Mock 契约

模型定价修订：已设置价格可编辑单价、起止日期及启用状态，仍可新增版本。日期均为 Asia/Shanghai 自然日，开始与结束当天均包含，结束留空表示长期；同提供商/模型的启用区间禁止重叠。新增 `GET /models/unpriced` 按 Mock 对话请求时间检查实际覆盖，未配置/日期未覆盖/价格停用按连续缺口分行列入“待设置价格”，展示请求数并预填缺口区间。`PATCH /models/prices/{id}` 编辑后重新计算缺口。新增 unpriced-demo 模型 fixture，合计 6 个调用模型、5 个初始价格配置；以上均为 M1 内存演示，不改真实账单或历史 fixture 费用。

最新页面批注：筛选下拉框去除前置“部门/人员/MCP 服务”等文字，保留 aria-label，使用胶囊圆角与统一箭头。全部饼图的常驻标注仅显示名称；Tokens/费用数值与百分比仅在悬停 Tooltip 显示。

M1 仅实现 React 页面、ECharts、模拟接口和交互。插件仍由 Hermes 注册组件，单一 `/usage-manager` Tab；内部以 `hum_page` query 参数切页，保留宿主其他 query。没有新增站点、独立生产服务或核心修改。

## 原型映射

| 原型 | 实现 / 截图（build/m1/） |
|---|---|
| 概览.png | 三组 KPI、费用细分、双轴趋势、部门堆叠、三分布饼图、用户排行 / overview.png |
| 使用分析.png | 部门日期联动、堆叠柱 + 活跃折线、人员/模型饼图、排行 / usage.png |
| MCP分析.png | 服务筛选、面积趋势、带 dataZoom 的全部工具排行、完整 Tooltip / mcp.png |
| 用量明细.png | 分页、排序、部门人员日期筛选、失败/未知值、请求详情；按用户批注移除独立搜索栏 / requests.png |
| 对话审计.png | 会话分页表、筛选、详情入口 / sessions.png |
| 对话审计-对话详情.png | 原图与列表相近；按规格补充摘要、消息与连续工具双层折叠 / session-detail.png |
| 人员设置-用户列表.png | 搜索、部门筛选、映射新增编辑、分页 / people-users.png |
| 人员设置-部门分配.png | 部门新建编辑删除，含成员禁止删除 / people-departments.png |
| 人员设置-部门分配-1.png | 双部门列表、搜索、多选/全选、确认迁移、同部门禁止 / people-assignment.png |
| 补充设计：模型设置 | USD/百万 Tokens、历史价格版本、新增生效日及启停字段 / models.png |

沿用浅紫侧栏/卡片、深紫选中胶囊、圆角与表格细线。增加小标题、Mock 标签、无障碍图表数据列表和必要操作列。根据用户页面批注，导航与 information 图标改为本地打包的 Google Material Symbols Outlined 字体，不依赖远程字体服务或额外 React 实例。说明性提示统一放在页面/图表标题旁的 information 图标内，点击展开，支持键盘、Escape 与点击外部关闭；Mock 标签和实际错误仍显式展示。

窄屏使用可展开的插件内导航，卡片单列，表格仅在自身容器滚动。所有发布 CSS 都以 `.hum-root` 限定，包括 dialog；Mock 宿主工具栏的样式只存在开发 HTML。

## 数据与阶段边界

- `dev/fixtures.py` 统一生成虚构数据：3 个部门、12 个用户、3 个 Profile、5 个模型/供应商、2 个 MCP 服务、15 个工具、30 天请求与会话；包含失败、缺缓存、未知费用、8 次连续工具调用的长会话。
- 固定模拟基准日 `2026-10-15`；近 7 天为 10-09 至 10-15（含两端）。查询 `start` 包含、`end` 不包含。页面标出 Asia/Shanghai。
- `input` 是模拟的输入未命中缓存，`cached` 是另一细分；它们不代表原始供应商 usage 字段。未知细分在表格中保留 null，统计只展示已知部分并提示缺失数量。
- 费用为虚构 fixture 值，按 60%/10%/30% 拆成模拟费用细分；没有真实报价含义。不是 M2 价格引擎。价格版本保存不反算既有 fixture 费用。
- 用户迁移只改变 Mock 当前映射，已有请求/工具/会话的部门快照不变。Mock 修改在同一服务进程内保留，重启即重置；未写 SQLite 或 Hermes 配置。
- `dev/mock_api.py` 单独挂载 `dev/preview_api.py`；真实 `dashboard/plugin_api.py` 仍只导出 health。发行包排除 dev 目录。
- UI 先验证 health。只有 `data_source=mock` 才调用 Mock 业务 API；Live 显示全部导航和业务不可用提示，不请求 fixture、不静默降级。
- 模拟角色通过开发宿主的专用 header 传给 Mock API，服务端拒绝越权；不能作为生产身份或 RBAC 的实现。Live 没有敏感业务接口。

## M1 Mock API 契约

前缀 `/api/plugins/hermes-usage-manager`。以下仅存在于开发宿主，不承诺真实 Hermes 已实现。

响应统一 `{data, meta:{data_source:'mock',tz:'Asia/Shanghai',total?,page?,page_size?}}`。前端 `services/preview.ts` 的 Zod schema 做运行时校验。生产 health 保留直接响应。错误使用 FastAPI `detail`；M2 再收敛正式错误 envelope。

| 方法 / 路径 | 用途 |
|---|---|
| GET /filters | 有权限的部门/人员、MCP 服务、模拟基准日 |
| GET /preview/analytics | M1 专用聚合：KPI、趋势、分布、排行；不从全量明细在浏览器聚合 |
| GET /requests、/sessions | 服务端筛选、排序、分页，`page_size<=100` |
| GET /sessions/{id}/timeline | 授权的模拟消息及完整工具分组 |
| GET/POST/PATCH /people/departments | 部门读取、新建、改名 |
| DELETE /people/departments/{id} | 含成员返回 409 |
| GET/POST/PATCH /people/users | 用户映射读取、新增、编辑，Open ID 冲突返回 409 |
| POST /people/assignments/move | 迁移用户主部门，不改历史记录 |
| GET/POST /models/prices | 列表与新增生效版本，同模型同日冲突返回 409 |

日期查询使用 `start/end`，筛选使用 `department_id/user_id/server_id`；表格增加 `page/page_size/sort/order/search`。M1 的 `/preview/analytics` 是明确的临时聚合契约，M2 将拆成 README 第 9 节的正式查询接口，并迁移前端 service；不将其冒充官方 Hermes SDK。

开发场景：URL `?scenario=empty|slow|error|forbidden`。角色：`?role=admin|auditor|department`。顶栏可直接切换。403、503、加载、无结果均有明确显示；请求变化与组件卸载会中止旧请求。

## 图表与详情

ECharts 6 使用 core 按需注册 Line/Bar/Pie、Tooltip/Grid/Legend/Aria/DataZoom、SVGRenderer、LabelLayout，见[官方按需引入说明](https://echarts.apache.org/handbook/en/basics/import/)。图表尺寸由 ResizeObserver 管理，卸载断开 observer、解绑事件并 dispose，见[官方生命周期说明](https://echarts.apache.org/handbook/en/concepts/chart-size/)。尊重 reduced-motion。

Tooltip 使用 richText 而非拼接 HTML。模型名在图上可截断，但 Tooltip 和数据列表保留完整值。MCP Tooltip 含工具标识、服务、次数、失败次数和平均耗时；15 个工具都可通过 dataZoom 和明细表访问。

会话内容由 React 文本节点安全输出，不执行 HTML，也不默认复制真实原文。当前 Mock 使用纯文本消息，完整 Markdown 富文本、源数据不可用适配及真实访问审计在后续真实会话阶段完善。原生 dialog 提供焦点限制、Escape 与关闭后的焦点恢复。

## 构建与许可

React/ReactDOM 仅为 Mock Host 的开发依赖；正式 TSX 使用 `SDK.React`。构建器拒绝 React 及其子路径的运行时导入，模块图只允许 ECharts/zrender/tslib/Zod；单 IIFE，无未解析 imports。

ECharts 等第三方库允许打包，发行 `dist/THIRD_PARTY_NOTICES.txt` 和构建器的 `index.js.LEGAL.txt` 保留许可文本。插件自身未擅自选定许可证。
