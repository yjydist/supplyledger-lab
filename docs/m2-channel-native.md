# M2 NET-03: native application-channel block generation

This is the first-run record procedure for [issue #17](https://github.com/yjydist/supplyledger-lab/issues/17), `SPEC.md` §§3.2, 5.2–5.4, 10.4 and `T-NET-03`. The production input is [network/channel/configtx.yaml](../network/channel/configtx.yaml), authored for Fabric 3.1.5. It has one `SupplyChannel` application profile, three founder application MSPs, one OrdererMSP and three Raft consenters. There is no `Consortium`, `Consortiums`, system channel profile, or old `peer channel create` step.

Complete the M1 [public MSP verification](m1-msp-assembly.md) before generating the block. Set `M1_RUNTIME_DIR` to the **existing** ignored runtime that holds the four public MSPs and original Orderer TLS signcerts. In the integrated main worktree this is `$PWD/.runtime`; in an isolated checkout it may be the original main worktree's `.runtime`. The input certificate files are public PEMs. Neither `configtxgen` nor `configtxlator` needs a signing key, registrar credential or network connection.

The three Orderer TLS leaves issued in M1 #10 include both serverAuth and clientAuth. Each consenter's `ClientTLSCert` and `ServerTLSCert` therefore points to the **same node's** TLS signcert, and both embedded PEM byte strings must match that node's retained M1 signcert. These are the Raft transport certificates, not the Orderer admin API server leaves or the dedicated admin **client** certificate. The [offline trust matrix](m1-tls-trust.md) checks their SAN and roots; the [initial-block verifier](../scripts/verify-m2-initial-block.py) checks the bytes embedded in the block against the original M1 files and the #10 certificate inventory.

## Prepare public inputs

From the repository root, set an absolute runtime path and stage only three public certs in the ignored output directory. The lines below are separate preparation commands; they do not register, re-enroll, or rewrite an identity.

```sh
M1_RUNTIME_DIR=${M1_RUNTIME_DIR:-$PWD/.runtime}
mkdir -p .runtime/channel/consenter-certs
install -m 0644 "$M1_RUNTIME_DIR/identities/orderer/orderer0-tls/msp/signcerts/cert.pem" .runtime/channel/consenter-certs/orderer0.pem
install -m 0644 "$M1_RUNTIME_DIR/identities/orderer/orderer1-tls/msp/signcerts/cert.pem" .runtime/channel/consenter-certs/orderer1.pem
install -m 0644 "$M1_RUNTIME_DIR/identities/orderer/orderer2-tls/msp/signcerts/cert.pem" .runtime/channel/consenter-certs/orderer2.pem
```

Verify the pinned `supply-tools` image against `versions.lock.yaml` with `make doctor` and the M1 source material with `make verify-m1 M1_RUNTIME_DIR="$M1_RUNTIME_DIR"`. The image contains the measured Fabric `configtxgen` and `configtxlator` 3.1.5 binaries. The commands below use it with no network, a read-only root filesystem, the current host UID/GID, and narrow read-only input mounts. Do not substitute a floating image tag or mount the entire M1 identity tree with private keys.

## Run the native Fabric commands individually

Generate the candidate application-channel initial block. Do this as a single explicit native `configtxgen` call before wrapping channel creation in any script. This produces an ignored artifact and a local ignored log; it does not start or join a node.

```sh
docker run --rm --pull=never --platform linux/arm64 --network none --read-only --tmpfs /tmp \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/network/channel,dst=/work/channel,readonly" \
  --mount "type=bind,src=$M1_RUNTIME_DIR/public-msps,dst=/work/public-msps,readonly" \
  --mount "type=bind,src=$PWD/.runtime/channel/consenter-certs,dst=/work/orderer-consenter-certs,readonly" \
  --mount "type=bind,src=$PWD/.runtime/channel,dst=/work/artifacts" \
  --entrypoint configtxgen supply-tools:m0-fabric3.1.5-ca1.5.22 \
  -configPath /work/channel -profile SupplyChannel -channelID supplychannel \
  -outputBlock /work/artifacts/supplychannel.block \
  > .runtime/channel/configtxgen-native.log 2>&1
```

Run `configtxlator` separately to decode the actual block bytes to JSON. Then run `configtxgen -inspectBlock` separately as an independent native inspection path. The two JSON files should be byte-identical. Keep their full contents under ignored `.runtime/`; they contain public MSP/TLS certificate bytes and do not belong in a compact evidence report.

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

cmp .runtime/channel/supplychannel.block.json .runtime/channel/inspect-block.json
make verify-m2-initial-block M1_RUNTIME_DIR="$M1_RUNTIME_DIR"
```

The verifier asserts the inspected `CONFIG` block is for `supplychannel`, the public MSP roots and NodeOUs match M1 byte-for-byte, the three anchors and Orderer endpoints match the declared DNS, all three Raft consenter client/server PEM bytes match original M1 node leaves, and batch/capability/ACL/policy/`mod_policy` values match `SPEC.md`. It evaluates each Signature policy's encoded threshold over every combination of its listed principals. A **PASS** means this offline initial block is internally consistent. It does not establish that a live Orderer accepted it or that a later current configuration remains identical.

The `sha256sum`/`shasum` of `supplychannel.block` is an **artifact-file checksum**. It is not the Fabric block-header hash used as a channel genesis identity. Do not record that file checksum as `genesisHash`. The initial block is a candidate until the later native Orderer joins and Peer channel joins use the same bytes. M2 [#16](https://github.com/yjydist/supplyledger-lab/issues/16) next starts three channel-less Orderers and checks their admin APIs (NET-04); [#18](https://github.com/yjydist/supplyledger-lab/issues/18) joins them individually (NET-05). #16 then starts Peer/CouchDB (NET-06), #18 handles Peer joins/anchors, and #17 returns to decode the **current** live config and complete `T-NET-03` (NET-08). Keep #17 open and mark those live results **NOT RUN** until observed.
