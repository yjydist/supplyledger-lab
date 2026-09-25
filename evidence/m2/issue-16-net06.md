# M2 #16 — NET-06 first CouchDB starts and Seller Peer BCCSP failure

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

Fabric v3.1.5 [`InitBCCSPConfig`](https://github.com/hyperledger/fabric/blob/v3.1.5/internal/peer/common/common.go#L150-L157) returns this exact error when `viper.Sub("peer.BCCSP")` is absent. All three tracked and old rendered Peer `core.yaml` files lack that subtree. The pinned [sample `core.yaml`](https://github.com/hyperledger/fabric/blob/v3.1.5/sampleconfig/core.yaml#L305-L319) supplies software BCCSP, SHA2 and 256-bit security. The #16 source correction adds that configuration with each Peer's own `/run/supply/msp/keystore`; its separate staged replacement and Seller-only force-recreate procedure is in the [runbook](../../docs/m2-node-config-native.md#one-time-recovery-from-the-first-seller-peer-bccsp-startup-failure). **Those migration and retry steps have not run at this checkpoint.**

Buyer and Carrier Peer startups, Peer TLS/operations checks, Peer-to-CouchDB connectivity, all three `peer channel join` commands, Peer local `supplychannel` ledger checks, and full `T-NET-02` Docker/repository inspection are **NOT RUN**. No transaction was submitted during this startup failure: no txId or validation code exists for it, and no Peer block height is claimed. The independently observed Orderer height 1 is not Peer readiness.
