# M4 阶段报告（按用户调整后的验收范围完成）

## 最终范围调整与交付结论

用户明确“不用新服务器验证了”，将新服务器安装验收从本次范围免除，而非暂缓或实测通过。现有测试机升级/代码回退/恢复新版、可恢复卸载重装已获验收；v0.5.1标签指向57cf045，隔离标签检出严格打包成功（source_dirty=false），输出build/tagged/v0.5.1，原候选包未覆盖。标签检出Python123、IIFE3、类型/Lint/无React构建及包verify/stage通过。标签包尚未单独在目标安装，新服务器仍无证据；不将同版本既有候选的实测冒充该zip已安装。按用户调整范围，M4交付完成，不代表生产批准、CLI remove或数据库原位回滚通过。

本次只记录范围变化，不移动标签、不重打包、不Git提交/推送、不部署。下方“进行中/待新服务器”段落为此前历史状态，以本节和m4-acceptance.md为准。

## 用户决定暂缓新服务器验收

用户明确“先跳过全新测试服务器安装验收”。记录为暂缓/未验证，不降低README第13节退出条件，不标记M4全部完成。现有测试机0.5.1继续运行，不再安排重复停机演练。当前补齐验收矩阵并修正文档历史状态；后续如生成带匹配tag的本地交付包，必须另获提交/tag授权，既有候选包与checksum应保留，不能原名改写已验证产物。未获生产部署授权，不push、不自动打tag。本轮只改文档，不重跑业务测试或重打包。

## 现有测试机可恢复卸载/重装：用户确认通过

用户按重新校验0.5.1包、暂存/doctor、安装到空路径、enable、读取原库汇总、启动Dashboard和恢复Gateway的指引后，确认“验证了没问题”。据此记录现有测试机的可恢复移出/重装及Live页面/旧数据检查获用户确认；此次未附具体doctor日志/数据库汇总/服务状态，不能新增精确计数、时间或具体输出断言。卸载采用disable+移动保留代码，不是CLI remove；原库未安排覆盖或删除，不代表数据库原位回滚已验收。

当前现有测试机升级→代码回退→恢复新版、可恢复移出→重装流程已获验收，当前版本按用户确认恢复为0.5.1。保留全部备份，无自动清理；当前已上传候选包未重打。M4整体仍未完成：全新无本项目开发环境的测试服务器安装尚无资源/证据，正式版本tag/严格发布门禁及生产安全/身份审查亦未完成。暂停继续停机演练，等待新服务器或下一步用户指令，不替用户创建tag、推送或部署生产。本轮仅文档补证，无新代码、本地测试或Git提交。

## 可恢复移出后的界面检查：用户确认通过

M4成果已按用户要求提交3d0ea39（未push/tag），提交前完整pytest123通过、工作区干净。用户执行可恢复卸载指引后表示验证无问题，记录为用户确认“用量管理入口消失、其他Dashboard页面正常”。未附命令日志或本轮备份目录，因此不新增具体快照路径/计数/doctor输出断言，也不将手工disable+移出目录称为CLI remove已验证。下一步重新停止Dashboard，确认Gateway仍停止，校验既有0.5.1发行包并在新目录暂存、doctor，然后只安装代码到空插件路径，继续使用原DB，重装UI仍待验。已上传候选包不重打，本轮无新代码或本地测试。

## 现有测试机升级、代码回退、恢复新版闭环通过

用户回传安全快照中的0.5.1代码及实际安装目录doctor均通过，0工具/5 Hook，重新启用成功；原DB为Live、0001–0005，计数请求3/工具1/会话2/Profile1/价格0/访问审计21。随后确认Live · M4、数据正常及Gateway恢复。访问审计从20到21符合界面检查新增访问，不误判数据不一致。当前运行0.5.1，已走通0.4.4→0.5.1→0.4.4→0.5.1的实机代码升级/回退/恢复闭环；整个过程原DB未被覆盖，快照恢复只写新目录。

本次现有测试机升级/回滚验证完成；不扩大为数据库原位回滚、真实卸载/重装或全新服务器通过。备份目录/home/ubuntu/hum-m4-051.t6rUvM和/home/ubuntu/hum-m4-rollback.CRcF8l保留，未删除/修改校验清单。M4仍待可恢复卸载/重装、全新无开发环境服务器验收及干净源码/正式tag发布；不将候选包称为正式生产发布。本轮仅补充用户实机证据，无新代码/本地测试/重打包或Git提交。

## 回退旧版Live页面验收通过

