# M1 CA native first run

This is the manual recordable path for SPEC.md §§4.1–4.4, 19.2. Run each native command separately and keep its redacted exit status. The nine CA volumes contain the live SQLite databases, bootstrap configuration, issuer private keys, and Enrollment CA HTTPS keys. They are not in Git or the tools build context. A fresh initialization produces new roots and fingerprints; a restart of the same volumes must retain them.

## Preflight and order

```sh
make doctor
make ca-config
umask 077
install -d -m 700 .secrets/ca .runtime/trust .runtime/ca-logs .runtime/identities
```

The pinned CA image is `docker.io/hyperledger/fabric-ca:1.5.22@sha256:a70b6ba64a08b4d856802fe1fa66af9f2e03a26a63ceaff0de7c852ca7178b72`. `compose/ca.yaml` keeps every service behind the `ca` profile on an internal organization network with no published port. A service refuses to start without its initialized private volume.

Execute the following rows **one at a time**. Complete the first two Seller CAs and the Seller operator check before any other row. The rest follow TLS-before-Enrollment order. `ca-orderer-admin-tls` is dedicated to future Orderer admin mTLS client certificates; it is not a broad client trust root.

| First-run order | Service | CA name | Bootstrap registrar | HTTPS DNS | Root-trust file | Named volume |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `ca-seller-tls` | `seller-tls-ca` | `seller-tls-registrar` | `ca-tls.seller.supply.test` | `.runtime/trust/seller-tls-ca.pem` | `supplyledger_ca_seller_tls` |
| 2 | `ca-seller-enroll` | `seller-enroll-ca` | `seller-enroll-registrar` | `ca-enroll.seller.supply.test` | Seller TLS root for HTTPS; `.runtime/trust/seller-enroll-ca.pem` for ECerts | `supplyledger_ca_seller_enroll` |
| 3 | `ca-buyer-tls` | `buyer-tls-ca` | `buyer-tls-registrar` | `ca-tls.buyer.supply.test` | `.runtime/trust/buyer-tls-ca.pem` | `supplyledger_ca_buyer_tls` |
| 4 | `ca-carrier-tls` | `carrier-tls-ca` | `carrier-tls-registrar` | `ca-tls.carrier.supply.test` | `.runtime/trust/carrier-tls-ca.pem` | `supplyledger_ca_carrier_tls` |
| 5 | `ca-orderer-tls` | `orderer-tls-ca` | `orderer-tls-registrar` | `ca-tls.orderer.supply.test` | `.runtime/trust/orderer-tls-ca.pem` | `supplyledger_ca_orderer_tls` |
| 6 | `ca-orderer-admin-tls` | `orderer-admin-tls-ca` | `orderer-admin-tls-registrar` | `ca-admin-tls.orderer.supply.test` | `.runtime/trust/orderer-admin-tls-ca.pem` | `supplyledger_ca_orderer_admin_tls` |
| 7 | `ca-buyer-enroll` | `buyer-enroll-ca` | `buyer-enroll-registrar` | `ca-enroll.buyer.supply.test` | Buyer TLS root for HTTPS; `.runtime/trust/buyer-enroll-ca.pem` for ECerts | `supplyledger_ca_buyer_enroll` |
| 8 | `ca-carrier-enroll` | `carrier-enroll-ca` | `carrier-enroll-registrar` | `ca-enroll.carrier.supply.test` | Carrier TLS root for HTTPS; `.runtime/trust/carrier-enroll-ca.pem` for ECerts | `supplyledger_ca_carrier_enroll` |
| 9 | `ca-orderer-enroll` | `orderer-enroll-ca` | `orderer-enroll-registrar` | `ca-enroll.orderer.supply.test` | Orderer TLS root for HTTPS; `.runtime/trust/orderer-enroll-ca.pem` for ECerts | `supplyledger_ca_orderer_enroll` |

## First TLS CA: Seller

