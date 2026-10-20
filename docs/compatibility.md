# Hermes Usage Manager 兼容性记录

## URL安装器清单版本修正（2026-10-20）

用户回传`hermes plugins install`拒绝manifest_version 2，安装器上限为1。此前doctor和手工放置插件目录的验收没有覆盖URL安装器的版本门槛，不能据此判断安装器支持v2。官方同类问题见[NousResearch/hermes-agent #90451](https://github.com/NousResearch/hermes-agent/issues/90451)，加载器和安装器可能使用不同上限，直接升级不保证解决。

本插件只注册五个观察Hook，不使用requires_plugins/python_dependencies/config_schema等v2专属声明。现在plugin.yaml声明manifest_version: 1，api_version: 1保留，运行代码与Hook不变；README示例同步，并在兼容测试中约束清单不能再次超出v1安装器上限。本地测试通过不代表已在用户目标机完成URL重装；本轮未升级Hermes或连接服务器。

## 0.6.0 独立端口：用户授权变更，本地通过

用户明确选择独立端口仅显示平台，调整此前嵌入限制：原生IIFE继续复用宿主React且无React打包，独立入口单独构建React/ReactDOM并带自己的管理员登录；两者共用业务API/SQLite，五Hook与schema不变。153项Python、32项原生浏览器、4项独立浏览器、3项IIFE共192项通过，类型/lint/双构建通过；独立登录/写入CSRF/会话失效/包内运行得到本地验证。0.6.0实际Hermes及Linux服务启动仍待当前测试机回传，不把0.5.1实测扩大为新入口通过；新服务器免除决定不变。详见standalone.md、standalone-report.md。

## 用户免除新服务器验收：本次M4范围完成

用户最终明确“不用新服务器验证了”，将新服务器安装验收从本次交付范围免除，不是实测通过。现有测试机已确认流程与本地严格标签包交付满足调整后的M4范围；未实测的新环境兼容性仍未知。v0.5.1指向57cf045，严格包另存build/tagged/v0.5.1，未单独在目标安装。范围调整不改变标签/既有包，不批准生产部署。此前“暂缓/仍阻塞M4”的描述为历史，当前以此结论为准。

## 新服务器验收由用户决定暂缓

按用户明确指令先跳过全新测试服务器安装验收，本项仍未验证，不以现有机重装替代。现有测试机已验证链路保持有效；暂停重复停机演练。完整M4退出条件仍未满足，源码提交/tag与生产部署需分别确认；本轮只记录状态，不修改已上传候选包。

## 现有测试机重装检查获用户确认

用户按0.5.1校验暂存/安装doctor/enable/原库检查/Live页面及恢复Gateway的指引后，确认验证无问题；作为用户确认的重装旧数据保留证据，不虚构未回传的具体计数和日志。结合已记录升级/回退/恢复链路，当前测试机运维演练已通过；使用手工可恢复移出而非CLI remove，DB原位回滚未执行。保留备份及既有0.5.1候选包；M4全新服务器、正式发布和生产审查仍待完成，不标记M4整体完成。

## 可恢复移出界面检查获用户确认

用户确认可恢复卸载指引后的页面验证无问题（入口消失/其他页面正常）；未回传命令日志、目录和新计数，不扩大为CLI remove或特定快照输出通过。下一项从校验后的0.5.1包重装到空安装目录，原DB不覆盖，重装doctor/Live仍待回传。M4源码阶段提交3d0ea39，未push/tag，候选包未重打。

## 现有测试机0.5.1恢复完成，升级回退闭环通过

用户回传恢复副本与安装目录doctor均0.5.1、0工具/5 Hook，enable成功；原DB仍Live、五步迁移，计数3/1/2/1/0/21，新增访问审计保留。确认Live · M4、数据正常且Gateway恢复。实机0.4.4→0.5.1→0.4.4→0.5.1代码链路通过，快照检查后恢复到新目录已通过；未覆盖原DB，不声称数据库原位回滚已验收。当前运行0.5.1。可恢复卸载/重装、全新服务器及正式发布门禁仍待完成，M4不标记全部完成。

## 旧版Live回退验收通过

用户确认0.4.4回退后Live · M3及各统计/列表正常、旧数据保留，正文关闭503符合预期。现有测试机代码回退的doctor/数据保留/Live UI链路已通过；DB恢复仅验证新目录副本，不声称覆盖原库。下一步恢复0.5.1代码并检查新版页面，Gateway在此之前保持停止；M4新服务器等退出项仍待验。

## 实际代码回退0.4.4通过

用户回传两个快照restore成功，旧恢复副本和实际安装目录doctor均0.4.4、0工具/5 Hook，启用成功；原DB五步迁移、计数3/1/2/1/0/20不变。仅代码回退，不恢复旧18条审计DB。新版代码保留/home/ubuntu/hum-m4-rollback.CRcF8l/plugin-0.5.1；旧版页面、恢复新版及新服务器等退出项仍待验。

## 实际回滚前当前数据已备份

用户确认所有已列Gateway停止；当前代码/DB快照/home/ubuntu/hum-m4-rollback.CRcF8l/snapshot成功，DELETE/format=1，Live五步迁移、计数3/1/2/1/0/20。比旧快照新增2条访问审计，后续仅代码回退，不把旧DB覆盖当前数据。实际回退及旧版Live仍待回传。

## 0.5.1 实际Live页面通过

用户确认Live · M4，概览、用量明细、MCP、对话列表保留旧数据无接口错误，正文关闭后503 SESSION_CONTENT_UNAVAILABLE符合预期。Gateway已重新启动，原快照之后的数据不能假定不变；回滚前必须重新停写并备份当前0.5.1代码/DB。此项补齐实际升级UI/API证据，不代表实际回滚、卸载或新服务器通过，也不证明公网网络安全配置已审查。

## 0.5.1 实际安装与启用通过

用户回传安装目录原生doctor确认0.5.1、0工具/5 Hook，plugins list确认enabled0.5.1。停机代码替换后原DB为Live、0001–0005，计数3/1/2/1/0/18保持不变。未授予内置工具覆盖权限，不影响本插件所需契约；不额外授权该能力。当前已具备实际安装升级证据，新版Dashboard/Live API及实际回滚、卸载/重装、新服务器验收仍待执行。

## 0.5.1 目标暂存及快照恢复检查通过

用户回传/home/ubuntu/hum-m4-051.t6rUvM中的新版暂存doctor通过（0.5.1、0工具/5 Hook），新快照DELETE/format=1经inspect-db后restore成功，恢复旧代码doctor通过（0.4.4、0工具/5 Hook）。原库/快照/恢复副本均Live、五步迁移、计数3/1/2/1/0/18一致。此前“0.5.1恢复尚未通过”已获补证；安装目录仍未替换，实际新版Live/回滚与新服务器验收不因此标绿。历史0.5.0失败证据保留。

## 0.5.1修复候选：实机恢复检查尚未通过

修复后本地完整pytest123、Playwright32、IIFE3共158项通过，类型/ESLint通过；覆盖snapshot→inspect快照→restore实际顺序。目标0.5.1原生Doctor及恢复检查尚无回传，不标记实际升级/回滚通过。

0.5.0实际恢复副本检查返回ValueError并在代码替换前停止，原0.4.4/原DB未被该脚本替换。已本地复现旧WAL快照经inspect-db生成sidecar导致严格库存拒绝恢复；0.5.1只对新备份封存DELETE模式，保留原库WAL和旧快照，新增明确错误码及顺序回归。不能仅凭旧通用报错确定实机唯一原因。请使用m4-051-recovery.md重新在新目录暂存、备份、恢复检查，不继续旧0.5.0升级命令。以下快照汇总通过为历史证据，不代表恢复/升级通过；M4仍待实机与新服务器验收。

## M4实机快照通过，升级尚待执行

用户回传Live原库与快照汇总一致：五步迁移、模型3、工具1、会话2、Profile1、价格0、访问审计18；快照成功保存/home/ubuntu/hum-m4-upgrade.0rwyvF/snapshot。基于SQLite backup的真实快照已完成，不等于已将新版本安装或已回滚原库。下一步恢复到新目录检查，再替换旧插件代码并doctor，保持原DB路径不变。

## 用户实机0.5.0暂存Doctor通过

zip/ops.py校验OK，外置工具verify/stage均成功。用户实际暂存/home/ubuntu/hum-m4-stage.mtpXSY/staged/hermes-usage-manager的doctor --ci输出manifest0.5.0、发现/manifest/导入/注册通过，0工具/5 Hook。确认当前候选的目标原生加载契约，不等于已安装升级、Live业务API或真实回滚通过。下一步仅做旧版本代码和外部DB一致性快照，现有0.4.4不先覆盖。

## M4进行中：0.5.0交付候选

本轮本地pytest120、浏览器32、IIFE3共155项通过，类型/lint/构建/React排除和Bash语法检查通过。M4交付30项覆盖无Node独立工具、包可复现/损坏拒绝、SQLite WAL快照/恢复、文件/DB升级回滚仿真；不能据此把真实新服务器、0.5.0 doctor或CLI remove标绿。M4仍进行中，下一项只暂存校验，不覆盖现有0.4.4。详细证据见m4-report.md。

M3按用户要求提交61b7663后继续M4。0.5.0保留目标v0.21.0已验证五Hook/0001–0005 schema与身份/正文边界，仅新增交付校验/备份/暂存/恢复等运维工具与M4标识。当前没有0.5.0实机doctor或新服务器证据，M3的0.4.4实测不自动继承为新版全部通过。候选包记录source_dirty=true和未建立tag，不伪造正式发布；正式发布入口有--require-tag门禁。

重新核对[官方原生插件文档](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)：Web Dashboard与Desktop扩展是不同表面，doctor使用实际发现/manifest/注册契约；最新文档存在validate但目标用户CLI没有该子命令，继续以目标doctor为准。没有修改Hermes核心或升级宿主依赖。详细步骤、安全限制与本地/实机证据等级见deployment.md、security-review.md及m4-report.md。

## M3基础验收通过：Hermes v0.21.0 / 插件0.4.4

用户提供cli.py:17804目标计算代码，CLI摘要计数是工具相关消息条数（role=tool或非空tool_calls），一次调用可有助手调用消息和工具结果消息两条，解释本次摘要2与插件MCP1的口径，不要求插件复制该摘要算法。原生doctor、真实主请求/MCP、正文显式开关与审计、Dashboard重启持久化和新UI证据已齐，M3在当前五Hook/单Profile范围基础验收通过。详见m3-final-acceptance.md；后续历史待验证描述以此为准，不代表辅助完整覆盖、实机重复投递、多Profile、生产或M4验收。

## 当前目标版本0.4.4 Doctor已通过

用户回传已安装0.4.4的doctor --ci，runtime discovery/manifest parsing/import/registration全部通过，注册0工具/5 Hook。结合此前真实Dashboard截图，新版本原生加载与UI均有目标宿主证据，覆盖先前“仍为0.4.2/新版doctor待确认”的历史状态。CLI摘要输出已定位cli.py:17845，计数计算代码尚未给出，暂不解释2与1的差异。

## 用户确认新详情界面在真实Hermes中正常

用户更新指引后回传“没问题了”及真实Dashboard两张截图：新版抽屉/灰色遮罩/气泡、已加载消息与源时间显示正常，旧测试记录仍可读；另一个会话503时元数据摘要与列表保留。此项升级为目标宿主UI通过，不再仅为Mock。两图不同会话且权限时序未知，不推断为同一关闭状态；此前明确的关闭权限拒绝证据保持有效。截图无manifest版本，最新直接doctor版本证据仍是0.4.2；CLI摘要2次口径另待核对。

## 当前测试机原生Doctor通过：实际安装0.4.2

用户最新输出显示/home/ubuntu/.hermes/plugins/hermes-usage-manager实际manifest版本0.4.2；关闭采集运行doctor --ci，发现/manifest/导入/注册全部通过，0工具/5 Hook。未安装最新版0.4.4，不能把此前本地Mock UI验收扩大为0.4.4实机验收。下一步使用现有0.4.4包备份更新测试机，保留既有测试DB；无需重做付费模型/MCP调用。原先“当前版本doctor待回传”至此补证为0.4.2，而非0.4.4。

## 实机访问审计及MCP结构化元数据通过

用户回传正文访问审计ok=4、unavailable=9，成功及关闭不可用访问均有留痕。MCP指定会话记录为mcp__sellersprite__trademark_country_list / mcp / sellersprite / success / 280ms / received，类型、Server归属、状态与耗时得到实机证据。工具时间仍为接收时间，不扩大精度保证。CLI摘要2 tool calls口径及当前安装版本doctor仍待补证，不声称实际重复投递或全覆盖通过。

## 用户确认正文关闭权限验收通过

关闭正文临时权限并重启后，新请求为503 SESSION_CONTENT_UNAVAILABLE；对话列表、用量统计、MCP统计正常，用户已回传确认。只读正文显式启用可读、关闭不可读且元数据仍可用的流程已验证。访问审计与MCP结构化归属/状态/耗时尚待只读补证；没有本次doctor输出，不新增目标0.4.4 doctor通过声明。

## M3 收尾验收进行中

用户已确认当前浏览器详情UI无问题（上下文为本地Mock预览），未据此扩大为目标Hermes全部滚动场景通过。收尾清单见m3-acceptance.md：下一项是关闭正文临时权限后的新请求拒绝，同时保留宿主认证与已有统计。审计与MCP状态/归属/耗时、CLI摘要计数差异仍待核对。

## 0.4.4 抽屉遮罩与无分页连续滚动

本轮本地后端90、浏览器32、IIFE3共125项通过，类型/lint/构建/React排除及空白检查通过。实际测试宿主滚动祖先恢复、长内容滚动、连续加载及关闭请求取消；截图为Mock。目标Hermes安装后的滚动行为仍需用户确认。

按用户4条浏览器批注：增加灰色遮罩并锁定html/body及宿主滚动祖先；关闭时恢复原内联overflow值/优先级、滚动位置和焦点。仅白色对话区域滚动，顶部摘要不动，移除上一段/下一段/位置分页栏。界面连续滚动接近底部时有界加载，先前消息保留，跨读取边界的连续工具组合并；加载失败保留已有消息并可重试同一offset，取消时中止请求。

后端公开接口分页契约不变，无需无界读取或批量抓取全会话。每次最多100条，单次查看最多5000条，达到上限明确标注后续内容未加载；防止源分页不前进导致循环请求。已加载数不冒充完整会话总数，权限/只读/脱敏策略不变。0.4.4目标Hermes实机UI仍待用户核对，不标记M3全部完成。

## 0.4.3 对话详情UI还原及0.4.2正文补证

本轮本地测试：后端90、浏览器26、IIFE3共119项通过，类型/lint/构建与React排除检查通过；截图核对含桌面/移动端。不是0.4.3宿主实机验证，正式更新需重启Dashboard并强制刷新前端，按m3-042-testing.md操作。原有辅助Hook、身份/费用未知和oneshot心跳过期状态语义未在本次UI任务中变更。

用户明确反馈0.4.2可看到真实对话记录，确认显式宿主Profile映射解决正文503；关闭开关后的不可读测试尚未回传，不将它标为通过。按最新确认的两张对话详情原型，将居中弹窗改为右侧抽屉、固定摘要及独立滚动区、左右气泡、长文展开、灰底分组和白色工具二级折叠。未改变只读、授权、归属、脱敏与工具结果默认隐藏策略。

授权正文接口提供真实源会话ID与脱敏标题；有效来源timestamp可展示，缺失/无时区/非法值返回未知，绝不使用当前时间或会话时间补齐。标题缺失回退“对话详情”；原始当前段消息数和MCP次数明确区分总数，历史未知不补零。0.4.3目标Hermes实机UI仍待用户确认，不代表M3整体完成。

## 0.4.2 正文归属兼容修复

本地验证：后端82通过、IIFE3通过，类型/lint/构建与React/ReactDOM排除检查通过；本轮未重跑浏览器测试。Starlette/httpx弃用告警保留，实机0.4.2 doctor与正文验证尚未完成。

用户实机确认owner_profile=default且公开有界接口可读2条；插件采用home哈希Profile ID，0.4.1直接比较导致503。0.4.2增加按实例/Profile隔离的显式USAGE_MANAGER_SESSION_PROFILES映射，保留原归属检查与只读/权限/目录白名单，不改核心或既有ID。新增8项映射回归测试；安装配置见m3-042-testing.md。新包实机正文开启/关闭验证仍待回传，不把独立诊断脚本成功视为插件验收通过。

## 2026-10-16 队列诊断与 Dashboard 重启补证

用户在测试机只读查询：collector_runs=2、fresh_runs=0，last_seen=2026-10-16T00:36:41.025126+00:00，last_success=2026-10-16T00:36:41.010339+00:00；dropped=0、invalid=0、context_missing=4，队列done=4，llm_requests=3、tool_calls=1。按当前状态判定，degraded由心跳过期触发；context_missing计数表示已归一化事件缺少external_user_id，不代表该事件未入库。不能把三条模型事件全部归为额外用户请求，或据此证明CLI工具摘要计数完全一致。

用户按指引重启Dashboard后确认记录仍在，Dashboard进程重启持久化检查通过。不是Agent异常中断、机器重启、实机去重或只读正文验收。已知UI将采集进程退出后的心跳过期与采集异常统一显示degraded，尚未修改该状态语义。辅助覆盖与身份归属缺口仍保留。

## 2026-10-16 用户实机 MCP 入库补证（0.4.1）

用户回传卖家精灵trademark_country_list测试会话20261016_083622_14517b：CLI显示MCP调用约0.3秒、模型报告业务返回code=OK，CLI会话摘要为2 tool calls；Dashboard的MCP趋势及工具排行榜各显示1次，采集状态degraded。确认至少一次真实MCP事件采集及展示成功，但尚未核对完整Server归属、结构化状态/耗时，以及CLI摘要与MCP计数差异，不能据此证明无漏采或去重正确。需查看最新质量指标区分心跳过期与无效/丢弃/隔离。

同次CLI出现Hermes tools/mcp_tool.py:6189的RuntimeWarning（MCPServerTask._watch_stdio_children协程未await）。记录宿主告警，不推定其与degraded或计数差异有因果关系，不修改Hermes核心。

## 2026-10-16 用户实机主请求入库补证（0.4.1）

用户回传测试机CLI与Dashboard截图：会话20261016_082227_2455c4成功回复，2条消息、0次工具调用；页面为Live / M3 / observed，当前库Profile心跳1/1，最后入库2026/10/16 08:22:40（Asia/Shanghai）。质量面板显示请求1、待处理0、隔离0、丢弃0、无效0、用量缺失0；身份未知1、缓存未知1、费用未知1。确认一次真实主请求元数据采集及页面读取链路成功，不据此证明所有Token字段语义或定价正确。CLI身份未知与缓存/费用未知保留为未知，辅助Hook仍不可用，不代表用量为零。

此前unavailable由两个终端均未设置采集环境变量暴露；用户按相同DB路径与采集开关重新启动Dashboard及chat后回传上述证据。证据由用户提供，未远程访问。MCP调用、实机去重、只读会话正文与重启持久化仍待验证，M3不标记整体完成。以下“真实请求待验证”是本次补证前的历史状态。

## v0.21.0 实机预检差异修复（插件0.4.1）

实机Doctor补证（用户回传）：对临时解压的0.4.1包运行 `USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci <staging-path>`，输出 `OK: runtime discovery, manifest parsing, import, and registration passed`，注册数为0工具、5 Hook。这证明目标v0.21.0上的发现/manifest/导入/注册已通过；未替换现有插件、未启用采集，不能据此标记真实请求、MCP或会话正文验证通过。

用户终端输出确认：Hermes v0.21.0 / Python3.11.15 / FastAPI0.133.1，Asia/Shanghai可用；缺少post_auxiliary_call。实际解释器为`/home/ubuntu/.hermes/hermes-agent/venv/bin/python3`。SessionDB支持read_only；get_messages支持limit/offset/latest，但没有include_ancestors。证据来自用户实机签名，不以较新源码覆盖该事实。

修复：此测试包的manifest与实际注册统一为五个受支持Hook，不声明或注册不存在的辅助事件；不升级Hermes、不改核心、不开新网站。/quality返回hook_coverage=partial及unavailable_hooks，标题说明明确辅助用量未采集、不代表为零。辅助事件normalizer保留单元测试，但本包不会收集该通道，也不动态多注册manifest未声明的Hook。

正文Provider先检查公开方法签名，要求有界limit/offset/latest；较新接口明确传include_ancestors=False，用户旧接口省略该不存在的参数。不是捕获TypeError后盲试，也不回退到私有SQL或无界读取。若返回行明确属于别的session则拒绝。只读、来源白名单、管理员权限和默认关闭均保持不变。

新增5个兼容用例，后端74通过。该输出只证明接口存在性，不证明实际Hook字段、Token语义、MCP身份或真实正文可读；doctor和真实对话仍待用户验证。使用新包hermes-usage-manager-0.4.1-m3.zip，不继续安装旧0.4.0包。0.4.0以下记录保留为历史。

## 当前 M3（0.4.0，本地实现，真实验收未完成）

M2已按用户要求建立Git基线提交815b340，未push。M3适配已在本地实现，但**未满足真实对话/MCP退出条件**。本机无Hermes、未连接用户服务器、未覆盖M0安装；下述M2/M1/M0结果是历史，不是M3兼容证明。

2026-10-15再次读取[官方原生插件文档](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)及[Hook文档](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks)，并对照固定源码commit525dbcad8d744710a43d01eb7366500e46eacbf4的真实调用点。具体文件/字段、未知值与降级策略见m3-design.md。

六个注册事件为pre_llm_call、post_api_request、api_request_error、post_tool_call、post_auxiliary_call、on_session_end。v0.21.0是否全支持仍需doctor和签名检查，不能用最新文档替代实测；尤其仍不建议在用户CLI执行不存在的plugins validate。

重要差异：usage是Hermes CanonicalUsage而非任意Provider SDK格式，input_tokens不应直接当总输入；raw_usage已被剥离、默认零不能证明原字段presence。post_tool_call没有可信源时间与显式Server字段，使用received标记和当前作用域真实registry归属。MCP猜名字、缓存缺失补零、重复加MoA摘要均被禁止。

会话Provider仅在独立授权+绝对home白名单下，调用已检查的SessionDB(read_only=True)/get_messages；不碰私有表，旧签名/关闭时503。正文管理员权限与普通审计元数据权限分离；请求成功/拒绝/不可用均留审计。

本地69后端+24浏览器+3 IIFE测试通过，六回调三次Mock重播通过，M2到M3迁移与独立解压加载通过。目标认证、隔离宿主、Profile、Linux/ACL、一次真实对话与MCP及正文读取仍未验证。测试命令见m3-testing.md；完整结果见m3-report.md。只有真实验收补证后才能关闭M3，当前未开始M4。

## M2 历史记录（0.3.0）

本机仍没有安装/运行 Hermes。M2 在 Windows 上用同一生产 router 的 SQLite Mock Host 验证；没有连接用户服务器。M0 v0.21.0 的截图确认不外推为 M2 的运行时兼容证明。当前 health=0.3.0/M2；storage 由实际数据库检查决定，collection=unavailable、hermes_runtime=unverified。

### 官方源码核对与版本风险

沿用只读官方源码基线 `525dbcad8d744710a43d01eb7366500e46eacbf4`，本阶段再次检查：

- `plugins/plugin_storage.py:27` 的 `plugin_data_dir(name)` 作为默认外部数据目录 helper；缺失时允许显式 USAGE_MANAGER_DB_PATH，不写源码目录。
- `hermes_cli/web_server.py:330` 的同步 `_require_token(request)` 为当前认证适配点。该名字带下划线，是版本相关内部接口，不视作稳定 SDK；用户 v0.21.0 是否相同尚未验证。
- Dashboard API 仍通过 manifest 的 api 文件导出 APIRouter；路径作用域 package loader 已通过解压后独立加载测试，无需修改 Hermes sys.path 或核心源码。
- 不使用 Hermes Desktop Plugin SDK。前端继续复用 Web Dashboard 的 React/fetchJSON/register，构建 AST+模块图检查无 React/ReactDOM。

默认不信任角色 header、查询参数或仅前端隐藏按钮。真实业务请求403 IDENTITY_UNAVAILABLE；测试管理员显式 opt-in 后仍必须经过宿主 token 校验。身份适配缺失返回503。真实部门/个人身份 Provider、隔离 Plugin Host、跨 Profile 共享数据库与会话读取 Adapter 均留待目标环境/M3验证。

### M2 本地验证

后端40项（包含迁移、重启持久化、价格修订冻结、缓存公式、缺失值、三次重播、角色越权、MCP分类、午夜/DST、CSV安全、独立发行包加载）、浏览器21项、IIFE3项通过；类型检查和 lint 通过。Windows 无法证明 Linux 文件权限或目标宿主兼容；没有宣称通过规模压测。完整命令/结果见 m2-report.md。

### 仅供独立测试 Hermes 的命令

不要在生产账号执行；不要直接覆盖用户已成功的 M0。以下用于**没有现有此插件的独立测试账号**。先由用户将 M2 zip 放到该账号当前目录，并为 HERMES_PYTHON 填入实际 Hermes 使用的解释器；缺依赖应停下确认安装到正确环境。

```bash
hermes --version
hermes plugins doctor --help
command -v hermes
"$HERMES_PYTHON" -c 'import fastapi, sqlite3; from zoneinfo import ZoneInfo; print(fastapi.__version__, sqlite3.sqlite_version, ZoneInfo("Asia/Shanghai"))'

(
set -eu
test -f ./hermes-usage-manager-0.3.0-m2.zip
test ! -e "$HOME/.hermes/plugins/hermes-usage-manager"
test ! -L "$HOME/.hermes/plugins/hermes-usage-manager"
mkdir -p "$HOME/.hermes/plugins"
"$HERMES_PYTHON" -m zipfile -e ./hermes-usage-manager-0.3.0-m2.zip "$HOME/.hermes/plugins"
hermes plugins doctor --ci "$HOME/.hermes/plugins/hermes-usage-manager"
hermes plugins enable hermes-usage-manager
hermes plugins list
hermes plugins doctor --ci hermes-usage-manager
mkdir -p "$HOME/.hermes/usage-manager-test-data"
chmod 700 "$HOME/.hermes/usage-manager-test-data"
export USAGE_MANAGER_DB_PATH="$HOME/.hermes/usage-manager-test-data/usage.sqlite3"
export USAGE_MANAGER_TRUST_DASHBOARD_ADMIN=1
hermes dashboard --no-open
)
```

不要用 `hermes plugins validate`：用户 v0.21.0 已确认没有该子命令。安装目录没有 `.git` 时，`rev-parse` 失败是源码来源未知，不表示插件失败；保留 `hermes --version` 输出即可，不擅自初始化 git 或升级 Hermes。

在认证 Dashboard 内检查：health 的版本与 storage=ready；正式页面空数据而非 fixture；管理员新建部门/价格后重启仍存在；关闭显式 opt-in 后业务请求403；篡改 role 参数不能越权；Network/Console 无重复 React。M2真实对话**不会**采集记录，不能据此判采集失败或声称 Hooks 已接入。若宿主返回 HOST_AUTH_UNAVAILABLE，保存脱敏输出并停下定位，不能改为跳过认证。

数据升级前须停相关进程或使用 sqlite backup API 做一致性备份，不直接拷贝正在写入的单个 WAL 数据库文件。降级旧代码时保留原 DB 备份；新版 schema 拒绝旧版解释。Windows ACL、Linux权限、后台启动环境变量传递、base path、host隔离等均是待真实验证项。

## M1 历史记录（0.2.0）

M1 的原型页面、Mock API 与交互在本地验证；远端仍只确认过 M0（0.1.0）。正式构建继续仅使用 Web Dashboard 的 SDK.React / SDK.fetchJSON / register，不使用 Desktop SDK、不修改 Hermes 核心。当前 Python health 版本为 0.2.0 / M1，采集与存储仍为 unavailable。

M1 引入 ECharts 6 / Zod 4，模块图允许 ECharts、zrender、tslib、Zod，拒绝 React/ReactDOM 运行时导入。构建单 IIFE，并附完整第三方许可。浏览器测试证明普通 script 加载、一次注册、切换时清理图表实例的 ResizeObserver、Live 状态不请求模拟业务数据。

本地 Mock UI 的角色 header 仅用于演示，不能作为真实身份断言。真实 Hermes 没有挂载 Mock 查询或写入接口，未实现生产 RBAC，也不会展示虚构统计。M2/M3 尚未开始。

完整结果见 `docs/m1-report.md`，本地启动见 `docs/development.md`。M1 安装包仅提供原生运行骨架与预构建页面；若安装至 Hermes，将显示业务数据尚未接入。无需更新远端即可从本仓库本地验收完整 Mock 页面。

## M0 历史核验记录

核验日期：2026-10-15（Asia/Shanghai）。状态：**本地 Mock 测试通过；用户截图确认真实 Hermes 的 Tab、页面和 health 主链路成功，剩余运行时检查待补证**。

## 环境

| 项目 | 结果 |
|---|---|
| 本机 | Windows / PowerShell，工作区 `F:\projects\Hermes_Usage_Manager` |
| Hermes CLI | `Get-Command hermes` 无结果；`where.exe hermes` 未找到，无法执行 `hermes --version` |
| 已安装 Hermes 版本 | unavailable；用户已明确本机未安装 |
| 官方源码核对基线 | `NousResearch/hermes-agent`，commit `525dbcad8d744710a43d01eb7366500e46eacbf4` |
| 源码身份 | 临时目录只读核对，未安装或启动 Hermes；不是本机已安装版本，也不是用户已选目标发布版 |
| 源码提交时间 | 2026-10-15T00:07:50-04:00 |
| Web SDK contract | 源码声明 `1.1.0`；本插件仅依赖 React、fetchJSON 和 register |
| Node | v24.19.0 |
| 包管理器 | pnpm 11.25.0；本机 PATH 无 npm，使用内置 pnpm 执行同名 package scripts |
| Python | 3.12.14（独立 `.venv`） |
| 真实服务连接 | 无；只访问官方公开文档、GitHub、依赖注册表与本地 loopback Mock |

### 用户提供的远端 CLI 实测

2026-10-15 用户粘贴的 `ubuntu@VM-0-10-ubuntu` 输出（本代理未连接该机器）：

- Hermes Agent `v0.21.0 (2026.8.31)`，目录 `/home/ubuntu/.hermes/hermes-agent`，安装方式 unknown。
- Python `3.11.15`，OpenAI SDK `2.24.0`。
- `hermes plugins --help` 不包含 `validate`；实际运行 `validate --help` 返回 invalid choice。
- `hermes plugins doctor --help` 支持 `--ci` 和可选的插件路径/已安装 ID。
- 该版本应使用 `hermes plugins doctor --ci PATH_OR_ID`，不执行 `validate`。此前固定源码比此安装版本更新，不能由源码核对推断此版本已兼容 Dashboard。
- 用户执行 `git -C /home/ubuntu/.hermes/hermes-agent rev-parse HEAD` 返回 not a git repository，远端源码 commit 记为 unavailable。
- 是否隔离测试机尚未确认；以下安装命令仅适用于隔离测试环境。

### 用户提供的真实 Dashboard 截图

用户报告“成功了”，并提供真实 Hermes Dashboard 截图，确认：

- 宿主侧栏已出现并打开“用量管理”插件入口。
- 插件组件渲染“用量管理 · Hello Hermes”，浅紫 CSS 已加载。
- 页面显示“Live 路由”和“API 连接正常”，插件版本 0.1.0；依据当前组件响应校验逻辑，可确认真实 health 请求返回了兼容响应。
- 采集和存储仍显示 unavailable，符合 M0 范围。

截图文件：`C:/Users/it/AppData/Local/Temp/codex-clipboard-b4a411b5-f97d-4615-9f25-fb4955226213.png`（用户本地临时附件，非发行包文件）。本代理没有远程登录或独立检查服务器。UI 中“尚未验证 Hermes 集成”是 POC 的固定保守文案，不是本次请求失败；本轮仅更新验收记录。

源码构建检查已证明产物未携带第二份 React；截图补充证明组件能够在真实宿主渲染。doctor 原始输出、浏览器 Console/Network、切换/重挂载、真实 Hook 触发、隔离模式和自定义 base path 仍无直接证据。截图顶部还包含宿主 agent 意外重启提示，发生时间及原因未核对，不能从截图判断与插件有关。

## 官方证据

文档：[Dashboard 扩展](https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard)、[Python 插件](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)、[Hooks](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks)。文档会变化，下面以固定 commit 的源码为核对依据。

| 协议 | 固定源码证据 | M0 使用方式 |
|---|---|---|
| React 与注册 | [web/src/plugins/registry.ts](https://github.com/NousResearch/hermes-agent/blob/525dbcad8d744710a43d01eb7366500e46eacbf4/web/src/plugins/registry.ts)，`exposePluginSDK`、`registerPlugin` | 从 `window.__HERMES_PLUGIN_SDK__.React` 取实例，同步 `register(name, Component)` |
| SDK 类型 | [sdk.d.ts](https://github.com/NousResearch/hermes-agent/blob/525dbcad8d744710a43d01eb7366500e46eacbf4/web/src/plugins/sdk.d.ts) | 只定义使用到的接口子集，无虚构 SDK 方法 |
| API 认证与前缀 | [web/src/lib/api.ts](https://github.com/NousResearch/hermes-agent/blob/525dbcad8d744710a43d01eb7366500e46eacbf4/web/src/lib/api.ts)，`fetchJSON`、`BASE` | 使用 SDK.fetchJSON，不手取 token，不用裸 fetch 绕过宿主 |
| Dashboard 发现与 API 挂载 | [web_server_dashboard.py](https://github.com/NousResearch/hermes-agent/blob/525dbcad8d744710a43d01eb7366500e46eacbf4/hermes_cli/web_server_dashboard.py)，`_get_dashboard_plugins`、`_mount_one_plugin_api` | dashboard manifest + `router`，挂载 `/api/plugins/hermes-usage-manager` |
| Python 加载 | 同上，`spec_from_file_location`、`sys.modules`、`exec_module` | router 文件自包含，不假定相对包导入；pytest 按相同文件导入形态测试 |
| Hook | [hermes_cli/plugins.py](https://github.com/NousResearch/hermes-agent/blob/525dbcad8d744710a43d01eb7366500e46eacbf4/hermes_cli/plugins.py)，`VALID_HOOKS`、`PluginContext.register_hook` | 仅注册 `pre_llm_call`，`**kwargs`，返回 None；本阶段不采集 |
| Manifest | [plugins_manifest.py](https://github.com/NousResearch/hermes-agent/blob/525dbcad8d744710a43d01eb7366500e46eacbf4/hermes_cli/plugins_manifest.py) | `manifest_version: 2` 与 `api_version: 1` 分离 |
| CLI | [subcommands/plugins.py](https://github.com/NousResearch/hermes-agent/blob/525dbcad8d744710a43d01eb7366500e46eacbf4/hermes_cli/subcommands/plugins.py)、[plugin_validate.py](https://github.com/NousResearch/hermes-agent/blob/525dbcad8d744710a43d01eb7366500e46eacbf4/hermes_cli/plugin_validate.py) | 真实测试使用 validate / enable / doctor；本机未执行 |

### 与 README 示例的差异

1. README 称 API 需重启。当前源码 `_try_hot_mount_plugin_api` 支持未挂载插件首次请求热挂载；已挂载路由的代码替换仍需重启。本项目继续使用重启流程，避免依赖新版特性。
2. 当前源码限制项目级 `./.hermes/plugins/` Python API 自动导入；需安装到测试 Hermes 的用户级插件目录并显式 enable。仅在工作区放 manifest 不证明后端能加载。
3. 源码存在隔离 plugin host 分支，不能以本地 FastAPI 直接导入测试代替真实隔离模式验证。
4. health 采用 README 10.3 的直接健康响应，扩展 version / milestone / data_source / capabilities；业务查询 envelope 留待 M2。`status=ok` 仅表示健康路由可响应，存储/采集均为 `unavailable`。
5. 不声明 `license: MIT`：仓库尚无用户选定许可证，不凭示例替用户确定授权。
6. 补充 `description` 和 `provides_hooks: [pre_llm_call]`；官方 validate 会比对实际注册能力与声明，不能仅复制 README 的最简 YAML。

## 原型阅读记录（9/9）

| 文件 | 已核对内容 |
|---|---|
| 概览.png | 三组 KPI、双轴趋势、部门柱图、三分布饼图、用户排行 |
| 使用分析.png | 部门/日期筛选、堆叠柱与活跃人数、两饼图、用户排行 |
| MCP分析.png | 服务筛选、面积趋势、可滚动工具排行及 Tooltip |
| 用量明细.png | 请求状态、模型与用量表、筛选及分页 |
| 对话审计.png | 会话表、部门/人员/日期筛选 |
| 对话审计-对话详情.png | 与列表近似，未提供独立详情设计，详情留待补充设计 |
| 人员设置-用户列表.png | 用户/部门列、搜索与分页、内嵌 Tab |
| 人员设置-部门分配.png | 实际为部门列表，含新建/编辑/删除 |
| 人员设置-部门分配-1.png | 双列表、选择、搜索、部门迁移 |

M0 仅借用浅薰衣草容器、紫色胶囊按钮与圆角，不提前实现上述 M1 页面。

## M0 真实 Hermes 测试命令（历史流程，非当前 M1 更新命令）

以下仅在独立测试机器或明确隔离的测试账号上执行。使用已有 Hermes 测试安装，不连接生产；先记录实际版本/commit。官方源码基线不等于兼容任意旧版。

```bash
hermes --version
hermes plugins --help
hermes plugins doctor --help
git -C /home/ubuntu/.hermes/hermes-agent rev-parse HEAD

# 将 M0 zip 上传至当前目录；子 shell 中任一步失败即停止
(
set -eu
test -f ./hermes-usage-manager-0.1.0-m0.zip
if [ -e "$HOME/.hermes/plugins/hermes-usage-manager" ] || [ -L "$HOME/.hermes/plugins/hermes-usage-manager" ]; then
  echo "插件目录已存在，停止；请先检查现有安装。" >&2
  exit 1
fi
mkdir -p "$HOME/.hermes/plugins"
python3 -m zipfile -e ./hermes-usage-manager-0.1.0-m0.zip "$HOME/.hermes/plugins"
hermes plugins doctor --ci "$HOME/.hermes/plugins/hermes-usage-manager"
hermes plugins list
hermes plugins enable hermes-usage-manager
hermes plugins doctor --ci hermes-usage-manager
hermes dashboard --no-open
)
```

子 shell 的 `set -e` 确保检查失败时不继续后面的安装/启用命令；单独在交互终端执行 `test` 本身不能保证后续命令停止。doctor 失败时保留输出并停止，不跳过检查或直接升级 Hermes。打包目录内的 FastAPI 依赖由测试 Hermes 环境满足；如缺失，在该测试环境按插件依赖声明安装后重启。以后发布 Git 仓库时可使用官方 `hermes plugins install OWNER/REPO --no-enable`，当前工作区不是 Git 仓库，不伪造仓库地址或创建提交。

打开测试机 loopback Dashboard（默认 `http://127.0.0.1:9119`），点击“用量管理”：

1. `GET /api/dashboard/plugins` 包含 manifest，静态 IIFE/CSS 返回 200。
2. 页面出现“用量管理 · Hello Hermes”，health 返回 `data_source=live` 且采集/存储 unavailable。通过页面的 SDK 请求验证认证；不要以无认证 curl 代替认证测试。
3. 无 invalid hook call、无第二份 React；切走/返回 Tab，Network 与 Console 无异常。
4. doctor 确认 `pre_llm_call` 注册；执行一条测试对话观察 Hermes 无异常。本阶段 callback 不存事件，不能以健康接口声称真实 Hook 已触发。
5. 重启测试 Dashboard 再次验证 API；记录宿主 Python/React 版本、隔离模式、源码 commit、doctor 原始输出与脱敏 health 样例。仅在 CLI 明确支持 validate 的其他版本补充该项。

## 未验证项与退出条件

真实 Hermes v0.21.0 的 Tab、组件渲染和 health 主链路已获用户截图确认；本地构建无重复 React。doctor 原始结果、真实 Hook 调用、浏览器错误检查、重挂载、隔离模式及自定义 base path 尚未补证，不能将全部运行时检查标绿，也不代表生产就绪。

可执行测试和本次输出见 `docs/m0-report.md`。M0 到此停止，等待下一阶段指令。
