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

The `sha256sum`/`shasum` of `supplychannel.block` is an **artifact-file checksum**. It is not the Fabric block-header hash used as a channel genesis identity. Do not record that file checksum as `genesisHash`. At the first-generation stage, this block was only a candidate. Later native Orderer and Peer joins used that same block identity; the [six-node current-CONFIG checkpoint](../evidence/m2/issue-17.md#six-node-live-current-config-read-only-checkpoint) records the current governance comparison after #16 startup and #18 joins. These stages remain separately evidenced, and a later #19 configuration update requires a new approved current baseline.

## Later NET-08: fetch current CONFIG from each live ledger

This section is the native procedure; [the executed six-node checkpoint](../evidence/m2/issue-17.md#six-node-live-current-config-read-only-checkpoint) records its observed results. The first execution waited for #18's three Peer joins and local ledger checks to pass independent review. Preserve the original #17 block, decoded JSON, three Orderer identities and existing volumes. Use a new ignored 0700 `.runtime/channel/current-config` directory for a fresh checkpoint; set `umask 077`, refuse existing output filenames, and retain one 0600 command/log/exit set per invocation. Fetches and decoding are read-only for the channel but create local ignored output files. Run each native command individually, inspect the response, and stop on any failure.

The pinned Fabric 3.1.5 [`osnadmin channel fetch` help](https://hyperledger-fabric.readthedocs.io/en/latest/commands/osnadminchannel.html#osnadmin-channel-fetch) accepts `--blockID config` and `-o` for an **exact Orderer admin endpoint**. The locally pinned `supply-tools` image also printed those flags with `--network none` and exit 0 during runbook preparation. Use the dedicated admin TLS client from #18. The first Orderer example writes its **complete native command** before executing it exactly once; the command, log and process-exit marker remain 0600. The HTTP status is a separate gate because `osnadmin` has previously exited 0 for an HTTP 400:

```sh
umask 077
test ! -e .runtime/channel/current-config
mkdir -m 0700 .runtime/channel/current-config
out=$PWD/.runtime/channel/current-config
test ! -e "$out/orderer0.command.sh" && test ! -e "$out/orderer0.log" && test ! -e "$out/orderer0.exit"
cat > "$out/orderer0.command.sh" <<'SH'
docker run --rm --pull=never --platform linux/arm64 --network supply-orderer \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/trust/orderer-tls-ca.pem,dst=/run/trust/orderer-tls-ca.pem,readonly" \
  --mount "type=bind,src=$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/signcerts/cert.pem,dst=/run/admin/client.pem,readonly" \
  --mount "type=bind,src=$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/keystore,dst=/run/admin/keystore,readonly" \
  --mount "type=bind,src=$PWD/.runtime/channel/current-config,dst=/run/fetch" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'umask 077; set -- /run/admin/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; \
   test ! -e /run/fetch/orderer0.config.block; \
   exec osnadmin channel fetch --channelID supplychannel --blockID config \
     --outputfile /run/fetch/orderer0.config.block -o orderer0.orderer.supply.test:9443 \
     --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"'
SH
chmod 0600 "$out/orderer0.command.sh"
set +e
bash "$out/orderer0.command.sh" > "$out/orderer0.log" 2>&1
code=$?
set -e
printf '%s\n' "$code" > "$out/orderer0.exit"
test "$code" -eq 0
rg -q '^Status: 200$' "$out/orderer0.log"
test -s "$out/orderer0.config.block"
python3 -c 'import os, stat, sys; assert all(stat.S_IMODE(os.stat(p).st_mode) == 0o600 for p in sys.argv[1:])' \
  "$out/orderer0.command.sh" "$out/orderer0.log" "$out/orderer0.exit" "$out/orderer0.config.block"
```

Run the same **separate** capture procedure for Orderer1 and Orderer2, substituting the endpoint, output filename and three evidence filenames with their exact node number; refuse existing files before each call. Require process exit `0`, **HTTP 200** in each native response, a nonempty new mode-0600 block file, and an active/consenter `osnadmin channel list --channelID supplychannel` status. Apply the same capture pattern to each Peer fetch and each offline decode; never run a six-node loop that hides first native calls. #18 already fetched `oldest` block 0 from all three Orderers and matched the original bytes; recheck those retained files/hashes before using them as genesis evidence.

Pinned Fabric 3.1.5 [`peer channel fetch` source](https://github.com/hyperledger/fabric/blob/v3.1.5/internal/peer/channel/fetch.go#L47-L59) chooses the **local Peer Deliver** client when no `-o` endpoint is supplied; [`InitCmdFactory`](https://github.com/hyperledger/fabric/blob/v3.1.5/internal/peer/channel/channel.go#L149-L164) confirms that branch. A command with `-o ordererN:7050` fetches from the Orderer and **cannot prove the Peer local ledger**. For each Peer, mount only its own admin ECert MSP for the signed Deliver request, its own short-lived Peer TLS pair for 7051 mTLS, its own public Peer root, rendered core.yaml, and the ignored output directory. Do not pass `-o` or an Orderer address environment override. First Seller example:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/network-config/peer0-seller.yaml,dst=/etc/hyperledger/fabric/core.yaml,readonly" \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/seller-admin1/msp,dst=/run/supply/msp,readonly" \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/seller-peer0-tls/msp,dst=/run/supply/tls,readonly" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/run/supply/peer-tls-root.pem,readonly" \
  --mount "type=bind,src=$PWD/.runtime/channel/current-config,dst=/run/fetch" \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=SellerMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.seller.supply.test:7051 \
  -e CORE_PEER_TLS_ENABLED=true -e CORE_PEER_TLS_CLIENTAUTHREQUIRED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'umask 077; test -z "${ORDERER_ADDRESS:-}"; \
   test ! -e /run/fetch/peer0-seller.config.block; \
   exec peer channel fetch config /run/fetch/peer0-seller.config.block -c supplychannel'
```

Run Buyer and Carrier **individually** with their own `supply-buyer`/`supply-carrier` network, rendered config, `buyer-admin1`/`carrier-admin1` ECert MSP, own `peer0-tls` MSP, root, DNS, MSP ID and distinct `peer0-buyer.config.block`/`peer0-carrier.config.block` output. Require exit `0` and `Received block:`/`Retrieving last config block:` in each log. #18 has already fetched block 0 separately from all three **local Peer Deliver** services and compared their equal-height `getinfo` hashes. If repeating that check, change `config` to `oldest` and the output filename to `<node>.block0.block` in separate native calls. Decode each local block and compare its **header and data** with the original #17 block, then calculate the canonical block-header hash and compare with `getinfo` at the same height. Preserve each file SHA-256 separately: #18 measured the three Peer-fetched files as byte-identical to one another, but each was one metadata byte longer than the original #17 file. A raw-file equality requirement against #17 would incorrectly reject this valid observed block-0 identity. A tool pointed at an Orderer cannot establish local Peer provenance.

Decode each of the **six** newly fetched `.config.block` files in a separate pinned `configtxlator proto_decode --type common.Block` invocation with `--network none`, no MSP/key mount, and 0600 `<node>.config.json` output. For Orderer0, the native command is:

```sh
docker run --rm --pull=never --platform linux/arm64 --network none \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/channel/current-config,dst=/run/fetch" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'umask 077; test ! -e /run/fetch/orderer0.config.json; \
   exec configtxlator proto_decode --input /run/fetch/orderer0.config.block \
     --type common.Block --output /run/fetch/orderer0.config.json'
```

Repeat this **individually** for Orderer1, Orderer2, Seller, Buyer and Carrier, substituting both block and JSON filenames. Save each exact command, exit, log, raw block SHA-256 and decoded JSON SHA-256; review the one-to-one raw-input/decoded-output provenance for every pinned native decode. Retain the independently approved **raw** CONFIG baseline, its raw-file SHA-256, decoded JSON and decoded-file SHA-256. Do not compare only CSV rows or the initial `inspect-block.json`. The [current-config verifier](../scripts/verify-m2-current-config.py) requires the previously recorded original decoded block-0 JSON SHA-256 and canonical block-0 **header** hash, plus the independently approved decoded expected CONFIG block and its recorded SHA-256. For the initial M2 configuration those expected inputs are the original #17 raw `supplychannel.block` (file SHA-256 `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a`) and `inspect-block.json` (SHA-256 `2e3c9994819ae2f5ec5c6a5741f6bf558d0c364380ffee3cac10930f8f4b4e09`), with header hash `5c68bf099e95b934b6034a4d7aa8c52442751c30bc8b56fcbbde9b0138e38ba7`. After a later authorized #19 configuration transaction, retain and approve its new native raw baseline and decoded JSON with both SHA-256 checksums before using that new decoded block as the expectation; a changed BatchTimeout must not pass merely because six nodes share it.

```sh
make verify-m2-current-config \
  M1_RUNTIME_DIR="$PWD/.runtime" M2_CHANNEL_DIR="$PWD/.runtime/channel" \
  M2_CURRENT_CONFIG_DIR="$PWD/.runtime/channel/current-config" \
  M2_APPROVED_CONFIG="$PWD/.runtime/channel/inspect-block.json" \
  M2_APPROVED_SHA256=2e3c9994819ae2f5ec5c6a5741f6bf558d0c364380ffee3cac10930f8f4b4e09 \
  M2_INITIAL_SHA256=2e3c9994819ae2f5ec5c6a5741f6bf558d0c364380ffee3cac10930f8f4b4e09 \
  M2_GENESIS_HASH=5c68bf099e95b934b6034a4d7aa8c52442751c30bc8b56fcbbde9b0138e38ba7
```

The verifier permits a later CONFIG block number and sequence, checks the approved **decoded JSON file** digest, M1 public MSP/consenter pins, capability, ACL, governance and `mod_policy`, then requires all six decoded block headers and complete CONFIG data to match that approved decoded baseline. Its PASS is limited to decoded-JSON governance structure and six-input agreement: it does **not** independently recompute Fabric `BlockDataHash` from raw envelope bytes or verify that any decoded JSON came from its claimed raw `.block`. A live NET-08 PASS requires the six retained native raw fetches, pinned one-to-one decodes, source/output hashes and independent review of that provenance in addition to this verifier's result. The synthetic later CONFIG with a 2s BatchTimeout exercises governance structure despite its deliberately stale `data_hash`; it is **not** a valid Fabric block or an integrity PASS. The verifier also does not validate later `last_update` signatures or prove that a proposed configuration transaction had the required authorization; #19 must retain its signed update and governance evidence separately. #18's three local Peer block-0 fetches and equal-height header-hash comparison have **PASS** evidence in its [three-Peer checkpoint](../evidence/m2/issue-18.md#three-peer-same-height-block-0-checkpoint-net-06), and #17's six-node current CONFIG comparison has [separate live evidence](../evidence/m2/issue-17.md#six-node-live-current-config-read-only-checkpoint). Full live MSP enforcement and post-genesis delivery remain **NOT RUN**. Fetches submit no channel update or business transaction and yield no committed txId or validation code.
