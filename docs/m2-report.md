# M2 阶段报告

## Milestone

M2：SQLite + API + 统计口径，版本0.3.0。用户授权继续下一阶段；本阶段不接真实 Hooks，不自动部署远端。

## 已完成

- 四步可校验迁移、WAL/外键、有限忙等待、写事务回滚、数据库外置与 Mock/Live 模式隔离。
- 归一化事件 Repository、稳定事件/会话键、去重重播、缓存子集/未知值语义、UTC和时区分桶、微美元费用与历史价格修订冻结。
- 正式统计、请求/会话元数据、人员部门、价格、设置、审计与默认关闭的 CSV API。模型价格起止日、编辑和待设置区间保留并接 SQLite。
- 按平台外部ID/显式映射解析身份、历史主部门、迁移不改旧事件；MCP/本地/未知分类，同名不同Server分开；服务端权限及范围交集。
- React 页面共用正式 API；校验响应来源，不回退样例；本地 Mock 配置重启保留；真实正文缺失明确503并审计。
- 原生安装包包括 backend/迁移/构建产物，解压后脱离工作区可加载；构建不打包 React/ReactDOM，宿主复用方式不变。

## 新建/修改文件

- `backend/{db,events,identity,queries,admin,schemas,responses,security,api}.py`、`backend/adapters/hermes.py`、4个SQL迁移；路径隔离加载入口 `dashboard/plugin_api.py`。
- `dev/seed_sqlite.py`、`dev/sqlite_api.py`；前端 App/Dashboard/数据契约/图表/人员与价格页；浏览器按测试独立DB。
- `tests/test_m2_sqlite.py`、`tests/test_m2_package.py`、`frontend/tests/m2.spec.ts`；旧阶段测试按当前版本契约更新。
- `scripts/replay_fixture.py`、`scripts/package_m2.py`；版本声明、依赖、CHANGELOG、README、development/compatibility/m2-design/本报告。

## 执行测试与结果

在本机 Windows、Python venv、Node24.19.0 上执行：

| 命令 | 结果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | 40通过；其中包括M0/M1回归、M2数据库/公式/权限/独立解压加载 |
| `frontend/node_modules/.bin/tsc.cmd --noEmit`（frontend工作目录） | 通过 |
| `frontend/node_modules/.bin/eslint.cmd src mock tests scripts playwright.config.ts`（frontend工作目录） | 通过 |
| `node scripts/build.mjs`（frontend工作目录） | 通过；单IIFE、模块图/AST检查，无React/ReactDOM |
| `frontend/node_modules/.bin/playwright.cmd test`（frontend工作目录） | 21通过；原18项UI/批注回归+3项M2数据源/持久化契约测试 |
| `node --test tests/bundle.test.mjs`（frontend工作目录） | 3通过 |
| `.venv/Scripts/python.exe scripts/replay_fixture.py --repetitions 3` | new_rows=1，persisted_rows=1，total_tokens=120，source=mock |
| `.venv/Scripts/python.exe scripts/package_m2.py` | 生成 `build/hermes-usage-manager-0.3.0-m2.zip`；测试验证无dev/fixtures/DB/bytecode |

合计64个自动化用例通过。后端有1条依赖告警：Starlette 测试客户端使用 httpx 的弃用提示，不影响测试结果。重启持久化由 Store/Mock runtime 重新实例化验证；浏览器验证刷新持久化与价格编辑不改变旧费用。Live UI 用例只是对同路由响应来源做受控改写的契约测试，**不是已运行真实 Hermes**。

## 尚未验证项

- 本机未安装 Hermes；未对远端v0.21.0运行M2、doctor、真实认证、隔离宿主、base path、Linux文件权限或Windows ACL验证。
- 未真实采集模型请求/工具事件，未确认v0.21.0的usage语义、事件重试字段、跨进程及多Profile覆盖。
- 真实会话正文/脱敏策略未接入；未知字段不使用 Hermes 私有表猜测。
- 尚未做百万行规模压测或完整升级/回滚部署演练；不声称生产就绪。

## 风险/需要确认

- `_require_token` 是已检查源码中的内部适配点，目标版本可能不同；默认拒绝访问。仅隔离测试可显式 opt-in，缺适配返回503，不跳过认证。
- profile_user_mapping 已预留并在唯一显式映射时使用；用户Profile文本不是员工授权。当前原生适配仅管理员，无真实部门/个人SSO。
- 历史费用冻结：补价消除待设置区间不会自动重算旧请求。若将来需要重算，应新增显式审计任务，不暗改历史。
- 数据库必须外置并备份，不能把 Mock DB 用于Live；测试只覆盖当前DB配置范围，不代表公司全部Profile。

## 下一步建议

M2到此停止。下一阶段M3应先核实目标Hermes版本/Hook事件真实字段与身份来源，再接入Hooks、会话Provider和数据质量指标；最终真实集成/部署仍需单独授权。
