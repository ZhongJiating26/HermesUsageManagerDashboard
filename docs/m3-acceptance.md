# M3 最终验收清单（基础验收通过）

## 最终结论

用户提供目标cli.py:17804计算式，CLI将role=tool或含tool_calls的消息按条计数，因此一次调用的助手消息及工具结果消息可显示为2，与插件实际MCP1次不冲突，不能泛化为所有会话均除以2。结合0.4.4原生doctor、真实模型/MCP、正文开关/访问审计、持久化及新UI证据，M3在当前五Hook、单测试Profile范围基础验收通过。正式七项报告见m3-final-acceptance.md；下面“进行中/待核对”为历史，不自动扩大到实机重复投递、多Profile或辅助全覆盖。M4未开始。

## 最新Doctor补证：0.4.4通过

用户回传已安装路径原生doctor --ci：manifest=hermes-usage-manager 0.4.4，runtime discovery/manifest parsing/import/registration全部通过，0工具/5 Hook。正式补齐当前0.4.4目标版本证据，下面“当前安装0.4.2/版本待输出”为历史。

用户同时回传目标cli.py:17845退出摘要代码，输出msg_count、user_msgs、tool_calls，但片段未包含tool_calls计算赋值；不能由输出变量名推定两倍计数或漏采。需只读补看该变量计算，再完成口径对账。未触发新的模型/MCP调用。

## 最新截图补证：真实 Dashboard 新详情UI通过

用户在更新指引后反馈“没问题了”，并提供真实Hermes v0.21.0 Dashboard截图。截图一显示源会话20261016_082227_2455c4、真实标题、2条已加载消息及各消息时间，右侧抽屉、灰色遮罩和左右气泡正常；截图二显示另一个会话的503 SESSION_CONTENT_UNAVAILABLE，摘要与背景列表仍在。结合用户反馈，将新详情界面记录为目标宿主UI验证通过、既有记录仍可见；不再仅归为Mock。

两张截图涉及不同会话，不能推定拍摄时权限配置相同或都在正文关闭状态；关闭权限测试仍以此前明确回传为证。截图不含manifest版本，最后直接证实的doctor仍为0.4.2，当前实际manifest版本待新版输出。CLI“2 tool calls”与插件一次MCP的摘要口径仍待目标源码核对，不据此猜测漏采或去重成功。

## 当前安装版本已核实：0.4.2

用户在已安装路径/home/ubuntu/.hermes/plugins/hermes-usage-manager执行USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci hermes-usage-manager，实际manifest为0.4.2，发现/解析/导入/注册通过，0工具/5 Hook。这是当前安装0.4.2的原生验证，不是0.4.4实机验证。此前真实采集、正文开关和访问审计应归于用户测试机实际版本证据；0.4.4 UI确认来自本地Mock。

下一步按m3-042-testing.md备份更新测试机到0.4.4，保持原测试数据库，关闭正文临时权限，重启Dashboard并强制刷新。回传新版doctor及旧统计保留情况，不需要再次调用模型/MCP；CLI摘要计数差异仍单独待核对，不能拿版本差异当成原因。

## 最新用户补证：审计与MCP元数据通过

正文访问审计ok=4（最新2026-10-16T05:17:39.266827+00:00）、unavailable=9（最新2026-10-16T05:50:03.415589+00:00），确认成功与不可用访问均有留痕。指定MCP会话有一条mcp__sellersprite__trademark_country_list，tool_type=mcp、mcp_server_id=sellersprite、status=success、duration_ms=280、time_source=received。Server/类型/成功状态/耗时已得到结构化实机证据；received只表示工具发生时间使用接收时间，不能冒充可信源时间。下一步仍需核对目标CLI摘要计数实现及当前安装版本doctor；不再次调用卖家精灵。

## 已有证据

- 用户测试机Hermes v0.21.0，0.4.1原生doctor通过，5 Hook；辅助Hook缺失明确记录，不宣称全覆盖。
- 用户真实无工具主请求与卖家精灵MCP请求入库；只读查询模型3条、工具1条，队列4条done，丢弃/无效0。
- Dashboard重启后记录仍在；oneshot结束超过180秒后的degraded已定位为心跳过期，身份未知仍保留。
- 用户确认0.4.2经显式Profile映射可读正文；用户确认0.4.4当前浏览器详情布局/遮罩/滚动交互无问题。后者来自本地Mock浏览器验收，不扩大为目标Hermes所有设备验证。
- 当前本地0.4.4完整测试结果见m3-report.md；模型和工具事件三次隔离Mock重播不增加唯一记录，不把该结果冒充真实Hook重复投递证据。

## 当前步骤：关闭正文权限验证

用户回传结果：关闭正文开关并重启后，新请求返回503 SESSION_CONTENT_UNAVAILABLE，对话列表、用量统计、MCP统计仍正常。本项通过。未回传本次doctor输出，不能新增0.4.4目标doctor已通过的结论。下一项只读检查正文访问审计与既有MCP事件的Server/状态/耗时，不再次调用模型或MCP。

仅在已授权测试机Dashboard终端操作，Ctrl+C停止原Dashboard，保留宿主认证，不停止无关进程。为避免不同终端环境不一致，明确设置测试DB：

```bash
export USAGE_MANAGER_DB_PATH="$HOME/.hermes/usage-manager-m3-test-041/usage.sqlite3"
export USAGE_MANAGER_INSTANCE_ID=usage-manager-test
export USAGE_MANAGER_COLLECTION=1
export USAGE_MANAGER_TRUST_DASHBOARD_ADMIN=1
unset USAGE_MANAGER_PROFILE_ID USAGE_MANAGER_EXPECTED_PROFILES
unset USAGE_MANAGER_SESSION_CONTENT USAGE_MANAGER_SESSION_HOMES USAGE_MANAGER_SESSION_PROFILES USAGE_MANAGER_TOOL_CONTENT
USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci hermes-usage-manager
```

Doctor失败立即停止并回传；通过时记录实际manifest版本和5 Hook注册数，再启动：

```bash
hermes dashboard --host 0.0.0.0 --port 9119 --no-open
```

网络保持现有受限访问与宿主认证，不开放全公网。关闭旧详情，Ctrl+F5刷新，重新打开同一测试会话。预期列表/统计仍可读，正文返回503 SESSION_CONTENT_UNAVAILABLE；工具参数/结果不可见。不得以浏览器此前已显示的内容判断权限关闭失败；需要新请求。不得为通过测试关闭认证、将未知补零或改成Mock。

用户需回传doctor版本/注册数、正文错误码、列表/统计是否仍正常，无需正文或密钥。通过后再做访问审计记录检查及真实MCP Server/状态/耗时核对；仍不进入M4。

## 后续待核对

- 已通过：正文成功/关闭不可用访问均有审计记录，不要求正文写入插件库。
- 已通过：MCP结构化Server/状态/耗时；仍待核对CLI 2 tool calls与插件1次MCP的统计口径，不凭模型自然语言宣称已对账。
- 实机重复投递、身份归属、辅助覆盖缺口分别标记证据等级，不向真实采集库注入伪造事件来“验收”。
- 多Profile、异常强退和完整升级/回滚等未测场景不自动标绿，按README阶段范围归类。

M3是否完成须根据剩余证据逐项报告，不因UI通过或本地测试全部通过直接宣布整体完成。
