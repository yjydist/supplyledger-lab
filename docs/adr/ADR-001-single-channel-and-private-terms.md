# ADR-001：单业务通道与 Seller/Buyer 私有条款集合

- 状态：接受为实施基线；运行验收待 M2、M4、M5、M8
- 关联：`SPEC.md` §§3.1–3.2、10–11、19；CON-05、INV-12；T-PVT-01–06、T-AUD-02/04

## 背景与约束

Seller、Buyer、Carrier 要对同一批次的公开状态达成一致；Audit 后续须在保留原账本的通道上读取公开历史。交易金额、salt 和合同信息只允许 Seller、Buyer 的合格路径持有。公开哈希不能替代私有明文的存储或恢复，也不能把公开元数据变成秘密。

## 决策

主业务只使用 `supplychannel`，链码为 `supplycc`。批次、交易状态、物流、批准和审计所需的公共记录在同一通道内按业务交易更新。私有 `TradeTermsV1` 只存于显式 `sellerBuyerTerms` 集合：成员为 SellerMSP、BuyerMSP，`memberOnlyRead=true`、`memberOnlyWrite=true`、`requiredPeerCount=1`、`maxPeerCount=3`、`blockToLive=0`，集合背书同时要求双方 Peer。私有输入仅通过 `transient.trade_terms` 到达双方合格的 Gateway 和背书 Peer；普通参数、公共状态、事件、错误与日志不得含私有原值。

公开交易记录保留经规范编码验证的摘要和必要业务元数据。ConfirmTrade 之后涉及 Carrier 的业务只读公开 `agreementHash` 与状态，不要求 Carrier 读取它无资格持有的私有集合。Audit 加入原通道后只能按身份与 ACL 读取公共数据，不加入私有集合、业务背书策略或创始组织治理门槛。集合的 `requiredPeerCount` 按 Peer 个数而非组织个数解释，私有分发与恢复须单独验证。

## 取舍

单通道让跨 Batch、Trade、Shipment 的公共业务更新处于同一笔 Fabric 交易，也让后加入的 Audit 能从保留的公共区块读取历史。代价是成员能看到交易存在、参与方、时间和公开字段；PDC 只限制私有明文的持有范围，不能隐藏这些元数据，也不能对宿主机 Docker 管理员保密。

另设 Seller/Buyer 专用通道可以扩大通道级隔离，但主流程需跨通道协调公共交易与私有条款，不能假设跨通道写入原子提交。把加密条款放在公共状态也会把密文永久复制给所有成员，并增加密钥分发与轮换责任。本项目不把这两种方案加入 1.0 主线。

## 验证与重新评估

M4/M5 在真实网络上核对集合成员、分发、双方背书、规范摘要和公开面脱敏；对 Carrier、Orderer、Audit、公共区块、CouchDB、事件和日志执行 T-PVT-01–06。M8 在原网络接入 Audit 后核对其公共查询和私有读取拒绝。M0 仅确立设计，尚不能据此声称隐私或背书已通过。若实测显示私有字段泄露、合法交易不能满足分发或背书、或成员范围改变，应先记录失败和影响，再修改设计与 ADR。
