# M2 issue #17 — first native initial-block generation and static audit

- Issue: https://github.com/yjydist/supplyledger-lab/issues/17 — **OPEN** until current live channel config and full `T-NET-03` are checked.
- Checked: 2026-09-25, `darwin/arm64` host, Docker `linux/arm64`; pinned Fabric `configtxgen`/`configtxlator` v3.1.5 in `supply-tools:m0-fabric3.1.5-ca1.5.22`.
- Test IDs: `M2-I17-01` through `M2-I17-07`; static initial-block portion of `T-NET-03` passed, full `T-NET-03` **NOT RUN**.
- Specification: `SPEC.md` §§3.2, 5.2–5.4 (NET-03, later NET-08), 10.4, 19.1 and 20.1 (`T-NET-03`).
- Source commit: the commit introducing this report; resolve its full SHA after review with `git log --diff-filter=A -1 --format=%H -- evidence/m2/issue-17.md`. The reviewed M2 #15 baseline is `d57d0a05bf334cfaca5d9b44d753b1d069d8d238`.
- Version lock: `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`. Local tools image descriptor was `sha256:6b466c4dbd8aee240cbbc4c95860c4bf0b7a0de83b3edc808bc3dc71b895f8fe|linux/arm64`, matching the lock.
- Compose tier: M2 base `compose/bootstrap.yaml` + `compose/ca.yaml` + `compose/network.yaml` is available from #15, but **no** Peer, Orderer, CouchDB or application service was started by NET-03. Native CLI containers used `--network none`, `--read-only`, `--tmpfs /tmp`, `--pull=never` and narrow mounts; no Compose `up` or channel join was run.
- Network `genesisHash`: **NOT RUN**. The generated block file SHA-256 below is an **artifact-file checksum**, not a Fabric block-header hash or accepted network genesis identity. Candidate block header number is `0`; no node ledger height has been observed. Its generated CONFIG envelope has tx_id `5684029d6ae93fa475d862105c752d0c46e606b879207c25efe29cd436c400f1`, but it was not submitted as a transaction. A committed txId, validation code and live block height are **NOT RUN**.
- Prepared data: four existing ignored public MSPs from M1 #11, each with one pinned Enrollment root, one ordinary TLS root and public NodeOUs; three existing M1 #10 Orderer TLS signcerts. A fresh `make verify-m1 M1_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime` exited 0 on 2026-09-25, matching the committed 41-certificate CSV, 27 local NodeOUs, four public MSPs, five pinned TLS roots and the M1 offline TLS matrix; this re-established the #9/#10/#11/#12 pins for the **current** runtime files. Each public consenter leaf was copied byte-for-byte into this isolated checkout's ignored `.runtime/channel/consenter-certs/`; the three `cmp` checks exited 0. No local MSP, private key, registrar material, admin client certificate or CA database was mounted or copied. The native block, decoded JSON and logs remain under ignored `.runtime/channel/`.

## Actual first native commands

The commands were run individually from `/Users/yjydist/Code/supplyledger-lab-issue-17`, after writing [the production configtx input](../../network/channel/configtx.yaml), confirming the pinned tools descriptor, and running `M1_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime python3 scripts/assemble-msps.py verify` (exit 0). The full `make verify-m1` check above was run afterward to recheck the retained inputs against all M1 pins. The [native runbook](../../docs/m2-channel-native.md) gives the reusable command envelope and exact public-input paths. The first generation used the following **single** `configtxgen` invocation; no wrapper generated or joined a channel.

```sh
docker run --rm --pull=never --platform linux/arm64 --network none --read-only --tmpfs /tmp \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/network/channel,dst=/work/channel,readonly" \
  --mount "type=bind,src=/Users/yjydist/Code/supplyledger-lab/.runtime/public-msps,dst=/work/public-msps,readonly" \
  --mount "type=bind,src=$PWD/.runtime/channel/consenter-certs,dst=/work/orderer-consenter-certs,readonly" \
  --mount "type=bind,src=$PWD/.runtime/channel,dst=/work/artifacts" \
  --entrypoint configtxgen supply-tools:m0-fabric3.1.5-ca1.5.22 \
  -configPath /work/channel -profile SupplyChannel -channelID supplychannel \
  -outputBlock /work/artifacts/supplychannel.block \
  > .runtime/channel/configtxgen-native.log 2>&1
```

It exited 0. The ignored log reported `orderer type: etcdraft`, loaded `/work/channel/configtx.yaml`, then `Creating application channel genesis block` and `Writing genesis block`. It created a 27,946-byte `.runtime/channel/supplychannel.block`. `shasum -a 256` returned **artifact checksum** `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a`; it is not recorded as `genesisHash`. The command was not rerun after this first success, so the candidate block bytes stayed stable for the later native joins.

The pinned native decode and separate pinned native inspection both exited 0:

```sh
docker run --rm --pull=never --platform linux/arm64 --network none --read-only --tmpfs /tmp \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/channel,dst=/work/artifacts" \
  --entrypoint configtxlator supply-tools:m0-fabric3.1.5-ca1.5.22 \
  proto_decode --input /work/artifacts/supplychannel.block --type common.Block \
  --output /work/artifacts/supplychannel.block.json \
  > .runtime/channel/configtxlator-native.log 2>&1

docker run --rm --pull=never --platform linux/arm64 --network none --read-only --tmpfs /tmp \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/channel,dst=/work/artifacts" \
  --entrypoint configtxgen supply-tools:m0-fabric3.1.5-ca1.5.22 \
  -inspectBlock /work/artifacts/supplychannel.block \
  > .runtime/channel/inspect-block.json 2> .runtime/channel/inspect-block-native.log
```

