# M2 #16 — NET-04 first Orderer startup checkpoint

This is the first **native** channel-less Orderer startup attempt. It failed while loading a TLS root file. The failure is retained as evidence; no channel join, Peer or CouchDB startup was attempted. The corrected source paths await independent review and integration before a retry.

- Test: `M2-I16-NET04-01` (SPEC.md §§5.2–5.4, 19.1). Full `T-NET-04` and `T-NET-02`: **NOT RUN**.
- Source commit at attempt: `f7960652b809eaedd53a637445cb583c6f0cda3e`; version lock SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`.
- Host: `darwin/arm64`; Docker `linux/arm64`; Orderer image `docker.io/hyperledger/fabric-orderer:3.1.5@sha256:dcb4c042237993a6f537b2f54e701e749f8e108f25c0cbe0c6742c205fccc3d5`.
- Compose tier: `bootstrap.yaml` + `ca.yaml` + `network.yaml`, project `supplyledger`, `bootstrap` and `ca` profiles. No M2 service was running before this attempt.
- Prepared data: retained ignored M1 identity/trust runtime and #17 native decoded candidate block; `make prepare-m2-nodes` created six ignored mode 0600 configs and six ignored mode 0600 organization-scoped env files. No credential value is reproduced here.
- Channel/genesisHash: **NOT RUN**; the native candidate block is not an observed live channel block. txId, block height and validation code: **NOT RUN**; this was a process startup failure before any Fabric transaction.

## Actual commands and result

| Command | Expected | Actual | Judgment |
| --- | --- | --- | --- |
| `make doctor`; `make verify-m1`; `make verify-m2-initial-block`; `make network-config`; `make prepare-m2-nodes`; `make verify-m2-node-block M2_INSPECT_BLOCK=.runtime/channel/inspect-block.json` | Locked tools and M1 roots match; candidate Raft certificates equal the rendered node paths; only ignored private outputs created | Each exited 0. `make prepare-m2-nodes` generated six configs and six env files; block-to-node verification matched all three consenters. Generated config and env directories are 0700; their files are 0600. | **PASS**, preflight only |
| `docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml -f compose/network.yaml --profile bootstrap --profile ca up -d --no-deps orderer0` | One channel-less Orderer starts and stays running | Compose returned 0 after container creation; the process then exited 1 at `initializeServerConfig`: `Failed to load TLS ServerRootCAs file 'open /run/supply/tls/tlscacerts/orderer-tls-ca.pem: no such file or directory'`. `docker inspect` reported `Status=exited`, `ExitCode=1`. | **FAIL**, configuration load stage; no admin request ran |

The original command output and full container startup log are retained only in ignored `.runtime/m2-node-logs/orderer0-start.log` and `orderer0-first-fail.log` in the main checkout. The tracked quotation above contains no private bytes or password. The actual M1 TLS MSP root file has a Fabric CA generated basename; the source YAML had assumed a fixed basename. The follow-up source correction uses an existing stable public root bind for Orderers and an explicit own-organization public root bind for each Peer.

`orderer1` and `orderer2` were **NOT RUN**. All admin mTLS acceptance/rejection, channel joins and live T-NET-02 inspection remain **NOT RUN**. A successful Compose return was not treated as node health.

## Reviewed retry gate — NOT RUN

The existing ignored six-file `.runtime/network-config` directory still contains the failed source paths. The preflight deliberately rejects changed generated output, and the exited Orderer0 container may retain its old file bind. After the correction is reviewed and integrated, follow the exact [one-time replacement procedure](../../docs/m2-node-config-native.md#one-time-recovery-from-the-first-orderer0-root-path-failure): archive the old configs and their hashes beside the retained failure logs, generate new configs from unchanged M1 material and existing credential files, prove the six root-path-only substitutions and unchanged credential hashes, then verify the original #17 block. Record the source commit and the named Orderer0 ledger volume before retry. Recreate **only** the failed Orderer0 container with `--force-recreate`, prove a new container ID and the same named ledger volume, and then inspect the actual process/admin response. No broad reset or volume removal is part of this recovery.

Those replacement, recreation and live API commands have **NOT RUN** at this checkpoint. The first FAIL above remains the observed result until the retry produces separate evidence.
