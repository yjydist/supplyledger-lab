# M1 issue #9 — nine native Fabric CA services

- Issue: https://github.com/yjydist/supplyledger-lab/issues/9
- Checked: 2026-09-24 UTC, on `darwin/arm64` with Docker `linux/arm64`
- Test IDs: `M1-I9-01` through `M1-I9-06`; partial CA-side checks for `T-NET-02`, `T-NET-05`, and `T-ID-01`
- Specification: §§3.1, 3.4–3.5, 4.1–4.4, 18.3, 19.1–19.2, 20.1; CON-03
- Source commit: the commit introducing this report; resolve its full SHA with `git log --diff-filter=A -1 --format=%H -- evidence/m1/issue-9.md`. The unchanged M0 baseline before this work was `d27e079`.
- Version lock: `versions.lock.yaml` SHA-256 `422fba14294aaf9f0c40862fcd112ed3d2ed664cd5294c7bfe0aa14477fa234b`; CA image `docker.io/hyperledger/fabric-ca:1.5.22@sha256:a70b6ba64a08b4d856802fe1fa66af9f2e03a26a63ceaff0de7c852ca7178b72`; locally verified `fabric-ca-client v1.5.22`, `linux/arm64`; Compose `v5.5.1`.
- Compose tier: `compose/bootstrap.yaml` + `compose/ca.yaml`, profile `ca`; nine CA services only. Formal §3.5 Peer/Orderer/app network Compose: **NOT RUN**.
- Channel and genesisHash: **NOT RUN**; no channel exists. txId, block height and validation code: **NOT RUN**; no Fabric transaction was submitted.
- Prepared data: nine independent CA named volumes, nine ignored private bootstrap secret files, four ignored TLS registrar MSPs, four ignored Enrollment HTTPS identity MSPs, one Seller Enrollment registrar MSP, one Seller operator MSP, nine ignored local CA root trust copies. The Seller TLS registrar/HTTPS identity are included in the four. No API, Peer, Orderer, chaincode or backup data was created.
- Redaction: secret values, private key contents, CA YAML rendered into volumes, CA databases, and native client logs remain only in ignored `.secrets/` and `.runtime/` or Docker volumes. This report gives names and certificate metadata, not secret values. `git check-ignore` covered the private paths. Native `init -b`, client `enroll --url`, and `register --id.secret` expanded the secrets into short-lived **container process arguments**; Docker/host administrators could inspect them. This is within ADR-004's host trust boundary, not eliminated by read-only secret bind mounts.

## Native command sequence and result

The [runbook](../../docs/m1-ca-native.md) gives the full command syntax. Every first registration and enrollment below used a separate `fabric-ca-client` invocation from the locked native `supply-tools` image on the relevant internal network, with `--tls.certfiles` pointing to the measured local TLS CA root. Each password was read from a read-only bind mount at `/run/secrets/...` inside the container, then expanded into the native command's argv; no secret value is reproduced here. First-run `fabric-ca-server init -b` used the same private bind-mount pattern and argv expansion. Init/client output was captured under ignored `.runtime/ca-logs/`; service-start failure was inspected with `docker logs` and its redacted error is preserved below. Native init/client commands returned 0 unless stated otherwise.

| Order | Concrete native operation and path | Expected | Actual | Judgment |
| --- | --- | --- | --- | --- |
| 1 | `bash scripts/install-ca-config.sh ca-seller-tls`; `fabric-ca-server init -b seller-tls-registrar:<private file>`; `up -d --no-deps ca-seller-tls` | Persistent Seller TLS CA root/DB and verified HTTPS | Init exit 0. First `start` failed at the TLS server startup stage with `Error: File specified by 'tls.keyfile' does not exist: /etc/hyperledger/fabric-ca-server/tls-key.pem`. Five TLS CA templates were corrected to let Fabric CA generate its own HTTPS cert/key; the initialized Seller root/DB and volume were retained. Second `start` passed. | FAIL first start; PASS after fix |
| 2 | Seller TLS `fabric-ca-client enroll` for `seller-tls-registrar`; `register` and `enroll --enrollment.profile tls --csr.hosts ca-enroll.seller.supply.test` for `seller-enroll-server-tls` | TLS CA signs a distinct Enrollment HTTPS identity | Three native commands exit 0; certificate issuer is Seller TLS root, SAN is exact DNS, EKU includes serverAuth, and `openssl verify` passed. | PASS |
| 3 | `bash scripts/install-ca-config.sh ca-seller-enroll`; copy the issued HTTPS cert/key to its **own** named volume; `fabric-ca-server init -b seller-enroll-registrar:<private file>`; `up -d --no-deps ca-seller-enroll` | Enrollment CA starts only after its HTTPS identity is issued | Init/start exit 0; Seller Enrollment root/DB persisted and HTTPS trust passed. | PASS |
| 4 | Seller Enrollment `fabric-ca-client enroll` for `seller-enroll-registrar`; `register --id.name seller-operator1 --id.attrs 'supply.userId=seller.operator1:ecert,supply.role=operator:ecert'`; `enroll --enrollment.attrs supply.userId,supply.role` | First Seller operator ECert has trusted business attrs | Three native commands exit 0. ECert extension `1.2.3.4.5.6.7.8.1` contains exactly `supply.role=operator` and `supply.userId=seller.operator1`; root chain, key match and local NodeOUs file checks passed. | PASS for §19.2 file check; full `T-ID-01` NOT RUN |
| 5 | Individually install/init/start `ca-buyer-tls`, `ca-carrier-tls`, `ca-orderer-tls`, `ca-orderer-admin-tls` using their corresponding `<name>-registrar` private bootstrap files | Four distinct TLS roots/DBs and HTTPS endpoints | Four separate native init commands exited 0; each CA started and passed HTTPS root/hostname verification. | PASS |
| 6 | For each of Buyer, Carrier, Orderer: native TLS registrar `enroll`, dedicated `<org>-enroll-server-tls` `register`, TLS-profile `enroll --csr.hosts ca-enroll.<org>.supply.test`, copy cert/key to the matching Enrollment CA volume, native Enrollment CA `init`, then `start` | Three Enrollment HTTPS identities signed by the matching TLS CA; independent Enrollment roots/DBs | Each native command exited 0. Each HTTPS cert had the exact SAN and serverAuth EKU; all three Enrollment CAs started and passed HTTPS verification. | PASS |

