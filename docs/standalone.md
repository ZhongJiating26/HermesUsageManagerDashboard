# 独立端口平台（0.6.0）

用户已明确选择独立端口仅显示用量管理，调整了此前“只能嵌入Dashboard”的交付约束。现在支持两种入口：原生Dashboard插件继续使用宿主React；独立入口提供自己的React/ReactDOM构建、管理员登录和FastAPI进程。两者复用同一业务router、迁移、SQLite和只读正文适配。Hooks仍由Hermes运行，不修改Hermes核心，不使用Desktop SDK。

独立端口不依赖9119运行，没有Hermes侧栏，不使用iframe或转发宿主登录令牌。它不是Mock，不回退到Fixture。一次性初始化独立管理员凭据后，可以由用户systemd服务常驻。安装/注册Hook不会自动启动监听、修改服务或开放防火墙。

## 1. 安装与版本检查

### 推荐：两条命令完成安装与初始化（Linux 用户 systemd）

安装时会先询问访问端口：首次默认 `9120`，回车使用默认值；已安装时回车保留当前端口。输入其他端口可更换脚本生成的服务端口，并自动备份旧服务文件，保留数据库和管理员密码。无交互安装可使用 `bash ~/.hermes/plugins/hermes-usage-manager/install.sh --port 9200` 跳过端口提示。访问地址及安全组放行端口应使用实际选择的端口；自定义服务配置仍需管理员检查。

正式安装分支为 `master`，包含运行文件和预构建前端，不包含测试与开发工具。远端默认分支设为 `master` 后，直接安装仓库地址即可，无需指定 SHA；见[分发说明](install-distribution.md)。

```bash
hermes plugins install --enable https://gitee.com/ZhongJiating26/HermesUsageManagerDashboard.git
bash ~/.hermes/plugins/hermes-usage-manager/install.sh
```

安装引导自动检测Hermes命令的Python解释器（无法识别时检查Hermes目录内的venv），首次只需交互输入两次管理员密码。按用户2026-10-20要求，脚本默认使用`--host 0.0.0.0 --allow-http`，自动创建私有目录及数据库、保存采集配置、生成并启动用户systemd服务；之后浏览器直接访问`http://服务器IP:9120`。公网和内网IP均可，无需配置public-url；客户端来源IP不由插件限制，但仍需登录。HTTP不加密，长期使用可配置HTTPS入口。云安全组/防火墙需允许9120；脚本不修改Gateway、安全组或防火墙。

直接IP模式只接受IP地址或localhost作为Host，不能使用任意域名；每次登录、写操作仍严格比较Origin与当前访问的协议、IP及端口，保留CSRF校验，不设置通配CORS，不信任X-Forwarded-*。域名/HTTPS入口继续用固定--public-url配置。现有自动生成的127.0.0.1服务会先备份再更新并重启；已有密码和数据保留，自定义unit或drop-in需由管理员检查。

只需本机访问时可运行`bash ~/.hermes/plugins/hermes-usage-manager/install.sh --host 127.0.0.1`。下方手动分步serve/service命令默认仍为本机监听；安装引导脚本才默认采用所有网卡。

最后按原启动方式重启Gateway以加载新版插件。无需在终端或Gateway服务手动设置数据库、实例ID、采集变量；实例ID继续使用现有自动生成规则。显式环境变量仍优先，已有Gateway若配置过旧数据库路径或关闭采集，应先调整对应旧配置。多Profile需分别运行对应Home的引导，或显式配置共享DB，不能自动跨Profile汇聚。

默认数据库为当前Hermes Home下的`plugin-data/hermes-usage-manager/usage.sqlite3`；共享设置保存在同目录的`settings.json`，凭据为`usage-manager-data/standalone-auth.json`。Home优先使用Hermes自身解析函数，独立环境则使用HERMES_HOME或~/.hermes；systemd保存解析后的Home。数据库和凭据不在源码目录中。重复运行保留已有密码和数据；已有unit完全相同可复用，不同则拒绝覆盖。

自定义监听参数可以直接追加，例如HTTPS代理入口：

```bash
bash ~/.hermes/plugins/hermes-usage-manager/install.sh --public-url https://usage.example.com
```

无systemd的环境使用Hermes实际Python执行`standalone.py setup`初始化，再执行`standalone.py serve`前台启动；两者都不再要求手动指定DB。setup不带--start-service时不会创建或启动系统服务。systemd失败会保留已经完成的配置并返回失败，可修复后重跑；仅安装插件或注册Hooks不会自动监听。下面保留手动分步命令供自定义部署使用。

