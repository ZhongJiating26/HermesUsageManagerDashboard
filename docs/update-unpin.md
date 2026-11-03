# 原三条命令更新：旧锁定修复

修复版本0.7.1。新版install.sh在初始化成功后自动运行ops/unpin_install.py，仅将hermes-usage-manager安装记录中的pinned置为false，保留revision及其他插件记录。修改前创建0600权限备份，重复运行不重复修改；拒绝符号链接、陌生源及不安全元数据。

已有旧锁定发生在下载阶段，所以即便远程代码更新，新的install.sh也不会被下载。首次必须由维护者将新版ops/unpin_install.py单独复制到服务器，用Hermes实际Python执行一次（例如 ~/.hermes/hermes-agent/venv/bin/python ~/hum-unpin-install.py）。该步骤不安装插件、不启停服务、不修改数据库。若当前安装未锁定则无需执行。

随后以及以后每次升级，只使用原三条命令：

```bash
hermes plugins install --force --enable https://gitee.com/ZhongJiating26/HermesUsageManagerDashboard.git
bash ~/.hermes/plugins/hermes-usage-manager/install.sh
hermes gateway restart
```

新版初始化提示端口，回车保留现有端口；首次默认为9120。任何一步失败时停止后续步骤。不要删除数据库或schema_migrations来处理版本问题。

仅在124隔离环境验证：18项相关测试通过、bash语法和TypeScript检查通过、两种前端生产构建通过。创建独立HERMES_HOME并植入7595601旧锁定，运行修复工具后，原样plugins install --force --enable命令成功安装远端默认分支544fff6，安装元数据保持pinned=false。没有修改124当前运行安装记录，没有操作43，没有推送。
