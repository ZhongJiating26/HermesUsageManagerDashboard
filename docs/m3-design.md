# M3：Hooks 与会话适配

## 0.4.1目标修正（优先于下面0.4.0设计）

用户v0.21.0实机确认无post_auxiliary_call，且get_messages无include_ancestors。当前包只声明/注册五个基础Hook，质量面板明确辅助用量未采集；旧/新会话方法通过签名检查有界调用，不触碰私有表。0.4.0的六Hook设计与签名是较新源码基线，不是目标实机事实。完整辅助覆盖仍不可用，不能宣称M3全功能验收。见compatibility.md、m3-testing.md。

状态：0.4.0本地实现及测试通过，真实Hermes退出条件未完成。M2基线提交为815b340；未连接生产、未修改Hermes核心、未使用Desktop SDK。

## 官方证据与兼容边界

2026-10-15复核[原生插件开发文档](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)和[Hooks文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks)，并逐项对照只读官方源码commit `525dbcad8d744710a43d01eb7366500e46eacbf4`。文档最新内容不是用户v0.21.0的保证，尤其不能把当前文档的validate命令套到用户CLI。

源码证据：

- `agent/turn_context.py:806`：pre_llm_call携带session/turn/platform/sender_id。只取身份，不读取user_message/history。
- `agent/turn_response_intake.py:69`：post_api_request包含api_request_id、started_at/ended_at、api_call_count、provider/model、usage。
- `agent/api_request_hooks.py:36`与`agent/usage_pricing.py:75`：usage来自CanonicalUsage，prompt=input+cache_read+cache_write；raw_usage已被删除，默认零不等于供应商确实报告零。
- `agent/api_request_hooks.py:163`：api_request_error包含retry_count/status_code和原始error/request；本插件只取数字状态与稳定ID，丢弃error/request正文。
- `agent/auxiliary_hooks.py:140`：post_auxiliary_call每物理attempt发出，包含成功/错误/流式缺usage情形。
- `model_tools.py:675`：post_tool_call含tool_call_id、turn_id、duration_ms、ok/error；不含可信事件时间，所以明确记为received。
- `tools/registry.py:988`及`tools/mcp_tool_registration.py:326`：在回调当前作用域读取实际toolset归属；mcp-{server}才归MCP，不按工具名字猜。
- `hermes_state.py:579`与`hermes_state_messages.py:1409`：SessionDB只读构造和带limit/offset的get_messages；经该方法读取，不查询Hermes私有表。

这些是已检查源码的适配点；旧版缺字段/签名时显式降级，不使用猜测字段或核心monkey patch。

## 原生回调与身份

注册pre_llm_call、post_api_request、api_request_error、post_tool_call、post_auxiliary_call、on_session_end。register只接线，不启动DB；USAGE_MANAGER_COLLECTION不为1时回调立即返回None。开启后也始终返回None，不改变Agent提示词、工具结果或任务成败。

每次回调读取当前get_hermes_home，捕获实例/Profile/DB上下文后再交后台；不能在后台线程重读丢失的ContextVar。实例默认由本机主机名+用户目录的哈希得到，可显式指定稳定USAGE_MANAGER_INSTANCE_ID；Profile优先显式设置，其次官方profile_name_for_home，缺helper时按home路径哈希隔离，不拿Profile名推断员工。默认DB按已核对的plugin-data/{插件名}/usage.sqlite3约定外置，支持显式路径。

pre_llm_call的sender/platform只在instance/profile/session/turn严格相同的有界内存上下文复用；上限512，TTL900秒，结束移除。没关联上则保留未知。用户身份仍经platform+external_id或唯一显式profile_user_mapping解析，历史部门规则不变。

## 归一化与去重

- 主/辅助请求分开；成功/失败分开。source_event_id是hook种类、session、api_request_id、源started_at及attempt的确定性哈希，再与instance/profile组成事件键。
- 缺稳定请求ID、源时间、会话ID或工具调用ID时拒绝该事件并增加invalid，不按接收时间乱造幂等ID。
- 原生CanonicalUsage字段完整且互相一致才解释Token。缓存为输入子集，不重复加；canonical默认cache=0无法证明供应商报告过缓存零，因此保留NULL。output/prompt默认零同理，缺原始字段时不做虚假精确统计。
- cache_write单独保存；现有三档价格没有cache-write溢价，cache_write>0时不生成不准确费用。流式辅助调用usage尚未聚合时记录未知，不推算。
- MoA的main facade带moa_references时不作为额外物理请求入账（invalid可见），不把advisor摘要再加总一次；辅助物理调用仍逐条处理。MoA/流式完整对账尚未实测，不宣称覆盖所有高级路由。
- 工具分类在原始回调作用域查询已加载的真实registry；无registry或不明MCP归属则unknown。工具ok/error映射success/failed；没有status不从敏感result猜。
- API时间使用源ended_at；工具没有源时间时time_source=received，质量API单列此类工具数量。不能用接收时间宣称历史调用的精确日期。

