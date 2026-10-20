# M2 SQLite 与 API 契约

## 运行边界

生产只导出 `dashboard/plugin_api.py:router`，由 Hermes 挂载。入口通过路径哈希命名的 Python package 加载 backend，不修改 sys.path、不修改 Hermes 核心、不创建独立生产站点。Mock Host 位于 `dev/sqlite_api.py`，复用同一个 router，仅本地依赖覆盖注入模拟身份、Mock 数据库和虚构正文 Provider。旧 `dev/mock_api.py` 只保留 M1 内存契约回归，不是默认开发入口。

正式 IIFE 继续使用 SDK.React/SDK.fetchJSON；无 React/ReactDOM 生产运行时。先验证 health，再绑定预期 Mock/Live 来源；业务响应来源不匹配会报错，不显示样例或降级成功。

## 数据库

`USAGE_MANAGER_DB_PATH` 可指定外部绝对路径；未指定时尝试官方源码中的 `plugins.plugin_storage.plugin_data_dir`。缺失不回退插件源码目录。SQLite 文件不得放在插件安装/源码目录内部。首次建立版本迁移记录与 SHA256，已执行脚本变更或数据库版本较新时拒绝继续；升级不删除数据。0001 建表，0002 价格修订，0003 身份/usage 字段及索引，0004 部门历史区间约束。

连接启用外键、WAL、busy_timeout=2500ms；写事务 BEGIN IMMEDIATE，失败整体回滚。Unix 要求文件和父目录归当前用户所有，文件不允许其他用户读写，父目录不允许组/其他用户写入；新目录0700、文件0600。Windows 不声称已验证 ACL，部署者必须限制服务账户之外的访问。Mock/Live 模式标记持久化，禁止混用同一数据库。两个模式均不存 API key 或原始对话正文。

## 统计与事件

M2 只接收进程内、经过上游验证的归一化 ModelEvent/ToolEvent；没有公开事件写入 HTTP 接口，没有真实 Hook 采集。来源适配器必须提供语义可信的 usage 和稳定、逐 attempt 的 source_event_id；它不是可复用的 api_request_id。M3 负责把源事件映射为这个契约。

- input_total 包含 cache；uncached 仅在 total/cache 均已知时相减。total_tokens=input_total+output，不重复加 cache。
- 缺失字段保留 NULL，失败与辅助调用分别可计数。KPI/图表是各字段的已知部分；部分缺失时三个细分的独立聚合不保证等于独立 total 聚合。
- 费用使用 Decimal 单价乘 Tokens，逐组件四舍五入到微美元整数。输入/缓存/输出均可信且存在当时有效价才计算总费用，否则 unknown，不伪造零。
- 发生时冻结费用、price_id 和不可变 price_revision_id。编辑/停用/补价只影响以后入库，不重算旧请求；待设置列表反映当前配置是否覆盖历史调用日期，不表示历史费用已补算。
- 请求事件按 instance/profile/model/source_event_id 确定性去重；会话按 instance/profile/session_id 去重。数据库重开、事件重播不会重复统计。
- 外部身份按 platform+external_user_id 匹配，不按名字匹配。主部门从事件快照或时间对应的 membership 获取。显式 profile_user_mapping 只有唯一有效映射才使用；用户表 Profile 文本不是自动身份授权。
- 部门迁移事务性关闭/新增 membership，只改当前用户主部门，不重写历史事件。会话列表是当前筛选窗口内的请求汇总，跨部门/多用户时不虚构单一归属；未归属显示 —/未归属。
- MCP 仅包含 confirmed mcp 且有 Server ID 的去重调用；同工具ID在不同服务分开，本地/未知不进入 MCP 统计。活跃人数包括模型和工具活动的关联用户去重。
- UTC 存储；查询 `[from,to)`，tz 用 IANA ZoneInfo。自然日分桶支持跨午夜和 DST，最多366个自然日。价格起止日均包含，按持久化 Asia/Shanghai 判断，内部结束转为次日零点 exclusive；同提供商/模型启用区间不重叠。

## HTTP

前缀 `/api/plugins/hermes-usage-manager`。health 为直接对象，标明 M2、storage ready/unavailable、collection unavailable、hermes_runtime unverified。其余成功返回 `{data,meta}`，meta 包含 data_source、tz、coverage；时间查询增加 from/to，分页增加 total/page/page_size。错误统一 `{error:{code,message,request_id}}`，不返回 SQL、文件路径或参数值。

实现 README 9.2 所列查询与管理路径，增加 `/overview/summary` 给组合页面一次加载，以及 `PATCH /models/prices/{id}`。`/preview/analytics` 不存在于生产 router。旧 start/end 参数仅为兼容，页面后续迁移可使用 from/to；两者都提供时 from/to 优先。

请求/会话每页最多100，时间/输入/输出排序白名单；管理列表支持分页与稳定 ID 排序，名称或审计时间支持对应列表。分组维度结果最多10000，超限明确422，不静默截断；管理页面按每页100分批读取，上限100页。CSV 默认禁用，管理员 PATCH settings 显式启用；导出遵守授权范围，最多10000条，危险公式前缀加单引号，写审计日志。M2 settings 只允许 export_enabled，时区不允许经此接口任意修改以免改变既有定价解释。

## 身份与权限

真实请求默认403 IDENTITY_UNAVAILABLE，不信任任何 role 查询参数或 Mock HTTP头。受控测试环境可显式设置 `USAGE_MANAGER_TRUST_DASHBOARD_ADMIN=1`，调用已检查官方源码的 `_require_token(request)` 认证 Dashboard 管理员；这是版本相关内部适配点，不是承诺稳定的公共 API，v0.21.0 仍需实测。适配模块缺失503，不降级开放访问。修改操作校验浏览器 Origin 与 Host 一致。

服务端能力：admin 可管理；auditor 可读统计/会话元数据；department 只能其绑定部门统计/请求；user 只能其绑定用户统计/请求。后两者不能看会话或配置，过滤参数不能扩大范围；这些 Principal 由可信服务端身份 Provider 注入，不由客户端声明。当前原生适配只提供显式启用的管理员，尚无真实部门/个人 SSO。

真实 SessionContentProvider 未接入；正文503 SESSION_CONTENT_UNAVAILABLE并写访问日志，不猜 Hermes 私有 state.db 表。Mock 的虚构消息/工具参数只存在 dev，不进发行包。默认不额外采集原文。

## 范围与限制

coverage 指当前配置数据库内 Profile，不是全公司名单。缺失 Profile 的全局清单未知，不能把当前库冒充公司全集。M2 只有 fixture/replay 测试数据；真实部署即使 storage ready 也不会自动产生用量。规模压测、隔离 Plugin Host、v0.21.0 认证与存储 helper 均仍需目标 Hermes 验证。M3 才做真实 Hooks、跨进程采集与会话 Adapter。