The native `init` commands used `docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml --profile ca run --rm --no-deps -T --volume "$PWD/.secrets/ca/<name>.bootstrap:/run/secrets/bootstrap:ro" --entrypoint sh ca-<name> -ceu 'IFS= read -r secret < /run/secrets/bootstrap; exec fabric-ca-server init -b "<name>-registrar:$secret"'`, with `<name>` replaced by each actual service suffix. In chronological order, the nine concrete suffixes were `seller-tls`, `seller-enroll`, `buyer-tls`, `carrier-tls`, `orderer-tls`, `orderer-admin-tls`, `buyer-enroll`, `carrier-enroll`, `orderer-enroll`. Each `up -d --no-deps ca-<name>` was issued separately on its first run. The actual registrar names and the one-to-one volume mapping are in the runbook table. There was no first-run loop or one-click network bootstrap.

The three Enrollment HTTPS identity operations for each organization used these actual names and arguments:

| TLS CA | Registrar MSP enrolled from | HTTPS identity registered and TLS-enrolled with `--csr.hosts` | TLS-trust path used for `--tls.certfiles` |
| --- | --- | --- | --- |
| `seller-tls-ca` | `.runtime/identities/seller/tls-registrar/msp` | `seller-enroll-server-tls`; `ca-enroll.seller.supply.test` | `.runtime/trust/seller-tls-ca.pem` |
| `buyer-tls-ca` | `.runtime/identities/buyer/tls-registrar/msp` | `buyer-enroll-server-tls`; `ca-enroll.buyer.supply.test` | `.runtime/trust/buyer-tls-ca.pem` |
| `carrier-tls-ca` | `.runtime/identities/carrier/tls-registrar/msp` | `carrier-enroll-server-tls`; `ca-enroll.carrier.supply.test` | `.runtime/trust/carrier-tls-ca.pem` |
| `orderer-tls-ca` | `.runtime/identities/orderer/tls-registrar/msp` | `orderer-enroll-server-tls`; `ca-enroll.orderer.supply.test` | `.runtime/trust/orderer-tls-ca.pem` |

The temporary runtime correction for the already initialized Seller TLS CA removed only the two nonexistent `tls.certfile`/`tls.keyfile` entries from its private volume config. It did not recreate the volume, root or DB. Before this fix, the first-start failure had no Fabric transaction, txId or block.

### Concrete native operation ledger

The following rows expand the actual service and identity arguments behind the overview above. For server `init`, the exact native argument was `-b <listed registrar>:<redacted file contents>`; the container wrapper mounted `.secrets/ca/<service suffix>.bootstrap` read-only and wrote the indicated ignored init log. For `start`, the exact Compose operation was `docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml --profile ca up -d --no-deps <listed service>`. A Compose exit 0 was counted as a service PASS only after the subsequent container/HTTPS check.

