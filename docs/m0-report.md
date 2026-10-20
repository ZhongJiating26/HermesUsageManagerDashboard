# M0 阶段报告

后续实测更新（2026-10-15）：用户提供 Hermes v0.21.0 / Python 3.11.15 的 CLI 输出及真实 Dashboard 成功截图，确认插件入口、页面和 Live health 主链路成功。此版本无 validate，使用 doctor --ci；安装目录无 Git 元数据，commit unavailable。doctor 原始输出及其余运行时检查待补证。下面保留首次本地交付记录；最新验收证据以 `docs/compatibility.md` 为准。仍停在 M0，未开始 M1。

Milestone:

M0：官方接口核验与最小原生插件 POC。本地 Mock 部分完成；**真实 Hermes 的退出条件未满足，不能将 M0 全部验收标绿**。完成 README 全文和 references 9/9 图片阅读。未开始 M1–M4，未连接生产。

已完成:

- 检查 PATH 中的 Hermes：未安装，版本 unavailable；仅克隆官方公开源码用于阅读，固定 commit 为 `525dbcad8d744710a43d01eb7366500e46eacbf4`。
- 核对 Web Dashboard manifest、组件注册、SDK.React、SDK.fetchJSON、FastAPI router 文件导入和挂载协议、Hook 注册以及 CLI 参数。
- 原生 Python 插件清单和 `register(ctx)`，只注册无副作用 `pre_llm_call` 观察回调，不记录或修改消息。
- 正式 React + TypeScript IIFE，使用宿主实例；普通 script 加载一次注册“用量管理”组件，显示“用量管理 · Hello Hermes”。
- `/api/plugins/hermes-usage-manager/health`，Pydantic 响应约束；采集/存储为 unavailable，Hermes runtime 为 unverified。
- 独立本地 Mock Host 承载同一 router，Mock React 仅存在开发宿主；Mock 状态显著标识，失败无静默降级。
- 浅紫容器、圆角、胶囊按钮、错误/加载/重试和窄屏显示；清理卸载请求；预构建 JS/CSS 与最小测试安装 zip。

新建/修改文件:

| 范围 | 文件 |
|---|---|
| 插件 | `plugin.yaml`、`__init__.py`、`pyproject.toml` |
| Dashboard | `dashboard/manifest.json`、`dashboard/plugin_api.py`、`dashboard/dist/index.js`、`dashboard/dist/style.css` |
| 前端 | `frontend/src/entry.tsx`、`App.tsx`、`platform/hermes-sdk.ts`、`platform/react-host.ts`、`services/api.ts`、`theme.css` |
| Mock | `dev/mock_api.py`、`frontend/mock/index.html`、`frontend/mock/host.tsx` |
| 构建与测试配置 | `frontend/package.json`、`pnpm-lock.yaml`、`pnpm-workspace.yaml`、`tsconfig.json`、`eslint.config.js`、`playwright.config.ts` |
| 脚本 | `frontend/scripts/build.mjs`、`build-mock.mjs`、`check-bundle.mjs`、`dev.mjs`、`scripts/package_m0.py` |
| 测试 | `tests/test_m0.py`、`frontend/tests/bundle.test.mjs`、`frontend/tests/host.spec.ts` |
| 文档 | `README.md`（新增 M0 状态说明，保留规格）、`docs/compatibility.md`、`docs/development.md`、本报告、`CHANGELOG.md` |
| 开发环境 | `.gitignore`、`requirements-dev.txt` |
| 本地输出（不作为源码提交） | `build/plugin-metafile.json`、`build/m0-mock.png`、`build/hermes-usage-manager-0.1.0-m0.zip` |

执行测试与结果:

本机 npm 不在 PATH；使用内置 pnpm 11.25.0 执行 package scripts，Python 使用工作区 `.venv/Scripts/python.exe`。以下均为本次实际执行结果。

| 位置 / 命令 | 结果 |
|---|---|
| frontend：`pnpm install --frozen-lockfile` | 通过；esbuild 原生构建脚本在 allowBuilds 中显式允许 |
| frontend：`node scripts/build.mjs` | 退出 0：`PASS: single IIFE, no imports, no bundled React/ReactDOM; metafile checked` |
| frontend：`tsc --noEmit` | 退出 0 |
| frontend：`eslint src mock tests scripts playwright.config.ts` | 退出 0 |
| frontend：`node --test tests/bundle.test.mjs` | `tests 3 / pass 3 / fail 0` |
| 根目录：`python -m pytest -q` | `4 passed, 1 warning` |
| frontend：`playwright install chromium` | Chromium / headless shell 安装成功 |
| frontend：`playwright test`（设置 `HUM_PYTHON` 为工作区 Python） | `3 passed (3.1s)` |
| 根目录：`python scripts/package_m0.py` | 成功生成 M0 zip |

合计 10 项测试通过。构建 JS 4,325 bytes、CSS 1,638 bytes。模块图只有 6 个本项目输入模块，不含 node_modules；正式构建禁止 react、react-dom 及子路径运行时导入，AST 验证单 IIFE（允许 use strict 指令），产物无未解析 import/export。

浏览器实际加载 `dashboard/dist/index.js`，验证一次注册、健康接口 JSON、Mock 标签、卸载/重新挂载、390px 窄屏、503 错误、畸形响应、重试恢复、卸载取消未完成请求；页面异常列表为空。截图 `build/m0-mock.png` 已人工视觉核对。测试服务运行于 loopback，完成后无 8765 监听进程。

pytest 的单条警告是当前 Starlette TestClient 对 httpx 的弃用提示，不是 API 或测试失败。安装阶段 ESLint 9 有上游弃用提示；当前锁定版本 lint 已通过。后续依赖维护可单独升级，未以屏蔽警告处理。

尚未验证项:

- 真实 CLI 版本、`hermes plugins validate`、`doctor`、实际用户插件目录发现/enable。
- 真实 Hermes Tab 打开、宿主 React 运行、宿主认证/base path、隔离 plugin host API 挂载。
- 真实 Agent Hook 被触发；本阶段不声称已采集真实事件。
- SQLite、统计 API、ECharts 和 9 张原型对应的完整页面均在后续阶段，不属于本次实现。

风险/需要确认:

用户尚未指定测试 Hermes 发布版/commit；当前只能陈述与官方固定源码协议相符。README 所称 API 重启与新版首次热挂载差异、用户级插件 enable 门禁、隔离宿主分支均已记录在兼容文档。测试 zip 仅供隔离测试，不是生产就绪交付。许可证尚未选定，因此不声明 MIT。

下一步建议:

按 `docs/compatibility.md` 在隔离测试 Hermes 上解压、validate、enable、doctor、启动 Dashboard，确认真实 Tab/health 并记录版本及输出。**本轮工作到 M0 停止，等待下一步指令，不自动实施 M1。**
