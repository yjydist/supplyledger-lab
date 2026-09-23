# SupplyLedger Lab 项目规格说明书

**项目：从零搭建的多组织供应链协作与追溯系统**   
**文档版本：1.0 · 规格基线日期：2026-09-23**   
**目标开发者：JINGYUAN**   
**运行环境：单机 Docker / Docker Compose；链码及应用主语言：Go** 

> 本文定义要实现的系统、接口契约、信任边界与验收方法，不是已经实现或实测通过的交付报告。所有性能数字均为本项目拟定的验收目标或资源预算，不是对你的电脑的实测结果。版本依据已核对的官方发布记录；机器架构、镜像 digest、Docker 实际版本在 M0 阶段实测锁定。

---

## 0. 阅读方式与规格效力

**MUST / 必须** 表示毕业验收的硬性要求； **SHOULD / 应当** 表示偏离时必须写 ADR（架构决策记录）； **MAY / 可选** 表示不影响主线验收。文中的需求编号用于追踪实现、测试与证据。本文的业务规则是专为学习设计的项目决策，不应当误认为 Fabric 默认规则。

本项目将“掌握 Fabric”落实为：独立设计网络与身份体系，编写 Go 链码和应用，完成组网、升级、加组织、证书维护、并发处理、隐私验证与故障恢复；能够解释一笔交易在各阶段的行为。BFT、HSM、Kubernetes、多机生产安全和修改 Fabric 内核不在 1.0 的必做范围，不因完成本项目就声称已穷尽这些领域。

**建议阅读顺序：**  第 1–5 章确定边界与组网；第 6–12 章实现业务与链码；第 13–17 章完成应用和运维；第 18–21 章逐项验收。先推进 M0–M3，不要同时启动全部功能开发。

### 目录

1. 项目目标、硬约束与非目标
2. 技术版本、环境与资源预算
3. 组织、节点、网络与 Compose 拓扑
4. 身份、证书、MSP 与访问控制
5. 从零组网的工作包与配置契约
6. 业务范围、角色与核心不变量
7. 状态机与业务流程
8. 数据模型、键空间与数据分类
9. Go 链码接口契约
10. 背书、状态级背书与网络治理
11. 私有数据、哈希与隐私验收
12. 确定性、并发与业务幂等
13. Go 客户端、组织 API 与交易状态
14. 事件、链外投影与附件
15. 链码升级、新组织接入与配置变更
16. 可观测性、备份与故障演练
17. 性能验证与安全要求
18. 仓库结构与工程规范
19. 里程碑与交付清单
20. 验收测试矩阵
21. 最终完成定义与能力答辩
22. 可选进阶实验
23. 官方依据与版本核对记录

---

## 1. 项目目标、硬约束与非目标

### 1.1 要交付的系统

供应商创建工业零部件批次，与采购商协商并确认交易；物流方接货、运输和报告交付；采购商确认实物接收并验收。系统同时支持拒收退回、交易取消、业务冻结、召回标记，以及后加入的只读审计组织。

真正的交付物包括三个部分： **可重建的联盟链网络、具有明确一致性与隐私约束的业务应用、能够复现的测试和运维证据** 。一个漂亮的页面或成功调用链码的截图都不能替代后两者。

### 1.2 硬约束

| 编号   | 必须满足的约束                                               | 证据                       |
| ------ | ------------------------------------------------------------ | -------------------------- |
| CON-01 | 不依赖、不复制、不执行 fabric-samples；不使用 test-network、network.sh、其 Compose 或链码 | 仓库依赖和脚本审查         |
| CON-02 | 网络配置、Dockerfile、Compose、CA 配置、通道配置和运维脚本自行编写 | 每个关键配置项有说明       |
| CON-03 | 首次完成 CA、通道创建、链码生命周期时逐条执行原生命令，然后才封装自己的脚本 | 脱敏命令记录和产物         |
| CON-04 | 链码使用 Go；业务客户端、事件投影器和 API 同样使用 Go        | go.mod、源码、构建记录     |
| CON-05 | 全部必做功能在本地 Docker Compose 运行，无云主机、付费 SaaS 或 Kubernetes 依赖 | 断开外部业务服务仍能运行   |
| CON-06 | 正式验收网络使用 Fabric CA，不使用 cryptogen 代替身份生命周期 | CA 数据、签发记录、MSP     |
| CON-07 | 不通过重建网络代替升级、接入新组织或恢复                     | 变更前后 genesis hash 相同 |
| CON-08 | 不将 Docker socket 挂载给 Peer；使用自建 CCaaS 外部服务运行链码 | Compose 和容器挂载审查     |

允许使用官方 Fabric / Fabric CA 二进制、镜像、Go SDK、链码库和官方文档。允许查阅固定版本 Fabric 自身的 `sampleconfig` 来理解配置字段，但不能整份复制后仅修改组织名；它不是本项目的运行模板。这里的“从零”是从空项目构建网络与应用，不是重新实现密码学、Raft 或 Fabric 本身。[R01][R07][R08][R09]

### 1.3 非目标

1.0 不实现真实付款、税务、ERP、订单拆分、部分收货、批次拆分合并、国际物流、自动获取 IoT 数据、手机钱包或公链跨链。不建设复杂前端，不把区块浏览器当作必要基础设施。每批次只完成一次出售或一次拒收退回；完成后的二次转售和售后所有权反向转移属于进阶扩展。

链上数据只能证明特定身份曾提交、确认了某些记录，不能单独证明实物质量、线下交付或检测结论真实。对系统中的角色、数量、条款与实物事实负责的主体必须在业务文档中明确。

---

## 2. 技术版本、环境与资源预算

### 2.1 版本基线

| 组件                      | 本规格采用的版本 / 选择                                      | 锁定方式与说明                                               |
| ------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Fabric Peer、Orderer、CLI | 3.1.5                                                        | 全网同版本；镜像 tag 加 digest；发布二进制校验 SHA-256       |
| Fabric CA server / client | 1.5.22                                                       | 两者同版本；独立于 Fabric 的版本号                           |
| Go 构建工具链             | 1.26.8                                                       | 固定构建镜像 digest，`GOTOOLCHAIN=local`，不得静默下载另一个工具链 |
| Go Contract API           | `fabric-contract-api-go/v2 v2.2.3`                           | `go.mod`、`go.sum`                                           |
| Go chaincode shim         | `fabric-chaincode-go/v2 v2.3.1-0.20260831054443-83a556592560` | 与上面 Contract API 的已声明依赖保持一致                     |
| Go protobuf bindings      | `fabric-protos-go-apiv2 v0.3.7`                              | 不混用旧 protobuf import 家族                                |
| Go Gateway                | `fabric-gateway v1.12.1`                                     | `go.mod`、`go.sum`                                           |
| 世界状态数据库            | Apache CouchDB 3.4.2                                         | 每个 Peer 独立一套；该版本列于 Fabric 3.1.5 测试依赖         |
| 业务投影 / 请求日志数据库 | PostgreSQL 17.10                                             | 本地容器，各组织独立数据库及账号                             |
| 共识                      | etcdraft / Raft，3 个 Orderer                                | 不使用 Solo、Kafka 或 system channel                         |
| 容器编排                  | Docker Engine / Docker Desktop + Compose CLI                 | M0 记录实际完整版本，验证本文需要的特性，不凭空指定宿主机版本 |
| 链码运行                  | 自建 Go CCaaS + 自建 external builder                        | 不使用 Peer 内置 Docker 启动链码路径                         |

Fabric 3.1.5 发布记录列出 Go 1.26.4、CouchDB 3.4.2 为它的测试依赖；这不表示应用或外部链码必须使用完全相同的 Go 补丁版本。本规格选择 Go 1.26.8，是因为固定的 Contract API 2.2.3 声明至少 Go 1.26.7，并且 1.26.8 已在官方发布列表中。上表组合仍须通过 M0/M3 的本机编译与联网冒烟测试，不能把多个独立发布记录等同于一张完整的官方兼容认证。[R01][R02][R03][R04][R05][R06]

`versions.lock.yaml` 必须记录：各镜像完整引用、实际平台、manifest / 平台 digest、CLI 版本、二进制校验值、源码 commit、Go 工具链、模块清单。digest 必须实际拉取并检查后填写，不能在规格中捏造。版本更新应提交独立变更并重跑回归，不使用 `latest`、浮动 Git 分支或无说明的 `go get -u`。

### 2.2 宿主机假设

只要求可运行 Linux 容器，不预设你使用 Windows、macOS 或 Linux。Windows 使用 Linux 容器环境；所有平台差异尽量收敛到自建 `tools` 容器。脚本使用 LF 换行。文件执行权限、容器 UID/GID、时区和文件挂载行为在 M0 检查。

优先使用宿主机原生架构；ARM64 机器不得默认强制全部镜像使用 AMD64。若必须仿真，记录原因，并将性能结果单独标注，不与原生架构混报。

### 2.3 资源档位

| 档位       | 运行内容                                                     | 规划预算，不是保证                                           |
| ---------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| bootstrap  | CA 与工具容器，分组织逐步初始化                              | 可在较低资源配置上开始                                       |
| dev        | 3 Peer + 3 CouchDB + 3 CCaaS + 3 Orderer；API / DB 后期开启  | 建议宿主机 16 GB RAM，向容器环境分配约 8–12 GB，预留 50 GB 磁盘 |
| resilience | dev 加每业务组织第二套 Peer / CouchDB / CCaaS，审计节点按实验开启 | 建议宿主机 32 GB RAM，容器预算约 16–20 GB                    |

CA 在签发、续期和吊销任务结束后可以停止运行，以节省内存，但必须保留它的数据库和密钥。证书生命周期实验时再启动。上述资源是初始预算，实际以 `docker stats`、宿主机压力与实验记录为准。所有容器在一台电脑上，不能据此声称抵御宿主机故障或具备生产级高可用。

---

## 3. 组织、节点、网络与 Compose 拓扑

### 3.1 组织定义

| 组织               | MSP ID     | 业务角色                                           | 初始节点                     |
| ------------------ | ---------- | -------------------------------------------------- | ---------------------------- |
| 供应商             | SellerMSP  | 创建批次、提出交易、发货授权、质量召回             | peer0 + couchdb0 + cc0       |
| 采购商             | BuyerMSP   | 确认交易、收货、验收、拒收                         | peer0 + couchdb0 + cc0       |
| 物流商             | CarrierMSP | 接货、运输记录、报告交付、退回运输                 | peer0 + couchdb0 + cc0       |
| 排序服务组织       | OrdererMSP | 管理 3 个排序节点，不处理业务或持有业务私有明文    | orderer0、orderer1、orderer2 |
| 审计观察方，后加入 | AuditMSP   | 读取公共业务历史与投影；不自动取得价格或业务写权限 | peer0 + couchdb0 + cc0       |

初始四个组织各有独立 Enrollment CA 和 TLS CA，另设一个只签发 Orderer 管理客户端凭证的专用 TLS CA，共 9 个 CA 服务；审计组织加入时再增加 2 个。CA 按初始化任务启停，不要求持续并行运行；每个 CA 使用独立数据卷。初始每个 Peer 都配置一个 CCaaS 服务和一个 CouchDB；resilience 档位增加第二套独立实例，不让两个 Peer 共用同一个 CouchDB 或同一个链码进程来伪装全链路冗余。

### 3.2 通道与链码

业务通道固定为 `supplychannel`，链码固定为 `supplycc`，合约命名空间固定为 `SupplyContract`。通道创建时就包含 SellerMSP、BuyerMSP、CarrierMSP 和排序组织；AuditMSP 必须在保留原账本的情况下加入。

1.0 只保留一个主业务通道。需要对比多通道隔离时，在独立实验中建立第二通道，不能把它变成主流程的前置复杂度。

### 3.3 网络命名

Docker 网络：`supply-fabric` 为 Peer / Orderer 互联网络；`supply-seller`、`supply-buyer`、`supply-carrier` 为组织内部网络；后期增加 `supply-audit`。组织内部网络使用 `internal: true`，放置 CouchDB、CCaaS、CA、组织 API 和组织投影服务。

每个 Peer 同时加入公共 Fabric 网络和自己的内部网络。CouchDB、CCaaS 不加入其他组织网络。工具服务按角色接入必要网络，不创建一个长期挂载所有组织私钥的“万能 CLI”。一台宿主机的 Docker 管理员仍能越过这些隔离，必须在威胁模型中承认。

示例内部 DNS：`peer0.seller.supply.test`、`cc0.seller.supply.test`、`couchdb0.seller.supply.test`、`orderer0.orderer.supply.test`。证书 SAN 必须覆盖实际使用的 DNS 名。内部服务发现地址不得填写宿主机映射端口或 `localhost`。

### 3.4 端口契约

| 服务                          | 容器内部端口         | 宿主机映射策略                                               |
| ----------------------------- | -------------------- | ------------------------------------------------------------ |
| Peer gRPC / Gateway           | 7051                 | 默认不映射；调试 override 才映射至 127.0.0.1                 |
| Orderer gRPC                  | 7050                 | 默认不映射                                                   |
| Orderer admin / participation | 9443                 | 默认不映射；由 orderer 工具容器访问                          |
| CCaaS gRPC                    | 9999                 | 不映射；仅组织内部网络可达，Peer 使用 mTLS 凭证调用          |
| CouchDB                       | 5984                 | 不映射；数据库调试仅使用临时工具容器                         |
| CA HTTPS                      | 7054                 | 不映射；各 CA 容器端口可相同                                 |
| PostgreSQL                    | 5432                 | 不映射                                                       |
| 各组织 API HTTPS              | 8080                 | seller / buyer / carrier 分别映射到 127.0.0.1:8081 / 8082 / 8083；audit 为 8084 |
| 运维指标                      | 配置中明确的独立端口 | 仅内部监控网络或工具容器访问                                 |

### 3.5 Compose 契约

无 profile 的基础服务包含 3 Orderer 和三组织第一套 Peer / DB / CCaaS；`ca` profile 启动 CA；`app` 启动 API、投影器和 PostgreSQL；`resilience` 添加第二套 Peer / DB / CCaaS；`audit` 添加审计节点；`observability` 可添加指标采集。

CA 初始化、MSP 生成和通道加入 **不是** 靠 `depends_on` 自动完成。`depends_on: condition: service_healthy` 只能用于已明确定义的启动健康依赖，不能将进程启动等同于通道已加入、链码已提交。必须另做网络级 readiness 检查。[R29][R30]

服务必须使用独立 named volume；不得将同一份 `/var/hyperledger/production` 同时挂载给多个节点。`stop`、`down` 默认保留数据；销毁数据单独使用 `reset`，要求显式参数 `CONFIRM_DESTROY=supplyledger`，并打印将删除的精确卷列表，禁止泛化的 `docker system prune --volumes`。

---

## 4. 身份、证书、MSP 与访问控制

### 4.1 每组织身份清单

**CA registrar** 负责注册身份； **组织管理员** 负责本组织的链码批准和配置签名； **Peer / Orderer 节点身份** 用于节点 MSP； **业务用户身份** 用于交易签名； **TLS 身份** 用于通信。它们必须分别签发、分别存储，不能使用同一张 admin 证书承担全部职责。

业务用户证书必须含受信属性：`supply.userId` 为组织内稳定且唯一的用户标识，`supply.role` 为 `operator`、`quality` 或 `auditor`，并明确申请写入 ECert。链码使用客户端身份 API 提取 MSP、用户标识和角色，不信任 JSON、HTTP Header 或文件名中的身份声明。[R11][R12][R13]

每个业务组织至少签发 operator、quality（Carrier 可不签发）、无业务属性的普通 client、组织 admin 各一个。另准备一个非本通道组织的身份用于越权测试。AuditMSP 只有 auditor 业务角色；其 admin 仅用于节点和本组织生命周期操作。

### 4.2 MSP 文件边界

节点 / 用户的本地 MSP 包含自己的 `signcerts`、`keystore`、根证书及 `config.yaml`；通道组织 MSP 定义仅包含公有信任材料、NodeOUs 与 CRL，不得包含私钥。NodeOUs 必须区分 client、peer、admin、orderer。

