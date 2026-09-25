# M1 issue #11 — local NodeOUs and public organization MSPs

- Issue: https://github.com/yjydist/supplyledger-lab/issues/11
- Checked: 2026-09-24 UTC, `darwin/arm64` host and Docker `linux/arm64`
- Test IDs: `M1-I11-01` through `M1-I11-07`; static partial evidence for `T-NET-02`, `T-NET-03`, and `T-ID-01`
- Specification: §§3.1–3.5, 4.1–4.3, 5.2–5.4, 19.1–19.2, 20.1; CON-03
- Source commit: the commit introducing this report; resolve its full SHA with `git log --diff-filter=A -1 --format=%H -- evidence/m1/issue-11.md`. The unchanged #10 baseline was `6526f79c93e50181b5c55ae19f1f1c7497a72f1f`.
- Version lock: `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`; local tools image `supply-tools:m0-fabric3.1.5-ca1.5.22`; native `configtxgen v3.1.5`, commit `86c1172`, Go `1.26.4`, `linux/arm64`.
- Compose tier: `compose/bootstrap.yaml` + `compose/ca.yaml`, `ca` profile, the nine previously initialized CAs only. The static parser used a short-lived, network-disabled tools container with read-only public inputs. Formal §3.5 Peer/Orderer/app Compose: **NOT RUN**.
- Channel/genesisHash: **NOT RUN**; no channel exists. txId/block height/validation code: **NOT RUN**; no Fabric transaction was submitted.
- Prepared data: nine root trust copies and 41 local issued certificates measured in #9/#10; 27 local non-TLS signing MSP directories (including nine CA registrar clients), 14 separate TLS-profile credential directories. The assembler wrote 26 new local `config.yaml` files, preserved the existing Seller operator config byte-for-byte, and created four ignored public MSP directories and an ignored parser-only fixture. No CA database, volume, root, leaf certificate or signing key was regenerated, overwritten or reset.
- Redaction: public root fingerprints and file layout are recorded; public PEM bytes, native tool JSON/logs, all local MSPs, CA state and the parser fixture remain under ignored `.runtime/`. Private secret values and key contents are absent from this report and tracked files. Host/Docker administrators remain within ADR-004's trust boundary.

## Native inputs, output boundary and actual commands

The [assembly runbook](../../docs/m1-msp-assembly.md) explains the trust pin and exact copy rules. [Nine pinned root fingerprints](../../network/msp/trust-root-fingerprints.csv) were extracted from the committed #9 first-run inventory, then re-read and matched against the current public `.runtime/trust/<ca>-ca.pem` certificates. The root manifest SHA-256 is `70a98465d3ea17726bc5765a40765b284877f7a64958dca469f707badeaacc41`. The [41-certificate #10 inventory](issue-10-certificates.csv) pins current signcert/public-key identities and roles; the assembler re-ran the #10 audit and rejected changed certificate metadata before writing.

The actual generation and read-only check were:

```sh
python3 scripts/assemble-msps.py build
python3 scripts/assemble-msps.py verify
```

Both commands exited 0. `build` wrote only missing 0600 local NodeOUs configs, the four public MSPs and the ignored parser fixture. A second `build` exited 0 and left the bytes **and mtime** of all 40 generated/config files unchanged. The existing Seller operator `config.yaml` remained at its original path, owner and mode. The 14 TLS-profile identities did not receive a NodeOUs file.

The public MSP allowlist is exactly these three files per organization, with `501:20:0644` ownership/mode on this host. Public MSP and its `cacerts`/`tlscacerts` directories are `0755`; the containing ignored runtime directory limits host access. Every public root file is byte-identical to the corresponding pinned local trust copy. Each public NodeOUs config names **its own Enrollment root** in all four role entries. Each local 0600 config similarly names the one root in its own local `cacerts` directory. The source local signing keys remain separate at `501:20:0600`, one per identity, with 0700 identity directories.

