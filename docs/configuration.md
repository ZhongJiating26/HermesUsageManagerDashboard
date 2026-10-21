# 运行配置与安全边界

0.6.0新增可选独立端口入口，见standalone.md。独立入口自己的管理员登录不依赖USAGE_MANAGER_TRUST_DASHBOARD_ADMIN；此开关仍只属于原生Dashboard身份桥接。Hooks、数据库和正文授权设置共用，独立服务的systemd环境需单独配置，不继承另一个终端的export。升级/卸载/恢复前还必须停止hermes-usage-manager.service或前台serve进程。

## 基础配置

用量显示：M Token表示百万Token，数据库、API和CSV仍保留原始整数；仅展示层换算，未知值仍为未知。日期预设的近半年为180天、近一年为365天，均包含今天；`all_time=true`忽略日期界限但保留部门、人员和权限范围。超过366天的全部记录趋势按月汇总，超过20年按年汇总；自定义日期范围仍最多366天。

历史排行：管理员在“所有时间”下可查看`/history/users`提供的当前Hermes Home/Profile的state.db会话模型用量汇总。仅读取会话身份、父子关系和session_model_usage统计，不读消息正文、不改原库、不导入逐次请求表。平台身份通过已有人员映射解析，subagent仅继承明确的同Profile父会话；无法映射保持未归属，未知汇总不补零。历史汇总含主调用与辅助调用，与当前采集库的卡片/分布/逐次排行不相加；不支持将会话汇总精确拆分到任意日期范围。部门筛选按当前人员归属。该接口仅对具备audit_detail权限的管理员开放；Mock模式不读取真实Hermes数据。

供应商名称：当Hermes调用事件仅返回custom、auto或custom:变体时，插件只读当前Hermes Home的config.yaml，按该次调用base_url精确匹配providers/custom_providers条目。当前model.provider仅在model.base_url也匹配时优先；多个名称歧义、地址缺失或配置不可读时保留原始标识。原本有明确名称的供应商不改写。解析缓存只保留名称与地址，不保留API Key；事件与采集库不增加地址或凭据字段。费用按最终供应商名称匹配有效价格，不能确认价格时保持未知。

人员部门：请求中的空department_id表示“未分配部门”，数据库保存NULL。撤销部门会关闭当前department_membership区间，不创建虚假部门，不改写已有请求或工具记录的历史部门快照。重新分配时创建新的有效区间；普通用户与部门角色不能执行这些管理员写操作。

推荐先执行安装目录的`bash install.sh`：自动保存当前Hermes Home下`plugin-data/hermes-usage-manager/settings.json`，Hooks、原生Dashboard与独立入口共用其中的数据库路径，元数据采集随引导显式启用。没有设置文件且没有采集环境变量时仍默认关闭采集。`USAGE_MANAGER_DB_PATH`和`USAGE_MANAGER_COLLECTION`显式环境变量优先（包括值0），实例ID继续自动生成，无需手动配置。更改设置后按原运行方式重启相关进程。独立凭据路径也存入设置文件，重复setup保留数据及密码。其他权限变量不因安装引导而启用。

以下是仍支持的手动环境变量方式；已有服务若设置过旧值，需要先调整，否则会覆盖安装引导保存的默认配置。

在启动Dashboard和会话的各终端分别设置；新终端不会继承其他终端的export，进程启动后修改父终端也不会更新运行进程。不要把下面示例自动覆盖到现有服务环境；升级保持原DB和Instance ID。

```bash
export USAGE_MANAGER_DB_PATH="$HOME/.hermes/usage-manager-data/usage.sqlite3"
mkdir -p "$(dirname "$USAGE_MANAGER_DB_PATH")"
chmod 700 "$(dirname "$USAGE_MANAGER_DB_PATH")"
export USAGE_MANAGER_INSTANCE_ID=usage-manager-test
export USAGE_MANAGER_COLLECTION=1
export USAGE_MANAGER_TRUST_DASHBOARD_ADMIN=1
unset USAGE_MANAGER_PROFILE_ID
unset USAGE_MANAGER_SESSION_CONTENT USAGE_MANAGER_SESSION_HOMES USAGE_MANAGER_SESSION_PROFILES USAGE_MANAGER_TOOL_CONTENT
hermes dashboard --host 127.0.0.1 --port 9119 --no-open
```

这是新账号示例DB；既有测试机继续使用已验收的`$HOME/.hermes/usage-manager-m3-test-041/usage.sqlite3`，不能因为升级换库后把空数据误当丢失。上面不会启动/重启Gateway，服务管理方式需现场确认。

## 环境变量