| Native operation | Exact service and registrar argument | Ignored log / direct result | Judgment |
| --- | --- | --- | --- |
| `fabric-ca-server init -b` | `ca-seller-tls`, `seller-tls-registrar:<redacted>` | `seller-tls-init.log`, exit 0 | PASS |
| `up -d --no-deps` first attempt | `ca-seller-tls` | Compose exit 0, container exit 1; `tls.keyfile` absent at TLS startup | FAIL |
| `up -d --no-deps` after in-place config fix | `ca-seller-tls` | running; HTTPS 200, verify 0 | PASS |
| `fabric-ca-server init -b` | `ca-seller-enroll`, `seller-enroll-registrar:<redacted>` | `seller-enroll-init.log`, exit 0 | PASS |
| `up -d --no-deps` | `ca-seller-enroll` | running; HTTPS 200, verify 0 | PASS |
| `fabric-ca-server init -b` | `ca-buyer-tls`, `buyer-tls-registrar:<redacted>` | `buyer-tls-init.log`, exit 0 | PASS |
| `up -d --no-deps` | `ca-buyer-tls` | running; HTTPS 200, verify 0 | PASS |
| `fabric-ca-server init -b` | `ca-carrier-tls`, `carrier-tls-registrar:<redacted>` | `carrier-tls-init.log`, exit 0 | PASS |
| `up -d --no-deps` | `ca-carrier-tls` | running; HTTPS 200, verify 0 | PASS |
| `fabric-ca-server init -b` | `ca-orderer-tls`, `orderer-tls-registrar:<redacted>` | `orderer-tls-init.log`, exit 0 | PASS |
| `up -d --no-deps` | `ca-orderer-tls` | running; HTTPS 200, verify 0 | PASS |
| `fabric-ca-server init -b` | `ca-orderer-admin-tls`, `orderer-admin-tls-registrar:<redacted>` | `orderer-admin-tls-init.log`, exit 0 | PASS |
| `up -d --no-deps` | `ca-orderer-admin-tls` | running; HTTPS 200, verify 0 | PASS |
| `fabric-ca-server init -b` | `ca-buyer-enroll`, `buyer-enroll-registrar:<redacted>` | `buyer-enroll-init.log`, exit 0 | PASS |
| `up -d --no-deps` | `ca-buyer-enroll` | running; HTTPS 200, verify 0 | PASS |
| `fabric-ca-server init -b` | `ca-carrier-enroll`, `carrier-enroll-registrar:<redacted>` | `carrier-enroll-init.log`, exit 0 | PASS |
| `up -d --no-deps` | `ca-carrier-enroll` | running; HTTPS 200, verify 0 | PASS |
| `fabric-ca-server init -b` | `ca-orderer-enroll`, `orderer-enroll-registrar:<redacted>` | `orderer-enroll-init.log`, exit 0 | PASS |
| `up -d --no-deps` | `ca-orderer-enroll` | running; HTTPS 200, verify 0 | PASS |

Every client operation below used the exact listed `--caname`, HTTPS `--url` host, and `--tls.certfiles` root. The URL user was the listed identity and its password came from the private file; `<redacted>` replaces the value that was transiently present in argv. Every client command had its own ignored log under `.runtime/ca-logs/`; the listed exit 0 was observed at execution. Full Docker wrappers, read-only mounts and UID choices are in the runbook.

