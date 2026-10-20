# M4 测试交付手册（0.5.1 候选包）

本手册主体保留0.5.1历史交付流程。0.6.0新增独立端口，请以standalone.md为当前安装/启动说明。用户免除新服务器验收后M4按调整范围完成，但0.6.0新入口仍待目标机回传。后续停写流程须额外停止hermes-usage-manager.service或前台serve；不可只停Gateway和9119便替换代码/DB。旧zip/标签不改写，0.6.0包含独立构建，不能混用0.5.1校验文件。

0.5.0快照检查后恢复误拒绝已定位，若正在续验用户现有测试机，先按m4-051-recovery.md使用0.5.1新工具在新目录重新取快照；不要删除旧sidecar、改snapshot.json或继续执行旧0.5.0升级脚本。

用户已选择暂时只使用现有测试机，先验收升级/回滚：按第2节校验暂存，通过后再进入第4节。第3节全新服务器安装仍保留待验，不自动跳过M4退出条件。

M3已提交61b7663。0.5.1是M4候选包，不是已完成新服务器验收的生产发布。本地没有Hermes；本文远端步骤由用户在隔离测试账号执行，Codex不连接服务器。不要修改Hermes核心、关闭认证或安装Desktop Plugin SDK来绕过问题。

## 1. 发布与依赖边界

- 目标已验证基础为Hermes v0.21.0 / Python3.11.15 / FastAPI0.133.1；0.5.1在目标上的doctor与UI仍待执行。五Hook保持不变，辅助Hook缺失明确显示；SQLite仍为0001–0005，不新增schema迁移。
- 构建机需要Git、Python3.11+与requirements-dev.txt、Node20+、pnpm及frontend依赖。Linux/macOS用`bash scripts/package-release.sh`，Windows按development.md。服务机不需要Node、pnpm、源码仓库或本项目开发依赖；Python运行依赖由Hermes解释器提供，需要FastAPI、Pydantic2.9+及ZoneInfo/时区数据。不盲目pip install开发requirements或升级Hermes依赖；doctor不通过应先回传诊断。
- 原生包包含plugin.yaml、register(ctx)、dashboard manifest/router、编译IIFE/CSS/本地字体/许可、backend/migrations、docs与stdlib运维工具；不包含React/ReactDOM、Mock、fixtures、node_modules、测试代码或SQLite数据。
- zip内release.json逐文件SHA256与source_revision/source_dirty/source_tag/release_status，zip和外置ops.py的SHA256在同名.sha256内（固定LF）。检查可发现损坏/库存不一致，不是发布者签名；三个文件必须通过可信渠道传输。source_dirty=true或无匹配tag时标记candidate；正式发布需用户授权提交并建立v0.5.1 tag，然后运行`python scripts/package_release.py --require-tag`或`bash scripts/package-release.sh --require-tag`。严格模式拒绝脏工作区/未匹配HEAD的tag，不覆盖既有候选包；本轮不创建tag。固定zip成员时间/权限/顺序保证相同输入与工具链的可复现性，不承诺跨所有工具链字节一致。
- 运维工具只验证、暂存、备份或恢复到新目录，不启停服务、不覆盖目标、不编辑Hermes配置、不执行数据库迁移。失败可能留下私有半成品目录，保留检查，不盲目继续。

## 2. 先做离线校验（当前建议只执行到这里）

用户将以下3个文件上传到测试账号$HOME：

1. hermes-usage-manager-0.5.1.zip
2. hermes-usage-manager-0.5.1.sha256
3. hermes-usage-manager-0.5.1-ops.py

```bash
(
set -eu
cd "$HOME"
sha256sum -c hermes-usage-manager-0.5.1.sha256
PY=/home/ubuntu/.hermes/hermes-agent/venv/bin/python3
OPS="$HOME/hermes-usage-manager-0.5.1-ops.py"
ARCHIVE="$HOME/hermes-usage-manager-0.5.1.zip"
SUM="$(awk '$2=="hermes-usage-manager-0.5.1.zip" {print $1}' hermes-usage-manager-0.5.1.sha256)"
"$PY" "$OPS" verify "$ARCHIVE" --sha256 "$SUM"
workspace="$(mktemp -d "$HOME/hum-m4-stage.XXXXXX")"
chmod 700 "$workspace"
"$PY" "$OPS" stage "$ARCHIVE" --sha256 "$SUM" --output "$workspace/staged"
printf '后续暂存路径：%s\n' "$workspace/staged/hermes-usage-manager"
USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci "$workspace/staged/hermes-usage-manager"
)
```

