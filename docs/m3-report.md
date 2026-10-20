# M3 阶段报告

## 最终结论：M3基础验收通过

目标cli.py:17804由用户回传，tool_calls按role=tool或含tool_calls的消息条数计算，一次调用的助手调用消息及工具结果消息可显示2；与插件一次MCP不冲突，不是所有会话通用的除二规则。补齐0.4.4原生doctor及此前实机证据后，按README第13节退出条件，M3在v0.21.0五Hook、单测试实例/Profile范围基础验收通过。完整“Milestone/已完成/文件/测试/未测/风险/下一步”报告见m3-final-acceptance.md。仅文档收尾，无新实现或版本变更；M4未开始，不自动提交或部署。

## 当前0.4.4实机原生Doctor通过

用户最新完整输出确认manifest=hermes-usage-manager 0.4.4，发现、解析、导入、注册全部通过，0工具/5 Hook。此前目标版本未确认的限制已补齐；不将历史0.4.2仍视为当前安装版本。目标cli.py:17845摘要确实输出tool_calls变量，但现有片段未包含其计算方式，CLI 2与MCP 1的口径差异仍待核对。本轮只更新证据，无新代码、测试或外部调用。

## 用户实机新详情UI验收通过

用户在更新指引后反馈“没问题了”，提供真实Hermes v0.21.0 Dashboard新详情截图：一张显示旧测试会话标题、源ID、2条消息及来源时间、灰色遮罩/左右气泡；另一张显示不同会话正文503降级、摘要与列表保留。结合用户反馈，新详情UI实机验收通过、旧记录仍在；不再局限为Mock验收。两张图不是同一会话或已证明同一权限配置，不追加“同一关闭状态仍可读取”推断。当前manifest版本尚无新doctor输出；CLI摘要计数口径未解释。本次仅补文档证据，无代码变更或新测试。

## 最新实机Doctor确认目标仍为0.4.2

用户回传当前安装路径doctor --ci成功：manifest=hermes-usage-manager 0.4.2，runtime discovery/manifest parsing/import/registration通过，0工具/5 Hook。确认0.4.2原生验证；不将它写成0.4.4通过。真实请求、正文开关、审计与MCP元数据证据保留，最新UI仅本地Mock验收。需按既有备份安装指引更新测试机0.4.4、重启/刷新并确认持久化；不新增模型或MCP费用，不据版本差异解释CLI计数。M3尚未标为整体完成。

## 用户实机访问审计与MCP归属验收通过

用户只读查询回传：正文访问ok=4，最新2026-10-16T05:17:39.266827+00:00；unavailable=9，最新2026-10-16T05:50:03.415589+00:00。确认可读/关闭不可用两侧均记录访问审计。MCP会话20261016_083622_14517b有一条mcp__sellersprite__trademark_country_list，类型mcp、Server=sellersprite、状态success、耗时280ms，与CLI约0.3秒相符；time_source=received仍为接收时间降级，不冒充可信源时间。

上述项通过。尚未解释目标CLI的2 tool calls摘要，不将1条记录自动视为去重或无漏采证明；当前安装版本doctor未回传。仅更新证据文档，未运行新测试、未触发外部调用或修改运行代码。

## 正文临时权限关闭验收通过

用户明确反馈：按验收步骤关闭权限后，正文新请求返回503 SESSION_CONTENT_UNAVAILABLE，而对话列表、用量统计和MCP统计仍正常。确认默认关闭正文时优雅降级且元数据功能不受影响；与此前成功读取正文构成开/关两侧证据。不据此新增本次doctor版本确认或审计记录已存在的结论。下一步只读核对访问审计及既有MCP元数据，本轮仅文档更新，未运行新测试。

## 最终验收继续（进行中）

本轮执行scripts/replay_hooks.py：Mock临时库5个注册回调、同事件重播3次，唯一模型事件2条、MCP事件1条，原文未保留检查通过；M3采集与v0.21兼容专项50项通过，保留Starlette/httpx弃用告警。未重跑完整125项，未将本地重播计为实机幂等验证。本轮仅新增验收清单/更新报告，无运行代码或发行包变更。

用户确认当前0.4.4浏览器UI无问题，记录为本地Mock界面验收，不扩大为目标Hermes所有宿主/设备通过。继续M3，先按m3-acceptance.md验证关闭正文权限后新请求被拒绝且列表/统计正常，再核对访问审计与MCP结构化元数据。未向真实数据库重播测试事件，未进入M4或自动Git提交。

## 0.4.4 浏览器批注修正

