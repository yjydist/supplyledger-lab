# SupplyLedger Lab Agent 契约

本文件约束本仓库中的 Agent 工作。`SPEC.md` 是需求、接口、信任边界和验收的基线；本文件只提炼执行时容易遗漏的约束。遇到冲突先核对规格章节和实际运行证据，不得静默改变 MUST。偏离 SHOULD 要提交 ADR，规格与固定版本不符时先做最小复现，再更新 ADR、测试和规格。

## 推进与验收

- 按 `SPEC.md` §19 的 M0–M9 顺序交付，每阶段提交代码、自动化测试和脱敏证据后再进入下一阶段。优先完成 M0–M3，不同时启动所有功能。
- 第一次 CA 注册与签发、通道创建和链码生命周期必须逐条运行原生命令，保留脱敏记录，然后才封装自己的脚本。不要用一键启动掩盖这些首次操作。
- 每项实现关联规格章节、需求编号或 §20 测试编号。以可观察行为和真实 Fabric 阶段判定结果；测试只有 PASS、FAIL、NOT RUN，未执行不得声称通过。Mock 不能证明真实背书、MSP、PDC、MVCC、TLS 或通道治理。
- 每份阶段证据记录测试编号、源码 commit、版本锁摘要、Compose 档位、genesisHash、准备数据、命令、预期与实际结果、判定，以及实际存在的 txId、区块高度和验证码。未上链失败记录失败阶段，不编造交易编号。

## 版本与组网

- 不依赖、不复制、不执行 `fabric-samples`、`test-network` 或 `network.sh`。网络配置、Dockerfile、Compose、CA/通道配置和运维脚本由本仓库编写。固定版本与依赖遵守 `SPEC.md` §2；镜像 digest、宿主平台、CLI 版本和校验值必须实测后写入 `versions.lock.yaml`，不能猜测，不使用 `latest` 或浮动分支。
- 链码、业务客户端、API 和投影器使用 Go；保持 `chaincode` 与 `app` 两个模块的依赖锁。链码采用自建 CCaaS 和 external builder，Peer 不挂载 Docker socket。
- 正式网络使用 Fabric CA、三节点 Raft、channel participation API、`supplychannel` 和 `supplycc`。组织、MSP、网络、TLS、ACL、策略及端口按 `SPEC.md` §§3–5、10 实现；不能用重建网络代替链码升级、审计组织接入或恢复。
- `stop` 和 `down` 默认保留数据。销毁只通过独立 `reset` 流程：要求 `CONFIRM_DESTROY=supplyledger`，先列出精确目标卷，默认不删除备份；禁止泛化清理命令。

## 身份、安全与隐私

- 业务身份以受信 ECert 的 MSP、`supply.userId` 和 `supply.role` 为准；HTTP token 只能映射本组织实际用户签名身份。不得从 JSON、Header、路径或钱包参数接受自称的组织、角色、actor、owner。Admin 和无业务属性 client 不自动获得业务写权限。
- CA registrar、组织 admin、节点身份、业务用户和 TLS 身份分别签发和保管。公共通道 MSP 不含私钥；组织 API 不挂载其他组织、registrar 或 admin 私钥。TLS 验证、SAN 与管理端 mTLS 不得通过跳过验证来修复。
- 私有条款只经 `transient.trade_terms` 进入 Seller/Buyer 合格背书路径和 `sellerBuyerTerms` 集合。金额、salt、合同内容不得出现在普通参数、公共状态、公共事件、错误、日志或投影中。公开哈希不等于私有明文；隐私结论必须说明宿主机管理员的信任边界。
- 真实密钥、口令、token、CA 数据、数据库、构建 release 秘密产物、运行态和备份不进入 Git。提交前检查仓库、构建上下文及脱敏证据。

## 链码与应用一致性

- `SPEC.md` §1.2 的 `CON-01–08` 与 §§6–12 的 `INV-01–15`、状态机、写/查函数和错误码是实现契约。每个写函数在链码内验证身份、严格 JSON、业务阶段、期望 revision 和幂等键；不提供通用状态写入接口。owner 与 custodian 分开，只有有效提交的 `AcceptBatch` 转移所有权。
- 业务批准、Peer 背书与通道治理是三层不同权限。按完整写集计算默认策略和 SBE；Audit 业务用户可查询公共记录但不可写业务或读取价格，Audit admin 可做本组织生命周期操作但仍不可写业务。
- 链码状态和事件必须确定性：不以本机时间、随机数、网络请求或不稳定遍历决定写入；先读取并完成校验，在内存构造目标状态，再写业务对象、索引、回执与单个聚合事件。规范编码和摘要需由客户端与链码共享 golden tests。
- 幂等键是 `(channel, creatorMSP, supply.userId, requestId)`。同语义重放返回原回执；不同语义复用 requestId 报错。回执与业务变更同交易写入。超时后保留全部 attempt txId，按提交状态和回执收敛；`SUBMITTED`、`PENDING_UNKNOWN` 与 `COMMITTED_VALID` 不得混同。
- PostgreSQL 只存组织隔离的请求日志和公共投影，不是业务事实来源。投影仅处理有效区块事件；事件、领域更新和 checkpoint 在同一数据库事务提交，并能从保留历史的 Peer 重放。禁止通过直接改 SQL 或 CouchDB fixture 制造业务状态。

## 变更完成条件

- 修改前阅读相关代码、调用方、测试和规格；只实现当前里程碑需要的完整行为。变更后审阅差异，运行与风险相称的检查，记录实际结果和限制。
- 保留升级前后 genesisHash 和历史数据。链码更新必须记录实际 sequence、packageId、镜像 digest 与 schemaVersion；M8 在原网络上升级并接入 Audit。备份恢复按 `SPEC.md` §16 的成套冷备份流程验证。
- 需要的 ADR 见 `SPEC.md` §18.4 的 ADR-001–010；资源和性能目标要附实测条件，未达目标如实标记，不把单机容器故障演练描述为生产级高可用。