回传SHA/verify/doctor结果和暂存路径，禁止跳过失败步骤。这里只写新的暂存目录，不替换已安装0.4.4，不启动采集或访问正文。新测试服务器上先`hermes --version`、确认实际Python解释器与`hermes plugins doctor --help`；没有doctor则停止，不拿新官网的validate替代目标CLI契约。

## 3. 新测试账号安装（不能冒充已执行）

必须是无旧安装的测试账号/新测试服务器，先确认Hermes和Dashboard可运行，完成第2节校验。将暂存路径赋值为实际输出，不能把下方占位路径直接执行：

```bash
set -eu
SRC=/实际暂存路径/hermes-usage-manager
DST="$HOME/.hermes/plugins/hermes-usage-manager"
test -f "$SRC/plugin.yaml"
test ! -e "$DST"
test ! -L "$DST"
mkdir -p "$HOME/.hermes/plugins"
cp -a "$SRC" "$DST"
USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci "$DST"
hermes plugins enable hermes-usage-manager
hermes plugins list
```

任何一项失败停止，不继续启动。新账号选新外部DB路径；不得指向旧Hermes state.db，也不得把Fixture导入Live。按configuration.md设置四个基础变量、默认关闭正文，再`hermes dashboard --host 127.0.0.1 --port 9119 --no-open`。通过SSH转发访问，保留宿主认证。验证Live/M4、storage ready、页面/统计API无403/503；空库无数据是正常状态，不能补Mock。新服务器首次请求/MCP验收由用户决定是否产生额度费用，不自动调用。

## 4. 旧测试机升级（先停止全部写入者）

当前用户实机已确认`hermes gateway stop`可用，用户服务hermes-gateway.service已inactive/dead且退出0，gateway list中default/test-a/test-b均not running；Dashboard仍需回到其前台终端Ctrl+C确认停止。不要为此读取/回传systemd Environment或.env，避免暴露凭据。验收结束恢复原运行服务，不现在重启Gateway。

第2节doctor通过后才进行。停止本测试账号的Dashboard、CLI及会写这个DB的Gateway/其他Profile进程；不要只停Dashboard就假定没有Hook写入，不结束无关服务。确认实际启动/监督方式，systemd等自动重启的服务先用对应服务管理器停止。保留当前认证配置，不修改其他插件。

在测试终端设置实际路径：

```bash
set -eu
export HERMES_PYTHON=/home/ubuntu/.hermes/hermes-agent/venv/bin/python3
export USAGE_MANAGER_DB_PATH="$HOME/.hermes/usage-manager-m3-test-041/usage.sqlite3"
export OPS="$HOME/hermes-usage-manager-0.5.1-ops.py"
export DST="$HOME/.hermes/plugins/hermes-usage-manager"
export SRC=/实际暂存路径/hermes-usage-manager
```

下面分步执行并检查结果，不拼接忽略错误的长命令：

```bash
test -f "$SRC/plugin.yaml" && test -d "$DST" && test ! -L "$DST"
USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci "$SRC"
"$HERMES_PYTHON" "$OPS" inspect-db --db "$USAGE_MANAGER_DB_PATH"
```

记录原计数（审计计数可能因后续UI访问增加）。建立同时包含旧代码和SQLite一致性备份的快照：

```bash
WORKSPACE="$(mktemp -d "$HOME/hum-m4-upgrade.XXXXXX")"
export WORKSPACE
chmod 700 "$WORKSPACE"
export SNAPSHOT="$WORKSPACE/snapshot"
"$HERMES_PYTHON" "$OPS" snapshot --plugin "$DST" --db "$USAGE_MANAGER_DB_PATH" --output "$SNAPSHOT"
printf '务必保存快照路径：%s\n' "$SNAPSHOT"
```

snapshot使用SQLite backup API，不能用运行中的裸db文件复制代替；包含WAL已提交数据并检查quick_check。只有操作成功且输出status=ok才继续。目录新建且不覆盖既有快照；Unix权限700/600，备份也视作私密数据。Windows需另核对NTFS ACL，POSIX chmod不是Windows权限保障。