新服务器首次安装：

```bash
hermes plugins install --enable https://gitee.com/ZhongJiating26/HermesUsageManagerDashboard.git
hermes plugins doctor --ci hermes-usage-manager
```

确认实际安装为0.6.0及以上且包含standalone.py。如果仓库尚未同步或目标安装器不同，不假定已有新功能；按实际版本停止检查。需要启用时执行hermes plugins enable hermes-usage-manager，不授予覆盖内置工具权限。不要求服务机安装Node、pnpm或本项目开发依赖。

已安装0.5.1的机器不要直接覆盖：停止独立服务（如存在）、Dashboard、CLI及全部相关Gateway后，用原有ops工具备份代码和外部DB，再按deployment.md升级代码，原DB路径/Instance ID不变。0.6.0没有新增schema迁移，仍不能跳过备份。

查看Hermes实际Python：

```bash
command -v hermes
head -n 1 "$(command -v hermes)"
```

后续PY必须使用输出中的真实解释器，不用系统python替代，也不盲目升级Hermes依赖。FastAPI/Pydantic/uvicorn缺失时先排查安装依赖提示。

## 2. 初始化独立管理员密码

下面PY为已验收Ubuntu机器示例；新机器需调整。DB新机可选新路径，现有测试机必须继续使用原usage-manager-m3-test-041/usage.sqlite3。

```bash
PY="$HOME/.hermes/hermes-agent/venv/bin/python3"
PLUGIN="$HOME/.hermes/plugins/hermes-usage-manager"
AUTH="$HOME/.hermes/usage-manager-data/standalone-auth.json"
export USAGE_MANAGER_DB_PATH="$HOME/.hermes/usage-manager-m3-test-041/usage.sqlite3"
"$PY" "$PLUGIN/standalone.py" init --auth-file "$AUTH"
```

交互输入两次12–256字符密码，不放在命令参数、环境、Git或聊天记录中。只保存scrypt盐与hash，无默认密码；凭据不放安装目录。Unix目录700/文件600，不安全权限拒绝，已有文件不会覆盖。Windows须额外核对ACL。密码忘记时，先停独立服务，把旧凭据移到私密备份路径，再重新init并重启；不删除业务DB。

## 3. 前台运行（默认9120）

```bash
"$PY" "$PLUGIN/standalone.py" serve --auth-file "$AUTH"
```

默认仅监听127.0.0.1:9120，浏览器访问http://127.0.0.1:9120，用刚设置的密码登录。只显示用量管理；9119可以关闭，Gateway按原方式运行。

如果使用SSH本地转发至19120，客户端先建立转发，服务端指定浏览器的准确来源：

```bash
# 客户端执行，将主机替换为真实测试机
ssh -N -L 19120:127.0.0.1:9120 ubuntu@测试服务器地址
```

```bash
# 服务端执行；浏览器必须使用这里的127.0.0.1而非localhost
"$PY" "$PLUGIN/standalone.py" serve --auth-file "$AUTH" \
  --public-url http://127.0.0.1:19120
```

直接IP访问仅供隔离测试，需明确允许HTTP并限制安全组/防火墙来源IP。例如：

```bash
"$PY" "$PLUGIN/standalone.py" serve --auth-file "$AUTH" \
  --host 0.0.0.0 --port 9120 \
  --public-url http://192.0.2.10:9120 --allow-http
```

该IP为文档专用示例，不是可访问的服务器，必须替换为实际测试地址。明文HTTP不能保证密码/会话传输机密性，不用于生产。未提供public-url的远程监听、未明确允许的远程HTTP均拒绝启动。

长期使用推荐HTTPS反向代理到127.0.0.1:9120，启动参数为--public-url https://你的实际域名。代理必须保留Host及Origin，不配置通配CORS，不移除认证，不信任任意X-Forwarded-*；uvicorn关闭proxy_headers。public-url必须精确包含浏览器来源的协议/主机/非默认端口，不包含路径。代理另行设置请求体大小和连接/请求限速。

## 4. 配置常驻服务（Linux用户systemd）

先停止前台serve避免占端口。使用与serve完全相同的host/port/public-url参数生成独立服务，例如仅本机监听：

