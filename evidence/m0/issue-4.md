# M0 issue #4 — self-authored supply-tools image

- Checked at: 2026-09-24T09:23:39Z
- Issue: https://github.com/yjydist/supplyledger-lab/issues/4
- Specification: §§1.2, 2.1–2.2, 5.1, 19.1–19.2; CON-01, CON-02
- Source commit: the commit introducing this report; resolve its full SHA with `git log --diff-filter=A -1 --format=%H -- evidence/m0/issue-4.md`. The repository baseline before this change was `9ab5fedc0064650c5033e81d8e2380912def4719`.
- Version lock digest: SHA-256 `96c9eda6334736ecddfa35de430de26812da9d1518b10441efefc9ad2d8e08f0` for `versions.lock.yaml`
- Compose tier: **NOT RUN**; no Compose stack was started
- Network genesisHash: **NOT RUN**; no channel exists
- Prepared data: pulled Ubuntu 24.04 Linux ARM64 base image and locally built `supply-tools:m0-fabric3.1.5-ca1.5.22`; no CA identity, ledger, or business data
- txId / block height / validation code: **NOT RUN**; no Fabric transaction was submitted

## Source and build

`docker/tools/Dockerfile` uses the Ubuntu 24.04 OCI index pinned by digest. The official [Fabric v3.1.5](https://github.com/hyperledger/fabric/releases/tag/v3.1.5) and [Fabric CA v1.5.22](https://github.com/hyperledger/fabric-ca/releases/tag/v1.5.22) Linux archives are selected by BuildKit `TARGETARCH`; unsupported architectures fail. The expected archive SHA-256 values came from the official GitHub Release API and match the independently downloaded ARM64 archives recorded in issue #3. The Dockerfile checks each downloaded archive before extracting only the required binaries. No downloaded script is executed.

The build context was `docker/tools`, with `.dockerignore` allowing only its Dockerfile and ignore file. The build output reported a 70-byte ignore file and no source context transfer. The Dockerfile pins the eight directly installed Ubuntu diagnostic packages to exact versions. Ubuntu's signed package source in this ARM64 image is `http://ports.ubuntu.com/ubuntu-ports/`, with the `noble`, `noble-updates`, `noble-backports`, and `noble-security` suites. The direct versions and SHA-256 of the sorted *entire installed package manifest* are in `versions.lock.yaml`. Transitive packages are not individually pinned in the Dockerfile, so a future rebuild must compare that manifest and local image digest; this is not a claim of byte-identical rebuilds. A registry distribution digest is **NOT RUN** because this local image has not been pushed.

An ephemeral ARM64 base-container check of `APT::Snapshot "20260923T000000Z"` did not expose `jq` package metadata from the configured ports source. The final build used exact direct package versions from the current signed Ubuntu repository instead; it makes no snapshot reproducibility claim.

```sh
docker pull --platform linux/arm64 docker.io/library/ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
docker buildx imagetools inspect docker.io/library/ubuntu:24.04
set -o pipefail
docker buildx imagetools inspect --raw docker.io/library/ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 | shasum -a 256
docker buildx build --platform linux/arm64 --load --progress=plain -t supply-tools:m0-fabric3.1.5-ca1.5.22 -f docker/tools/Dockerfile docker/tools
docker image inspect supply-tools:m0-fabric3.1.5-ca1.5.22 --format '{{.Descriptor.Digest}} {{.Os}}/{{.Architecture}}'
docker image inspect --platform linux/arm64 supply-tools:m0-fabric3.1.5-ca1.5.22 --format '{{.Descriptor.Digest}} {{.Os}}/{{.Architecture}}'
```

The base pull returned index digest `sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3`; raw-index hashing matched it. The selected ARM64 manifest was `sha256:11dc1ccb427f0464a2369e645454c272bb0baece7357c892ba69d313b3a332cf`, and the pulled image reported `linux/arm64`. In the first build, both archive checks printed `OK`. After removing an unnecessary floating Dockerfile frontend tag, the final build reused those verified layers. Its local OCI index digest was `sha256:6b466c4dbd8aee240cbbc4c95860c4bf0b7a0de83b3edc808bc3dc71b895f8fe`; its local ARM64 manifest digest was `sha256:518f2c0569e28415082bce18a7d680a2232d811085542f13d51c0ca789e60c23`. These are local Docker artifacts, not published registry references.

One concurrent raw-index lookup failed with a transient Docker Hub authorization EOF; its piped hash was discarded. A retry with `pipefail` exited 0 and returned the pinned index digest above.

## Executable checks

CLI checks ran in the final image with `--pull=never --platform linux/arm64 --network none --read-only`. All six Fabric/CA binary SHA-256 values matched `releases.*.binariesSha256` in the version lock. The actual versions were:

| Command | Actual result |
| --- | --- |
| `peer version` | v3.1.5, commit `86c1172`, linux/arm64 |
| `orderer version` | v3.1.5, commit `86c1172`, linux/arm64 |
| `configtxgen -version` | v3.1.5, commit `86c1172`, linux/arm64 |
| `configtxlator version` | v3.1.5, commit `86c1172`, linux/arm64 |
| `fabric-ca-client version` | v1.5.22, linux/arm64 |
| `osnadmin --help` | Exit 0 and listed channel join/list/remove/update/fetch |
| `bash`, `jq`, `openssl`, `curl`, `tar`, `gzip` | 5.2.21, 1.7, 3.0.13, 8.5.0, 1.35, 1.12 respectively |

`osnadmin` does not report its Fabric release through a working version command in this artifact; the verified archive and its recorded binary SHA-256 establish provenance. The image also reported `aarch64`, and `command -v` found every required command. The complete sorted `dpkg-query -W` manifest hashed to `1c4abe3b235899fdf7f2c65707ae6e5d1fd3128b5c02600a6d5e105051c5d3d8`.

```sh
docker run --rm --pull=never --platform linux/arm64 --network none --read-only --entrypoint bash supply-tools:m0-fabric3.1.5-ca1.5.22 -euc '
  uname -m
  peer version
  orderer version
  configtxgen -version
  configtxlator version
  fabric-ca-client version
  osnadmin --help >/dev/null
  bash --version | head -1
  jq --version
  openssl version
  curl --version | head -1
  tar --version | head -1
  gzip --version | head -1'

docker run --rm --pull=never --platform linux/arm64 --network none --read-only --entrypoint bash supply-tools:m0-fabric3.1.5-ca1.5.22 -euc '
  sha256sum /usr/local/bin/{peer,orderer,configtxgen,configtxlator,osnadmin,fabric-ca-client}
  dpkg-query -W -f="\${Package}=\${Version}\n" | LC_ALL=C sort | sha256sum'

if rg -n 'fabric-samples|test-network|network\.sh|fabric-tools|docker\.sock' docker/tools; then exit 1; fi
```

| Test ID | Expected result | Actual result | Judgment |
| --- | --- | --- | --- |
| M0-I4-01 base image | Pinned official image pulls as native ARM64; index and child digests match | Pull, raw-index hash, manifest selection, and local platform matched | PASS |
| M0-I4-02 archive integrity | Fabric/CA fixed archives match official hashes before extraction | Both in-build `sha256sum --check` commands printed `OK` | PASS |
| M0-I4-03 CLI versions | Required commands exist, execute, and identify the fixed releases where supported | Version/help commands and six binary hashes matched the lock | PASS |
| M0-I4-04 diagnostics | Required diagnostic commands execute with recorded package versions | Six commands executed; eight direct package versions and full package manifest digest recorded | PASS |
| M0-I4-05 independent build context | No sample network, Docker socket, copied project secrets, or remote bootstrap script | Restricted context, explicit Dockerfile inspection, and forbidden-string scan passed | PASS |
| M0-I4-06 AMD64 build | The second architecture builds and its CLI binaries execute | Not built on this ARM64 host | NOT RUN |
| M0-I4-07 project-built CLI | Future application CLI is included once implemented | M3 CLI does not exist yet | NOT RUN |
| M0-I4-08 live network | Identities, channel, and transactions use this image | No CA/channel/network started in this issue | NOT RUN |

No registrar secret, private key, token, CA data, database, runtime state, or backup was created for this issue. The local tools image remains available in Docker; publishing and digest locking for a distributed image will require a separate release operation.