用户确认回退0.4.4后的页面检查全部正常：Live · M3，概览/用量明细/MCP/对话列表数据保留无接口错误，正文关闭503符合预期。结合此前安装doctor及原DB计数一致，现有测试机的实际代码回退演练通过。没有实际覆盖原DB；快照数据恢复只在新目录验证。下一步从已恢复校验的0.5.1安全快照副本恢复新版代码，保留原DB并再次验证Live · M4后恢复Gateway。新版恢复、卸载/重装、新服务器及正式发布门禁仍待完成。本轮仅更新证据，无新代码、测试或重打候选包。

## 实际代码回退0.4.4通过，旧版页面待验

用户回传新版安全快照及旧快照restore均成功（DELETE/format=1）；旧恢复副本和安装目录doctor均0.4.4、0工具/5 Hook，重新enable成功。原DB仍Live、0001–0005、计数3/1/2/1/0/20，未覆盖DB，新增审计保留。旧安装0.5.1代码保存在/home/ubuntu/hum-m4-rollback.CRcF8l/plugin-0.5.1。实际代码回退已通过，旧版Live页面及恢复0.5.1仍待验证；未将副本restore冒充原库实际回滚。用户已获说明此为M4恢复能力演练而非新版故障。下一步保持Gateway停止，启动旧版Dashboard检查后再停止并恢复新版；不产生模型/MCP调用费用。本轮仅补证，无新代码/本地测试/候选包重打。

## 实际回滚前停写与新版快照通过

用户再次停止Gateway，default/test-a/test-b均not running；带Dashboard无9119监听检查的脚本成功。当前0.5.1配对快照保存/home/ubuntu/hum-m4-rollback.CRcF8l/snapshot，DELETE/format=1，Live、0001–0005，计数请求3/工具1/会话2/Profile1/价格0/访问审计20。访问审计由18增至20，保留新增记录，不恢复旧18条DB。下一步从已验证旧快照恢复到新目录、doctor旧代码后，仅代码回退0.4.4并保留原DB；实际回退与旧版页面仍待回传。

## 0.5.1 实际Dashboard升级验收通过

用户确认升级后页面显示Live · M4，概览/用量明细/MCP/对话列表保留旧数据且无接口错误；正文临时授权关闭时详情返回503 SESSION_CONTENT_UNAVAILABLE，符合预期。Gateway于2026-10-16 15:51:28 CST重新active，随后Dashboard已启动，因此旧快照之后可能新增写入，不直接用旧DB覆盖。用户用0.0.0.0监听后可访问，保留认证；公网IP可访问不等于HTTPS/防火墙审查通过。下一步停止相关写入者，对当前0.5.1代码和原DB做新的回滚前快照，先保留当前数据再测试同schema代码回退。实际回滚、卸载/重装及全新服务器仍未验收。本轮只补证，不重打包、不新增本地测试。

## 0.5.1 实际安装升级及启用通过

用户回传实际安装路径/home/ubuntu/.hermes/plugins/hermes-usage-manager的原生doctor通过：manifest0.5.1、0工具/5 Hook；disable/代码替换/enable完成，plugins list显示enabled0.5.1。升级后原DB仍Live、五步迁移、计数3/1/2/1/0/18不变。旧代码保留在/home/ubuntu/hum-m4-051.t6rUvM/previous-plugin；未覆盖原DB。宿主提示未授予内置工具覆盖权限，不是启用失败，本插件不需要该权限，不建议增加allow-tool-override。下一步验证新版Dashboard及Live API；实际回滚/卸载/新服务器仍未完成。本轮仅记录实机回传，无新代码或本地测试，不重打已上传候选包。

## 0.5.1 实机快照恢复检查通过

用户回传0.5.1 zip/ops校验、verify/stage成功；/home/ubuntu/hum-m4-051.t6rUvM/staged/hermes-usage-manager原生doctor通过，0工具/5 Hook。新快照/home/ubuntu/hum-m4-051.t6rUvM/snapshot为DELETE模式、format=1，检查后restore成功；恢复副本旧0.4.4的doctor通过，0工具/5 Hook。原库、新快照、恢复副本均Live、0001–0005，计数一致：请求3、工具1、会话2、Profile1、价格0、访问审计18。确认0.5.0恢复拒绝问题的修复已在目标流程补证；不是实际安装升级或已将快照覆盖原库。下一步仅停机替换插件代码，原DB保持不动；新版Live、实际回滚及新服务器仍待验。

## 0.5.0 恢复检查失败，0.5.1 修复候选

用户在“验证快照可恢复，不覆盖原库”第一步收到ValueError，脚本在插件替换之前停止；未执行后续disable/mv/cp/enable。此前快照汇总一致不等于快照可恢复，以下历史通过记录不扩大为恢复通过。