| MSP ID | Local non-TLS MSPs | Public `cacerts` | Public `tlscacerts` | Public `config.yaml` SHA-256 |
| --- | ---: | --- | --- | --- |
| `SellerMSP` | 7 | `seller-enroll-ca.pem` | `seller-tls-ca.pem` | `372a4773cd40f0ee05026c4ee337df319d7d926e4bce5ead64e77ec7050c53fc` |
| `BuyerMSP` | 7 | `buyer-enroll-ca.pem` | `buyer-tls-ca.pem` | `7c211071593e18211a6aafaeb481d01a24d3c89bda71038ba3cfcac31a2b1008` |
| `CarrierMSP` | 6 | `carrier-enroll-ca.pem` | `carrier-tls-ca.pem` | `2d703545a8f4f5df7310b39070e65978aa434b00272b841a255d67c84f9d33a0` |
| `OrdererMSP` | 7 | `orderer-enroll-ca.pem` | `orderer-tls-ca.pem` | `ba66edc1d372d99a2198927f012815f03a35dbf9237353c64bb19c5b8a73eff3` |

No public MSP contains `signcerts`, `keystore`, `admincerts`, registrar material, private-key marker, CA DB/config, leaf TLS cert, or the `orderer-admin-tls-ca.pem` dedicated management-client root. No CRL has been issued, so the public MSPs contain no CRL. This is a deliberate exact allowlist, not a recursive copy of local MSPs. The dedicated admin-client TLS root remains separate for the future Orderer admin API trust configuration.

## Pinned Fabric static parser result

The assembler's ignored `.runtime/msp-probe/configtx.yaml` is an **organization-only parser fixture**: it has four MSPDir references, required placeholder org policies, `Channel: V3_0`, and three Orderer endpoints so Fabric selects the Orderer organization parser. It has no channel profile and is not the M2 production `configtx.yaml`; none of its placeholder policy rules is asserted as final channel policy.

For each MSP ID, this exact command shape was run as a separate pinned `configtxgen` invocation, changing only the final ID and ignored output names:

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

| `-printOrg` argument | Native exit | Decoded `values.MSP.value.config` | Judgment |
| --- | ---: | --- | --- |
| `SellerMSP` | 0 | One Seller Enrollment root, one ordinary Seller TLS root, four NodeOUs pointing at Seller Enrollment root; `signing_identity=null`, `admins=[]` | **PASS, static parser** |
| `BuyerMSP` | 0 | One Buyer Enrollment root, one ordinary Buyer TLS root, four matching NodeOUs; no signer/admin cert | **PASS, static parser** |
| `CarrierMSP` | 0 | One Carrier Enrollment root, one ordinary Carrier TLS root, four matching NodeOUs; no signer/admin cert | **PASS, static parser** |
| `OrdererMSP` | 0 | One Orderer Enrollment root, one ordinary Orderer TLS root, four matching NodeOUs; no signer/admin cert; `Endpoints` present | **PASS, static parser** |

The JSON root and NodeOU certificate fields were base64-decoded and compared **byte-for-byte** with the pinned corresponding root PEMs. The JSON had empty intermediates and revocation lists. The Orderer JSON `Endpoints` field is the decoded representation of the parser fixture's `OrdererEndpoints`; it is not proof of an Orderer joining a channel.

The first static `-printOrg SellerMSP` probe failed at fixture policy parsing with `no policies defined`; a second probe with only an Admins policy failed with `no Readers policy defined`. Both returned exit 1 and produced no org JSON. The fixture was corrected to include the minimal parser-required policy keys; all four final probes passed. A separate post-parse Python assertion initially expected the raw YAML name `OrdererEndpoints` in decoded JSON, but Fabric emitted `Endpoints`; correcting the assertion made all four decoded-output checks pass. These diagnostic failures did not change CA or identity state and produced no channel transaction.

## Judgment and NOT RUN boundary