执行测试与结果：完整后端90项、Playwright32项、IIFE3项共125项通过；类型检查、ESLint、正式构建、无React/ReactDOM打包及diff空白检查通过。覆盖遮罩、文档与宿主容器滚动锁、关闭后恢复、仅白区滚动且顶部不动、连续追加、失败同offset重试、工具跨批次合并、零进度拒绝、5000条上限和关闭中止请求。已查看build/m3/session-drawer-scroll-mask.png确认灰色遮罩及白区滚动画面，截图为Mock，不是实机。仍有Starlette/httpx弃用及Node颜色环境告警，未为消除告警改动无关依赖。

Milestone：M3 UI修正，未进入M4。

已完成：按4条用户批注加灰色遮罩，锁住文档及宿主滚动容器，关闭恢复原样式/优先级/滚动位置/焦点；白色记录区独立上下滚动，删除分页栏，接近底部自动有界加载并保留前文，跨批次连续工具段合并。失败原位置重试，关闭取消请求。已加载数与总消息数明确区分；单次查看最多5000条，达到上限明确提示后续未加载。

新建/修改文件：frontend/src/services/conversation.ts、components/common.tsx、SessionDetails.tsx、theme.css、tests/m3.spec.ts、session-detail.spec.ts；版本/构建产物及README、CHANGELOG、兼容与测试机指引。

尚未验证项：0.4.4真实宿主自定义滚动容器/移动设备行为、正文关闭权限拒绝读取、实机去重与CLI工具摘要差异。风险/需要确认：无界一次抓取正文被禁止，界面取消分页不等于后端取消有界读取；5000条安全上限会明确提示，不能当作完整正文。

下一步建议：本地Mock确认后按m3-042-testing.md备份更新测试机、重启Dashboard并Ctrl+F5，无需新的模型或MCP调用。不得部署生产或宣称M3整体完成。

## 0.4.3 对话详情原型还原

执行测试与结果：后端90项、Playwright26项、IIFE3项合计119项通过；类型检查、ESLint、正式IIFE构建及不打包React/ReactDOM检查通过。新增桌面/移动端抽屉、气泡对齐、长文展开、嵌套工具、焦点恢复测试和8项时间边界测试，原有分页/未知状态/503降级回归通过。已查看build/m3/session-drawer-desktop.png和session-drawer-mobile.png，与两张原型核对；均为标明Mock的本地测试画面，不是实机截图。仍有Starlette/httpx弃用及Node颜色环境告警。首次浏览器启动因本机子进程PATH/解释器环境缺失退出9009，显式指定本机Node路径及HUM_PYTHON后完整通过，未修改业务逻辑绕过检查。

Milestone：M3兼容与UI修正，不进入M4。用户已回传0.4.2真实正文可读；临时权限关闭后的不可读测试尚未确认。

已完成：完整查看用户最新指定的references/对话详情.png和references/对话审计-对话详情.png，纠正README旧“无独立详情设计”描述。改为右侧抽屉、顶部摘要、左右浅紫气泡、独立滚动、长文展开/收起、两级工具折叠；保留未知状态、分页、503降级、默认隐藏工具内容，支持窄屏与Escape/焦点恢复。只读Provider输出脱敏标题及可用来源消息时间，接口显示真实源会话ID；不扩大读取范围、不增加核心修改或正文落库。

新建/修改文件：frontend/src/components/SessionDetails.tsx、common.tsx、pages/RecordsPage.tsx、services/preview.ts、theme.css；backend/adapters/session_content.py、api.py；frontend/tests/session-detail.spec.ts、m1.spec.ts及tests/test_v021_compatibility.py；版本/构建产物和相关文档。

尚未验证项：0.4.3真实Hermes界面与来源消息时间字段可用性、关闭正文权限后拒绝读取、实机重复事件幂等和CLI工具摘要差异。风险：原型中的全量消息数/全部工具数不可凭当前分页或MCP范围推断，因此明确标为当前段消息/MCP调用；未知标题与时间不补造。

下一步建议：按m3-042-testing.md在测试机备份更新0.4.3，重新打开已有会话核对UI，无需新模型请求；验证后关闭正文临时权限。当前不自动提交Git，不部署生产。

## 0.4.2 正文归属兼容修复

本次执行后端完整测试82通过、IIFE测试3通过，类型检查/lint/正式构建及无React/ReactDOM打包检查通过。未重跑浏览器24项，不沿用旧结果冒充本次运行。后端仍有Starlette/httpx弃用告警。首次构建因从仓库根目录调用相对路径脚本失败，改为frontend工作目录后成功。最终包为build/hermes-usage-manager-0.4.2-m3.zip，目标Hermes doctor和正文实测仍待用户执行。

