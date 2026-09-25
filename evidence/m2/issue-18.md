# M2 #18 — native channel participation and Peer join

Issue [#18](https://github.com/yjydist/supplyledger-lab/issues/18) remains **OPEN**. The first checkpoint records the three Orderer admin mTLS matrices and the first Orderer0 join failure. After the independently reviewed #16 request-size repair, Orderer0 joined the same retained block. Orderer1/2 joins, Peer/CouchDB startup, Peer joins, anchors, equal-height block-hash comparison and full `T-NET-04` remain **NOT RUN**.

- Tests: `M2-I18-ADMIN-01` (live three-node admin mTLS matrix) **PASS**; `M2-I18-NET05-01` (Orderer0 first native join) **FAIL** at admin request parsing; `M2-I18-NET05-02` (Orderer0 retry and status) **PASS**; full `T-NET-04` **NOT RUN**. See `SPEC.md` §§5.4, 19.1, 20.1 and the dedicated-client requirement transferred from #12.
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
