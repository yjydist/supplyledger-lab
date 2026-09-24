# M0 issue #3 — measured versions and ARM64 environment

- Checked at: 2026-09-24T09:01:06Z
- Issue: https://github.com/yjydist/supplyledger-lab/issues/3
- Specification: §§2.1–2.3, 19.1; CON-05
- Source commit: the commit introducing this report; resolve its full SHA with `git log --diff-filter=A -1 --format=%H -- evidence/m0/issue-3.md`. The repository baseline before this change was `0f912e9da0456639f2ca231721be22caf38f0ad8`.
- Version lock digest: SHA-256 `600fe6b8fe16786fc42f948f5a2cb8c340ede9579f5611a757be9bb6e2a4d285` for `versions.lock.yaml`
- Compose tier: **NOT RUN**; no Compose stack or Fabric network was started
- Network genesisHash: **NOT RUN**; no channel exists
- Prepared data: six fixed Linux ARM64 images pulled; official Fabric, Fabric CA, and Go release archives downloaded into automatically deleted temporary directories for checksum and binary checks; no ledger data
- txId / block height / validation code: **NOT RUN**; no Fabric transaction was submitted

## Host and container environment

| Measurement | Actual result |
| --- | --- |
| Host | macOS 27.0 build 26A428, Darwin/arm64, 51,539,607,552 bytes RAM |
| Docker | Docker Desktop 4.92.0 build 240144; client and Engine 29.8.0, API 1.56; client commit `88096ef`, Engine commit `3ce5872` |
| Container runtime | Linux/arm64, 14 CPUs, 16,481,579,008 bytes memory, overlayfs; `desktop-linux` context |
| Compose / buildx | Compose v5.5.1; buildx v0.37.1 |
| Host Go | go1.27.1 darwin/arm64; not used as the fixed project build toolchain |
| Storage at check | 474 GiB free on the workspace filesystem |

All selected images have native Linux ARM64 manifests; no AMD64 emulation was used. The Docker memory allocation fits the initial dev budget in §2.3, but no running-network resource measurement or performance test has been made.

## Image pull and manifest verification

For each of the six `images.*.reference` values in `versions.lock.yaml`, `docker pull --platform linux/arm64 --quiet <reference>` exited 0. The check then fetched the tag's raw OCI index with `docker buildx imagetools inspect --raw <tag>`, computed its SHA-256, selected the `linux/arm64` child manifest, and inspected the pulled `<reference>` with `docker image inspect`. In every case the raw index digest matched `manifestDigest`, the child digest matched `platformDigest`, the local Descriptor matched the index digest, and the local image reported `linux/arm64`.

| Image key | Expected result | Actual result | Judgment |
| --- | --- | --- | --- |
| `fabricPeer` | Fabric 3.1.5 index and ARM64 digest match the pulled image | Both digests and local platform matched | PASS |
| `fabricOrderer` | Fabric 3.1.5 index and ARM64 digest match the pulled image | Both digests and local platform matched | PASS |
| `fabricCA` | Fabric CA 1.5.22 index and ARM64 digest match the pulled image | Both digests and local platform matched | PASS |
| `couchdb` | CouchDB 3.4.2 index and ARM64 digest match the pulled image | Both digests and local platform matched | PASS |
| `postgres` | PostgreSQL 17.10 index and ARM64 digest match the pulled image | Both digests and local platform matched | PASS |
| `goBuilder` | Go 1.26.8 Bookworm index and ARM64 digest match the pulled image | Both digests and local platform matched | PASS |

The manifest check used the following Python operations for each fixed reference, with expected values taken from the independent pull/inspection results now recorded in the lock:

```python
raw = subprocess.check_output(["docker", "buildx", "imagetools", "inspect", "--raw", tag])
index_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
arm64_digest = next(m["digest"] for m in json.loads(raw)["manifests"]
                    if m["platform"].get("os") == "linux"
                    and m["platform"].get("architecture") == "arm64")
local = json.loads(subprocess.check_output(["docker", "image", "inspect", reference]))[0]
```

## Release archives, binaries, and CLI versions

