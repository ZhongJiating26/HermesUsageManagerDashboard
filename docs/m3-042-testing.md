# 0.4.4 测试机正文与详情UI验证

本文件保留原路径便于已有链接访问；当前命令已更新为0.4.4包，包含0.4.2兼容修复、原型UI还原、遮罩/外层滚动锁及无分页的连续滚动。用户已确认0.4.2正文可读，不需要为UI验证再次调用模型或MCP。

实机SessionDB可以只读查到会话并有界读取2条消息，owner_profile=default；插件Profile ID为home-44a0dbab218426884fd7。0.4.1直接比较两种标识导致503。0.4.2新增USAGE_MANAGER_SESSION_PROFILES显式归属映射，未配置时仍严格比较原Profile ID，不自动将任意来源当作default。无效配置或归属不匹配拒绝读取。保留原目录白名单、管理员认证、只读连接、分页和脱敏。不改Hermes核心、会话库或已有采集ID。

这是Profile级授权，不是单会话白名单；工具参数不读取，结果仍隐藏。仅用于用户授权的测试机。由用户上传build/hermes-usage-manager-0.4.4-m3.zip到远端$HOME，停止测试Dashboard和chat后执行，不停止无关服务，不删除数据库：

```bash
(
set -eu
export HERMES_PYTHON=/home/ubuntu/.hermes/hermes-agent/venv/bin/python3
stage="$(mktemp -d "$HOME/hum-m3-044-check.XXXXXX")"
"$HERMES_PYTHON" -m zipfile -e "$HOME/hermes-usage-manager-0.4.4-m3.zip" "$stage"
src="$stage/hermes-usage-manager"
dst="$HOME/.hermes/plugins/hermes-usage-manager"
test -f "$src/plugin.yaml"
test -d "$dst"
test ! -L "$dst"
USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci "$src"
backup="$(mktemp -d "$HOME/hum-before-044.XXXXXX")"
chmod 700 "$backup"
printf '旧插件备份目录：%s\n' "$backup"
hermes plugins disable hermes-usage-manager
mv "$dst" "$backup/hermes-usage-manager"
cp -a "$src" "$dst"
USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci "$dst"
hermes plugins enable hermes-usage-manager
hermes plugins list
)
```

任一步失败停止并回传错误，保留备份，不继续启动。没有新增数据库迁移，不据此宣称完整升级/回滚验证通过。

## Dashboard终端

```bash
export USAGE_MANAGER_DB_PATH="$HOME/.hermes/usage-manager-m3-test-041/usage.sqlite3"
export USAGE_MANAGER_INSTANCE_ID=usage-manager-test
export USAGE_MANAGER_COLLECTION=1
export USAGE_MANAGER_TRUST_DASHBOARD_ADMIN=1
unset USAGE_MANAGER_PROFILE_ID USAGE_MANAGER_EXPECTED_PROFILES
export USAGE_MANAGER_SESSION_CONTENT=1
export USAGE_MANAGER_SESSION_HOMES='{"usage-manager-test/home-44a0dbab218426884fd7":"/home/ubuntu/.hermes"}'
export USAGE_MANAGER_SESSION_PROFILES='{"usage-manager-test/home-44a0dbab218426884fd7":"default"}'
unset USAGE_MANAGER_TOOL_CONTENT
hermes dashboard --host 0.0.0.0 --port 9119 --no-open
```

保留登录认证，仅允许测试人员访问；远程使用HTTPS、VPN或SSH隧道。Ctrl+F5刷新后，在对话审计打开20261016_082227_2455c4对应会话，预期可见用户和助手文本。抽屉外灰色遮罩且无法滚动；长对话仅白色区域滚动，无分页控件，底部按需加载且保留前文。关闭后外层恢复滚动。单次查看达到5000条时提示后续未加载，不等于所有消息已读完。无需再调用模型/MCP，无需发送正文，只回传可读与否或结构化错误。

## 结束后关闭权限

Dashboard终端Ctrl+C后执行：

```bash
unset USAGE_MANAGER_SESSION_CONTENT USAGE_MANAGER_SESSION_HOMES USAGE_MANAGER_SESSION_PROFILES USAGE_MANAGER_TOOL_CONTENT
hermes dashboard --host 0.0.0.0 --port 9119 --no-open
```

刷新后重新打开会话，预期正文不可用，统计仍在。关闭权限不擦除浏览器此前已显示文本，不分享测试页面。映射只影响正文归属校验，不解决人员身份/费用未知。
