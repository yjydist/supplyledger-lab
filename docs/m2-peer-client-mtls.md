# M2 Peer delivery client mTLS repair (#16)

This is the guarded repair for the [Seller post-join delivery TLS failure](../evidence/m2/issue-18.md#seller-post-join-block-delivery-tls-failure). Seller has already joined `supplychannel` locally at height 1; Buyer and Carrier have not joined. The three Orderers and three CouchDBs remain on their existing volumes. Run these commands from the retained main checkout only after this source change has been independently reviewed and integrated. Do not run `reset`, `down`, a broad Compose `up`, or another Peer join as part of this repair.

Pinned Fabric v3.1.5 [gates the delivery client certificate on `peer.tls.clientAuthRequired`](https://github.com/hyperledger/fabric/blob/v3.1.5/core/deliverservice/config.go#L168-L193), even when `clientCert.file` and `clientKey.file` are present. The same key [enables client authentication on the Peer 7051 listener](https://github.com/hyperledger/fabric/blob/v3.1.5/core/peer/config.go#L353-L387). The [native Peer CLI reads its own client pair only when that key is true](https://github.com/hyperledger/fabric/blob/v3.1.5/internal/peer/common/common.go#L285-L334). The three Peer templates therefore set it to true and explicitly list the three business-organization public TLS CA roots in `peer.tls.clientRootCAs.files`. Each Peer receives the other two roots as read-only **public certificate files**; no other organization's private MSP or CA key is mounted. The Peer outbound delivery pair remains its own M1 `peer0-tls` identity; the Orderers already trust all three business TLS roots at 7050.

| Connection | Transport identity and trust | Separate authorization |
| --- | --- | --- |
| Peer → Orderer 7050 delivery | Peer presents its own `peer0-tls` clientAuth leaf/key; Orderer validates its organization's TLS CA; Peer validates Orderer DNS and the channel's Orderer TLS root. | Channel delivery request remains signed with the Peer ECert. |
| Peer ↔ Peer 7051 gossip | Each Peer 7051 listener accepts client TLS chains under exactly Seller, Buyer and Carrier public TLS roots. Each Peer presents its own TLS pair. | Channel MSP and gossip rules still decide peer membership; TLS acceptance alone does not grant channel access. Cross-organization NET-07 discovery remains a live test. |
| M2 one-shot admin CLI → own Peer 7051 | On its own organization network only, the tool mounts that organization's rendered `core.yaml`, public Peer root and existing `peer0-tls` MSP read-only as the TLS client pair. The tool runs nonroot/read-only. | It separately mounts its own organization admin ECert MSP at `/run/supply/msp` to sign the CSCC request. The TLS certificate is not an admin ECert. |
| M3 app/Gateway → own Peer 7051 | Issue a **separate** application TLS clientAuth identity under an allowed organization TLS CA; configure the Go gRPC TLS client with that cert/key, own Peer TLS root and DNS verification. Do not put the Peer node TLS key in a long-lived app. | Business user ECert signs proposals; TLS identity alone does not grant business role. M3 app connection and cross-organization TLS behavior remain NOT RUN. |

The dedicated Orderer **admin API** client CA remains separate and is not in the Peer 7051 trust list. The operations service on 9444 continues to trust only its own organization root. The static checks pin the source/rendered YAML list and exact read-only Compose binds; `make verify-m1` checks the retained cert/key material and roots. A passing static check is not a live Peer delivery, gossip or Gateway result.

## Stage and compare before stopping any Peer

Capture each literal block in a fresh ignored mode-0600 `.command.sh` under `.runtime/m2-node-logs/`, execute it separately with stdout/stderr redirected to its own mode-0600 `.log`, and record the actual process exit in a paired `.exit`; stop on nonzero before the next block. Use `umask 077` and do not print credential values. The following first block has no network mutation. It refuses absent private credentials before `prepare-m2-nodes` can create them, snapshots all nine current IDs, the three named Peer ledger identities, all M1 identity bytes, six credential env files, the original #17 block/decoded JSON, three Orderer YAMLs and the historical delivery-failure log. Stop on any mismatch. Retain the generated manifests only in ignored runtime storage.

~~~sh
set -eu
umask 077
test -z "$(git status --porcelain)"
test -d .runtime/m2-node-logs && test ! -L .runtime/m2-node-logs
test -s .runtime/m2-issue18-peer-logs/seller-delivery-tls-fail.filtered.log
test ! -e .runtime/m2-peer-client-mtls-stage
test ! -L .runtime/m2-peer-client-mtls-stage
test ! -e .runtime/m2-node-logs/network-config-before-peer-client-mtls
test ! -L .runtime/m2-node-logs/network-config-before-peer-client-mtls
python3 - <<'INNER'
from pathlib import Path
from stat import S_IMODE
root = Path('.secrets')
assert root.is_dir() and not root.is_symlink() and S_IMODE(root.stat().st_mode) == 0o700
for subdir in ('couchdb', 'peer-couchdb'):
    directory = root / subdir
    assert directory.is_dir() and not directory.is_symlink()
    assert S_IMODE(directory.stat().st_mode) == 0o700
    assert {p.name for p in directory.iterdir()} == {'seller.env', 'buyer.env', 'carrier.env'}
    for path in directory.iterdir():
        assert path.is_file() and not path.is_symlink()
        assert S_IMODE(path.stat().st_mode) == 0o600
print('PASS: all six original credential env files exist before prepare mode')
INNER
git rev-parse HEAD > .runtime/m2-node-logs/peer-client-mtls-source-commit
shasum -a 256 .runtime/m2-issue18-peer-logs/seller-delivery-tls-fail.filtered.log > .runtime/m2-node-logs/peer-client-mtls-first-failure.sha256
for name in orderer0 orderer1 orderer2 couchdb0-seller couchdb0-buyer couchdb0-carrier peer0-seller peer0-buyer peer0-carrier; do
  test "$(docker inspect --format '{{.State.Status}}' "supplyledger-${name}-1")" = running
  docker inspect --format '{{.Id}}' "supplyledger-${name}-1" > ".runtime/m2-node-logs/${name}-before-peer-client-mtls-id"
done
for org in seller buyer carrier; do
  docker volume inspect --format '{{.Name}} {{.CreatedAt}}' "supplyledger_peer0_${org}_ledger" > ".runtime/m2-node-logs/peer0-${org}-before-peer-client-mtls-ledger"
done
make verify-m1 > .runtime/m2-node-logs/m1-before-peer-client-mtls.log 2>&1
python3 - <<'INNER' > .runtime/m2-node-logs/m1-identity-before-peer-client-mtls.sha256
from hashlib import sha256
from pathlib import Path
root = Path('.runtime/identities')
for path in sorted(root.rglob('*')):
    assert not path.is_symlink(), path
    if path.is_file():
        print(sha256(path.read_bytes()).hexdigest(), path.relative_to(root))
INNER
shasum -a 256 .secrets/couchdb/*.env .secrets/peer-couchdb/*.env > .runtime/m2-node-logs/m2-env-before-peer-client-mtls.sha256
shasum -a 256 .runtime/channel/supplychannel.block .runtime/channel/inspect-block.json > .runtime/m2-node-logs/channel-before-peer-client-mtls.sha256
shasum -a 256 .runtime/network-config/orderer*.yaml > .runtime/m2-node-logs/orderer-config-before-peer-client-mtls.sha256
make network-config
make prepare-m2-nodes M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-client-mtls-stage
make verify-m2-nodes M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-client-mtls-stage
make verify-m2-node-block M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-client-mtls-stage M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json
shasum -a 256 .runtime/network-config/*.yaml .runtime/m2-peer-client-mtls-stage/network-config/*.yaml > .runtime/m2-node-logs/peer-client-mtls-configs-reviewed.sha256
~~~

The comparison must pass **before** any stop. It permits exactly one false→true replacement and the three exact public client-root paths per Peer, with the other three YAMLs byte-identical. It does not inspect or change a named volume.

~~~sh
python3 - <<'INNER'
from pathlib import Path
old_dir = Path('.runtime/network-config')
stage_dir = Path('.runtime/m2-peer-client-mtls-stage/network-config')
assert old_dir.is_dir() and stage_dir.is_dir()
assert not old_dir.is_symlink() and not stage_dir.is_symlink()
assert old_dir.stat().st_dev == stage_dir.stat().st_dev, 'rename must stay on one filesystem'
assert {p.name for p in old_dir.iterdir()} == {p.name for p in stage_dir.iterdir()}
for index in range(3):
    name = f'orderer{index}.yaml'
    assert (stage_dir / name).read_bytes() == (old_dir / name).read_bytes(), name
for org in ('seller', 'buyer', 'carrier'):
    name = f'peer0-{org}.yaml'
    old = (old_dir / name).read_bytes()
    old_tls = b'  tls:\n    enabled: true\n    clientAuthRequired: false\n'
    assert old.count(old_tls) == 1, name
    roots = b''.join((
        b'        - /run/supply/peer-tls-root.pem\n' if member == org else
        f'        - /run/supply/client-roots/{member}.pem\n'.encode()
    ) for member in ('seller', 'buyer', 'carrier'))
    new_tls = (b'  tls:\n    enabled: true\n    clientAuthRequired: true\n'
               b'    clientRootCAs:\n      files:\n' + roots)
    assert (stage_dir / name).read_bytes() == old.replace(old_tls, new_tls, 1), name
print('PASS: Orderers identical; each Peer adds only exact 7051 client roots and true mTLS')
INNER
~~~

## Peer-only stopped-state migration

Compare reviewed stage hashes immediately before stop. Stop Seller, Buyer and Carrier **individually**, confirm original IDs now exited, and move only their three generated YAMLs after all three are stopped. `docker compose stop` and the later `--force-recreate` keep the existing named ledgers. No Orderer or CouchDB is restarted. The old Peer configs and failure log remain under ignored 0700/0600 runtime paths.

~~~sh
set -eu
umask 077
shasum -a 256 .runtime/network-config/*.yaml .runtime/m2-peer-client-mtls-stage/network-config/*.yaml > .runtime/m2-node-logs/peer-client-mtls-configs-before-stop.sha256
cmp .runtime/m2-node-logs/peer-client-mtls-configs-reviewed.sha256 .runtime/m2-node-logs/peer-client-mtls-configs-before-stop.sha256
shasum -a 256 .secrets/couchdb/*.env .secrets/peer-couchdb/*.env > .runtime/m2-node-logs/m2-env-before-stop-peer-client-mtls.sha256
cmp .runtime/m2-node-logs/m2-env-before-peer-client-mtls.sha256 .runtime/m2-node-logs/m2-env-before-stop-peer-client-mtls.sha256
shasum -a 256 .runtime/channel/supplychannel.block .runtime/channel/inspect-block.json > .runtime/m2-node-logs/channel-before-stop-peer-client-mtls.sha256
cmp .runtime/m2-node-logs/channel-before-peer-client-mtls.sha256 .runtime/m2-node-logs/channel-before-stop-peer-client-mtls.sha256
for org in seller buyer carrier; do
  test "$(docker inspect --format '{{.State.Status}}' "supplyledger-peer0-${org}-1")" = running
  docker inspect --format '{{.Id}}' "supplyledger-peer0-${org}-1" > ".runtime/m2-node-logs/peer0-${org}-prestop-peer-client-mtls-id"
  cmp ".runtime/m2-node-logs/peer0-${org}-before-peer-client-mtls-id" ".runtime/m2-node-logs/peer0-${org}-prestop-peer-client-mtls-id"
done
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca stop peer0-seller
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca stop peer0-buyer
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca stop peer0-carrier
for org in seller buyer carrier; do
  test "$(docker inspect --format '{{.State.Status}}' "supplyledger-peer0-${org}-1")" = exited
  docker inspect --format '{{.Id}}' "supplyledger-peer0-${org}-1" > ".runtime/m2-node-logs/peer0-${org}-stopped-peer-client-mtls-id"
  cmp ".runtime/m2-node-logs/peer0-${org}-before-peer-client-mtls-id" ".runtime/m2-node-logs/peer0-${org}-stopped-peer-client-mtls-id"
done
mkdir -m 700 .runtime/m2-node-logs/network-config-before-peer-client-mtls
for org in seller buyer carrier; do
  old=".runtime/network-config/peer0-${org}.yaml"
  archived=".runtime/m2-node-logs/network-config-before-peer-client-mtls/peer0-${org}.yaml"
  test -f "$old" && test ! -L "$old"
  cp -p "$old" "$archived"
  cmp "$old" "$archived"
done
for org in seller buyer carrier; do
  staged=".runtime/m2-peer-client-mtls-stage/network-config/peer0-${org}.yaml"
  current=".runtime/network-config/peer0-${org}.yaml"
  test -f "$staged" && test ! -L "$staged"
  mv -f "$staged" "$current"
done
make verify-m2-nodes
make verify-m2-node-block M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json
make network-config
make verify-m1 > .runtime/m2-node-logs/m1-after-peer-client-mtls.log 2>&1
python3 - <<'INNER' > .runtime/m2-node-logs/m1-identity-after-peer-client-mtls.sha256
from hashlib import sha256
from pathlib import Path
root = Path('.runtime/identities')
for path in sorted(root.rglob('*')):
    assert not path.is_symlink(), path
    if path.is_file():
        print(sha256(path.read_bytes()).hexdigest(), path.relative_to(root))
INNER
cmp .runtime/m2-node-logs/m1-identity-before-peer-client-mtls.sha256 .runtime/m2-node-logs/m1-identity-after-peer-client-mtls.sha256
shasum -a 256 .secrets/couchdb/*.env .secrets/peer-couchdb/*.env > .runtime/m2-node-logs/m2-env-after-peer-client-mtls.sha256
cmp .runtime/m2-node-logs/m2-env-before-peer-client-mtls.sha256 .runtime/m2-node-logs/m2-env-after-peer-client-mtls.sha256
shasum -a 256 .runtime/channel/supplychannel.block .runtime/channel/inspect-block.json > .runtime/m2-node-logs/channel-after-peer-client-mtls.sha256
cmp .runtime/m2-node-logs/channel-before-peer-client-mtls.sha256 .runtime/m2-node-logs/channel-after-peer-client-mtls.sha256
shasum -a 256 .runtime/network-config/orderer*.yaml > .runtime/m2-node-logs/orderer-config-after-peer-client-mtls.sha256
cmp .runtime/m2-node-logs/orderer-config-before-peer-client-mtls.sha256 .runtime/m2-node-logs/orderer-config-after-peer-client-mtls.sha256
shasum -a 256 .runtime/m2-issue18-peer-logs/seller-delivery-tls-fail.filtered.log > .runtime/m2-node-logs/peer-client-mtls-first-failure-after.sha256
cmp .runtime/m2-node-logs/peer-client-mtls-first-failure.sha256 .runtime/m2-node-logs/peer-client-mtls-first-failure-after.sha256
for name in orderer0 orderer1 orderer2 couchdb0-seller couchdb0-buyer couchdb0-carrier; do
  test "$(docker inspect --format '{{.State.Status}}' "supplyledger-${name}-1")" = running
  docker inspect --format '{{.Id}}' "supplyledger-${name}-1" > ".runtime/m2-node-logs/${name}-after-peer-client-mtls-id"
  cmp ".runtime/m2-node-logs/${name}-before-peer-client-mtls-id" ".runtime/m2-node-logs/${name}-after-peer-client-mtls-id"
done
for org in seller buyer carrier; do
  docker volume inspect --format '{{.Name}} {{.CreatedAt}}' "supplyledger_peer0_${org}_ledger" > ".runtime/m2-node-logs/peer0-${org}-after-peer-client-mtls-ledger"
  cmp ".runtime/m2-node-logs/peer0-${org}-before-peer-client-mtls-ledger" ".runtime/m2-node-logs/peer0-${org}-after-peer-client-mtls-ledger"
done
~~~

Review this stopped-state checkpoint before any recreate. Recreate **Seller only** first with `docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate peer0-seller`. Require a new running ID on the same named ledger/creation timestamp, exact two networks, the new two public root mounts and own read-only MSP/TLS/config/builder binds, no socket or published ports. Preserve its startup log (it can print effective private config). The three Orderer and CouchDB IDs must remain unchanged; Buyer/Carrier stay stopped pending independent Seller review. No Peer channel join is repeated: Seller's joined ledger is retained.

If the staged comparison or old-file archive gate fails, leave the existing bind sources in place and retain the logs. The archive step copies and byte-compares **all three** old mode-0600 YAMLs before the first replacement. Each staged YAML is then renamed directly over its current path on the same `.runtime` filesystem, with no remove-then-create gap. If a replacement fails after any subset of Peers has switched, keep all Peers stopped and retain all logs/manifests. The following **config-only rollback** works for that partial cutover: it retains the old archive, preserves any current replacement in a separate ignored directory, and atomically restores each original file from a checked temporary copy. It removes no container or ledger volume. It deliberately restores the known delivery TLS defect, so this is a preserved-ledger fallback, not a delivery PASS. The new preflight will reject restored old YAML by design; do not treat that expected rejection as a reason to rotate credentials or rebuild the network. Any later start from restored files must use individual `--force-recreate` and a fresh review checkpoint.

~~~sh
set -eu
umask 077
for org in seller buyer carrier; do
  container="supplyledger-peer0-${org}-1"
  status="$(docker inspect --format '{{.State.Status}}' "$container")"
  if test "$status" = running; then
    docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca stop "peer0-${org}"
  else
    test "$status" = exited
  fi
done
test ! -e .runtime/m2-node-logs/network-config-replaced-peer-client-mtls
test ! -L .runtime/m2-node-logs/network-config-replaced-peer-client-mtls
for org in seller buyer carrier; do
  old=".runtime/m2-node-logs/network-config-before-peer-client-mtls/peer0-${org}.yaml"
  test -f "$old" && test ! -L "$old"
  current=".runtime/network-config/peer0-${org}.yaml"
  test ! -L "$current"
  test ! -e "${current}.rollback" && test ! -L "${current}.rollback"
done
mkdir -m 700 .runtime/m2-node-logs/network-config-replaced-peer-client-mtls
for org in seller buyer carrier; do
  old=".runtime/m2-node-logs/network-config-before-peer-client-mtls/peer0-${org}.yaml"
  current=".runtime/network-config/peer0-${org}.yaml"
  if test -f "$current"; then
    cp -p "$current" .runtime/m2-node-logs/network-config-replaced-peer-client-mtls/
  fi
  cp -p "$old" "${current}.rollback"
  cmp "$old" "${current}.rollback"
  mv -f "${current}.rollback" "$current"
  cmp "$old" "$current"
done
shasum -a 256 .runtime/channel/supplychannel.block .runtime/channel/inspect-block.json > .runtime/m2-node-logs/channel-after-peer-client-mtls-rollback.sha256
cmp .runtime/m2-node-logs/channel-before-peer-client-mtls.sha256 .runtime/m2-node-logs/channel-after-peer-client-mtls-rollback.sha256
for org in seller buyer carrier; do
  docker volume inspect --format '{{.Name}} {{.CreatedAt}}' "supplyledger_peer0_${org}_ledger" > ".runtime/m2-node-logs/peer0-${org}-after-peer-client-mtls-rollback-ledger"
  cmp ".runtime/m2-node-logs/peer0-${org}-before-peer-client-mtls-ledger" ".runtime/m2-node-logs/peer0-${org}-after-peer-client-mtls-rollback-ledger"
done
~~~

## Seller transport and channel-local probes

First verify Seller's configured TLS client cert/key still match and have clientAuth EKU with `make verify-m1`; the retained Orderer client roots and Peer roots must match the exact `.runtime/trust/{org}-tls-ca.pem` public files. Probe the Orderer 7050 with Seller's TLS client pair, validating Orderer DNS/root without bypass, and inspect fresh Seller/Orderer logs for whether the **actual Fabric delivery dial** still reports `certificate required` or establishes a stream. A successful standalone TLS handshake establishes transport trust only; an absence of errors alone does not prove a Fabric Deliver response. Because no new block is currently ordered, receipt of a new block remains **NOT RUN** until a later ordered operation and height/hash check.

For Peer 7051, require an own-client TLS handshake and a no-client TLS rejection (`certificate required`, no application response). The operations service still requires its own client cert and returns `/healthz` HTTP 200/OK. To exercise the native CSCC path on the already joined Seller ledger, run `peer channel list` and `peer channel getinfo -c supplychannel` separately, with actual process exits and private logs, using this exact one-shot CLI form. Keep the mounted Seller admin ECert MSP and the Seller `peer0-tls` transport MSP separate. `core.yaml` sets `peer.tls.clientAuthRequired=true`; the explicit matching `CORE_PEER_TLS_CLIENTAUTHREQUIRED=true` guard prevents a tool environment from silently omitting its certificate. Use the same form with each organization's own network/MSP/root/TLS pair for Buyer/Carrier after their separate reviewed recreation, never cross-mount private MSPs.

~~~sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/network-config/peer0-seller.yaml,dst=/etc/hyperledger/fabric/core.yaml,readonly" \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/seller-admin1/msp,dst=/run/supply/msp,readonly" \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/seller-peer0-tls/msp,dst=/run/supply/tls,readonly" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/run/supply/peer-tls-root.pem,readonly" \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=SellerMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.seller.supply.test:7051 \
  -e CORE_PEER_TLS_ENABLED=true -e CORE_PEER_TLS_CLIENTAUTHREQUIRED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel list
~~~

For the separate getinfo call, replace only the trailing `channel list` with `channel getinfo -c supplychannel`. Expected: list includes Seller's existing `supplychannel`; getinfo returns local height at least 1. These are signed CSCC **queries**, not submitted channel transactions; they do not prove fresh block receipt. Do not call either PASS based on Docker exit alone: inspect Peer response and output. Buyer/Carrier joins and NET-07 cross-organization gossip remain on hold until independent review; full nine-service `T-NET-02`, three-Peer equal-height hashes, canonical `genesisHash`, functional M3 builder/CCaaS and app Gateway client mTLS remain **NOT RUN**.