确认DST仍为本账号预期插件目录、SRC为刚通过doctor的暂存目录，然后：

```bash
test "$DST" = "$HOME/.hermes/plugins/hermes-usage-manager"
test ! -e "$WORKSPACE/previous-plugin"
hermes plugins disable hermes-usage-manager
mv -- "$DST" "$WORKSPACE/previous-plugin"
cp -a -- "$SRC" "$DST"
USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci "$DST"
```

doctor失败立即停止，按第5节回滚，不enable或启动。成功才：

```bash
hermes plugins enable hermes-usage-manager
"$HERMES_PYTHON" "$OPS" inspect-db --db "$USAGE_MANAGER_DB_PATH"
```

按configuration.md保持原DB/Instance ID，不随升级改变Profile ID，关闭正文临时权限。启动Dashboard（默认loopback），Ctrl+F5，核对0.5.1/M4健康响应、旧记录/价格/人员映射、抽屉及统计；再inspect-db确认迁移仍为5步、模型/工具记录未减少。不把未产生新请求时的无心跳当作升级失败。当前发布没有新迁移，但不据此免除备份。

## 5. 回滚：先恢复到新目录，禁止直接覆盖运行中DB

停止全部写入者，保存失败版本的数据，先恢复快照到新目录验证，不删除任何文件。需要恢复DB意味着快照之后的新数据会丢失，必须由用户确认；可先仅回滚同schema代码，但不承诺任意旧版本能读当前schema。

```bash
export RESTORE="$WORKSPACE/restore"
"$HERMES_PYTHON" "$OPS" restore "$SNAPSHOT" --output "$RESTORE"
USAGE_MANAGER_COLLECTION=0 hermes plugins doctor --ci "$RESTORE/hermes-usage-manager"
"$HERMES_PYTHON" "$OPS" inspect-db --db "$RESTORE/usage.sqlite3"
```

只有全部成功后，确认DST和DB绝对路径均是这次测试账号的预期路径、全部写入者已停止。若`$USAGE_MANAGER_DB_PATH-wal`或`-shm`仍存在，停止检查连接，不删除sidecar后强行覆盖。恢复前再次对当前代码/DB建立新快照以保留失败现场，输出选未存在的新目录。用户确认后逐步移动失败插件到WORKSPACE的新目录、恢复旧代码；如确需恢复数据，将原DB移动到DB同目录的新归档名，再复制RESTORE/usage.sqlite3到原路径并chmod600（跨卷不依赖原子rename）。不提供递归删除命令，不恢复到Hermes核心state.db。

用已安装旧版本doctor通过后再enable、恢复原环境、重启Dashboard并确认旧版本及旧计数。回滚目标为与快照配对的代码+DB，不手动修改schema_migrations来欺骗旧代码。helper不会替操作者执行这些覆盖/移动。

## 6. 可恢复卸载与重新安装

仅在隔离测试机验证：停止全部相关进程，先snapshot，执行`hermes plugins disable hermes-usage-manager`；确认DST绝对路径后把整个插件目录移动到WORKSPACE下一个未存在的`uninstalled-plugin`目录，不删除外部DB。`hermes plugins list`检查不会再加载，重启Dashboard确认插件消失；其他插件/对话不应受影响。

重新按第2节校验/暂存后拷贝到空DST、doctor通过再enable，继续指向原DB；确认统计仍在。若要使用目标CLI的`hermes plugins remove`，先在独立账号上核对其帮助/源码并备份后验证，本轮不能把手工可恢复卸载仿真当成真实remove已通过。永久删除数据必须另获用户明确授权，本工具无删除命令。

## 7. M4退出与回传

回传：新服务器Hermes/Python版本、离线校验/doctor、无Node安装的Live健康与页面、升级前后inspect-db汇总、回滚/卸载/重装结果及异常。不要发送DB、正文、Key或完整配置。

现有测试机已完成0.4.4→0.5.1→0.4.4→0.5.1代码升级/回退/恢复，原库保留、快照恢复到新目录通过；可恢复移出/重装及Live页面正常获用户确认。不是CLI remove或数据库原位回滚验收。全新无开发环境服务器与正式tag仍待验证，见m4-acceptance.md。M4仍进行中；生产部署必须在测试完成后再获得用户单独确认。