| Test | Expected | Actual | Judgment |
| --- | --- | --- | --- |
| `M1-I11-01` | Inputs stay pinned to native CA/identity evidence | Nine root fingerprints match #9; 41 current identity fingerprints/public keys, roles and roots match #10; 27 local key owners/modes checked | **PASS** |
| `M1-I11-02` | Every non-TLS local signer has signcert, one private key, own root and four-role NodeOUs | 27 matching `config.yaml` files with correct root references and mode; Seller operator preserved; 14 TLS profiles separate | **PASS, local file structure** |
| `M1-I11-03` | Four public channel MSP inputs contain only allowed public materials | Four exact three-file allowlists, pinned Enrollment and ordinary TLS roots, no private/leaf/registrar/dedicated admin root | **PASS** |
| `M1-I11-04` | Pinned Fabric CLI can parse public MSP definitions | Four `configtxgen v3.1.5 -printOrg` exits 0; decoded public roots and NodeOUs verified | **PASS, static parser** |
| `M1-I11-05` | Re-running assembly preserves previously issued material | Second build changed neither bytes nor mtime of 40 generated/config files; no re-enrollment or CA volume action | **PASS, local idempotence** |
| `M1-I11-06` | No secret/key material enters Git/build context/evidence | Final candidate-file and ignored-path checks below | **PASS** after final scan |
| `M1-I11-07` | Live channel MSP/authorization classification | No channel, Peer, Orderer or chaincode exists yet; M2/M8 own live checks | **NOT RUN** |

- Full `T-ID-01` remains **NOT RUN**: CA-side operator/quality issuance and static NodeOUs passed, but AuditMSP/auditor await M8 #64/#66 and live MSP/application signer checks await later milestones.
- Full `T-NET-02` remains **NOT RUN**: no Peer/Orderer/container network security inspection exists at this stage. The public MSP/key separation is a static partial result.
- Full `T-NET-03` and network genesisHash remain **NOT RUN**: no production `configtx.yaml`, block, channel config or live MSP classification was generated. M2 must use these public MSPs as inputs and independently validate the actual block/configuration.
- Orderer admin endpoint mTLS and Peer→CCaaS mTLS remain **NOT RUN**. Their certificate and trust paths are separate from channel MSP material.

## Final local verification

The following outcomes were observed after assembly:

| Command/check | Actual result | Judgment |
| --- | --- | --- |
| `python3 scripts/assemble-msps.py verify` | Exit 0; 27 exact local NodeOUs, 14 TLS profiles without NodeOUs, four exact public MSPs; pinned roots/41 signcerts/key owners checked | **PASS** |
| `python3 scripts/inspect-local-certs.py > .runtime/msp-probe/local-certificates.csv`; `cmp -s` against #10 CSV | Exit 0; current 41-row public certificate inventory is byte-identical to committed #10 evidence | **PASS** |
| `ruby` YAML parse of all local/public `config.yaml` files | 31 files parsed; each enables NodeOUs and has distinct client/peer/admin/orderer identifiers with a `cacerts/` certificate reference | **PASS** |
| Four pinned `configtxgen -printOrg` probes, decoded-root/OU Python checks | Four native exits 0; 1+1 correct public roots, four Enrollment-root-bound OUs, no signing identity/admin leaf | **PASS, static parser** |
| Repeated `python3 scripts/assemble-msps.py build` | Exit 0; SHA-256 bytes and nanosecond mtime of all 40 config/public/probe files unchanged | **PASS** |
| `make ca-config`; `make doctor` | Both exit 0; CA Compose parses and M0 host/tools checks pass; formal network readiness remains NOT RUN | **PASS for stated scope** |
| Candidate secret and formatting scan; `git check-ignore`; `git diff --check` | No value from 41 ignored secret files or private PEM marker appears in five changed files; runtime MSP/probe and secret paths are ignored; Python syntax/CSV parse/LF/whitespace pass | **PASS** |

No Peer/Orderer service, application channel, chaincode or business transaction was started or submitted. Consequently genesisHash, txId, block height and validation code remain **NOT RUN**, not zero or invented values.
