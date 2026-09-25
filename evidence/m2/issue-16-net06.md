# M2 #16 — NET-06 CouchDB starts and Seller Peer startup failures

- Test: `M2-I16-NET06-01` (SPEC.md §§5.4 NET-06, 19.1; §20.1 T-NET-02). **FAIL** at Seller Peer process initialization; three CouchDB startup and `/_up` probes **PASS** at their stated scope. Full NET-06 and `T-NET-02`: **NOT RUN**.
- Source commit at live attempt: `45dab4215f482452c594abfd48221a550282d347`; `versions.lock.yaml` SHA-256: `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`. Host `darwin/arm64`, Docker `linux/arm64`. Compose project `supplyledger`, overlays `bootstrap.yaml` + `ca.yaml` + `network.yaml`, profiles `bootstrap` and `ca`.
- Prepared data: retained M1 node MSP/TLS identities, six ignored organization-scoped credential env files and rendered node YAMLs, original #17 block SHA-256 `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a` (27,946 bytes). All three Orderers had independently joined `supplychannel` with HTTP 201 and `active`/height 1 per [#18 NET-05 evidence](issue-18.md). This block **file checksum is not the canonical `genesisHash`**; NET-08 remains **NOT RUN**.
- Locked images: CouchDB `docker.io/library/couchdb:3.4.2@sha256:2817ad50b5c5cf7461f5963670466197426605a790a19a6208068c509a2d8a59`; Peer `docker.io/hyperledger/fabric-peer:3.1.5@sha256:e07c735b6f2d131315f3ae6e582c5aa602143d9d14805bb98be8ebc9d6baa82c`.

## Individual native starts and probes

Each command below was issued separately in the retained main checkout with `--no-deps`. The common actual Compose prefix was `docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps`; the final service argument and process outcome are recorded per row. Compose exit `0` alone is not a health claim. Each CouchDB `/_up` probe used a separate short-lived, read-only `supply-tools:m0-fabric3.1.5-ca1.5.22` container on **only** that organization's network. Its own existing credential env file supplied curl's credentials through stdin with `curl --config -`; no password appeared in the command line or logged output. `/_up` success does not prove that this endpoint enforces authentication.

The first-run probes' exact organization, DNS target, exit marker and ignored output are mapped below; all tabled log/exit names are under `.runtime/m2-node-logs/`. The following sanitized literal Docker/curl form was also executed once per organization as a read-only evidence recheck, with `org` set separately to `seller`, `buyer` and `carrier`. It gives the credentials to curl through stdin, writes only HTTP status and the selected JSON status to the ignored log, and writes the actual process exit to a separate ignored file. All three recheck outputs byte-match their original first-run output logs. No Peer was retried.

~~~sh
set -u
umask 077
org=seller  # substitute buyer, then carrier in separate invocations
log=".runtime/m2-node-logs/couchdb0-${org}-auth-up-recheck.log"
docker run --rm --pull=never --platform linux/arm64 \
  --network "supply-${org}" --read-only --tmpfs /tmp \
  --user "$(id -u):$(id -g)" \
  --env-file ".secrets/couchdb/${org}.env" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'printf "user = \"%s:%s\"\n" "$COUCHDB_USER" "$COUCHDB_PASSWORD" | \
     curl --config - --silent --show-error --fail --max-time 10 \
       --output /tmp/couchdb-up.json --write-out "http_code=%{http_code}\n" \
       "http://couchdb0.$1.supply.test:5984/_up"; \
   jq -er '\''select(.status == "ok") | "body.status=" + .status'\'' /tmp/couchdb-up.json' \
  sh "$org" > "$log" 2>&1
result=$?
printf '%s\n' "$result" > ".runtime/m2-node-logs/couchdb0-${org}-auth-up-recheck.exit"
exit "$result"
~~~

| `org`; DNS target on its sole container network | Original first-run output / exit files | Read-only recheck output / exit files | Expected and actual |
| --- | --- | --- | --- |
| `seller`; `couchdb0.seller.supply.test:5984` on `supply-seller` | `couchdb0-seller-auth-up.log` / `.exit` | `couchdb0-seller-auth-up-recheck.log` / `.exit` | Exit `0`, HTTP `200`, `body.status=ok` / same |
| `buyer`; `couchdb0.buyer.supply.test:5984` on `supply-buyer` | `couchdb0-buyer-auth-up.log` / `.exit` | `couchdb0-buyer-auth-up-recheck.log` / `.exit` | Exit `0`, HTTP `200`, `body.status=ok` / same |
| `carrier`; `couchdb0.carrier.supply.test:5984` on `supply-carrier` | `couchdb0-carrier-auth-up.log` / `.exit` | `couchdb0-carrier-auth-up-recheck.log` / `.exit` | Exit `0`, HTTP `200`, `body.status=ok` / same |

