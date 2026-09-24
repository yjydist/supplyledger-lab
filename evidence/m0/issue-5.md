# M0 issue #5 — bootstrap operations and guarded reset

- Checked at: 2026-09-24T09:58:17Z
- Issue: https://github.com/yjydist/supplyledger-lab/issues/5
- Specification: §§2.2–2.3, 3.5, 18.3, 19.1, 21.1; CON-03; T-NET-02 and T-OPS-08 are future network checks
- Source commit: the commit introducing this report; resolve its full SHA with `git log --diff-filter=A -1 --format=%H -- evidence/m0/issue-5.md`. The baseline before this change was `a56565cd5d8909596709ea37aa850a55ae5d26f3`.
- Version lock digest: SHA-256 `96c9eda6334736ecddfa35de430de26812da9d1518b10441efefc9ad2d8e08f0` for `versions.lock.yaml`
- Compose tier: **bootstrap only**; `compose/bootstrap.yaml` parsed, but no service was started. The formal §3.5 network Compose and dev/resilience profiles are **NOT RUN**.
- Network genesisHash: **NOT RUN**; no channel exists
- Prepared data: locked local `supply-tools:m0-fabric3.1.5-ca1.5.22` image from issue #4; one isolated, disposable Docker volume was created and deleted for the reset test. No CA identity, ledger, business data, or backup was created.
- txId / block height / validation code: **NOT RUN**; no Fabric transaction was submitted

## Commands and observed results

```sh
bash -n scripts/doctor.sh scripts/reset.sh
make help
make -n tools-build        # inspect native-platform build command; no image rebuild
make compose-config
make doctor
make pki                  # exit 2, NOT RUN
make reset                # exit 2, NOT RUN; no project resources changed
CONFIRM_DESTROY=wrong make reset  # exit 2, NOT RUN
make stop                 # exit 0; no bootstrap service existed
make down                 # exit 0; no bootstrap service existed
CONFIRM_DESTROY=supplyledger make reset  # exit 0, exact target list was empty
docker volume ls --filter label=com.docker.compose.project=supplyledger --format '{{.Name}}'
git diff --check
```

The bootstrap Compose config parsed. `make help` listed every §18.3 target plus the M0 tools and config commands. A Bash loop ran `make pki`, `network-up`, `channel-create`, `chaincode-deploy`, `app-up`, `verify`, `test-e2e`, `test-fault`, `backup`, and `restore`; every target exited 2 with its own `NOT RUN` message and milestone pointer. The unconfirmed and wrong-confirmation `make reset` commands printed `Reset target named volumes (0): none` and stopped before `down` or deletion. The confirmed M0 reset also listed zero targets, then ran `down` without `-v`. The project volume query returned no names. `git diff --check` and Bash syntax checks passed.

`make doctor` passed its M0 bootstrap checks. It measured host `darwin/arm64`, Docker `linux/arm64` with 14 CPUs and 16,481,579,008 bytes assigned, host memory 51,539,607,552 bytes, and over 496 million KiB free at the workspace. Docker client/server were 29.8.0/29.8.0, Compose 5.5.1, and buildx v0.37.1. The bootstrap Compose image tag, locked local tools image digest, and platform matched `versions.lock.yaml`; the required Fabric, CA, and diagnostic commands executed with network disabled and a read-only container filesystem. The temporary bind probe executed an LF shell script, wrote and read a file, and verified process UID:GID `501:20`, created-file UID `501`, and container `TZ=UTC` offset `+0000`. The host offset was `+0800`. Docker Desktop presented that bind-mounted file with GID `0` rather than host GID `20`; doctor recorded this difference as `INFO` because process GID, file UID, and actual read/write behavior passed. The temporary probe directory was removed before doctor printed PASS. Formal network readiness was explicitly `NOT RUN`. An injected `mktemp` failure caused doctor to exit 1 before a probe write or PASS message.

