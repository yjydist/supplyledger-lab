# M1 native identity issuance

This is the manual continuation of the [nine-CA first run](m1-ca-native.md) for SPEC.md §§4.1–4.4 and 19.2. Use it only after confirming that all nine previously initialized CA roots match the recorded fingerprints in [issue #9 evidence](../evidence/m1/issue-9.md). Each first registration and enrollment is a **separate** native `fabric-ca-client` invocation. The [issue #10 ledger](../evidence/m1/issue-10.md) records the concrete commands, HTTPS trust root, ignored log and observed exit status for every identity.

Do not reinitialize or reset any CA volume to issue more identities. Keep `.secrets/identities/`, `.secrets/ca/`, `.runtime/identities/`, native logs, SQLite and CA private keys out of Git and the image build context. Set `umask 077` before creating credentials. A secret read from a read-only bind mount still appears transiently in native `register --id.secret` or `enroll --url` process arguments to Docker/host administrators (ADR-004). Redact these arguments and logs before sharing them.

## Issuance matrix

The Seller `operator1` ECert was already issued in #9 and is retained. Each new row gets its own secret file and local MSP directory. `ECert` rows use the organization's Enrollment CA; `TLS` rows use the indicated TLS CA and `--enrollment.profile tls`. Every CA connection uses its organization's verified HTTPS DNS and TLS root through `--tls.certfiles`. The `--caname` value is explicit even when the server has one CA.

| Organization | Identity (private directory suffix) | Issuing CA | `--id.type` | Business ECert attributes or TLS CSR DNS |
| --- | --- | --- | --- | --- |
| Seller | `operator1` (existing #9) | `seller-enroll-ca` | `client` | `supply.userId=seller.operator1:ecert,supply.role=operator:ecert`; explicit enroll request |
| Seller | `seller-quality1` | `seller-enroll-ca` | `client` | `supply.userId=seller.quality1:ecert,supply.role=quality:ecert`; explicit enroll request |
| Seller | `seller-client1` | `seller-enroll-ca` | `client` | no `supply.*` attributes |
| Seller | `seller-admin1` | `seller-enroll-ca` | `admin` | no `supply.*` attributes |
| Seller | `seller-peer0` | `seller-enroll-ca` | `peer` | no `supply.*` attributes |
| Seller | `seller-peer0-tls` | `seller-tls-ca` | `peer` | `peer0.seller.supply.test` |
| Buyer | `buyer-operator1` | `buyer-enroll-ca` | `client` | `supply.userId=buyer.operator1:ecert,supply.role=operator:ecert`; explicit enroll request |
| Buyer | `buyer-quality1` | `buyer-enroll-ca` | `client` | `supply.userId=buyer.quality1:ecert,supply.role=quality:ecert`; explicit enroll request |
| Buyer | `buyer-client1` | `buyer-enroll-ca` | `client` | no `supply.*` attributes |
| Buyer | `buyer-admin1` | `buyer-enroll-ca` | `admin` | no `supply.*` attributes |
| Buyer | `buyer-peer0` | `buyer-enroll-ca` | `peer` | no `supply.*` attributes |
| Buyer | `buyer-peer0-tls` | `buyer-tls-ca` | `peer` | `peer0.buyer.supply.test` |
| Carrier | `carrier-operator1` | `carrier-enroll-ca` | `client` | `supply.userId=carrier.operator1:ecert,supply.role=operator:ecert`; explicit enroll request |
| Carrier | `carrier-client1` | `carrier-enroll-ca` | `client` | no `supply.*` attributes |
| Carrier | `carrier-admin1` | `carrier-enroll-ca` | `admin` | no `supply.*` attributes |
| Carrier | `carrier-peer0` | `carrier-enroll-ca` | `peer` | no `supply.*` attributes |
| Carrier | `carrier-peer0-tls` | `carrier-tls-ca` | `peer` | `peer0.carrier.supply.test` |
| Orderer | `orderer-admin1` | `orderer-enroll-ca` | `admin` | no `supply.*` attributes |
| Orderer | `orderer0`, `orderer1`, `orderer2` | `orderer-enroll-ca` | `orderer` | distinct node ECerts; no `supply.*` attributes |
| Orderer | `orderer0-tls`, `orderer1-tls`, `orderer2-tls` | `orderer-tls-ca` | `orderer` | corresponding `ordererN.orderer.supply.test` |
| Orderer | `orderer0-admin-server-tls`, `orderer1-admin-server-tls`, `orderer2-admin-server-tls` | `orderer-tls-ca` | `orderer` | corresponding admin endpoint `ordererN.orderer.supply.test` |
| Orderer | `osnadmin-client1-tls` | **`orderer-admin-tls-ca`** | `client` | `osnadmin-client1.orderer.supply.test`; dedicated admin mTLS client |

Carrier quality is optional in SPEC §4.1 and was not issued. An auditor business certificate awaits AuditMSP in M8 #64/#66. The out-of-channel organization identity for negative authorization awaits M4 #29.

## One native pair, shown concretely

The following was the shape used for `seller-quality1`; it is a reproducible **first-run example**, not a command to repeat against an existing CA identity. Run the register command and then the enroll command separately, recording each exit code in an ignored log. A new run must create the secret only if it does not already exist, and must not overwrite an existing local MSP. For other matrix rows, use the exact CA/HTTPS DNS/root/network/registrar/identity in the operation ledger, with `--id.attrs` and `--enrollment.attrs` **only** for business operator/quality ECerts. Do not copy attributes onto client, admin, node or TLS identities.

```sh
set -eu
umask 077
install -d -m 700 .secrets/identities .runtime/identities/seller/seller-quality1
test ! -e .runtime/identities/seller/seller-quality1/msp
test ! -e .secrets/identities/seller-quality1.enroll
openssl rand -hex 32 > .secrets/identities/seller-quality1.enroll
docker run --rm --network supply-seller --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/enroll-registrar,dst=/registrar,readonly" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/trust/ca.pem,readonly" \
  --mount "type=bind,src=$PWD/.secrets/identities/seller-quality1.enroll,dst=/run/secrets/enroll,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'IFS= read -r secret < /run/secrets/enroll; exec fabric-ca-client register --home /registrar --mspdir /registrar/msp --url https://ca-enroll.seller.supply.test:7054 --tls.certfiles /trust/ca.pem --caname seller-enroll-ca --id.name seller-quality1 --id.type client --id.secret "$secret" --id.attrs "supply.userId=seller.quality1:ecert,supply.role=quality:ecert"'
docker run --rm --network supply-seller --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/seller-quality1,dst=/identity" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/trust/ca.pem,readonly" \
  --mount "type=bind,src=$PWD/.secrets/identities/seller-quality1.enroll,dst=/run/secrets/enroll,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'IFS= read -r secret < /run/secrets/enroll; exec fabric-ca-client enroll --home /identity --mspdir /identity/msp --url "https://seller-quality1:$secret@ca-enroll.seller.supply.test:7054" --tls.certfiles /trust/ca.pem --caname seller-enroll-ca --enrollment.attrs supply.userId,supply.role'
```

Before issuing each identity, prove CA HTTPS with the matching trusted root and exact host, for example `curl --cacert /trust/ca.pem https://ca-enroll.seller.supply.test:7054/cainfo` inside the organization's tools network. Never use `-k` or `--insecure`. Check the ECert issuer chain against the organization's **Enrollment** root after issuance; the HTTPS TLS root is a separate trust role. TLS-profile identities use the corresponding TLS CA root for both roles. For Orderer admin, keep the client certificate issued by the dedicated admin TLS root; all six node/admin-server TLS certificates use the ordinary Orderer TLS root.

## Post-issuance boundary

`python3 scripts/inspect-local-certs.py > evidence/m1/issue-10-certificates.csv` audits the 41 currently present local signcerts, root copies, key match, permissions and public metadata. This is an inspection after the separate native commands, not an issuance script. It reads private keys solely to compare public keys; it prints only public certificate metadata, key ownership/mode and PASS markers. The measured CSV and [issue #10 evidence](../evidence/m1/issue-10.md) are the certificate record.

New local MSP `config.yaml` files and public channel MSP assembly are M1 #11 work; only the initial Seller operator's local NodeOUs file was checked in #9. A CA ECert plus its attributes does not yet prove a live channel MSP classification or chaincode authorization. Peer-to-CCaaS mTLS client identities and handshake belong to M3; these Peer node TLS certificates are not claimed as that test. Orderer admin endpoint mTLS policy and trust restriction belong to M2.