所有公有根证书可以分发；组织 CA 私钥、节点私钥和用户签名私钥必须限制挂载。组织 API 只挂载本组织普通业务用户的签名材料，不挂载组织管理员或其他组织用户私钥。

### 4.3 CA 建立顺序

每个组织先初始化 TLS CA，再为 Enrollment CA 服务签发 HTTPS 证书，然后启动 Enrollment CA、注册并签发组织 admin、节点和业务用户。CA 数据库使用持久化 SQLite 即可，不为学习 CA 额外部署数据库集群。首次引导信任通过读取并核验本地 CA 根证书指纹完成，不使用 `curl -k` 或跳过 TLS 验证作为常态。[R11]

必须记录 issuer、subject、serial、AKI、SKI、SAN、用途、过期时间和文件归属。Enroll 重新生成证书和密钥不等于“原文件随意覆盖”；运维必须记录证书替换及其依赖。

### 4.4 TLS 矩阵

| 通信路径                 | 1.0 要求                                         |
| ------------------------ | ------------------------------------------------ |
| CA client → CA           | 服务端 TLS，正确根信任和主机名验证               |
| App / CLI → Peer Gateway | 服务端 TLS；业务请求另用 ECert 签名              |
| Peer / 客户端 → Orderer  | TLS；使用正确通道身份执行相关请求                |
| Raft 节点间              | 按排序集群配置使用双向 TLS，consenter 证书一致   |
| Orderer admin API        | 强制 mTLS，管理客户端独立证书                    |
| Peer → CCaaS             | 强制 mTLS；每 Peer 独立客户端 TLS 凭证           |
| Local API → 用户 CLI     | HTTPS + 本地测试 token，token 和证书均不写入源码 |

Orderer admin API 的客户端信任根必须仅包含专用管理客户端 TLS CA 的根；该 CA 不给业务客户端或普通节点签发凭证，单独保管 registrar 和签发数据。管理端点的服务端 TLS 证书仍由 Orderer 组织 TLS CA 签发。不能直接信任能给全部普通客户端发证的广泛客户端根，使它们都成为节点管理调用者。通道治理签名与该 mTLS 管理访问是两个不同权限层。[R09][R14]

### 4.5 审计只读与 ACL 陷阱

`AuditMSP` 的业务用户不能提交业务更新，但必须能够向 Peer 提交查询提案。不能一面把它从所有提案权限中排除，一面又要求其调用链码查询。

本项目将 `peer/Propose` ACL 映射到 `/Channel/Application/Readers`，由链码逐函数实施业务写授权；通道 `Writers` 不包含 AuditMSP 普通 client，但包含 AuditMSP admin，以便其完成本组织链码生命周期操作。Audit admin 不具备业务角色，仍被链码业务写接口拒绝。加入后的 ACL 和角色必须同时做正向与反向测试。[R07]

---

## 5. 从零组网的工作包与配置契约

### 5.1 工具镜像

自行构建 `supply-tools`，包含固定版本的 `peer`、`orderer`（可仅用于版本检查）、`configtxgen`、`configtxlator`、`osnadmin`、`fabric-ca-client`、`bash`、`jq`、`openssl`、`curl`、`tar`、`gzip` 和项目自编 CLI。二进制从对应官方发布包取得并校验。不得依赖 `fabric-tools` 镜像或下载即执行的官方 bootstrap 脚本。

自建 Peer 镜像基于固定 Fabric Peer 镜像，只加入自己的 external builder 及所需运行依赖。必须显式确认 builder 使用的 shell / JSON 解析器在镜像中实际存在，不假设官方 Peer 镜像预装了 bash、jq 或 Go。[R08]

### 5.2 配置产物

