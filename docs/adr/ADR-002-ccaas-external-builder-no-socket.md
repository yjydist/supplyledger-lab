# ADR-002：自建 CCaaS、external builder 与无 Docker socket 的 Peer

- 状态：接受为实施基线；运行验收待 M3
- 关联：`SPEC.md` §§1.2、3.1、5.1、5.5–5.6、19；CON-02、CON-08；T-NET-02、T-LC-01–04

## 背景与约束

链码必须以 Go 实现，由每个 Peer 对应的本组织独立 CCaaS 服务运行。Peer 不得挂载 Docker socket。首次链码安装、批准和提交要逐条执行原生命令并保留脱敏记录，不能用一键脚本掩盖包、组织批准与通道定义的区别。

## 决策

基于固定 digest 的官方 Fabric Peer 镜像添加本仓库编写的 external builder，并在镜像中显式提供 builder 实际使用的 shell 和 JSON 工具；不假设基础镜像已有这些命令。Peer 配置不提供 Docker 启动端点，也不挂载 Docker socket，builder 失配必须失败并可定位。

确定性链码包包含 `metadata.json`、无秘密的 `service.json` 和所需索引。`service.json` 以 `artifactId` 关联源码 commit 与 CCaaS 镜像 digest，不含 TLS 私钥。自建 `detect` 验证包类型，`build` 检查无秘密内容，`release` 从该 Peer 的本地映射与受控 TLS 材料生成连接 JSON 和索引；不使用 `bin/run` 代替外部服务。生成的连接文件若含客户端私钥，仅 Peer 进程可读，不提交到 Git 或共享包。

CCaaS 显式使用 `shim.ChaincodeServer`，其 CCID 等于该 Peer 的实际 package ID。Peer 与本组织 CCaaS 双向 TLS，验证服务端 SAN 和正确根证书，每个 Peer 使用自己的客户端 TLS 凭证。镜像、包、package ID、artifactId、实际服务 digest 与链码定义 sequence 分别记录，不混为同一标识。

## 取舍

独立 CCaaS 容器使 Peer 不需要访问宿主 Docker daemon，组织可以分别部署和检查运行服务。代价是必须管理每 Peer 的地址、CCID、TLS 与服务可用性；包已安装或通道定义已提交都不能证明外部服务连接正常。Fabric 生命周期也不能单独证明运行容器的二进制对应声明的源码，必须核对 artifactId 到实际镜像 digest 的映射并做端到端调用。

使用 Peer 内置 Docker 启动路径会减少连接配置，但要求本项目禁止的 Docker socket 权限。包内嵌运行私钥虽省去局部映射，却会把秘密复制到安装包和日志可见的路径，因此不采用。

## 验证与重新评估

M3 在真实 Peer 上检查 builder 三阶段产物与权限、两次打包一致性、安装/批准/提交记录、正确 CCID 和 mTLS 冒烟调用；用错误 CCID、错误根证书和缺失 artifactId 验证失败位置，并以 Compose 与 `docker inspect` 检查无 socket。M0 的 tools 镜像构建不证明这些运行行为。若连接配置无法隔离私钥或镜像映射不可验证，应停止生命周期交付并修正 builder 与发布记录。
