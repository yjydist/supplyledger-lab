# SupplyLedger Lab

This repository follows [SPEC.md](SPEC.md). Work proceeds by the M0–M9 milestones in §19.

## Start here: M0 tools, M1 CAs and M2 static topology

```sh
make tools-build       # build the locked local CLI image on this host
make doctor            # check the host, Docker, tools, and a temporary bind mount
make compose-config    # validate compose/bootstrap.yaml only
make verify-m0          # check the M0 exit: pinned tools, both Go modules, and repository scans
make ca-config          # validate the nine-CA Compose overlay
make verify-m1          # compare issued identities and verify MSP/TLS trust material
make network-config     # validate M2 Peer/Orderer/CouchDB declarations without starting nodes
make help              # list stage entry points
```

For M1, follow the [native CA runbook](docs/m1-ca-native.md) one CA at a time, then the [native identity runbook](docs/m1-identities-native.md) for separate registrar, user, admin and node issuance. The [identity evidence](evidence/m1/issue-10.md) records each first native command and the public certificate inventory. After issuance, use the [MSP assembly runbook](docs/m1-msp-assembly.md) to add local NodeOUs and build four public channel MSP inputs from measured roots. Run `make verify-m1` to check those identities, MSPs and the [TLS trust matrix](docs/m1-tls-trust.md) against the measured records; an isolated checkout can set `M1_RUNTIME_DIR` to the original ignored runtime path. The [M1 stage review](evidence/m1/issue-13.md) records the observed result and later test boundaries. CA startup requires an initialized private volume; `make pki` remains `NOT RUN` for automated issuance, because first registration and enrollment were performed with the native runbooks. If a fresh tools build has a different digest, `make doctor` fails until the image and version lock are reviewed together.

The [M2 topology guide](docs/m2-compose-topology.md) explains the base Orderer/Peer/CouchDB overlay and its [static evidence](evidence/m2/issue-15.md). `make network-config` parses the merged Compose model and checks the pinned images, network membership, mounts and separate state volumes without starting a node. The three CCaaS declarations and self-built image belong to M3 [#22](https://github.com/yjydist/supplyledger-lab/issues/22); live Docker inspection and full `T-NET-02` belong to M2 [#16](https://github.com/yjydist/supplyledger-lab/issues/16). `make network-up` and `make channel-create` (M2), `make chaincode-deploy` (M3), and later stage targets still exit `NOT RUN` until their first native steps are recorded.

`make stop` covers the declared CA, Orderer, Peer and CouchDB services. `make down` removes their containers and networks while retaining their named data volumes. The M2 overlay declares nine new node/database volumes in addition to the nine existing CA volumes; declaring them does not create them. `make reset` prints the exact **existing** Compose named volumes selected for deletion, then refuses to change anything unless run as `CONFIRM_DESTROY=supplyledger make reset`. It deletes only explicitly reset-enabled project data volumes; external volumes and backups are retained. Do not use reset as a backup procedure.

The `chaincode` and `app` directories are separate Go modules. Their dependency versions are fixed in each module's `go.mod` and `go.sum`.

Use Go 1.26.8 with `GOTOOLCHAIN=local` to build each module.