| 文件 / 产物             | 必须解释的关键内容                                           |
| ----------------------- | ------------------------------------------------------------ |
| 每组织 CA YAML          | CA 名称、根签发配置、TLS、注册权限、数据持久化、签发属性     |
| 每节点 core.yaml        | localMSPID、MSP 路径、TLS、对外地址、gossip、Gateway、CouchDB、externalBuilders、账本路径、指标 |
| 每 Orderer orderer.yaml | local MSP、TLS、admin mTLS、participation API、文件账本、Raft WAL / snapshot、指标 |
| configtx.yaml           | 组织公有 MSP、Policies、ACLs、Capabilities、AnchorPeers、Raft consenters、批次参数 |
| supplychannel.block     | 应用通道初始配置区块；不是 system-channel genesis            |
| 解码后的配置 JSON       | 对照检查 MSP、策略、TLS 证书、consenter 与 capability        |
| deployments/*.json      | 镜像 digest、包 ID、定义 sequence、版本和各组织批准情况      |

### 5.3 Fabric 3.1.5 配置基线

使用 channel participation API 管理应用通道；不创建 system channel，不使用 consortium 配置和旧式 `peer channel create` 路线。3.1.5 的官方 `orderer.yaml` 已没有旧的 `General.BootstrapMethod` 字段，本文不要求添加 `BootstrapMethod: none` 这类旧教程配置。[R09][R14]

Capabilities 固定为：`Channel: V3_0`、`Orderer: V2_0`、`Application: V2_5`。三者不是“把所有字段都写 V3_0”；采用的是固定版本中实际支持的各层 capability。[R07]

排序参数采用学习基线：`BatchTimeout=1s`、`MaxMessageCount=20`、`PreferredMaxBytes=512 KB`、`AbsoluteMaxBytes=10 MB`。这些是项目选择，后续仅通过受控配置变更实验调整，不能写成 Fabric 默认值。

每个 Peer 直接从排序服务获取区块：`gossip.orgLeader=true`、`gossip.useLeaderElection=false`、`gossip.state.enabled=false`、`deliveryclient.blockGossipEnabled=false`。保留用于组织发现及私有数据分发的 gossip，不把“关闭区块 gossip”误认为关闭所有 gossip。[R01][R10]

### 5.4 从空目录到可用通道

以下每步都必须先完成一次手工操作，并保留脱敏证据：

| 步骤   | 输入与动作                                             | 验收产物                                                 |
| ------ | ------------------------------------------------------ | -------------------------------------------------------- |
| NET-01 | 初始化各组织 TLS CA、Enrollment CA                     | 根证书、CA 数据库、指纹清单                              |
| NET-02 | 注册并 enroll 节点、管理及业务身份；建立本地和公有 MSP | 证书检查报告；无私钥进入公有 MSP                         |
| NET-03 | 编写 configtx.yaml，运行 configtxgen                   | `supplychannel.block` 和解码 JSON                        |
| NET-04 | 启动 3 个无通道 Orderer，检查 admin API                | 每节点可通过正确 mTLS 查询                               |
| NET-05 | 逐个执行 osnadmin channel join                         | 三节点均加入 supplychannel，达到 active / consenter 状态 |
| NET-06 | 启动各组织 Peer / CouchDB，逐个 peer channel join      | 每 Peer 本地账本存在 supplychannel                       |
| NET-07 | 验证 anchor peer、externalEndpoint、TLS 和 gossip      | 组织之间可发现所需 Peer                                  |
| NET-08 | 解码并核对通道配置，记录区块 0 的规范标识              | 全 Peer 与 Orderer 对同一通道初始区块一致                |

原生命令形态如下；环境变量、路径和 mTLS 材料由你自己的目录约定明确填写，不能把此片段当成完整启动脚本：

```bash
configtxgen -profile SupplyChannel \
  -channelID supplychannel \
  -outputBlock /work/artifacts/supplychannel.block

osnadmin channel join \
  --channelID supplychannel \
  --config-block /work/artifacts/supplychannel.block \
  -o orderer0.orderer.supply.test:9443 \
  --ca-file /run/trust/orderer-admin-server-ca.pem \
  --client-cert /run/secrets/osnadmin-client.crt \
  --client-key /run/secrets/osnadmin-client.key

# 在已明确设置 Seller admin 本地 MSP、Peer 地址与 TLS 根的工具容器中执行。
peer channel join -b /work/artifacts/supplychannel.block
peer channel getinfo -c supplychannel
```

必须区分 osnadmin 管理端口和 Orderer 交易端口。通道参与 API 的节点加入权限不等于随意修改通道中的 consenter 集合；既有网络的成员调整需要先分析对应通道配置更新。[R14][R15]

### 5.5 CCaaS 与自建 external builder

每个 Peer 连接本组织对应的独立 CCaaS 容器。Go 链码使用 `contractapi.NewChaincode` 构造合约，将其交给 `shim.ChaincodeServer`，显式配置 `CCID`、监听地址和 TLS。CCID 必须等于该 Peer 实际安装的包 ID，不能填写链码名或 version。[R16]

包结构必须自行生成：

```text
supplycc_1.0.0.tar.gz
  metadata.json          # type=supplyledger-ccaas，label 为固定发布标签
  code.tar.gz
    service.json         # 无秘密：artifactId、源码 commit、镜像 digest 等
    META-INF/statedb/couchdb/indexes/*.json
```

采用“包内无私钥、每 Peer 运行配置单独挂载”的方案。所有 Peer 可安装相同的确定性归档包；各自的 builder 从本地配置解析 artifactId 对应的 CCaaS 地址和 mTLS 材料，最终生成 `chaincode/server/connection.json`。该运行产物含私钥时必须仅 Peer 进程可读，不加入 Git、共享制品或公开构建日志。

`bin/detect` 验证 metadata.type；`bin/build` 验证 service.json 和索引，复制无秘密产物；`bin/release` 读取该 Peer 的本地服务映射，输出连接 JSON 与 `statedb/couchdb/indexes/*.json`。若依赖环境变量，必须通过 `propagateEnvironment` 明确允许。服务连接信息由 release 提供后不使用 `bin/run` 启动链码。自定义 Peer 配置去掉 Docker endpoint，避免 builder 失配后回退到 Docker socket 路径。[R08]

mTLS 的连接 JSON 使用真正的 JSON 布尔值，并满足 `tls_required=true`、`client_auth_required=true`；server 根信任、客户端证书/私钥和 DNS 校验必须齐全。每个服务映射将 artifactId 绑定到实际运行镜像 digest； **Fabric 生命周期本身不会证明外部服务容器运行的二进制就是你宣称的源码** ，该映射还需镜像审查和端到端行为测试。[R16]

### 5.6 链码首次部署原生步骤

自行打包 → `calculatepackageid` → 每 Peer `install` → `queryinstalled` → 各业务组织 `approveformyorg` → `checkcommitreadiness` → `commit` → `querycommitted` → 启动/检查对应 CCaaS → 冒烟调用。

首次最小实现的定义：name=`supplycc`，version=`0.1.0`，sequence=`1`，`init-required=false`，背书和集合配置按第 10–11 章。不同组织对同一定义的 name、version、sequence、policy、collections 和 init 要求必须一致；包 ID 属于组织本地批准信息，不应被误当成全通道定义字段。[R17]

为了保留学习透明度，自编脚本必须打印非敏感的实际命令、当前组织/MSP/目标节点、输入输出路径、阶段结果；失败时停止，不吞掉退出码。记录 secret 时只显示文件路径或摘要，禁止 `set -x` 把 enrollment secret 或 TLS 私钥输出到日志。

---

## 6. 业务范围、角色与核心不变量

### 6.1 业务角色

| MSP / 证书角色                         | 可执行的主要业务                                           |
| -------------------------------------- | ---------------------------------------------------------- |
| SellerMSP / operator                   | 创建批次、提出交易、取消提案、协商取消、授权发货、确认退回 |
| SellerMSP / quality                    | 冻结、参与解除冻结、召回                                   |
| BuyerMSP / operator                    | 确认交易、取消提案、协商取消、确认收货、授权退回           |
| BuyerMSP / quality                     | 验收通过、拒收、冻结、参与解除冻结                         |
| CarrierMSP / operator                  | 接货、运输记录、报告送达、退回接货、报告退回送达           |
| AuditMSP / auditor                     | 查询公共记录、查看历史与业务投影                           |
| 任一组织 admin 或缺少业务属性的 client | 不自动拥有以上任何业务写权限                               |

所有已授权业务角色可读取公共业务信息；商业条款明文仅 SellerMSP / BuyerMSP 的 operator 可经链码读取。链码访问限制不等于能限制这些组织的 Peer / 宿主机管理员直接访问其持有的明文。

### 6.2 必须成立的不变量

| 编号   | 不变量                                                       |
| ------ | ------------------------------------------------------------ |
| INV-01 | 批次总量和计量单位在创建后不可修改；不允许拆分、合并、部分交付 |
| INV-02 | 同一批次最多有一笔未关闭交易，不能同时售给两个买方           |
| INV-03 | 当前所有权 ownerMSP 与实物保管方 custodianMSP 分开建模       |
| INV-04 | 所有权只在 Buyer quality 执行 AcceptBatch 并有效提交时由 Seller 转给 Buyer |
| INV-05 | Carrier 只能在已确认交易和发货授权下接货，不得替 Seller 批准发运 |
| INV-06 | Carrier 的送达报告不改变保管方；Buyer 确认接收后才由 Carrier 变成 Buyer |
| INV-07 | 双方业务同意必须有各自客户端身份发起的有效交易；Peer 背书不替代它 |
| INV-08 | 确认交易绑定不可变 agreementHash；修改条款必须取消旧提案、创建新 tradeId |
| INV-09 | 拒收不转移所有权；退回时必须记录 Buyer 授权、Carrier 接货和 Seller 接收 |
| INV-10 | 任何状态更新必须来自受限链码函数，不提供通用 SetState / UpdateAnything / DeleteBatch 接口 |
| INV-11 | 同一业务命令最多产生一次业务状态变化；超时和重试不能重复交付或转移所有权 |
| INV-12 | 私有金额、salt、合同内容不得出现在普通参数、公共状态、公共事件、错误或运行日志中 |
| INV-13 | 链外查询数据库不是业务事实来源，禁止通过改 SQL 表改变链上业务结果 |
| INV-14 | 历史业务不删除；取消和纠正使用新记录，不能删除区块或改旧交易 |
| INV-15 | 每次成功变更记录签名者 MSP、稳定 userId、证书指纹、txId 和提案时间 |

这些不变量必须能由自动化测试检查，而不是仅在 README 中宣称。账本历史与当前世界状态是不同结构，世界状态可以反映新的取消或纠正结果，不能由此推断历史已被删除。[R27]

---

## 7. 状态机与业务流程

### 7.1 主要状态

Batch.state：`READY`、`RESERVED`、`IN_TRANSIT`、`DELIVERED`、`ACCEPTED`、`RETURN_IN_TRANSIT`、`RETURNED`。

Trade.state：`PROPOSED`、`CONFIRMED`、`IN_TRANSIT`、`DELIVERED`、`COMPLETED`、`REJECTED`、`RETURN_AUTHORIZED`、`RETURN_IN_TRANSIT`、`RETURNED`、`CANCELLED`。

Shipment.state：`PLANNED`、`READY_FOR_PICKUP`、`IN_TRANSIT`、`DELIVERY_REPORTED`、`DELIVERED`、`RETURN_AUTHORIZED`、`RETURN_IN_TRANSIT`、`RETURN_DELIVERY_REPORTED`、`RETURNED`、`CANCELLED`。

`frozen` 和 `recalled` 是 Batch 上独立的限制标志，不用它们覆盖物流状态。标志记录关联原因和版本；不能为了表示冻结而丢掉货物当前所在环节。

### 7.2 正常流程

| 命令 / 提交者                        | 前置条件                                       | 主要状态变化                                                 | 所有权 / 保管方                  |
| ------------------------------------ | ---------------------------------------------- | ------------------------------------------------------------ | -------------------------------- |
| CreateBatch / Seller operator        | batchId 不存在                                 | Batch=READY                                                  | Seller / Seller                  |
| ProposeTrade / Seller operator       | READY，无活动交易，无冻结召回                  | Trade=PROPOSED；Batch=RESERVED；写私有条款                   | 不变                             |
| ConfirmTrade / Buyer operator        | PROPOSED，agreementHash 一致，私有条款校验通过 | Trade=CONFIRMED；建立 PLANNED Shipment；加强 Batch SBE       | 不变                             |
| AuthorizeDispatch / Seller operator  | CONFIRMED + PLANNED，无冻结召回、无待处理取消  | Shipment=READY_FOR_PICKUP；记录 Seller 授权                  | 不变                             |
| PickupShipment / Carrier operator    | 有有效 Seller 授权，无冻结召回、无待处理取消   | Batch/Trade/Shipment=IN_TRANSIT                              | Seller / Carrier                 |
| RecordCheckpoint / Carrier operator  | Shipment=IN_TRANSIT                            | 追加运输记录，增加 Shipment.revision                         | 不变                             |
| ReportDelivery / Carrier operator    | Shipment=IN_TRANSIT                            | Shipment=DELIVERY_REPORTED                                   | Seller / Carrier，尚未交给 Buyer |
| AcknowledgeDelivery / Buyer operator | DELIVERY_REPORTED                              | Batch/Trade/Shipment=DELIVERED                               | Seller / Buyer                   |
| AcceptBatch / Buyer quality          | DELIVERED，无冻结召回，尚无验收结论            | Batch=ACCEPTED；Trade=COMPLETED；新增 Inspection；关闭活动交易 | Buyer / Buyer                    |

`Shipment` 在 ConfirmTrade 中产生，shipmentId 由客户端提出但必须唯一，并绑定 tradeId。各阶段不通过传入 ownerMSP/custodianMSP 来“设置目标所有者”，而由链码根据上述转换确定。

### 7.3 取消流程

**提案尚未确认：**  Seller 或 Buyer operator 可执行 CancelProposedTrade，将 Trade 改为 CANCELLED，Batch 恢复 READY，清除 activeTradeId。旧条款和提案历史保留；不得改写旧提案后复用原确认。

**已确认、尚未接货：**  Seller 或 Buyer operator 执行 RequestCancellation，创建不可变取消提案，包含 tradeId、agreementHash、原因摘要和 approvalId（Trade.pendingCancellationId 引用该 ID）；另一方执行 ConfirmCancellation 才能取消。Shipment 只能处于 PLANNED / READY_FOR_PICKUP，且提案必须在接货前建立。存在待处理取消提案时禁止 AuthorizeDispatch / PickupShipment；发起方可 WithdrawCancellation 恢复正常流程。

ConfirmCancellation 将 Trade/Shipment 改为 CANCELLED，Batch 恢复 READY，并将 Batch 的 SBE 恢复为双方策略。SBE 变更交易仍必须满足变更前策略。已经接货后，不允许通过取消把实物保管方直接改回 Seller；必须走后续记录与退回流程。

### 7.4 拒收与退回

| 命令 / 提交者                           | 前置条件                    | 变化                                                         |
| --------------------------------------- | --------------------------- | ------------------------------------------------------------ |
| RejectBatch / Buyer quality             | 已确认收货，Batch=DELIVERED | Trade=REJECTED；新增 REJECTED Inspection；Batch 仍 DELIVERED，owner=Seller、custodian=Buyer |
| AuthorizeReturn / Buyer operator        | REJECTED                    | Trade/Shipment=RETURN_AUTHORIZED；记录 Buyer 交回授权        |
| PickupReturn / Carrier operator         | 有 Buyer 退回授权           | Batch/Trade/Shipment=RETURN_IN_TRANSIT；custodian=Carrier    |
| ReportReturnDelivery / Carrier operator | RETURN_IN_TRANSIT           | Shipment=RETURN_DELIVERY_REPORTED；保管方不变                |
| AcknowledgeReturn / Seller operator     | RETURN_DELIVERY_REPORTED    | Batch/Trade/Shipment=RETURNED；custodian=Seller；关闭活动交易；恢复 Batch 双方 SBE |

退回过程从未把 owner 改为 Buyer；因此不是“把已经转移的所有权回滚”。RETURNED 和 ACCEPTED 是 1.0 的终态，不继续支持再次出售。运输记录允许单独存放，不将无限增长的 checkpoint 数组嵌在 Batch 中。

### 7.5 冻结与召回

FreezeBatch 由 Seller quality 或 Buyer quality 发起，记录 freezeId、原因、发起身份和 freezeRevision。已冻结时再次冻结应返回明确冲突，而不是覆盖原有冻结原因。

解除冻结需要 RequestUnfreeze 和另一组织 quality 的 ConfirmUnfreeze 两次有效交易，绑定 freezeId 和 freezeRevision。同一方的两个账号不等于双方批准。旧的解冻提案不能作用于一次新冻结。不存在冻结时不允许创建解冻提案。

RecallBatch 仅允许 Seller quality 执行，设置不可逆的 `recalled=true` 及召回原因。不得把召回直接等同于退款、所有权撤销或实物已退回。ACCEPTED 后允许记录召回警示，但完整售后退货流不在 1.0 范围。

| 操作类别                                                     | frozen=true        | recalled=true              |
| ------------------------------------------------------------ | ------------------ | -------------------------- |
| ProposeTrade、ConfirmTrade、AuthorizeDispatch、PickupShipment、AcceptBatch | 拒绝               | 拒绝                       |
| 实际运输检查点、报告送达、确认接收                           | 允许记事实         | 允许记事实                 |
| RejectBatch、退回授权与实际退回交接                          | 允许               | 允许                       |
| 取消交易 / 取消提案处理                                      | 按取消阶段规则允许 | 按取消阶段规则允许         |
| 冻结与解冻管理                                               | 按独立审批规则     | 解冻不能消除 recalled 标志 |
| 公共查询、历史查询                                           | 允许               | 允许                       |

这样定义的“冻结”是阻止继续发运、交易承诺或验收完成，不是禁止记录已经发生的物理事实。

---

## 8. 数据模型、键空间与数据分类

### 8.1 通用规则

业务 ID 使用 `[A-Z][A-Z0-9-]{2,63}`；userId 使用 `[a-z0-9._-]{3,64}`；requestId 使用标准小写 UUID 字符串。ID 不允许分隔符注入、NUL 和路径字符。链码键必须经 `CreateCompositeKey` 构造；文中的 `batch~ID` 仅表示逻辑命名，不要求手工拼接波浪线。

所有可变主对象包含：`docType`、`schemaVersion`、`id`、`revision`、`createdTxId`、`updatedTxId`、`createdAt`、`updatedAt`。revision 在每次实际变更时恰好增加 1，不是 Fabric 内部 MVCC 版本；内部版本不由业务自行指定。

数量与金额在 Go 内用检查溢出的整数运算。JSON 中数量、revision 和金额用十进制数字字符串表示，避免前端大整数精度问题；不允许小数、负数、指数表示或前导加号。数量范围为 1–10^12；金额以币种最小单位表示，范围为 1–10^15。1.0 只支持单位 PCS / GRAM 和币种 CNY。时间为 UTC RFC3339Nano，来源见第 12 章。

### 8.2 公共对象

| 对象 / 逻辑键                                   | 关键业务字段                                                 | 更新规则                                                    |
| ----------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------- |
| Batch / batch~batchId                           | sku、quantity、unit、issuerMSP、ownerMSP、custodianMSP、state、activeTradeId、frozen、freezeRevision、recalled、publicDocumentRefs | SKU、数量、单位、issuer 不变；其他字段只能由状态机更新      |
| Trade / trade~tradeId                           | batchId、sellerMSP、buyerMSP、carrierMSP、shipmentId、state、agreementVersion、agreementHash、privateTermsHash、proposedBy、confirmedBy、pendingCancellationId | 协议内容不可改，只改变流程状态与关联批准                    |
| Shipment / shipment~shipmentId                  | batchId、tradeId、carrierMSP、state、dispatchAuthorization、deliveryReport、returnAuthorization、returnDeliveryReport | 授权与报告一旦形成保留原记录，不能覆盖成另一个事实          |
| Inspection / inspection~inspectionId            | batchId、tradeId、decision、reasonCode、publicReportHash、inspector | 一笔交易只允许一个验收结论，不允许先 ACCEPT 后覆盖为 REJECT |
| Checkpoint / checkpoint~shipmentId~checkpointId | locationCode、conditionCode、evidenceHash、actor、recordedAt | 追加、不可修改；单条大小受限                                |
| BusinessApproval / approval~approvalId          | kind=CANCEL/UNFREEZE、targetId、boundHash、boundRevision、requester、confirmer、status | 内容绑定后不可修改；只能终结或撤回，保留记录                |
| RecallNotice / recall~batchId                   | reasonCode、publicEvidenceHash、initiator、txId              | 1.0 每批次一份，不允许撤销或覆盖                            |
| CommandReceipt / cmd~MSP~userId~requestId       | function、requestHash、originalTxId、resultRefs、resultSummary | 不可修改，作为幂等与结果核对依据                            |

Actor 结构：`mspId`、`userId`、`certificateSHA256`。证书指纹用于审计，稳定 userId 用于跨续期的业务身份匹配；身份真实性仍由 MSP 和证书属性验证，不能因为请求里填了相同 userId 就接受。

### 8.3 复合键索引

必须实现 `batchByOwner~ownerMSP~batchId`、`batchByState~state~batchId`、`tradeByBatch~batchId~tradeId`、`checkpointByShipment~shipmentId~checkpointId`。索引值为空占位或最小元数据，不能复制整份主对象。改变 owner / state 时同一交易内删除旧索引、写入新索引。注意索引键也是写集的一部分，会影响交易所需背书。

CouchDB 至少包含批次 owner+state+id、交易 buyer+state+id 两类 JSON 索引。读 API 只接受结构化白名单过滤参数，不接受客户端传入任意 Mango selector。分页默认 20、最大 100，bookmark 视为不透明值。多次分页请求不承诺跨请求快照隔离；完整一致性导出使用固定区块高度的事件投影快照，不以并发变化中的分页结果证明无遗漏。

富查询和分页用于只读接口，不能把一次富查询结果作为同一交易中批量更新的安全依据；写交易对明确键进行读取及版本约束。不要直接修改 CouchDB 文档绕过链码。[R20][R21]

### 8.4 私有对象

`TradeTermsV1` 存入 `sellerBuyerTerms`，键为 `terms~tradeId`；包含 `docType`、`schemaVersion`、tradeId、batchId、sellerMSP、buyerMSP、quantity、unit、currency、totalPriceMinor、contractDocumentHash 和 salt。

单条私有条款最大 16 KiB；不写自由文本合同正文。`salt` 是客户端生成的 32 个随机字节的 Base64 编码；它只存私有集合，不作为普通参数或公共字段。合同原文件保留于链外受控存储，不通过公共对象或公共事件泄露下载凭据。

### 8.5 数据大小与保留

公共主对象目标上限 16 KiB；单条证据元数据 4 KiB；单交易事件上限 256 KiB；链码普通请求 JSON 上限 64 KiB。拒绝超限输入，不依赖 gRPC 的较大默认消息上限替你做业务限制。

主流程中公共对象和 CommandReceipt 不物理删除。集合默认不按区块数过期，`blockToLive=0`。私有数据 purge 仅在独立实验数据或明确审批的扩展流程测试，不能为了腾磁盘自动清除在途交易条款。[R19]

### 8.6 字段级约束补充

以下约束消除实现时的自由解释；接口白名单中列出的 payload 字段默认必填，只有明确声明可选的字段例外。无附件时 `publicDocumentRefs=[]`，不用 null。未形成的链上关联 ID 使用空字符串；各状态须验证其是否应为空。所有 SHA-256 字段使用 64 位小写十六进制，无摘要时不得用随意文本占位。

| 字段/结构                                             | 固定约束                                                     |
| ----------------------------------------------------- | ------------------------------------------------------------ |
| schemaVersion / eventSchemaVersion / agreementVersion | JSON 正整数，1.0 初始均为 1；与字符串型业务 revision 区分    |
| revision                                              | 新对象从字符串 `"1"` 开始；每次实际修改加一；范围 1..2^63-1，达到上限拒绝继续更新 |
| quantity / totalPriceMinor                            | 规范十进制字符串；无前导零；按第 8.1 章范围和单位校验        |
| sku                                                   | ASCII `[A-Z0-9][A-Z0-9._-]{0,63}`；创建后不变                |
| reasonCode                                            | 白名单 QUALITY_ISSUE / DAMAGE / WRONG_GOODS / AGREEMENT_CHANGE / OTHER；不存自由文本商业秘密 |
| locationCode                                          | ASCII `[A-Z0-9][A-Z0-9._-]{0,63}`；只记录非敏感位置代号      |
| conditionCode                                         | NORMAL / DAMAGED / DELAYED / EXCEPTION                       |
| buyerMSP / carrierMSP                                 | 1.0 只接受 BuyerMSP / CarrierMSP；sellerMSP 从已认证 Seller 身份确定，不允许任意组织字符串 |
| publicDocumentRefs                                    | 最多 8 项；按 fileId 排序且唯一；每项含 fileId、sha256、sizeBytes、mediaType、ownerMSP；sizeBytes 为规范十进制字符串，最大 10 MiB |
| publicReportHash 与各 EvidenceHash                    | 非空、格式正确的 SHA-256；可指向链外受控证据；哈希格式校验不证明文件内容或事实真实 |
| Actor                                                 | mspId、userId、certificateSHA256；来自客户端身份，不是 Peer 本地 MSP 或 HTTP token 中未验证的声明 |
| BusinessApproval.status                               | REQUESTED / CONFIRMED / WITHDRAWN；请求内容不可改；失去适用条件的旧提案即使保留 REQUESTED，也不能再确认 |
| freezeRevision                                        | Batch 上单调增长的冻结计数，每次新冻结加一，解冻不归零；freezeId、freezeRevision、原因和发起者共同绑定当前冻结 |

对同一冻结允许存在多个尚未完成的解冻提案，但只有匹配当前 freezeId+freezeRevision 且尚未解除的提案可确认；首次有效确认解除冻结后，其他旧提案变为不适用，不能用于下次冻结。此规则不需要在 RequestUnfreeze 中写 Batch，从而保持第 10 章的写集/背书定义一致。

AcceptBatch 和 RejectBatch 都必须同时满足 Trade=DELIVERED、Shipment=DELIVERED、Batch=DELIVERED、尚未存在该交易的验收结果。仅检查 Batch=DELIVERED 不足以阻止拒收后的第二次验收。接受后 Shipment 保留 DELIVERED；它表示实物交接完成，不承担 Trade 的商业完成语义。

取消确认/撤回均清除 Trade.pendingCancellationId，并终结对应 Approval。Batch.frozen 的 true→false 只能来自合法 ConfirmUnfreeze；RecallBatch 不能再次覆盖已存在 RecallNotice。完整 schema 和每函数 JSON Schema 必须纳入实现仓库的版本控制，并与这些契约及 OpenAPI 保持一致。

---

## 9. Go 链码接口契约

### 9.1 合约形态

合约名 `SupplyContract`。每个写函数都接收一个严格解码的 JSON 请求，返回 `CommandReceipt`；不暴露自由指定底层键、MSP 或状态的通用写接口。

```go
// 所有其他写函数遵循相同契约；这是接口形态，不是完整实现。
func (c *SupplyContract) CreateBatch(
    ctx contractapi.TransactionContextInterface,
    requestJSON string,
) (*CommandReceipt, error)
```

请求公共封套：`schemaVersion=1`、`requestId`、`expectedRevisions`、`payload`。expectedRevisions 是已存在 Batch / Trade / Shipment 等业务主对象的 objectType、id、revision 列表，按 objectType+id 排序，重复项拒绝。新建对象不携带预期版本。每个函数在自己的契约中列出需要检查的对象；不得接受客户端声明“无需检查版本”。

反序列化必须拒绝未知字段、重复 JSON 字段和尾随第二个 JSON 值，所有字符串与数值做长度/格式校验。actor、txId、ownerMSP 等系统字段由链码生成，payload 携带它们时拒绝而不是悄悄忽略。

### 9.2 写函数清单

下表中的“主要载荷”不重复公共封套。函数除以下约束外，还必须满足第 7 章阶段、角色及冻结规则。

| 函数                 | 主要载荷                                                     | 已存在主对象的版本检查                   | 特殊行为                                                 |
| -------------------- | ------------------------------------------------------------ | ---------------------------------------- | -------------------------------------------------------- |
| CreateBatch          | batchId、sku、quantity、unit、publicDocumentRefs             | 无                                       | ID 必须不存在；owner/custodian 自动为 Seller             |
| ProposeTrade         | tradeId、batchId、buyerMSP、carrierMSP、privateTermsHash     | Batch                                    | transient.trade_terms 必须存在；创建不可变提案           |
| ConfirmTrade         | tradeId、shipmentId、expectedAgreementHash                   | Batch、Trade                             | Buyer 核验条款；新 Shipment；设置后续运输 SBE            |
| CancelProposedTrade  | tradeId、reasonCode                                          | Batch、Trade                             | 仅 PROPOSED，单方可终止未成立提案                        |
| RequestCancellation  | tradeId、approvalId、reasonCode                              | Batch、Trade、Shipment                   | 仅接货前；绑定 agreementHash；设置 pendingCancellationId |
| ConfirmCancellation  | approvalId、expectedApprovalHash                             | Batch、Trade、Shipment、BusinessApproval | 仅另一组织 operator；恢复可售状态                        |
| WithdrawCancellation | approvalId                                                   | Trade、BusinessApproval                  | 仅发起者组织 operator，且尚未确认                        |
| AuthorizeDispatch    | tradeId、authorizationEvidenceHash                           | Batch、Trade、Shipment                   | 只能 Seller 发起；写入不可变发运授权                     |
| PickupShipment       | shipmentId、pickupEvidenceHash                               | Batch、Trade、Shipment                   | 只允许授权的 Carrier 接货                                |
| RecordCheckpoint     | shipmentId、checkpointId、locationCode、conditionCode、evidenceHash | Batch、Shipment                          | 明确读取 Batch 的限制标志；追加记录并增加 Shipment 版本  |
| ReportDelivery       | shipmentId、deliveryEvidenceHash                             | Batch、Trade、Shipment                   | 仅报告，不变更 custodian                                 |
| AcknowledgeDelivery  | shipmentId、receiptEvidenceHash                              | Batch、Trade、Shipment                   | Buyer 确认后才变更 custodian                             |
| AcceptBatch          | tradeId、inspectionId、publicReportHash                      | Batch、Trade、Shipment                   | Buyer quality；唯一所有权转移点                          |
| RejectBatch          | tradeId、inspectionId、reasonCode、publicReportHash          | Batch、Trade、Shipment                   | Buyer quality；所有权仍归 Seller                         |
| AuthorizeReturn      | tradeId、returnEvidenceHash                                  | Batch、Trade、Shipment                   | Buyer operator 对交回实物授权                            |
| PickupReturn         | shipmentId、pickupEvidenceHash                               | Batch、Trade、Shipment                   | custodian 从 Buyer 变 Carrier                            |
| ReportReturnDelivery | shipmentId、returnDeliveryEvidenceHash                       | Batch、Trade、Shipment                   | 只报告，不变更 custodian                                 |
| AcknowledgeReturn    | shipmentId、receiptEvidenceHash                              | Batch、Trade、Shipment                   | Seller 确认接回，终结退回流程                            |
| FreezeBatch          | batchId、freezeId、reasonCode、publicEvidenceHash            | Batch                                    | Seller/Buyer quality；不能覆盖旧冻结                     |
| RequestUnfreeze      | batchId、approvalId、freezeId、freezeRevision、reasonCode    | Batch                                    | 发起双方解冻审批                                         |
| ConfirmUnfreeze      | approvalId、expectedApprovalHash                             | Batch、BusinessApproval                  | 另一组织 quality，严格匹配当前冻结                       |
| RecallBatch          | batchId、reasonCode、publicEvidenceHash                      | Batch                                    | Seller quality；不可逆标记                               |

为了避免重复逻辑，各函数统一调用身份验证、严格解码、幂等检查、读取/版本校验、业务校验、写集构造、索引维护、事件构造等内部组件。业务校验不得散落在 HTTP 层而链码内缺失。

### 9.3 查询函数

| 函数                                            | 契约                                                         |
| ----------------------------------------------- | ------------------------------------------------------------ |
| GetBatch(batchId)                               | 返回公共 Batch；不存在则 E_NOT_FOUND                         |
| GetTrade(tradeId)                               | 返回公共 Trade，不返回价格或 salt                            |
| GetShipment(shipmentId)                         | 返回公共 Shipment                                            |
| GetInspection(inspectionId)                     | 返回不可变验收结果                                           |
| GetApproval(approvalId)                         | 返回取消 / 解冻审批内容和状态                                |
| GetRecall(batchId)                              | 返回召回元数据                                               |
| GetPublicBundle(batchId)                        | 返回当前批次和当前/最近关联交易、运单的公共视图，方便客户端构造版本条件 |
| GetPrivateTerms(tradeId)                        | 仅 SellerMSP / BuyerMSP 的 operator；连接可持有条款的 Peer   |
| GetPrivateTermsHash(tradeId)                    | 授权公共读角色可读；返回已提交私有值的哈希，不返回明文       |
| GetCommandReceipt(requestId)                    | 默认只能读取当前 MSP+userId 的回执；不接受任意 impersonation 参数 |
| ListBatches(queryJSON)                          | 过滤字段、排序、分页和索引白名单                             |
| ListTradesByBatch(batchId, pageSize, bookmark)  | 复合键只读分页                                               |
| ListCheckpoints(shipmentId, pageSize, bookmark) | 复合键只读分页                                               |
| GetBatchHistory(batchId, limit)                 | 教学用有界公共历史，limit 1–100；不声称 history API 原生支持 CouchDB bookmark |

公共历史的完整导出通过第 14 章区块/事件索引完成，而不是每次查询都在链码里无界扫描账本历史。开启 history database，并单独解释 history DB、世界状态 DB 和区块存储的职责。[R27]

### 9.4 错误契约

应用层稳定错误码包含：`E_INVALID_ARGUMENT`、`E_FORBIDDEN`、`E_NOT_FOUND`、`E_ALREADY_EXISTS`、`E_INVALID_STATE`、`E_VERSION_CONFLICT`、`E_ACTIVE_TRADE_EXISTS`、`E_AGREEMENT_MISMATCH`、`E_PRIVATE_DATA_UNAVAILABLE`、`E_FROZEN`、`E_RECALLED`、`E_DUPLICATE_REQUEST_MISMATCH`、`E_APPROVAL_INVALID`、`E_LIMIT_EXCEEDED`。

链码业务错误采用统一可解析的公共格式，例如 `E_INVALID_STATE: cannot accept before delivery acknowledgement`。应用不得仅依赖模糊字符串匹配处理所有 Gateway 错误；Fabric 验证码如 `MVCC_READ_CONFLICT`、`ENDORSEMENT_POLICY_FAILURE` 和连接/超时错误应保留各自类别。不能在错误中包含私有金额、合同正文或 transient 原文。

---

## 10. 背书、状态级背书与网络治理

### 10.1 三个不同的批准层

**业务批准：**  Seller / Buyer 的客户端身份分别提交业务交易；判断谁同意哪一版条款。

**业务交易背书：**  指定 Peer 组织确认同一提案的执行结果；判断谁共同信任这次账本更新。

**网络和链码定义治理：**  管理员修改通道配置、组织批准链码定义和提交定义；判断规则由谁维护。

三者不允许互相冒充。一个 Buyer Peer 可以为 Seller 的 ProposeTrade 背书，而 Buyer 的业务人员尚未执行 ConfirmTrade。[R17][R18][R22]

### 10.2 主链码策略

定义两种策略：

```text
P_SB  = AND('SellerMSP.peer','BuyerMSP.peer')
P_SBC = AND('SellerMSP.peer','BuyerMSP.peer','CarrierMSP.peer')
```

主链码默认背书策略为 P_SB。Batch 在 CreateBatch 时设置 P_SB；ConfirmTrade 将该 Batch 的键级策略改为 P_SBC，并将新建 Shipment 的键级策略设为 P_SBC。Trade 使用 P_SB。业务终结或确认取消时，将 Batch 恢复为 P_SB；终态 Shipment 保留 P_SBC，不再修改。

这是教学用的明确取舍：买卖双方共同保护交易；履约阶段涉及物流方的联合确认。它增加了可用性依赖，不能解释成“物流业务员也必须点击批准每一次操作”。

### 10.3 必须按完整写集计算策略

| 场景                                                 | 最少需要的组织背书            | 原因                                                         |
| ---------------------------------------------------- | ----------------------------- | ------------------------------------------------------------ |
| 创建批次 / 提出交易                                  | Seller + Buyer                | 默认公共键与私有集合均为 P_SB                                |
| 确认交易、首次加强 Batch 策略                        | Seller + Buyer                | 本交易按旧 Batch 策略和新键的默认策略验证                    |
| 发运、运输、收货、验收、拒收退回                     | Seller + Buyer + Carrier      | 会写运输中的 Batch 或 Shipment 的 P_SBC 键                   |
| 接货前的 RequestCancellation / WithdrawCancellation  | 按实际写集通常 Seller + Buyer | 它们只写 Trade / Approval；读取 Batch 不等于修改它的键级策略 |
| ConfirmCancellation                                  | Seller + Buyer + Carrier      | 修改当前受 P_SBC 保护的 Batch 和 Shipment                    |
| 运输阶段 FreezeBatch / RecallBatch / ConfirmUnfreeze | Seller + Buyer + Carrier      | 修改受 P_SBC 保护的 Batch                                    |
| 单纯创建 RequestUnfreeze                             | Seller + Buyer                | 仅读取 Batch，新增 Approval 和回执使用默认策略               |
| 已完成批次的 FreezeBatch / RecallBatch               | Seller + Buyer                | Batch 已恢复 P_SB                                            |
| 查询公共对象                                         | 不通过提交获取业务写背书      | 是查询，不代表已经达成提交共识                               |

上表描述交易验证必须满足的最低策略，不保证 Gateway 实际只选择这些节点；Gateway 的模拟与背书规划可能因读取、服务可用性而收集更多背书。缺签验证实验必须手工控制实际背书集合。

每次新建 CommandReceipt、索引、Inspection、Checkpoint 等公共键也会引入默认 P_SB 要求。不得只看 Batch 的策略就断言交易“只需一家背书”。对于任何新增函数，都必须写出读集、写集和有效策略组合，并测试缺少其中一家背书的结果。

状态级策略更新必须满足更新前生效的策略；首次给新键设置策略并不能绕过创建交易的默认背书要求。同一交易涉及不同键时，需要满足各写键适用策略的合取条件。[R18][R22]

### 10.4 治理策略

| 配置位置                         | 项目要求                                                     |
| -------------------------------- | ------------------------------------------------------------ |
| 每个组织自身 Admins              | 该组织 admin 签名                                            |
| Application/Admins               | Seller、Buyer、Carrier 三个创始业务组织 admin 中任意两个     |
| Application/LifecycleEndorsement | 三个创始业务组织 peer 中任意两个；与业务 P_SB 分开           |
| Application/Endorsement          | 固定 P_SB；链码定义同时显式固定 P_SB                         |
| Orderer/Admins                   | OrdererMSP.admin                                             |
| Channel/Admins                   | OrdererMSP.admin 且至少两个创始业务组织 admin，用于根层级受此策略控制的变更 |
| Application/Readers              | 各成员组织 Readers，包括后加入的 AuditMSP                    |
| Application/Writers              | 三个创始业务组织允许的 client/admin/peer；AuditMSP 仅 admin  |
| peer/Propose ACL                 | Application/Readers；写函数仍强制检查业务身份和角色          |

所有配置值的 `mod_policy` 必须随通道配置导出检查，不能仅写出一张策略表却让关键节点仍继承其他策略。加入审计组织不自动改变上述创始组织治理门槛。AuditMSP 不是业务背书的必需方，也不因为持有 Peer 就自动取得价格。

主线仍要求三家业务组织都批准和安装正常发布，以确保业务能够执行；“两家已满足生命周期门槛”并不意味着另一家的 Peer 已准备好参与业务背书。故障测试必须演示这一差异。

---

## 11. 私有数据、哈希与隐私验收

### 11.1 集合配置

主集合配置如下；它是你需要实现并测试的明确项目配置：

```json
[
  {
    "name": "sellerBuyerTerms",
    "policy": "OR('SellerMSP.member','BuyerMSP.member')",
    "requiredPeerCount": 1,
    "maxPeerCount": 3,
    "blockToLive": 0,
    "memberOnlyRead": true,
    "memberOnlyWrite": true,
    "endorsementPolicy": {
      "signaturePolicy": "AND('SellerMSP.peer','BuyerMSP.peer')"
    }
  }
]
```

`requiredPeerCount=1` 要求在背书时成功向至少一个其他合格 Peer 分发；它不是“另一个组织必须收到”的组织数量约束。dev 只有两家各一个合格 Peer；resilience 有四个合格 Peer，maxPeerCount=3 是上限而非必须有三台在线。该配置需要与实际在线节点数、gossip、endorsement 和恢复实验一起验证。[R19]

### 11.2 条款传输与访问

ProposeTrade 的商业条款只从 transient map 的 `trade_terms` 读取。应用连接 Seller 的 Gateway，明确将背书组织限制在 SellerMSP 和 BuyerMSP；ConfirmTrade 连接 Buyer Gateway，也只让双方执行需要私有条款的逻辑。

从 ConfirmTrade 之后的物流/验收/冻结流程只使用公共 agreementHash 和业务状态，不调用 GetPrivateData，也不将条款放进 transient。否则会与 P_SBC 中 Carrier 的隐私资格发生冲突。传给一个 Gateway 或背书 Peer 的 transient 明文并不会因为最终存入 PDC 就对那个服务自动保密。[R19][R22]

禁止把敏感内容放入普通链码参数：即便最后没有 PutState，普通参数仍属于交易提案/交易材料。PDC 保护的是明文的持有范围，不隐藏发生过一笔交易、参与组织、访问时序或所有公开业务元数据。[R19]

### 11.3 规范编码与确认摘要

定义唯一的 TradeTermsV1 Go struct 字段顺序，使用固定 JSON 编码规则、无 map、无省略字段和无尾随换行，将验证后的私有对象编码成 canonicalBytes。

`privateTermsHash = SHA256(canonicalBytes)`，使用 64 位小写十六进制表示。PutPrivateData 存入的就是 canonicalBytes，这样返回的 GetPrivateDataHash 可直接与其核对。客户端不得直接对任意格式的 JSON 文件字节求哈希后假设结果一致；必须先按相同类型解码、验证、规范化。

agreementHash 由另一个固定结构计算，含 `schemaVersion`、`tradeId`、`batchId`、sellerMSP、buyerMSP、carrierMSP、quantity、unit、agreementVersion 和 privateTermsHash。Buyer 在 ConfirmTrade 中提交 expectedAgreementHash；链码重新核验公开结构、私有字节和当前提案的匹配关系。

32 字节随机 salt 在客户端生成并包含于 canonicalBytes，防止金额等低熵数据仅凭公开哈希被轻易穷举。salt 重试时必须复用原请求值，不要每次 retry 都生成新的条款摘要。哈希校验只是内容一致性检查，不是实物真实性证明。

### 11.4 规范编码校验向量

字段顺序固定为第 8.4 章的声明顺序，JSON 键使用下列拼写；`schemaVersion` 是 JSON 整数，其余数量/金额是字符串。Go 端使用此固定 struct 的 `json.Marshal` 规则，无尾随换行。这里全零的合同摘要和 salt  **仅是编码测试占位值** ，正式交易必须使用真实文件摘要和随机 salt。

```json
{"docType":"TradeTermsV1","schemaVersion":1,"tradeId":"TRADE-001","batchId":"BATCH-001","sellerMSP":"SellerMSP","buyerMSP":"BuyerMSP","quantity":"100","unit":"PCS","currency":"CNY","totalPriceMinor":"123456","contractDocumentHash":"0000000000000000000000000000000000000000000000000000000000000000","salt":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="}
```

以上单行 UTF-8 字节（不包括 Markdown 围栏与行末换行）的 SHA-256 必须为：

```text
2f71ece7331df5c91747a7d6565c89633b4db0c37ab398dfc909e60d97fd9865
```

该向量只验证编码/摘要，不代表一个真实业务合同，也不能用于隐私强度测试。实现必须再加入真实随机 salt、边界数值和严格解码反例的 golden tests。

### 11.5 必做隐私测试

在合法私有字段中使用可追踪的测试值（如唯一 salt、特殊金额及其组合），分别检查 Carrier Peer、Orderer 区块、Audit Peer、公共 CouchDB 文档、公共事件、API 日志、链码日志、CLI 记录和 PostgreSQL 投影。搜索完整明文之外，还应检查可能的 JSON 字段、Base64 包装和错误回显，形成明确的“检查对象—方法—结果”报告。

Carrier / Audit client 读取 private terms 应失败，但只检查接口返回 403 并不足以验收；必须检查这些组织实际持有的存储与区块数据。Seller 和 Buyer 应能读取并与链上哈希核对。所有 Peer 都可能拥有相应哈希，不能把“能读到哈希”算作明文泄露。

本地测试不能证明宿主机管理员无法看见 Seller / Buyer 数据，也不能证明恶意集合成员不会主动把明文转发出去。隐私验收结论必须带上这个信任边界。

---

## 12. 确定性、并发与业务幂等

### 12.1 确定性要求

链码中不得使用 `time.Now()`、本地随机数、宿主机文件、网络请求、环境变量中的业务规则或不确定的外部服务结果决定账本写入。随机 ID 和 salt 在客户端产生，作为已签名请求的一部分输入；涉及私有内容时通过 transient 传递。

业务记录时间取自 `GetTxTimestamp()`，并统一编码为 UTC。它是客户端提案携带的时间，不是可靠的共识时钟，也不是区块提交时间；本项目不依赖它自动裁决付款到期或合同过期。实际观测到的提交时间由应用记录，命名为 observedCommitAt，与链上提案时间分开。[R33]

将会影响状态或事件的 map 转成确定排序的序列；金额运算不用 float；事件中的 changes 按 objectType+id 排序；跨组织必须使用兼容且固定的序列化和同一发布业务逻辑。链码升级中的兼容规则写入 ADR。

业务函数按“全部读取与校验完成 → 内存构造目标状态 → 写入状态、索引、回执、事件”执行。不要假设同一交易里 PutState 后再 GetState 一定返回刚写入的值；Fabric 模拟读取不是常规数据库事务的 read-your-writes 接口。需要使用自己维护的内存对象。[R20]

### 12.2 版本控制

expectedRevisions 是用户可解释的乐观锁；Fabric MVCC 是提交验证时的读版本冲突检查，两者都需要。仅检查 payload.revision 而不读取真实主键，不足以建立必要的读集。

写操作必须读取目标键；创建对象必须先读取并确认不存在，避免无读取的盲写覆盖。Batch 的 activeTradeId 与状态同一个交易内更新，不能靠 API 内存锁实现跨组织的单一活动交易约束。

### 12.3 幂等定义

幂等键为 `(channel, creatorMSP, supply.userId, requestId)`，不是 Fabric txId。续期后证书指纹可能改变，但稳定 userId 不变，因此不会因为换证书而重复同一业务操作。

requestHash 包含函数名、规范化的业务 payload、私有条款的 privateTermsHash； **不包含**  expectedRevisions、网络超时设置、客户端重试次数或本次 Fabric txId。这些字段是并发/传输条件，不是业务意图。绑定协议或审批的 expectedAgreementHash / expectedApprovalHash 是 payload 的一部分，必须计入。

每个写函数的处理顺序必须是：身份与角色验证 → 请求结构和语义哈希计算 → 读取本用户回执 → 若存在则比较哈希并返回既有结果 → 若不存在再检查当前状态、预期版本和 transient → 执行业务更新并写回执。

同一幂等键、相同语义请求返回原始结果，不再次变更状态、不再发事件；同一键、不同语义请求返回 E_DUPLICATE_REQUEST_MISMATCH。有效的重复查询/提交可能产生另一个 Fabric txId，但回执仍保留 originalTxId。对 ProposeTrade 的幂等重放，既有回执已经证明原条款摘要，不必为无写重放再次提供明文；首次执行仍必须验证 transient 与摘要一致。

回执必须和业务写入在同一 Fabric 交易里。只有 API 数据库里的一行 requestId，不能提供链上幂等保证。

### 12.4 超时与重试规则

| 情况                                    | 行为                                                         |
| --------------------------------------- | ------------------------------------------------------------ |
| 输入、权限、业务阶段不合法              | 不重试；返回可解释业务错误                                   |
| Endorse 之前明确失败                    | 可以重试网络操作，但保持业务 requestId                       |
| 已取得 txId，Submit / CommitStatus 超时 | 标记 PENDING_UNKNOWN，先查该 txId 和 CommandReceipt          |
| 已证实 INVALID / MVCC_READ_CONFLICT     | 重新读账本，确认业务仍适用，再用原语义 requestId 和新提案 txId 重试 |
| 原命令已有有效回执                      | 返回原结果，不重新执行                                       |
| 交易状态暂时查不到                      | 不能直接推断失败；保持待确认，进行有上限的状态核对           |
| 自动重试达到 3 次                       | 停止自动业务重试并暴露明确状态；状态确认可继续，不伪装成功   |

如果原提案尚未到达排序服务，后来用相同业务 requestId 重新发出提案，链上回执键的读冲突仍是防止双重业务执行的最后防线。API 必须记录一个 requestId 的所有 attempt txId，不能丢掉超时的旧 txId。[R20][R22][R23]

### 12.5 必做并发实验

先创建一个 READY 批次，构造两笔不同 tradeId 的 ProposeTrade，都读取同一批次版本； **两笔都完成背书后才开始提交** 。不得只是发两个并发 HTTP 请求后猜测它们用了同一读版本。

预期：在没有其他干扰写的情况下，一笔有效，另一笔因 MVCC 冲突无效；只有一个活动 Trade 和一份实际业务结果。无效交易可能存在于区块内，但其业务写集不进入世界状态。检查 block validation code，而不是只看客户端日志。[R20][R27]

---

## 13. Go 客户端、组织 API 与交易状态

### 13.1 交付的应用

必须实现 `supplyctl` Go CLI、同一代码构建的每组织 API 实例、公共事件投影器。CLI 先于 HTTP API 完成。复杂网页可选，OpenAPI 文档、curl / CLI 能完成全部业务就满足交互要求。

`supplyctl` 至少支持 identity inspect、business command、query、tx status、receipt、block inspect、event watch；管理网络仍使用独立工具与管理员凭证，不把 CA registrar 或通道 admin 功能暴露成业务 API。

应用通过 Fabric Gateway Go API 连接本组织 Peer，使用客户端 ECert 进行签名。必须在一个教学模式中分别展示 Evaluate、NewProposal / Endorse、Submit、CommitStatus，而不是全部隐藏在 SubmitTransaction 一行调用中；正常业务可以封装这些步骤。[R22][R23]

### 13.2 组织身份隔离

seller-api 只能访问 Seller 业务钱包，buyer-api 只能访问 Buyer，carrier-api 只能访问 Carrier。测试登录使用预先生成的随机 token 映射至本组织 `supply.userId`，token 的摘要和映射只存本地受控配置，不从 `X-Org`、URL 或 payload 选择任意钱包。

HTTP 登录认证本身不等于 Fabric 签名：API 要把当前登录用户映射到该用户的 ECert signer，不能让所有人的操作都由一个共享管理员 signer 提交。CLI 也必须明确显示当前 MSP 和 userId。

本地组织 API 是该组织受信的私钥托管者；本项目不证明 API 管理员无法冒充其托管用户。跨组织隔离仍必须成立。token 认证只是单机学习替代方案，不宣称是生产身份提供商。

### 13.3 HTTP 接口

| HTTP 接口                         | 契约                                                         |
| --------------------------------- | ------------------------------------------------------------ |
| POST /v1/commands/{operation}     | operation 是第 9 章写函数的固定映射白名单；请求为公共封套及必要私有输入 |
| GET /v1/commands/{requestId}      | 查询当前登录用户自己的业务请求和全部 attempt 状态            |
| GET /v1/transactions/{txId}       | 返回授权范围内的交易提交状态和验证码                         |
| GET /v1/batches/{id}              | 默认直接从本组织 Peer Evaluate，注明来源                     |
| GET /v1/batches/{id}/bundle       | 获取当前公共业务主对象及 revision                            |
| GET /v1/trades/{id}               | 公共交易记录                                                 |
| GET /v1/trades/{id}/private-terms | 仅 Seller / Buyer 适当角色                                   |
| GET /v1/shipments/{id}            | 运单与业务状态                                               |
| GET /v1/batches、/v1/trades       | 默认 PostgreSQL 公共投影，返回投影进度                       |
| GET /v1/batches/{id}/timeline     | 有界分页公共业务历史，来自区块/事件索引                      |
| POST /v1/documents                | 仅上传允许公开的证据附件；私有合同不使用这个公共通路         |
| GET /v1/documents/{id}            | 身份验证后读取公共附件并返回摘要                             |
| GET /health/live、/health/ready   | 区分进程存活与依赖/通道/链码可用                             |

POST /commands 的 operation 统一入口仅是 HTTP 路由减少重复，不得直接把任意函数名转发给任意 chaincode/channel。允许的函数、角色、payload 和 transient 映射由静态代码和 OpenAPI 指定。

金额等私有输入从 HTTPS body 转入 transient，禁用请求 body 日志，不放 query string。查询结果含私有字段时同样禁止通用响应日志。

### 13.4 提交响应语义

状态枚举：`RECEIVED`、`ENDORSED`、`SUBMITTED`、`COMMITTED_VALID`、`COMMITTED_INVALID`、`PENDING_UNKNOWN`、`REJECTED`。

`SUBMITTED` 只能表示已提交给排序服务或提交调用成功，不表示有效提交；`COMMITTED_VALID` 必须取得有效提交状态，或通过账本中已验证的同一业务回执确认原操作生效。Evaluate 返回值不构成提交证明。[R22]

正常写请求持久化请求摘要后返回 `202 Accepted` 和 requestId / 当前 txId / statusUrl。已确认的同语义重放返回 `200 OK` 与原始回执。请求结构错误 400、未认证 401、无权限 403、不存在 404、业务冲突 409、请求过大 413；已进入待确认状态的提交超时不得简单变成“500=未执行”。

默认时限是项目配置而非 Fabric 默认值：Evaluate 5s、Endorse 15s、Submit 5s、CommitStatus 单次等待 30s。每个阶段单独记录耗时与失败原因；慢电脑可调整并记录差异。重启 API 后从请求日志恢复未确认请求。

### 13.5 查询一致性

每个响应标注 `source=ledger|projection`、`channelId`、`genesisHash` 和可获得的观测进度。投影返回 `projectedThroughBlock`；不要让用户把异步列表当成即时账本状态。

明确区分“相同区块高度的两个 Peer 一致”与“两个可能处于不同高度的 Peer 当前查询结果相同”。提交确认后如从另一个滞后 Peer 查询，要等待它追上或说明滞后，不能把短暂旧值认定为账本分叉。

---

## 14. 事件、链外投影与附件

### 14.1 事件协议

每笔产生业务变更的链码交易只调用一次 SetEvent，事件名为 `SupplyLedger.DomainChanged`，payload 为版本化的批量变化封套。这样一笔跨 Batch / Trade / Shipment 的操作不会用多次 SetEvent 覆盖前一次事件。

字段：`eventSchemaVersion=1`、txId、requestId、operation、actor、proposalTimestamp、changes。每个 change 含 objectType、id、revision、完整公共 after-image 或明确删除标记。1.0 不对业务主对象使用删除。

事件不得包含 private terms、salt、原始 transient、证书私钥或下载 token。链码不知道最终区块号、交易在区块中的位置和最终提交时刻，不在事件里编造这些字段；消费方从有效区块补齐。[R24][R33]

必须包含足够公共数据支持重放：不能只发 batchId，然后消费者在重放历史事件时查询“今天的最新状态”，否则得到的不是当时状态。CommandReceipt 与底层二级索引无需作为领域 after-image 进入公共业务投影；它们由账本保留。

### 14.2 消费实现

主投影器按完整区块顺序消费 Peer Deliver 服务，解码交易并检查 validation flag，只处理 `VALID` 的 supplycc 事件；配置交易、其他链码交易和无事件交易也应推进区块进度。另实现一个 Gateway ChaincodeEvents 观察命令，用于学习和对照，不让两个消费者同时无协调地更新同一组投影。[R24]

每组织只允许一个有效的投影写者，使用数据库锁或等价机制防止双实例并行写同一进度。采用“至少一次消费 + 数据库幂等”，不宣称整个跨系统链路提供 exactly-once 交付。

### 14.3 数据库契约

单个 PostgreSQL 容器中为 Seller、Buyer、Carrier 和后加入 Audit 建立独立数据库/账号，仅保存公共投影和各自 API 请求日志。该单机共享数据库基础设施是资源简化，不是跨组织物理隔离证明。

| 表                                                           | 关键约束                                                     |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| network_identity                                             | channelId + genesisHash，启动时必须核对，防止重建后的同名通道混用旧数据 |
| projection_checkpoint                                        | 下一待处理 blockNumber；绑定 channelId + genesisHash         |
| ledger_events                                                | 唯一键 channelId + genesisHash + txId + eventName；保存 blockNumber、txIndex、payloadHash |
| batches / trades / shipments / inspections / approvals / checkpoints / recalls | 主键绑定网络身份与对象 ID；保存 revision 与最后来源 txId     |
| command_requests                                             | 当前组织 userId + requestId 唯一；语义摘要、总体状态、原始回执引用 |
| command_attempts                                             | txId 唯一，关联业务 requestId；分阶段状态与验证结果          |

每个区块的事件插入、领域 upsert 和 checkpoint 更新在 **同一个 PostgreSQL 事务** 完成。发生崩溃后重读这个区块也不能重复累计业务指标。区块内按交易顺序应用；若同一主键 revision 出现无法解释的缺口或回退，停止推进并报警，不静默覆盖。

API 请求日志与区块投影不是同一类可恢复数据。重建投影只清空 projection/领域表，不删除用户 token、钱包、command_requests 或秘密配置。重建所有公共投影不等于能重建用户私钥或原始私有合同。

### 14.4 重放验收

在每个关键故障点杀掉消费者：收到区块后、插入 event 后但事务未提交、领域对象已更新但 checkpoint 未提交、事务已提交但下一次读取前。重启后得到与无故障连续消费完全相同的公共投影摘要和业务统计。

另外清空投影表，从区块 0 开始重放至同一高度，比较按主键排序后的规范 JSON 摘要。主线不使用 snapshot 加入的无历史节点作为唯一重放源；只有保留相应历史区块的 Peer 才能提供完整事件历史。[R24][R28]

### 14.5 链外文件

1.0 使用按组织分离的本地受控文件卷即可，不强制引入 MinIO。公共证据附件最大 10 MiB，允许 PDF、PNG、JPEG；拒绝路径穿越、可执行文件和不符声明的类型。计算文件原始字节 SHA-256，链上仅保存 fileId、hash、大小、媒体类型和负责提供文件的组织。

fileId 为不可预测 ID，不能用文件名直接拼接磁盘路径。源组织用户通过本组织已认证 API 下载附件；跨组织副本在 1.0 通过受控的离线文件交换提供，接收者必须重新校验摘要。跨组织在线文件授权不在本项目 1.0 范围，不能声称本地 token 自动支持联盟身份联合登录。所谓公共证据，是通道相关方允许共享，不是互联网匿名公开。

私有合同通过 Seller / Buyer 各自受控的私有文件路径提供给交易操作，不经公共附件 API 分发；其摘要存 PDC。1.0 不承诺私有合同原文件的跨组织在线共享服务，测试可由两个受控客户端预先持有同一文件。禁止把预签名 URL、密码或本机绝对私有路径写入公共账本。

---

## 15. 链码升级、新组织接入与配置变更

### 15.1 版本与 schema 的四个维度

必须区分 Fabric 节点软件版本、chaincode version、chaincode definition sequence、业务 schemaVersion。再额外记录 packageId 和 CCaaS image digest。它们各有职责，不要求数字相等。

链码定义 sequence 每次定义更新递增；只更改策略或集合配置也可能需要新的定义 sequence，而无需改变业务代码。更新一份外部服务容器不会自动形成通道层面的可审计链码升级。[R17]

### 15.2 必做链码升级

从已验收的 chaincode 1.0.0 / sequence S 升级到 1.1.0 / sequence S+1（S 取发布清单中的实际正整数），为 Batch 新增 `qualityGrade`，枚举为 UNKNOWN / A / B / C。历史 schemaVersion=1 缺失字段必须能够读取为 UNKNOWN；不得要求删账本重来。

新增 `SetQualityGrade` 只允许 Seller quality 在 READY 状态设置；不得借升级修改已交付批次的历史质量声明。新写对象使用 schemaVersion=2；历史对象采用显式、逐键的受控迁移或读取兼容策略，方案写 ADR，禁止“升级后启动时自动全库扫描写入”。

本地从 1.0 到 1.1 的升级采用维护窗口：暂停业务新写 → 等待已提交交易状态收敛并记录未确认请求 → 构建/审查新 CCaaS 镜像和确定性包 → 各 Peer 安装 → 各组织批准 → 检查 readiness → 提交 sequence S+1 → 验证各 Peer 可调用新服务 → 验证旧对象 → 恢复写入。

旧服务保留到所有可能使用旧定义的在途交易都处理完，不声称发布零停机。出现错误时不能把 sequence 降回旧值；发布修正的更高 sequence，并说明数据 schema 是否允许旧逻辑恢复。业务补偿另用业务交易，不直接修改 CouchDB。

### 15.3 新组织接入

AuditMSP 必须在至少存在 100 笔业务相关有效交易、且包含一笔已完成交易和一笔私有条款交易后加入。

步骤：生成 Audit CA / 身份 / 公有 MSP → 获取当前通道配置 → 解码并仅加入审核过的组织、reader/必要 admin writer 权限与 anchor 信息 → compute_update → 创建 ConfigUpdateEnvelope → 按现有 mod_policy 收集签名 → 提交通道配置更新 → Audit Peer 从保留的区块 0 加入并同步 → 安装链码、批准同一现有定义供本组织 Peer 使用 → 启动审计查询和投影。[R26]

Audit 的加入不能无意改变创始组织 Admins / LifecycleEndorsement 门槛，不能加入 sellerBuyerTerms 的分发策略，也不能把 Audit 加进业务 P_SB / P_SBC。

新组织加入同一通道会取得该通道可提供的公共历史。不能承诺“加入后只能看新数据、看不到以前的公共交易”。若业务需要时间段隔离，应另做数据共享边界设计，而不是以链码查询过滤代替账本可见性。

### 15.4 通道配置变更证据

每次变更必须保留：变更前 config block、规范化 JSON diff、ConfigUpdate 原始文件、签名组织清单、提交 txId、变更后 config block，以及回归验证。导出材料不得含私钥。证书、策略、anchor 或批次参数变更不得用覆盖本地 YAML 冒充通道已生效。

---

## 16. 可观测性、备份与故障演练

### 16.1 日志与指标

所有业务服务输出结构化日志，含 component、org、operation、requestId、txId、阶段、耗时、公共错误码。不得记录完整请求 body、transient、签名私钥、enrollment secret 或私有读取响应。

至少采集 Peer 区块高度、交易验证结果、Orderer 领导/共识状态、容器 CPU/RAM、CouchDB 请求状况、Gateway 各阶段耗时、投影滞后、证书剩余有效期。指标名以固定版本实际 `/metrics` 输出为准，不在代码里猜不存在的指标名。[R35]

readiness 必须检查本组织所需的 Peer 可连接、正确通道可查询、supplycc 定义匹配、查询可执行。观察到单个实例活着不足以宣布“网络可写”；是否满足某函数所需背书与 Raft 多数派，应单独展示。

### 16.2 故障矩阵

| 故障注入                              | 预期现象                                                     | 恢复与验收                                                   |
| ------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 停 1 个 Raft Orderer                  | 其余两个形成多数派；必要条件满足时仍能推进，领导切换期间可短暂延迟 | 恢复节点并追平；不丢已确认有效交易                           |
| 停 2 个 Raft Orderer                  | 不能继续推进新排序提交；已存在账本的查询可继续               | 恢复至少多数派，确认待定交易结果，不盲目重发                 |
| dev 停 Seller 唯一 Peer               | P_SB / P_SBC 相关写无法收集所需背书                          | 恢复后追平；业务不因失败部分更新                             |
| resilience 停 Seller peer0 + 对应 cc0 | 同组织 peer1/cc1 可承担所需业务执行                          | 应用重连本组织备用 Gateway，保持身份和 requestId             |
| 停某 CCaaS 容器                       | 对应 Peer 可能无法模拟该链码；不应误报 Orderer 故障          | 重启正确镜像/CCID/TLS 服务，恢复调用                         |
| 停 CouchDB                            | 对应 Peer 的查询/模拟或提交能力受影响                        | 恢复数据库后确认 Peer 追平与状态正确                         |
| 暂停 API 的 CommitStatus 响应路径     | 客户端进入 PENDING_UNKNOWN，不擅自判失败                     | 按 txId / 回执核对，确认仅一次业务变化                       |
| 杀事件消费者                          | 投影落后，账本仍可运行                                       | 从数据库 checkpoint 重读，不丢不重                           |
| Seller 私有数据持有 Peer 离线后恢复   | 区分区块同步成功与私有明文是否已补齐                         | 在保留完整数据的合格 Peer 帮助下核验恢复；无可用副本时明确不能从哈希恢复明文 |
| 破坏一个 TLS SAN 或使用错误 CA        | TLS 握手/主机名验证失败                                      | 定位证书而非靠关闭 TLS 绕过                                  |
| 吊销一个业务 ECert                    | CA 吊销本身尚不是全网生效证明                                | 发布相关 MSP CRL 配置，之后新交易被拒绝                      |
| 删除一个指定的测试节点卷              | 该节点失去本地数据                                           | 从冷备份或保留账本的合法恢复流程恢复，不删其他节点           |

三节点 Raft 的容错基于多数派；停机测试验证的是崩溃故障，不是恶意节点下的 BFT。恢复后按同一区块高度比较区块哈希和业务状态，不将短暂高度差当作分叉。[R15]

### 16.3 证书运维

必须完成一次业务用户 reenroll，验证稳定 userId 下的回执和权限连续性；一次业务 ECert 吊销并将 CRL 更新进相关验证方的 MSP/通道配置；一次 Peer TLS 服务端证书轮换，验证 SAN、信任和重连。

另在 resilience 中逐个轮换 Orderer TLS 证书，事先检查 consenter 中嵌入的客户端/服务端 TLS 证书以及本地证书文件；根据实际证书绑定方式执行配置更新并一次只维护一个节点。不能同时替换三台后再处理信任，造成永久失去多数派。[R15][R25]

不要声称“CA 中执行 revoke 后所有网络服务自动知道”，也不要把 TLS 证书时效与账本历史上 ECert 的验证语义混为一谈。吊销实验报告必须记录生效所需步骤以及变更前后新提案的实际结果。

### 16.4 备份范围

必须备份：CA 根私钥/证书和数据库、节点/用户 MSP 与 TLS 材料、各 Peer 全部账本持久化数据、对应 CouchDB 数据、各 Orderer 账本/WAL/snapshot、已批准链码包与 CCaaS 镜像标识、数据库与业务文件、配置和版本锁。

主线使用冷备份：暂停业务写和消费者，确认在途结果，按受控顺序停止有关服务，再备份成套数据与元数据。恢复必须使用同版本和已记录的节点身份，不能把一份运行中的数据库文件随意 tar 后当成一致备份。

备份清单包含时间、网络 genesisHash、各节点高度、文件校验值、配置版本、镜像 digest、数据库版本和证书有效期。备份含秘密，必须加密或置于受控目录，不能进入 Git。

必须完成一次恢复演练，并证明恢复前已确认的业务记录全部存在。备份仍在同一块宿主机硬盘上时，验收只证明“误删/容器卷丢失演练可恢复”，不能声称已实现异地灾备或抵御整盘损坏。

---

## 17. 性能验证与安全要求

### 17.1 正确性优先的性能指标

所有测量使用真实 Fabric 网络、固定数据集、已锁定版本和记录的宿主机资源。成功率和吞吐量以 `COMMITTED_VALID` 或有效业务回执为准，不以 HTTP 202、背书成功数或 Orderer 接收数冒充。

报告至少包含 offered load、尝试数、有效提交数、无效数、未知结果数、有效提交吞吐量、端到端 p50/p95/p99、各阶段耗时、资源峰值和冲突率。未知结果不能简单归入成功或丢弃。

| 测试           | 固定实验设计                                              | 通过条件                                                     |
| -------------- | --------------------------------------------------------- | ------------------------------------------------------------ |
| 基础业务正确性 | 正常闭环 100 组、拒收退回 20 组、取消 20 组               | 无不变量破坏；每条关键路径有有效提交证据                     |
| 独立键负载     | 预热后，对 1,000 个独立批次执行固定更新，目标输入 5 次/秒 | 无故障条件下至少 99% 在 30s 内取得明确结果；最终无永久未知；不变量 100% 成立 |
| 热点冲突       | 并发度 1/5/20/50，对比同一批次与独立批次                  | 记录冲突和有效提交，不设虚构 TPS 下限                        |
| 索引对照       | 10,000 个批次，固定查询条件和分页                         | explain / 查询证据证明使用预期索引；结果一致，报告前后延迟   |
| 区块参数对照   | 相同输入分别测 1s/20 条与另一个受控配置                   | 解释吞吐、等待和资源变化，不仅展示最高峰值                   |
| 投影延迟       | 无故障、固定输入负载                                      | 目标 p95 可观测延迟不高于 5s；较低资源机器可在报告中记录偏差及原因 |

本项目的硬性安全/正确性不允许降低；资源相关延迟目标如未达到，应记录“性能目标未达标”，不能捏造达标。即使硬件偏弱，也可以先完成语义与故障验收，而不必购买云服务器。

### 17.2 安全边界

假设宿主机与 Docker 管理员可信，组织 registrar 正确签发角色，满足背书策略的组织集合没有全部被攻破。本项目不保证抵御已能替换所有容器、读取所有卷或盗取多数必要签名密钥的宿主机攻击者。

必须防止普通客户端跨组织冒充、绕过链码授权、重放导致重复业务、错误策略降低保护、敏感输入入公共账本、API 路径穿越和不受限输入。CA / 节点管理接口不得映射到 0.0.0.0 的宿主机公开端口。

仓库扫描必须排除私钥、真实 enrollment secret、数据库口令、API token 和含明文秘密的 builder release 产物。`.env.example` 仅含非秘密模板，真实 `.env` 和 `.secrets/` 不提交。Compose secrets / 只读 bind mount 是本地配置约束，不被描述为专用硬件密钥隔离。

---

## 18. 仓库结构与工程规范

### 18.1 目录

```text
supplyledger-lab/
  README.md
  SPEC.md
  Makefile
  versions.lock.yaml
  .env.example
  .gitignore
  compose/
    compose.yaml
    compose.debug.yaml
  network/
    ca/{seller,buyer,carrier,orderer,orderer-admin-tls,audit}/
    peers/{seller,buyer,carrier,audit}/
    orderers/{orderer0,orderer1,orderer2}/
    channel/configtx.yaml
    channel/collections.json
    policies/
  docker/
    tools/Dockerfile
    peer/Dockerfile
    chaincode/Dockerfile
    app/Dockerfile
  builders/supplyledger-ccaas/bin/{detect,build,release}
  chaincode/
    go.mod
    go.sum
    cmd/server/
    internal/{contract,domain,auth,ledger,codec,events}/
    META-INF/statedb/couchdb/indexes/
    testdata/
  app/
    go.mod
    go.sum
    cmd/{supplyctl,api,projector}/
    internal/{gateway,identity,commands,httpapi,projection}/
    migrations/
  api/openapi.yaml
  scripts/{pki,channel,chaincode,network,backup,restore}/
  tests/{unit,integration,e2e,privacy,concurrency,fault,performance}/
  docs/
    architecture.md
    adr/
    manual-bootstrap.md
    transaction-trace.md
    runbooks/
    capability-map.md
  evidence/                 # 仅提交脱敏报告；大文件可单独受控存放
  artifacts/                # 生成的公共区块、配置与发布清单；按规则筛选提交
  .secrets/                 # 不入 Git
  .runtime/                 # 节点本地连接文件、builder 秘密产物；不入 Git
  backups/                  # 不入 Git
```

Go 使用两个模块，chaincode 和 app 分别锁定依赖；共享的规范编码/协议类型可放入独立小模块或以受控方式复用，必须有双方共同运行的 golden tests，避免客户端与链码计算出不同摘要。

### 18.2 工程规范

`go test ./...`、`go vet ./...`、格式检查、Go race 检查（支持的本地架构下）、静态安全扫描和依赖漏洞检查必须有明确运行入口。domain / auth / codec 的语句覆盖率目标至少 85%，同时必须覆盖每个状态转换和反向权限分支；不能仅用总体覆盖率替代关键业务测试。

单元测试可使用自定义小接口 fake 或与当前模块匹配的 mock。不得为了找到旧 shimtest 示例而把整个项目降回旧 protobuf/shim API。真实 endorsement、MSP、PDC、MVCC、TLS 和配置治理只在真实网络测试中验收，mock 测试不充当其证明。

### 18.3 自动化入口

必须提供可发现的命令：`make doctor`、`make pki`、`make network-up`、`make channel-create`、`make chaincode-deploy`、`make app-up`、`make verify`、`make test-e2e`、`make test-fault`、`make backup`、`make restore`、`make stop` 和受保护的 `make reset`。

首次手工完成前，不实现把全部阶段隐藏起来的单一 up 脚本。后续可以提供一键重建，但每个阶段仍可独立执行、重复检查和定位失败。幂等脚本先查询现有身份、通道、包或定义再决定动作，不把“already exists”以外的真实错误当作成功。

### 18.4 必须完成的 ADR

ADR-001：为什么单通道 + PDC；ADR-002：为什么使用 CCaaS、自建 builder 与无 socket；ADR-003：业务批准与 SBE 的边界；ADR-004：本地身份托管与宿主机信任假设；ADR-005：幂等与未知结果处理；ADR-006：投影一致性与重放；ADR-007：证书及节点存储生命周期；ADR-008：链码 schema 升级；ADR-009：审计组织的可见性、只读与治理门槛；ADR-010：实际资源预算与性能取舍。

---

## 19. 里程碑与交付清单

每个里程碑均需提交代码、自动化测试和脱敏证据，再进入下一阶段。可以在早期逐步增加链码函数；只要更新已提交的链码定义，就必须记录新的 sequence，而不能反复删除网络来保持 sequence=1。

| 里程碑             | 本阶段实现范围                                               | 必须交付                                                     | 阶段出口                                                     |
| ------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| M0：空仓库与工具链 | 空目录初始化；自建 tools 镜像；检查宿主机、架构、Go、Compose 和镜像 | versions.lock.yaml、doctor、依赖锁、环境报告、初始 ADR       | 不依赖 samples；工具版本可核对；Go 两模块能构建；Compose 校验通过 |
| M1：身份与信任     | 分组织建立 Enrollment / TLS CA；专用 Orderer 管理客户端 TLS CA；签发 admin、节点、用户 | CA YAML、证书清单、正确的本地/通道 MSP、手工 register/enroll 记录 | 证书用途和 SAN 正确；私钥未进入公共 MSP 或 Git；能解释每张证书的信任方 |
| M2：从零组网       | 三个 Raft Orderer、三个组织 Peer/CouchDB；应用通道与锚节点   | 自写配置/Compose、创世区块、osnadmin/peer join 记录、配置解码报告 | 三组织账本达到同一高度时区块哈希一致；停一台排序节点仍可推进测试配置交易 |
| M3：第一份链码     | 自建 CCaaS image/builder/package；Go 合约先只实现 CreateBatch/GetBatch；Go CLI | builder 三阶段产物说明、首次安装/批准/提交记录、交易解码报告 | 两组织背书、有效提交、世界状态/历史可查询；无 Docker socket  |
| M4：业务主线与策略 | 正常交接、取消、拒收退回、冻结召回；基本 PDC/摘要使提案可运行，角色授权与 SBE | 完整状态转换测试、每函数读写集/策略表、业务脚本              | INV-01–15 中与该阶段相关的不变量成立；缺少客户端业务批准不能推进 |
| M5：隐私与一致性   | 完整隐私边界/规范哈希验证、全部幂等约束、确定性和并发实验    | 编码 golden vectors、隐私报告、双交易屏障测试、幂等报告      | 不泄密；条款一致；可稳定观察 VALID 与 MVCC 冲突；重复请求不重复业务 |
| M6：应用闭环       | 三组织 API、请求日志、异步确认、区块投影、附件               | OpenAPI、CLI 使用说明、数据库迁移、故障重放测试              | 请求超时可收敛；投影可断点恢复和从头重建；业务写不依赖修改 SQL |
| M7：1.0 基线冻结   | 完整业务回归与规范一致性审查                                 | 1.0.0 镜像/包/sequence=S 发布清单、测试报告、完整手工重建文档 | 1.0 全部接口和主要语义验收通过；至少 100 笔有效业务交易保留  |
| M8：维护与新组织   | 在原网络升级 1.1.0、sequence=S+1；加入 AuditMSP              | 升级前后证据、schema 兼容测试、配置差异与签名、审计只读测试  | 创世哈希不变；旧数据可读；审计有公共历史、无价格、无业务写权限 |
| M9：故障与毕业验收 | resilience、证书轮换/吊销、冷备份恢复、性能对照              | 故障报告、恢复清单、性能原始数据、能力答辩、最终 README      | 第 20–21 章要求闭环；未达性能目标明确标注；不冒充生产 HA     |

M3 的第一笔学习交易可以只有创建与读取；M4/M5 逐步加入复杂功能并走真实生命周期。M7 的 S 是发布清单中的实际 sequence，不强制为 1。临时实验可使用独立的 `lab-*` 网络/卷，但升级、新组织与最终恢复证据必须来自保留数据的正式验收网络。

### 19.1 每个里程碑的证据封套

每份报告必须包含：测试编号、规格章节、源码 commit、版本锁摘要、Compose 档位、网络 genesisHash、准备数据、实际命令、预期结果、实际结果、通过/失败判定，以及相关 txId / 区块高度 / 验证码。

对不进入账本的错误，保留失败阶段和脱敏日志即可，不伪造 txId 或区块号。故障实验记录注入与恢复操作。性能记录宿主机与容器资源、输入负载和原始结果。截图只能辅助，不替代可解析日志、区块或自动化断言。

### 19.2 第一项实际开发任务

先创建仓库、versions.lock.yaml 的结构和自建 tools Dockerfile，验证 Fabric/CA CLI、Go 和 Compose 的实际版本。随后只启动 Seller 的两个 CA，手工完成一个 operator 身份的注册与签发，检查 ECert 属性、私钥、根证书和 NodeOUs。

在你能解释这一组文件之前，不编写“一键启动整个网络”的脚本，也不开始做前端。

---

## 20. 验收测试矩阵

以下测试都是主线必须实施的测试；某些性能项的数值是目标而非对任意硬件的保证，适用第 17 章的偏差报告规则。测试网络必须能通过受控 fixture 建立前置状态，fixture 也应通过正式业务交易造数，不能直接写 CouchDB。

### 20.1 组网、身份与生命周期

| ID       | 场景与操作                                         | 明确预期                                                     |
| -------- | -------------------------------------------------- | ------------------------------------------------------------ |
| T-NET-01 | 在新目录/新卷中，按自己的手工文档重建              | 不拉取/调用 samples；工具、配置和身份来源可追踪；完成首笔有效业务交易 |
| T-NET-02 | 检查 Compose、Docker inspect 和仓库                | 无 docker.sock；无私钥入 Git；Peer/CA/DB 管理端口不暴露公网；每 Peer 有独立状态卷 |
| T-NET-03 | 解码通道创世和当前配置                             | 初始三业务 MSP、OrdererMSP、3 个 Raft consenter；capability/ACL/policy/mod_policy 与规格一致 |
| T-NET-04 | 逐台通过 osnadmin 加入应用通道并查询状态           | 无 system channel；每台最终 active；管理 API 强制 mTLS；无有效管理证书请求失败 |
| T-NET-05 | 使用有效链但错误主机名的 TLS 证书访问节点          | TLS 验证失败；修复 SAN/连接名后通过；不能使用跳过验证作为“修复” |
| T-ID-01  | 正常 operator/quality/auditor 证书身份检查         | MSP、稳定 userId、role 与签发记录一致；不是从请求 JSON 推断身份 |
| T-ID-02  | 无属性 client、admin、非通道组织 client 调用写函数 | 在真实认证/授权边界被拒绝；无有效业务变化；记录具体拒绝阶段  |
| T-ID-03  | 用户在 JSON 中伪造角色、MSP、owner、actor          | 严格字段验证或链码身份校验拒绝；不能凭参数提权               |
| T-ID-04  | API token 绑定 Seller 用户，却指定 Buyer 钱包/用户 | API 拒绝或根本不提供该参数；容器无 Buyer 私钥挂载            |
| T-LC-01  | 独立构建相同发布的链码包两次                       | 包确定性规则下字节/包 ID 一致；清单对应实际安装包和镜像摘要  |
| T-LC-02  | 使用错误 CCID、错误连接 TLS 根或未映射 artifactId  | 链码执行失败且日志可定位；不自动退回 Docker 启动路径         |
| T-LC-03  | 故意只批准一份不足法定门槛的定义                   | readiness 显示缺失；不能成功提交合法新定义；补足后正常提交   |
| T-LC-04  | 对比 queryinstalled/queryapproved/querycommitted   | 明确区分本地包、组织批准和通道定义；三类信息与发布清单相符   |

### 20.2 业务、权限与状态机

| ID       | 场景与操作                                                | 明确预期                                                     |
| -------- | --------------------------------------------------------- | ------------------------------------------------------------ |
| T-BIZ-01 | 完整正常交接                                              | 只有 AcceptBatch 有效提交时 owner 变 Buyer；所有阶段状态和 actor 正确 |
| T-BIZ-02 | 创建重复 batchId、第二笔活动提案                          | 明确拒绝；既有对象/索引/版本不变                             |
| T-BIZ-03 | Peer 都在线且可背书，但未由 Buyer 执行 ConfirmTrade       | 无法发货/接货；背书不替代业务批准                            |
| T-BIZ-04 | Carrier 在无 Seller AuthorizeDispatch 时接货              | E_INVALID_STATE 或明确授权错误；custodian 不变               |
| T-BIZ-05 | Carrier ReportDelivery 后读取 Batch                       | custodian 仍 Carrier；Buyer AcknowledgeDelivery 后才是 Buyer |
| T-BIZ-06 | Buyer operator 代替 quality 验收；Carrier 代替 Buyer 收货 | E_FORBIDDEN；无状态变化                                      |
| T-BIZ-07 | PROPOSED 阶段双方分别测试单方取消                         | 对应提案 CANCELLED，Batch READY，activeTradeId 清空；旧提案和条款可审计 |
| T-BIZ-08 | 已确认提案发起取消，同组织第二用户确认                    | 不构成双方同意；另一组织 operator 确认才终结                 |
| T-BIZ-09 | 待取消时发运/接货；随后撤回取消再发运                     | 前者拒绝；合法撤回后重新按正常前置条件执行；旧 Approval 保留 |
| T-BIZ-10 | 接货后尝试普通取消                                        | 拒绝；不得把 custody 直接改回 Seller                         |
| T-BIZ-11 | 完整拒收退回，覆盖各次授权、报告和实物确认                | owner 始终 Seller；custodian 按 Buyer→Carrier→Seller 变化；最终 RETURNED |
| T-BIZ-12 | 重复验收、先接受再拒收、已拒收后再接受                    | 不允许产生第二个结论或覆盖原 Inspection；无所有权反复变化    |
| T-BIZ-13 | 冻结后尝试发运、接货和接受，同时记录真实交付              | 前三类受阻；符合阶段的事实记录仍可有效提交                   |
| T-BIZ-14 | 同组织解冻、旧 freezeRevision 解冻、合法另一方解冻        | 前两类拒绝；最后一类只解除当前冻结，不清除 recalled          |
| T-BIZ-15 | Seller quality 召回已接受批次，随后尝试撤销召回           | 标记可记录；owner 不变；无撤销接口；拒绝重复覆盖原因         |
| T-BIZ-16 | 对 RETURNED/ACCEPTED 批次再售，或要求部分收货             | 1.0 明确拒绝；不是通过修改 quantity 绕过范围                 |
| T-BIZ-17 | 非法枚举、溢出/负金额、重复 JSON 字段、未知字段、超限正文 | 严格拒绝，公共错误无私密载荷；不写部分状态                   |

### 20.3 背书、私有数据与并发

| ID       | 场景与操作                                              | 明确预期                                                     |
| -------- | ------------------------------------------------------- | ------------------------------------------------------------ |
| T-END-01 | 手工准备缺 Seller 或 Buyer 背书的完整交易               | 如提交成功入块，则验证为背书策略不满足、状态不更新；不使用会自动补足背书的 Gateway 调用充当该实验 |
| T-END-02 | ConfirmTrade 后，手工准备缺 Carrier 的运输更新          | P_SBC 验证失败；Batch/Trade/Shipment 都不部分更新            |
| T-END-03 | 观察首次设置/后续变更/恢复 Batch SBE                    | 当前交易依据旧策略验证；新策略约束后续交易；新 Receipt/索引默认策略也被计算 |
| T-END-04 | 独立停止必需组织唯一 Peer，再尝试正常 Gateway 写        | 在背书阶段不能满足要求；可以没有上链交易，不能伪称必然出现区块无效码 |
| T-PVT-01 | Seller 提案、Buyer 校验，公开 hash 与规范字节核对       | 双方明文一致；GetPrivateDataHash 与规范私有字节 SHA-256 相等 |
| T-PVT-02 | 修改金额、salt、合同摘要或 expectedAgreementHash 后确认 | 摘要/提案一致性校验失败；原 Trade 不被更新                   |
| T-PVT-03 | Carrier/Audit 查询条款，同时读取公开哈希                | 明文读取失败；哈希可见不算泄露；无明文出现在错误中           |
| T-PVT-04 | 全路径植入敏感样本并扫描账本、区块、日志、事件、投影    | Carrier/Orderer/Audit 与公共数据面不存在私有原值、完整条款或其可逆编码；报告扫描边界 |
| T-PVT-05 | requiredPeerCount 无可用接收者的受控私有写实验          | 记录实际分发/背书失败；恢复合格 Peer 后通过；不把 peer count 当组织数 |
| T-PVT-06 | 正常完成需要 Carrier 背书的所有后续业务                 | Carrier 可执行公共逻辑，不因读取无资格私有集合而失败         |
| T-CON-01 | 两个独立 requestId 的互斥更新先全部背书，再依次提交     | 固定同一读取版本下一个 VALID，另一个 MVCC_READ_CONFLICT；无效写不进世界状态 |
| T-CON-02 | 同一用户、requestId、语义请求在成功后重复调用           | 返回原回执；同一业务状态只变更一次；无重复领域事件           |
| T-CON-03 | 同 requestId 修改业务内容后调用                         | E_DUPLICATE_REQUEST_MISMATCH；不把不同意图当作重试           |
| T-CON-04 | 同一 requestId 并发首次执行                             | 回执键读版本参与冲突控制；最终只有一次业务结果；其他尝试收敛到原回执 |
| T-CON-05 | MVCC 失败后刷新 expectedRevisions，保持相同语义重试     | 使用新 txId、同 requestId；重新检查业务条件；不绕过状态机或换一份私有条款 |
| T-CON-06 | 组织用户换证，仍用原稳定 userId 查询或重放命令          | 权限重新验证，原幂等键仍有效；不依赖证书 DER 恒定不变        |
| T-CON-07 | 对同一输入在多个 Peer 模拟并检查结果                    | 确定性结果一致；无本机时间/随机数/外部 API/不稳定遍历产生差异 |
| T-CON-08 | 根据富查询列表尝试构造批量写入口                        | 系统无该危险通用接口；正式写函数只对明确读取的键进行更新     |

### 20.4 应用、投影、升级与审计

| ID       | 场景与操作                                                   | 明确预期                                                     |
| -------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| T-APP-01 | Submit 后切断确认响应，再恢复连接                            | PENDING_UNKNOWN；通过 txId/回执核对；最终仅一次业务变化      |
| T-APP-02 | 业务请求持久化后/API 重启前后注入崩溃                        | 请求日志保留；已知 txId 可恢复查询；未确认尝试不被静默忘记   |
| T-APP-03 | 查询投影落后于账本                                           | 返回来源和进度；不把旧值当最新强一致结果                     |
| T-APP-04 | 在无并发写的固定数据集对比不同页、复合键/JSON 索引、非法过滤参数 | 无故意分页边界重复/遗漏；非法任意 selector 拒绝；查询结果/索引可核查 |
| T-APP-05 | 附件路径穿越、超大文件、内容类型伪装、摘要不符               | 拒绝危险输入；更换文件字节后摘要校验失败；无 token 或绝对私有路径入链 |
| T-EVT-01 | 一个业务交易修改多对象                                       | 仅一个聚合领域事件，包含完整公共 after-images；不靠重查最新状态还原旧事件 |
| T-EVT-02 | 含无效交易、配置交易和无事件交易的区块                       | 无效业务不投影；其他交易不阻断区块 checkpoint 前进           |
| T-EVT-03 | 重读区块、每个数据库事务边界强杀投影器                       | 不丢事件、不重复累计；最终投影摘要等于无故障对照             |
| T-EVT-04 | 清空投影表，从区块 0 重放到固定高度                          | 公共领域投影摘要一致；不删除钱包、token、业务请求日志        |
| T-EVT-05 | 同名通道但不同 genesis，或启动第二个投影写者                 | 前者拒绝混用旧数据；后者不能抢占同一 checkpoint 并造成重复写 |
| T-UPG-01 | M7 原网络从 sequence S 升级 S+1                              | genesis 不变，定义/代码/包映射正确，旧 schema 可读，新功能受权限和状态限制 |
| T-UPG-02 | 尝试降低 sequence 或直接改 DB 修复升级                       | 治理/流程拒绝；修复使用更高 sequence 与明确数据兼容方案      |
| T-AUD-01 | 后加入 Audit 并查询加入前公共交易                            | 能取得保留的公共历史；不声称只看加入后的数据                 |
| T-AUD-02 | Audit auditor 提案查询、业务写、价格查询                     | 公共 Evaluate 成功；业务写和私有明文查询失败；不是全部提案都被 ACL 禁掉 |
| T-AUD-03 | Audit admin 批准当前本地定义，再尝试业务更新                 | 本组织生命周期操作可行；业务写仍因无角色拒绝                 |
| T-AUD-04 | 对照加入前后关键治理策略                                     | 创始组织门槛不变；Audit 不加入 P_SB/P_SBC/PDC；所有 mod_policy 经检查 |

### 20.5 故障、证书、恢复与性能

| ID        | 场景与操作                                 | 明确预期                                                     |
| --------- | ------------------------------------------ | ------------------------------------------------------------ |
| T-OPS-01  | 分别停一个 Raft 节点和当前 leader          | 达到稳定多数派后恢复推进；已确认交易不丢失；记录切换时延     |
| T-OPS-02  | 停两个 Raft 节点                           | 无新排序进展；已有 Peer 账本查询仍可用；恢复多数派后核对待定请求 |
| T-OPS-03  | resilience 停 Seller peer0+cc0             | 应用重连 peer1；所需组织背书仍可满足；备用 Peer 私有数据需已可用 |
| T-OPS-04  | 单独停 CCaaS 或 CouchDB                    | 识别故障组件；恢复后 Peer 追平；不把所有故障解释为共识问题   |
| T-OPS-05  | Peer TLS 轮换、业务 ECert 续期             | 信任/SAN 正确、可重连；稳定 userId 与权限连续，旧凭证处置有记录 |
| T-OPS-06  | 吊销 ECert 并发布相关 CRL/MSP 变更         | 记录发布前后差异；新提案不再被接受；不删除历史交易           |
| T-OPS-07  | 逐个轮换 Orderer TLS 及相应 consenter 绑定 | 多数派持续可恢复；通道配置与本地证书一致；没有三节点同时失联 |
| T-OPS-08  | 冷备份，删除指定测试节点数据卷，再恢复     | 恢复后 identity/genesis/区块/状态匹配；不删除其他节点来掩盖问题 |
| T-OPS-09  | 合格 Peer 私有数据缺失/离线后的恢复实验    | 分别证明公共区块和私有明文结果；无幸存副本时明确报告不可由哈希重建 |
| T-PERF-01 | 100 个正常闭环、20 拒收退回、20 取消       | 核对全部 INV；报告有效提交而非 API 接收量                    |
| T-PERF-02 | 独立键/热点键/索引/区块参数对照            | 保留数据与资源条件；延迟、有效 TPS、冲突和未知数分开统计     |
| T-SEC-01  | 全仓库、构建上下文、镜像层、日志脱敏审查   | 无私钥/token/enrollment secret 入发布或版本库；问题修复后重跑扫描 |

### 20.6 结果判定规则

每个测试只有 PASS、FAIL、NOT RUN 三种基础结果，不以“应该可以”标为通过。性能目标可另加 TARGET MET / TARGET NOT MET，但不能覆盖功能正确性失败。无法在本机运行 resilience 时可先完成 dev 阶段，但最终报告必须把相应恢复测试标为 NOT RUN，不宣称已经完成全部主线。

缺少背书、业务前置条件不满足、网络不可达、MVCC 无效和确认未知是不同结果。测试必须在各自真实阶段观测，不能为得到期望截图而用应用模拟错误替代 Fabric 行为。

---

## 21. 最终完成定义与能力答辩

### 21.1 Definition of Done

核心完成标准为：从空目录按自己的文档重建网络；完整业务、权限、隐私、幂等、投影测试通过；在原网络完成一次升级和一次组织接入；完成规定的证书与恢复实验；没有未说明的安全/数据一致性缺陷；代码、配置、说明与实际运行一致。

交付包必须包含：源码及依赖锁、配置和 Dockerfile、自建 builder、Go CLI/API/投影器、OpenAPI、自动化测试、手工组网记录、架构/ADR/运行手册、版本化发布清单、故障/隐私/性能报告。真实秘密另行受控存放，不包含在可公开交付包中。

README 第一屏必须说明怎么检查环境、启动哪个阶段、如何验证、如何停止，以及 reset 会删除什么。危险命令必须要求显式确认目标网络/卷，并默认不删除备份。文档中的命令必须在干净环境验证，示意变量与真实可执行值明确区分。

### 21.2 必须能独立解释的问题

| 能力面   | 答辩问题与所需证据                                           |
| -------- | ------------------------------------------------------------ |
| 身份     | ECert、TLS 证书、MSP、CA registrar、org admin 分别被谁验证？用户换证后为什么还能识别同一请求？ |
| 交易     | 找一笔 tx，说明 proposal、模拟读写集、endorsement、排序、validation、commit；另一笔无效交易为什么还在区块里？ |
| 业务同意 | Buyer Peer 背书与 Buyer 用户同意有什么区别？哪个对象证明用户同意了哪一份内容？ |
| 策略     | 一笔交易同时写 Batch、Shipment、索引和回执，如何推导最少背书？首次设置 SBE 为什么不是立即按新策略验证？ |
| 隐私     | 价格经过哪些进程？谁持有明文？为什么 transient 不能传给不可信 Gateway？只有哈希为什么无法恢复原条款？ |
| 并发     | 业务 revision 和 Fabric MVCC 版本有什么区别？两次请求先背书后提交为什么能稳定制造冲突？ |
| 正确性   | 交易超时后如何区分失败、无效、未知和最终成功？为什么重试必须保留 requestId 却可能更换 txId？ |
| 状态     | owner 与 custodian 为什么不能是一个字段？拒收/召回为什么不能简单“回滚区块”？ |
| 查询     | CouchDB 索引解决什么，不解决什么？为什么富查询列表不能直接当作安全批量写集合？ |
| 事件     | 为什么只写 ID 再查询最新状态不能精确重放历史？数据库提交与 checkpoint 如何保证断线恢复？ |
| 治理     | version、sequence、packageId、image digest、schemaVersion 各代表什么？Audit 加入后哪些权限不能默认给它？ |
| 运维     | 停一个/两个排序节点、停必需组织唯一 Peer、停 CCaaS，各自失败在哪？冷恢复时哪些数据不能漏？ |
| 源码     | 能从本项目一次调用定位 Gateway/shim/Peer 处理路径，找到错误产生处，而不是只搜索错误提示后盲改配置 |

回答必须结合自己的配置、交易、日志或代码，不以背诵概念代替。无需记住所有 CLI 参数，但应该能查官方契约、识别错误配置，并预测修改的影响。

### 21.3 未见过的需求变更题

在不删除已有账本的前提下，增加“高价值批次交接必须由审计人员批准，但审计组织不能读取价格”的规则。先写威胁模型、数据分类、批准结构与背书设计，再实现最小实验。

特别检查：不能为了判断是否高价值而让 Audit 读取它无权持有的私有数据；也不能只相信卖方传来的未受约束布尔值。你可以调整参与方证明/确认流程与公开分类，但必须说明信任由谁承担、哪些信息会因此公开。此题不预设唯一方案，评价依据是正确性、可验证性和取舍说明。

### 21.4 达成后的能力表述

当所有硬性主线完成、资源相关偏差如实记录，并且你能够解释和修改上述设计时，可以说： **“我能够独立设计、开发、部署和排查一个本地多组织 Hyperledger Fabric 系统，理解其身份、交易、背书、隐私、治理和恢复机制。”** 

这比“看完了文档”或“做过一个溯源 Demo”更可验证。它仍不等于已经验证多地域生产容灾、HSM 保护或所有共识攻击模型。

---

## 22. 可选进阶实验

以下实验不阻塞 1.0，但可用于从工程熟练走向更深入的机制理解。使用独立网络/数据集，不能污染正式隐私与恢复证据。

| 实验                   | 具体任务                                                     | 认知边界                                                     |
| ---------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| BFT 排序               | 用 4 个独立排序节点建立 SmartBFT 实验，比较 Raft 的故障假设与配置 | 四容器仍同一宿主机；只做停机不等于验证任意恶意行为；遵循实际版本 BFT 配置 [R31] |
| 第二个通道             | 建立不同成员的独立通道，比较 PDC 与通道级账本隔离            | 不假设跨通道读写具有原子事务语义                             |
| 隐式集合与私有数据清理 | 实验 implicit collection、BTL、显式 purge 和历史哈希         | 在可丢弃数据集上明确观察分发、过期、补齐和不可恢复条件 [R19] |
| 查询并发               | 对比明确键读取、范围查询与 CouchDB 富查询的冲突检查          | 用两阶段背书/提交屏障保证可复现，不从一次“没冲突”推断安全 [R20][R21] |
| 世界状态重建           | 在克隆网络上停止 Peer，按正式工具契约重建状态数据库          | 先备份；区分可由区块重建的数据与私有明文，禁止生产目录冒险 [R34] |
| Snapshot 加入          | 新 Peer 通过 ledger snapshot 加入，对比从区块 0 同步         | 明确哪些历史区块/事件并不在 snapshot 节点本地，避免错误全量重放假设 [R28] |
| Fabric 3.1 批量 API    | 实验相应 shim 的批量读写能力，比较延迟与错误传播             | 批量调用不是跨交易原子性，也不自动消除 MVCC；按固定依赖真实 API 实现 [R31][R33] |
| 内核路径与贡献         | 追踪成功/失败交易，制作最小复现，补测试或修复小问题          | 不要求凭空修改共识；先证明观察、定位和修复的因果关系         |

---

## 23. 官方依据与版本核对记录

核对日期为  **2026-09-23** 。固定版本发布页与源码文件优先于随时间变化的 `latest` 文档；如果通用文档与 3.1.5 实际配置发生冲突，以固定版本契约为准，并记录差异。以下资料用于核对机制与字段，不授权将 fabric-samples 作为项目实现或启动依赖。

- **[R01] Fabric 3.1.5 发布记录与测试依赖** ：[官方发布页](https://github.com/hyperledger/fabric/releases/tag/v3.1.5)。
- **[R02] Fabric CA 1.5.22 发布记录** ：[官方发布页](https://github.com/hyperledger/fabric-ca/releases/tag/v1.5.22)。
- **[R03] Contract API v2.2.3 精确模块依赖** ：[固定版本 go.mod](https://raw.githubusercontent.com/hyperledger/fabric-contract-api-go/v2.2.3/go.mod)。
- **[R04] Fabric Gateway v1.12.1 精确模块依赖** ：[固定版本 go.mod](https://raw.githubusercontent.com/hyperledger/fabric-gateway/v1.12.1/go.mod)。
- **[R05] Go 发行版本和校验值** ：[Go Downloads](https://go.dev/dl/)。M0 另保存选定 1.26.8 平台的具体校验值。
- **[R06] PostgreSQL 17.10 发布说明** ：[官方说明](https://www.postgresql.org/docs/release/17.10/)。
- **[R07] Fabric 3.1.5 通道配置字段** ：[固定版本 configtx.yaml](https://raw.githubusercontent.com/hyperledger/fabric/v3.1.5/sampleconfig/configtx.yaml)。仅字段核对，不是运行模板。
- **[R08] External builders and launchers** ：[官方文档](https://hyperledger-fabric.readthedocs.io/en/latest/cc_launcher.html)。
- **[R09] Fabric 3.1.5 排序节点配置字段** ：[固定版本 orderer.yaml](https://raw.githubusercontent.com/hyperledger/fabric/v3.1.5/sampleconfig/orderer.yaml)。
- **[R10] Fabric 3.1.5 Peer 配置字段** ：[固定版本 core.yaml](https://raw.githubusercontent.com/hyperledger/fabric/v3.1.5/sampleconfig/core.yaml)。
- **[R11] CA 部署与签发链** ：[CA deployment guide](https://hyperledger-fabric-ca.readthedocs.io/en/latest/deployguide/cadeploy.html)。
- **[R12] 注册和签发身份** ：[Registering and enrolling identities](https://hyperledger-fabric-ca.readthedocs.io/en/latest/deployguide/use_CA.html)。
- **[R13] MSP 信任与组织身份** ：[Membership Service Providers](https://hyperledger-fabric.readthedocs.io/en/latest/msp.html)。
- **[R14] osnadmin channel 命令契约** ：[官方命令文档](https://hyperledger-fabric.readthedocs.io/en/latest/commands/osnadminchannel.html)。
- **[R15] Raft 配置、成员与 TLS** ：[Configuring and operating a Raft ordering service](https://hyperledger-fabric.readthedocs.io/en/latest/raft_configuration.html)。
- **[R16] Chaincode as an external service** ：[官方文档](https://hyperledger-fabric.readthedocs.io/en/latest/cc_service.html)。
- **[R17] Fabric chaincode lifecycle** ：[官方文档](https://hyperledger-fabric.readthedocs.io/en/latest/chaincode_lifecycle.html)。
- **[R18] 链码、集合与状态级背书** ：[Endorsement policies](https://hyperledger-fabric.readthedocs.io/en/latest/endorsement-policies.html)。
- **[R19] 私有数据机制与集合配置** ：[Private data architecture](https://hyperledger-fabric.readthedocs.io/en/latest/private-data-arch.html)。
- **[R20] 读写集、MVCC 与 read-your-writes 限制** ：[Read-Write set semantics](https://hyperledger-fabric.readthedocs.io/en/latest/readwrite.html)。
- **[R21] CouchDB 查询与索引约束** ：[CouchDB as the State Database](https://hyperledger-fabric.readthedocs.io/en/latest/couchdb_as_state_database.html)。
- **[R22] Gateway 的背书规划与提交阶段** ：[Fabric Gateway](https://hyperledger-fabric.readthedocs.io/en/latest/gateway.html)。
- **[R23] Go Gateway 客户端 API** ：[官方模块 API](https://pkg.go.dev/github.com/hyperledger/fabric-gateway/pkg/client)。实际以 [R04] 锁定版本编译结果为准。
- **[R24] Peer 区块与链码事件服务** ：[Peer channel-based event services](https://hyperledger-fabric.readthedocs.io/en/latest/peer_event_services.html)。
- **[R25] CA 属性、reenroll、revoke 与 CRL** ：[Fabric CA User's Guide](https://hyperledger-fabric-ca.readthedocs.io/en/latest/users-guide.html)。
- **[R26] 通道配置更新与新增组织机制** ：[Adding an Org to a Channel](https://hyperledger-fabric.readthedocs.io/en/latest/channel_update_tutorial.html)。只参考配置更新机制，不使用该页面依赖的样例脚本。
- **[R27] 账本与世界状态** ：[Ledger](https://hyperledger-fabric.readthedocs.io/en/latest/ledger/ledger.html)。
- **[R28] 账本 Snapshot** ：[Taking ledger snapshots and using them to join channels](https://hyperledger-fabric.readthedocs.io/en/latest/peer_ledger_snapshot.html)。
- **[R29] Compose profiles** ：[Docker 官方文档](https://docs.docker.com/compose/how-tos/profiles/)。
- **[R30] Compose 启动依赖与健康检查** ：[Control startup and shutdown order](https://docs.docker.com/compose/how-tos/startup-order/)。
- **[R31] Fabric 3.x 功能变化** ：[What's new](https://hyperledger-fabric.readthedocs.io/en/latest/whatsnew.html)。
- **[R32] peer chaincode 原生命令** ：[命令契约](https://hyperledger-fabric.readthedocs.io/en/latest/commands/peerchaincode.html)。
- **[R33] Go shim 接口语义** ：[官方模块 API](https://pkg.go.dev/github.com/hyperledger/fabric-chaincode-go/v2/shim)。实际以 [R03] 锁定的 pseudo-version 为准。
- **[R34] Peer 节点恢复相关命令** ：[peer node 命令](https://hyperledger-fabric.readthedocs.io/en/latest/commands/peernode.html)。
- **[R35] 可用指标字段** ：[Fabric metrics reference](https://hyperledger-fabric.readthedocs.io/en/latest/metrics_reference.html)。部署时仍需核对 3.1.5 实际输出。

**规格交付说明：**  本文提供实施与验收契约；没有在你的硬件上运行上述网络，也未声称其代码、镜像 digest 或测试已由本文自动生成/验证。实施过程中发现实际版本契约冲突，应建立最小复现，更新 ADR 与测试，再修订规格，而不是静默改变核心不变量。
