# M0 issue #6 — initial ADRs and evidence template

- Checked at: 2026-09-24T10:24:30Z
- Issue: https://github.com/yjydist/supplyledger-lab/issues/6
- Specification: §§3–5, 11, 17.2, 18.4, 19.1; ADR-001, ADR-002, ADR-004
- Source commit: the commit introducing this report and the three ADRs; resolve the full SHA after commit with `git log --diff-filter=A -1 --format=%H -- evidence/m0/issue-6.md`. The repository baseline before this change was `5e7b0b38774b7c3f7b8dfe835cf1fdcfee32139e`.
- Version lock digest: SHA-256 `96c9eda6334736ecddfa35de430de26812da9d1518b10441efefc9ad2d8e08f0` for `versions.lock.yaml` at review time; refresh this line if the lock changes before commit
- Compose tier: **NOT RUN**; this issue changed documentation only
- Network genesisHash: **NOT RUN**; no channel exists
- Prepared data: `SPEC.md`, issue #6 requirements, and the current version lock; no business fixture or secret
- txId / block height / validation code: **NOT RUN**; no Fabric transaction was submitted

## Deliverables and verification

The files added for this issue are `docs/adr/ADR-001-single-channel-and-private-terms.md`, `docs/adr/ADR-002-ccaas-external-builder-no-socket.md`, `docs/adr/ADR-004-local-identity-custody-and-host-trust.md`, and `docs/evidence-template.md`. Each ADR states the relevant constraints, implementation decision, tradeoffs, tests and current verification limit. The template names every §19.1 evidence field and keeps absent runtime values explicitly `NOT RUN`.

```sh
rg -n '^# ADR-|^## (背景与约束|决策|取舍|取舍与信任声明|验证与重新评估)' docs/adr/ADR-001-single-channel-and-private-terms.md docs/adr/ADR-002-ccaas-external-builder-no-socket.md docs/adr/ADR-004-local-identity-custody-and-host-trust.md
rg -n 'memberOnlyRead=true|memberOnlyWrite=true|requiredPeerCount=1|maxPeerCount=3|blockToLive=0' docs/adr/ADR-001-single-channel-and-private-terms.md
rg -n '测试编号|源码 commit|版本锁|Compose 档位|genesisHash|准备数据|实际命令|预期结果|实际结果|判定|txId|区块高度|validation code' docs/evidence-template.md
python3 -c 'from pathlib import Path; files=[*Path("docs/adr").glob("ADR-*.md"), Path("docs/evidence-template.md"), Path("evidence/m0/issue-6.md")]; assert len(files)==5; assert all(p.read_bytes().endswith(b"\n") and b"\r" not in p.read_bytes() and not any(line.rstrip()!=line for line in p.read_text().splitlines()) for p in files); print("five documentation files: LF, final newline, no trailing whitespace")'
if rg -n -- "$(printf '%s%s' '-----' 'BEGIN')|$(printf '%s%s' '-----' 'END')|[A-Za-z0-9+/]{80,}" docs/adr docs/evidence-template.md evidence/m0/issue-6.md; then exit 1; fi
shasum -a 256 versions.lock.yaml
```

| Test ID | Expected result | Actual result | Judgment |
| --- | --- | --- | --- |
| M0-I6-01 ADR scope | ADR-001/002/004 document constraints, decision, tradeoffs and verification limits without claiming runtime success | Three files added with those sections and explicit M1–M8 checks | PASS |
| M0-I6-02 evidence template | Reusable §19.1 fields include lock digest, genesisHash, commands, actual outcomes and clear verdict | Template contains all required fields plus failure stage, tx and performance guidance | PASS |
| M0-I6-03 formatting and redaction | Documents use LF and contain no actual credential material | Five files passed newline/whitespace and PEM/high-entropy marker checks; no secret value was introduced | PASS |
| M0-I6-04 runtime architecture | PDC privacy, CCaaS/mTLS, MSP/TLS and API custody are observed in a real network | No CA, Peer, channel, chaincode or API was started for this documentation issue | NOT RUN |

The first marker scan matched its own literal command in this report. The recorded command constructs that marker at runtime; it exited 0 with no matches. This was a test-command false positive, not a discovered secret.

These ADRs record intended boundaries only. They do not replace the real Fabric, CA, privacy or host-boundary tests assigned to later milestones. No key, registrar secret, token, private term, database or backup was created or included in the report.
