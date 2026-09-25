# M2 node configuration and first-run boundary (#16)

This is the configuration and preflight procedure for [issue #16](https://github.com/yjydist/supplyledger-lab/issues/16), following the [M2 Compose topology](m2-compose-topology.md) and the native [NET-03 channel block](m2-channel-native.md). It covers SPEC.md §§3.3–3.5, 4.4, 5.2–5.4, 16.1, 19.1 and T-NET-02. The six reviewed source YAMLs are in `network/config/`. They contain no key bytes or passwords. Their key path markers are filled using the one existing M1 private key filename in each relevant TLS MSP. Only ignored `.runtime/network-config/*.yaml` files are mounted by Compose.

## Prepare without starting services

Use the original M1 runtime with the 41 pinned identities. In the integrated main checkout `M2_SOURCE_RUNTIME_DIR=.runtime`; an isolated worktree may point `M2_SOURCE_RUNTIME_DIR` at the original main checkout's ignored `.runtime`. Preparation only **reads** M1 identities. It neither registers, enrolls, renews nor modifies certificates or keys.

```sh
M2_SOURCE_RUNTIME_DIR=${M2_SOURCE_RUNTIME_DIR:-$PWD/.runtime}
make verify-m1 M1_RUNTIME_DIR="$M2_SOURCE_RUNTIME_DIR"
make prepare-m2-nodes M2_SOURCE_RUNTIME_DIR="$M2_SOURCE_RUNTIME_DIR"
make verify-m2-nodes M2_SOURCE_RUNTIME_DIR="$M2_SOURCE_RUNTIME_DIR"
make network-config
make verify-m2-node-block M2_SOURCE_RUNTIME_DIR="$M2_SOURCE_RUNTIME_DIR" \
  M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json
```

`prepare-m2-nodes` validates the fifteen existing node ECert/TLS certificate-key pairs it needs against the #10 public certificate inventory, checks each keystore contains exactly one 0600 nonsymlink `*_sk` file, then writes six mode 0600 configs to `.runtime/network-config/`. Existing different output fails closed; no file is overwritten. The generated paths remain inside each node's own read-only MSP/TLS bind. The Orderer cluster client certificate is its `ordererN-tls` leaf and the shared 7050 cluster server listener uses that same `General.TLS.Certificate`; these bytes must match both #17 consenter PEM fields. The 9443 admin server uses its separate `ordererN-admin-server-tls` leaf. Its `ClientRootCAs` contains **only** the measured dedicated `orderer-admin-tls-ca` root.

The same preparation creates three distinct random CouchDB admin passwords in ignored `.secrets/couchdb/<org>.env` and a corresponding ignored `.secrets/peer-couchdb/<org>.env` for each Peer. Directory modes are 0700 and file modes are 0600. Each Peer receives only its own `CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME` and `CORE_LEDGER_STATE_COUCHDBCONFIG_PASSWORD`; its CouchDB receives the matching `COUCHDB_USER` and `COUCHDB_PASSWORD`. Rerunning preparation verifies and retains existing secrets byte-for-byte; a mismatch fails. Never print full `docker compose config`, `docker inspect .Config.Env`, or env file content, because those expose passwords to the host/Docker administrator. The latter remains inside ADR-004's trust boundary.

`make network-config` uses Compose `--no-env-resolution` and checks only source paths and service declarations. A static PASS does not prove that secrets or generated node configs exist; `make verify-m2-nodes` supplies that local preflight. For an isolated checkout, first-run service startup must occur only after the reviewed #17 NET-03 artifact and this branch are integrated into the checkout that owns the retained M1 runtime and volumes. Do not copy private MSPs into Git or an image build context.

`verify-m2-node-block` additionally reads the **native** #17 `inspect-block.json`, checks all three decoded client/server consenter PEM byte strings against the original M1 leaf files, and verifies the effective Orderer cluster client and shared-listener server certificate paths in the rendered node YAML. It requires the native artifact; a missing artifact must remain NOT RUN. `make test-m2-nodes M2_SOURCE_RUNTIME_DIR="$M2_SOURCE_RUNTIME_DIR" M2_INSPECT_BLOCK=<path>` performs the same comparison using ephemeral node configs and credentials in a temporary directory and rejects a modified consenter certificate.

## Native first-run sequence to execute later

These are separate operations, not a `make network-up` shortcut. Before each operation, record source commit, version-lock SHA-256, image digest, Compose tier, command/exit code and redacted output under `evidence/m2/`.

1. After #17's native `configtxgen` and static block decode, compare the **actual decoded** three consenters' client/server certificate PEM bytes to each `ordererN-tls` signcert and the effective `General.Cluster.ClientCertificate`/shared `General.TLS.Certificate` paths. Confirm cert-key match, SAN and ordinary TLS root. Keep the generated block and JSON ignored.
2. Start `orderer0`, `orderer1`, `orderer2` **one at a time** using the merged Compose overlays and `up -d --no-deps <name>`; inspect each actual process, mount and image digest. No channel is joined at this step. For each 9443 endpoint, use a short-lived Orderer-only tools container with the ordinary `orderer-tls-ca.pem` as `osnadmin --ca-file` and the existing dedicated `osnadmin-client1-tls` cert/key as `--client-cert`/`--client-key`. `osnadmin channel list` should return HTTP 200, `systemChannel:null` and an empty channels list. A request with no client certificate must fail at TLS; do not confuse CLI argument rejection with a handshake test. Record the server and client certificate fingerprints, exit/status and failure stage. #18 owns the full three-node wrong-CA negative matrix and native channel joins.
3. After #18 has joined all three Orderers with individual `osnadmin channel join` commands, start `couchdb0-seller`, `couchdb0-buyer`, `couchdb0-carrier` separately, check authenticated `/_up` from scoped tool contexts without logging passwords, then start `peer0-seller`, `peer0-buyer`, `peer0-carrier` separately. Check process/TLS/operations health and CouchDB connection. This is NET-06 component startup; Peer channel join and network-level readiness remain #18 work. Do not call a process that merely listens on 7051 ready for `supplychannel` or `supplycc`.

## T-NET-02 live inspection and evidence

After those nine services run, rerun `make network-config` and use a structured, redacted `docker inspect` assertion over all real Orderer, Peer, CouchDB and any extant CA containers. Check the locked image digest and expected command, status, exact network membership/DNS, no published management ports, no Docker socket, each node's own read-only identity binds, no cross-organization private MSP, and a distinct named ledger/data volume. Inspect **all** runtime mounts, including any Docker-image-created anonymous parent mounts, and verify ledger/WAL/snapshot paths reside on the declared named volumes. Check the tracked repository and image build contexts contain no credentials or private key material; report counts/paths/fingerprints only. Preserve sanitized actual results, not a copied raw `docker inspect` JSON object.

Record T-NET-02 as **NOT RUN** until these live checks succeed. T-NET-04, full admin negative matrix, Peer joins, current channel configuration, block-hash comparison and chaincode/transaction checks remain **NOT RUN** here until their owners execute them. The `genesisHash` field stays NOT RUN until the real block-0 identity is observed; a candidate block's file SHA-256 is only an artifact checksum. No txId, block height or validation code is invented for offline preflight.
