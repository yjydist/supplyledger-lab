# M1 TLS trust matrix and certificate-side checks

This is the M1 portion of [issue #12](https://github.com/yjydist/supplyledger-lab/issues/12), following the separate native CA and identity issuance in [#9](../evidence/m1/issue-9.md) and [#10](../evidence/m1/issue-10.md). It records which trust root and TLS identity each path must use under `SPEC.md` §§3.3–3.5, 4.4 and 5.5. The [read-only verifier](../scripts/verify-m1-tls-trust.py) checks the existing public certificates against the measured #9 root fingerprints. Node service configuration and live handshakes remain M2/M3 work.

The Enrollment CA roots authenticate ECerts for MSP membership. They are **not** the TLS roots for CA HTTPS, Peer, Orderer or the admin API. Root copies can be distributed; no local `keystore`, CA database, registrar credential or service TLS private key belongs in a public channel MSP, this document, or Git.

## Trust by path

| Path | Client verifies server with | Server identity and DNS | Server verifies client with | First live check |
| --- | --- | --- | --- | --- |
| CA client → each organization's TLS or Enrollment CA | That organization's `<org>-tls-ca.pem` | `ca-tls.<org>.supply.test` or `ca-enroll.<org>.supply.test`; public leaf copy `.runtime/trust/<org>-{tls,enroll}-server.pem` | CA enrollment uses its separate registrar credential; HTTPS does not require transport mTLS | M1 #9/#10 CA HTTPS probes |
| CA client → dedicated Orderer admin-client CA | `orderer-admin-tls-ca.pem` | `ca-admin-tls.orderer.supply.test`; `.runtime/trust/orderer-admin-tls-server.pem` | Dedicated CA registrar credential | M1 #9/#10 CA HTTPS probes |
| App / CLI → Peer Gateway | The target organization's `<org>-tls-ca.pem` | `peer0.<org>.supply.test`; `<org>-peer0-tls` | Fabric proposal identity is a separate ECert and MSP decision, not inferred from TLS | M2 #16/#18; transaction signer in M3 #26 |
| Peer / client → Orderer transaction endpoint | `orderer-tls-ca.pem` | `ordererN.orderer.supply.test`; `ordererN-tls` | Correct channel identity/policy for requests; node TLS identity may be used on transport as configured | M2 #16/#18 |
| Raft Orderer ↔ Orderer | `orderer-tls-ca.pem` in both directions | Distinct `orderer0-tls` through `orderer2-tls`, each with its actual DNS SAN; channel consenter TLS certs must match | `orderer-tls-ca.pem`; require client TLS purpose and mTLS in the node configuration | M2 #17/#19 |
| `osnadmin` → Orderer admin API | **Ordinary** `orderer-tls-ca.pem` | `ordererN-admin-server-tls`, SAN `ordererN.orderer.supply.test`, port 9443 | **Only** `orderer-admin-tls-ca.pem`; use the dedicated `osnadmin-client1-tls` certificate and its separate private key | M2 #16/#18 |
| Peer → same-organization CCaaS | The issuing root of `cc0.<org>.supply.test` service certificate, planned as `<org>-tls-ca.pem` | `cc0.<org>.supply.test`; no CCaaS server certificate issued in M1 | Same-organization TLS root and a **distinct per-Peer client TLS credential**; the existing `<org>-peer0-tls` node certificate is not evidence of that credential | M3 #22/#24 |
| Local user CLI → organization API | Exact API HTTPS root to be fixed with the API certificate | Per-organization loopback API endpoint | HTTPS plus local token bound to an existing same-organization ECert signer | M6 API work |

`<org>` means Seller, Buyer or Carrier where a Peer exists, and Seller, Buyer, Carrier or Orderer for CA HTTPS. The admin-client CA is a separate ninth CA. Its registrar certificate is held by CA operations and must not be mounted into an Orderer node or broad tools container. A root-only mTLS policy accepts any valid client certificate issued by that dedicated CA; therefore the CA registrar and issuance boundary is part of management access control. A business ECert or an ordinary Orderer node TLS certificate must not become an admin API client by sharing a broad trust root.

## M1 read-only verification

Run against the ignored runtime from the original CA issuance. The verifier requires OpenSSL 3 with `verify -verify_hostname`; on this macOS host it discovers the Homebrew executable because `/usr/bin/openssl` is LibreSSL. An explicit `--openssl /path/to/openssl` is available for other hosts.

```sh
make verify-m1-tls
# From an isolated worktree with no copied private runtime, point at the existing one:
make verify-m1-tls M1_RUNTIME_DIR=/absolute/path/to/supplyledger-lab/.runtime
```

It pins the five existing TLS roots to their measured #9 X.509 SHA-256 fingerprints and checks their self-signatures with `-check_ss_sig`. It then verifies 18 CA/Peer/Orderer/admin server certificates with the correct root, exact DNS SAN, explicit Digital Signature KU and serverAuth EKU, and TLS server purpose. Peer and Raft node TLS leaves also need explicit clientAuth EKU and client purpose. Each server leaf is challenged with a different pinned root and a wrong hostname; both must fail for the expected issuer or hostname reason. The dedicated `osnadmin-client1-tls` certificate must have explicit Digital Signature KU and clientAuth EKU, pass client-purpose validation under the admin-client CA root and fail under all four other pinned TLS roots. All chain probes use only the specified `-CAfile`, with default CA path/store disabled. This reads no private key and performs no CA enrollment or network change. Public issuer, root fingerprint, SAN, KU/EKU, purpose and file-ownership details are cross-referenced in the [#12 evidence inventory](../evidence/m1/issue-12.md#public-certificate-inventory-used-for-this-issue).

The issued Seller operator ECert is an important negative control: OpenSSL 3 accepts it under `verify -purpose sslserver` despite its missing TLS EKU, while the explicit EKU check rejects it. This guards against treating OpenSSL purpose validation alone as proof of TLS certificate suitability.

The issued admin-server and admin-client leaves have both server and client EKUs. An OpenSSL `-purpose` pass therefore establishes that the requested use is allowed by the certificate; it does not establish an exclusive TLS role. Separate issuing roots and the eventual admin endpoint's dedicated client-root configuration provide the intended separation.

The checks establish certificate and local trust-file suitability only. They inspect no Peer, Orderer, admin API or CCaaS consumer configuration. They cannot prove that a future container actually mounts the intended root, rejects a client during the handshake, or has no broad fallback CA bundle. The Peer→CCaaS row above is a future wiring contract and has no M1 certificate check.

## M2/M3 wiring and live acceptance

For each Orderer admin API, use `ordererN-admin-server-tls` as the server certificate and its own ignored private key. Configure client authentication as required and its client-root list with **only** the dedicated `orderer-admin-tls-ca.pem`. Do not put `orderer-tls-ca.pem`, an Enrollment CA root or all nine roots in that list. `osnadmin` must verify the admin server with `orderer-tls-ca.pem` and connect to its exact DNS name; its client certificate/key must be the separate `osnadmin-client1-tls` pair. A successful admin mTLS connection grants endpoint access, while channel configuration changes still require their own governance signatures.

In M2 #18, first inspect the rendered `orderer.yaml`, process mounts and exact root fingerprints. With the real Orderer endpoint, record success with the dedicated client credential and failure with no client credential, an ordinary Orderer/Peer TLS client credential, a wrong server root and a wrong DNS name. Complete full `T-NET-05` against a real Peer or Orderer in [#86](https://github.com/yjydist/supplyledger-lab/issues/86). Do not use `-k`, `--insecure`, `InsecureSkipVerify` or a trust-all bundle. Capture the observed TLS failure stage; no Fabric txId exists for a handshake rejected before submission.

In M3 #22, separately issue and mount the Peer→CCaaS client credential and CCaaS server certificate. The service DNS, peer-specific private key, root, `tls_required` and `client_auth_required` must be present in the actual builder release connection, with secrets absent from the shared package. Test both a valid connection and wrong root/CCID/artifact mapping on the running Peer. A M1 Peer node certificate is not proof of this mTLS path.
