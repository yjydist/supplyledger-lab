# SupplyLedger Lab

This repository follows [SPEC.md](SPEC.md). Work proceeds by the M0–M9 milestones in §19.

## Start here: M0 bootstrap only

```sh
make tools-build       # build the locked local CLI image on this host
make doctor            # check the host, Docker, tools, and a temporary bind mount
make compose-config    # validate compose/bootstrap.yaml only
make help              # list stage entry points
```

The bootstrap Compose file contains only a tools service. The stage entry points are `make pki` (M1), `make network-up` and `make channel-create` (M2), and `make chaincode-deploy` (M3); run `make help` for later stages. Their first native CA, channel, and chaincode commands must be recorded before automation, so these targets currently exit with `NOT RUN`. The formal §3.5 network Compose configuration is also **NOT RUN**. If a fresh tools build has a different digest, `make doctor` fails until the image and version lock are reviewed together.

`make stop` stops the bootstrap service. `make down` removes its containers and networks while retaining named volumes. `make reset` prints the exact existing Compose named volumes selected for deletion, then refuses to change anything unless run as `CONFIRM_DESTROY=supplyledger make reset`. It deletes only explicitly reset-enabled project data volumes; external volumes and backups are retained. There are no project data volumes in the M0 bootstrap Compose file. Do not use reset as a backup procedure.

The `chaincode` and `app` directories are separate Go modules. Their dependency versions are fixed in each module's `go.mod` and `go.sum`.

Use Go 1.26.8 with `GOTOOLCHAIN=local` to build each module.