| Native client command and concrete arguments | TLS trust root | Ignored log / result |
| --- | --- | --- |
| `enroll --caname seller-tls-ca --url https://seller-tls-registrar:<redacted>@ca-tls.seller.supply.test:7054 --mspdir /identity/msp` | `seller-tls-ca.pem` | `seller-tls-registrar-enroll.log`, exit 0 |
| `register --caname seller-tls-ca --url https://ca-tls.seller.supply.test:7054 --id.name seller-enroll-server-tls --id.type client --id.maxenrollments 1 --id.secret <redacted>` | `seller-tls-ca.pem` | `seller-enroll-server-tls-register.log`, exit 0 |
| `enroll --caname seller-tls-ca --url https://seller-enroll-server-tls:<redacted>@ca-tls.seller.supply.test:7054 --enrollment.profile tls --csr.hosts ca-enroll.seller.supply.test` | `seller-tls-ca.pem` | `seller-enroll-server-tls-enroll.log`, exit 0; SAN/issuer verified |
| `enroll --caname seller-enroll-ca --url https://seller-enroll-registrar:<redacted>@ca-enroll.seller.supply.test:7054 --mspdir /identity/msp` | `seller-tls-ca.pem` | `seller-enroll-registrar-enroll.log`, exit 0 |
| `register --caname seller-enroll-ca --url https://ca-enroll.seller.supply.test:7054 --id.name seller-operator1 --id.type client --id.maxenrollments 1 --id.secret <redacted> --id.attrs supply.userId=seller.operator1:ecert,supply.role=operator:ecert` | `seller-tls-ca.pem` | `seller-operator1-register.log`, exit 0 |
| `enroll --caname seller-enroll-ca --url https://seller-operator1:<redacted>@ca-enroll.seller.supply.test:7054 --enrollment.attrs supply.userId,supply.role` | `seller-tls-ca.pem` | `seller-operator1-enroll.log`, exit 0; ECert attributes verified |
| `enroll --caname buyer-tls-ca --url https://buyer-tls-registrar:<redacted>@ca-tls.buyer.supply.test:7054 --mspdir /identity/msp` | `buyer-tls-ca.pem` | `buyer-tls-registrar-enroll.log`, exit 0 |
| `register --caname buyer-tls-ca --url https://ca-tls.buyer.supply.test:7054 --id.name buyer-enroll-server-tls --id.type client --id.maxenrollments 1 --id.secret <redacted>` | `buyer-tls-ca.pem` | `buyer-enroll-server-tls-register.log`, exit 0 |
| `enroll --caname buyer-tls-ca --url https://buyer-enroll-server-tls:<redacted>@ca-tls.buyer.supply.test:7054 --enrollment.profile tls --csr.hosts ca-enroll.buyer.supply.test` | `buyer-tls-ca.pem` | `buyer-enroll-server-tls-enroll.log`, exit 0; SAN/issuer verified |
| `enroll --caname carrier-tls-ca --url https://carrier-tls-registrar:<redacted>@ca-tls.carrier.supply.test:7054 --mspdir /identity/msp` | `carrier-tls-ca.pem` | `carrier-tls-registrar-enroll.log`, exit 0 |
| `register --caname carrier-tls-ca --url https://ca-tls.carrier.supply.test:7054 --id.name carrier-enroll-server-tls --id.type client --id.maxenrollments 1 --id.secret <redacted>` | `carrier-tls-ca.pem` | `carrier-enroll-server-tls-register.log`, exit 0 |
| `enroll --caname carrier-tls-ca --url https://carrier-enroll-server-tls:<redacted>@ca-tls.carrier.supply.test:7054 --enrollment.profile tls --csr.hosts ca-enroll.carrier.supply.test` | `carrier-tls-ca.pem` | `carrier-enroll-server-tls-enroll.log`, exit 0; SAN/issuer verified |
| `enroll --caname orderer-tls-ca --url https://orderer-tls-registrar:<redacted>@ca-tls.orderer.supply.test:7054 --mspdir /identity/msp` | `orderer-tls-ca.pem` | `orderer-tls-registrar-enroll.log`, exit 0 |
| `register --caname orderer-tls-ca --url https://ca-tls.orderer.supply.test:7054 --id.name orderer-enroll-server-tls --id.type client --id.maxenrollments 1 --id.secret <redacted>` | `orderer-tls-ca.pem` | `orderer-enroll-server-tls-register.log`, exit 0 |
| `enroll --caname orderer-tls-ca --url https://orderer-enroll-server-tls:<redacted>@ca-tls.orderer.supply.test:7054 --enrollment.profile tls --csr.hosts ca-enroll.orderer.supply.test` | `orderer-tls-ca.pem` | `orderer-enroll-server-tls-enroll.log`, exit 0; SAN/issuer verified |

## Measured CA roots

Each root was copied from the corresponding running CA volume's `ca-cert.pem` into ignored `.runtime/trust/<name>-ca.pem`. `openssl x509 -noout -subject -issuer -serial -dates -fingerprint -sha256` and `openssl x509 -text -noout` produced the following values. Every subject begins `C=CN, O=SupplyLedger Lab`; the table gives the remaining OU and CN. Every root's issuer equals its subject, `openssl verify -CAfile <root> <root>` returned `OK`, and the Authority Key Identifier extension was **absent** (not guessed from SKI). All times are UTC.

