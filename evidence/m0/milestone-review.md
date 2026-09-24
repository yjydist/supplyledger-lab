# M0 independent milestone review

- Reviewed at: 2026-09-24T11:48:28Z
- Scope: `SPEC.md` §§2.1–2.3, 5.1, 18.2–18.4, 19–19.2; GitHub milestone 1, parent issue #1, and native sub-issues #2–#7
- Reviewed source commit: `f2bddba69faddba3b3a0eac2666397eae5e5e3e9`. Local `HEAD` and remote `github/main` matched; the worktree was clean before this report was written.
- Version lock: `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`; measured host `darwin/arm64`, native containers `linux/arm64`
- Compose tier: `bootstrap` only. The formal network Compose, `dev`, and `resilience` tiers are **NOT RUN**.
- Network genesisHash, txId, block height, and validation code: **NOT RUN**; no CA, channel, or transaction exists at M0.
- Prepared data: the previously built local `supply-tools:m0-fabric3.1.5-ca1.5.22` image, seven pinned official images, and the two Go module locks. Verification used disposable containers and a temporary doctor bind-mount probe; no ledger, CA identity, persistent test volume, or backup was prepared.
- Redaction: this report contains only public commit IDs, image names, digests, versions, resource counts, and command outcomes. It contains no credential, private key, token, or private trade term.

## Independent commands and results

| Test ID | Actual command or inspection | Expected | Actual result | Judgment |
| --- | --- | --- | --- | --- |
| M0-REVIEW-01 source and issue state | `git status --short --branch`; `git rev-parse HEAD`; `git ls-remote github refs/heads/main`; GitHub milestone and sub-issue API | Review the pushed committed tree and all M0 children | Local and remote main both `f2bddba69faddba3b3a0eac2666397eae5e5e3e9`; children #2–#7 closed; parent #1 and milestone 1 open | PASS |
| M0-REVIEW-02 toolchain and module exit | `make verify-m0` | Check locked versions, images, CLI binaries, bootstrap Compose, doctor, both Go modules, and repository dependencies | Exit 0. Seven official image index/platform pairs and the local tools image descriptors matched the lock; six Fabric/CA CLI binary hashes, release versions, and OS package manifest matched. Doctor passed native platform, resource, LF/executable, bind read/write, UID, and UTC checks. Go 1.26.8 with `GOTOOLCHAIN=local` built, tested, vetted, and verified both modules. `go test` found no test files in either module. Sample/submodule and tracked secret scans passed. | PASS for M0 toolchain; business behavior tests NOT RUN |
| M0-REVIEW-03 Compose and shell checks | `make compose-config`; `shellcheck scripts/*.sh`; `git diff --check` | Bootstrap config parses; scripts and committed diff have no reported lint/whitespace errors | All exited 0. Only the bootstrap tools service was validated. | PASS |
| M0-REVIEW-04 guarded and future entry points | `make reset`; `make pki` without confirmation or M1 setup | Reset must list exact targets and refuse deletion; M1 target must not claim readiness | Each exited 2 with `NOT RUN`. Reset listed zero volumes and reported no change; `pki` identified M1 native first-run work. | PASS for guards; M1 execution NOT RUN |
| M0-REVIEW-05 deliverables and evidence | Read `versions.lock.yaml`, tools Dockerfile/context, doctor/reset/verification scripts, Go modules, ADR-001/002/004, and `evidence/m0/issue-2.md` through `issue-7.md` | M0 code, automatic verification, measured environment, initial ADRs, and redacted evidence exist | All named artifacts exist. The lock includes platform, image index/platform digests, CLI/binary checksums, source commits, Go toolchain, and module requirements. Evidence distinguishes actual checks from future network claims. | PASS |

The `make verify-m0` result was obtained after issue #7 had been committed and pushed. Docker Desktop exposed the doctor's temporary bind file as GID 0 although the container process GID was 20; the doctor recorded this as information and verified the file UID and actual read/write behavior. The report does not infer full future bind-mount permission behavior from this bootstrap probe.

## M0 acceptance against §19

| Requirement | Current evidence | Judgment |
| --- | --- | --- |
| Empty repository initialized and two locked Go modules build | Committed repository tree; `chaincode/go.mod`/`go.sum`, `app/go.mod`/`go.sum`; pinned Go 1.26.8 build/test/vet/module verification | PASS |
| Self-authored tools image and checkable Fabric/CA commands | `docker/tools/Dockerfile`, allowlisted build context, measured local image descriptor, six CLI hashes and version/help probes | PASS |
| Host, architecture, Go, Compose, and image measurements | Lock and issue #3/#4 reports; current doctor and verifier results on native ARM64 | PASS |
| `versions.lock.yaml`, doctor, dependency locks, environment report, initial ADR | Named files and six issue evidence reports; ADR-001/002/004 | PASS |
| No samples or prebuilt tools dependency, no Peer Docker socket at M0 | Executable source/submodule scan and tools image context review found no such dependency; no Peer image exists yet | PASS for M0 executable paths; future Peer runtime check NOT RUN |
| Compose validation | `make compose-config` and verifier parsed `compose/bootstrap.yaml` | PASS for bootstrap; formal §3.5 network Compose NOT RUN |
| Code, automated checks, and redacted stage evidence before M1 | Issue commits #2–#7, `make verify-m0`, and `evidence/m0/issue-2.md` through `issue-7.md` | PASS |

The project-built application CLI named in §5.1 is **NOT RUN** because §19 assigns its implementation to M3; issue #4's report records this explicitly. Formal CA enrollment, channel/genesis, CCaaS, endorsement, MSP, PDC, TLS, transaction, and business behavior tests are **NOT RUN** and must be judged in their owning milestones. A published tools registry manifest is also **NOT RUN**; only measured local Docker descriptors exist.

## Findings and recommendation

1. **Nonblocking, medium priority — global engineering checks lack run entries.** `SPEC.md` §18.2 requires discoverable format, Go race, static security, and dependency vulnerability checks. `Makefile:8–50` and `scripts/verify-m0.sh:165–173` currently expose build/test/vet, but no entries for those additional checks. Track and implement these gates as substantive Go code arrives, before claiming §18.2 complete. The specific §19 M0 toolchain exit remains satisfied.
2. **Nonblocking, low priority — diagnostic wording is inverted.** `scripts/verify-m0.sh:59` rejects an emulated platform when the lock says `false`, but its failure text says the lock “requires an emulated container architecture.” Correct the wording on a later relevant edit.

**Recommendation:** parent issue #1 and milestone M0 may close on the §19 M0 acceptance evidence above, after this milestone review is recorded. Do not treat closure as proof of the formal network or of the still-missing §18.2 run entries.
