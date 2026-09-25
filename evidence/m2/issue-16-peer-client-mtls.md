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