已定位宿主default名称与插件home哈希ID不同导致的503；新增显式归属映射与8项回归测试，保留目录白名单、只读、权限、分页、脱敏与工具结果默认隐藏。不迁移数据库或修改采集ID。测试机安装/关闭临时权限见m3-042-testing.md；插件正文实机验收仍未完成。

## 2026-10-16 持久化及 degraded 诊断补证

用户只读查询确认：2个采集运行记录、0个最近180秒心跳；丢弃/无效0，context_missing=4；队列4条全部done，模型请求3条、工具1条。依当前质量判定，degraded由心跳过期触发，无待处理/隔离队列证据；身份缺失仍是归属缺口，不等于事件丢失。不能根据本次检查证明无漏采、实际重复事件幂等或CLI摘要计数一致。

用户随后按指引重启Dashboard并确认记录仍在，Dashboard重启持久化验收通过。未验证Agent强制退出或机器重启场景；实机去重与默认关闭的只读会话正文仍待验收，M3整体未完成。本次只更新证据文档，未修改运行代码、未运行新测试。

## 2026-10-16 实机 MCP 补证

卖家精灵trademark_country_list测试会话20261016_083622_14517b由用户执行并回传：CLI工具约0.3秒，模型报告code=OK；Dashboard趋势与排行榜显示1次MCP调用，证明至少一次真实MCP元数据入库及读取。截图状态degraded，CLI摘要2 tool calls与页面MCP1次的计数范围尚待核对，完整Server/状态/耗时尚未确认，不判定整体通过或无漏采。待用户刷新数据质量，区分180秒心跳过期与无效、丢弃、隔离等原因。

宿主另报告tools/mcp_tool.py:6189协程未await的RuntimeWarning，不据此认定插件异常原因；不改核心。本次仅更新用户证据文档，未新增运行测试。实机去重、只读正文、重启持久化仍待验证。

## 2026-10-16 实机主请求补证

用户提供Hermes v0.21.0 / 插件0.4.1测试结果：CLI会话20261016_082227_2455c4成功完成，0工具调用；Dashboard截图为Live / M3 / observed，Profile心跳1/1，最后入库08:22:40（Asia/Shanghai），当前范围请求1。队列待处理/隔离/丢弃/无效均0，用量缺失0；身份未知1、缓存未知1、费用未知1。该证据确认一次真实主请求元数据采集和页面读取，不证明所有Token语义、费用计算或全Profile覆盖。辅助调用仍未采集，不能记零。

两个终端显式设置同一测试DB及采集开关并重启进程后成功；身份适配仅在Dashboard显式开启并保留宿主认证。未连接远程服务器，本次仅更新证据文档、未修改代码或运行新测试。MCP调用、实机去重、只读正文及重启持久化未验收，M3整体仍未完成；下文待验证描述按此最新补证更新理解。

## 0.4.1兼容预检修复

用户已回传v0.21.0实机Doctor通过：0.4.1临时包的runtime discovery、manifest parsing、import和registration均成功，0工具/5 Hook。该次明确关闭采集，仅做staging校验；现有安装替换、真实请求/MCP入库、正文读取和重启持久化仍待验证。本文后续“doctor尚待”描述为该补证前状态，以本条为准。

用户v0.21.0实机输出确认缺少post_auxiliary_call，且get_messages没有include_ancestors。当前manifest和注册均为五个基础Hook，辅助用量在质量API/UI标明不可用、非零；正文按公开签名协商有界参数，不以TypeError盲重试或回退私有SQL。当前测试包为build/hermes-usage-manager-0.4.1-m3.zip。

本地后端74项、浏览器24项、IIFE3项（合计101）通过；类型/lint/构建检查通过。五回调三次重播得到模型2条（主成功/失败）、MCP1条；辅助normalizer保留但没有注册/采集。新增兼容测试按用户提供的v0.21.0签名执行，并验证缺少有界分页参数时拒绝读取。

这只修复已知接口差异，不等于目标doctor或真实主请求/MCP/正文已经成功。当前辅助完整覆盖受宿主能力限制；不自行升级Hermes、不连接生产、不覆盖旧插件。先按m3-testing.md临时解压运行doctor并回传结果，以下0.4.0六Hook结果是历史。本地浏览器测试服务器另出现一次Windows连接重置回调日志WinError10054，24项仍通过；测试通过不表示没有运行时告警。

## Milestone

M3本地实现（0.4.0）；**真实Hermes退出条件未通过，等待独立测试验收**。用户要求先提交一版再继续：M2已提交为 `815b340 feat: establish M2 SQLite usage manager baseline`，作者身份只配置到当前仓库。未push，M3改动留在工作区，未额外自动提交。

