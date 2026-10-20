# 本地开发（0.6.0 双入口）

当前支持原生Dashboard和独立9120入口。独立入口由用户明确授权新增，不属于Mock回退；其登录/部署见standalone.md。下文M3/M4的旧状态为历史，以compatibility.md最新记录为准。构建顺序为先build:plugin再build:standalone，两份指纹均需存在才可打包。

M3已按用户要求提交61b7663；0.4.4目标实机基础验收报告见m3-final-acceptance.md。当前0.5.1添加交付校验与运维工具，仍声明五个基础Hook；目标0.5.1真实安装/升级/回滚及全新服务器未验收，不沿用0.4.4结果冒充通过。

产品契约见m2-design.md、m3-design.md；M3历史结果见m3-report.md，当前交付见deployment.md、configuration.md和security-review.md。本文只操作本地Mock，不连接远端。

## 启动与验证

Python >=3.11、Node >=20、pnpm。以下只运行本机 loopback Mock Host，不连接 Hermes 或生产服务器。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:HUM_PYTHON=(Resolve-Path .venv/Scripts/python.exe).Path
cd frontend
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run lint
pnpm run build:plugin
pnpm run build:standalone
pnpm test
pnpm exec playwright install chromium
pnpm run test:e2e
pnpm run test:standalone
pnpm run dev
```

浏览器访问 `http://127.0.0.1:8765/`。源码变更需要重启，启动时重新构建。Windows 的 python 若是 Store 别名，用 HUM_PYTHON 指向真实解释器。已有服务器占用8765时先停止自己的旧开发进程再运行 Playwright；测试不会复用现有服务器。

在另一个已激活 venv 的终端、仓库根目录：

```powershell
python -m pytest -q
python scripts/replay_fixture.py --repetitions 3
python scripts/replay_hooks.py
python scripts/package_release.py
```

当前环境没有全局 npm；可用 `C:\Users\it\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd`，也可直接调用 `frontend/node_modules/.bin/tsc.cmd` 等已安装工具。

## Mock 数据持久化

- 默认 Windows 数据路径：`%LOCALAPPDATA%/hermes-usage-manager-dev/m2-mock.sqlite3`；其他平台是 `~/.local/share/hermes-usage-manager-dev/m2-mock.sqlite3`。
- `HUM_MOCK_DB_PATH` 可设置另一条外部绝对路径。首次装入虚构 fixture（3 Profile、12用户、1080请求）；后续重启不重灌，不丢弃配置修改。
- 测试使用系统临时目录内的独立 DB，浏览器各测试注入 test-case header，在仅测试进程的 HUM_MOCK_TESTING=1 模式隔离。它不是生产身份机制，生产包不包含 dev 和 fixtures。
- 顶栏可切换 normal/empty/slow/error/forbidden 与模拟角色。empty 使用另一只空 Mock DB，不删除持久库。
- 如需全新演示，停止服务，设置新的 HUM_MOCK_DB_PATH；不要为了升级删除原数据库。
- M1/M2 截图仍生成在 `build/m1/`、`build/m2/`（回归用），M3新截图在 `build/m3/`；不要将标记Live的契约模拟截图视为真实Hermes验证。

## 原生运行

候选包build/hermes-usage-manager-0.6.0.zip包含原生声明、Dashboard router、backend与5步SQL迁移、原生IIFE/CSS/字体/许可、独立standalone.py和standalone/dist、stdlib运维工具，无Mock。原生IIFE无React/ReactDOM，独立构建包含自己的React运行时及许可，两者不混用。另生成.sha256和-ops.py。运行不需要Node，安装测试按standalone.md；旧package_m3.py仅为当前严格打包器兼容入口，不再生成旧M3版本包。

真实 DB 使用 `USAGE_MANAGER_DB_PATH`，否则尝试 Hermes 官方源码 helper。它与开发专用 HUM_MOCK_DB_PATH 不同。默认业务认证拒绝访问；受控测试才设置 `USAGE_MANAGER_TRUST_DASHBOARD_ADMIN=1`。缺少宿主内部认证函数时503，不降级。Hermes 进程环境须具备 FastAPI 与 tzdata；本仓库 `.venv` 不等于远端 Hermes 解释器。

storage ready仅证明SQLite可用。USAGE_MANAGER_COLLECTION=1才启动元数据采集；不启用则五个回调均无采集副作用。共享本机DB可设置相同外部USAGE_MANAGER_DB_PATH和稳定USAGE_MANAGER_INSTANCE_ID，Profile身份仍独立，不能把多个Profile强制设成同一个USAGE_MANAGER_PROFILE_ID。预期Profile清单未设置时不能声称全量覆盖。

`USAGE_MANAGER_SESSION_CONTENT=1`另行启用只读正文，必须设置明确的 `USAGE_MANAGER_SESSION_HOMES` 来源白名单；默认拒绝。工具结果再由 `USAGE_MANAGER_TOOL_CONTENT=1`单独控制，参数不读取。管理员正文权限独立于审计员元数据权限。所有选项、隐私限制与真实验收步骤见 `m3-design.md`、`m3-testing.md`。