| 名称 | 默认/作用 |
| --- | --- |
| USAGE_MANAGER_DB_PATH | 明确外部绝对路径优先；否则使用Hermes宿主helper。禁止指向Hermes state.db或插件安装目录；Mock库不能混入Live |
| USAGE_MANAGER_INSTANCE_ID | 建议稳定设置，同一实例不同Profile共享；跨机器不能靠同名ID实现聚合 |
| USAGE_MANAGER_COLLECTION | 仅值1开启元数据采集，否则回调无采集副作用；五个Hook注册仍可被doctor发现 |
| USAGE_MANAGER_PROFILE_ID | 默认按实际Hermes home解析；不要为不同Profile强制设置同一ID |
| USAGE_MANAGER_EXPECTED_PROFILES | 可选JSON数组，最多100个预期Profile；未设置只知道当前库已见范围，不代表公司全量覆盖 |
| USAGE_MANAGER_TRUST_DASHBOARD_ADMIN | 仅值1开启版本特定的宿主认证桥接；否则业务API默认403。只适合全部已认证访问者均受信任为管理员的Dashboard |
| USAGE_MANAGER_SESSION_CONTENT | 独立入口管理员默认可读当前Hermes Home的对话；原生Dashboard仍默认关闭。显式0可关闭，1启用有界只读正文 |
| USAGE_MANAGER_SESSION_HOMES | JSON映射instance/Profile到允许的绝对Hermes home；只读取其中现有state.db，不接受HTTP传入路径 |
| USAGE_MANAGER_SESSION_PROFILES | 可选JSON映射instance/Profile到真实宿主profile_name，例如home哈希ID映射default；未设置仍严格比较原ID，不默认放宽 |
| USAGE_MANAGER_TOOL_CONTENT | 独立入口管理员默认可读脱敏后的工具参数与结果，原生Dashboard仍默认关闭；显式0同时隐藏参数和结果 |

HUM_MOCK_DB_PATH/HUM_MOCK_TESTING仅用于开发Mock，不是服务机身份/数据源开关。时区与导出等业务配置保存在插件SQLite，默认Asia/Shanghai；费用是版本化价格估算，不是账单。

正文配置示例和验证后关闭方法见m3-042-testing.md。授权范围是Profile级而不是一条会话。通过审计页的管理员校验才读取正文，成功/拒绝/不可用写入访问审计；正文不复制到插件库，脱敏只是启发式，不能保证识别所有秘密。浏览器已经显示的数据不会因服务端关开关自动抹除，须关闭详情并刷新。

2026-10-20按用户要求调整独立入口：登录成功即当前实例管理员，不再要求手工打开正文开关或为本机默认Home填写映射。默认只读当前Hermes Home的state.db；自动识别本机Profile/旧版home哈希ID，并将默认Home映射到Hermes会话的default归属。其他Home或机器的数据仍须显式配置映射；不会根据客户端参数打开任意路径。旧实例标签但相同Home哈希的历史记录仍可读取。原生Dashboard的身份桥接和显式正文开关保持原有行为。

2026-10-21按用户要求补齐工具审计：优先使用Hermes保存的tool_name，通过tool_call_id关联先前assistant消息中的function.arguments，脱敏后格式化显示。分页最多回看200条同会话消息以关联跨页调用；匹配不到时明确提示，不猜测参数。工具参数与正文均不复制到插件数据库。

## 网络与身份

- 默认监听127.0.0.1；远程推荐SSH转发：客户端执行`ssh -N -L 19119:127.0.0.1:9119 ubuntu@测试服务器地址`，浏览器访问localhost:19119，仍需Dashboard认证。
- 如果必须监听0.0.0.0，云安全组/防火墙只允许测试人员IP，外网使用HTTPS/VPN，保留Hermes认证；不添加跳过认证参数，不启用通配CORS。
- 当前桥接调用宿主私有_require_token，缺接口时503并拒绝访问。桥接将通过验证的Dashboard访问者作为管理员，不是宿主细粒度角色映射；拥有普通用户的共享Dashboard不得开启此桥接充当完整RBAC。生产多用户身份集成未验收，不能只靠query/header自报角色。
- 不保存Provider Key、模型输入、工具参数或完整结果到采集队列；固定脱敏告警不输出原异常载荷。SQLite及备份未内建加密，需文件权限、磁盘加密与组织保留/删除策略。

## 状态解读

- Live只表示真实路由/数据源，不代表所有宿主能力都通过验收。hermes_runtime=unverified是运行时保守值，人工验收记录另见compatibility.md。
- oneshot退出180秒后无新心跳时degraded可能只是进程结束；结合队列待处理/隔离/丢弃/无效计数判断。
- 辅助Hook在目标v0.21.0缺失，辅助用量未知非零；身份、缓存、成本缺失同样不能补零。
- CLI摘要按工具相关消息计数，一次调用的助手消息和工具结果可显示2；插件MCP按实际工具事件计数，不是通用除二换算。