## 已完成

- 复核官方插件/Hook文档和固定官方源码基线；注册六个原生观察回调，显式开启元数据采集，不修改Agent行为。
- 请求/工具归一化、缺字段未知、缓存不重复、辅助/失败attempt区分、当前作用域MCP归属、跨实例/Profile/会话去重。
- 有界非阻塞内存队列、durable pending/inbox、有限重试/隔离、退出尽力flush、脱敏固定告警、跨进程SQLite事务协调。
- 采集心跳、最后入库、丢弃/未知质量指标及显式Profile清单；标题information面板显示诊断，不直接铺小提示。
- 可选只读SessionDB Provider，正文与工具结果分别opt-in、管理员正文权限、来源白名单、审计、脱敏、分页、未知状态与不可用降级。
- 第五步增量迁移，Mock六回调三次重播，修复新并发请求暴露的初始化竞态，正式构建仍无React/ReactDOM。

## 新建/修改文件

- `backend/collector.py`、`backend/adapters/hooks.py`、`backend/adapters/session_content.py`、`backend/quality.py`、`backend/migrations/0005_collection.sql`。
- 原生入口/manifest/plugin声明、backend事件/API/质量/权限/版本契约、前端连接状态/质量面板/正文分页、Mock初始化锁。
- `tests/test_m3_collection.py`、`frontend/tests/m3.spec.ts`、旧版本回归契约、`scripts/replay_hooks.py`、`scripts/package_m3.py`。
- README、CHANGELOG、development、compatibility、m3-design、m3-testing、本报告及重建IIFE产物。

## 执行测试与结果

本机Windows、独立Python venv、Node24；未在本机安装或运行Hermes。

| 命令 | 结果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | 69通过，含M0–M2回归与M3归一化/队列/权限/迁移/发行包测试 |
| `tsc.cmd --noEmit`（frontend） | 通过 |
| `eslint.cmd src mock tests scripts playwright.config.ts`（frontend） | 通过 |
| `playwright.cmd test`（frontend） | 24通过，含原21项和质量面板/正文分页/不可用3项 |
| `node --test tests/bundle.test.mjs`（frontend） | 3通过 |
| `node scripts/build.mjs`（frontend） | 单IIFE，模块图/AST无React/ReactDOM |
| `.venv/Scripts/python.exe scripts/replay_hooks.py` | source=mock；6回调；重播3次；模型记录3（主成功/失败/辅助），MCP记录1；无原始payload |
| `.venv/Scripts/python.exe scripts/package_m3.py` | 生成 `build/hermes-usage-manager-0.4.0-m3.zip`；独立解压加载测试通过，无dev/fixtures/DB |

合计96项自动化测试。后端仍有1条Starlette/httpx测试客户端弃用告警，不影响结果。测试中发现并修复了新增并发请求触发的初始化竞态；没有通过复用旧服务器或扩大超时掩盖。浏览器Live字样仍是受控契约测试，不代表真实Hermes。队列压力测试是本地有限生产者/双worker/锁冲突测试，不等于生产规模压测。

## 尚未验证项

- 用户v0.21.0的六Hook是否全部存在、真实payload/CanonicalUsage语义、真实sender链与MCP作用域。
- 一次真实对话产生正确请求和MCP记录的退出条件；尚未取得真实doctor结果或连接目标服务器。
- SessionDB只读签名/返回字段、认证私有适配点、宿主隔离、base path、Linux权限/Windows ACL和真实共享多Profile部署。
- MoA/流式辅助调用完整对账、高负载长期运行、备份/回滚与组织正文授权。

## 风险/需要确认

- 采集默认关闭，需显式USAGE_MANAGER_COLLECTION=1；正文另行opt-in及来源白名单。启发式脱敏不是完备DLP。
- 官方CanonicalUsage丢失原字段presence，默认0不能证明缓存确实报告为0；未知仍为NULL，cache-write溢价未支持时不估价。MoA facade不重复入账，高级路由未声称全覆盖。
- 非阻塞内存到durable队列存在强杀丢失窗口；不声称exactly-once delivery。数据库坏时计数未必能持久化，只能结合固定告警/缺失心跳诊断。
- 当前库Profile覆盖不等于全公司；跨机器/NFS共享SQLite不支持，事实与审计元数据长期保留需运营方明确归档策略。

## 下一步建议

按m3-testing.md在独立测试Hermes验证并回传脱敏结果，再补齐兼容记录。到此停止，不自动部署、push、开始M4或宣称M3真实验收通过。
