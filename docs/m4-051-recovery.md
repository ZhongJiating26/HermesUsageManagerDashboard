# 0.5.0 快照恢复拒绝：0.5.1 修复与安全续验

## 事实与原因

用户在实际替换插件之前执行restore，得到通用ValueError并停止。因此未执行disable/mv/cp/enable，原0.4.4与原库尚未被此次脚本替换。旧快照/home/ubuntu/hum-m4-upgrade.0rwyvF/snapshot应保留，不删目录、WAL/SHM或改校验清单。

本地精确复现0.5.0问题：SQLite backup生成的快照继承源WAL模式，snapshot.json记录库存后，inspect-db的只读SQL连接仍会生成usage.sqlite3-wal/-shm；数据库主体hash未改变，但新增文件令严格库存校验拒绝restore。此前测试没有覆盖“snapshot→inspect快照→restore”这个实际顺序，已补回归。实机是否还有恢复目录已存在等因素，不能仅由通用ValueError区分。

0.5.1只在新备份目标上执行PRAGMA journal_mode=DELETE并检查成功，再quick_check、关闭连接、记录hash，使快照为自包含数据库；源Live库保持WAL。旧快照不会被自动改写，不忽略额外文件、不删除sidecar、不放宽hash校验。恢复失败新增明确SNAPSHOT_INVENTORY_MISMATCH或OUTPUT_EXISTS错误码。snapshot/restore成功输出snapshot_format/database_journal，不再用version:null表示快照动作。

0.5.0包保留历史，不再继续升级它。上传完整0.5.1 zip/.sha256/-ops.py，换新目录从未改动的旧插件与原库再建快照。不是把损坏/不匹配的旧快照强行标为有效。

## 仅暂存、重做新快照和恢复检查，不替换插件

前提：Gateway仍停止、Dashboard已Ctrl+C且无其他共享这个DB的写入进程。不要结束无关服务。若需要先恢复正常使用，可先暂停升级并恢复旧服务；之后续验必须重新停写和取新快照。

将三个0.5.1文件上传到$HOME，通过可信渠道核对checksum（SHA不是发布者签名），执行：

```bash
(
set -eu
state="$(systemctl --user show hermes-gateway.service --property=ActiveState --value)"
test "$state" = inactive
listeners="$(ss -ltnH 'sport = :9119')"
test -z "$listeners"

cd "$HOME"
sha256sum -c hermes-usage-manager-0.5.1.sha256
PY=/home/ubuntu/.hermes/hermes-agent/venv/bin/python3
OPS="$HOME/hermes-usage-manager-0.5.1-ops.py"
ZIP="$HOME/hermes-usage-manager-0.5.1.zip"
SUM="$(awk '$2=="hermes-usage-manager-0.5.1.zip" {print $1}' hermes-usage-manager-0.5.1.sha256)"
"$PY" "$OPS" verify "$ZIP" --sha256 "$SUM"

WORK="$(mktemp -d "$HOME/hum-m4-051.XXXXXX")"
chmod 700 "$WORK"
"$PY" "$OPS" stage "$ZIP" --sha256 "$SUM" --output "$WORK/staged"
USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci "$WORK/staged/hermes-usage-manager"

DB="$HOME/.hermes/usage-manager-m3-test-041/usage.sqlite3"
PLUGIN="$HOME/.hermes/plugins/hermes-usage-manager"
echo '=== 原库汇总 ==='
"$PY" "$OPS" inspect-db --db "$DB"
"$PY" "$OPS" snapshot --plugin "$PLUGIN" --db "$DB" --output "$WORK/snapshot"
echo '=== 新快照汇总 ==='
"$PY" "$OPS" inspect-db --db "$WORK/snapshot/usage.sqlite3"
"$PY" "$OPS" restore "$WORK/snapshot" --output "$WORK/restore-check"
USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci "$WORK/restore-check/hermes-usage-manager"
echo '=== 恢复副本汇总 ==='
"$PY" "$OPS" inspect-db --db "$WORK/restore-check/usage.sqlite3"
printf '新暂存路径：%s\n新快照路径：%s\n' "$WORK/staged/hermes-usage-manager" "$WORK/snapshot"
)
```

任一步失败即停，不重复同一个输出目录。预期新包doctor=0.5.1、旧代码恢复副本doctor=0.4.4，两侧均5 Hook；原库/新快照/恢复副本均Live、五步迁移，原基线模型3/工具1/会话2/Profile1/价格0/审计18（若曾恢复旧服务，则使用新的原库汇总对比，不强行改回这些数字）。成功后回传全部结果和新路径，再安排实际升级。此次仍不覆盖原DB或插件，Gateway保持停止。
