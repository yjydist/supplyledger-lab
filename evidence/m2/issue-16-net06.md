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

The guarded [Peer-only stage/stop/replace/recreate procedure](../../docs/m2-node-config-native.md#one-time-recovery-from-the-first-seller-peer-channel-list-proposal-status-500), a new `peer channel list`, all Peer joins, channel-local block checks, functional user chaincode builder/CCaaS, full NET-06 and current-state `T-NET-02` are **NOT RUN** at this corrective review checkpoint. No runtime config file, identity, credential, original block, service container or named ledger has been changed by this diff. #18 must retry the native list and joins only after the corrected three Peers are independently reviewed and recreated.