本地复现snapshot→inspect快照→restore：0.5.0快照继承WAL模式，只读检查生成-wal/-shm，严格库存检查因新增文件拒绝恢复，主体hash未变化。旧错误输出不能排除输出目录已存在等其他原因。0.5.1仅将新备份目标封存为DELETE模式，源库仍WAL；新增库存/输出目录错误码及实际顺序回归。保留旧快照和0.5.0包，不删除sidecar或忽略校验。续验按m4-051-recovery.md，在新目录重做暂存、快照和恢复副本检查，不替换插件/原DB。

当前候选为0.5.1，目标0.5.1暂存Doctor、实际恢复、升级/回滚及新服务器退出条件仍待用户回传；本修复不声称M4完成。下文0.5.0测试与计划为历史记录，当前操作以修复续验指引为准。

修复后重新执行完整pytest123项、Playwright32项、IIFE3项，合计158项通过；类型检查与ESLint通过。新增回归覆盖重复检查封存快照不产生sidecar/改变库存、源库仍WAL且备份含已提交数据、旧WAL库存不匹配仍拒绝，以及现存输出目录明确报OUTPUT_EXISTS。保留Starlette/httpx弃用和Node颜色环境告警，不升级无关依赖。本地通过不替代Linux实机续验。

## 用户实机升级前一致性快照通过

用户运行带Gateway inactive与9119无监听前置检查的脚本后回传：原库与快照均Live、0001–0005五步迁移，llm_requests=3、tool_calls=1、sessions=2、profiles=1、model_prices=0、audit_access_logs=18；snapshot status=ok。实际快照/home/ubuntu/hum-m4-upgrade.0rwyvF/snapshot。两侧汇总一致，记录为真实插件代码与SQLite一致性快照完成；snapshot输出version=null仅因快照操作不返回发行版本，不是失败。

下一项先把快照验证恢复到新的restore-check目录并对恢复旧代码运行doctor，再仅替换停止状态的插件代码、验证0.5.0已安装doctor及原数据库汇总。不会将快照DB覆盖原库；收到输出前不标实际升级/回滚完成。Gateway仍保持停止，尚未验证0.5.0 Live API。本轮仅文档补证，未修改代码/包或运行新本地测试。

## 用户确认Gateway已停止

用户回传目标CLI帮助确认支持gateway stop/status/list，并执行停止。hermes-gateway.service为Ubuntu用户systemd服务，2026-10-16 15:17:59 CST进入inactive (dead)，主进程退出status=0/SUCCESS；default、test-a、test-b均not running。记录为相关Gateway已停止证据，不扩大为Dashboard/所有独立CLI均已停止。日志含WebSocket ConnectionClosedOK关闭信息，不据此认定停止失败或修改核心。后续先确认Dashboard停机并进行一致性快照，不立即重新启动Gateway。

## 用户实机暂存校验通过：0.5.0

用户回传zip与外置ops.py的SHA256校验均OK，verify/stage均status=ok/version=0.5.0；暂存路径/home/ubuntu/hum-m4-stage.mtpXSY/staged/hermes-usage-manager。该路径原生doctor --ci确认manifest0.5.0，发现/解析/导入/注册通过，0工具/5 Hook。仅临时暂存，未证明已替换现有0.4.4或新版Live API通过。

下一项：用户先停止本测试DB的所有相关写入进程，再用ops工具读取升级前汇总、备份旧代码及SQLite一致性快照，并对快照DB读取汇总对照；收到status=ok与实际快照路径前不移动现有插件，不做回滚/卸载操作。当前真实升级/回滚和新服务器仍待验收。本轮仅文档补证，无新本地测试或代码/候选包变更。

## 用户选择：先在现有测试机验收升级/回滚

用户明确表示暂时只有现有测试机，先完成升级/回滚验证。继续使用已授权测试机及原0.4.4数据，先校验/暂存0.5.0并运行原生doctor，通过后再停止全部写入者并做代码+SQLite一致性快照；不直接覆盖运行中的插件或DB。全新服务器无开发环境安装仍未验收，不因用户选择现有测试机而降低或标绿README的M4退出条件。未连接生产，本轮仅记录验收顺序，无新代码或测试。

## Milestone

M4真实插件集成与交付。按用户要求先提交M3为`61b7663579763e715220beaee0e3fb828c8ff91e`，提交信息`feat: complete M3 native hooks and session audit acceptance`，包含已确认原型；提交身份沿用本仓库Zhong Jiating / 2832132400@qq.com，未push、未创建分支或tag。M4实现留在工作区，当前0.5.0为候选，不将M3 0.4.4的实机通过记录当作0.5.0已通过。

## 已完成