| Service argument; actual Compose exit | Scoped live observation | Judgment |
| --- | --- | --- |
| `couchdb0-seller`; `0` | Container `7583fbe9b3b44976dd255c832ae2dac392e2f451fd8ef7e6a057f50233fd0638` running; own `supply-seller` network and named `supplyledger_couchdb0_seller_data` volume created `2026-09-25T15:08:43Z`; pinned image, no published host port or Docker socket. Credential-bearing `http://couchdb0.seller.supply.test:5984/_up` probe exit `0`, HTTP `200`, `body.status=ok`. | **PASS**, CouchDB process and scoped `/_up` |
| `couchdb0-buyer`; `0` | Container `66c109bae235ffae1d503d74998784e4cebd7bb07c2a48b51528eef68d85d7a6` running; own `supply-buyer` network and named `supplyledger_couchdb0_buyer_data` volume created `2026-09-25T15:09:23Z`; same pinned image, no published host port or Docker socket. Own `/_up` probe exit `0`, HTTP `200`, `body.status=ok`. | **PASS**, CouchDB process and scoped `/_up` |
| `couchdb0-carrier`; `0` | Container `c03cedec53fe965231e02089f8cfa0223b19f008f7873dc5f6796a7fafd6f459` running; own `supply-carrier` network and named `supplyledger_couchdb0_carrier_data` volume created `2026-09-25T15:09:49Z`; same pinned image, no published host port or Docker socket. Own `/_up` probe exit `0`, HTTP `200`, `body.status=ok`. | **PASS**, CouchDB process and scoped `/_up` |
| `peer0-seller`; `0` | Compose created container `980039f65ebf366c82ab8dce2cb46e9aca2c5dee0be68b78d238faefd6e15002` and named `supplyledger_peer0_seller_ledger` volume created `2026-09-25T15:10:23Z`. Actual pinned-image process then reported `exited:1`; its one-line `InitCmd` error was `Cannot run peer because could not get peer BCCSP configuration`. | **FAIL**, Peer BCCSP configuration before usable Peer process or channel join |

Actual Compose stdout/stderr and exit markers, the three scoped `/_up` outputs and exits, the one-line Seller container log, and its process/ledger identities remain only in ignored, mode `0600` `.runtime/m2-node-logs/` files (`0700` directory) in the retained main checkout. Files include `couchdb0-{seller,buyer,carrier}-first-start.{log,exit}`, `couchdb0-{seller,buyer,carrier}-auth-up.{log,exit}`, `peer0-seller-first-start.{log,exit}`, `peer0-seller-first-container.log`, `peer0-seller-first-process-status` and `peer0-seller-first-ledger-identity`. The six credential env files and original #17 block matched their pre-start SHA-256 manifests after the failure; secret values were not copied into tracked evidence.

