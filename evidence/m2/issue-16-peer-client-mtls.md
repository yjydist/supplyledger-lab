# M2 #16 — Peer delivery client mTLS static repair checkpoint

- Test `M2-I16-NET06-08` (SPEC.md §§4.4, 5.4 NET-06, 19.1; §20.1 T-NET-02). This is a **static PASS** for the reviewed configuration and negative controls, with **live delivery FAIL retained** from [#18 `M2-I18-NET06-03`](issue-18.md#seller-post-join-block-delivery-tls-failure). New runtime migration, transport handshake, Fabric delivery stream, Buyer/Carrier joins and current-container `T-NET-02` are **NOT RUN** at this checkpoint.
- Execution baseline: clean local/remote main `0aa5c14966eb1d176377b4300f90855cd61c1105`. At this static snapshot the corrective worktree diff was uncommitted pending independent review; after its commit, resolve the source commit with `git log --diff-filter=A -1 --format=%H -- evidence/m2/issue-16-peer-client-mtls.md`. `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`. Host `darwin/arm64`, Docker image platform `linux/arm64`; Compose project `supplyledger`, overlays `bootstrap.yaml`, `ca.yaml`, `network.yaml`, profiles `bootstrap`, `ca`. The locked Fabric Peer image remains `docker.io/hyperledger/fabric-peer:3.1.5@sha256:e07c735b6f2d131315f3ae6e582c5aa602143d9d14805bb98be8ebc9d6baa82c`.
- Prepared retained data: original #17 block 27,946 bytes, SHA-256 `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a`; decoded JSON SHA-256 `2e3c9994819ae2f5ec5c6a5741f6bf558d0c364380ffee3cac10930f8f4b4e09`. These are artifact checksums, **not** the canonical `genesisHash`, which remains NET-08 **NOT RUN**. No new transaction was submitted by this static work, so it has no txId, block height or validation code. Seller's earlier local join/height 1 is recorded separately in #18 and remains valid; its subsequent delivery handshake is **FAIL**.

The pinned v3.1.5 [delivery config](https://github.com/hyperledger/fabric/blob/v3.1.5/core/deliverservice/config.go#L168-L193) loads the Peer TLS client pair only when `peer.tls.clientAuthRequired=true`. The [Peer 7051 server config](https://github.com/hyperledger/fabric/blob/v3.1.5/core/peer/config.go#L353-L387) uses that same key for inbound mTLS and reads `peer.tls.clientRootCAs.files`; the [native CLI](https://github.com/hyperledger/fabric/blob/v3.1.5/internal/peer/common/common.go#L285-L334) likewise sends its configured client pair only when its value is true. The existing Seller leaf/key match and have clientAuth purpose under the M1 root, while the retained Orderer0 log states the client sent **no certificate**. The corrective templates turn that flag on, keep the existing own `peer0-tls` client pair, and give each Peer exactly the three public Seller/Buyer/Carrier roots for 7051. The three Orderer YAMLs, M1 identities, existing private env files and running network have not been changed by this diff.

| Actual command/check on the isolated candidate | Expected and actual | Judgment |
| --- | --- | --- |
| `make network-config` | Compose accepted exact two additional public read-only root binds per Peer, with no private cross-org MSP, Docker socket or host port. | **PASS**, static |
| `make test-m2-compose` | Baseline plus 22 negative mutations passed, including `CORE_PEER_TLS_CLIENTAUTHREQUIRED=false`, missing/wrong/writable cross-org public-root binds and existing secret/builder controls. | **PASS**, static |
| `make test-m2-nodes M2_SOURCE_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime M2_INSPECT_BLOCK=/Users/yjydist/Code/supplyledger-lab/.runtime/channel/inspect-block.json` | 20 reported subchecks passed; source and rendered checks reject false/omitted client-auth flag, missing/extra/swapped roots, incomplete/wrong client pair and private env overrides. The original decoded #17 Raft certs still match. | **PASS**, temporary files only |
| `make verify-m1 M1_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime` | 41 cert inventory rows, cert/private-key matching, five measured roots, Peer SAN/serverAuth/clientAuth and wrong-root controls passed. Its printed live-test `NOT RUN` refers to tests this M1 verifier itself does not execute. | **PASS**, M1 static |
| Read-only `rendered_config` against main's retained `.runtime/network-config` | All three Orderer YAMLs byte-identical; each Peer YAML differs only by the reviewed false→true flag and exact three public client-root paths. No bind source was replaced. | **PASS**, byte comparison |
| `bash -n` on five literal [migration/probe runbook](../../docs/m2-peer-client-mtls.md) shell blocks; Python `py_compile`; `git diff --check` | All exited `0`; no command block was executed against Docker by this check. | **PASS**, syntax/diff |
| Temporary-directory fault injection with Python `shutil.copy2`/`os.replace`, matching the runbook's copy-and-same-filesystem-rename steps | At 0, 1, 2 and 3 of 3 staged Peer replacements, rollback restored all three original mode-0600 YAML bytes from the retained archive. The archive and a **dummy** ledger marker were unchanged. This was a filesystem simulation, not a real Docker volume or container operation. | **PASS**, partial-cutover recovery simulation |

The exact temporary-filesystem fault-injection invocation for the last row was:

~~~sh
python3 - <<'PY'
from pathlib import Path
import os, shutil, stat, tempfile
orgs = ('seller', 'buyer', 'carrier')
for switched in range(4):
    with tempfile.TemporaryDirectory(prefix='supply-peer-mtls-rollback-') as temp:
        root = Path(temp)
        current, stage = root / 'network-config', root / 'stage'
        archive, replaced = root / 'archive', root / 'replaced'
        ledger = root / 'peer-ledger-marker'
        for directory in (current, stage, archive, replaced):
            directory.mkdir(mode=0o700)
        ledger.write_bytes(b'retained-ledger')
        for org in orgs:
            name = f'peer0-{org}.yaml'
            for directory, body in ((current, b'old-' + org.encode()),
                                    (stage, b'new-' + org.encode())):
                path = directory / name
                path.write_bytes(body)
                path.chmod(0o600)
        assert current.stat().st_dev == stage.stat().st_dev
        for org in orgs:
            name = f'peer0-{org}.yaml'
            shutil.copy2(current / name, archive / name)
            assert (current / name).read_bytes() == (archive / name).read_bytes()
        for org in orgs[:switched]:
            name = f'peer0-{org}.yaml'
            os.replace(stage / name, current / name)
        for org in orgs:
            name = f'peer0-{org}.yaml'
            now, old = current / name, archive / name
            if now.is_file():
                shutil.copy2(now, replaced / name)
            temporary = current / f'{name}.rollback'
            assert not temporary.exists()
            shutil.copy2(old, temporary)
            assert temporary.read_bytes() == old.read_bytes()
            os.replace(temporary, now)
            assert now.read_bytes() == b'old-' + org.encode()
            assert stat.S_IMODE(now.stat().st_mode) == 0o600
            assert old.read_bytes() == b'old-' + org.encode()
        assert ledger.read_bytes() == b'retained-ledger'
    print(f'PASS: temporary fault injection after {switched}/3 replacements restored all old configs and ledger marker')
PY
~~~

The [guarded runbook](../../docs/m2-peer-client-mtls.md) requires a pre-stage exact-six credential gate, existing nine running IDs, all three Peer named-ledger identities, original Seller delivery-FAIL log and pre/post M1/env/block/Orderer hashes. It stages and compares generated YAML before stopping the three Peers, archives only their old YAML, verifies unchanged Orderers/CouchDBs and ledgers, then allows Seller-only force-recreation and native client-cert CSCC probes after independent review. The short-lived M2 CLI may mount its **own** Peer TLS pair as transport identity while its separate admin ECert signs CSCC; it does not put the node key in a long-lived application. M3 app/Gateway needs its own issued TLS client identity and user ECert separately. Seller's post-recreate 7051 own-client positive/no-client negative, Orderer delivery handshake and stream, new block receipt, Buyer/Carrier joins, cross-org NET-07 gossip and full live `T-NET-02` remain **NOT RUN** here. The old delivery failure log is preserved, not converted to PASS by this candidate.

## Guarded migration and three-Peer live transport checkpoint

- Tests `M2-I16-NET06-09` (guarded Peer config migration) and `M2-I16-NET06-10` (individual Peer starts, 7051/9444 and local CSCC probes); SPEC.md §§4.4, 5.4 NET-06, 19.1 and §20.1 T-NET-02. **PASS** at the specific migration/process/TLS/local-query scopes below. The original [Seller delivery TLS FAIL](issue-18.md#seller-post-join-block-delivery-tls-failure) remains historical evidence; actual receipt of a **new** post-genesis block, cross-organization gossip NET-07, Buyer/Carrier joins and full current-container `T-NET-02` remain **NOT RUN**.
- Effective source at execution: clean local and remote main `6e083037662db2c8002d85ae8cb5d91e26c451e3`; lock SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`. Host `darwin/arm64`; Docker `linux/arm64`; Compose project `supplyledger`, overlays `bootstrap.yaml` + `ca.yaml` + `network.yaml`, profiles `bootstrap` + `ca`. Pinned Peer image digest is the one above. The original #17 block file remains 27,946 bytes with SHA-256 `b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a`; decoded JSON SHA-256 remains `2e3c9994819ae2f5ec5c6a5741f6bf558d0c364380ffee3cac10930f8f4b4e09`. [#17's separate block-0 header calculation](issue-17.md#later-read-only-block-0-header-hash-cross-check) yielded `5c68bf099e95b934b6034a4d7aa8c52442751c30bc8b56fcbbde9b0138e38ba7` and matched Seller's height-1 `currentBlockHash`; this is the observed **local block-0 identity**, not full three-Peer NET-08 acceptance. No submitted transaction, committed txId or validation code resulted from this config migration and the signed CSCC queries.

Three reviewed [literal runbook shell blocks](../../docs/m2-peer-client-mtls.md#stage-and-compare-before-stopping-any-peer) ran **separately** from the retained main checkout. Each block's exact code, stdout/stderr and actual aggregate process exit were saved as ignored mode-0600 `.runtime/m2-node-logs/peer-client-mtls-<stage|exact-delta|stop-replace>-command.{sh,log,exit}`. The blocks use `set -eu`, so exit `0` means each contained native command passed. They were run in order, with no Seller/Buyer/Carrier recreation until independent review of the stopped state.

| Native block; command-file SHA-256 | Expected and actual | Judgment |
| --- | --- | --- |
| `stage`; `1cd12f66bcc8343bdf3c0ca46c60e9736a2ec5bd80215b96d2921d27b432de15` | Exit `0`; exact six mode-0600 credential env files, nine original running IDs, three Peer ledger identities, M1/env/block/Orderer/historical-FAIL snapshots, M1/Compose checks and staged node/native-block verifiers passed. No live bind source changed. | **PASS**, staged only |
| `exact-delta`; `dd2135b8f0cf336a43892e01f34a7d8a97ee96d56b60aa97f2f8265078b906ac` | Exit `0`; all three staged Orderer YAMLs byte-identical to old; each Peer YAML has exactly the reviewed true flag and three client-root paths added. Same-filesystem rename precondition passed. | **PASS**, pre-stop comparison |
| `stop-replace`; `784e59c6fdc6c22f696443bd4a6326350bb0b6ee372811a28fe1f6ec5b53f0b9` | Exit `0`; Seller, Buyer, Carrier stopped **individually** with old container IDs retained/exited. All three old 0600 YAMLs copied and byte-compared in ignored 0700 archive before direct same-filesystem replacements. Main-runtime node/block/Compose/M1 checks and pre/post manifests passed; six Orderer/CouchDB IDs remained running unchanged, and all three Peer named volume names/creation times matched. | **PASS**, guarded cutover |

After an independent stopped-state audit, three **separate** native `docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps --force-recreate peer0-<org>` calls ran in Seller → Buyer → Carrier order, with all checks below completed before starting the next Peer. Their exact literal commands and outputs are ignored mode-0600 `peer0-<org>-client-mtls-recreate-command.{sh,log,exit}`; each Compose process exited `0`. Docker exit alone was followed by fresh process and mount inspection. Buyer and Carrier were **not joined**.

| Peer | Old → new container ID; retained volume | Actual Docker/process result |
| --- | --- | --- |
| Seller | `035653e758122ff1c7989e88aad2545870ab2b9726a6ac61fd7670b9a4c8153d` → `e50cd1235b62d0aad4f9d2921aa931a5ee0d7bdd1265930daed78a330537b9b5`; `supplyledger_peer0_seller_ledger` created `2026-09-25T15:10:23Z` | Running pinned Peer image; exactly own `supply-fabric`/`supply-seller` networks, own read-only MSP/TLS/config/deny-builder, Orderer public root plus Buyer/Carrier public client roots, no host port/socket. Effective log shows `clientAuthRequired:true`, three client roots and in-process cscc/qscc/_lifecycle. |
| Buyer | `036736251a0d749601f9b2acb5fbd6004f9d9541c69c1cd4ef4bea8035e92276` → `82d545ae97f4329e14643e99434f97b2650d93f1e70806097f2bb382b2036d56`; `supplyledger_peer0_buyer_ledger` created `2026-09-25T16:04:56Z` | Running pinned image with own networks/private binds, Seller/Carrier **public** client roots, no port/socket; same effective mTLS and system-chaincode settings. |
| Carrier | `3c9817eb3fcd275010275d8b7b5ec6d5800d77190925093efacd9b40b8d0aff4` → `b0f92d2438840c29b2aff84d07692f3bbc55335f426084afaeeb82036614902a`; `supplyledger_peer0_carrier_ledger` created `2026-09-25T16:06:01Z` | Running pinned image with own networks/private binds, Seller/Buyer **public** client roots, no port/socket; same effective mTLS and system-chaincode settings. |

Each of the following native probes ran in its own short-lived, nonroot, read-only `supply-tools:m0-fabric3.1.5-ca1.5.22` container with `--pull=never --platform linux/arm64 --tmpfs /tmp`. The exact executed command, output and process exit are retained separately as mode-0600 `.runtime/m2-node-logs/peer0-<org>-client-mtls-<probe>-command.{sh,log,exit}`: `grpc-positive`, `grpc-no-client`, `operations-health`, `operations-no-client`, `orderer2-handshake`, `channel-list`; Seller also has `channel-getinfo`. This is **22** native command/log/exit triads across the three Peers, including the three recreations. Seller's CLI is the literal [runbook command](../../docs/m2-peer-client-mtls.md#seller-transport-and-channel-local-probes); Buyer/Carrier command files substitute only their own organization paths, DNS, `supply-<org>` network and MSP ID. The one-shot CLI mounts the own `peer0-tls` MSP as transport client and a **separate own admin ECert** MSP for signing; no other organization's private material is used. The TLS probes use `openssl s_client -verify_hostname -verify_return_error -CAfile` with an own client pair for positives, or `curl --cacert` with **no** client cert for negatives; no verification bypass or private values are logged in this report.

| Actual probe / expected | Seller actual | Buyer actual | Carrier actual | Judgment |
| --- | --- | --- | --- | --- |
| Own TLS client → own Peer 7051 | Exit `0`, TLS 1.3, DNS/root `Verification: OK` | Same | Same | **PASS**, TLS transport |
| No client cert → own Peer 7051 | Exit `56`; server DNS/root verified, then TLS `certificate required`; no application response | Same | Same | **PASS**, TLS rejection |
| Own TLS client → own 9444 `/healthz` | Exit `0`, HTTP `200`, `body.status=OK` | Same | Same | **PASS**, operations health endpoint at probe time |
| No client cert → own 9444 | Exit `56`; server verified, TLS `certificate required` | Same | Same | **PASS**, operations TLS rejection |
| Own TLS client → `orderer2.orderer.supply.test:7050` | Exit `0`, TLS 1.3, Orderer DNS/root `Verification: OK` | Same | Same | **PASS**, direct mTLS transport only |
| Own-admin native `peer channel list` | Exit `0`, lists `supplychannel` | Exit `0`, empty list | Exit `0`, empty list | **PASS**, local CSCC query |
| Own-admin native `peer channel getinfo -c supplychannel` | Exit `0`, height `1`, `currentBlockHash=XGi/CZ6VuTS2A0pNeqjFJEJ1HDC8i1b8u96bATjji6c=` | **NOT RUN**, unjoined | **NOT RUN**, unjoined | **PASS**, Seller local ledger only |

The raw Seller post-recreate log remains ignored mode-0600 at `.runtime/m2-node-logs/peer0-seller-client-mtls-post-probes-container.log` (SHA-256 `9ad42d0086029a819d0bea5195576aeea6b48d8f22690181afa5ed3aed62cbde`); Buyer/Carrier analogues have SHA-256 `0bded23da6bd8435a1fd594f283b3336764eb5e4630e15a489f76d60b848142b` and `aaaa7517a0de91ee5215d9611e692205835e19d2ff61a78cdf8240ceda45093e`. These raw logs are not committed because Fabric's effective config dump can contain private settings. Seller's new log records `StartDeliverForChannel` and `BlockReceiver starting ... orderer2...:7050`, without the old Orderer delivery `remote error: tls: certificate required` during the captured interval. Three `client didn't provide a certificate` lines instead correspond to our **own 7051 and 9444 no-client negative probes** (`PeerServer`/operations), so they are not counted as delivery failures. The direct Seller→Orderer2 TLS handshake passed, but no explicit Fabric Deliver response or new block was observed; successful ongoing block delivery and post-genesis receipt are **NOT RUN**. Buyer/Carrier have no BlockReceiver because they have not joined.

After Carrier's probes, a read-only hash audit again matched all **273** M1 identity files, six private credential env files, original block plus decoded JSON, three Orderer YAMLs and original Seller delivery-FAIL log to the pre-stage manifests. All six Orderer/CouchDB IDs were still running and unchanged; the three Peers were running on the new IDs above with original distinct named ledgers. Tracked main remained clean at `6e083037662db2c8002d85ae8cb5d91e26c451e3`. One **auxiliary read-only** Buyer log-count check first exited `1` with Python `TypeError: 'in <string>' requires string as left operand, not bytes` because it used `text=True` but searched a byte literal. Its preceding preservation assertions had passed; it changed no container. A corrected bytes-only `docker logs` count exited `0`, confirming Buyer had no `BlockReceiver starting` or Orderer delivery TLS error before join. This auxiliary **FAIL → corrected PASS** is separate from all native Peer/TLS/CLI command outcomes; no missing `.exit` marker is invented for the first ad hoc script.

No Peer join was executed during this #16 migration: Seller's earlier local join remains, Buyer/Carrier remain unjoined. The signed CSCC list/getinfo calls did not submit a channel transaction and yield no new committed txId or validation code. Three-organization equal-height/hash comparison, current config decoding, live NET-07 cross-org gossip, full nine-node `T-NET-02` mount/build-context/secret audit, M3 application TLS identity/Gateway and post-genesis block receipt remain **NOT RUN**. #18 owns any later native Buyer/Carrier join after independent review of this checkpoint.
