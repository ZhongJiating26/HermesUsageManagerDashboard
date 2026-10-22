# Hermes Usage Manager

正式安装版 0.6.0，提供用量与费用统计、人员和部门分配、供应商与 MCP 分析及对话审计。当前版本已在 Hermes v0.21.0 上部署验证。

## 安装

安装时会先询问访问端口：首次默认 `9120`，回车使用默认值；已安装时回车保留当前端口。输入其他端口可更换脚本生成的服务端口，并自动备份旧服务文件，保留数据库和管理员密码。无交互安装可使用 `bash ~/.hermes/plugins/hermes-usage-manager/install.sh --port 9200` 跳过端口提示。访问地址及安全组放行端口应使用实际选择的端口；自定义服务配置仍需管理员检查。

先安装并配置 Hermes。以下步骤适用于 Linux 用户 systemd 环境，仓库默认分支须设为 `master`：

```bash
hermes plugins install --enable https://gitee.com/ZhongJiating26/HermesUsageManagerDashboard.git
bash ~/.hermes/plugins/hermes-usage-manager/install.sh
hermes gateway restart
```

首次按提示输入两次管理员密码（至少 12 个字符）。脚本自动寻找 Hermes 的 Python，创建数据库与凭据，保存采集配置并启动后台服务，无需手动设置环境变量。

默认监听 `0.0.0.0:9120`。在安全组或防火墙放行 TCP 9120 后，浏览器打开 `http://服务器IP:9120` 并登录。脚本不会修改安全组或防火墙。仅本机访问、HTTPS 和非 systemd 环境见[独立端口说明](docs/standalone.md)。

## 升级

```bash
hermes plugins install --force --enable https://gitee.com/ZhongJiating26/HermesUsageManagerDashboard.git
bash ~/.hermes/plugins/hermes-usage-manager/install.sh
hermes gateway restart
```

升级保留安装目录外的数据库、设置和密码；请先备份业务数据。自定义服务配置需管理员检查。

默认数据位置（自定义 Hermes Home 时随 Home 调整）：

- 数据库：`~/.hermes/plugin-data/hermes-usage-manager/usage.sqlite3`
- 设置：`~/.hermes/plugin-data/hermes-usage-manager/settings.json`
- 凭据：`~/.hermes/usage-manager-data/standalone-auth.json`

新机器使用独立数据库，旧机器的记录不会自动迁移。

## 数据范围

用量按 M Token 展示，数据库与导出保留整数精度。未知用量和费用不按零处理，费用为配置价格下的估算值。

日常排行统计已采集的逐次请求。“所有时间”下另有当前 Hermes Home 已保存的历史汇总排行，分开展示，不重复写入请求库。辅助调用 Hook 不可用时，相应逐次用量仍显示未采集。

登录独立入口后具有管理员权限，可只读查看当前 Hermes Home 的对话及脱敏工具参数和结果。其他 Profile/Home 不会自动开放或汇聚。

## 服务检查

```bash
systemctl --user status hermes-usage-manager.service --no-pager
journalctl --user -u hermes-usage-manager.service -n 50 --no-pager
```

## 分支

- `master`：正式运行版，包含预构建前端，不包含测试、Mock 或开发工具，不需要 Node.js。
- `codex/development`：开发源码、测试和构建工具。

安装不需要填写提交 SHA；如需固定版本或回退，可选用 `--ref` 指定已经发布的完整提交 SHA。

[分发说明](docs/install-distribution.md) · [配置说明](docs/configuration.md) · [兼容记录](docs/compatibility.md) · [更新记录](CHANGELOG.md)


### 补设价格与历史费用

保存或启用价格后，自动补算同一供应商、同一模型且处于价格生效日期内的历史缺失费用。请将生效开始日期设为需要覆盖的历史日期；也可在“待设置价格”中直接选择未覆盖区间。此前已配置过价格但费用仍缺失的模型，可编辑该价格后再次保存触发补算。

已有费用（包括已知零费用）保留原价格修订，不因调价重新计算。用量或缓存未知、暂不支持计价的请求继续显示未知。补算关联所用价格修订，并在管理审计中记录补算数量；费用仍为估算值。