Fabric v3.1.5 [`InitBCCSPConfig`](https://github.com/hyperledger/fabric/blob/v3.1.5/internal/peer/common/common.go#L150-L157) returns this exact error when `viper.Sub("peer.BCCSP")` is absent. All three tracked and old rendered Peer `core.yaml` files lack that subtree. The pinned [sample `core.yaml`](https://github.com/hyperledger/fabric/blob/v3.1.5/sampleconfig/core.yaml#L305-L319) supplies software BCCSP, SHA2 and 256-bit security. The #16 source correction adds that configuration with each Peer's own `/run/supply/msp/keystore`; its separate staged replacement and Seller-only force-recreate procedure is in the [runbook](../../docs/m2-node-config-native.md#one-time-recovery-from-the-first-seller-peer-bccsp-startup-failure). **Those migration and retry steps had not run at this first-failure checkpoint.**

Buyer and Carrier Peer startups, Peer TLS/operations checks, Peer-to-CouchDB connectivity, all three `peer channel join` commands, Peer local `supplychannel` ledger checks, and full `T-NET-02` Docker/repository inspection are **NOT RUN**. No transaction was submitted during this startup failure: no txId or validation code exists for it, and no Peer block height is claimed. The independently observed Orderer height 1 is not Peer readiness.

## Reviewed BCCSP migration and second Seller Peer failure

- Test: `M2-I16-NET06-02` (SPEC.md §§5.4 NET-06, 19.1; §20.1 T-NET-02). **PASS** for the guarded, Peer-only BCCSP config migration and retained state; **FAIL** for Seller Peer process startup at a later Fabric guard. Full NET-06 and `T-NET-02` remain **NOT RUN**.
- Source commit at execution: `c54a270f7dc356c96e886e4435484476eea97b30`, clean local/remote main before migration. Version lock SHA-256, Compose tier, pinned images and original #17 block are the same as above. Canonical `genesisHash`, txId, Peer block height and validation code: **NOT RUN**; no channel or transaction request was made by this retry.
- Prepared data: old failed Seller container `980039f65ebf366c82ab8dce2cb46e9aca2c5dee0be68b78d238faefd6e15002` exited `1`; Buyer/Carrier Peer containers absent; three Orderers and three CouchDBs retained. Original `.runtime/channel/supplychannel.block` and decoded JSON SHA-256 were checked against #17 before any config change.

| Actual operation | Expected | Actual | Judgment |
| --- | --- | --- | --- |
| Execute the first three shell blocks of the [reviewed Peer-only BCCSP recovery procedure](../../docs/m2-node-config-native.md#one-time-recovery-from-the-first-seller-peer-bccsp-startup-failure): exact six pre-existing 0600 credential-file gate; `make verify-m1`; before manifests; `make prepare-m2-nodes M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-bccsp-stage`; staged `make verify-m2-nodes` and `make verify-m2-node-block M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-bccsp-stage M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json`; byte-level diff; archive/replace only three Peer YAMLs; main-runtime verifiers and after manifests | Add only three own-MSP BCCSP mappings; keep all Orderer YAMLs, M1 identities, six credential env files, original block and decoded JSON byte-identical; retain Orderer IDs and Seller ledger | Each of the stage, exact-delta and migration blocks exited `0`. Byte comparison found exactly one BCCSP mapping added per Peer and byte-identical Orderer YAMLs. `make verify-m1`, staged/main node verifiers and native decoded-block comparison passed. Before/after manifests matched for all 273 M1 identity files, six env files, original block/inspect JSON, three Orderer configs and three unchanged running Orderer IDs. Seller ledger name/creation remained `supplyledger_peer0_seller_ledger` / `2026-09-25T15:10:23Z`. | **PASS**, ignored config migration only |
| `docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate peer0-seller` | Recreate only exited Seller with reviewed BCCSP config, new running container, same ledger | Compose exit `0`; Seller ID changed to `bfb12bc843542e7a17a74b3045f458bd7883860f2edf9b4a555ea2b2d752431d`, pinned Peer image unchanged, exact `supply-fabric` and `supply-seller` networks, own read-only MSP/TLS/config/public-root binds, no published port/socket, same named ledger creation. Actual process exited **`2`** after BCCSP, TLS setup, LedgerMgr and CouchDB initialization. It created `_users`, `_replicator` and `fabric__internal`, then panicked: `VMEndpoint not set and no ExternalBuilders defined`. The log also warned `peer.deliveryclient.blockGossipEnabled is not set; defaulting to true`; the old YAML placed `deliveryclient` at root instead of under `peer`. | **FAIL**, later chaincode builder startup guard; no usable Peer endpoint |

The original BCCSP `exited:1` log remains untouched. The second Compose output/exit, full second container log, source commit, staged/archive configs, checksums, old/new IDs and ledger identity are retained only under ignored `.runtime/m2-node-logs/` in the main checkout. The new key files are `peer-bccsp-stage.{log,exit}`, `peer-bccsp-exact-delta.{log,exit}`, `peer-bccsp-migrate.{log,exit}`, `peer0-seller-bccsp-retry-start.{log,exit}` and `peer0-seller-bccsp-container.log`; selected logs and markers are mode 0600 under a 0700 directory. The second failure log contains none of the six credential-file password values. A fresh read-only comparison after exit `2` confirmed the 273 identity files, six env files, block/inspect JSON, Orderer configs and running Orderer IDs still match the pre-migration snapshots.

Pinned Fabric v3.1.5 [`node.serve`](https://github.com/hyperledger/fabric/blob/v3.1.5/internal/peer/node/start.go#L534-L546) panics if both the Docker VM endpoint and the external-builder list are empty. Setting a Docker VM endpoint would enter the Docker client path and violate CON-08/ADR-002. The candidate M2 source correction configures one repository-owned, read-only, executable external builder that **rejects every package**, and moves `blockGossipEnabled:false` under `peer.deliveryclient`. The [second safe migration procedure](../../docs/m2-node-config-native.md#one-time-recovery-from-the-second-seller-peer-startup-failure) and a fresh Seller retry are **NOT RUN** here. The functional self-built CCaaS builder, custom Peer image, chaincode installation and Peer→CCaaS mTLS remain M3 #22 work. Buyer/Carrier Peer startup, Peer TLS/operations probes and all Peer channel joins remain **NOT RUN**.

## Deny-all builder correction: offline checkpoint

- Test: `M2-I16-NET06-03` (SPEC.md §§5.4 NET-06, 19.1; §20.1 T-NET-02). **PASS** for source/Compose preflight, negative controls and direct offline script rejection only. Full NET-06 and live `T-NET-02` are **NOT RUN**.
- Source at this offline execution: uncommitted corrective branch `issue/16-m2-node-config` based on `c54a270f7dc356c96e886e4435484476eea97b30`, pending independent review. Version lock SHA-256 remained `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`. Compose tier and original block checksum remain as stated above. No genesisHash, txId, Peer height or validation code was produced.
- Prepared data: retained M1 runtime and native #17 decoded block JSON were **read only** for the static checks; a separate temporary directory held newly rendered test configs and credentials. The pinned Peer image was used offline with no network or private identity/credential mounts. The failed Seller container, ledger, joined Orderers, CouchDBs and main ignored Peer configs were not changed by these probes.

| Actual command/check | Expected and actual | Judgment |
| --- | --- | --- |
| `make network-config`; `make test-m2-compose` | Source Compose model accepted with exact read-only builder binds, no Docker endpoint/socket or CORE builder override; baseline and 17 negative mutations passed, including changed detector and extra builder-root file rejection. | **PASS**, static only |
| `make test-m2-nodes M2_SOURCE_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime M2_INSPECT_BLOCK=/Users/yjydist/Code/supplyledger-lab/.runtime/channel/inspect-block.json` | 17 reported subchecks passed. Source/rendered YAML enforces the sole builder, nested `peer.deliveryclient.blockGossipEnabled:false`, absent VM endpoint and private env override rejection; original native #17 consenter certificate comparisons passed. | **PASS**, static only |
| `make verify-m1 M1_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime` | Retained M1 identity/MSP/TLS verification passed. Its live handshake tests remain **NOT RUN**. | **PASS**, M1 static only |
| Separate temporary render from the retained M1 runtime, followed by the [documented byte comparison](../../docs/m2-node-config-native.md#one-time-recovery-from-the-second-seller-peer-startup-failure) | All three rendered Orderer YAMLs were byte-identical to the retained main runtime; each Peer YAML differed only by the nested delivery setting and sole builder mapping. The real main ignored configs were not replaced. | **PASS**, temporary files only |

The following literal invocation was run from the corrective worktree. It used the locked Peer image digest, `/bin/sh` present in that image, a read-only root, read-only public builder bind, no network, no private mounts and UID:GID `65534:65534`. The shell asserted **each** of `detect`, `build` and `release` was executable, exited exactly `1` and emitted only the fixed rejection message. Docker itself exited `0` after those assertions; this does not claim a Fabric chaincode installation attempt.

~~~sh
docker run --rm --pull=never --platform linux/arm64 --network none --read-only --tmpfs /tmp \
  --user 65534:65534 \
  --mount type=bind,src="$PWD/builders/m2-chaincode-disabled",dst=/opt/supplyledger/m2-chaincode-disabled,readonly \
  --entrypoint sh \
  docker.io/hyperledger/fabric-peer:3.1.5@sha256:e07c735b6f2d131315f3ae6e582c5aa602143d9d14805bb98be8ebc9d6baa82c \
  -ceu 'test -x /bin/sh; for name in detect build release; do
    path="/opt/supplyledger/m2-chaincode-disabled/bin/$name"
    test -x "$path"
    set +e; output="$($path 2>&1)"; result=$?; set -e
    test "$result" -eq 1
    test "$output" = "M2 chaincode builder disabled; use the M3 #22 builder"
    printf "PASS: %s exits 1 in pinned Peer image\n" "$name"
  done'
~~~

Actual output was three `PASS` lines, one per program, and Docker exit `0`. The tracked `bin/{detect,build,release}` files have Git mode `100755` (filesystem mode `0755`) and SHA-256 values `581ef8cf5c519b603a5b116aa4d7e48aff620249704d77b8458b7cb0074ae33f`, `d322c173f8f7708acf3691dd70aae39a9251662d2064aecae13e2066209fbc14` and `76377bfa9730dab505a56e7f525e9cca0fcb1edb90131a431a3e1649c5a6f587`, respectively. This offline check is separate from Seller's prior **FAIL** at process exit `2`. The guarded ignored-config migration, Seller retry, Buyer/Carrier starts, Peer TLS/operations health, all Peer joins, full NET-06 and live `T-NET-02` were **NOT RUN at this offline checkpoint**; the subsequent Seller-only results follow.

## Guarded Peer migration and Seller-only live retry

- Test: `M2-I16-NET06-04` (SPEC.md §§5.4 NET-06, 19.1; §20.1 T-NET-02). **PASS** for the guarded config migration and Seller process/TLS/operations checkpoint. Full NET-06, all-Peer `T-NET-02`, Peer channel joins and channel readiness are **NOT RUN**.
- Source commit at execution: clean local and GitHub main `28c6c8ac06ee0178ee9a957b4179160890dd37a6`. `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`; host `darwin/arm64`, Docker `linux/arm64`; Compose project/overlays/profiles and pinned Peer image as above. Original #17 block SHA-256 `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a` and native decoded JSON SHA-256 `2e3c9994819ae2f5ec5c6a5741f6bf558d0c364380ffee3cac10930f8f4b4e09`.
- Initial state: Seller's second failed container `bfb12bc843542e7a17a74b3045f458bd7883860f2edf9b4a555ea2b2d752431d` was `exited:2`; its first `exited:1` predecessor and both failure logs remained retained. Buyer/Carrier Peer containers were absent. The three joined Orderers and three CouchDBs were running; Seller ledger `supplyledger_peer0_seller_ledger` had creation timestamp `2026-09-25T15:10:23Z`.

The first, second and third `sh` blocks in the [reviewed second Seller recovery procedure](../../docs/m2-node-config-native.md#one-time-recovery-from-the-second-seller-peer-startup-failure) were executed separately in the retained main checkout. A Python wrapper extracted each literal block and passed it to `/bin/sh -eu`, redirecting stdout/stderr to a fresh ignored mode-0600 `.runtime/m2-node-logs/peer-deny-{stage,exact-delta,migrate}.log` and recording each actual exit in the paired `.exit` file. Each exited `0`; the commands inside those three linked blocks are the exact migration commands. No container was restarted during staging or replacement.

| Native operation and expected result | Actual result | Judgment |
| --- | --- | --- |
| Pre-stage exact six-file credential/mode gate, Seller `exited:2` and Buyer/Carrier absent gate, `make verify-m1`, source/identity/credential/block/Orderer and service-ID snapshots, `make network-config`, `make prepare-m2-nodes M2_OUTPUT_RUNTIME_DIR=.runtime/m2-peer-deny-stage`, staged node/block verifiers | Stage block exit `0`; no credential regeneration; six new ignored YAMLs were verified before replacing any bind source. | **PASS**, stage only |
| Run the documented byte comparison: Orderer YAMLs unchanged; each Peer YAML only moves `blockGossipEnabled:false` under `peer` and selects the sole deny-all builder | Exact-delta block exit `0`; three Orderers byte-identical, three Peers matched those exact substitutions. | **PASS**, pre-replacement comparison |
| Archive/replace **only** the three Peer YAMLs, run main-runtime node/block/Compose/M1 verifiers, compare retained inputs, Seller volume and six running Orderer/CouchDB IDs | Migration block exit `0`; all 273 M1 identity files, six original env files, block plus decoded JSON, and three Orderer YAMLs matched pre-migration hashes. Seller named ledger name/creation and six service IDs stayed identical. | **PASS**, ignored config migration |
| `docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate peer0-seller` | Compose exit `0`; new Seller ID `7adb02032008cbbfaa1aed2d4cd0538b1c2254afa960a5b55af2387f9446fe73`, process `running`, exit code `0`; same ledger name/creation, pinned image, exactly `supply-fabric` and `supply-seller` networks, own read-only MSP/TLS/config/public-root mounts, sole read-only tracked builder bind, no Docker socket or published port. | **PASS**, Seller process only |

The three Orderer IDs remained `eaecd7616246f2458c7ac929f205110205df0ef83dbdaa86cbaab878620`, `2c85e897e37fa4056c4847f02c4ff1d9bbf4671aee8e256c18db291883b4dfe6` and `f260c67f163c31fb8c5a16425459166e09bc6a6970345f74238d7c4e8425f19c`; the three CouchDB IDs remained `7583fbe9b3b44976dd255c832ae2dac392e2f451fd8ef7e6a057f50233fd0638`, `66c109bae235ffae1d503d74998784e4cebd7bb07c2a48b51528eef68d85d7a6` and `c03cedec53fe965231e02089f8cfa0223b19f008f7873dc5f6796a7fafd6f459`. All six were still running at the post-retry read-only check. The 273-file M1, six-file env, two-file block/JSON and three-file Orderer config manifests still matched **after** Seller's retry; no values or private-key hashes appear here.

The first read-only Docker inspection script exited `1` solely because it compared Docker Desktop's bind source `/host_mnt/Users/.../builders/m2-chaincode-disabled` directly to the host's `/Users/...` path. It did not change a container. The repeated inspection normalized the `/host_mnt` prefix and passed the exact source, read-only flag, own MSP/TLS/config mounts, named ledger, image, networks and absent socket/ports. The new Seller log's effective configuration dump contains `blockgossipenabled: false` and the sole `m2-chaincode-disabled` builder; neither the earlier BCCSP error, VM/external-builder panic nor the `blockGossipEnabled` default-to-true warning appears. The log remains ignored and mode 0600 because the effective dump may include private settings.

Three separate short-lived native tool containers then probed Seller on only `supply-seller`. The exact sanitized commands below correspond to ignored mode-0600 `peer0-seller-peer-deny-{grpc-tls,operations-health,operations-no-client}.{log,exit}` files. `$PWD` was the retained main checkout; `$(id -u):$(id -g)` resolved to `501:20`. The client key was selected within the container from the Seller Peer TLS keystore and never printed or copied.

~~~sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/run/trust/seller-tls-ca.pem,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'openssl s_client -connect peer0.seller.supply.test:7051 \
    -servername peer0.seller.supply.test -verify_hostname peer0.seller.supply.test \
    -verify_return_error -CAfile /run/trust/seller-tls-ca.pem -brief < /dev/null'

docker run --rm --pull=never --platform linux/arm64 --network supply-seller \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/run/trust/seller-tls-ca.pem,readonly" \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/seller-peer0-tls/msp,dst=/run/tls,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/tls/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; \
   curl --silent --show-error --fail --max-time 10 \
     --cacert /run/trust/seller-tls-ca.pem --cert /run/tls/signcerts/cert.pem --key "$1" \
     --write-out "\nhttp_code=%{http_code}\n" \
     https://peer0.seller.supply.test:9444/healthz'

docker run --rm --pull=never --platform linux/arm64 --network supply-seller \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/run/trust/seller-tls-ca.pem,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'curl --verbose --fail --max-time 10 --cacert /run/trust/seller-tls-ca.pem \
    --output /tmp/no-client-response https://peer0.seller.supply.test:9444/healthz'
~~~

The gRPC TLS probe exited `0`, negotiated TLS 1.3 and printed `Verification: OK` for the Seller Peer DNS name and root. The own-cert operations mTLS probe exited `0`, returned HTTP `200` and `{"status":"OK",...}`. In Fabric v3.1.5, [the operations health endpoint includes the configured CouchDB check](https://github.com/hyperledger/fabric/blob/v3.1.5/docs/source/operations_service.rst#L340-L366); this establishes Seller's health check at this instant, not its local channel ledger. The no-client operations probe exited `56`: its verbose log first says `SSL certificate verify ok`, then records the TLS 1.3 `certificate required` alert. No application-level HTTP status was accepted without a client certificate.

Buyer and Carrier Peers were not started. No `peer channel join`, channel-list, endorsement, chaincode lifecycle or transaction command ran in this checkpoint. Full NET-06 and `T-NET-02` remain **NOT RUN** until all three Peers and the full live inspection are complete; Peer-local channel height/hash, canonical `genesisHash`, txId and validation code are **NOT RUN** or nonexistent for this startup-only work. The original two Seller failure logs and named ledger are retained.

## First Seller prejoin list failure and in-process system-chaincode repair

- Test: `M2-I16-NET06-05` (SPEC.md §§5.4 NET-06, 19.1). The first native Seller `peer channel list` **FAIL** is recorded with its [exact scoped Docker command and ignored log](issue-18.md#seller-first-native-peer-prejoin-list-failure-net-06) as #18 `M2-I18-NET06-01`. Its execution source commit was clean local/remote main `22af10ed8dde301fc77b38aa437e5db844d07168`; lock SHA-256, Compose tier and original block checksum remained as above. No Peer join ran.
- Actual failure: the CLI exited `1` after gRPC reached `READY`, then received status `500` while locally simulating `cscc`: no registered in-process `cscc` handler existed, so the Peer tried to read missing `/var/hyperledger/production/chaincodes/cscc.syscc`. The original mode-0600 `.runtime/m2-issue18-peer-logs/seller-pre-join-list.log` SHA-256 was `44a6deedcf81af8bf285fee6ac8528f55fb10bd89ae02c7aa6da05ac9b12b3bb`. It records a failed proposal **attempt** ID, not a submitted or committed transaction; no Peer block height or validation code resulted. The Seller log showed `cscc`, `qscc` and `_lifecycle` skipped as not enabled. Buyer and Carrier prejoin lists and all three joins remain **NOT RUN**.
- Root cause from pinned Fabric v3.1.5: [`chaincode.GlobalConfig`](https://github.com/hyperledger/fabric/blob/v3.1.5/core/chaincode/config.go#L64-L67) starts with an empty `SCCAllowlist` and reads `chaincode.system`; [`node.serve`](https://github.com/hyperledger/fabric/blob/v3.1.5/internal/peer/node/start.go#L770-L779) deploys only allowlisted `_lifecycle`, `cscc` and `qscc`. [`DeploySysCC`](https://github.com/hyperledger/fabric/blob/v3.1.5/core/scc/scc.go#L59-L85) launches those built-ins in process and bypasses the user-chaincode builder. The v3.1.5 sample includes legacy `lscc`, but this pinned startup loop does not deploy it.

The corrective eight-path source tree is based on integrated main `69729efc5373e4870eda0f15e0fe7be0abc0e9fb` at this review checkpoint. Three Peer templates now enable exactly the three deployed built-ins under `chaincode.system`; source and rendered preflight reject omitted, disabled, extra and root-level entries. The existing deny-all builder, absent VM endpoint, pinned image and all three named Peer ledgers remain the intended M2 boundary. Fresh `make network-config` and `make test-m2-compose` passed (baseline plus 18 reported negative mutations); `make test-m2-nodes M2_SOURCE_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime M2_INSPECT_BLOCK=/Users/yjydist/Code/supplyledger-lab/.runtime/channel/inspect-block.json` passed 19 reported subchecks, including source/rendered allowlist mutations and original #17 consenter byte comparison. A separate temporary render from the retained M1 runtime passed the [documented exact byte comparison](../../docs/m2-node-config-native.md#one-time-recovery-from-the-first-seller-peer-channel-list-proposal-status-500): the three Orderer YAMLs stayed identical, and each Peer YAML gained only the allowlist. This static PASS is **not** a live CSCC or channel-list result.

The guarded [Peer-only stage/stop/replace/recreate procedure](../../docs/m2-node-config-native.md#one-time-recovery-from-the-first-seller-peer-channel-list-proposal-status-500), a new `peer channel list`, all Peer joins, channel-local block checks, functional user chaincode builder/CCaaS, full NET-06 and current-state `T-NET-02` are **NOT RUN** at this corrective review checkpoint. No runtime config file, identity, credential, original block, service container or named ledger has been changed by this diff. The later Seller-only prejoin-list retry is recorded below; #18 still owns the individual Peer joins and post-join checks.

## Guarded system-chaincode migration and Seller-only prejoin list

- Test: `M2-I16-NET06-06` (SPEC.md §§5.4 NET-06, 19.1; §20.1 T-NET-02). **PASS** for Peer-only ignored-config migration, Seller process/TLS/operations startup, in-process system-chaincode deployment and an empty native prejoin channel list. Buyer/Carrier restart, Peer joins, channel readiness, full NET-06 and current-container `T-NET-02` remain **NOT RUN**.
- Execution source: clean local and GitHub main `b69082a45b70fe7f2240cc668281fd000d35b345`; `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`. Host `darwin/arm64`, Docker `linux/arm64`; Compose project `supplyledger`, overlays `bootstrap.yaml` + `ca.yaml` + `network.yaml`, profiles `bootstrap` and `ca`, pinned Peer image listed above. The original #17 block file remained 27,946 bytes with SHA-256 `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a`; decoded JSON SHA-256 `2e3c9994819ae2f5ec5c6a5741f6bf558d0c364380ffee3cac10930f8f4b4e09`. These are artifact checksums, **not** the canonical `genesisHash`.
- Initial state: all three Peers and six Orderer/CouchDB services were running. Seller ID was `7adb02032008cbbfaa1aed2d4cd0538b1c2254afa960a5b55af2387f9446fe73`; Buyer `07b85055d75c9920eb420c26b466107f5ccd6eded31c747697ea73ee79052468`; Carrier `360cd8d63e446d300be94b15ea30fdd4acfe3e506e3e9c094d7292f8b344750a`. The original Seller prejoin-list **FAIL** log remained at `.runtime/m2-issue18-peer-logs/seller-pre-join-list.log` with SHA-256 `44a6deedcf81af8bf285fee6ac8528f55fb10bd89ae02c7aa6da05ac9b12b3bb`.

The first three literal `sh` blocks of the [reviewed system-chaincode recovery procedure](../../docs/m2-node-config-native.md#one-time-recovery-from-the-first-seller-peer-channel-list-proposal-status-500) were copied without changing their commands into the following ignored mode-0600 command files and run separately by `bash <file>`. Each stdout/stderr stream and actual process exit was captured to a paired ignored mode-0600 `.log` and `.exit` file; the command files themselves make the exact native `make`, Docker inspect/stop, hash and move steps reproducible without embedding private values in tracked evidence.

| Executed command file, SHA-256 | Actual exit and observation | Judgment |
| --- | --- | --- |
| `bash .runtime/m2-node-logs/peer-system-stage-command.sh` (`be5df8fc6b241cc5d548ffe9bebe177d0e512b4dcb793057694b9663254203f8`); `peer-system-stage-command.{log,exit}` | `0`; exact six existing mode-0600 credentials, nine running starting IDs, original failure-log hash, M1/env/block/Orderer/ledger snapshots; `make verify-m1`, `make network-config`, staged `prepare-m2-nodes`, staged node and decoded-block verifiers passed. No live bind source changed. | **PASS**, stage |
| `bash .runtime/m2-node-logs/peer-system-exact-delta-command.sh` (`73dc4fa9f7f4dfc771f61f28874cc125403210dbde40df577d8ef8c18f945b12`); `peer-system-exact-delta-command.{log,exit}` | `0`; all three Orderer YAMLs byte-identical; each Peer YAML gained only the exact `chaincode.system` mapping for `_lifecycle`, `cscc`, `qscc`. | **PASS**, exact pre-stop delta |
| `bash .runtime/m2-node-logs/peer-system-stop-replace-command.sh` (`e02e74aa2c3c8b62bd98d92c19daefe7b6e41eb5b101187e1cfa29f02e84c271`); `peer-system-stop-replace-command.{log,exit}` | `0`; old/staged config, env and block hashes checked immediately before stop. Seller, Buyer and Carrier stopped individually with original IDs and ledgers, only their three YAMLs archived/replaced, then main-runtime node/decoded-block/Compose/M1 checks and preservation assertions passed. All six Orderer/CouchDB IDs remained running and unchanged. | **PASS**, Peer-only migration |

After those checks, the **only** recreated service was Seller, with this native command; its stdout/stderr and process exit are retained as ignored mode-0600 `.runtime/m2-node-logs/peer0-seller-system-recreate-command.{log,exit}`:

~~~sh
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml \
  --profile bootstrap --profile ca up -d --no-deps --force-recreate peer0-seller
~~~

Compose exited `0`. Seller became running as new ID `035653e758122ff1c7989e88aad2545870ab2b9726a6ac61fd7670b9a4c8153d` on the pinned Peer image digest, with the same `supplyledger_peer0_seller_ledger` name and `2026-09-25T15:10:23Z` creation time. Actual Docker inspect showed exactly `supply-fabric` and `supply-seller`, own read-only MSP/TLS/public-root/config and deny-all builder binds, no Docker socket or host port. The ignored mode-0600 `.runtime/m2-node-logs/peer0-seller-system-container.log` (SHA-256 `3e6b8700a166e71a52d7eba7a381e52ee53e0d712141460ecc59fba57cc84e1c`) contains effective `blockgossipenabled: false`, the sole `m2-chaincode-disabled` builder, and three distinct `DeploySysCC` lines: `deploying system chaincode 'cscc'`, `'qscc'` and `'_lifecycle'`. It has no `cscc.syscc` package-lookup failure. Buyer and Carrier remained **exited** under their original IDs and ledger names/creation times.

The following native Seller-only `peer channel list` was run from the retained main checkout. It repeats the first [#18 command](issue-18.md#seller-first-native-peer-prejoin-list-failure-net-06) with only a new log target. The exact command is also retained as ignored mode-0600 `.runtime/m2-issue18-peer-logs/seller-pre-join-list-after-system-command.sh` (SHA-256 `477e82fb861126441e431e09e4808edbeebd9d6ce7580f67cbb817e97fca2d2e`). Its `.log` and `.exit` files use the same stem.

~~~sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/network-config/peer0-seller.yaml",dst=/etc/hyperledger/fabric/core.yaml,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-admin1/msp",dst=/run/supply/msp,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/seller-tls-ca.pem",dst=/run/supply/peer-tls-root.pem,readonly \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=SellerMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.seller.supply.test:7051 -e CORE_PEER_TLS_ENABLED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel list \
  > .runtime/m2-issue18-peer-logs/seller-pre-join-list-after-system.log 2>&1
~~~

The CLI exited **`0`**; after gRPC reached `READY`, its final output was exactly `Channels peers has joined:` with no entries. The new ignored log SHA-256 is `756c237ad2d29b93e0b28f2262b23c9b22db2bb1dad41fe46111b664ee3122d7`. This proves the corrected in-process CSCC handled a prejoin list, **not** that Seller has joined `supplychannel`. The original CLI exit-`1`/proposal-status-`500` log remained byte-identical. The list itself sent a signed CSCC proposal, but no Peer join, business-chaincode endorsement or submitted channel transaction was attempted; the earlier failed proposal hex ID is not a committed txId and has no validation code.

The three [previously recorded literal Seller TLS/operations commands](#guarded-peer-migration-and-seller-only-live-retry) were rerun separately, with exact command copies and output/exit markers under ignored mode-0600 `.runtime/m2-node-logs/peer0-seller-peer-system-{grpc-tls,operations-health,operations-no-client}-command.sh` and matching `.log`/`.exit` files. Own-DNS gRPC TLS probe exited `0` with TLS 1.3 and `Verification: OK`; own-client operations `/healthz` exited `0` with HTTP `200` and `status=OK` (configured CouchDB dependency healthy at probe time); no-client operations probe exited `56` after server verification and TLS `certificate required`. This is process and transport readiness only.

Post-retry read-only checks matched all **273** M1 identity file hashes, six credential env hashes, original block and decoded JSON hashes, three Orderer YAML hashes, and original Seller FAIL-log hash to the before snapshots. All three Orderers and three CouchDBs remained running with original IDs; Seller retained its named ledger, and Buyer/Carrier kept original stopped container IDs and ledger identities. Clean tracked Git status was confirmed. The full nine-node current-container `T-NET-02`, Buyer/Carrier system-chaincode startup/list, all Peer joins, Peer-local block heights/hashes, current channel configuration, functional CCaaS builder and lifecycle, and canonical `genesisHash` remain **NOT RUN** at this Seller-only checkpoint.

## Buyer and Carrier individual restarts: three-Peer prejoin checkpoint

- Test: `M2-I16-NET06-07` (SPEC.md §§5.4 NET-06, 19.1; §20.1 T-NET-02). **PASS** for all three Peer processes, own TLS/operations probes, in-process system chaincodes and native empty prejoin channel lists. Peer joins, local channel heights/hashes, full current-container `T-NET-02` and functional CCaaS remain **NOT RUN**.
- The effective node/Compose source was reviewed commit `b69082a45b70fe7f2240cc668281fd000d35b345`; during the individual checks main advanced to clean local/remote `82f24b4396347631d6bbbbd6c5766e6e5595732e`, whose only changed files are this evidence and the runbook. The lock SHA-256, pinned images, Compose tier, original block and decoded JSON checksums remain those in `M2-I16-NET06-06`. No M1 identity or secret was reissued.
- Initial state for these starts: Seller was running as `035653e758122ff1c7989e88aad2545870ab2b9726a6ac61fd7670b9a4c8153d`; Buyer and Carrier were individually stopped under their original IDs and original named ledgers after the reviewed Peer-only YAML replacement. The six Orderer/CouchDB nodes were still running under their original IDs.

The two actual native Compose commands ran **separately in this order**, each with stdout/stderr and actual exit retained under ignored mode-0600 `.runtime/m2-node-logs/peer0-<org>-system-recreate-command.{log,exit}`. Compose exit alone was followed by process, mount and TLS checks before proceeding to the next Peer.

~~~sh
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml \
  --profile bootstrap --profile ca up -d --no-deps --force-recreate peer0-buyer
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml \
  --profile bootstrap --profile ca up -d --no-deps --force-recreate peer0-carrier
~~~

| Peer; Compose exit; new container ID | Actual process and ledger | Judgment |
| --- | --- | --- |
| Buyer; `0`; `036736251a0d749601f9b2acb5fbd6004f9d9541c69c1cd4ef4bea8035e92276` | Running pinned Peer image; `supplyledger_peer0_buyer_ledger` retained name/creation `2026-09-25T16:04:56Z`. Docker inspect showed exactly `supply-fabric`/`supply-buyer`, own read-only MSP/TLS/public roots/rendered config/deny builder binds, no Docker socket or published host port. Its mode-0600 `peer0-buyer-system-container.log` (SHA-256 `c9f355897389d03513c5d18def49f5384bc575ad99b42ba93934417ad550807f`) shows effective gossip `false`, the sole deny builder and separate in-process `DeploySysCC` lines for `cscc`, `qscc`, `_lifecycle`. | **PASS**, Buyer process and configuration |
| Carrier; `0`; `3c9817eb3fcd275010275d8b7b5ec6d5800d77190925093efacd9b40b8d0aff4` | Running same pinned image; `supplyledger_peer0_carrier_ledger` retained name/creation `2026-09-25T16:06:01Z`. Docker inspect showed exactly `supply-fabric`/`supply-carrier`, own read-only binds, no Docker socket or published host port. Its mode-0600 `peer0-carrier-system-container.log` (SHA-256 `93a0ae3b2cf7c99cb6f49143b7284297b1532468f5cd45bbe28a0ee07bda1798`) shows the same three in-process system-chaincode deployments and effective deny builder/gossip setting. | **PASS**, Carrier process and configuration |

Each native `peer channel list` used its **own** `supply-<org>` network, `peer0.<org>.supply.test:7051`, `<org>-admin1` MSP, `<org>-tls-ca.pem` root and `<Org>MSP`; no other organization identity or TLS bypass was supplied. The full [Seller literal command](#guarded-system-chaincode-migration-and-seller-only-prejoin-list) was repeated by substituting `seller`→`buyer` and `SellerMSP`→`BuyerMSP`, then separately `seller`→`carrier` and `SellerMSP`→`CarrierMSP`. The resulting literal native commands, stdout/stderr and process exits are retained as ignored mode-0600 `.runtime/m2-issue18-peer-logs/<org>-pre-join-list-after-system-{command.sh,runner.log}` and `<org>-pre-join-list-after-system.{log,exit}`. Buyer command SHA-256 `904632b263158019b792abc6aa9b4205db9b64aa9080389c9f8a448c69397d3c`; Carrier `4585c29b43a9863f406ea1179e23ff5abcfe666c180cf17fcc55da8aec008442`. Each CLI exited **`0`**, reached gRPC `READY` and ended with exactly `Channels peers has joined:` and no entries. The output log SHA-256 values were Buyer `3bdc94509630a71609dae00e0e79a535791ce0c41b882327c54707049feb10e7` and Carrier `4e04579411be7264b2e05fcf0125bbdee30d4f2f3f1498af70a814716335f0c2`. These are signed CSCC queries, not Peer joins or committed transactions.

For each organization, the three [literal Seller TLS/operations commands](#guarded-peer-migration-and-seller-only-live-retry) were repeated in separate short-lived tools containers with every `seller` path/DNS/network token changed to that organization's own value; the actual per-org native commands are retained as ignored mode-0600 `.runtime/m2-node-logs/peer0-<org>-peer-system-{grpc-tls,operations-health,operations-no-client}-command.sh`, with matching `.log`/`.exit` files. The substitutions left the pinned tools image, read-only root, unprivileged UID/GID, explicit own TLS root, own Peer TLS client cert and no-client negative command unchanged.

The Buyer command-file SHA-256 values in that order are `69a46f0d48771562b50b09a9a598282bf85ed0b2eae491e48a2cb726402a3573`, `84c42e507377b3536cae377b2c6daf3966ebc7e58b94ffffc4a0016813c70938`, `8556186bab18750ead2016391fd15cda46f8bd7a3ef52af8c7539b518f3c2347`. Carrier's are `3e8e05fddcdc348dbd8f63cf5f64f99bb3de97bb3b25132a82ac98e298656712`, `1062c148ed65631bbb2413840f7329b93053c9bfbdf0623b0a566b901ebe0b38`, `2364e537cf930ed693fccb49fd53d0db56235020741a833a515f40b08c47607a`. No key bytes or credential values were logged.

| Organization | Own-DNS 7051 TLS | Own-client 9444 `/healthz` | No-client 9444 TLS | Judgment |
| --- | --- | --- | --- | --- |
| Buyer | Exit `0`, TLS 1.3, `Verification: OK` | Exit `0`, HTTP `200`, `status=OK` | Exit `56`; server verified, TLS `certificate required` | **PASS**, scoped transport and configured CouchDB health at probe time |
| Carrier | Exit `0`, TLS 1.3, `Verification: OK` | Exit `0`, HTTP `200`, `status=OK` | Exit `56`; server verified, TLS `certificate required` | **PASS**, same scope |

The earlier Seller probes retain the same results under `M2-I16-NET06-06`. After Carrier's probes, read-only checks again matched all **273** M1 identity file hashes, six credential env hashes, original block and decoded JSON hashes, three Orderer YAML hashes and the original Seller proposal-status-`500` log to the pre-migration snapshots. All three Orderers and three CouchDBs remained running with their unchanged IDs, and all three Peers were running with their new IDs and original separate named ledger name/creation times. Fresh `make verify-m1`, `make verify-m2-nodes`, `make verify-m2-node-block M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json` and `make network-config` passed at their **static** scope; those commands' local `NOT RUN` lines refer to live checks the commands themselves do not perform. Full nine-node live `T-NET-02` still requires a dedicated current-container inspection and secret/build-context review. No Peer joined `supplychannel`, no Peer-local block height/hash was measured, and no business-chaincode endorsement, submitted channel transaction, txId or validation code is claimed from these prejoin lists. Canonical `genesisHash` remains NET-08 **NOT RUN**; the block-file SHA-256 above is only an artifact checksum.