| CA root | Subject OU / CN (issuer identical) | Serial | Validity: 2026-09-24 → 2041-09-20 | SKI | SHA-256 fingerprint |
| --- | --- | --- | --- | --- | --- |
| Seller TLS | `seller tls CA` / `seller-tls-ca` | `2F38314C873ACA326F08F5A7B857761211FDD12B` | `12:10 → 12:10` | `79:D0:A6:6A:4C:73:1C:EF:1E:59:6E:83:4F:40:35:34:FA:29:51:A5` | `24:55:D7:35:B3:B8:A6:F5:76:AB:73:38:B6:58:05:74:AD:C5:50:6E:25:95:08:D0:8A:18:EC:B6:BD:5C:DF:77` |
| Seller Enrollment | `seller enroll CA` / `seller-enroll-ca` | `7A565FA297E229C1BDFF93465DF4B512D3E09F91` | `12:17 → 12:17` | `60:69:C9:EF:A8:5C:4F:FD:84:66:AC:BE:F0:90:4F:2A:24:04:EC:B1` | `0A:A6:8D:8B:A6:4B:99:9B:E7:ED:EC:6F:D9:C9:AF:B2:E7:B9:C7:50:B6:CD:7A:CA:76:93:48:6F:E6:D1:22:E4` |
| Buyer TLS | `buyer tls CA` / `buyer-tls-ca` | `7E93FF7BBA253583356D8BFDF2EBADA37443E5A7` | `12:19 → 12:19` | `C8:CB:03:79:C6:9D:13:79:FB:E8:4A:26:C3:5E:7A:37:E9:73:C5:44` | `5E:C8:AD:97:97:6E:49:65:06:DD:69:45:9A:63:D1:05:42:9C:36:A0:19:AA:DE:50:DE:32:3F:A3:C2:40:C3:54` |
| Buyer Enrollment | `buyer enroll CA` / `buyer-enroll-ca` | `643131D7518224F3E955845AC39D57273DFBCC02` | `12:28 → 12:28` | `96:C5:DE:3E:4F:D8:A0:80:86:B1:FB:FB:18:55:03:0B:D3:BF:CF:D4` | `8B:57:A9:8D:F8:BB:8A:09:AE:88:CA:8C:56:EE:DB:96:DF:E0:65:FC:E8:BD:68:D9:C0:B8:B8:BF:3A:E5:12:52` |
| Carrier TLS | `carrier tls CA` / `carrier-tls-ca` | `79E1AC19F7AF9051450AC9D73701C64CF16753A5` | `12:20 → 12:20` | `3C:FA:C4:E2:F3:28:96:B2:DF:A2:8D:FF:15:FD:3D:A5:63:14:90:57` | `3D:3F:FC:65:8F:1C:B6:3F:D1:81:E4:4F:77:23:EC:2E:6C:2E:C6:A1:07:B3:34:50:6B:D4:CC:B5:9E:4C:F9:6A` |
| Carrier Enrollment | `carrier enroll CA` / `carrier-enroll-ca` | `045EB34517901AC7736AB0B82FE39DB0DF371250` | `12:29 → 12:29` | `DC:41:1E:94:51:B1:13:6E:7F:48:C0:A2:4C:3D:E3:6A:DF:B9:33:8C` | `98:F5:9C:F2:AD:E1:C0:96:08:1E:34:6D:48:B5:69:17:0B:8B:01:18:A7:99:D0:D5:58:C4:C1:AE:14:20:35:A9` |
| Orderer TLS | `orderer tls CA` / `orderer-tls-ca` | `6C5CDDA477AEF476E39058285DDC8763BBC0862F` | `12:20 → 12:20` | `8C:71:0C:43:20:23:B8:C9:82:B7:46:4D:2D:B6:02:6D:1B:D7:5F:7D` | `25:D0:A6:EF:0B:CF:77:F1:E7:FF:85:85:70:8D:88:3F:79:CC:CA:81:FE:86:6A:AB:D9:13:E8:49:B7:D0:36:D4` |
| Orderer Enrollment | `orderer enroll CA` / `orderer-enroll-ca` | `292E16EC44197501E4A207B14426F6578E8463ED` | `12:30 → 12:30` | `4F:9C:63:1E:C5:D6:3C:F6:1B:DE:40:FB:DD:41:F3:49:AC:12:0E:54` | `92:AF:32:37:B4:E9:81:A0:89:69:13:A6:C7:57:BB:E3:C9:C6:CC:28:6A:CF:1B:25:52:BD:A0:C0:6D:23:DF:A4` |
| Orderer admin TLS | `orderer admin-tls CA` / `orderer-admin-tls-ca` | `68C0C1CC9EFF8B306EB36530A696BD40E661B961` | `12:27 → 12:27` | `E4:41:2A:9B:CC:53:85:8A:44:E4:02:92:A6:D3:9D:2B:3A:CE:8B:36` | `71:CE:E5:B9:8D:F4:A0:13:49:22:38:4D:C9:12:C5:C8:E6:F4:CC:F7:83:B5:DC:05:FB:80:E6:FF:76:DF:6B:72` |

For **each** of these nine root certificates, the measured SAN and Extended Key Usage extensions were absent, Key Usage was `Certificate Sign, CRL Sign`, and Basic Constraints were `CA:TRUE, pathlen:0`. The public `ca-cert.pem` in its own Docker volume was owned by `0:0` with mode `0644`; the ignored local trust copy was owned by host UID:GID `501:20` with mode `0600`. The corresponding root signing private key stayed in that CA's `msp/keystore` at `0:0:0600`.

## Measured HTTPS leaf certificates

The service certificates below were read from each CA volume without exporting private keys. `TLS-generated` subjects have `C=CN, O=SupplyLedger Lab, OU=<issuing TLS root's OU>` plus the listed CN. `TLS-enrolled` subjects have `C=US, ST=North Carolina, O=Hyperledger, OU=client` plus the listed CN. In every row, the issuer is the **full subject of the named TLS root in the root inventory above**, and the measured leaf AKI `keyid` exactly equals that root's listed SKI. These relationships were checked from the X.509 extensions, not inferred from filenames. Times are UTC.