```bash
"$PY" "$PLUGIN/standalone.py" service --auth-file "$AUTH"
systemctl --user daemon-reload
systemctl --user enable --now hermes-usage-manager.service
systemctl --user status hermes-usage-manager.service
```

service命令只新建~/.config/systemd/user/hermes-usage-manager.service，不覆盖已有unit，不调用systemctl、不修改Gateway服务。unit保存实际Python/插件路径/DB路径/监听参数，不保存密码；凭据文件在每次启动时读取。后台环境不会继承另一个终端的export，生成unit时会固化USAGE_MANAGER_DB_PATH。需要退出SSH后仍运行时由管理员检查该用户linger策略，不自动提权开启。

已有unit时保留并审查，不重复运行service强行覆盖；重装到相同插件路径后可复用原unit。完整卸载前使用systemctl --user disable --now hermes-usage-manager.service，避免下次登录尝试启动已移出的代码。ops快照包含插件代码/业务DB，不包含插件外的独立凭据或systemd unit；迁移机器时这些文件须另作私密备份，不能上传Git或混入公开zip。

早期安装引导生成的`WorkingDirectory="绝对路径"`可能导致systemd报告bad unit file setting。运行路径均已是绝对路径，新生成unit省略该字段。新版setup会对完全匹配当前参数的旧生成unit先备份再修复；自定义内容或参数不同仍拒绝覆盖。启动后检查`systemctl --user is-active --quiet`，失败不再打印启动成功。已安装机器可先执行`sed -i.bak '/^WorkingDirectory=/d' ~/.config/systemd/user/hermes-usage-manager.service`，再daemon-reload、restart并检查is-active；此修复保留数据库、密码及其他服务字段。仍失败时读取status诊断，不能视作已启动。安装器已经启用插件后，install.sh不再重复enable或请求内置工具覆盖权限。

停用独立入口：systemctl --user stop hermes-usage-manager.service。升级/卸载前也必须停止它；只停止Gateway和9119不再等于全部DB连接已停止。按用户最新要求，独立管理员登录后可直接查看当前Hermes Home的对话详情，不再要求手填本机映射；其他Profile/Home仍按configuration.md显式配置。

## 5. Hooks、数据与权限

- CLI/Gateway仍需USAGE_MANAGER_COLLECTION=1，并与独立平台指向完全相同的USAGE_MANAGER_DB_PATH；Instance ID保持原值。独立服务不代替Hermes采集，不擅自修改Gateway环境。
- 独立入口不需要USAGE_MANAGER_TRUST_DASHBOARD_ADMIN，它有自己的管理员认证；这不取消原生Dashboard的认证要求，也不改变其他插件。
- 独立登录目前是单管理员，不是员工自助/多租户SSO。密码正确后具有当前数据库的管理员权限。
- 会话8小时到期、进程重启全部失效，Cookie为HttpOnly/SameSite=Strict，HTTPS使用Secure；退出服务端撤销会话。登录每IP每分钟最多5次尝试，内存会话/限速表有上限，不依赖localStorage存令牌。
- CLI固定单worker；会话与限速在进程内，不支持将多个独立服务实例置于负载均衡后冒充共享登录集群。
- 业务API（包括health）均需登录；写入还需固定Origin和CSRF。Origin错误时检查public-url和实际访问URL，而不是关闭校验。
- 管理员登录后默认可读当前Hermes Home的正文、工具参数和结果；按调用ID关联参数，仍只读、分页、脱敏并记录审计。显式关闭变量或配置Profile映射仍优先，其他Home不自动开放；未知身份/缓存/费用不补零。
- 空库初次没有图表数据是正常状态；有采集后才显示真实记录。采集degraded需结合心跳与队列，不把进程退出当成零用量。

## 6. 本次验证边界

本地验证独立入口登录/退出、会话失效、真实SQLite业务读写、CSRF/Origin/Host、凭据权限/拒绝覆盖、包内独立加载与原生认证隔离；浏览器覆盖七页、移动端及无Hermes外壳。Linuxsystemd单元生成有受控测试，但尚未在目标机启动该unit；0.6.0的目标Hermes安装、实际9120访问仍需用户回传，0.5.1验收不冒充新入口实机通过。没有连接或改动生产服务器。

安全API依据：[Starlette Cookies](https://www.starlette.dev/responses/)、[TrustedHost](https://starlette.dev/middleware/)、[Uvicorn代理设置](https://uvicorn.dev/settings/)。
