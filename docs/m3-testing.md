# M3 独立测试 Hermes 验收

当前尚未完成真实Hermes验收。以下是给用户在**独立测试账号/测试机**上执行的步骤，不是Codex已执行的远端操作。不要连接生产，不要直接覆盖已经成功的M0。M4升级/回滚部署流程尚未开展。

## 1. 先核对目标接口

`HERMES_PYTHON`必须指向Hermes实际使用的Python解释器，而不是随便一个python3。用户已确认v0.21.0路径如下。0.4.1包使用五个基础Hook，辅助Hook缺失应记录为能力缺口，不再把它当作五Hook基础模式的断言失败。

```bash
hermes --version
hermes plugins doctor --help
hermes chat --help
export HERMES_PYTHON=/home/ubuntu/.hermes/hermes-agent/venv/bin/python3
cd /home/ubuntu/.hermes/hermes-agent
"$HERMES_PYTHON" - <<'PY'
import inspect
import fastapi
from zoneinfo import ZoneInfo
from hermes_cli.plugins import VALID_HOOKS
from hermes_state import SessionDB
needed = {'pre_llm_call','post_api_request','api_request_error','post_tool_call','on_session_end'}
print('missing_hooks:', sorted(needed - set(VALID_HOOKS)))
print('auxiliary_hook_available:', 'post_auxiliary_call' in VALID_HOOKS)
print('FastAPI:', fastapi.__version__, 'TZ:', ZoneInfo('Asia/Shanghai'))
print('SessionDB:', inspect.signature(SessionDB))
print('get_messages:', inspect.signature(SessionDB.get_messages))
assert not needed - set(VALID_HOOKS), '目标版本缺少必需Hook，请停止并提供输出'
PY
```

v0.21.0没有 `hermes plugins validate`；使用doctor --ci。安装目录不是git仓库时无需补git信息，保留版本和这些签名即可。

## 2. 原生测试安装

先由用户自行将 `hermes-usage-manager-0.4.1-m3.zip` 放到测试账号当前目录。可先仅解压到临时目录校验，不覆盖现有M0：

```bash
(
set -eu
export HERMES_PYTHON=/home/ubuntu/.hermes/hermes-agent/venv/bin/python3
stage="$(mktemp -d "$HOME/hermes-usage-manager-check.XXXXXX")"
"$HERMES_PYTHON" -m zipfile -e "$HOME/hermes-usage-manager-0.4.1-m3.zip" "$stage"
USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci "$stage/hermes-usage-manager"
)
```

先回传doctor结果。下面正式测试安装流程仍仅供无旧插件的独立测试账号；任一步失败停止，不覆盖现有插件。

```bash
(
set -eu
test -f ./hermes-usage-manager-0.4.1-m3.zip
test ! -e "$HOME/.hermes/plugins/hermes-usage-manager"
test ! -L "$HOME/.hermes/plugins/hermes-usage-manager"
mkdir -p "$HOME/.hermes/plugins"
"$HERMES_PYTHON" -m zipfile -e ./hermes-usage-manager-0.4.1-m3.zip "$HOME/.hermes/plugins"
hermes plugins doctor --ci "$HOME/.hermes/plugins/hermes-usage-manager"
hermes plugins enable hermes-usage-manager
hermes plugins doctor --ci hermes-usage-manager
hermes plugins list
)
```

不要用Mock DB充当Live。已有真实DB时先做一致性备份并单独评审升级；0005是增量迁移，不删数据，但旧版降级应恢复备份，不能强行让旧代码解释新schema。

## 3. 两个终端使用同一组环境

在两个测试终端分别执行以下配置；这些是当前测试账号的外部目录，不是插件源码目录。Profile ID应以目标Hermes实际home/官方profile名称为准；若自定义home无法映射，可只对该进程显式设置USAGE_MANAGER_PROFILE_ID，不能让多个真实Profile共用一个ID。

```bash
mkdir -p "$HOME/.hermes/usage-manager-test-data"
chmod 700 "$HOME/.hermes/usage-manager-test-data"
export USAGE_MANAGER_DB_PATH="$HOME/.hermes/usage-manager-test-data/usage.sqlite3"
export USAGE_MANAGER_INSTANCE_ID=usage-manager-test
export USAGE_MANAGER_COLLECTION=1
export USAGE_MANAGER_TRUST_DASHBOARD_ADMIN=1
export USAGE_MANAGER_EXPECTED_PROFILES='["default"]'
```

终端A：

```bash
hermes dashboard --no-open
```

从经过认证的Dashboard进入“用量管理”；不要以无认证curl代替SDK认证。初始health应为0.4.1/M3/live，storage ready、collection unavailable；这只表示还没有采集进程的心跳，不是伪造零用量。辅助调用采集为partial，不能把主请求统计当全部调用。控制台不应有重复React/invalid hook call。

终端B：

```bash
hermes chat
```

发送一句仅要求回复短文本的测试问题，随后明确要求调用一项**当前已授权的MCP只读工具**。不要测试危险写操作；没有配置MCP时记录为未验证，不冒充通过。CLI具体非交互参数先以该版本chat --help为准。

保持聊天进程运行，回到Dashboard刷新：

- 标题information面板显示本库Profile心跳和最后入库时间；collection observed仅表示看见记录，hermes_runtime仍unverified。
- 用量明细出现真实provider/model、请求ID、源时间、tokens；与Hermes实际usage核对input_total含cache，不得重复加。没提供缓存/usage时应未知，不是0。
- MCP榜单只增加已确认MCP，普通terminal/web等本地工具不进入。失败重试与成功事件分开，无usage失败为未知。
- 人员映射按真实platform/external_id维护。无法证明sender链时显示未归属，不以Profile名称猜员工。
- 设置对应provider/model的有效日期价格后再发新请求；新记录才按当前有效价估算，原记录费用冻结。Canonical默认零无法证明cache来源时允许保持费用未知。
- 刷新、切换Tab、重启Dashboard不丢数据；Agent退出后心跳会过期，不能把旧心跳标成仍连接。相同事件稳定ID重播不得重复入库。

若invalid增长，或usage全未知，不要关闭校验。仅提供脱敏后的版本、签名、Hook字段**名称**、质量计数和错误码用于定位；不要上传真实message/history、args/result、api key、原始payload或完整state.db。

## 4. 正文读取为额外授权项

默认应返回SESSION_CONTENT_UNAVAILABLE且审计日志记录unavailable。需要组织明确授权后才在Dashboard进程设置：

```bash
export USAGE_MANAGER_SESSION_CONTENT=1
export USAGE_MANAGER_SESSION_HOMES="{\"usage-manager-test/default\":\"$HOME/.hermes\"}"
```

重启测试Dashboard。这个home必须是该Profile真实且批准读取的目录；不要把source_event字段作为文件路径。Provider通过已核对的SessionDB只读方法读取state.db，不查询私有表；旧版签名不兼容应503而非尝试写库。

验证管理员可翻页，审计员元数据可读但正文403；工具参数保持隐藏，工具结果默认隐藏；原始成功状态缺失时显示未知。若组织另行授权工具结果展示，再设置USAGE_MANAGER_TOOL_CONTENT=1。用**虚构**密钥文本测试脱敏，不发送真实密钥；脱敏是启发式，不是完备DLP。取消正文环境变量后重启，应恢复不可用。

## 5. 验收回传

保留doctor --ci原始结果、版本/签名、脱敏health与quality、一次请求和MCP计数前后对比、浏览器Console检查以及正文关闭/权限/分页结果。只有真实对话与MCP验证完成后，才能把M3退出条件标为通过；当前不推进M4或生产部署。
