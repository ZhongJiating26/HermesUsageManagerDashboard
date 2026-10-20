# M3 阶段验收报告

## Milestone

**M3基础验收通过：插件0.4.4 / Hermes Agent v0.21.0，限当前支持的五Hook、单测试实例/Profile范围。** 证据日期2026-10-16，时区Asia/Shanghai。实机命令及截图由用户执行并回传，Codex未连接服务器或生产环境。M4未启动，未自动提交或推送Git。

该结论对应README第13节M3退出条件：一次真实对话形成请求记录、真实MCP工具计数核对、正文可选读取及不可用优雅降级；不等于全部可选场景、生产就绪或辅助用量完整覆盖。

## 已完成

| 验收项 | 证据与结论 |
| --- | --- |
| 原生发现与注册 | 用户最新doctor --ci确认已安装0.4.4，发现/manifest/导入/注册通过，0工具、5 Hook；不修改核心 |
| 真实模型请求 | 无工具测试会话20261016_082227_2455c4完成；Live界面observed，真实请求入库，未知身份/缓存/费用保留为未知 |
| 真实MCP调用 | 会话20261016_083622_14517b：mcp__sellersprite__trademark_country_list，Server=sellersprite、类型mcp、success、280ms、time_source=received；页面显示1次 |
| CLI计数差异 | 用户提供目标cli.py:17804实际计算：role为tool或含非空tool_calls的消息均计入摘要。一次助手工具调用消息加一条工具结果消息可得到2，不是两次物理调用。与插件一次MCP不存在计数口径冲突；不能泛化为所有会话均应除以2 |
| 队列及落库 | 用户只读查询：模型3、工具1，队列4条done，丢弃/无效0；context_missing=4为外部身份缺失，不是丢弃计数 |
| Dashboard重启持久化 | 用户重启后确认记录仍在；更新0.4.4后旧记录与新UI均在真实Dashboard截图中可见 |
| 可选只读正文 | 0.4.2显式宿主Profile名称映射解决503；公开SessionDB(read_only=True)与有界get_messages实际可读，0.4.4截图有真实标题、源会话ID及消息时间 |
| 正文关闭降级 | 用户明确回传关闭开关并重启后，新请求503 SESSION_CONTENT_UNAVAILABLE，列表、用量和MCP统计正常；不从不同时点/会话截图推断开关状态 |
| 访问审计 | 用户只读查询ok=4、unavailable=9，成功与不可用访问均留痕 |
| 原型UI | 两张用户指定原型核对；右侧抽屉、灰色遮罩、外层滚动锁、白区连续滚动、左右气泡、长文展开和两级工具折叠，经本地测试及用户实机反馈确认 |

## 新建/修改文件

- 原生入口与声明：__init__.py、plugin.yaml、dashboard/manifest.json、dashboard/plugin_api.py。
- 采集/正文适配：backend/collector.py、backend/adapters/hooks.py、backend/adapters/session_content.py、backend/quality.py、backend/migrations/0005_collection.sql，及事件/API/权限与响应契约。
- React详情：frontend/src/components/SessionDetails.tsx、common.tsx、frontend/src/services/conversation.ts、preview.ts、frontend/src/pages/RecordsPage.tsx、theme.css及预构建IIFE/CSS。
- 测试/工具：tests/test_m3_collection.py、tests/test_v021_compatibility.py、frontend/tests/m3.spec.ts、session-detail.spec.ts、scripts/replay_hooks.py、scripts/package_m3.py等。
- 文档：compatibility.md、m3-report.md、m3-acceptance.md、m3-042-testing.md及本报告，README和CHANGELOG。

未提交的M3实现仍留在工作区，M2基线提交为815b340；未修改用户原型图。

## 执行测试与结果

- 0.4.4本地完整运行：pytest90项、Playwright32项、IIFE3项，共125项通过。类型检查、ESLint、正式构建、React/ReactDOM不打包及diff空白检查通过。
- 后续M3采集/兼容专项重跑50项通过；五回调同事件三次隔离Mock重播，唯一模型事件2条（成功/失败各一）、MCP1条，原文未保留检查通过。不是目标实机Hook重复投递测试。
- 本轮以虚构四消息历史复现目标CLI计算公式：摘要2、声明调用1，断言通过。该检查只解释源码口径，不读取实机正文、不作为另一次真实MCP调用。
- 真实Hermes doctor、调用、持久化、正文开关及访问审计证据均来自用户回传；未声称由Codex远程执行。
- 已知告警：本地Starlette/httpx弃用、Node颜色环境告警；目标Hermes曾报告MCP协程未await。告警保留，不据此臆断漏采，不修改核心。

## 尚未验证项

- 实机重复Hook投递/断电/强退恢复、多Profile同时采集及预期Profile清单覆盖；本地幂等/事务测试不能替代这些实机证据。
- 高级MoA/辅助调用完整覆盖、所有供应商Token语义及真实账单对账、未知身份的组织人员映射。
- 全新测试机安装、完整升级/回滚/卸载及生产安全复核属于后续M4范围，未因本次测试升级成功而全部标绿。
- 所有浏览器/移动设备和自定义宿主滚动容器的实机覆盖；当前设备反馈不代表全平台。

## 风险/需要确认

- v0.21.0无post_auxiliary_call，当前包只注册五Hook，辅助用量未采集，不代表零。
- CLI缺外部用户身份、缓存/价格字段不明时保持未知；不猜人员、不补零、不伪造费用。
- 工具发生时间为received降级，280ms是Hook提供的耗时，不是可信源时间差保证。
- oneshot退出180秒后无心跳会显示degraded，目前与真正采集异常共用状态，需结合错误/队列计数解读。
- 正文是Profile级显式授权，不是单会话白名单；工具参数不读取、工具结果默认隐藏，脱敏为启发式而非完整DLP。
- 连续滚动每次有界读取100条，单次查看5000条安全上限并明确提示，已加载数不是完整会话总数。

## 下一步建议

本阶段停止，等待用户明确指令后再进入M4；不自动提交Git、不部署生产。测试结束应关闭正文临时权限并重启Dashboard；已验证过拒绝流程，之后为展示重新开启过时仍须再次关闭。保留测试DB、安装备份和当前版本记录。