## 后台队列与故障

回调不做SQLite事务，先生成白名单DTO，再非阻塞放入最多1024项的内存队列。每个DB路径一个daemon worker，最多8个路径。只有归一化字段持久化，不保留kwargs、消息、history、args/result、base_url、错误正文或密钥。

worker在外部SQLite中先持久化collection_queue和event_inbox pending，再在单一写事务内去重入库并标done。两个worker不能重复应用同一pending；重启可继续处理已持久化队列。错误最多3次后隔离，清除payload，仅留ID/固定错误码；done清除payload。最多4096个pending、10000个done标记、256个failed隔离记录；超限有drop计数。事实表/event_inbox/审计元数据目前长期保留，运营方需配置备份与离线归档策略。

必须承认的边界：内存入队到durable提交之间、进程被强杀时仍可能丢数据；这是非阻塞观察与磁盘持久化之间的窗口，不声称exactly-once delivery。数据库初始不可用时无法把本进程错误计数写进坏库；固定脱敏告警及心跳缺失提供诊断。回调不输出原始异常。退出每worker最多等待1秒尽力flush；数据库忙时优先保证Agent能退出，不无限等待。不要使用NFS/跨机器共享SQLite，本阶段只支持同机本地磁盘多进程。

## 数据质量

新增GET /quality，遵守服务端角色及日期/部门/用户授权交集。返回请求缺usage/cache/身份/价格数量、未知工具及接收时间工具数量，以及当前库的采集心跳、声明Hook、最后入库时间、pending/failed/dropped/invalid。

collector_runs心跳由后台写，180秒内视为fresh；unavailable表示无运行记录，registered表示有心跳但未见入库，observed表示已见入库，degraded表示心跳过期或存在丢弃/无效/隔离。不等于目标Hermes兼容性已验证，hermes_runtime仍unverified。

USAGE_MANAGER_EXPECTED_PROFILES可提供最多100个Profile ID的JSON数组。例如预期5个而仅2个回调出现时，返回configured=5、connected=2、missing_heartbeat=3。未提供则只知道本DB已配置/出现的Profile，不能推断全公司清单。前端放在标题information面板，默认不把小提示铺在页面。

## 正文读取与隐私

正文默认关闭；USAGE_MANAGER_SESSION_CONTENT=1加显式USAGE_MANAGER_SESSION_HOMES JSON白名单才可读取。键为instance_id/profile_id，值为经管理员批准的绝对Hermes home；只读其已确认的state.db，检查路径/会话归属，不跟随跨Profile祖先链。

真实Provider调用SessionDB(db_path=...,read_only=True)、get_session、get_messages(limit<=201,offset,latest=False,include_ancestors=False)，始终close。签名/模块/文件不兼容或关闭时503 SESSION_CONTENT_UNAVAILABLE，不读取私有表、不伪造正文。

正文权限audit_detail只给admin；auditor仍只能看会话元数据。允许、拒绝、不可用都记录审计，不把原文写本插件DB。只投影user/assistant文本和工具展示字段，忽略system/隐藏reasoning/结构化非文本；工具参数不读取，工具结果另需USAGE_MANAGER_TOOL_CONTENT=1。连续工具行分组，未知成功状态不伪造成失败或成功。

返回最多200条原始消息一页，默认100，带has_more/offset；UI可切换前后页。单段文本最多10000字符，有明确截断标记。对常见授权头、cookie、secret/password/api_key字段、常见密钥模式、完整或被截断的私钥块进行脱敏。启发式脱敏不可能识别所有未标注秘密，因此仅在组织授权的隔离测试中开启，不能把它当完备DLP。

## 阶段边界

M3本地代码、mock重播与测试不构成真实退出条件。用户v0.21.0的一次真实对话和MCP调用、usage语义、身份链、实际Profile/隔离宿主与会话API均待验证；步骤见m3-testing.md。未开始M4或生产部署。