Create a private bootstrap password file. Keep its literal value out of recorded commands and tracked files. `install-ca-config.sh` substitutes it into the secret-bearing YAML **inside the named volume**; the checked-in template has `pass: null`. The native `fabric-ca-server init -b`, `fabric-ca-client enroll --url`, and `register --id.secret` processes still receive the secret in their short-lived container process arguments. A Docker/host administrator can inspect those arguments under the ADR-004 trust boundary; do not claim that the bind-mounted file removes that exposure.

```sh
openssl rand -hex 32 > .secrets/ca/seller-tls.bootstrap
bash scripts/install-ca-config.sh ca-seller-tls
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml --profile ca \
  run --rm --no-deps -T \
  --volume "$PWD/.secrets/ca/seller-tls.bootstrap:/run/secrets/bootstrap:ro" \
  --entrypoint sh ca-seller-tls -ceu \
  'IFS= read -r secret < /run/secrets/bootstrap; exec fabric-ca-server init -b "seller-tls-registrar:$secret"'
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml --profile ca \
  up -d --no-deps ca-seller-tls
docker cp supplyledger-ca-seller-tls-1:/etc/hyperledger/fabric-ca-server/ca-cert.pem \
  .runtime/trust/seller-tls-ca.pem
chmod 600 .runtime/trust/seller-tls-ca.pem
openssl x509 -in .runtime/trust/seller-tls-ca.pem -noout \
  -subject -issuer -serial -dates -fingerprint -sha256
openssl verify -CAfile .runtime/trust/seller-tls-ca.pem \
  .runtime/trust/seller-tls-ca.pem
docker run --rm --network supply-seller --read-only \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/trust/ca.pem,readonly" \
  --entrypoint curl supply-tools:m0-fabric3.1.5-ca1.5.22 \
  -sS --fail --cacert /trust/ca.pem --output /dev/null \
  --write-out 'HTTP=%{http_code} TLS_VERIFY=%{ssl_verify_result}\n' \
  https://ca-tls.seller.supply.test:7054/cainfo
```

The TLS CA generates its own HTTPS key/certificate at first `start` because its template omits `tls.certfile` and `tls.keyfile`. The root and HTTPS key are different keys in the same private volume. Repeat these **individual native steps**, substituting the exact service, registrar, CA, DNS, network and root path from the table, for Buyer, Carrier, Orderer and Orderer admin TLS CAs after the Seller operator check.

## First Enrollment CA: Seller

The Enrollment CA HTTPS certificate is signed by the Seller TLS CA. First enroll the TLS CA registrar to an ignored local MSP, then register and enroll the dedicated HTTPS identity. The commands below use the locked tools image on `supply-seller`; each private identity directory is bind-mounted only for that operation. Capture native command output into ignored `.runtime/ca-logs` and redact any credentials before sharing it.

```sh
install -d -m 700 .runtime/identities/seller/tls-registrar \
  .runtime/identities/seller/enroll-server-tls
openssl rand -hex 32 > .secrets/ca/seller-enroll-server-tls.enroll
openssl rand -hex 32 > .secrets/ca/seller-enroll.bootstrap
docker run --rm --network supply-seller --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/tls-registrar,dst=/identity" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/trust/ca.pem,readonly" \
  --mount "type=bind,src=$PWD/.secrets/ca/seller-tls.bootstrap,dst=/run/secrets/bootstrap,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'IFS= read -r secret < /run/secrets/bootstrap; exec fabric-ca-client enroll --home /identity --mspdir /identity/msp --url "https://seller-tls-registrar:$secret@ca-tls.seller.supply.test:7054" --tls.certfiles /trust/ca.pem --caname seller-tls-ca'
docker run --rm --network supply-seller --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/tls-registrar,dst=/registrar,readonly" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/trust/ca.pem,readonly" \
  --mount "type=bind,src=$PWD/.secrets/ca/seller-enroll-server-tls.enroll,dst=/run/secrets/enroll,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'IFS= read -r secret < /run/secrets/enroll; exec fabric-ca-client register --home /registrar --mspdir /registrar/msp --url https://ca-tls.seller.supply.test:7054 --tls.certfiles /trust/ca.pem --caname seller-tls-ca --id.name seller-enroll-server-tls --id.type client --id.maxenrollments 1 --id.secret "$secret"'
docker run --rm --network supply-seller --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/enroll-server-tls,dst=/identity" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/trust/ca.pem,readonly" \
  --mount "type=bind,src=$PWD/.secrets/ca/seller-enroll-server-tls.enroll,dst=/run/secrets/enroll,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'IFS= read -r secret < /run/secrets/enroll; exec fabric-ca-client enroll --home /identity --mspdir /identity/msp --url "https://seller-enroll-server-tls:$secret@ca-tls.seller.supply.test:7054" --tls.certfiles /trust/ca.pem --caname seller-tls-ca --enrollment.profile tls --csr.hosts ca-enroll.seller.supply.test'
openssl verify -CAfile .runtime/trust/seller-tls-ca.pem \
  .runtime/identities/seller/enroll-server-tls/msp/signcerts/cert.pem
openssl x509 -in .runtime/identities/seller/enroll-server-tls/msp/signcerts/cert.pem \
  -noout -ext subjectAltName
```

