# M0 issue #2 — repository skeleton and Go module locks

- Checked at: 2026-09-24T08:47:35Z
- Issue: https://github.com/yjydist/supplyledger-lab/issues/2
- Specification: §§2.1, 18.1–18.2, 19.1; CON-04
- Source commit: the commit introducing this report; resolve its full SHA with `git log --diff-filter=A -1 --format=%H -- evidence/m0/issue-2.md`. Record that SHA and the tested module snapshot in the issue #2 completion comment.
- Tested module snapshot: `e88e758ff581d9d99ef73cf70e11b7bcd16a61b8773f6f36d40922b51784810c` (SHA-256 of the `shasum -a 256` output for `chaincode/go.mod`, `chaincode/go.sum`, `chaincode/internal/contract/contract.go`, `app/go.mod`, `app/go.sum`, and `app/internal/gateway/contract.go`, in that order)
- Version lock digest: **NOT RUN**; `versions.lock.yaml` belongs to M0 issue #3
- Compose tier: **NOT RUN**; no network or Compose stack was started for this issue
- Network genesisHash: **NOT RUN**; no channel exists for this issue
- Prepared data: none
- txId / block height / validation code: **NOT RUN**; no Fabric transaction was submitted

## Toolchain and dependency source

The official `golang:1.26.8-bookworm` image was pulled for `linux/arm64`. The observed image reference was `docker.io/library/golang@sha256:a688600ca24f8a4d3ca77f95b0dd40704a9fc787c826660eb7ba0b641b8b175d`; `go version` inside it returned `go1.26.8 linux/arm64` with `GOTOOLCHAIN=local` and networking disabled for that version check.

Pinned direct modules match the upstream fixed-version declarations in [Contract API v2.2.3 go.mod](https://raw.githubusercontent.com/hyperledger/fabric-contract-api-go/v2.2.3/go.mod) and [Gateway v1.12.1 go.mod](https://raw.githubusercontent.com/hyperledger/fabric-gateway/v1.12.1/go.mod):

| Module | Version | Result |
| --- | --- | --- |
| `github.com/hyperledger/fabric-contract-api-go/v2` | `v2.2.3` | PASS |
| `github.com/hyperledger/fabric-chaincode-go/v2` | `v2.3.1-0.20260831054443-83a556592560` | PASS |
| `github.com/hyperledger/fabric-protos-go-apiv2` | `v0.3.7` | PASS in both modules |
| `github.com/hyperledger/fabric-gateway` | `v1.12.1` | PASS |

The Go module checksum database was enabled (`GOSUMDB=sum.golang.org`). `go mod verify` reported `all modules verified` in both modules. Neither module's source or production package dependency list imports the old `fabric-chaincode-go`, `fabric-protos-go`, or `github.com/golang/protobuf` package paths. `go.sum` does include a checksum for `github.com/golang/protobuf v1.5.4` through upstream module graph requirements; it is not imported by either production package list.

## Commands and results

The following command ran from the repository root. The first module was `chaincode`; the same checks then ran under `app`.

```sh
docker run --rm --platform linux/arm64 --user "$(id -u):$(id -g)" \
  -e GOTOOLCHAIN=local -e GOPROXY=https://proxy.golang.org,direct \
  -e GOSUMDB=sum.golang.org -e GOMODCACHE=/go/pkg/mod -e GOCACHE=/tmp/gocache \
  -v "$PWD":/work -v "$HOME/.go/pkg/mod":/go/pkg/mod -w /work \
  golang@sha256:a688600ca24f8a4d3ca77f95b0dd40704a9fc787c826660eb7ba0b641b8b175d \
  bash -euc 'go version
cd chaincode
go mod verify
go build -mod=readonly ./...
go test -mod=readonly ./...
go vet -mod=readonly ./...
cd ../app
go mod verify
go build -mod=readonly ./...
go test -mod=readonly ./...
go vet -mod=readonly ./...'
```

| Test ID | Expected result | Actual result | Judgment |
| --- | --- | --- | --- |
| M0-I2-01 chaincode module | Go 1.26.8 compiles the Contract API v2 package tree using its locked modules | `go build -mod=readonly ./...` exit 0; `go mod verify`: `all modules verified`; `go vet` exit 0 | PASS |
| M0-I2-02 app module | Go 1.26.8 compiles the Gateway package tree using its locked modules | `go build -mod=readonly ./...` exit 0; `go mod verify`: `all modules verified`; `go vet` exit 0 | PASS |
| M0-I2-03 dependency family | Only the specified v2 shim and apiv2 protobuf package families enter production builds | `go list -m` returned the four pinned versions above; `go list -deps ./...` found no old family package imports | PASS |
| M0-I2-04 unit tests | Module test commands execute without failure | Both `go test -mod=readonly ./...` commands exited 0 and reported `[no test files]`; no behavior tests exist at this milestone | PASS for command execution; behavior tests NOT RUN |
| M0-I2-05 real Fabric behavior | Live endorsement, MSP, PDC, MVCC, TLS, and channel governance are observed | No Fabric network in this issue | NOT RUN |

The dependency check also ran `go list -m` for each pinned module and `go list -mod=readonly -deps ./...` in both module directories within the same image. The production package lists contained the v2 shim and apiv2 protobuf paths and no old family package paths. `gofmt -l` returned no source filenames. No chaincode transactions, API requests, network operations, or secrets were used in these checks.
