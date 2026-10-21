# 正式安装版分发

## 分支用途

`main` 是正式安装分支，保留后端、迁移、预构建前端、安装脚本、文档和运维工具。测试、Mock、前端开发源码及构建工具保留在 `master`，不包含在安装版中。

初始正式版 0.6.0 的运行代码来自源码提交 `298e25f205ea838a87655e3682734445d8e8a757`，与已部署验证的运行版 `5bc931e9a57a91b35285383c668af3b22a65ae17` 一致。本次只调整安装说明与分发元数据。

此前 Hermes v0.21.0 扫描完整源码仓库时，将安全测试中的凭据样例判为危险而拒绝安装。正式安装分支不分发测试；安装仍使用 Hermes 的扫描与确认机制，不关闭或绕过扫描。

## 发布到远端

维护者推送 `main` 后，须在 Gitee/GitHub 仓库设置中将默认分支设为 `main`。切换前，仅仓库 URL 仍可能安装旧源码分支；本地创建分支不会自动改变远端设置。

之后用户直接执行：

```bash
hermes plugins install --enable https://gitee.com/ZhongJiating26/HermesUsageManagerDashboard.git
bash ~/.hermes/plugins/hermes-usage-manager/install.sh
hermes gateway restart
```

无需填写 SHA。固定版本或回退时，可选用 `--ref` 指定已推送的完整 40 字符提交 SHA；当前目标安装器不接受分支名作为 `--ref`。

## 后续发布

在 `master` 完成开发验证和两种前端构建，再通过 `scripts/package_release.py --install-tree` 导出运行文件，核对差异后更新至 `main`。不要整体合并开发分支，以免重新带入测试。

`release.json` 记录原始源码提交及逐文件 SHA256，修改正式分支文件后需同步更新。`source_tag` 为空表示源码未打版本标签。正式版为 `release_status: released`，不冒充带标签的源码构建。

新版仍需在目标 Hermes 环境安装验收；某次扫描通过不保证所有环境和版本均通过。