Only after the HTTPS identity has the expected SAN and chain, install the Enrollment CA config, copy its distinct HTTPS certificate/key into its own volume, then run native CA init/start:

```sh
bash scripts/install-ca-config.sh ca-seller-enroll
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml --profile ca \
  run --rm --no-deps -T \
  --volume "$PWD/.runtime/identities/seller/enroll-server-tls:/source:ro" \
  --entrypoint sh ca-seller-enroll -ceu \
  'umask 077; destination=/etc/hyperledger/fabric-ca-server/tls; test ! -e "$destination/server.crt"; mkdir -p "$destination"; set -- /source/msp/keystore/*_sk; test "$#" -eq 1; cp /source/msp/signcerts/cert.pem "$destination/server.crt"; cp "$1" "$destination/server.key"; chmod 600 "$destination/server.crt" "$destination/server.key"'
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml --profile ca \
  run --rm --no-deps -T \
  --volume "$PWD/.secrets/ca/seller-enroll.bootstrap:/run/secrets/bootstrap:ro" \
  --entrypoint sh ca-seller-enroll -ceu \
  'IFS= read -r secret < /run/secrets/bootstrap; exec fabric-ca-server init -b "seller-enroll-registrar:$secret"'
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml --profile ca \
  up -d --no-deps ca-seller-enroll
docker cp supplyledger-ca-seller-enroll-1:/etc/hyperledger/fabric-ca-server/ca-cert.pem \
  .runtime/trust/seller-enroll-ca.pem
chmod 600 .runtime/trust/seller-enroll-ca.pem
docker run --rm --network supply-seller --read-only \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/trust/ca.pem,readonly" \
  --entrypoint curl supply-tools:m0-fabric3.1.5-ca1.5.22 \
  -sS --fail --cacert /trust/ca.pem --output /dev/null \
  --write-out 'HTTP=%{http_code} TLS_VERIFY=%{ssl_verify_result}\n' \
  https://ca-enroll.seller.supply.test:7054/cainfo
```

After the Seller operator check below, repeat the same **separate native register, enroll, init and start commands** for Buyer, Carrier and Orderer. Replace `seller` with the organization name in service/identity/secret paths, DNS and network, and use that organization's TLS CA name and root file from the table. Never reuse one organization's registrar MSP or root for another organization.

## Initial Seller operator check

Before any non-Seller CA first run, enroll `seller-enroll-registrar` on Seller Enrollment CA through verified HTTPS, register `seller-operator1` as a `client` with `supply.userId=seller.operator1:ecert` and `supply.role=operator:ecert`, then enroll it with `--enrollment.attrs supply.userId,supply.role`. Store its MSP under ignored `.runtime/identities/seller/operator1/msp`:

