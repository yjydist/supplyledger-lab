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

Fabric CA gives each TLS MSP `tlscacerts` file an enrollment-specific basename. Node YAML therefore uses stable read-only public root binds: `/run/supply/client-roots/orderer.pem` for Orderer outbound TLS, and each Peer's own `/run/supply/peer-tls-root.pem` for its TLS and operations configuration. The Compose checker pins every bind to the measured `.runtime/trust/<org>-tls-ca.pem` source.

The same preparation creates three distinct random CouchDB admin passwords in ignored `.secrets/couchdb/<org>.env` and a corresponding ignored `.secrets/peer-couchdb/<org>.env` for each Peer. Directory modes are 0700 and file modes are 0600. Each Peer receives only its own `CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME` and `CORE_LEDGER_STATE_COUCHDBCONFIG_PASSWORD`; its CouchDB receives the matching `COUCHDB_USER` and `COUCHDB_PASSWORD`. Rerunning preparation verifies and retains existing secrets byte-for-byte; a mismatch fails. Never print full `docker compose config`, `docker inspect .Config.Env`, or env file content, because those expose passwords to the host/Docker administrator. The latter remains inside ADR-004's trust boundary.

`make network-config` uses Compose `--no-env-resolution` and checks only source paths and service declarations. A static PASS does not prove that secrets or generated node configs exist; `make verify-m2-nodes` supplies that local preflight. For an isolated checkout, first-run service startup must occur only after the reviewed #17 NET-03 artifact and this branch are integrated into the checkout that owns the retained M1 runtime and volumes. Do not copy private MSPs into Git or an image build context.

`verify-m2-node-block` additionally reads the **native** #17 `inspect-block.json`, checks all three decoded client/server consenter PEM byte strings against the original M1 leaf files, and verifies the effective Orderer cluster client and shared-listener server certificate paths in the rendered node YAML. It requires the native artifact; a missing artifact must remain NOT RUN. `make test-m2-nodes M2_SOURCE_RUNTIME_DIR="$M2_SOURCE_RUNTIME_DIR" M2_INSPECT_BLOCK=<path>` performs the same comparison using ephemeral node configs and credentials in a temporary directory and rejects a modified consenter certificate.

Each Orderer source and rendered YAML must also set `ChannelParticipation.MaxRequestBodySize: 1 MB`. Fabric 3.1.5's [sample Orderer YAML](https://github.com/hyperledger/fabric/blob/v3.1.5/sampleconfig/orderer.yaml#L287-L291) uses this value. The [channel participation REST handler](https://github.com/hyperledger/fabric/blob/v3.1.5/orderer/common/channelparticipation/restapi.go#L391-L401) applies it to the complete multipart join request. It is separate from the Orderer gRPC message and block batch limits. The first native #18 Orderer0 join exposed the missing field: the effective limit was `0`, and a 27,946-byte block upload received HTTP 400 before block validation. Check the HTTP status and channel list; `osnadmin` process exit `0` alone does not prove a join.

## One-time recovery from the first Orderer0 root-path failure

The first native `orderer0` process at source commit `f7960652b809eaedd53a637445cb583c6f0cda3e` exited while reading a guessed TLS MSP root filename. Its failed container, six rendered YAMLs and ignored logs still exist in the retained main runtime. After the reviewed root-path correction is integrated, `prepare-m2-nodes` must reject those old rendered YAMLs rather than silently overwrite them. Perform this explicit one-time replacement before retrying. Do not touch M1 identities, the six existing credential env files, or the named ledger volume.

Run these commands in the integrated main checkout. Stop if any assertion fails. The archived directory must not already exist; this keeps a repeated attempt from overwriting the original failed input. The source commit, failed container ID, original config hashes, secret-file hashes and named-volume identity stay in ignored `.runtime/m2-node-logs/` alongside the original failure logs.

