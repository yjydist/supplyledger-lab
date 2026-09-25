# M2 #18 — native channel participation and Peer join

Issue [#18](https://github.com/yjydist/supplyledger-lab/issues/18) remains **OPEN**. The first checkpoint records the three Orderer admin mTLS matrices and the first Orderer0 join failure. After the independently reviewed #16 request-size repair, all three Orderers joined the same retained block individually and became active consenters. **`T-NET-04` PASS** at its specified Orderer join/admin mTLS scope. Seller, Buyer and Carrier later joined their local channel ledgers individually at height 1. Seller's original delivery connection failed at TLS client authentication; #16 subsequently repaired Peer client mTLS, while receipt of a new block remains unverified. A contemporaneous three-organization equal-height block-hash check, anchors and cross-organization discovery remain **NOT RUN**.

- Tests: `M2-I18-ADMIN-01` (live three-node admin mTLS matrix) **PASS**; `M2-I18-NET05-01` (Orderer0 first native join) **FAIL** at admin request parsing; `M2-I18-NET05-02` (Orderer0 retry and status) **PASS**; `M2-I18-NET05-03` (Orderer1/2 individual joins and block-0 agreement) **PASS**; `M2-I18-NET06-02` (Seller local Peer join) **PASS**; `M2-I18-NET06-03` (Seller's original live block delivery) **FAIL** at TLS client authentication; `M2-I18-NET06-04` (Buyer local Peer join) **PASS**; `M2-I18-NET06-05` (Carrier local Peer join) **PASS**. `T-NET-04` **PASS** for the exact §20.1 Orderer/admin scope; three native local Peer joins are complete, while contemporaneous ledger/delivery and NET-07/08 checks are pending. See `SPEC.md` §§5.4, 19.1, 20.1 and the dedicated-client requirement transferred from #12.
- Source commit at attempt: `4376ed4c0c6ae176f3240037c0e3a927c930d0c9`; this report's introducing commit must be resolved after review. `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`.
- Host `darwin/arm64`; Docker `linux/arm64`; pinned `supply-tools:m0-fabric3.1.5-ca1.5.22` local descriptor `sha256:6b466c4dbd8aee240cbbc4c95860c4bf0b7a0de83b3edc808bc3dc71b895f8fe`.
- Compose tier: `bootstrap.yaml` + `ca.yaml` + `network.yaml`, project `supplyledger`, `bootstrap` and `ca` profiles. Three Orderers were running with retained ledger volumes following independently reviewed [NET-04](issue-16-net04.md); no Peer or CouchDB was running or started here. Native short-lived tools containers used only `supply-orderer`, read-only root filesystems, `/tmp` tmpfs and narrow read-only certificate/key mounts.
- Prepared data: original ignored #17 `supplychannel.block`, 27,946 bytes. Source and retained main copy were byte-identical by `cmp`, with **artifact-file SHA-256** `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a` immediately before the join. This checksum is **not** the canonical Fabric `genesisHash`. At the first failure, network `genesisHash`, a committed txId, live block height and validation code were **NOT RUN**. The later Orderer0 status reported height **1**; canonical block-0 `genesisHash`, a transaction txId and validation code remain **NOT RUN**.
- Ignored runtime evidence: `/Users/yjydist/Code/supplyledger-lab/.runtime/m2-issue18-logs/` (directory `0700`; logs `0600`) holds all twelve full admin outputs, `preflight.txt`, `orderer0-join.log`, `orderer0-post-400-list.log`, and the separately named Orderer0 retry/list/status logs. Logs were scanned for private-key markers; no key or password bytes are reproduced here.

## Admin mTLS boundary before joining

Each Orderer admin server certificate was validated with the pinned ordinary Orderer TLS root and exact `ordererN.orderer.supply.test` DNS. The client certificate was verified for `sslclient` purpose under its own root with system CA path/store disabled, and has an explicit clientAuth EKU. The dedicated client fingerprint is `88:4F:48:6E:83:8D:E6:CC:74:19:CB:86:2D:AC:61:D7:4A:29:B4:62:B4:20:F4:F3:F1:4F:9C:AE:30:FC:23:C1`; the ordinary Orderer0 node TLS negative is `0D:3B:10:B0:08:4A:30:5E:F2:85:8B:AA:00:42:93:42:A7:CC:08:00:8F:F1:41:CE:35:A2:DD:42:F1:C9:FB:97`; the Seller Peer TLS negative is `82:77:22:9C:8A:DF:0B:E5:82:95:53:ED:3F:41:73:74:20:DC:70:2B:AA:78:FE:CA:24:E8:15:E7:86:A2:58:B5`. Their issuing root fingerprints are, respectively, `71:CE:E5:B9:8D:F4:A0:13:49:22:38:4D:C9:12:C5:C8:E6:F4:CC:F7:83:B5:DC:05:FB:80:E6:FF:76:DF:6B:72`, `25:D0:A6:EF:0B:CF:77:F1:E7:FF:85:85:70:8D:88:3F:79:CC:CA:81:FE:86:6A:AB:D9:13:E8:49:B7:D0:36:D4` and `24:55:D7:35:B3:B8:A6:F5:76:AB:73:38:B6:58:05:74:AD:C5:50:6E:25:95:08:D0:8A:18:EC:B6:BD:5C:DF:77`.

The twelve checks were **separate native Docker invocations**, one command per node and credential case. The exact commands follow; each `*_sk` glob was asserted to resolve to one existing file before `osnadmin` or `curl` executed. The ordinary negative used Orderer0's own TLS leaf on all three admin endpoints; the other-organization negative used Seller's Peer0 TLS leaf on all three. Each leaf has clientAuth EKU, verifies under its issuing root and has its own matching key. Only the ordinary public Orderer root was mounted for server verification. No `--insecure`, hostname override or broad CA bundle was used.

### Dedicated client, HTTP list

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/signcerts/cert.pem",dst=/run/admin/client.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/keystore",dst=/run/admin/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/admin/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec osnadmin channel list -o orderer0.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"' \
  > .runtime/m2-issue18-logs/orderer0-dedicated-list.log 2>&1

docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/signcerts/cert.pem",dst=/run/admin/client.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/keystore",dst=/run/admin/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/admin/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec osnadmin channel list -o orderer1.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"' \
  > .runtime/m2-issue18-logs/orderer1-dedicated-list.log 2>&1

docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/signcerts/cert.pem",dst=/run/admin/client.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/keystore",dst=/run/admin/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/admin/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec osnadmin channel list -o orderer2.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"' \
  > .runtime/m2-issue18-logs/orderer2-dedicated-list.log 2>&1
```

### No client certificate

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --entrypoint curl supply-tools:m0-fabric3.1.5-ca1.5.22 \
  --verbose --silent --show-error --max-time 10 --cacert /run/trust/orderer-tls-ca.pem \
  --output /dev/null --write-out 'http_code=%{http_code}\n' \
  https://orderer0.orderer.supply.test:9443/participation/v1/channels \
  > .runtime/m2-issue18-logs/orderer0-no-cert.log 2>&1

docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --entrypoint curl supply-tools:m0-fabric3.1.5-ca1.5.22 \
  --verbose --silent --show-error --max-time 10 --cacert /run/trust/orderer-tls-ca.pem \
  --output /dev/null --write-out 'http_code=%{http_code}\n' \
  https://orderer1.orderer.supply.test:9443/participation/v1/channels \
  > .runtime/m2-issue18-logs/orderer1-no-cert.log 2>&1

docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --entrypoint curl supply-tools:m0-fabric3.1.5-ca1.5.22 \
  --verbose --silent --show-error --max-time 10 --cacert /run/trust/orderer-tls-ca.pem \
  --output /dev/null --write-out 'http_code=%{http_code}\n' \
  https://orderer2.orderer.supply.test:9443/participation/v1/channels \
  > .runtime/m2-issue18-logs/orderer2-no-cert.log 2>&1
```

### Valid ordinary Orderer TLS client

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/orderer0-tls/msp/signcerts/cert.pem",dst=/run/client/cert.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/orderer0-tls/msp/keystore",dst=/run/client/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/client/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec curl --verbose --silent --show-error --max-time 10 --cacert /run/trust/orderer-tls-ca.pem --cert /run/client/cert.pem --key "$1" --output /dev/null --write-out "http_code=%{http_code}\n" https://orderer0.orderer.supply.test:9443/participation/v1/channels' \
  > .runtime/m2-issue18-logs/orderer0-ordinary-orderer-client.log 2>&1

docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/orderer0-tls/msp/signcerts/cert.pem",dst=/run/client/cert.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/orderer0-tls/msp/keystore",dst=/run/client/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/client/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec curl --verbose --silent --show-error --max-time 10 --cacert /run/trust/orderer-tls-ca.pem --cert /run/client/cert.pem --key "$1" --output /dev/null --write-out "http_code=%{http_code}\n" https://orderer1.orderer.supply.test:9443/participation/v1/channels' \
  > .runtime/m2-issue18-logs/orderer1-ordinary-orderer-client.log 2>&1

docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/orderer0-tls/msp/signcerts/cert.pem",dst=/run/client/cert.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/orderer0-tls/msp/keystore",dst=/run/client/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/client/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec curl --verbose --silent --show-error --max-time 10 --cacert /run/trust/orderer-tls-ca.pem --cert /run/client/cert.pem --key "$1" --output /dev/null --write-out "http_code=%{http_code}\n" https://orderer2.orderer.supply.test:9443/participation/v1/channels' \
  > .runtime/m2-issue18-logs/orderer2-ordinary-orderer-client.log 2>&1
```

### Valid Seller TLS client

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-peer0-tls/msp/signcerts/cert.pem",dst=/run/client/cert.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-peer0-tls/msp/keystore",dst=/run/client/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/client/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec curl --verbose --silent --show-error --max-time 10 --cacert /run/trust/orderer-tls-ca.pem --cert /run/client/cert.pem --key "$1" --output /dev/null --write-out "http_code=%{http_code}\n" https://orderer0.orderer.supply.test:9443/participation/v1/channels' \
  > .runtime/m2-issue18-logs/orderer0-seller-client.log 2>&1

docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-peer0-tls/msp/signcerts/cert.pem",dst=/run/client/cert.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-peer0-tls/msp/keystore",dst=/run/client/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/client/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec curl --verbose --silent --show-error --max-time 10 --cacert /run/trust/orderer-tls-ca.pem --cert /run/client/cert.pem --key "$1" --output /dev/null --write-out "http_code=%{http_code}\n" https://orderer1.orderer.supply.test:9443/participation/v1/channels' \
  > .runtime/m2-issue18-logs/orderer1-seller-client.log 2>&1

docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-peer0-tls/msp/signcerts/cert.pem",dst=/run/client/cert.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-peer0-tls/msp/keystore",dst=/run/client/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/client/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec curl --verbose --silent --show-error --max-time 10 --cacert /run/trust/orderer-tls-ca.pem --cert /run/client/cert.pem --key "$1" --output /dev/null --write-out "http_code=%{http_code}\n" https://orderer2.orderer.supply.test:9443/participation/v1/channels' \
  > .runtime/m2-issue18-logs/orderer2-seller-client.log 2>&1
```

| Admin endpoint | Dedicated client, expected/actual | No cert, expected/actual | Ordinary Orderer TLS-CA client, expected/actual | Seller TLS-CA client, expected/actual | Judgment |
| --- | --- | --- | --- | --- | --- |
| `orderer0:9443` | HTTP 200, no system/application channel / exit 0, HTTP 200, both null | TLS rejection / curl 56, `certificate required`, HTTP 000 | TLS rejection / curl 56, `unknown ca`, HTTP 000 | TLS rejection / curl 56, `unknown ca`, HTTP 000 | **PASS** |
| `orderer1:9443` | HTTP 200, no system/application channel / exit 0, HTTP 200, both null | TLS rejection / curl 56, `certificate required`, HTTP 000 | TLS rejection / curl 56, `unknown ca`, HTTP 000 | TLS rejection / curl 56, `unknown ca`, HTTP 000 | **PASS** |
| `orderer2:9443` | HTTP 200, no system/application channel / exit 0, HTTP 200, both null | TLS rejection / curl 56, `certificate required`, HTTP 000 | TLS rejection / curl 56, `unknown ca`, HTTP 000 | TLS rejection / curl 56, `unknown ca`, HTTP 000 | **PASS** |

The nine negative curl traces explicitly show `SSL certificate verify ok` for the pinned ordinary Orderer server root and exact DNS before the client-auth alert. The three native `osnadmin` HTTP 200 results used that same pinned CA file and exact DNS, establishing successful verified TLS connections without a curl trace. The negative requests reached no HTTP handler: `http_code=000`. Admin server SHA-256 fingerprints matched the local #10 leaves and #16 live observations: Orderer0 `10:3F:9B:11:70:B1:23:5B:D2:C5:1F:DF:EE:79:4F:0E:94:EF:24:5E:72:EB:B5:BD:ED:58:E9:E2:F8:4A:FA:43`; Orderer1 `76:78:1C:F2:8B:CA:55:1C:D0:75:7B:EE:26:F0:30:0D:2F:A9:68:2C:19:FB:FB:1A:84:04:60:7F:0B:C4:C6:0D`; Orderer2 `69:BD:4D:8E:42:31:B1:F9:32:9C:5B:B5:5A:AF:88:DB:2F:46:DA:EA:B1:BD:7A:87:9B:AC:77:DF:0D:62:57:7C`.

## First native Orderer0 join failure

After independent review of the admin matrix, the first native join ran **once** with the original #17 block and dedicated client. It was not a wrapper-driven multi-node join:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/channel/supplychannel.block",dst=/run/channel/supplychannel.block,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/signcerts/cert.pem",dst=/run/admin/client.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/keystore",dst=/run/admin/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/admin/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec osnadmin channel join --channelID supplychannel --config-block /run/channel/supplychannel.block -o orderer0.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"' \
  > .runtime/m2-issue18-logs/orderer0-join.log 2>&1
```

Expected: the first join should return HTTP **201 Created** with `supplychannel` as a consenter and subsequent native list/status observations should reach `active`, with no system channel. Actual: the CLI process exit was **0**, but its response was HTTP **400**: `cannot read form from request body: multipart: NextPart: http: request body too large`. The HTTP status, rather than process exit alone, determines **FAIL**. A separate native `osnadmin channel list` immediately afterward returned HTTP 200 with `"systemChannel": null` and `"channels": null`; no channel was created. The failure stage is the admin multipart parser, before Fabric block validation or ledger/consensus join. No txId, committed block height, validation code or `genesisHash` is assigned to this failed request.

Read-only diagnosis: the three tracked and rendered Orderer YAMLs specify `ChannelParticipation.Enabled: true` but omit `MaxRequestBodySize`. Fabric 3.1.5's [sample orderer configuration](https://github.com/hyperledger/fabric/blob/v3.1.5/sampleconfig/orderer.yaml#L287-L291) explicitly uses `1 MB`; its [REST handler](https://github.com/hyperledger/fabric/blob/v3.1.5/orderer/common/channelparticipation/restapi.go#L391-L401) limits the multipart body to the configured value. The minimal YAML left the effective limit at zero; all three running Orderer startup logs explicitly printed `ChannelParticipation.MaxRequestBodySize = 0` (sanitized lines retained as ignored `effective-size-before.log`). The proposed repair is an explicit `1 MB` in all three Orderer templates and a verifier assertion, followed by reviewed regeneration/recreation that retains the three ledger volumes and M1 credentials. This diagnosis is **not** a successful join claim. No edit, restart or retry had run at this checkpoint.

## Reviewed request-size repair and Orderer0 join retry

The #16 repair was integrated as source commit `be1390687f3dbc02f3f0c9e7407aa4ea4668a1a7`; the version-lock digest, pinned tools image and Compose tier above were unchanged. Independent review confirmed all three Orderer containers were recreated with their original named ledger volumes, M1 identity/certificate bytes and #17 block retained. The author-observed running startup logs each reported `ChannelParticipation.MaxRequestBodySize = 1048576`. In the clean main checkout, `cmp` confirmed the retained block was still byte-for-byte identical to the first-run #17 source copy, and both files had artifact checksum `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a`. A fresh native Orderer0 list before retry returned HTTP 200 with both `systemChannel` and `channels` null. The original HTTP 400 log was kept unchanged.

The following retry was **one individual native `osnadmin` command** against Orderer0. Only its output log filename differs from the first attempted command above; it did not regenerate or modify the block:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/channel/supplychannel.block",dst=/run/channel/supplychannel.block,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/signcerts/cert.pem",dst=/run/admin/client.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/keystore",dst=/run/admin/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/admin/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec osnadmin channel join --channelID supplychannel --config-block /run/channel/supplychannel.block -o orderer0.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"' \
  > .runtime/m2-issue18-logs/orderer0-join-retry.log 2>&1
```

| Native observation | Expected | Actual | Judgment |
| --- | --- | --- | --- |
| Orderer0 join retry | HTTP 201; `supplychannel` consenter, eventually active | CLI exit 0 **and HTTP 201**; JSON `name=supplychannel`, `consensusRelation=consenter`, `status=active`, `height=1` | **PASS** |
| Separate `osnadmin channel list` on Orderer0 | HTTP 200; no system channel, one application channel | CLI exit 0, HTTP 200; `systemChannel:null`, one `supplychannel` entry | **PASS** |
| Separate `osnadmin channel list --channelID supplychannel` on Orderer0 | HTTP 200; active consenter | CLI exit 0, HTTP 200; `consensusRelation=consenter`, `status=active`, `height=1` | **PASS** |

The post-join list and status used the same scoped read-only tools container, pinned root, dedicated client certificate and one-key assertion as the prejoin list; the status command added `--channelID supplychannel`. Their exact outputs are preserved as `orderer0-post-join-list.log` and `orderer0-post-join-status.log`; the pre-retry null list is `orderer0-pre-retry-list.log`. All four new files are ignored mode `0600`. Orderer1/2 joins were not attempted at this checkpoint. Peer/CouchDB startup and full `T-NET-04` remain **NOT RUN**. The observed Orderer0 channel height is not a committed business transaction or validation code; canonical block-0 `genesisHash` awaits #17's live NET-08 audit.

## Orderer1 and Orderer2 individual joins; three-node block agreement

The same clean main source commit `be1390687f3dbc02f3f0c9e7407aa4ea4668a1a7`, version-lock digest, fixed tools image and Compose tier remained in use. Before each join, the retained original #17 block checksum was rechecked as `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a`; fresh native per-node lists returned HTTP 200, no system channel and `channels:null`. The dedicated client and ordinary server root were the same pinned materials that passed the three-node admin matrix. Each first join was its own native `osnadmin` invocation, never a loop or a one-click channel script:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/channel/supplychannel.block",dst=/run/channel/supplychannel.block,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/signcerts/cert.pem",dst=/run/admin/client.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/keystore",dst=/run/admin/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/admin/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec osnadmin channel join --channelID supplychannel --config-block /run/channel/supplychannel.block -o orderer1.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"' \
  > .runtime/m2-issue18-logs/orderer1-join.log 2>&1

docker run --rm --pull=never --platform linux/arm64 --network supply-orderer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/channel/supplychannel.block",dst=/run/channel/supplychannel.block,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/orderer-tls-ca.pem",dst=/run/trust/orderer-tls-ca.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/signcerts/cert.pem",dst=/run/admin/client.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/orderer/osnadmin-client1-tls/msp/keystore",dst=/run/admin/keystore,readonly \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'set -- /run/admin/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec osnadmin channel join --channelID supplychannel --config-block /run/channel/supplychannel.block -o orderer2.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"' \
  > .runtime/m2-issue18-logs/orderer2-join.log 2>&1
```

The following native command and response ledger used the same pinned Docker options and public-root/dedicated-client/one-keystore mounts as the full dedicated-client list commands above. List/status calls did not mount the block; the read-only fetches added only ignored `.runtime/m2-issue18-logs/fetch` to `/run/fetch` as a writable output bind. Each row ran as a **separate** `supply-tools` container. The literal inner shell prelude was `set -- /run/admin/keystore/*_sk; test "$#" -eq 1 && test -f "$1"; exec osnadmin ... --client-key "$1"`; the table records the complete native `osnadmin` arguments after `exec`, with `"$1"` denoting that verified one key. `umask 077` inside the Orderer1/2 fetch containers set each new block file to `0600`; Orderer0's fetched public block was explicitly changed to `0600` immediately after creation. The fetches did not send a transaction or alter a ledger.

| Node | Exact native command inside scoped container | Ignored output log/file | Process exit; HTTP; actual result |
| --- | --- | --- | --- |
| Orderer1 | `osnadmin channel list -o orderer1.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"` | `orderer1-pre-join-list.log` | 0; 200; `systemChannel:null`, `channels:null` |
| Orderer1 | `osnadmin channel join --channelID supplychannel --config-block /run/channel/supplychannel.block -o orderer1.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"` | `orderer1-join.log` | 0; **201**; `consenter`, `active`, height **1** |
| Orderer1 | `osnadmin channel list -o orderer1.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"` | `orderer1-post-join-list.log` | 0; 200; no system channel, one `supplychannel` |
| Orderer1 | `osnadmin channel list --channelID supplychannel -o orderer1.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"` | `orderer1-post-join-status.log` | 0; 200; `consenter`, `active`, height **1** |
| Orderer2 | `osnadmin channel list -o orderer2.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"` | `orderer2-pre-join-list.log` | 0; 200; `systemChannel:null`, `channels:null` |
| Orderer2 | `osnadmin channel join --channelID supplychannel --config-block /run/channel/supplychannel.block -o orderer2.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"` | `orderer2-join.log` | 0; **201**; `consenter`, `active`, height **1** |
| Orderer2 | `osnadmin channel list -o orderer2.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"` | `orderer2-post-join-list.log` | 0; 200; no system channel, one `supplychannel` |
| Orderer2 | `osnadmin channel list --channelID supplychannel -o orderer2.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"` | `orderer2-post-join-status.log` | 0; 200; `consenter`, `active`, height **1** |
| Orderer0 | `osnadmin channel fetch --channelID supplychannel --blockID oldest --outputfile /run/fetch/orderer0-block0.block -o orderer0.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"` | `orderer0-fetch-oldest.log`; `fetch/orderer0-block0.block` | 0; 200; 27,946-byte block 0 |
| Orderer1 | `osnadmin channel fetch --channelID supplychannel --blockID oldest --outputfile /run/fetch/orderer1-block0.block -o orderer1.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"` | `orderer1-fetch-oldest.log`; `fetch/orderer1-block0.block` | 0; 200; 27,946-byte block 0 |
| Orderer2 | `osnadmin channel fetch --channelID supplychannel --blockID oldest --outputfile /run/fetch/orderer2-block0.block -o orderer2.orderer.supply.test:9443 --ca-file /run/trust/orderer-tls-ca.pem --client-cert /run/admin/client.pem --client-key "$1"` | `orderer2-fetch-oldest.log`; `fetch/orderer2-block0.block` | 0; 200; 27,946-byte block 0 |

For `M2-I18-NET05-03`, the expected result was HTTP 201 per new join; three active consenters with no system channel; and three ledger copies of the original block 0. The actual native responses and separate status calls above met those expectations. A byte comparison of each fetched block against the original retained #17 block passed; all three fetched files were 27,946 bytes with the same **artifact-file checksum** `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a`. This byte equality proves the three Orderers expose the same block 0; the file checksum is still **not** the canonical block-header `genesisHash` that #17 will record during NET-08.

A separate read-only Raft log scan (`raft-leader-scan.log`) found Orderer1/node 2 `became leader at term 2` and `Start accepting requests as Raft leader at block [0]`; Orderer0/node 1 and Orderer2/node 3 each recorded elected leader 2 at term 2. This establishes an observed Raft leader election after the nodes joined. It does **not** demonstrate a post-genesis configuration transaction or business transaction commit; those tests remain **NOT RUN**. No txId or validation code was produced by these admin join/fetch requests. `T-NET-04` is **PASS** on its §20.1 criteria (all three joined/active, no system channel, admin mTLS positive and negative matrix). The broader #18 acceptance still awaits #16 Peer/CouchDB startup, then individual Peer joins, anchor/discovery checks and three-organization equal-height block-hash comparison. The original HTTP 400 failure remains in its own log and FAIL row.

## Seller first native Peer prejoin list failure (NET-06)

- Test `M2-I18-NET06-01`; SPEC §§5.4 NET-06, 19.1. Source commit at execution: clean local/remote main `22af10ed8dde301fc77b38aa437e5db844d07168`; `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`. Compose tier: `bootstrap.yaml` + `ca.yaml` + `network.yaml`, project `supplyledger`, `bootstrap` and `ca` profiles. The native short-lived tools container used the locked local `supply-tools:m0-fabric3.1.5-ca1.5.22` image on the **Seller-only** `supply-seller` network; it had no Docker socket, published port or other organization's identity.
- Prepared data: Seller's ignored rendered `peer0-seller.yaml`, Seller admin local MSP (`CN=seller-admin1`, `OU=admin`, signcert SHA-256 fingerprint `05:42:F4:79:3E:F8:37:01:80:EF:18:DD:BD:0D:B5:AD:6E:78:C4:68:55:DC:4E:55:64:14:D7:10:D9:19:98:84`) and own public TLS root (`seller-tls-ca.pem`, fingerprint `24:55:D7:35:B3:B8:A6:F5:76:AB:73:38:B6:58:05:74:AD:C5:50:6E:25:95:08:D0:8A:18:EC:B6:BD:5C:DF:77`). The retained original #17 `.runtime/channel/supplychannel.block` was still mode `0600`, 27,946 bytes, ignored by Git and SHA-256 `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a` immediately before this call. That SHA is the **artifact-file checksum**, not canonical `genesisHash`; this list command did not mount or submit the block.
- The output file `.runtime/m2-issue18-peer-logs/seller-pre-join-list.log` was pre-created with mode `0600` under a mode-`0700` ignored directory. Its SHA-256 is `44a6deedcf81af8bf285fee6ac8528f55fb10bd89ae02c7aa6da05ac9b12b3bb`. No separate `.exit` marker was created; the native command's observed process exit **1** came from the command runner, not a retained marker file. The full output stays in the ignored log; no key or password bytes appear in this report.

The first Seller command was one native `peer channel list` invocation. The mounted `core.yaml` supplies the BCCSP keystore path `/run/supply/msp/keystore`; that path contained the mounted Seller admin MSP, not the Peer node MSP. The explicit environment fixed the same organization, exact Peer DNS and own TLS root, without a server-host override or TLS bypass:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/network-config/peer0-seller.yaml",dst=/etc/hyperledger/fabric/core.yaml,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-admin1/msp",dst=/run/supply/msp,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/seller-tls-ca.pem",dst=/run/supply/peer-tls-root.pem,readonly \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=SellerMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.seller.supply.test:7051 -e CORE_PEER_TLS_ENABLED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel list \
  > .runtime/m2-issue18-peer-logs/seller-pre-join-list.log 2>&1
```

| Expected | Actual | Judgment |
| --- | --- | --- |
| CLI exit 0 and an empty local channel list before Seller's first `peer channel join` | CLI exit **1**. The log shows gRPC connection `READY` to `peer0.seller.supply.test:7051`, then `Received bad response, status 500` during simulation: `could not launch chaincode cscc.syscc`; package lookup failed at `/var/hyperledger/production/chaincodes/cscc.syscc`. No channel list result was returned. | **FAIL**, Peer system-chaincode simulation before any join |

The error names proposal attempt ID `1584601cca1cd619219ce28edfe6d69c5c62ee649646870f56c084dc3f2ad751`. It is **not** a committed channel transaction ID; this failed local query produced no block height or validation code. A read-only check of the running Seller's retained startup log found `not deploying chaincode cscc`, `qscc` and `_lifecycle` because none was enabled. The three Peer source/rendered YAMLs omit `chaincode.system`. In pinned Fabric v3.1.5, [`chaincode.GlobalConfig`](https://github.com/hyperledger/fabric/blob/v3.1.5/core/chaincode/config.go#L64-L67) starts with an empty system-chaincode allowlist and loads it from that map; [`node.serve`](https://github.com/hyperledger/fabric/blob/v3.1.5/internal/peer/node/start.go#L770-L779) only deploys enabled in-process system chaincodes. This explains why the Endorser reached a legacy package lookup instead of the in-process `cscc`. It is a diagnosis, not a repaired or successful Peer join.

The earlier three-Orderer `T-NET-04` PASS and byte-identical block-0 observations remain separate. Seller's `peer channel join`, its post-join list/getinfo, Buyer/Carrier prejoin lists and joins, anchors, Peer block-height/hash comparison and current-config `T-NET-03` are **NOT RUN** at this checkpoint. No Peer ledger success or canonical `genesisHash` is claimed. The failed Seller log must remain available after #16's separately reviewed system-chaincode configuration repair and Peer recreation.

## Seller first native Peer join and local-ledger check (NET-06)

- Test `M2-I18-NET06-02`; SPEC §§5.4 NET-06, 19.1. Execution source was clean local/remote main `82f24b4396347631d6bbbbd6c5766e6e5595732e`; `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`. Compose project `supplyledger` used `bootstrap.yaml` + `ca.yaml` + `network.yaml` with `bootstrap` and `ca` profiles. #16 had separately recreated and checked all three Peers with the in-process system-chaincode fix and preserved ledgers; independent review authorized **Seller only** for this first Peer join.
- The retained original #17 `.runtime/channel/supplychannel.block` was Git-ignored, mode `0600`, 27,946 bytes. `shasum -a 256 .runtime/channel/supplychannel.block` returned `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a` before the list and immediately before the join. The same command returned that value after the four native calls; its post-join output is retained as ignored mode-`0600` `.runtime/m2-issue18-peer-logs/seller-block-sha-after-join.log`. This is an **artifact-file checksum**, not a canonical Fabric `genesisHash`.
- Four separate native, nonroot, read-only `supply-tools:m0-fabric3.1.5-ca1.5.22` containers used only `supply-seller`, exact `peer0.seller.supply.test:7051`, Seller admin local MSP and Seller TLS CA root. Each output was redirected to its own pre-created mode-`0600` ignored log under `.runtime/m2-issue18-peer-logs/` (`0700`). The four process exit codes below were observed from the command runner; no separate `.exit` marker files were captured. Retrospective mode-`0600` `.command.txt` copies adjacent to the four logs reproduce the literal commands below; `seller-runner-exits.observed.txt` records the runner-observed exits and explicitly states that contemporaneous `.exit` files do not exist. These retrospective copies are not additional executions. The prior first-list status-`500` FAIL log remains unchanged.

The **prejoin list** did not mount the block:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/network-config/peer0-seller.yaml",dst=/etc/hyperledger/fabric/core.yaml,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-admin1/msp",dst=/run/supply/msp,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/seller-tls-ca.pem",dst=/run/supply/peer-tls-root.pem,readonly \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=SellerMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.seller.supply.test:7051 -e CORE_PEER_TLS_ENABLED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel list \
  > .runtime/m2-issue18-peer-logs/seller-pre-join-list-after-scc.log 2>&1
```

The **join** was one native CSCC proposal using the exact retained block, with no orderer admin or other organization secret mounted:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/network-config/peer0-seller.yaml",dst=/etc/hyperledger/fabric/core.yaml,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-admin1/msp",dst=/run/supply/msp,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/seller-tls-ca.pem",dst=/run/supply/peer-tls-root.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/channel/supplychannel.block",dst=/run/channel/supplychannel.block,readonly \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=SellerMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.seller.supply.test:7051 -e CORE_PEER_TLS_ENABLED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel join -b /run/channel/supplychannel.block \
  > .runtime/m2-issue18-peer-logs/seller-join.log 2>&1
```

The **postjoin list** was a separate native call without the block mount:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/network-config/peer0-seller.yaml",dst=/etc/hyperledger/fabric/core.yaml,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-admin1/msp",dst=/run/supply/msp,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/seller-tls-ca.pem",dst=/run/supply/peer-tls-root.pem,readonly \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=SellerMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.seller.supply.test:7051 -e CORE_PEER_TLS_ENABLED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel list \
  > .runtime/m2-issue18-peer-logs/seller-post-join-list.log 2>&1
```

The **getinfo** call separately queried Seller's local `supplychannel` ledger:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/network-config/peer0-seller.yaml",dst=/etc/hyperledger/fabric/core.yaml,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/seller/seller-admin1/msp",dst=/run/supply/msp,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/seller-tls-ca.pem",dst=/run/supply/peer-tls-root.pem,readonly \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=SellerMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.seller.supply.test:7051 -e CORE_PEER_TLS_ENABLED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel getinfo -c supplychannel \
  > .runtime/m2-issue18-peer-logs/seller-post-join-getinfo.log 2>&1
```

| Native call; ignored raw log SHA-256 | Expected | Actual process exit and response | Judgment |
| --- | --- | --- | --- |
| Prejoin list; `seller-pre-join-list-after-scc.log` `c5421d342e4f0c2d6d28af78aee5e609669b81a34478363f2b32ccc372fd161a` | Exit 0, empty list | **0**; `Channels peers has joined:` with no entries | **PASS**, prejoin state |
| Join; `seller-join.log` `2c52d220a175622e4c4f9b9babc0419e5f7a12cae235a2c7a37119f5f85127e4` | Exit 0, CSCC accepts the original block | **0**; `Successfully submitted proposal to join channel` | **PASS**, native join proposal accepted |
| Postjoin list; `seller-post-join-list.log` `ae4c73ce27f4ad305f3e33b286964eb2b9054ef3eaa5845590140a3844838652` | Exit 0, exactly `supplychannel` | **0**; list contains exactly `supplychannel` | **PASS**, local channel entry |
| Getinfo; `seller-post-join-getinfo.log` `cb52eb704b05d4b86dd5dde5a1b3911b382f95f388dc6b36ce0ed9cac428874d` | Exit 0, local block height at least 1 | **0**; `height=1`, `currentBlockHash=XGi/CZ6VuTS2A0pNeqjFJEJ1HDC8i1b8u96bATjji6c=` | **PASS**, Seller local block-0 state |

The `currentBlockHash` is the value returned by Seller's native `BlockchainInfo`; its equal-height comparison with Buyer and Carrier and #17's canonical genesis identity audit are **NOT RUN**. This local CSCC join did not submit an ordered channel or business transaction, so there is no committed txId or validation code from these four calls. Buyer and Carrier joins, anchors, cross-organization discovery, three-Peer same-height block-hash comparison and current-config `T-NET-03` remain **NOT RUN** at this Seller-only snapshot. The original Seller prejoin status-`500` FAIL remains recorded separately above; this later PASS does not erase it.

### Seller post-join block-delivery TLS failure

- Test `M2-I18-NET06-03`; expected: after the local join, Seller's delivery client authenticates with a Seller TLS client certificate to the Orderers' `7050` endpoints and establishes block delivery. Actual: **FAIL** at the TLS handshake, before an Orderer Deliver response or a new block. The local join and height-1 `BlockchainInfo` above remain valid observations; ongoing block delivery is **not PASS**.
- A later **read-only** filtered `docker logs --timestamps --since 60m` capture, saved in ignored mode-`0600` `.runtime/m2-issue18-peer-logs/seller-delivery-tls-fail.filtered.log` (SHA-256 `73d48bf659cf080a3849c29b4ab241496260d6cb9d655c61dd938c9193183b79`), contains seven timestamped lines from the running Seller Peer and Orderer0. ANSI escapes were removed and Orderer0's remote IP/port was redacted. These were extracted after the native join, not captured by the four original CLI redirects. Seller's log reports `remote error: tls: certificate required` against each of `orderer0`, `orderer1` and `orderer2` at `7050`, followed by `peer.blocksprovider DeliverBlocks` connection/retry warnings. At `2026-09-25 16:39:44 UTC`, Orderer0 logged `Server TLS handshake failed ... tls: client didn't provide a certificate`.

Sanitized lines from that later capture (UTC):

```text
2026-09-25T16:39:44.340915841Z [Seller peer → orderer0.orderer.supply.test:7050] connection error: "error reading server preface: remote error: tls: certificate required"
2026-09-25T16:39:44.340819008Z [Orderer0] Server TLS handshake failed: tls: client didn't provide a certificate; remoteaddress=[redacted]
```
- Read-only cause check: all three tracked and rendered Peer YAMLs have `peer.tls.clientAuthRequired: false`, although `clientCert.file` and `clientKey.file` point to the Peer TLS leaf/key. Seller's leaf has explicit clientAuth EKU and verifies for `sslclient` against its pinned Seller TLS root. Pinned Fabric 3.1.5 [`loadDeliverServiceConfig`](https://github.com/hyperledger/fabric/blob/v3.1.5/core/deliverservice/config.go#L168-L193) copies `peer.tls.clientAuthRequired` into delivery `SecOpts.RequireClientCert` and reads the configured client cert/key **only when it is true**; the [CFT delivery dialer](https://github.com/hyperledger/fabric/blob/v3.1.5/core/deliverservice/deliveryclient.go#L180-L205) uses those options. The current `false` therefore explains the observed missing client certificate. Orderer `General.TLS.ClientAuthRequired` remains true; its client roots include the Seller TLS root. #16 must separately review, apply and verify the three-Peer configuration/runtime repair before further native joins. No Orderer TLS check was weakened here.
- No additional operator-triggered Peer join, anchor or ordered transaction was attempted in this diagnosis; the running Seller Peer continued its automatic delivery retries. Buyer/Carrier native joins remain **NOT RUN** pending the #16 repair and independent live review. No committed txId, new block height or validation code is inferred from the delivery retry logs.

## Buyer first native Peer join and local-ledger check (NET-06)

- Test `M2-I18-NET06-04`; `SPEC.md` §§5.4 NET-06, 19.1. Execution source: clean local/remote main `9975b0e2418b35fab678b01b905be7811aaaf5fb`; `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`. Compose tier: `bootstrap.yaml` + `ca.yaml` + `network.yaml`, project `supplyledger`, `bootstrap` and `ca` profiles. The pinned local `supply-tools:m0-fabric3.1.5-ca1.5.22` image used `linux/arm64`, nonroot, read-only, no published port or Docker socket. #16's reviewed [three-Peer client-mTLS checkpoint](issue-16-peer-client-mtls.md) was integrated before these calls; only Buyer was authorized, with Carrier held for separate review.
- Prepared inputs: Buyer's rendered `peer0-buyer.yaml`, Buyer admin ECert MSP (`CN=buyer-admin1`, `OU=admin`, SHA-256 signcert fingerprint `50:AA:46:2C:35:BC:48:AA:C5:66:D7:DB:E6:8A:70:F1:EA:AC:CD:C5:1E:26:94:34:45:F5:6A:09:CE:2F:87:7B`), distinct Buyer `peer0-tls` MSP (signcert fingerprint `36:E0:6D:3B:83:58:4A:7E:74:86:00:F5:FB:F1:51:E3:0D:3B:54:1E:61:C6:39:19:09:C7:FB:59:BD:F4:1B:3E`), and Buyer TLS root (fingerprint `5E:C8:AD:97:97:6E:49:65:06:DD:69:45:9A:63:D1:05:42:9C:36:A0:19:AA:DE:50:DE:32:3F:A3:C2:40:C3:54`). The original ignored `.runtime/channel/supplychannel.block` was 27,946 bytes, mode `0600`, with artifact-file SHA-256 `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a` immediately before the calls and after the join. That checksum is **not** the canonical block-header hash.
- Four separate native calls used only `supply-buyer`, Buyer admin ECert MSP at `/run/supply/msp` for CSCC signing, Buyer Peer TLS MSP at `/run/supply/tls` for the required 7051 mTLS client certificate, Buyer's own public TLS root, and exact DNS `peer0.buyer.supply.test:7051`. Each literal `docker run` command was written to an adjacent ignored mode-`0600` `.command.txt` **before** it ran; the raw `.log` and `.exit` files are also mode `0600` under mode-`0700` `.runtime/m2-issue18-peer-logs/`. No other organization's private key was mounted. The explicit `CORE_PEER_TLS_CLIENTAUTHREQUIRED=true` matches the rendered `core.yaml`; no TLS verification override was used.

The **prejoin list** used `peer channel list` with no block mount:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-buyer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/network-config/peer0-buyer.yaml",dst=/etc/hyperledger/fabric/core.yaml,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/buyer/buyer-admin1/msp",dst=/run/supply/msp,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/buyer/buyer-peer0-tls/msp",dst=/run/supply/tls,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/buyer-tls-ca.pem",dst=/run/supply/peer-tls-root.pem,readonly \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=BuyerMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.buyer.supply.test:7051 -e CORE_PEER_TLS_ENABLED=true \
  -e CORE_PEER_TLS_CLIENTAUTHREQUIRED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel list \
  > .runtime/m2-issue18-peer-logs/buyer-pre-join-list.log 2>&1
```

The **join** added only the read-only original block mount and called native CSCC once:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-buyer --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/network-config/peer0-buyer.yaml",dst=/etc/hyperledger/fabric/core.yaml,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/buyer/buyer-admin1/msp",dst=/run/supply/msp,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/buyer/buyer-peer0-tls/msp",dst=/run/supply/tls,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/buyer-tls-ca.pem",dst=/run/supply/peer-tls-root.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/channel/supplychannel.block",dst=/run/channel/supplychannel.block,readonly \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=BuyerMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.buyer.supply.test:7051 -e CORE_PEER_TLS_ENABLED=true \
  -e CORE_PEER_TLS_CLIENTAUTHREQUIRED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel join -b /run/channel/supplychannel.block \
  > .runtime/m2-issue18-peer-logs/buyer-join.log 2>&1
```

The **postjoin list** and **getinfo** were separate native calls without the block mount. Each used the exact prejoin envelope above, replacing only the final arguments and log path:

```sh
--entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel list \
  > .runtime/m2-issue18-peer-logs/buyer-post-join-list.log 2>&1
--entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel getinfo -c supplychannel \
  > .runtime/m2-issue18-peer-logs/buyer-post-join-getinfo.log 2>&1
```

| Native call; ignored raw log SHA-256 | Expected | Actual exit and response | Judgment |
| --- | --- | --- | --- |
| Prelist; `buyer-pre-join-list.log` `6ace16aa8bb298d9eabf0b32854d6c455c89ce2d2f74ff40ba7642c29fb29d2a` | Exit 0; no local channel | **0**; gRPC READY, `Channels peers has joined:` with no entries | **PASS**, prejoin local state |
| Join; `buyer-join.log` `b0321a02cf07ab2df77fcb902c19be07ff17560c588432706099b204db9de376` | Exit 0; CSCC accepts original block | **0**; `Successfully submitted proposal to join channel` | **PASS**, native join proposal accepted |
| Postlist; `buyer-post-join-list.log` `de27d3c48f9a566fe82e3a5db1c328bae74928294f84f35bc07c4384d7c98ab2` | Exit 0; exactly `supplychannel` | **0**; list contains exactly `supplychannel` | **PASS**, local channel entry |
| Getinfo; `buyer-post-join-getinfo.log` `1e5c8c0a0c34bf792aeb17362ddf76e20057b0beff82fc8a309b22231cf564e5` | Exit 0; local height at least 1 | **0**; `height=1`, `currentBlockHash=XGi/CZ6VuTS2A0pNeqjFJEJ1HDC8i1b8u96bATjji6c=` | **PASS**, Buyer local block-0 state |

Buyer's `currentBlockHash` matches Seller's previously observed height-1 value and #17's independently calculated canonical block-0 header hash (`5c68bf099e95b934b6034a4d7aa8c52442751c30bc8b56fcbbde9b0138e38ba7`). This comparison is limited to the two local ledgers at height 1. No post-genesis ordered block, delivery receipt, committed transaction ID or validation code is inferred from the join/getinfo commands. At this Buyer-only snapshot, Carrier join and three-Peer equal-height comparison, anchors, cross-organization discovery, current-config NET-08 and full `T-NET-03` were **NOT RUN**. The historical Seller delivery TLS **FAIL** above remains a real prior observation; #16's later mTLS repair established transport/client readiness but has not yet demonstrated a new delivered block.

## Carrier first native Peer join and local-ledger check (NET-06)

- Test `M2-I18-NET06-05`; `SPEC.md` §§5.4 NET-06, 19.1. Execution source: clean local/remote main `4b6f8a17f61055da717f970243180dede092a587`; `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`. Compose tier: `bootstrap.yaml` + `ca.yaml` + `network.yaml`, project `supplyledger`, `bootstrap` and `ca` profiles. The pinned local `supply-tools:m0-fabric3.1.5-ca1.5.22` image used `linux/arm64`, nonroot, read-only, no published port or Docker socket. Buyer was independently reviewed and its evidence integrated before this Carrier-only authorization.
- Prepared inputs: Carrier's rendered `peer0-carrier.yaml`, Carrier admin ECert MSP (`CN=carrier-admin1`, `OU=admin`, SHA-256 signcert fingerprint `28:DA:73:E5:2D:98:FE:0D:9E:5F:61:C0:75:CC:0E:C0:D0:95:48:94:EA:02:40:71:DB:7A:0B:A7:2C:BE:02:96`), separate Carrier `peer0-tls` MSP (signcert fingerprint `B8:B1:73:F4:1C:8B:9D:4F:FA:CB:75:8B:E3:6A:BF:3E:13:B8:82:93:25:0A:5B:8E:E2:5E:13:CE:CD:DE:43:B8`), and Carrier TLS root (fingerprint `3D:3F:FC:65:8F:1C:B6:3F:D1:81:E4:4F:77:23:EC:2E:6C:2E:C6:A1:07:B3:34:50:6B:D4:CC:B5:9E:4C:F9:6A`). The original ignored `.runtime/channel/supplychannel.block` stayed mode `0600`, 27,946 bytes, with artifact-file SHA-256 `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a` before and after the join. This checksum is distinct from the canonical block-header hash.
- Four separate native calls used only `supply-carrier`, Carrier admin ECert MSP at `/run/supply/msp` for CSCC signing, Carrier Peer TLS MSP at `/run/supply/tls` for the 7051 mTLS client pair, its own public TLS root, and exact DNS `peer0.carrier.supply.test:7051`. Each literal `docker run` command was written to an ignored mode-`0600` `.command.txt` before that call; the respective `.log` and `.exit` files are also mode `0600` under mode-`0700` `.runtime/m2-issue18-peer-logs/`. No other organization's private key or TLS verification override was used. The explicit `CORE_PEER_TLS_CLIENTAUTHREQUIRED=true` matches the current rendered `core.yaml`.

The **prejoin list** used no block mount:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-carrier --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/network-config/peer0-carrier.yaml",dst=/etc/hyperledger/fabric/core.yaml,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/carrier/carrier-admin1/msp",dst=/run/supply/msp,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/carrier/carrier-peer0-tls/msp",dst=/run/supply/tls,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/carrier-tls-ca.pem",dst=/run/supply/peer-tls-root.pem,readonly \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=CarrierMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.carrier.supply.test:7051 -e CORE_PEER_TLS_ENABLED=true \
  -e CORE_PEER_TLS_CLIENTAUTHREQUIRED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel list \
  > .runtime/m2-issue18-peer-logs/carrier-pre-join-list.log 2>&1
```

The **join** added only the original block as a read-only bind:

```sh
docker run --rm --pull=never --platform linux/arm64 --network supply-carrier --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/.runtime/network-config/peer0-carrier.yaml",dst=/etc/hyperledger/fabric/core.yaml,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/carrier/carrier-admin1/msp",dst=/run/supply/msp,readonly \
  --mount type=bind,src="$PWD/.runtime/identities/carrier/carrier-peer0-tls/msp",dst=/run/supply/tls,readonly \
  --mount type=bind,src="$PWD/.runtime/trust/carrier-tls-ca.pem",dst=/run/supply/peer-tls-root.pem,readonly \
  --mount type=bind,src="$PWD/.runtime/channel/supplychannel.block",dst=/run/channel/supplychannel.block,readonly \
  -e FABRIC_CFG_PATH=/etc/hyperledger/fabric \
  -e CORE_PEER_LOCALMSPID=CarrierMSP -e CORE_PEER_MSPCONFIGPATH=/run/supply/msp \
  -e CORE_PEER_ADDRESS=peer0.carrier.supply.test:7051 -e CORE_PEER_TLS_ENABLED=true \
  -e CORE_PEER_TLS_CLIENTAUTHREQUIRED=true \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/run/supply/peer-tls-root.pem \
  --entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel join -b /run/channel/supplychannel.block \
  > .runtime/m2-issue18-peer-logs/carrier-join.log 2>&1
```

The **postjoin list** and **getinfo** were separate native calls without the block bind, with the same prejoin envelope and only these distinct final arguments/log paths; their complete literal commands are in the adjacent ignored `.command.txt` files:

```sh
--entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel list \
  > .runtime/m2-issue18-peer-logs/carrier-post-join-list.log 2>&1
--entrypoint peer supply-tools:m0-fabric3.1.5-ca1.5.22 channel getinfo -c supplychannel \
  > .runtime/m2-issue18-peer-logs/carrier-post-join-getinfo.log 2>&1
```

| Native call; ignored raw log SHA-256 | Expected | Actual exit and response | Judgment |
| --- | --- | --- | --- |
| Prelist; `carrier-pre-join-list.log` `58d5f30f8451f30e644e0f7053bbffd60a6e1ea80a6baf4747994611957e781d` | Exit 0; no local channel | **0**; gRPC READY, `Channels peers has joined:` with no entries | **PASS**, prejoin local state |
| Join; `carrier-join.log` `09a97c290f4d118238ce9fc244f94b6281d1df9f4de3afac4e9e4dc9ed946e87` | Exit 0; CSCC accepts original block | **0**; `Successfully submitted proposal to join channel` | **PASS**, native join proposal accepted |
| Postlist; `carrier-post-join-list.log` `5fd35424f9bd4d7464410fee39f648f49d99f895aa12ee1d88d4cd1a8efb8391` | Exit 0; exactly `supplychannel` | **0**; list contains exactly `supplychannel` | **PASS**, local channel entry |
| Getinfo; `carrier-post-join-getinfo.log` `d2f70e42fedb5c01f7fbad65d61254e00ed4daf26ba04914a61a3833b3811f37` | Exit 0; local height at least 1 | **0**; `height=1`, `currentBlockHash=XGi/CZ6VuTS2A0pNeqjFJEJ1HDC8i1b8u96bATjji6c=` | **PASS**, Carrier local block-0 state |

Carrier's local height-1 `currentBlockHash` matches the prior Seller and Buyer observations and #17's offline canonical block-0 header hash (`5c68bf099e95b934b6034a4d7aa8c52442751c30bc8b56fcbbde9b0138e38ba7`). These were individual observations, not a contemporaneous three-Peer check. No post-genesis ordered block, delivery receipt, committed transaction ID or validation code is inferred from these CSCC calls. Three-Peer same-height hash and block-0 fetch, anchor/discovery checks, current-config NET-08 and full `T-NET-03` are **NOT RUN**; #18 remains OPEN. The prior Seller delivery TLS **FAIL** remains in its historical section, while #16's later repair has not yet proven receipt of a new ordered block.