| HTTPS service cert | Subject kind / CN; issuer root | Serial | SKI; AKI = issuer-root SKI | Validity | DNS SAN |
| --- | --- | --- | --- | --- | --- |
| Seller TLS | TLS-generated / `b0a430cc3d10`; Seller TLS | `3E051D21903E7361A92F763E0B66C7E9F50395BA` | `9E:25:8C:3D:81:B9:91:9E:1B:53:BF:6C:78:55:4B:57:FC:B8:1B:72`; Seller TLS SKI | 2026-09-24 12:12 → 2027-09-24 12:12 | `ca-tls.seller.supply.test` |
| Seller Enrollment | TLS-enrolled / `seller-enroll-server-tls`; Seller TLS | `1DEA91D7CF55CDA6C78BD154F430138C8AF9DBC3` | `B6:44:73:02:15:6D:69:55:60:4F:55:9E:DF:A6:C5:46:97:1F:6A:79`; Seller TLS SKI | 2026-09-24 12:10 → 2027-09-24 12:21 | `ca-enroll.seller.supply.test` |
| Buyer TLS | TLS-generated / `8f089d83356e`; Buyer TLS | `455E2AA36FB28B666E4F49962761770511C35CCA` | `24:E4:45:04:B3:B7:50:EF:56:6A:80:05:43:AF:9C:F3:F5:27:DC:6D`; Buyer TLS SKI | 2026-09-24 12:20 → 2027-09-24 12:20 | `ca-tls.buyer.supply.test` |
| Buyer Enrollment | TLS-enrolled / `buyer-enroll-server-tls`; Buyer TLS | `1AA94EF8B4A0C1B289FEEFF31200A039C408649E` | `EE:63:D8:AA:1D:84:27:7C:59:43:63:15:07:BA:F7:5A:AE:00:82:E2`; Buyer TLS SKI | 2026-09-24 12:19 → 2027-09-24 12:32 | `ca-enroll.buyer.supply.test` |
| Carrier TLS | TLS-generated / `21846aa1e025`; Carrier TLS | `67942B37B0EC62F63D370A6DAB866E7F96AA5921` | `80:1F:82:B9:3D:A6:BC:45:06:99:FC:60:4E:14:8E:AF:47:4C:DE:18`; Carrier TLS SKI | 2026-09-24 12:20 → 2027-09-24 12:20 | `ca-tls.carrier.supply.test` |
| Carrier Enrollment | TLS-enrolled / `carrier-enroll-server-tls`; Carrier TLS | `1CBDD8E5F544A3EEBAA59218BD119B3744CD3579` | `4E:FD:A5:AB:77:25:3C:4E:45:96:AA:CF:AA:26:98:A3:AD:3A:0F:01`; Carrier TLS SKI | 2026-09-24 12:20 → 2027-09-24 12:34 | `ca-enroll.carrier.supply.test` |
| Orderer TLS | TLS-generated / `dedfdbf07e04`; Orderer TLS | `1608F89AAEC7BFD14B2F9632CF8BFE0F6B815B3B` | `0F:45:E6:C5:35:30:EE:C4:80:1C:7E:2E:ED:5B:5B:7E:F7:27:79:D1`; Orderer TLS SKI | 2026-09-24 12:26 → 2027-09-24 12:26 | `ca-tls.orderer.supply.test` |
| Orderer Enrollment | TLS-enrolled / `orderer-enroll-server-tls`; Orderer TLS | `0249840653F40985F8BEBD9CADE56D4945653EF3` | `C0:5C:F5:49:AB:8C:84:BA:A0:FD:E1:B4:3C:AC:66:AC:E3:DD:A2:5A`; Orderer TLS SKI | 2026-09-24 12:20 → 2027-09-24 12:35 | `ca-enroll.orderer.supply.test` |
| Orderer admin TLS | TLS-generated / `05e81a03a126`; Orderer admin TLS | `45A448ED284756B6035FA6506181915DA241F147` | `40:14:D2:1B:13:B3:98:ED:90:F2:66:47:34:B4:A0:DB:7B:10:A7:98`; Orderer admin TLS SKI | 2026-09-24 12:27 → 2027-09-24 12:27 | `ca-admin-tls.orderer.supply.test` |

Every HTTPS leaf had Key Usage `Digital Signature, Key Encipherment, Key Agreement`, Extended Key Usage `TLS Web Server Authentication, TLS Web Client Authentication`, and Basic Constraints `CA:FALSE`. The public certificates in the five TLS CA volumes are `tls-cert.pem`, owner `0:0`, mode `0644`; their HTTPS private keys remain under that volume's `msp/keystore`, mode `0600`. The four Enrollment CA public certificates are `tls/server.crt`, owner `0:0`, mode `0600`, and each paired `tls/server.key` is `0:0:0600` in the same volume. The ignored local public copies `.runtime/trust/<name>-server.pem` were host-owned `501:20:0600`. HTTPS certificate ownership was measured with `docker exec ... stat -c '%n %u:%g:%a'`.

## HTTPS and local identity checks

