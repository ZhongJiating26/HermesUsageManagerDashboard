# 附件审计（2026-11-03）

附件副本保存在管理数据库同目录的 attachments/，独立 SQLite 索引记录会话、消息、收发方向、原文件名、大小、SHA-256 和快照时间；每条传输记录独立，不覆盖已有快照。目录 0700，索引和副本 0600。附件不随临时缓存清理，备份管理平台时需同时备份整个 attachments/。

独立服务启动后增量补扫历史消息，正常运行每两秒扫描新增消息。采集启用时 pre_llm_call 和 on_session_end 也触发扫描。支持 Hermes 文档、图片、音频、视频缓存标记及 assistant MEDIA 标记；只接受本 Profile 的 cache 内常规文件，拒绝越界路径和符号链接。无法补存的附件显示不可用状态，不提供原路径下载。未来其他传输协议需要增加明确的路径适配；本功能不是传输网关事务的一部分，文件在首次捕获前已删除时无法恢复。

下载需要登录及 audit_detail 权限，并再次核验筛选范围、会话和 Profile 归属。响应使用 attachment、application/octet-stream、nosniff、private/no-store。下载行为记录在现有访问审计中。

详情默认读取最新100条，向上读取更早记录，每次查看最多5000条。列表和详情均显示管理平台会话键。

## 验证

所有开发测试均在124.222.243.117执行。前端 TypeScript 检查、Dashboard 与独立入口构建通过。37项相关测试通过，覆盖快照不覆盖、源文件删除后读取、符号链接/越界拒绝、未登录拒绝、跨会话拒绝及205条消息倒序分页完整性。3个同组IP参数测试未计入该37项；首次全组执行为37通过1失败，失败发生在旧Starlette TestClient解析IPv6主机字符串，与业务请求处理无关。

Chromium页面测试通过：详情初始 scrollTop=10058、scrollHeight=10712、clientHeight=654；列表/详情ID一致。测试夹具源文件删除后，浏览器下载快照成功。

更新前代码备份：测试 /home/ubuntu/hum-before-attachments-20261103.d8iHEf/plugin；正式 /home/ubuntu/hum-before-attachments-20261103.oKOKwL/plugin。更新后两台管理平台和Gateway服务active，首页200，未认证审计请求401。

正式指定会话原始ID 20261102_180117_5ab02ba5 的ZIP（8223290字节）和EXE（734240字节）已补建快照并复核SHA-256。正式环境只进行了更新及更新后的只读服务/快照检查，未导入测试数据。


## 消息内附件卡片修正

附件按 files.message 与消息 id 关联，只有加载对应消息后才渲染到该消息中。有匹配快照记录的文档系统说明、MEDIA路径及重复Attachment标记转换为文件卡片；用户正文保持原样。卡片提供图标、可换行文件名、大小、方向、快照状态和下载按钮。

测试机指定会话 54ceb492b4d6c28113ef6c11652ee9d99d506f112bad6547a521892678b5c249 已验证消息位置、无原路径/英文系统说明、浏览器下载成功以及390px布局无卡片溢出。10项附件及审计测试、类型检查、两种生产构建通过。

更新前备份：测试 /home/ubuntu/hum-before-inline-attachments-20261103.EwNzQd/plugin；正式 /home/ubuntu/hum-before-inline-attachments-20261103.QQWSqP/plugin。两台管理服务active、首页200。