~~~sh
set -eu
test -f .runtime/m2-node-logs/orderer0-first-fail.log
test "$(docker inspect --format '{{.State.Status}}:{{.State.ExitCode}}' supplyledger-orderer0-1)" = "exited:1"
test ! -e .runtime/m2-node-logs/network-config-before-root-fix
umask 077
git rev-parse HEAD > .runtime/m2-node-logs/root-fix-source-commit
docker inspect --format '{{.Id}}' supplyledger-orderer0-1 > .runtime/m2-node-logs/orderer0-failed-id
docker volume inspect --format '{{.Name}} {{.CreatedAt}}' supplyledger_orderer0_ledger > .runtime/m2-node-logs/orderer0-ledger-before
shasum -a 256 .runtime/network-config/*.yaml > .runtime/m2-node-logs/network-config-before.sha256
shasum -a 256 .secrets/couchdb/*.env .secrets/peer-couchdb/*.env > .runtime/m2-node-logs/m2-env-before.sha256
mv .runtime/network-config .runtime/m2-node-logs/network-config-before-root-fix
make prepare-m2-nodes
make verify-m2-nodes
make verify-m2-node-block M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json
shasum -a 256 .secrets/couchdb/*.env .secrets/peer-couchdb/*.env > .runtime/m2-node-logs/m2-env-after.sha256
cmp .runtime/m2-node-logs/m2-env-before.sha256 .runtime/m2-node-logs/m2-env-after.sha256
~~~

Check that the six new files differ from the preserved failed input **only** by the reviewed root-path substitutions; the command prints no key or password. The preflight commands above also verify new directory/file modes (0700/0600), the same M1 cert-key pairs, and the #17 byte-pinned Raft certificates.

~~~sh
python3 - <<'PY'
from pathlib import Path
old_dir = Path(".runtime/m2-node-logs/network-config-before-root-fix")
new_dir = Path(".runtime/network-config")
for index in range(3):
    name = f"orderer{index}.yaml"
    old = (old_dir / name).read_bytes()
    source = b"/run/supply/tls/tlscacerts/orderer-tls-ca.pem"
    assert old.count(source) == 1, name
    expected = old.replace(source, b"/run/supply/client-roots/orderer.pem")
    assert (new_dir / name).read_bytes() == expected, name
for org in ("seller", "buyer", "carrier"):
    name = f"peer0-{org}.yaml"
    old = (old_dir / name).read_bytes()
    source = f"/run/supply/tls/tlscacerts/{org}-tls-ca.pem".encode()
    assert old.count(source) == 2, name
    expected = old.replace(source, b"/run/supply/peer-tls-root.pem")
    assert (new_dir / name).read_bytes() == expected, name
print("PASS: six regenerated configs contain only reviewed root-path changes")
PY
~~~

Only after the above checks pass, explicitly recreate the **failed Orderer0 container only**. Compose's `--force-recreate` replaces its old file binds; it does not select the other Orderers, Peers or CouchDBs. Compare the container IDs and the retained named-volume identity, then inspect the new process and admin API as the next NET-04 observation. Do not use `reset` or remove a volume.

~~~sh
set -eu
umask 077
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate orderer0
docker inspect --format '{{.Id}}' supplyledger-orderer0-1 > .runtime/m2-node-logs/orderer0-retry-id
! cmp -s .runtime/m2-node-logs/orderer0-failed-id .runtime/m2-node-logs/orderer0-retry-id
docker volume inspect --format '{{.Name}} {{.CreatedAt}}' supplyledger_orderer0_ledger > .runtime/m2-node-logs/orderer0-ledger-after
cmp .runtime/m2-node-logs/orderer0-ledger-before .runtime/m2-node-logs/orderer0-ledger-after
test "$(docker inspect --format '{{.State.Status}}' supplyledger-orderer0-1)" = "running"
docker inspect --format '{{.State.Status}}:{{.State.ExitCode}}' supplyledger-orderer0-1
~~~

## One-time recovery from the first Orderer0 join HTTP 400

At source commit `4376ed4c0c6ae176f3240037c0e3a927c930d0c9`, #18 sent the original #17 block once to Orderer0. The CLI exited `0`, but the admin API returned HTTP `400` with `multipart: NextPart: http: request body too large`. A separate native list still returned HTTP `200`, `systemChannel:null` and `channels:null`. The three running Orderers each logged effective `ChannelParticipation.MaxRequestBodySize = 0`. The failure was at multipart parsing, before block validation or `JoinChannel`; no channel, txId, block height, validation code or live genesisHash resulted. Preserve `.runtime/m2-issue18-logs/orderer0-join.log`, `orderer0-post-400-list.log` and the original `.runtime/channel/supplychannel.block` byte-for-byte. See [#18's native command and evidence](../evidence/m2/issue-18.md#first-native-orderer0-join-failure).

Only after this `1 MB` source change is independently reviewed and integrated into the main checkout that owns the retained runtime, perform the following one-time migration. Confirm fresh native admin lists still show no joined channel before changing the node configs; if any node has joined, stop and review its ledger state. The archived path must not already exist. All three nodes are unjoined, so stop them **individually** before replacing their host config files. This preserves the three named ledger volumes and avoids a running process depending on a replaced bind path. Do not remove the containers or volumes, regenerate the #17 block, reissue M1 identities or rotate the three passwords in the six existing credential env files.

~~~sh
set -eu
umask 077
m1_file_hashes() {
  python3 - <<'PY'
from hashlib import sha256
from pathlib import Path
root = Path('.runtime/identities')
assert root.is_dir() and not root.is_symlink()
for path in sorted(root.rglob('*')):
    assert not path.is_symlink(), path
    if path.is_file():
        print(sha256(path.read_bytes()).hexdigest(), path.relative_to(root))
PY
}
test -f .runtime/m2-issue18-logs/orderer0-join.log
test -f .runtime/m2-issue18-logs/orderer0-post-400-list.log
test ! -e .runtime/m2-node-logs/network-config-before-join-limit
test ! -L .runtime/m2-node-logs/network-config-before-join-limit
test "$(shasum -a 256 .runtime/channel/supplychannel.block | awk '{print $1}')" = b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a
test "$(shasum -a 256 .runtime/channel/inspect-block.json | awk '{print $1}')" = 2e3c9994819ae2f5ec5c6a5741f6bf558d0c364380ffee3cac10930f8f4b4e09
make verify-m1 > .runtime/m2-node-logs/m1-before-join-limit.log 2>&1
m1_file_hashes > .runtime/m2-node-logs/m1-identity-before-join-limit.sha256
for name in orderer0 orderer1 orderer2; do
  test "$(docker inspect --format '{{.State.Status}}' "supplyledger-${name}-1")" = running
  docker inspect --format '{{.Id}}' "supplyledger-${name}-1" > ".runtime/m2-node-logs/${name}-before-join-limit-id"
  docker volume inspect --format '{{.Name}} {{.CreatedAt}}' "supplyledger_${name}_ledger" > ".runtime/m2-node-logs/${name}-join-limit-volume-before"
done
git rev-parse HEAD > .runtime/m2-node-logs/join-limit-source-commit
shasum -a 256 .runtime/network-config/*.yaml > .runtime/m2-node-logs/network-config-before-join-limit.sha256
shasum -a 256 .secrets/couchdb/*.env .secrets/peer-couchdb/*.env > .runtime/m2-node-logs/m2-env-before-join-limit.sha256
shasum -a 256 .runtime/channel/supplychannel.block .runtime/channel/inspect-block.json > .runtime/m2-node-logs/channel-before-join-limit.sha256
for name in orderer0 orderer1 orderer2; do
  docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca stop "$name"
  test "$(docker inspect --format '{{.State.Status}}' "supplyledger-${name}-1")" = exited
done
mv .runtime/network-config .runtime/m2-node-logs/network-config-before-join-limit
make prepare-m2-nodes
make verify-m2-nodes
make verify-m2-node-block M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json
make verify-m1 > .runtime/m2-node-logs/m1-after-join-limit.log 2>&1
m1_file_hashes > .runtime/m2-node-logs/m1-identity-after-join-limit.sha256
cmp .runtime/m2-node-logs/m1-identity-before-join-limit.sha256 .runtime/m2-node-logs/m1-identity-after-join-limit.sha256
shasum -a 256 .secrets/couchdb/*.env .secrets/peer-couchdb/*.env > .runtime/m2-node-logs/m2-env-after-join-limit.sha256
cmp .runtime/m2-node-logs/m2-env-before-join-limit.sha256 .runtime/m2-node-logs/m2-env-after-join-limit.sha256
shasum -a 256 .runtime/channel/supplychannel.block .runtime/channel/inspect-block.json > .runtime/m2-node-logs/channel-after-join-limit.sha256
cmp .runtime/m2-node-logs/channel-before-join-limit.sha256 .runtime/m2-node-logs/channel-after-join-limit.sha256
shasum -a 256 .runtime/network-config/*.yaml > .runtime/m2-node-logs/network-config-after-join-limit.sha256
~~~

The retained M1 identity files and ignored credential files must remain byte-identical, proven by the before/after manifests and `cmp`; both `make verify-m1` runs must pass. The preflight verifies new config mode `0600`, directory mode `0700`, exact node key paths and the original #17 Raft certificate bytes. Compare all six new configs with the archive: **only** the new `1 MB` line in each Orderer is allowed; all three Peer configs must be identical. These comparisons print no private value.

~~~sh
python3 - <<'PY'
from pathlib import Path
old_dir = Path('.runtime/m2-node-logs/network-config-before-join-limit')
new_dir = Path('.runtime/network-config')
assert {p.name for p in old_dir.iterdir()} == {p.name for p in new_dir.iterdir()}
for index in range(3):
    name = f'orderer{index}.yaml'
    old = (old_dir / name).read_bytes()
    needle = b'ChannelParticipation:\n  Enabled: true\n'
    assert old.count(needle) == 1, name
    expected = old.replace(needle, needle + b'  MaxRequestBodySize: 1 MB\n')
    assert (new_dir / name).read_bytes() == expected, name
for org in ('seller', 'buyer', 'carrier'):
    name = f'peer0-{org}.yaml'
    assert (new_dir / name).read_bytes() == (old_dir / name).read_bytes(), name
print('PASS: only three reviewed Orderer join-body limits changed')
PY
~~~

If any comparison fails, leave the Orderers stopped and preserve both config directories for review. After all checks pass, recreate **one Orderer at a time** using `--force-recreate` so the process receives the new file bind; `docker compose restart` may retain the old bind. Start with Orderer0 and seek a live checkpoint before Orderer1/2. For each node, check the new container ID, the unchanged named volume identity, running status, and startup log line `ChannelParticipation.MaxRequestBodySize = 1048576`. Rerun native dedicated-client `osnadmin channel list` against its 9443 DNS endpoint and require HTTP 200 with `systemChannel:null`, `channels:null` before #18 retries a join. Keep full logs ignored and mode `0600`; do not print environment variables, keys or passwords.

~~~sh
set -eu
umask 077
name=orderer0
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate "$name"
docker inspect --format '{{.Id}}' "supplyledger-${name}-1" > ".runtime/m2-node-logs/${name}-after-join-limit-id"
! cmp -s ".runtime/m2-node-logs/${name}-before-join-limit-id" ".runtime/m2-node-logs/${name}-after-join-limit-id"
docker volume inspect --format '{{.Name}} {{.CreatedAt}}' "supplyledger_${name}_ledger" > ".runtime/m2-node-logs/${name}-join-limit-volume-after"
cmp ".runtime/m2-node-logs/${name}-join-limit-volume-before" ".runtime/m2-node-logs/${name}-join-limit-volume-after"
test "$(docker inspect --format '{{.State.Status}}' "supplyledger-${name}-1")" = running
docker logs "supplyledger-${name}-1" > ".runtime/m2-node-logs/${name}-join-limit-container.log" 2>&1
rg -F 'ChannelParticipation.MaxRequestBodySize = 1048576' ".runtime/m2-node-logs/${name}-join-limit-container.log"
~~~

Repeat the last block for `orderer1` and `orderer2` only after Orderer0's reviewed checkpoint, with separate native commands and logs. A successful HTTP status is necessary for a later join; after a join, also require the channel to appear and eventually report `active`. At that prejoin checkpoint, full T-NET-04 remained NOT RUN; #18 subsequently verified all three joined Orderers as active.

## One-time recovery from the first Seller Peer BCCSP startup failure

At source commit `45dab4215f482452c594abfd48221a550282d347`, all three Orderers had joined and the three CouchDBs started individually. Each CouchDB returned `/_up` HTTP 200 with `status=ok` when the scoped probe supplied its own credentials; this does not establish that `/_up` requires authentication. The first native `peer0-seller` Compose start returned exit 0, but its process exited 1 at `InitCmd` with `Cannot run peer because could not get peer BCCSP configuration`. Buyer and Carrier Peers were not started; no Peer joined the channel. Preserve the failed Seller container ID, `supplyledger_peer0_seller_ledger` volume and ignored `.runtime/m2-node-logs/peer0-seller-first-container.log`. Fabric v3.1.5 [requires a `peer.BCCSP` subtree at initialization](https://github.com/hyperledger/fabric/blob/v3.1.5/internal/peer/common/common.go#L150-L157); the pinned [sample `core.yaml`](https://github.com/hyperledger/fabric/blob/v3.1.5/sampleconfig/core.yaml#L305-L319) uses software BCCSP, SHA2 and 256-bit security. The three reviewed Peer templates now select `SW`, `SHA2`, `256` and each node's **own** `/run/supply/msp/keystore` read-only mount. The failure occurred before Peer TLS, Peer-to-CouchDB connectivity or channel readiness could be observed.

Only after this source fix is independently reviewed and integrated into the retained main checkout, stage six newly rendered configs in a **separate ignored output directory**. Do not move or replace the running Orderers' config files or restart their joined ledger containers. The staging and archive paths must be absent. Record the failed Seller container/volume identity, source commit and before snapshots first; no key or password value goes into tracked evidence. The same M1 identity manifest function used in the previous recovery provides a byte-for-byte continuity check.

~~~sh
set -eu
umask 077
test "$(docker inspect --format '{{.State.Status}}:{{.State.ExitCode}}' supplyledger-peer0-seller-1)" = exited:1
test -f .runtime/m2-node-logs/peer0-seller-first-container.log
for org in buyer carrier; do
  if docker inspect "supplyledger-peer0-${org}-1" > /dev/null 2>&1; then
    printf 'FAIL: peer0-%s container exists; inspect before replacing its config\n' "$org" >&2
    exit 1
  fi
done
test ! -e .runtime/m2-peer-bccsp-stage
test ! -L .runtime/m2-peer-bccsp-stage
test ! -e .runtime/m2-node-logs/network-config-before-peer-bccsp
test ! -L .runtime/m2-node-logs/network-config-before-peer-bccsp
python3 - <<'PY'
from pathlib import Path
from stat import S_IMODE
root = Path('.secrets')
assert root.is_dir() and not root.is_symlink()
assert S_IMODE(root.stat().st_mode) == 0o700
for subdir in ('couchdb', 'peer-couchdb'):
    directory = root / subdir
    assert directory.is_dir() and not directory.is_symlink()
    assert S_IMODE(directory.stat().st_mode) == 0o700
    assert {path.name for path in directory.iterdir()} == {
        'seller.env', 'buyer.env', 'carrier.env'}
    for path in directory.iterdir():
        assert path.is_file() and not path.is_symlink()
        assert S_IMODE(path.stat().st_mode) == 0o600
print('PASS: exact six existing 0600 credential files; stage cannot generate any')
PY
m1_file_hashes() {
  python3 - <<'PY'
from hashlib import sha256
from pathlib import Path
root = Path('.runtime/identities')
assert root.is_dir() and not root.is_symlink()
for path in sorted(root.rglob('*')):
    assert not path.is_symlink(), path
    if path.is_file():
        print(sha256(path.read_bytes()).hexdigest(), path.relative_to(root))
PY
}
git rev-parse HEAD > .runtime/m2-node-logs/peer-bccsp-source-commit
docker inspect --format '{{.Id}}' supplyledger-peer0-seller-1 > .runtime/m2-node-logs/peer0-seller-before-bccsp-id
docker volume inspect --format '{{.Name}} {{.CreatedAt}}' supplyledger_peer0_seller_ledger > .runtime/m2-node-logs/peer0-seller-ledger-before-bccsp
for name in orderer0 orderer1 orderer2; do
  test "$(docker inspect --format '{{.State.Status}}' "supplyledger-${name}-1")" = running
  docker inspect --format '{{.Id}}' "supplyledger-${name}-1" > ".runtime/m2-node-logs/${name}-before-peer-bccsp-id"
done
make verify-m1 > .runtime/m2-node-logs/m1-before-peer-bccsp.log 2>&1
m1_file_hashes > .runtime/m2-node-logs/m1-identity-before-peer-bccsp.sha256
shasum -a 256 .secrets/couchdb/*.env .secrets/peer-couchdb/*.env > .runtime/m2-node-logs/m2-env-before-peer-bccsp.sha256
shasum -a 256 .runtime/channel/supplychannel.block .runtime/channel/inspect-block.json > .runtime/m2-node-logs/channel-before-peer-bccsp.sha256
shasum -a 256 .runtime/network-config/orderer*.yaml > .runtime/m2-node-logs/orderer-config-before-peer-bccsp.sha256
make prepare-m2-nodes M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-bccsp-stage
make verify-m2-nodes M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-bccsp-stage
make verify-m2-node-block M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-bccsp-stage M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json
~~~

Before replacing any file, compare the stage with the old rendered configs. All three Orderers must be byte-identical. Each Peer may gain **only** the reviewed BCCSP mapping immediately after its ledger path; no MSP/TLS key path, CouchDB address, password or other setting may change.

~~~sh
python3 - <<'PY'
from pathlib import Path
old_dir = Path('.runtime/network-config')
stage_dir = Path('.runtime/m2-peer-bccsp-stage/network-config')
assert {p.name for p in old_dir.iterdir()} == {p.name for p in stage_dir.iterdir()}
for index in range(3):
    name = f'orderer{index}.yaml'
    assert (stage_dir / name).read_bytes() == (old_dir / name).read_bytes(), name
block = (b'  BCCSP:\n    Default: SW\n    SW:\n      Hash: SHA2\n'
         b'      Security: 256\n      FileKeyStore:\n'
         b'        KeyStore: /run/supply/msp/keystore\n')
for org in ('seller', 'buyer', 'carrier'):
    name = f'peer0-{org}.yaml'
    old = (old_dir / name).read_bytes()
    needle = b'  fileSystemPath: /var/hyperledger/production\n'
    assert old.count(needle) == 1, name
    assert (stage_dir / name).read_bytes() == old.replace(needle, needle + block), name
print('PASS: only three own-MSP Peer BCCSP mappings were added')
PY
~~~

Only if that comparison passes, archive and replace the **three Peer YAML files only**. Seller Peer is exited and Buyer/Carrier Peers have not started; the three joined Orderers keep their original config file bind sources and container IDs. Run the main-runtime preflight again, then compare M1, credential, block, decoded JSON and Orderer config snapshots. Stop and preserve all old/new files if any check fails.

~~~sh
set -eu
umask 077
test "$(docker inspect --format '{{.State.Status}}:{{.State.ExitCode}}' supplyledger-peer0-seller-1)" = exited:1
for org in buyer carrier; do
  if docker inspect "supplyledger-peer0-${org}-1" > /dev/null 2>&1; then
    printf 'FAIL: peer0-%s container exists; inspect before replacing its config\n' "$org" >&2
    exit 1
  fi
done
mkdir -m 700 .runtime/m2-node-logs/network-config-before-peer-bccsp
for org in seller buyer carrier; do
  mv ".runtime/network-config/peer0-${org}.yaml" .runtime/m2-node-logs/network-config-before-peer-bccsp/
  mv ".runtime/m2-peer-bccsp-stage/network-config/peer0-${org}.yaml" .runtime/network-config/
done
make verify-m2-nodes
make verify-m2-node-block M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json
make verify-m1 > .runtime/m2-node-logs/m1-after-peer-bccsp.log 2>&1
python3 - <<'PY' > .runtime/m2-node-logs/m1-identity-after-peer-bccsp.sha256
from hashlib import sha256
from pathlib import Path
root = Path('.runtime/identities')
assert root.is_dir() and not root.is_symlink()
for path in sorted(root.rglob('*')):
    assert not path.is_symlink(), path
    if path.is_file():
        print(sha256(path.read_bytes()).hexdigest(), path.relative_to(root))
PY
cmp .runtime/m2-node-logs/m1-identity-before-peer-bccsp.sha256 .runtime/m2-node-logs/m1-identity-after-peer-bccsp.sha256
shasum -a 256 .secrets/couchdb/*.env .secrets/peer-couchdb/*.env > .runtime/m2-node-logs/m2-env-after-peer-bccsp.sha256
cmp .runtime/m2-node-logs/m2-env-before-peer-bccsp.sha256 .runtime/m2-node-logs/m2-env-after-peer-bccsp.sha256
shasum -a 256 .runtime/channel/supplychannel.block .runtime/channel/inspect-block.json > .runtime/m2-node-logs/channel-after-peer-bccsp.sha256
cmp .runtime/m2-node-logs/channel-before-peer-bccsp.sha256 .runtime/m2-node-logs/channel-after-peer-bccsp.sha256
shasum -a 256 .runtime/network-config/orderer*.yaml > .runtime/m2-node-logs/orderer-config-after-peer-bccsp.sha256
cmp .runtime/m2-node-logs/orderer-config-before-peer-bccsp.sha256 .runtime/m2-node-logs/orderer-config-after-peer-bccsp.sha256
for name in orderer0 orderer1 orderer2; do
  test "$(docker inspect --format '{{.State.Status}}' "supplyledger-${name}-1")" = running
  docker inspect --format '{{.Id}}' "supplyledger-${name}-1" > ".runtime/m2-node-logs/${name}-after-peer-bccsp-id"
  cmp ".runtime/m2-node-logs/${name}-before-peer-bccsp-id" ".runtime/m2-node-logs/${name}-after-peer-bccsp-id"
done
~~~

After independent review of those checks, retry **only** the failed Seller Peer with `docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate peer0-seller`. Require a new running container ID, unchanged `supplyledger_peer0_seller_ledger` name/creation time, pinned image, own read-only MSP/TLS/config binds and own CouchDB credential environment without printing its values. Probe its gRPC TLS hostname and `/healthz` operations endpoint with the own TLS root/client identity; Fabric v3.1.5's [operations health check](https://github.com/hyperledger/fabric/blob/v3.1.5/docs/source/operations_service.rst#L340-L366) includes CouchDB when configured. Do not call `peer channel list` or a listening port proof of `supplychannel` readiness: #18 owns individual Peer joins. Only after Seller's reviewed startup should Buyer and Carrier Peers start one by one. Never use `reset`, change the #17 block or reissue M1 identities to fix this failure.

## One-time recovery from the second Seller Peer startup failure

The reviewed BCCSP migration retained all 273 M1 identity files, six credential env files, the original #17 block and decoded JSON, the three joined Orderer configs/IDs and the Seller ledger. The Seller-only force-recreate at source commit `c54a270f7dc356c96e886e4435484476eea97b30` produced a new container but exited `2`. Its ignored mode 0600 log `.runtime/m2-node-logs/peer0-seller-bccsp-container.log` shows BCCSP and CouchDB initialization, then Fabric v3.1.5's [startup guard](https://github.com/hyperledger/fabric/blob/v3.1.5/internal/peer/node/start.go#L534-L546): `VMEndpoint not set and no ExternalBuilders defined`. The log also warns that `peer.deliveryclient.blockGossipEnabled` was absent and defaulted to `true`; the old YAML placed that key at root. Retain both failed Seller logs, both old IDs and the same ledger; do not clear the initialized CouchDB databases.

M2 uses the tracked `builders/m2-chaincode-disabled/bin/{detect,build,release}` as an **explicit deny-all startup bridge**. All three programs return `1` for any input. The pinned Peer image has `/bin/sh` and executes them as an unprivileged user in a network-none, read-only offline probe. The builder directory contains only `bin/` and is mounted read-only at `/opt/supplyledger/m2-chaincode-disabled` for each Peer. Each `core.yaml` selects only that named absolute-path builder, has no `vm.endpoint`, and sets `peer.deliveryclient.blockGossipEnabled:false`. The exact program bytes/modes, Compose bind, source/rendered YAML and private env schema are preflighted. The functional self-built CCaaS builder, custom Peer image, chaincode installation and Peer→CCaaS mTLS remain M3 #22 **NOT RUN**.

Only after this source change is independently reviewed and integrated into the retained main checkout, stage new YAMLs in a fresh ignored directory. Require the second Seller container still `exited:2`, Buyer/Carrier Peer containers absent and the three Orderers/CouchDBs running. Check exactly six original 0600 credential env files before `prepare-m2-nodes`, since prepare mode could create a missing file. Record a fresh M1/env/block/Orderer manifest and container/volume IDs. Never move running Orderer configs or a named ledger. The stage and archive paths must be absent.

~~~sh
set -eu
umask 077
test "$(docker inspect --format '{{.State.Status}}:{{.State.ExitCode}}' supplyledger-peer0-seller-1)" = exited:2
test -f .runtime/m2-node-logs/peer0-seller-bccsp-container.log
test ! -e .runtime/m2-peer-deny-stage
test ! -L .runtime/m2-peer-deny-stage
test ! -e .runtime/m2-node-logs/network-config-before-peer-deny
test ! -L .runtime/m2-node-logs/network-config-before-peer-deny
for org in buyer carrier; do
  if docker inspect "supplyledger-peer0-${org}-1" > /dev/null 2>&1; then
    printf 'FAIL: peer0-%s container exists; inspect before config replacement\n' "$org" >&2
    exit 1
  fi
done
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
print('PASS: six original credential files exist and cannot be regenerated')
INNER
git rev-parse HEAD > .runtime/m2-node-logs/peer-deny-source-commit
docker inspect --format '{{.Id}}' supplyledger-peer0-seller-1 > .runtime/m2-node-logs/peer0-seller-before-peer-deny-id
docker volume inspect --format '{{.Name}} {{.CreatedAt}}' supplyledger_peer0_seller_ledger > .runtime/m2-node-logs/peer0-seller-ledger-before-peer-deny
for name in orderer0 orderer1 orderer2 couchdb0-seller couchdb0-buyer couchdb0-carrier; do
  test "$(docker inspect --format '{{.State.Status}}' "supplyledger-${name}-1")" = running
  docker inspect --format '{{.Id}}' "supplyledger-${name}-1" > ".runtime/m2-node-logs/${name}-before-peer-deny-id"
done
make verify-m1 > .runtime/m2-node-logs/m1-before-peer-deny.log 2>&1
python3 - <<'INNER' > .runtime/m2-node-logs/m1-identity-before-peer-deny.sha256
from hashlib import sha256
from pathlib import Path
root = Path('.runtime/identities')
for path in sorted(root.rglob('*')):
    assert not path.is_symlink(), path
    if path.is_file():
        print(sha256(path.read_bytes()).hexdigest(), path.relative_to(root))
INNER
shasum -a 256 .secrets/couchdb/*.env .secrets/peer-couchdb/*.env > .runtime/m2-node-logs/m2-env-before-peer-deny.sha256
shasum -a 256 .runtime/channel/supplychannel.block .runtime/channel/inspect-block.json > .runtime/m2-node-logs/channel-before-peer-deny.sha256
shasum -a 256 .runtime/network-config/orderer*.yaml > .runtime/m2-node-logs/orderer-config-before-peer-deny.sha256
make network-config
make prepare-m2-nodes M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-deny-stage
make verify-m2-nodes M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-deny-stage
make verify-m2-node-block M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-deny-stage M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json
~~~

Compare the stage against the old rendered YAMLs before replacing any bind source. The three Orderers must be byte-identical. Each Peer may differ **only** by moving `blockGossipEnabled:false` under `peer.deliveryclient` and replacing the empty external-builder list with the reviewed sole deny-all builder. The builder programs are tracked as mode 0755 despite the repository's general `bin/` ignore rule; `make network-config` checks their exact bytes, directory contents/modes and read-only mounts.

~~~sh
python3 - <<'INNER'
from pathlib import Path
old_dir = Path('.runtime/network-config')
stage_dir = Path('.runtime/m2-peer-deny-stage/network-config')
assert {p.name for p in old_dir.iterdir()} == {p.name for p in stage_dir.iterdir()}
for index in range(3):
    name = f'orderer{index}.yaml'
    assert (stage_dir / name).read_bytes() == (old_dir / name).read_bytes(), name
for org in ('seller', 'buyer', 'carrier'):
    name = f'peer0-{org}.yaml'
    old = (old_dir / name).read_bytes()
    root_delivery = b'deliveryclient:\n  blockGossipEnabled: false\n'
    old_builder = (b'chaincode:\n'
                   b'  # M3 #22 supplies the external builder and CCaaS image before deployment.\n'
                   b'  externalBuilders: []\n')
    peer_tls_anchor = b'    state:\n      enabled: false\n  tls:\n'
    assert old.count(root_delivery) == 1 and old.count(peer_tls_anchor) == 1, name
    assert old.count(old_builder) == 1, name
    expected = old.replace(peer_tls_anchor,
                           b'    state:\n      enabled: false\n'
                           b'  deliveryclient:\n    blockGossipEnabled: false\n  tls:\n', 1)
    expected = expected.replace(root_delivery, b'', 1)
    expected = expected.replace(old_builder,
        b'chaincode:\n'
        b'  # M2 denies all package installs. M3 #22 supplies the functional own builder.\n'
        b'  externalBuilders:\n'
        b'    - {name: m2-chaincode-disabled, path: /opt/supplyledger/m2-chaincode-disabled}\n', 1)
    assert (stage_dir / name).read_bytes() == expected, name
print('PASS: only three reviewed Peer delivery/builder changes; Orderers identical')
INNER
~~~

Archive/replace **only** the three Peer YAMLs after that byte comparison. Recheck all retained inputs and six Orderer/CouchDB container IDs before any retry. Stop and preserve the stage, archive and logs if an assertion fails.

~~~sh
set -eu
umask 077
test "$(docker inspect --format '{{.State.Status}}:{{.State.ExitCode}}' supplyledger-peer0-seller-1)" = exited:2
for org in buyer carrier; do
  if docker inspect "supplyledger-peer0-${org}-1" > /dev/null 2>&1; then
    printf 'FAIL: peer0-%s container exists; inspect before config replacement\n' "$org" >&2
    exit 1
  fi
done
mkdir -m 700 .runtime/m2-node-logs/network-config-before-peer-deny
for org in seller buyer carrier; do
  mv ".runtime/network-config/peer0-${org}.yaml" .runtime/m2-node-logs/network-config-before-peer-deny/
  mv ".runtime/m2-peer-deny-stage/network-config/peer0-${org}.yaml" .runtime/network-config/
done
make verify-m2-nodes
make verify-m2-node-block M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json
make network-config
make verify-m1 > .runtime/m2-node-logs/m1-after-peer-deny.log 2>&1
python3 - <<'INNER' > .runtime/m2-node-logs/m1-identity-after-peer-deny.sha256
from hashlib import sha256
from pathlib import Path
root = Path('.runtime/identities')
for path in sorted(root.rglob('*')):
    assert not path.is_symlink(), path
    if path.is_file():
        print(sha256(path.read_bytes()).hexdigest(), path.relative_to(root))
INNER
cmp .runtime/m2-node-logs/m1-identity-before-peer-deny.sha256 .runtime/m2-node-logs/m1-identity-after-peer-deny.sha256
shasum -a 256 .secrets/couchdb/*.env .secrets/peer-couchdb/*.env > .runtime/m2-node-logs/m2-env-after-peer-deny.sha256
cmp .runtime/m2-node-logs/m2-env-before-peer-deny.sha256 .runtime/m2-node-logs/m2-env-after-peer-deny.sha256
shasum -a 256 .runtime/channel/supplychannel.block .runtime/channel/inspect-block.json > .runtime/m2-node-logs/channel-after-peer-deny.sha256
cmp .runtime/m2-node-logs/channel-before-peer-deny.sha256 .runtime/m2-node-logs/channel-after-peer-deny.sha256
shasum -a 256 .runtime/network-config/orderer*.yaml > .runtime/m2-node-logs/orderer-config-after-peer-deny.sha256
cmp .runtime/m2-node-logs/orderer-config-before-peer-deny.sha256 .runtime/m2-node-logs/orderer-config-after-peer-deny.sha256
docker volume inspect --format '{{.Name}} {{.CreatedAt}}' supplyledger_peer0_seller_ledger > .runtime/m2-node-logs/peer0-seller-ledger-after-peer-deny
cmp .runtime/m2-node-logs/peer0-seller-ledger-before-peer-deny .runtime/m2-node-logs/peer0-seller-ledger-after-peer-deny
for name in orderer0 orderer1 orderer2 couchdb0-seller couchdb0-buyer couchdb0-carrier; do
  test "$(docker inspect --format '{{.State.Status}}' "supplyledger-${name}-1")" = running
  docker inspect --format '{{.Id}}' "supplyledger-${name}-1" > ".runtime/m2-node-logs/${name}-after-peer-deny-id"
  cmp ".runtime/m2-node-logs/${name}-before-peer-deny-id" ".runtime/m2-node-logs/${name}-after-peer-deny-id"
done
~~~

After independent review of the preserved-state checkpoint, use a separate native `docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate peer0-seller` invocation. Require a new **running** Seller ID, the same named ledger name/creation time, pinned image, exact two networks, own read-only config/MSP/TLS/public-root binds **and** the sole read-only deny-all builder bind, no Docker socket or published port. Its log must no longer contain either startup failure or the `peer.deliveryclient.blockGossipEnabled` default-to-true warning. From a scoped `supply-seller` tools container, verify the Peer 7051 certificate against the own TLS root and DNS name; use that own TLS client identity for operations `https://peer0.seller.supply.test:9444/healthz`. Require verified TLS, HTTP 200 and `status=OK`; Fabric v3.1.5 [registers a CouchDB health check](https://github.com/hyperledger/fabric/blob/v3.1.5/docs/source/operations_service.rst#L340-L366) when configured. A no-client-certificate operations request must fail at TLS. Keep full logs ignored and mode 0600; never print private key or CouchDB password values. Buyer/Carrier Peers and all Peer joins remain on hold until Seller's checkpoint is reviewed. A listener or `/healthz` alone does not prove a local `supplychannel` ledger; #18 owns each native `peer channel join`.

## Native first-run sequence and remaining steps

These are separate operations, not a `make network-up` shortcut. Before each operation, record source commit, version-lock SHA-256, image digest, Compose tier, command/exit code and redacted output under `evidence/m2/`.

1. After #17's native `configtxgen` and static block decode, compare the **actual decoded** three consenters' client/server certificate PEM bytes to each `ordererN-tls` signcert and the effective `General.Cluster.ClientCertificate`/shared `General.TLS.Certificate` paths. Confirm cert-key match, SAN and ordinary TLS root. Keep the generated block and JSON ignored.
2. Start `orderer0`, `orderer1`, `orderer2` **one at a time** using the merged Compose overlays and `up -d --no-deps <name>`; inspect each actual process, mount and image digest. No channel is joined at this step. For each 9443 endpoint, use a short-lived Orderer-only tools container with the ordinary `orderer-tls-ca.pem` as `osnadmin --ca-file` and the existing dedicated `osnadmin-client1-tls` cert/key as `--client-cert`/`--client-key`. `osnadmin channel list` should return HTTP 200, `systemChannel:null` and the observed prejoin `channels:null`. A request with no client certificate must fail at TLS; do not confuse CLI argument rejection with a handshake test. Record the server and client certificate fingerprints, exit/status and failure stage. #18's [three-node admin mTLS matrix](../evidence/m2/issue-18.md#admin-mtls-boundary-before-joining) has now passed; #18 owns the native channel joins.
3. After #18 has joined all three Orderers with individual `osnadmin channel join` commands, start `couchdb0-seller`, `couchdb0-buyer`, `couchdb0-carrier` separately, check credential-bearing `/_up` from scoped tool contexts without logging passwords, then start `peer0-seller`, `peer0-buyer`, `peer0-carrier` separately. The three CouchDBs have started; the first Seller Peer failure and recovery are recorded above. Check process/TLS/operations health and CouchDB connection. This is NET-06 component startup; Peer channel join and network-level readiness remain #18 work. Do not call a process that merely listens on 7051 ready for `supplychannel` or `supplycc`.

## T-NET-02 live inspection and evidence

After those nine services run, rerun `make network-config` and use a structured, redacted `docker inspect` assertion over all real Orderer, Peer, CouchDB and any extant CA containers. Check the locked image digest and expected command, status, exact network membership/DNS, no published management ports, no Docker socket, each node's own read-only identity binds, no cross-organization private MSP, and a distinct named ledger/data volume. Inspect **all** runtime mounts, including any Docker-image-created anonymous parent mounts, and verify ledger/WAL/snapshot paths reside on the declared named volumes. Check the tracked repository and image build contexts contain no credentials or private key material; report counts/paths/fingerprints only. Preserve sanitized actual results, not a copied raw `docker inspect` JSON object.

Record T-NET-02 as **NOT RUN** until these live checks succeed. The three-node admin mTLS matrix and full §20.1 `T-NET-04` are **PASS** in [#18 evidence](../evidence/m2/issue-18.md); Peer joins, current channel configuration, three-organization equal-height block-hash comparison and chaincode/transaction checks remain **NOT RUN** until their owners execute them. The canonical `genesisHash` field stays NOT RUN until NET-08 records the real block-0 header identity; the matching fetched block files' SHA-256 is an artifact checksum. No txId or validation code is invented for offline preflight.