`openssl verify -CAfile <corresponding TLS root> <HTTPS server cert>` returned `OK` for all nine services. The five TLS CA HTTPS certs were generated by their own CA roots at `start`; the four Enrollment CA HTTPS certs were explicitly signed by their organization's TLS CA before that Enrollment CA started. `openssl x509 -text` found both `TLS Web Server Authentication` and `TLS Web Client Authentication` EKUs in every HTTPS cert. Every service had exactly the following DNS SAN, and a `curl --cacert <corresponding TLS root> https://<DNS>:7054/cainfo` from the matching internal network returned HTTP 200, `ssl_verify_result=0`, before and after `make down`/restart:

| Service | HTTPS DNS SAN / verified URL host | Trust root |
| --- | --- | --- |
| `ca-seller-tls` | `ca-tls.seller.supply.test` | Seller TLS |
| `ca-seller-enroll` | `ca-enroll.seller.supply.test` | Seller TLS |
| `ca-buyer-tls` | `ca-tls.buyer.supply.test` | Buyer TLS |
| `ca-buyer-enroll` | `ca-enroll.buyer.supply.test` | Buyer TLS |
| `ca-carrier-tls` | `ca-tls.carrier.supply.test` | Carrier TLS |
| `ca-carrier-enroll` | `ca-enroll.carrier.supply.test` | Carrier TLS |
| `ca-orderer-tls` | `ca-tls.orderer.supply.test` | Orderer TLS |
| `ca-orderer-enroll` | `ca-enroll.orderer.supply.test` | Orderer TLS |
| `ca-orderer-admin-tls` | `ca-admin-tls.orderer.supply.test` | Orderer admin TLS |

Seller TLS CA negative host check used `curl --cacert <Seller TLS root> --connect-to wrong.seller.supply.test:7054:ca-tls.seller.supply.test:7054 https://wrong.seller.supply.test:7054/cainfo`: exit **60**, as expected for a trusted chain with the wrong requested hostname. No `--insecure` or `-k` was used. This is a CA-side analogue of `T-NET-05`; the full node TLS case remains **NOT RUN**.

The preliminary Seller operator ECert has subject `CN=seller-operator1, OU=client`, issuer `seller-enroll-ca`, and its chain verifies with the measured Seller Enrollment root. The cert extension contains `{"attrs":{"supply.role":"operator","supply.userId":"seller.operator1"}}`. Its local MSP `cacerts` copy has the same SHA-256 bytes as the measured Seller Enrollment root (`75e082d8bf3f532e779348cc47a84805fe04cac9724122244afba22d26cfa45b`). Exactly one local signing key exists in `msp/keystore`, mode `0600`, owner UID:GID `501:20`; its public-key SHA-256 matches the ECert's public-key SHA-256 (`7d7f66976b7358b63fda7316c879f70d8795ae7eec713813c14808fb1ee5ae75`). That private file is ignored by Git and is not copied to a public MSP. The private local `msp/config.yaml` enables NodeOUs and maps client/peer/admin/orderer OUs to the same Enrollment root; it parsed and all referenced root files exist. The observed `OU=client` matches the client mapping. Fabric MSP classification in an actual Peer/channel is **NOT RUN** until issue #11.

The full observed operator ECert subject was `C=US, ST=North Carolina, O=Hyperledger, OU=client, CN=seller-operator1`; its issuer was `C=CN, O=SupplyLedger Lab, OU=seller enroll CA, CN=seller-enroll-ca`. Serial `4FBE84265FCF88A6776A0683018BFF50ECECEFD3`; SKI `40:80:F5:92:14:8F:50:DE:C3:3E:D5:93:C2:18:FB:63:EB:E2:90:55`; AKI `keyid:60:69:C9:EF:A8:5C:4F:FD:84:66:AC:BE:F0:90:4F:2A:24:04:EC:B1`, matching Seller Enrollment root SKI. Validity: `2026-09-24 12:17:00` to `2027-09-24 12:23:00` UTC. SAN `DNS:e5f658b80aa8` is the observed local client CSR host and is not used as a service DNS name. Key Usage was `Digital Signature`; Extended Key Usage was absent. SHA-256 certificate fingerprint: `00:C9:C2:30:2B:42:E3:36:68:97:74:A0:A0:89:DB:C0:83:CE:3D:56:53:5E:56:BD:CB:30:D0:5B:44:58:56:50`. Its local public signcert and CA cert were `501:20:0644`; private local `config.yaml` was `501:20:0600`.

## Persistence, volume ownership and guarded reset

`docker ps` showed nine running CA containers and only internal `7054/tcp` container ports, with no host port bindings. Each CA used a distinct `supplyledger_ca_*` named volume labeled for the `supplyledger` project. In every volume, `ca-cert.pem`, `fabric-ca-server.db`, rendered `fabric-ca-server-config.yaml` and CA private `msp/keystore/*_sk` existed. The five TLS CA volumes had two `*_sk` files (CA root and generated HTTPS key); the four Enrollment CA volumes had one root `*_sk` plus their explicitly issued `tls/server.key`. The generated SQLite DB and Idemix `IssuerSecretKey`/`IssuerRevocationPrivateKey` were manually tightened from generated `0644` to root-owned `0600`. Root `*_sk` files and rendered configs were root-owned `0600`; Enrollment HTTPS keys were `0600` in their own volume. This checks file ownership inside Docker volumes; Docker host administrators remain within the trust boundary.

