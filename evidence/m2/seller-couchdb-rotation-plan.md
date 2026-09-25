# M2 Seller CouchDB credential rotation: offline plan evidence

- Test M2-SELLER-CDB-ROT-PLAN-01: **PASS** for offline input checks and runbook syntax/phase separation only. Actual credential rotation M2-SELLER-CDB-ROT-01 is **NOT RUN**.
- Offline checks completed by 2026-09-25T19:12:59Z. The command results below were observed before any rotation action. The three `make` checks and block checksum below ran in `/Users/yjydist/Code/supplyledger-lab` on clean main; script syntax, shell-block parsing, fake controls and Git diff checks ran in `/Users/yjydist/Code/supplyledger-lab-seller-couchdb-rotation`. The live read-only runtime checker ran from the isolated worktree using its `scripts/verify-m2-seller-couchdb-runtime.py` and explicitly pointed to the main deployment and private env roots.
- Candidate source: isolated ops/seller-couchdb-rotation based on clean main e767c34d95e735d70ed8a7b22f29e30eaba1b91f. Resolve the introducing commit after independent review with git log --diff-filter=A -1 --format=%H -- docs/m2-seller-couchdb-credential-rotation.md. No final commit is invented before review.
- Lock: versions.lock.yaml SHA-256 e4600225619dd24545b047623ab22090a03317c1b60ee898ff08c1778efa64d1. Existing Compose tier: bootstrap.yaml + ca.yaml + network.yaml with bootstrap and ca profiles. Original retained block file SHA-256 b0a5ec0894d45ca7b6577b8f576d176347ad90cb4f80ac18de2dea3cc5ebd08a is a file checksum. The previously verified `genesisHash = canonical BlockHeaderHash(block0)` is 5c68bf099e95b934b6034a4d7aa8c52442751c30bc8b56fcbbde9b0138e38ba7; this offline plan did not fetch a block.
- Existing private input observation, with no values displayed: the two Seller env files are regular mode 0600 under mode-0700 directories; their corresponding CouchDB and Peer environment keys match the running containers in memory. Only sanitized PASS lines were printed. Exact Seller mount destinations, types, expected source ownership and read-only bits, networks and unpublished ports were checked. The CouchDB has only the named /opt/couchdb/data mount, not a persistent /opt/couchdb/etc mount. This read-only observation does not rotate or re-authenticate the password.

## Actual offline commands and results

| Command/check | Expected | Actual | Verdict |
| --- | --- | --- | --- |
| make network-config | Exact M2 topology without env values | Exit 0; static topology PASS | PASS |
| make verify-m2-nodes | Current old rendered configs and six env files match current main | Exit 0; three separate org secrets and six node YAMLs PASS | PASS |
| make verify-m1 | Tracked M1 cert/MSP/TLS inventory matches retained runtime | Exit 0; static M1 PASS | PASS |
| shasum -a 256 .runtime/channel/supplychannel.block | Original #17 artifact file SHA | Exit 0; b0a5ec...d08a | PASS |
| python3 -m py_compile scripts/verify-m2-seller-couchdb-rotation.py, scripts/verify-m2-seller-couchdb-runtime.py and scripts/test-verify-m2-seller-couchdb-runtime.py; bash -n scripts/m2-seller-couchdb-rotation-state.sh | Source parses | All exit 0 | PASS |
| Parse each runbook shell block with bash -n; count Docker commands | Each independent block parses, reloads state after setup, at most one Docker operation | 40 blocks parsed; all later blocks loaded state; no block had multiple Docker operations | PASS |
| python3 scripts/verify-m2-seller-couchdb-runtime.py --secrets-root /Users/yjydist/Code/supplyledger-lab/.secrets --deployment-root /Users/yjydist/Code/supplyledger-lab --component both | Running Seller DB/Peer env equals their private files; exact expected mounts and networks, no published ports; no raw Docker inspect output | Exit 0; two sanitized PASS lines naming components only | PASS |
| python3 scripts/test-verify-m2-seller-couchdb-runtime.py | Expected mounts and /host_mnt normalization accept; extra cross-org Peer/DB private mounts, wrong private source, writable private bind, wrong named or anonymous volume and duplicate mount reject | Exit 0; seven unsafe mutations rejected | PASS |
| Fake mode-0700/0600 env-pair fixture via verifier CLI | Distinct matched pair accepts; mismatch, unchanged secret, permissive file and symlink reject | Exits 0 / 1 / 1 / 1 / 1 | PASS |
| Fake rotation-state fixture via Bash source | Valid marker accepts; marker 0644, target 0755, path escape and missing marker reject | Exits 0 / 1 / 1 / 1 / 1 | PASS |
| Fake half-switch/half-rollback fixture via verifier CLI | Reject mixed pair at either midpoint; accept complete candidate and complete rollback | Exits 0 / 1 / 0 / 1 / 0 | PASS |
| git diff --check | No whitespace errors | Exit 0 | PASS |

The fake fixture passwords were fixed test strings in temporary directories, not live credentials; the temporary directories were removed automatically. These checks do not prove CouchDB admin reconfiguration, restored volume contents, a live Peer health result, or Discovery. No Seller service was stopped or recreated, no volume was exported, and no new credential was generated for the actual network.

## Live §19.1 record to fill only after reviewed execution

| Stage | Current verdict | Record after execution |
| --- | --- | --- |
| Before state | NOT RUN | UTC; source/lock/image; M1; nine container IDs and volume Name/CreatedAt; six env file fingerprints; original block artifact/header; Seller list/getinfo |
| Local cold-state recovery point | NOT RUN | Separate Peer-stop/DB-stop exits; two stopped-volume tar command/log/exit and archive SHA; private extraction check; old-env controlled copy; no §16.4 full-backup claim |
| New credential input | NOT RUN | Candidate/active verifier exits; exact two-file stage/switch results; no password values |
| CouchDB gate | NOT RUN | Force-recreate exit/new ID/same volume; new admin-only HTTP 200, old credential HTTP 401/403; response bodies/headers discarded |
| Peer gate | NOT RUN | Force-recreate exit/new ID/same ledger; TLS and /healthz; separate native list/getinfo exits, actual height/header; seven other node IDs unchanged |
| Cleanup or rollback | NOT RUN | Independent acceptance, old-env copies removed or exact rollback phase and old-admin/Peer results; private new-env backup and updated #16 baseline |

Full SPEC §16.4 cold backup/restore, T-OPS-08, #16 Discovery migration and #18 NET-07 remain **NOT RUN** here. No channel or business transaction was submitted by these offline checks; no new txId, block height or validation code exists for this plan.