The expected archive hashes came from the official GitHub Release API `assets[].digest` for [Fabric v3.1.5](https://github.com/hyperledger/fabric/releases/tag/v3.1.5) and [Fabric CA v1.5.22](https://github.com/hyperledger/fabric-ca/releases/tag/v1.5.22), and the [Go downloads page](https://go.dev/dl/). Each archive was then actually downloaded and hashed locally. The archive and selected CLI binary SHA-256 values are in `versions.lock.yaml`; the official container binaries were hashed separately because their bytes differ from the release archive binaries.

| Archive | Official expected SHA-256 | Actual SHA-256 | Judgment |
| --- | --- | --- | --- |
| `hyperledger-fabric-linux-arm64-3.1.5.tar.gz` | `4a42cad740a7e0373eda6bf1e27c86e9b06132f9bb751daf7f0f7dc1d1bbfed9` | same; 108,669,436 bytes | PASS |
| `hyperledger-fabric-ca-linux-arm64-1.5.22.tar.gz` | `a2d8f5bf607dc38ce271d456244d754eb8f0a605332749285fcd1073ed19284f` | same; 31,590,513 bytes | PASS |
| `go1.26.8.linux-arm64.tar.gz` | `211ffced9dcb9633a55eac6364816ec0ddd951389a740e88fa8b3337971bdda0` | same; 63,811,405 bytes | PASS |

Commands and arguments used for source lookup and downloads:

```sh
gh api repos/hyperledger/fabric/releases/tags/v3.1.5 --jq '.assets[] | select(.name=="hyperledger-fabric-linux-arm64-3.1.5.tar.gz") | [.browser_download_url,.digest,.size] | @tsv'
gh api repos/hyperledger/fabric-ca/releases/tags/v1.5.22 --jq '.assets[] | select(.name=="hyperledger-fabric-ca-linux-arm64-1.5.22.tar.gz") | [.browser_download_url,.digest,.size] | @tsv'
gh release download v3.1.5 --repo hyperledger/fabric --pattern 'hyperledger-fabric-linux-arm64-3.1.5.tar.gz' --dir "$tmp_dir"
gh release download v1.5.22 --repo hyperledger/fabric-ca --pattern 'hyperledger-fabric-ca-linux-arm64-1.5.22.tar.gz' --dir "$tmp_dir"
curl -fL --retry 3 --silent --show-error -o "$tmp_dir/go1.26.8.linux-arm64.tar.gz" https://go.dev/dl/go1.26.8.linux-arm64.tar.gz
```

The temporary Python checks used `hashlib.sha256` on each downloaded archive, `tarfile` to read the binaries, and `hashlib.sha256` on their bytes. Version commands for Linux binaries ran in an existing Go Linux ARM64 image with `docker run --rm --pull=never --network none --read-only` and a read-only mount of the temporary directory. Pulled image CLI checks used the same restricted container options; image metadata was inspected with `docker image inspect`.

| Test ID | Expected result | Actual result | Judgment |
| --- | --- | --- | --- |
| M0-I3-01 host platform | Docker can run native Linux ARM64 and reports exact versions/resources | Host Darwin/arm64; Docker Linux/arm64; versions and resource values above | PASS |
| M0-I3-02 fixed images | All six versioned tag+digest references pull and their ARM64 manifests match locally | Six image rows above; all digest/platform comparisons matched | PASS |
| M0-I3-03 release checksums | Fabric and CA release tarballs match official release API hashes | Both downloaded hashes matched; binary hashes recorded separately | PASS |
| M0-I3-04 Fabric CLIs | Peer, Orderer, configtxgen report 3.1.5 and Linux ARM64; CA server/client report 1.5.22 | Fabric tools report v3.1.5, commit `86c1172`, Go 1.26.4; CA tools report v1.5.22, Go 1.26.4; image CLIs report matching versions | PASS |
| M0-I3-05 Go toolchain | Go 1.26.8 archive checksum matches Go's published value; the fixed build image runs the same Linux ARM64 Go executable with `GOTOOLCHAIN=local` | Archive hash matched; `go/bin/go` and image `/usr/local/go/bin/go` both SHA-256 `f69c40d8321223ad71f9107f6513950c760bd7c1f363f0c4273dec1d1d748425`; `go version` returned go1.26.8 linux/arm64 and `go env GOTOOLCHAIN` returned `local` | PASS |
| M0-I3-06 other image versions | PostgreSQL and CouchDB selected releases are present in the pulled ARM64 images | `postgres --version` returned 17.10; CouchDB image contains `/opt/couchdb/lib/couch-3.4.2` | PASS |
| M0-I3-07 module locks | Both Go module requirement lists and file hashes reflect the existing fixed module files | `go mod edit -json` requirements recorded in `versions.lock.yaml`; `go.mod` and `go.sum` SHA-256 match | PASS |
| M0-I3-08 network/Compose smoke | Network, Compose, and real Fabric behavior are exercised in their owning issues | No Compose configuration, CA identities, channel, or transactions yet | NOT RUN |

`osnadmin` from the verified Fabric archive has no `version` subcommand or `--version` flag; both commands returned argument errors. Its release origin is identified by the verified archive and its binary SHA-256, without claiming an unavailable version command succeeded. Calling CouchDB's `couchdb -V` without an admin account entered startup preflight and exited 1; this is not a version mismatch and no CouchDB service was started. No real enrollment, endorsement, MSP, PDC, MVCC, TLS, channel governance, or performance behavior was tested here.

M0 checks for LF line endings, executable file modes, container UID/GID mapping, time zone, bind-mount behavior, and Compose configuration are **NOT RUN** in this issue; the later doctor and tools work must record their own results.

The repository contains only the lock and this redacted report for issue #3. The temporary downloads were deleted automatically; no credentials, API token, registrar data, keys, runtime database, or backup were prepared or committed.
