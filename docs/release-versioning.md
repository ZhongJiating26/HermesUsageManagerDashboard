# 版本与部署阶段

当前基础版本0.7.1。backend/version.py定义VERSION，plugin.yaml、pyproject.toml、dashboard/manifest.json、frontend/package.json、release.json同步维护。版本变化必须同时更新这些元数据并执行tests/test_version.py。

运行阶段由USAGE_MANAGER_RELEASE_CHANNEL决定，仅支持alpha/beta；默认为beta，非法值阻止服务启动。124由测试服务drop-in配置alpha；43由用户安装，默认beta。基础版本与发布阶段是独立字段，展示为0.7.0 Alpha或0.7.0 Beta，同一版本不需要两份代码。登录前的/api/version只返回版本与阶段，不返回服务器路径或凭据；响应禁止缓存。

维护者手动更新43前，先自行推送master至实际安装源Gitee，然后用ubuntu登录43。备份现有插件、停止hermes-usage-manager服务，再按README升级命令执行hermes plugins install --force --enable、运行install.sh（--port 8500保持现有端口），最后hermes gateway restart。确认管理服务active并检查http://127.0.0.1:8500/api/version返回0.7.0/beta。不删除plugin-data，保留密码、数据库及附件快照。安装初始化失败时停止后续操作，使用备份排查，不盲目继续重启。

2026-11-03验证均在124进行：15项版本、附件与审计测试通过；TypeScript与两种生产构建通过；浏览器验证Alpha和Beta登录页及登录后标题。没有访问43或推送远程仓库。