```sh
install -d -m 700 .runtime/identities/seller/enroll-registrar \
  .runtime/identities/seller/operator1
openssl rand -hex 32 > .secrets/ca/seller-operator1.enroll
docker run --rm --network supply-seller --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/enroll-registrar,dst=/identity" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/trust/ca.pem,readonly" \
  --mount "type=bind,src=$PWD/.secrets/ca/seller-enroll.bootstrap,dst=/run/secrets/bootstrap,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'IFS= read -r secret < /run/secrets/bootstrap; exec fabric-ca-client enroll --home /identity --mspdir /identity/msp --url "https://seller-enroll-registrar:$secret@ca-enroll.seller.supply.test:7054" --tls.certfiles /trust/ca.pem --caname seller-enroll-ca'
docker run --rm --network supply-seller --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/enroll-registrar,dst=/registrar,readonly" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/trust/ca.pem,readonly" \
  --mount "type=bind,src=$PWD/.secrets/ca/seller-operator1.enroll,dst=/run/secrets/enroll,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'IFS= read -r secret < /run/secrets/enroll; exec fabric-ca-client register --home /registrar --mspdir /registrar/msp --url https://ca-enroll.seller.supply.test:7054 --tls.certfiles /trust/ca.pem --caname seller-enroll-ca --id.name seller-operator1 --id.type client --id.maxenrollments 1 --id.secret "$secret" --id.attrs "supply.userId=seller.operator1:ecert,supply.role=operator:ecert"'
docker run --rm --network supply-seller --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/operator1,dst=/identity" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/trust/ca.pem,readonly" \
  --mount "type=bind,src=$PWD/.secrets/ca/seller-operator1.enroll,dst=/run/secrets/enroll,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu \
  'IFS= read -r secret < /run/secrets/enroll; exec fabric-ca-client enroll --home /identity --mspdir /identity/msp --url "https://seller-operator1:$secret@ca-enroll.seller.supply.test:7054" --tls.certfiles /trust/ca.pem --caname seller-enroll-ca --enrollment.attrs supply.userId,supply.role'
openssl verify -CAfile .runtime/trust/seller-enroll-ca.pem \
  .runtime/identities/seller/operator1/msp/signcerts/cert.pem
openssl x509 -in .runtime/identities/seller/operator1/msp/signcerts/cert.pem \
  -text -noout | grep -A1 '1.2.3.4.5.6.7.8.1'
```

Check exactly one local `0600` signing key and matching certificate/key public keys. Add a private local `msp/config.yaml` with `NodeOUs.Enable: true` and distinct `client`, `peer`, `admin`, `orderer` OU identifiers, all referring to this MSP's Seller Enrollment root in `cacerts`. The ECert must have `OU=client`; the [measured first-run result](../evidence/m1/issue-9.md) includes its root and key hashes. Full channel MSP validation belongs to M1 issue #11 and is not implied by this file check.

## Data and shutdown checks

After first init, tighten each volume's generated SQLite DB and Idemix issuer secret/revocation keys to `0600` as root. Check the CA root private `*_sk` files are `0600` and keep the Enrollment HTTPS key in its own volume. Do not copy any private key to a channel MSP or tracked directory. Root certs are public, but their measured fingerprints must be compared with your own trusted local bootstrap record before distributing them.

```sh
docker exec supplyledger-ca-seller-tls-1 sh -ceu \
  'cd /etc/hyperledger/fabric-ca-server; chmod 600 fabric-ca-server.db msp/keystore/IssuerSecretKey msp/keystore/IssuerRevocationPrivateKey; stat -c "%n %u:%g:%a" fabric-ca-server.db msp/keystore/*_sk'
make stop
make down
make reset  # prints exact target volumes and exits 2 without CONFIRM_DESTROY=supplyledger
```

Repeat the permission check for each CA container. `make stop` and `make down` retain all nine named CA volumes. To resume initialized CAs, run `docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml --profile ca up -d --no-deps`, then compare every root fingerprint with the original record and verify each HTTPS DNS name again. Do not run confirmed reset to test persistence.
