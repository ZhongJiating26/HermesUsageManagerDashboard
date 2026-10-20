# M4 安全复核（本地，非生产批准）

## 0.6.0 用户授权的独立入口

### 依赖扫描记录（2026-10-16）

推送时GitHub提示3项moderate；随后本机pnpm audit --json返回1项moderate/1项high，来源/更新时点/统计口径不同，不将两者混算，也不宣称零漏洞。

- [ECharts GHSA-fgmj-fm8m-jvvx](https://github.com/advisories/GHSA-fgmj-fm8m-jvvx)：当前6.0.0落在受影响范围，6.1.0有补丁。公告针对Lines系列默认HTML tooltip；代码仅注册BarChart/LineChart/PieChart（Line不等于Lines），现有tooltip均richText。根据代码审查推断，当前配置没有使用公告触发组合，不等同于完整无漏洞证明。此轮未扩大依赖升级范围，后续升级需双入口完整回归，新增图表不得盲目启用Lines/HTML formatter。
- [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)：通过typescript-eslint/fast-glob/micromatch进入开发工具链；公告当前没有修复版本。该包不在原生或独立构建的运行时白名单、也不在交付zip，不在服务器运行Node的路径中；CI/开发环境仍应避免处理不可信glob输入。没有通过强制override或隐藏audit掩盖告警。

以上为当前扫描和触发条件审查，不是渗透测试或生产部署批准；保持隔离测试和既有认证边界。

用户明确改为支持独立端口仅显示平台，故原“只允许嵌入Dashboard”约束不再适用于新入口；原生IIFE仍无第二份React，独立构建有自己的React和许可，业务router/SQLite/Hooks不复制实现。独立服务是新的受保护FastAPI应用，不信任Dashboard Cookie、角色header、浏览器自报身份或X-Forwarded-*；自己的管理员认证只覆盖该应用，不修改原生get_principal实现。

无默认密码，交互init保存scrypt hash及盐、拒绝覆盖，配置在插件外；Unix权限检查，Windows另核对ACL。独立管理员拥有当前库管理员权限，非SSO/员工多角色系统。服务端有界会话/每IP登录限速、重启失效/退出撤销，凭据和会话不写localStorage或输出日志；验证错误不回显输入密码。Cookie HttpOnly/Strict，HTTPS Secure；固定Origin与CSRF保护写入，TrustedHost校验、CSP和no-store。Cookie按主机而非端口隔离，同一主机上的其他HTTP服务必须可信；多实例/不可信站点应使用不同域名。

默认loopback，不自动监听公网/写Gateway配置。远程HTTP必须显式allow-http，仅供隔离测试；生产使用HTTPS反向代理和来源限制，外层另设请求体/连接限速。独立认证文件/运行unit创建不自动启停服务、提权或开放防火墙。需将独立服务加入停写/备份/升级清单。Linux unit仅本地受控生成测试，尚未验证目标systemd启动；0.6.0不能沿用0.5.1实机验收。以下M4复核为原生入口历史基线，不构成新服务生产批准。

## 保持的边界

- 原生Web Dashboard + Agent Hooks，不引入Desktop SDK、不改Hermes核心、不替换宿主React、不建立独立生产站点。
- 元数据默认不开采集，正文另行opt-in、工具结果再授权；不读工具参数，不把Fixture回退到Live，未知身份/缓存/费用保持未知。
- 当前生产路由默认403，显式信任管理员桥接后仍执行宿主认证，缺接口503；写操作有Origin检查。浏览器角色参数不能提升权限，admin/auditor/用户/部门权限在服务端执行。
- 管理员桥接不是多租户SSO/RBAC实现：所有获宿主认证者映射为插件admin，仅可用于管理员受控Dashboard。此限制必须告知操作者，未声称生产多用户安全就绪。
- SessionDB只读、允许的绝对Profile目录、宿主归属映射、limit/offset、最大消息文本与连续读取上限；访问审计保留成功/不可用；纯文本渲染不执行原文HTML/脚本。
- 采集队列有界、确定性事件键、隔离/重试，SQLite事务和迁移checksum，成本冻结；未测强退场景不宣称exactly-once。

## 本轮运维工具防护

0.5.1修复：新备份目标封存为DELETE模式，再计算库存；inspect快照不再生成WAL/SHM导致恢复误拒绝。对Live WAL库的只读SQL连接可能产生SQLite附属文件，不等于文件系统绝对零写入；旧WAL快照维持严格校验，不删除/忽略额外文件来强行恢复。已补精确操作顺序回归，原库journal模式不改。

- zip及helper SHA256可核对，内嵌逐文件库存；拒绝路径穿越/绝对路径/Windows盘符与反斜杠、重复与大小写冲突、symlink/特殊文件、加密zip、超出64MiB或2048成员的包。
- 校验与解压使用同一份已校验字节，避免校验后重新打开被替换的zip。只解压到新绝对目录，不覆盖现有文件。
- 文件系统路径拒绝symlink/重定向；备份、恢复目标必须不存在，工具无删除、自动服务控制或直接覆盖能力。快照为私有目录、Unix文件600/目录700；Windows需另行配置NTFS ACL。
- SQLite backup先识别插件schema与数据源，拒绝Hermes核心state.db及非插件库；包含已提交WAL数据，30秒进度超时和quick_check，不用裸文件复制做在线备份。恢复只输出新目录，校验完整库存后才复制，不自动应用到原DB。
- 回滚必须停止全部写入者、成对恢复旧代码/schema匹配DB、保留失败现场；快照后的新数据丢失风险由操作者确认，不删WAL/SHM强行覆盖，不伪造迁移记录。

## 已知限制 / 未完成

SHA不是发布签名；同渠道被同时替换的包和checksum不能被此机制识别。源工作区dirty状态被如实记录，正式发布的干净commit/tag仍待授权。没有SBOM/联网漏洞扫描结论，不将“不打包React”当作全部供应链安全保证。

宿主私有认证函数会随版本变化，正文脱敏为启发式、SQLite/备份无应用级加密；未验证所有真实Provider、故障恢复、多Profile并发、全平台ACL/滚动容器或生产反向代理。Hermes曾有MCP协程告警，不在插件内猴子补丁核心。

结论：可以进入隔离测试机的M4候选包验证；不可据本地回归或M3验收直接批准生产部署。新服务器、真实升级/回滚/卸载回传前M4不标完成。