- 严格发布入口校验原生manifest/版本/五Hook声明、构建输入输出指纹、React/ReactDOM排除、运行文件/迁移/许可库存；固定zip成员元数据，生成逐文件release.json、zip和无Node ops.py的SHA256。如实记录commit/dirty/tag状态，严格发布模式要求干净HEAD与v0.5.0 tag，不自动创建。
- 运维工具仅依赖Python标准库：校验包、只暂存到新目录、SQLite一致性快照、校验快照后只恢复到新目录、只读聚合inspect-db。拒绝穿越/重定向/symlink/重复/超限成员，不盲目解压或覆盖；校验解压使用同一份字节。SQLite backup覆盖已提交WAL，超时/quick_check，备份私密权限；无自动删除/服务控制/覆盖数据库。
- 写明新服务器无Node安装、旧测试机升级前停全部写入者、配对代码/DB回滚、可恢复卸载/重装、配置与安全复核。默认loopback、保留宿主认证及正文opt-in；明确管理员桥接不是生产多用户RBAC，不升级Hermes依赖、不修改核心。
- 包独立导入、默认业务认证拒绝，以及本地隔离文件/SQLite升级/回滚/卸载工作流可执行测试；不是在真实Hermes上运行这些运维链路。

## 新建/修改文件

- 新建：ops/manage.py、ops/__init__.py、scripts/package_release.py、scripts/package-release.sh、tests/test_m4_delivery.py、docs/deployment.md、configuration.md、security-review.md及本报告、.gitattributes的shell LF规则。
- 修改：frontend/scripts/build.mjs增加构建指纹；版本/health/M4徽标及对应契约测试；tests/test_m2_package.py切换严格发布包烟测；README、CHANGELOG、development.md、compatibility.md。scripts/package_m3.py保留为当前打包器兼容入口。
- 没有新DB迁移、没有新权限/业务功能或Hermes核心修改。正式构建仍复用宿主React，Mock仅在本地开发。

## 执行测试与结果

- 完整pytest **120项通过**（其中M4交付30项）、Playwright **32项通过**、IIFE **3项通过**，共155项。类型检查、ESLint、正式构建及无React/ReactDOM打包检查通过；Git diff空白检查通过。
- 已运行Python发布入口，zip重复构建SHA一致；校验输入/输出变动、危险路径/保留设备名/重复/超限/校验篡改、WAL提交数据备份、原数据保留、恢复拒绝覆盖/损坏快照、拒绝Hermes state.db/未知库、默认业务403及包外独立导入均通过。
- 外置工具在临时目录、PATH清空、Python隔离模式下实际运行snapshot/inspect-db/restore/inspect-db，未依赖Node或源码checkout。发布tag门禁正/负分支是受控Git输出夹具测试，没有创建真实v0.5.0 tag。隔离升级/回滚/可恢复卸载为本地文件/SQLite仿真，不是真实Hermes CLI运维链路。
- Git Bash执行`bash -n scripts/package-release.sh`通过；完整Bash包装器未一键运行，等效Python、前端和测试入口分别执行。当前Windows环境不证明Linux权限分支/NTFS ACL安全或真实新主机通过。
- 告警保留：Starlette/httpx弃用及Node颜色环境设置告警；未改无关依赖来消除日志。M3已知Hermes MCP协程告警未在核心打补丁。

## 尚未验证项

- 0.5.0在Hermes v0.21.0目标doctor/Live UI、全新服务器无开发环境安装，及真实升级/回滚/卸载/重装回传；已询问用户是否有新测试服务器。
- 目标多Profile写入者停止/监督方式、Unix文件权限及生产身份/网络审查。手工可恢复卸载仿真不等于目标CLI remove已通过。
- 干净M4源码commit与版本tag未授权/未建立；严格模式只做本地门禁测试，候选包source_dirty=true、source_tag=null。不发布生产。
- M3已知辅助Hook、未知身份/缓存/费用、实机重复投递/强退等限制保留。

## 风险/需要确认

- SHA256不是签名；包和checksum需可信传输。备份无应用级加密，需私密目录/磁盘和组织保留策略；Windows须核对NTFS ACL。
- 不能只停Dashboard就恢复DB；所有共享该DB的CLI/Gateway/Profile写入者必须停止。回滚旧DB会失去快照后的新数据，必须保留当前快照并由用户确认。
- 当前宿主认证桥接将已通过宿主认证者视为管理员，管理员受控Dashboard之外不得当成完整角色映射。缺私有函数会拒绝，不关闭认证绕过。
- 官方最新文档与目标v0.21.0存在差异，仍用实机doctor，不推荐目标不存在的validate；不改核心，不使用Desktop SDK。

## 下一步建议

只执行deployment.md第2节：可信上传zip/.sha256/-ops.py，校验、暂存、运行doctor并回传；不替换现有0.4.4、不启动正文/采集、不产生模型或MCP费用。暂存doctor通过后再分步进行备份和测试升级。M4退出条件未满足，维持进行中，生产部署需要独立确认。