The inspector log reported `Parsing genesis block`. Both decoded JSON files were 69,885 bytes, and `cmp .runtime/channel/supplychannel.block.json .runtime/channel/inspect-block.json` exited 0. The full JSON embeds public certificate bytes and stays ignored. The [read-only initial-block audit](../../scripts/verify-m2-initial-block.py) then evaluated the inspected JSON:

```sh
make verify-m2-initial-block M1_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime
```

It exited 0 with four scoped PASS lines for the initial block, four public MSPs/anchors/endpoints, three byte-pinned Raft certificate pairs and batch limits, and capability/governance/ACL/`mod_policy`. Its final line was `NOT RUN: current channel config, live MSP enforcement and full T-NET-03 await #18`.

## Decoded configuration judgment

| Test | Expected | Actual | Judgment |
| --- | --- | --- | --- |
| `M2-I17-01` application block identity | `supplychannel` CONFIG block 0 with only Application and Orderer groups; no system-channel consortium | Decoded header number `0`, previous hash empty, one CONFIG envelope for `supplychannel`; root groups exactly `Application` and `Orderer`; no Consortium value/group | **PASS**, offline candidate block |
| `M2-I17-02` public organizations and discovery | SellerMSP, BuyerMSP, CarrierMSP plus OrdererMSP from M1 public MSPs; each founder anchor `peer0.<org>.supply.test:7051`; three Orderer endpoints on 7050 | Fresh `make verify-m1` matched current public MSPs and certificates to the committed M1 pins. Four decoded MSP IDs, Enrollment/TLS roots and NodeOUs byte-matched those current public files; no signing identity/admin leaf/intermediate/CRL embedded; three exact anchors and `orderer0/1/2.orderer.supply.test:7050` endpoints | **PASS**, decoded input |
| `M2-I17-03` Raft and batching | etcdraft with three exact consenter TLS leaves, one per Orderer, and learning batch parameters | `ConsensusType=etcdraft`, normal state; all six embedded client/server PEM fields byte-matched the three original M1 Orderer TLS signcerts and their #10 DER fingerprints/SAN/dual TLS EKU; batch timeout `1s`, max `20`, preferred `524288` bytes, absolute `10485760` bytes. Raft options: `500ms`, election `10`, heartbeat `1`, max inflight `5`, snapshot `16777216` bytes. | **PASS**, decoded input; live Raft **NOT RUN** |
| `M2-I17-04` capability and ACL | Channel V3_0, Orderer V2_0, Application V2_5; `peer/Propose` maps to Application/Readers | Each decoded capability set contained exactly the required version; decoded ACL reference was `/Channel/Application/Readers` | **PASS**, decoded input |
| `M2-I17-05` founder governance | Per-org Admins own admin; Application/Admins any two founder admins; LifecycleEndorsement any two founder peers; Application/Endorsement Seller+Buyer peers; Orderer/Admins Orderer admin; Channel/Admins Orderer admin **and** any two founder admins | Audit evaluated each encoded Signature policy for every subset of its actual role principals; each truth table matched the stated requirement. Application/Readers/Writers, Channel/Readers/Writers and Orderer/Readers/Writers were `ImplicitMeta ANY` of their named org policies; Orderer/BlockValidation was `ANY Writers`. Every decoded group, value and policy had `mod_policy=Admins`. | **PASS**, decoded input |
| `M2-I17-06` current config/full `T-NET-03` | Decode **current** channel config after native joins; compare MSPs, consenters, capability, ACL, policies and `mod_policy` with this block; record accepted block-header identity | No Orderer or Peer joined `supplychannel`; no current config or live MSP decision exists. M2 #16/#18 must complete NET-04–07 before #17's NET-08 live comparison. | **NOT RUN** |
| `M2-I17-07` tracked material and secret boundary | Keep block/JSON/logs and M1 cert inputs ignored; commit only authored config, verifier, runbook and sanitized evidence | `git check-ignore` matched `.runtime/channel/supplychannel.block` and staged consenter PEMs; no key or password was mounted into the native CLI containers. `make verify-m0` exited 0, including the tracked secret path/key-marker scan, fixed CLI binary SHA-256 checks and tools build-context allowlist. Targeted changed-file secret marker scan found no values; `git diff --check` and Python syntax check exited 0. | **PASS**, candidate source and ignored-artifact boundary |

The first local version of the author-written auditor compared the #10 colon-delimited DER fingerprint without normalizing the colons, so that local audit exited 1 at `orderer0: M1 certificate pin, SAN or TLS use differs`. The pinned native generation/decode had already passed. After normalizing the representation, the auditor passed and the original block was not regenerated or modified. This report keeps the diagnostic failure distinct from the final static result.

The [first-run sequence](../../docs/m2-channel-native.md) remains NET-03 → #16 channel-less Orderer startup/admin checks (NET-04) → #18 individual Orderer joins (NET-05) → #16 Peer/CouchDB startup (NET-06) → #18 Peer joins/anchor checks (NET-07) → #17 current-config decode (NET-08). The present static block audit cannot stand in for a live current-channel configuration, consensus, channel governance signature or full `T-NET-03` result. No validation code is claimed.
