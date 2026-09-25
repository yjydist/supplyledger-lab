# M1 local and public MSP assembly

This is the post-issuance step for [issue #11](https://github.com/yjydist/supplyledger-lab/issues/11), SPEC.md §§4.2–4.3 and 19.1. Complete the [native CA](m1-ca-native.md) and [individual identity issuance](m1-identities-native.md) records first. This step copies **public roots only** into channel MSPs. It never registers, enrolls, renews or resets an identity or CA.

## Inputs and trust pin

`network/msp/trust-root-fingerprints.csv` records the nine CA root SHA-256 certificate fingerprints measured in [issue #9](../evidence/m1/issue-9.md). `evidence/m1/issue-10-certificates.csv` records the 41 issued identity certificates. The assembler checks the nine current ignored `.runtime/trust/*-ca.pem` roots against the pin, all 41 current signcerts against #10, and each local root copy against its corresponding pinned PEM **before writing**. A different root or reissued identity fails closed; verify and document any deliberate replacement and its dependencies before changing the manifests.

Run as the same host UID/GID that owns the 0600 signing keys. Generated MSPs stay in ignored `.runtime/`; no generated certificate, local MSP, CA database or private key enters Git or the tools image build context.

```sh
python3 scripts/assemble-msps.py build
python3 scripts/assemble-msps.py verify
python3 scripts/inspect-local-certs.py > .runtime/msp-probe/local-certificates.csv
```

`build` creates missing files exclusively and verifies matching existing files. It will not overwrite a differing Seller operator `config.yaml`, any other local config or an existing public MSP. A repeated `build` is idempotent. `verify` is read-only. The source certificate, signing key and CA volumes are never modified.

## Directory and copy boundary

For each of the **27 non-TLS-profile** CA-client, user and node identities, the existing private `.runtime/identities/<org>/<identity>/msp/` keeps its one `signcerts/cert.pem`, one 0600 `keystore/*_sk`, and one local `cacerts/*.pem`. The assembler adds a private 0600 `config.yaml` pointing each of client, peer, admin and orderer NodeOUs at that MSP's **existing** `cacerts` root. The Seller operator's initial #9 config is byte-for-byte preserved. The nine CA registrar local MSPs are for CA management only and must not be mounted into nodes or business services.

The other **14** identity directories are TLS-profile transport credentials: four Enrollment CA HTTPS servers, three Peer node TLS, three Orderer node TLS, three Orderer admin-server TLS, and one dedicated osnadmin client TLS. They keep their own `tlscacerts` and signing keys. The assembler does not add NodeOUs configs to them or turn them into channel-signing MSPs.

The public organization MSPs have exactly this structure, with `<org>` equal to `seller`, `buyer`, `carrier` or `orderer` and `<MSPID>` equal to `SellerMSP`, `BuyerMSP`, `CarrierMSP` or `OrdererMSP`:

```text
.runtime/public-msps/<MSPID>/msp/
  cacerts/<org>-enroll-ca.pem
  tlscacerts/<org>-tls-ca.pem
  config.yaml
```

No `cp -r` of a local MSP is used. The public `cacerts` file is an exact byte copy of the pinned ordinary Enrollment root, and `tlscacerts` is an exact copy of the pinned ordinary organization TLS root. The NodeOUs `Certificate` entries all name the local `cacerts/<org>-enroll-ca.pem`. Public MSPs contain no `keystore`, `signcerts`, `admincerts`, registrar files, generated CA YAML/DB, leaf TLS cert, or dedicated `orderer-admin-tls-ca.pem`. CRLs are absent because no revocation has been performed; add only genuine CA CRLs through a reviewed later change.

NodeOUs recognize four distinct certificate OUs: `client`, `peer`, `admin`, and `orderer`. Binding each role to the specific Enrollment root is intentional for the current single-root organizations; a future Enrollment root rotation needs an explicit MSP config/channel update. The public MSPs' root material may be distributed, but the generated directories are deployment-specific and remain ignored because a fresh native CA initialization produces different roots.

## Static Fabric parser check

The assembler also writes ignored `.runtime/msp-probe/configtx.yaml` with four organization definitions and minimal **parser-only** policies. It has no channel profile and is **not** the M2 `network/channel/configtx.yaml`, policy design or genesis block. The Orderer definition has three endpoints solely so pinned Fabric 3.1.5 `-printOrg` uses its Orderer organization parser.

Run the following command once for each of `SellerMSP`, `BuyerMSP`, `CarrierMSP`, and `OrdererMSP`, changing only the final ID and ignored output filenames:

```sh
docker run --rm --network none --read-only --tmpfs /tmp \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/public-msps,dst=/work/public-msps,readonly" \
  --mount "type=bind,src=$PWD/.runtime/msp-probe,dst=/work/probe,readonly" \
  --entrypoint configtxgen supply-tools:m0-fabric3.1.5-ca1.5.22 \
  -configPath /work/probe -printOrg SellerMSP \
  > .runtime/msp-probe/SellerMSP.json \
  2> .runtime/msp-probe/SellerMSP.log
```

Inspect `values.MSP.value.config` in each JSON: `name` matches the MSP ID, `root_certs` and `tls_root_certs` contain one public PEM each matching the pinned roots, `fabric_node_ous.enable=true` and all four roles reference the Enrollment root, `signing_identity=null`, and `admins=[]`. The Orderer group additionally encodes `Endpoints`; the other groups do not. [Issue #11 evidence](../evidence/m1/issue-11.md) records actual results. `-printOrg` proves the pinned Fabric CLI can parse and encode the **static public MSP**; it does not create a channel, start a Peer or Orderer, or prove live identity classification.

In M2, the real `configtx.yaml` must set each organization's `MSPDir` to its corresponding public MSP directory. A node's local MSP path must point only to that node's private ECert MSP, while its TLS certificate/key comes from its separate TLS-profile directory. The Orderer admin API server certificate uses the ordinary Orderer TLS CA; its **client trust root** alone uses the dedicated Orderer admin TLS CA. Do not add the dedicated root to the public `OrdererMSP`.
