# M2 issue #15 — base Compose topology and static safety

- Issue: https://github.com/yjydist/supplyledger-lab/issues/15
- Checked: 2026-09-25 on a `darwin/arm64` host, Docker container platform `linux/aarch64`, Docker Compose `v5.5.1`.
- Test IDs: `M2-I15-01` through `M2-I15-06`; full `T-NET-02` is **NOT RUN**.
- Specification: `SPEC.md` §§3.1–3.5, 19.1–19.2 and 20.1 (`T-NET-02`); `CON-08`.
- Source commit: the commit introducing this report; resolve its full SHA after review with `git log --diff-filter=A -1 --format=%H -- evidence/m2/issue-15.md`. The verified M1 baseline is `e2c0693995d12bb0e22609607fc1cd1863405236` (#13, after M1 tracker #8 closed).
- Version lock: `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`; Fabric Peer/Orderer `3.1.5`, Fabric CA `1.5.22` and CouchDB `3.4.2` use the measured image references and digests already in that file.
- Compose tier: `compose/bootstrap.yaml` + `compose/ca.yaml` + `compose/network.yaml`, with `bootstrap` and `ca` profiles enabled for static model rendering. The nine M2 Orderer/Peer/CouchDB services have no profile. No M2 node or database container was started in this issue.
- Channel/genesisHash: **NOT RUN**; no M2 channel genesis block exists. txId, block height and validation code: **NOT RUN**; these static Compose checks submit no Fabric transaction. A rejected Compose mutation fails before any network service starts.
- Prepared data: nine existing CA named volumes from M1; the M2 overlay declares nine additional separate data volumes, but none existed during this check. M2 #16 supplies node configuration files and ignored per-organization CouchDB credential env files. The checker uses `--no-env-resolution` and does not print credential values. No private key, CA database or password was copied into this worktree or evidence.

## Commands and observed outcomes

All commands were run in the isolated issue #15 worktree. The static verifier reads the rendered Compose model; its source and negative controls are [verify-m2-compose.py](../../scripts/verify-m2-compose.py) and [test-verify-m2-compose.py](../../scripts/test-verify-m2-compose.py).

```sh
make network-config
make test-m2-compose
make ca-config
make -n stop down
make reset  # CONFIRM_DESTROY deliberately absent; expected exit 2
docker volume ls --filter label=com.docker.compose.project=supplyledger --format '{{.Name}}'
docker ps --filter label=com.docker.compose.project=supplyledger --format '{{.Names}}'
bash -n scripts/reset.sh
```

| Test | Expected | Actual | Judgment |
| --- | --- | --- | --- |
| `M2-I15-01` base Compose render and policy | Three Orderers, three organization Peers and their distinct CouchDBs; exact 19-service/5-network model including nine CAs and tools; pinned images, exact SAN DNS aliases, one shared Fabric and four internal organization networks, no host ports or socket mounts; read-only node identity binds and separate state volumes | `make network-config` exited 0. It printed `PASS: shared Fabric network and four separate internal organization networks`, `PASS: 18 distinct, explicitly reset-labeled named volumes; no backup target`, and `PASS: 3 Orderer, 3 Peer, 3 CouchDB; pinned images, exact DNS/networks, isolated state and read-only identity mounts, no host ports or docker.sock`. Its final line said live Docker inspect/full `T-NET-02` and CCaaS were `NOT RUN`. | **PASS**, static rendered model only |
| `M2-I15-02` policy negative controls | Checker rejects unsafe or drifted rendered declarations | `make test-m2-compose` exited 0. In temporary copies it accepted the unmodified model and rejected eight mutations: published Orderer port, shared Peer volume, swapped Peer volumes, cross-organization Peer MSP bind, unlocked image pull, wrong Fabric network name, extra no-profile Docker-socket service and Peer `CORE_PEER_TLS_ENABLED=false` environment override. Each mutated run exited 1 for its expected policy reason. | **PASS**, checker regression controls |
| `M2-I15-03` M1 overlay compatibility | CA-only overlay still parses without the M2 overlay | `make ca-config` exited 0 with `PASS: M1 CA Compose config; use network-config for the M2 overlay`. No CA was started or re-enrolled. | **PASS**, static CA model |
| `M2-I15-04` retention command wiring | `stop`/`down` use all three overlays without `-v`; unconfirmed reset prints exact existing eligible volumes and rejects deletion | `make -n stop down` exited 0 and printed the three-overlay `docker compose ... stop` and `... down` commands with no volume flag. `make reset` printed `Reset target named volumes (9)` listing only the existing nine `supplyledger_ca_*` data volumes, then `Backups are not selected or deleted` and `NOT RUN: reset requires CONFIRM_DESTROY=supplyledger`; it exited 2. `bash -n scripts/reset.sh` exited 0. No M2 data volume existed. | **PASS** for static wiring and refusal; actual `stop`/`down` data retention **NOT RUN** |
| `M2-I15-05` real `T-NET-02` | Inspect running Peer/CA/DB mounts, ports, isolation and distinct state volumes; review repository secrets | `docker ps` showed no running `supplyledger` containers. No Peer, Orderer or CouchDB startup, `docker inspect` or full `T-NET-02` was performed. M2 [#16](https://github.com/yjydist/supplyledger-lab/issues/16) owns the live check and [#20](https://github.com/yjydist/supplyledger-lab/issues/20) reconciles stage evidence. | **NOT RUN** |
| `M2-I15-06` CCaaS base services | Three no-profile services with repository-built digest-pinned image and Peer→CCaaS mTLS | No runnable CCaaS image, server credentials or external-builder Peer image exists in M2 #15. M3 [#22](https://github.com/yjydist/supplyledger-lab/issues/22) owns the three declarations on these same organization networks and separate state as required by §3.5. | **NOT RUN** |

The `docker volume ls` command returned the nine CA volumes only, matching the guarded reset list. `make network-config` does not start nodes, create volumes or prove node behavior. The static model's no-port/no-socket assertion must be checked again with real Docker inspect after #16 supplies configuration, starts nodes through native first-run steps and records redacted output. Full `T-NET-02` cannot be marked **PASS** from this report.

The [topology guide](../../docs/m2-compose-topology.md) maps each network, mount and data volume to its later consumer. The current Peer image is the measured official Fabric 3.1.5 image for M2 networking; M3 #22 must replace it in place with the repository-built external-builder Peer image before chaincode work. The M2 node configuration and genesis/channel participation work remain with #16–#20. This report records no genesisHash, endpoint handshake, Raft readiness, transaction or block result.
