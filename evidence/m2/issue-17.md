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

## Later read-only block-0 header-hash cross-check

This limited `M2-I17-08` check ran on clean main `47923ccb36c5726e658240a097d6645e81d3d3cc` with unchanged `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`. Compose tier was `bootstrap.yaml` + `ca.yaml` + `network.yaml`, project `supplyledger`; this calculation started no container and sent no network request. Prepared ignored inputs in the main worktree were the original #17 `.runtime/channel/inspect-block.json` (SHA-256 `2e3c9994819ae2f5ec5c6a5741f6bf558d0c364380ffee3cac10930f8f4b4e09`), its unchanged block file (artifact SHA-256 `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a`), and the #18 Seller native post-join `.runtime/m2-issue18-peer-logs/seller-post-join-getinfo.log` (SHA-256 `cb52eb704b05d4b86dd5dde5a1b3911b382f95f388dc6b36ce0ed9cac428874d`). #18 had already fetched block 0 independently from each of three joined Orderers and found their bytes identical to this original file.

Fabric 3.1.5 [`protoutil.BlockHeaderHash`](https://github.com/hyperledger/fabric/blob/v3.1.5/protoutil/blockutils.go#L39-L62) hashes ASN.1 DER of `(block number, previous hash, data hash)`. The following read-only command used that rule for **block 0 only**; `302702010004000420` is the DER prefix for number 0, empty previous hash and a 32-byte data hash. It compared the result with Seller's earlier native `BlockchainInfo` output, rather than treating the SHA-256 of the whole `.block` file as `genesisHash`:

```sh
python3 - <<'PY'
import base64
import hashlib
import json
from pathlib import Path

header = json.loads(Path('.runtime/channel/inspect-block.json').read_text())['header']
assert header['number'] == '0' and header['previous_hash'] == ''
data_hash = base64.b64decode(header['data_hash'], validate=True)
assert len(data_hash) == 32
header_der = bytes.fromhex('302702010004000420') + data_hash
digest = hashlib.sha256(header_der).digest()
line = next(line for line in Path(
    '.runtime/m2-issue18-peer-logs/seller-post-join-getinfo.log'
).read_text().splitlines() if line.startswith('Blockchain info: '))
observed = base64.b64decode(json.loads(line.removeprefix(
    'Blockchain info: '))['currentBlockHash'], validate=True)
print('block0_header_hash_hex=' + digest.hex())
print('matches_seller_getinfo=' + str(digest == observed))
assert digest == observed
PY
```

Expected: the canonical block-header digest of the retained original block 0 equals Seller's live local-ledger `currentBlockHash` while Seller reports height 1. Actual: exit **0**, `block0_header_hash_hex=5c68bf099e95b934b6034a4d7aa8c52442751c30bc8b56fcbbde9b0138e38ba7`, `matches_seller_getinfo=True`; Seller's observed base64 value was `XGi/CZ6VuTS2A0pNeqjFJEJ1HDC8i1b8u96bATjji6c=`. **PASS** for this limited block-0 identity cross-check. This header hash is distinct from the block **file** SHA-256 `b0a5ec…d08a`. Buyer/Carrier Peer block-0 comparisons, current live configuration decoding, full NET-08 and `T-NET-03` remain **NOT RUN**. This calculation submitted no transaction, so it produced no new txId, block height or validation code; Seller's previously observed local height was 1.

## Current-CONFIG audit preparation; live fetch NOT RUN

`M2-I17-09` prepares the later NET-08 / `T-NET-03` check under SPEC.md §§5.4, 19.1, 20.1. Fresh checks ran after the isolated branch fast-forwarded to clean local/remote main `7b5dfac86dcf36aa5b21faaa4d6391365861c0c2` on `darwin/arm64`, Docker `linux/arm64`, with `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b` and Compose project `supplyledger` (`bootstrap.yaml` + `ca.yaml` + `network.yaml`, profiles `bootstrap` + `ca`). Resolve the introducing source commit after independent review with `git log --diff-filter=A -1 --format=%H -- scripts/verify-m2-current-config.py`. Prepared input was only the original ignored decoded #17 block-0 JSON (SHA-256 `2e3c9994819ae2f5ec5c6a5741f6bf558d0c364380ffee3cac10930f8f4b4e09`), its public M1 MSP/consenter pins and temporary synthetic copies. The known canonical block-0 **header** hash is `5c68bf099e95b934b6034a4d7aa8c52442751c30bc8b56fcbbde9b0138e38ba7`; the block-file SHA-256 remains a separate artifact checksum.

After the #18 three-Peer evidence appendix reached clean local/remote main `8ecb5632bfcbaf738d3fb883011fdb6b6eaa905c`, the isolated #17 branch fast-forwarded again. `make verify-m2-initial-block` and `make test-m2-current-config` were repeated against the same retained ignored M1/#17 inputs; independent review then identified five additional malformed-governance/genesis controls, and the final fresh suite returned four initial-block and **20 synthetic** PASS lines. `py_compile` and `git diff --check` also exited `0`. No native fetch was run by this #17 preparation. Separately, #18 had already **PASS** evidence for three local Peer `fetch 0` calls and equal-height canonical header hashes. Its Peer-fetched files were each 27,947 bytes with file SHA-256 `042d7e1c2cf18b83bc792575414ed7ff2b811300c718a9ac00c3320919da7137`, versus original #17's 27,946-byte file SHA-256 `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a`; decoded header/data matched, while metadata slot 2 gained one byte. See the [retained #18 checkpoint](issue-18.md#three-peer-same-height-block-0-checkpoint-net-06). Neither artifact-file hash is the canonical genesis header hash.

| Actual offline command | Expected / actual | Judgment |
| --- | --- | --- |
| Pinned `docker run --rm --pull=never --platform linux/arm64 --network none --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" --entrypoint osnadmin supply-tools:m0-fabric3.1.5-ca1.5.22 channel fetch --help` | Exit `0`; help lists `--blockID <newest\|oldest\|config\|number>` and `-o` exact OSN admin address plus mTLS flags. No channel request sent. | **PASS**, CLI syntax only |
| `make verify-m2-initial-block M1_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime M2_CHANNEL_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime/channel` | Exit `0`, four existing initial-block PASS lines; no regression to the block-0 audit. | **PASS**, offline initial block |
| `make test-m2-current-config M1_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime M2_CHANNEL_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime/channel` | Exit `0`, **20 synthetic decoded-JSON** controls: initial and later CONFIG numbers/sequences plus 2s timeout governance structure accepted; wrong channel/type, node drift/missing input, wrong approved JSON hash, mutated genesis envelope, duplicate JSON key, extra policy, SHA3/width/ChannelRestrictions changes and ACL/`mod_policy`/MSP/consenter drift rejected. The synthetic 2s fixture retains a stale `header.data_hash`; it tests decoded governance structure and is **not** a valid raw Fabric block or integrity PASS. | **PASS**, temporary decoded-structure fixtures only |
| `make verify-m2-current-config` without live input arguments | Exit `2`, prints `NOT RUN` and refuses to audit absent six native fetches/approved baseline. | **NOT RUN**, live data absent |
| `bash -n` on seven [runbook](../../docs/m2-channel-native.md#later-net-08-fetch-current-config-from-each-live-ledger) shell blocks; Python `py_compile`; `git diff --check` | Exits `0`; no runbook fetch was executed. | **PASS**, syntax/diff |

The [runbook](../../docs/m2-channel-native.md#later-net-08-fetch-current-config-from-each-live-ledger) requires each Orderer `osnadmin fetch config` via dedicated admin mTLS and each Peer `peer channel fetch config` **without `-o`** via its own Deliver service, followed by six separate native decodes. The verifier requires an explicitly hashed approved **decoded JSON** baseline, original decoded block-0 SHA and header hash, then compares all six decoded block headers and complete CONFIG data while rechecking M1 trust and governance. An authorized later #19 BatchTimeout change requires a newly reviewed raw block plus decoded baseline and both file digests; six mutually agreeing nodes alone do not authorize drift. This decoded-only comparison does **not** independently recompute raw `BlockDataHash` or verify raw-block-to-JSON provenance. A future live PASS requires six retained native raw fetches, pinned one-to-one decodes, raw/decoded file hashes and independent review as separate gates. It also does not validate a later CONFIG `last_update` signature set or governance authorization; #19 must retain and assess that transaction separately. #18's local Peer block-0 fetches are already recorded above; **six-node current live CONFIG fetch/decode, full NET-08 / `T-NET-03` and live MSP enforcement remain NOT RUN**. This preparation sent no channel transaction, so no new committed txId, block height or validation code exists.