The repository's unmodified `scripts/reset.sh` was exercised through `make reset` against the actual `supplyledger` M0 project without confirmation; it refused to proceed and had zero targets. A separate isolated fixture tested the nonempty target path. A temporary Compose file declared `data` with resolved name `supplyledger_issue5_qqnl6s_data` and `supplyledger.reset=allow`; its only service was a tools container, and no service was started. A disposable volume with that exact name was created with `com.docker.compose.project=supplyledger_issue5_qqnl6s`, `com.docker.compose.volume=data`, and the reset label. The fixture used a temporary copy of `reset.sh` with only its project name changed; its `repo_root` therefore resolved to the temporary fixture containing a link to the original version lock and the fixture Compose file. The volume selection and deletion logic were otherwise the same. This was a rehearsal of the reset logic, not deletion by the repository's `supplyledger` reset target.

```sh
docker volume create --name supplyledger_issue5_qqnl6s_data \
  --label com.docker.compose.project=supplyledger_issue5_qqnl6s \
  --label com.docker.compose.volume=data \
  --label supplyledger.reset=allow
bash "$fixture_dir/scripts/reset.sh"  # exit 2; listed volume remained
docker compose -p supplyledger_issue5_qqnl6s -f "$fixture_dir/compose/bootstrap.yaml" --profile bootstrap down
docker volume inspect supplyledger_issue5_qqnl6s_data  # still present
CONFIRM_DESTROY=supplyledger_issue5_qqnl6s bash "$fixture_dir/scripts/reset.sh"
docker volume inspect supplyledger_issue5_qqnl6s_data  # absent after exact deletion
```

The unconfirmed fixture reset listed exactly that one volume and preserved it. Compose `down` preserved the named volume. The confirmed reset again listed the one target, then removed exactly it. The temporary fixture files were removed. An earlier fixture driver written under zsh aborted because `status` is a read-only zsh variable; its disposable volume and temporary files were explicitly cleaned before the Bash rerun. No `supplyledger` project volume or backup was touched.

| Test ID | Expected result | Actual result | Judgment |
| --- | --- | --- | --- |
| M0-I5-01 host and tools doctor | Architecture, resources, Docker/Compose, lock, commands, mount, UID/GID, and time zone checked without false readiness claim | All functional M0 checks passed; Docker Desktop file GID remap recorded; formal network readiness labeled NOT RUN | PASS |
| M0-I5-02 bootstrap Compose | M0 Compose parses; no full network claim | Bootstrap config parsed; only a tools service was declared | PASS |
| M0-I5-03 stage entry points | Required target names discoverable; unimplemented stages fail nonzero | All §18.3 names listed; each of the 10 future targets exited 2 with NOT RUN and its milestone pointer | PASS |
| M0-I5-04 stop/down retention | Neither path removes named volumes by default | Commands contain no `-v`; isolated fixture volume survived `down` | PASS |
| M0-I5-05 reset protection | Exact Compose volumes listed; no deletion without confirmation; only explicitly labeled project data deleted | Empty M0 list refused without confirmation; isolated one-volume fixture survived refusal and was removed after exact confirmation | PASS |
| T-NET-02 formal network Compose | Inspect Peer/CA/DB isolation, mounts, ports, and secrets in the completed topology | Formal topology does not exist yet | NOT RUN |
| T-OPS-08 backup and recovery | Restore a deleted test-node volume from a cold backup | No network or backup exists yet | NOT RUN |

The local tools image was reused from issue #4; `make tools-build` was **NOT RUN** in this issue. A `make -n tools-build` check showed a Buildx command without a platform override, leaving platform selection to Docker's default; doctor still checks the resulting image and host against the measured lock. The bootstrap Compose file has no data volumes, so the confirmed reset against the actual M0 project deleted none. Its tested nonempty deletion path used only the isolated disposable fixture. M1–M3 first CA, channel, and chaincode commands remain manual until their redacted native-command evidence exists.
