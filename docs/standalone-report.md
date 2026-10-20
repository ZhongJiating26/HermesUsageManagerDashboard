# 0.6.0 独立端口交付报告

## Milestone

M4后的用户授权需求变更：独立端口仅显示用量管理，不带Hermes外壳。保留原生Dashboard与Agent Hooks，扩展而非修改Hermes核心；用户免除新服务器验收的决定不变，不据此声称新环境实测通过。

## 已完成

- 默认127.0.0.1:9120的独立FastAPI入口，共用原业务router/SQLite/迁移/正文适配，不依赖9119。无新schema，原Hook声明保持五个。
- 独立React构建提供运行时，原生IIFE仍从宿主获取React，构建隔离；本地字体/许可、七页与Material3样式复用，无iframe、CDN或Mock回退。
- 交互密码初始化、scrypt盐/hash、私有文件/拒绝覆盖；有界服务端会话、8小时到期、重启失效/退出撤销、每IP登录限速、Origin/CSRF/Host、HttpOnly/Strict/HTTPS Secure、CSP/no-store，不回显验证输入密码。
- init/serve/service命令；service仅显式写新用户systemd unit，不覆盖旧文件、不启停服务、不改Gateway或防火墙。远程监听需明确public-url，远程HTTP还需显式allow-http，仅测试使用。
- 发布包包含独立入口与静态产物、独立构建指纹/许可校验；0.5.1标签/包不修改。安装说明改用用户提供Git仓库地址。

## 新建/修改文件

backend/standalone.py、standalone.py、standalone/dist、frontend/src/standalone.tsx与CSS、独立构建/浏览器测试配置、dev/standalone_test.py、tests/test_standalone.py、docs/standalone.md；修改版本声明/health契约、发布器/包装器、包测试、README/配置/开发/安全/兼容文档。开发测试入口不会打入交付zip。

## 执行测试与结果

- 完整pytest153通过（含独立认证、源库共享、接口隔离、服务配置生成、包内独立加载及独立构建指纹）。
- 原生Playwright32通过，独立端口Playwright4通过，IIFE3通过，合计192项。
- 类型检查、ESLint、双构建、原生无React/ReactDOM检查和Git空白检查通过。独立截图包含登录/桌面/移动端，仅为本地隔离数据库验证，不冒充真实Hermes采集截图。
- 保留Starlette/httpx弃用与Node颜色变量警告；未升级无关依赖消除日志。完整Bash包装器未一键执行，等效入口分别运行。

## 尚未验证项

0.6.0实际Hermes安装、现有测试机独立端口访问、Linuxsystemd真正启动、Unix权限分支与公网HTTPS代理仍待回传。Windows测试仅受控生成Linux unit，不称其已在systemd运行；新服务器免除/未验证。0.5.1的真实采集/升级验收保留，但不继承为0.6.0新入口已实机通过。

## 风险/需要确认

GitHub推送后提示依赖告警；本机audit返回ECharts中风险与开发链braces高风险，触发条件/运行时范围见security-review.md。没有无依据宣布告警全部清零，也未扩大到无关依赖升级。

独立入口目前是单管理员，不是SSO/多租户角色系统；凭据与unit不在ops代码/DB快照中，需另行私密备份。Cookie按主机而非端口隔离，同主机其他服务须可信；生产应使用专用HTTPS域名/代理与外层限流。HTTP仅显式隔离测试；不默认授权正文。升级/卸载/恢复前须停止独立服务及所有既有写入者，不能只停9119/Gateway。

## 下一步建议

按用户授权已将功能提交df4e49c推送master，并同步既有v0.5.1标签（仍指向57cf045）。未创建未经授权的v0.6.0标签、未部署远端。当前zip安装的0.5.1机器应先备份再安全升级，不假定它是可直接git pull的安装。首次设置密码并前台验证独立入口后，再选择用户systemd常驻。具体步骤见standalone.md。
