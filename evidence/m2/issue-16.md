# M2 issue #16 — node configuration/preflight checkpoint

This report covers only the first reviewable configuration diff for [#16](https://github.com/yjydist/supplyledger-lab/issues/16). It is **not** a live T-NET-02 result. Continue it after #17 NET-03 is integrated and the NET-04/NET-05/NET-06 native sequence is observed.

- Test IDs: `M2-I16-01` through `M2-I16-04`; full `T-NET-02`, `T-NET-04` and `T-NET-05` remain **NOT RUN**.
- Specification: SPEC.md §§3.3–3.5, 4.4, 5.2–5.4, 16.1, 19.1 and 20.1.
- Source commit: the future reviewed #16 commit; after commit, resolve with `git log --diff-filter=A -1 --format=%H -- evidence/m2/issue-16.md`. The integrated baseline is `151170b9cda033ba7ddf9a1b7eb48c3dba9d265b` (#17, still open for live checks).
- Version lock: `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`; Fabric Peer/Orderer v3.1.5, CA v1.5.22, CouchDB 3.4.2; host `darwin/arm64`, container platform `linux/arm64`.
- Compose tier: static merged `bootstrap.yaml` + `ca.yaml` + `network.yaml`, `bootstrap` and `ca` profiles enabled for model rendering; the nine M2 services have no profile. No M2 container was started for this checkpoint.
- Channel/genesisHash: **NOT RUN** for this checkpoint; no live channel was joined or block-0 identity observed. Candidate block file SHA-256 would be an artifact checksum, not a substitute. txId, block height and validation code: **NOT RUN**; no Fabric transaction was submitted.
- Prepared data: current ignored M1 runtime in the main checkout, including the pinned 41 identities, nine roots and four public MSPs; #17's original native decoded candidate block copied byte-for-byte into the main checkout's ignored runtime; six tracked YAML templates; ephemeral mode 0600 node configs and six ephemeral env files made only in a temporary test directory, then removed. No actual CouchDB runtime password was created in the repo worktree or committed.
- Redaction: no private key or password bytes are printed. The temporary test checks that a generated password is absent from preflight stdout/stderr. Full `docker compose config` and raw `docker inspect` are intentionally excluded from evidence because they may expose env values after runtime preparation. Host/Docker administrator access remains within ADR-004's trust boundary.

## Commands and observed outcomes

Commands below ran against the isolated #16 worktree with `M1_RUNTIME_DIR` or `M2_SOURCE_RUNTIME_DIR` pointing to the original ignored main-checkout M1 runtime.

| Test | Actual command | Expected | Actual | Judgment |
| --- | --- | --- | --- | --- |
| `M2-I16-01` M1 input continuity | `make verify-m1 M1_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime` | 41 identities, public MSPs and five-root TLS trust matrix still match committed M1 pins | Exit 0; all 41 certificate rows, 27 local NodeOUs, 14 TLS profiles, four public MSPs, 5 roots, 18 service certs and admin-client negative controls passed offline | **PASS**, static M1 inputs |
| `M2-I16-02` Compose model | `make network-config`; `make test-m2-compose` | Exact nine M2 services and isolation; new private Peer env paths and Orderer trust-root mounts remain narrowly checked | Both exit 0; policy checker accepted base model and rejected ten unsafe mutations including cross-org Peer credential path and wrong admin client root | **PASS**, static model |
| `M2-I16-03` private runtime preparation and Raft pin | `make test-m2-nodes M2_SOURCE_RUNTIME_DIR=/Users/yjydist/Code/supplyledger-lab/.runtime M2_INSPECT_BLOCK=/Users/yjydist/Code/supplyledger-lab/.runtime/channel/inspect-block.json` | Temp preparation validates M1 cert/key pairs, generates six configs and distinct per-org CouchDB/Peer env files, repeated run unchanged; compares effective Orderer Raft certs byte-for-byte with decoded #17 block; nonzero/wrong-channel/non-CONFIG/multiple-envelope block, cross-org gossip bootstrap, partial Raft listener, bad secret, changed config/consenter cert, unsafe mode and unignored output rejected | Exit 0; ten reported subchecks passed; temporary outputs removed | **PASS**, offline candidate block and ephemeral preflight |
| `M2-I16-04` YAML syntax/diff hygiene | `ruby -e 'require "yaml"; Dir.glob("network/config/*.yaml").sort.each { |f| v=YAML.load_file(f); abort "invalid #{f}" unless v.is_a?(Hash); puts "PASS: #{f}" }'`; `git diff --check` | Six source YAMLs parse and tracked diff has no whitespace errors | Both exit 0; six YAML files parsed | **PASS**, source syntax |
| `T-NET-02` full runtime audit | Native starts and structured Docker inspect after #17/#18 sequence | Real mounts, ports, network membership, image digests, state volumes and repository/build contexts checked | No M2 node or CouchDB startup/inspect occurred in this checkpoint | **NOT RUN** |
| `T-NET-04` and admin mTLS | Three native Orderer starts and dedicated mTLS/wrong-client checks | Actual admin API responses and TLS rejections | No Orderer was started in this checkpoint | **NOT RUN** |

## Required continuation

The temporary comparison against #17's native candidate block passed, but the integrated runtime outputs and any live channel remain untested. Follow the [native runbook](../../docs/m2-node-config-native.md): prepare the ignored runtime inputs in the retained main checkout, verify the native block-to-node pin there, perform three individual channel-less Orderer starts and admin list checks (NET-04); #18's three individual Orderer joins (NET-05); then each CouchDB and Peer start plus full T-NET-02 runtime audit (NET-06). #18 performs Peer joins/anchors. Only observed results may change the NOT RUN rows above.