`docker image inspect` returned CA descriptor `sha256:a70b6ba64a08b4d856802fe1fa66af9f2e03a26a63ceaff0de7c852ca7178b72` and `linux/arm64`; `docker inspect` of the running CA confirmed its configured image reference included the same immutable digest.

```sh
make ca-config                         # PASS; CA overlay parsed, formal network NOT RUN
make reset                             # exit 2; listed exactly nine CA volumes, deleted none
make stop                              # exit 0; nine volumes remained
make down                              # exit 0; nine volumes remained
docker compose -p supplyledger -f compose/bootstrap.yaml -f compose/ca.yaml \
  --profile ca up -d --no-deps         # exit 0; nine initialized CAs restarted
docker cp <each-ca-container>:/etc/hyperledger/fabric-ca-server/ca-cert.pem \
  <ignored-after-restart-copy>         # `cmp -s` against each prior root: nine PASS
```

The post-restart nine HTTPS probes all returned HTTP 200 and TLS verify result 0. `make reset` listed exactly `supplyledger_ca_buyer_enroll`, `supplyledger_ca_buyer_tls`, `supplyledger_ca_carrier_enroll`, `supplyledger_ca_carrier_tls`, `supplyledger_ca_orderer_admin_tls`, `supplyledger_ca_orderer_enroll`, `supplyledger_ca_orderer_tls`, `supplyledger_ca_seller_enroll`, `supplyledger_ca_seller_tls`, then refused because `CONFIRM_DESTROY=supplyledger` was absent. A confirmed reset was **NOT RUN**; no CA data or backups were deleted. The empty-volume preflight in `compose/ca.yaml` requires config, DB and root before `start`, so a fresh `up` cannot silently perform first init.

Final local checks: `bash -n scripts/install-ca-config.sh scripts/reset.sh` PASS; Ruby YAML parsing of all nine templates and their one `pass: null` placeholder PASS; `make ca-config` PASS; Compose JSON inspection found nine digest-pinned, read-only CA services, nine distinct volumes, only internal networks, and no published host ports. `make doctor` PASS for its M0 scope; `make verify-m0` exit 0 and PASS for the locked M0 toolchain/modules while still reporting formal network tests NOT RUN. `git diff --check` PASS. A scan of 52 tracked/candidate files found none of the 14 private secret values or PEM private-key markers; `.secrets/` and `.runtime/` paths were ignored. All 18 public CA-root/HTTPS serial numbers in this report were compared with their local PEMs.

| Test ID | Expected | Observed | Judgment |
| --- | --- | --- | --- |
| `M1-I9-01` separate CA initialization | 9 unique CA roots/DBs and named volumes | 9 native init exits 0; 9 roots/DBs, distinct volumes | PASS |
| `M1-I9-02` TLS-before-Enrollment issuance | Enrollment HTTPS cert signed by own TLS CA before start | 4 distinct TLS-profile HTTPS identities signed and verified; 4 Enrollment CAs then started | PASS |
| `M1-I9-03` HTTPS root/hostname | Correct root and DNS for each CA | 9 × HTTP 200/verify 0; Seller wrong-host exit 60 | PASS |
| `M1-I9-04` §19.2 initial operator | Trusted ECert attrs, private key, root, NodeOUs file check | Seller operator local checks above passed | PASS |
| `M1-I9-05` retention and reset guard | stop/down preserve CA data; unconfirmed reset deletes none | 9 roots byte-identical after down/restart; reset listed 9 and exited 2 | PASS |
| `M1-I9-06` secret and port boundary | No secret tracked, no host CA port | Runtime paths ignored; config/DB/keys in private volumes; no published host port | PASS for CA scope |
| `T-ID-01` complete identity check | Operator/quality/auditor MSP and app identity path | Only first Seller operator local file check exists; no Peer/channel/application | NOT RUN |
| `T-NET-02` complete topology | Peer/CA/DB sockets, ports, keys, independent node volumes | CA portion checked; Peer/DB topology does not exist | NOT RUN |
| `T-NET-05` node hostname failure | Wrong-host node TLS connection fails | Only Seller CA analogue run; no Peer/Orderer endpoint exists | NOT RUN |

No test above proves channel MSP authorization, Orderer admin mTLS, node certificate use, business identity enforcement, or a full §3.5 network. Those belong to later M1/M2 issues. The first-start TLS configuration failure was fixed in place and is retained as a failed intermediate result, not misreported as an uninterrupted pass.
