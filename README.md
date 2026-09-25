# SupplyLedger Lab

This repository follows [SPEC.md](SPEC.md). Work proceeds by the M0–M9 milestones in §19.

## Start here: M0 tools and M1 CAs

```sh
make tools-build       # build the locked local CLI image on this host
make doctor            # check the host, Docker, tools, and a temporary bind mount
make compose-config    # validate compose/bootstrap.yaml only
make verify-m0          # check the M0 exit: pinned tools, both Go modules, and repository scans
make ca-config          # validate the nine-CA Compose overlay
make verify-m1           # compare issued identities and verify MSP/TLS trust material
make help              # list stage entry points
```

For M1, follow the [native CA runbook](docs/m1-ca-native.md) one CA at a time, then the [native identity runbook](docs/m1-identities-native.md) for separate registrar, user, admin and node issuance. The [identity evidence](evidence/m1/issue-10.md) records each first native command and the public certificate inventory. After issuance, use the [MSP assembly runbook](docs/m1-msp-assembly.md) to add local NodeOUs and build four public channel MSP inputs from measured roots. Run `make verify-m1` to check those identities, MSPs and the [TLS trust matrix](docs/m1-tls-trust.md) against the measured records; an isolated checkout can set `M1_RUNTIME_DIR` to the original ignored runtime path. The [M1 stage review](evidence/m1/issue-13.md) records the observed result and later test boundaries. CA startup requires an initialized private volume; `make pki` remains `NOT RUN` for automated issuance, because first registration and enrollment were performed with the native runbooks. `make network-up` and `make channel-create` (M2), `make chaincode-deploy` (M3), and later stages also exit `NOT RUN`. The formal §3.5 network Compose configuration is **NOT RUN**. If a fresh tools build has a different digest, `make doctor` fails until the image and version lock are reviewed together.

`make stop` stops the CA services. `make down` removes their containers and networks while retaining all nine CA data volumes. `make reset` prints the exact existing Compose named volumes selected for deletion, then refuses to change anything unless run as `CONFIRM_DESTROY=supplyledger make reset`. Once M1 is initialized, those targets are `supplyledger_ca_{seller,buyer,carrier,orderer}_{tls,enroll}` plus `supplyledger_ca_orderer_admin_tls`. It deletes only explicitly reset-enabled project data volumes; external volumes and backups are retained. Do not use reset as a backup procedure.

The `chaincode` and `app` directories are separate Go modules. Their dependency versions are fixed in each module's `go.mod` and `go.sum`.

Use Go 1.26.8 with `GOTOOLCHAIN=local` to build each module.
