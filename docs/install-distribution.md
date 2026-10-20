# v0.21.0 源码仓库扫描与运行版分发

## 已知问题

用户的Hermes v0.21.0 (2026.8.31)安装源码仓库时，扫描器把`tests/test_m3_collection.py`中的假Bearer凭据、私钥脱敏样例，以及`tests/test_standalone.py`中的测试密码判为CRITICAL，安装被拒绝。测试不应改成隐藏字符串来迎合规则，也不关闭扫描或修改Hermes核心。

运行版使用现有发布器的文件库存，包含后端原文、五Hook、原生Dashboard构建、独立入口构建、install.sh、文档及运维工具。测试、Mock、frontend开发源码和构建脚本不属于服务机运行依赖，继续保留在开发仓库中，不分发到运行版。编译JS、监听端口、数据库写入、systemd调用仍然可被扫描及审查，不对它们改名或混淆。

## 构建与检查

在开发机先完成两种前端构建，再运行（输出目录必须是未存在的绝对路径，父目录必须存在）：

```powershell
.venv/Scripts/python.exe scripts/package_release.py --install-tree F:/projects/Hermes_Usage_Manager/build/install-runtime-candidate
```

该目录与同次zip库存逐字节一致，包含release.json记录源码revision、dirty状态及文件SHA256；不会创建Git分支、推送代码、安装插件或更改服务器。源代码不干净时仍是候选包，不冒充正式tag。输出已存在则失败，避免覆盖检出的仓库或既有候选文件。

发布前使用目标Hermes自身的`tools.plugin_guard.scan_plugin`扫描完整运行目录，保留报告。dangerous仍然阻止发布/安装；需要审查的发现不能靠--force绕过dangerous。当前官方plugin-guard-v11本地扫描报告为safe（无critical/high）；这是本次候选的验证记录，不等于用户v0.21.0扫描器已经验收。原始报告在build/runtime-scan-report.json，使用的官方扫描器文件SHA256记录在报告中。

## 发布与服务器安装

发布者可把上述运行目录作为独立安装分支/仓库的完整根目录发布；开发分支仍保留测试和源码。发布需要先获得用户授权，不能把未推送的本地目录当成可用远端地址。

用户回传v0.21.0的安装帮助确认`--ref`只接受不可变的40字符Git提交SHA，不是分支名称。运行版提交发布到Gitee后，用其真实提交SHA和用户的仓库URL构造安装命令：`hermes plugins install --ref 完整运行版提交SHA 仓库URL`。安装仍走Hermes的扫描/确认机制，通过后才执行安装目录的`install.sh`。不要直接重试未指定运行版提交的源码仓库安装命令，否则仍会扫描源码测试。

本次尚未发布运行版远端提交，不能给出假SHA或宣称服务器重装通过。原数据、认证和Gateway不因构建或导出而更改。
