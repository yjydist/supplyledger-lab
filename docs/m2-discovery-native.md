# M2 NET-07: native cross-organization Peer discovery

This runbook belongs to [#18](https://github.com/yjydist/supplyledger-lab/issues/18) and SPEC.md §5.4 NET-07. It is prepared after the three founding Peers joined supplychannel at local height 1. Live Discovery, cross-organization gossip visibility, and receipt of a new ordered block are **NOT RUN** in this document.

## Prerequisites and trust boundary

1. Use the self-built supply-tools image only after its new local index and platform digests in versions.lock.yaml have been checked by make doctor and make verify-m0. The image installs the already locked Fabric v3.1.5 discover binary from the checked official archive. Its binary SHA-256 is 897c43005914f6824387b36fea35d318a40a87bbcd212522f1d855f58b8df5d9.
2. Before live Discovery, use the native read-only current-config retrieval coordinated with [#17](https://github.com/yjydist/supplyledger-lab/issues/17) to confirm that each Application org has exactly its own anchor peer0.<org>.supply.test:7051. This narrow anchor precheck does not claim the full later NET-08 audit. The original block-0 anchors and tracked externalEndpoint values are only inputs, not proof of current governance or live gossip.
3. Verify the three Peers are running and still have peer.gossip.externalEndpoint set to their own DNS:7051, a TLS listener that requires a client certificate, and exact trusted public TLS CA roots. The existing three-Peer height-1 comparison is separate evidence; do not use it as a Discovery result.
4. Run each query from a short-lived tool attached to **only its own organization network**. The transport identity is that organization's existing peer0-tls clientAuth certificate/key and own Peer TLS root. The signed Discovery request uses its separate admin ECert and MSP ID. Do not mount another organization's private MSP, the dedicated Orderer admin-API credential, a Docker socket, or a long-lived application identity.

The [pinned Fabric v3.1.5 Discovery CLI guide](https://github.com/hyperledger/fabric/blob/v3.1.5/docs/source/discovery-cli.md) requires a Peer TLS CA for server verification, a TLS client pair when the Peer enforces client authentication, and a separate ECert key/certificate plus MSP ID to sign the channel-scoped request. The checked native discover help confirms the exact flags below. No skip-verification option is used.

## Three separate native queries

Run from the repository checkout holding the ignored M1 identities and runtime node configuration. Set umask 077; make a new ignored .runtime/m2-issue18-discovery directory with mode 0700. Save each literal command, UTC start/end, stdout/stderr, and process exit separately with mode 0600. The raw Discovery response includes Peer Identity certificates; retain it only under ignored runtime storage and publish only a sanitized table of MSPID, Endpoint, LedgerHeight and checked certificate fingerprints. An exit code of zero alone is insufficient: inspect the response and verify all expected members.

Seller, using only supply-seller and Seller private material:

~~~sh
docker run --rm --pull=never --platform linux/arm64 --network supply-seller \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/seller-admin1/msp,dst=/run/supply/msp,readonly" \
  --mount "type=bind,src=$PWD/.runtime/identities/seller/seller-peer0-tls/msp,dst=/run/supply/tls,readonly" \
  --mount "type=bind,src=$PWD/.runtime/trust/seller-tls-ca.pem,dst=/run/supply/peer-tls-root.pem,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu '
    set -- /run/supply/msp/keystore/*_sk
    test "$#" -eq 1 && test -f "$1"
    user_key=$1
    set -- /run/supply/tls/keystore/*_sk
    test "$#" -eq 1 && test -f "$1"
    exec discover --peerTLSCA /run/supply/peer-tls-root.pem \
      --tlsCert /run/supply/tls/signcerts/cert.pem --tlsKey "$1" \
      --userKey "$user_key" --userCert /run/supply/msp/signcerts/cert.pem \
      --MSP SellerMSP peers --channel supplychannel \
      --server peer0.seller.supply.test:7051
  '
~~~

Buyer, using only supply-buyer and Buyer private material:

~~~sh
docker run --rm --pull=never --platform linux/arm64 --network supply-buyer \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/identities/buyer/buyer-admin1/msp,dst=/run/supply/msp,readonly" \
  --mount "type=bind,src=$PWD/.runtime/identities/buyer/buyer-peer0-tls/msp,dst=/run/supply/tls,readonly" \
  --mount "type=bind,src=$PWD/.runtime/trust/buyer-tls-ca.pem,dst=/run/supply/peer-tls-root.pem,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu '
    set -- /run/supply/msp/keystore/*_sk
    test "$#" -eq 1 && test -f "$1"
    user_key=$1
    set -- /run/supply/tls/keystore/*_sk
    test "$#" -eq 1 && test -f "$1"
    exec discover --peerTLSCA /run/supply/peer-tls-root.pem \
      --tlsCert /run/supply/tls/signcerts/cert.pem --tlsKey "$1" \
      --userKey "$user_key" --userCert /run/supply/msp/signcerts/cert.pem \
      --MSP BuyerMSP peers --channel supplychannel \
      --server peer0.buyer.supply.test:7051
  '
~~~

Carrier, using only supply-carrier and Carrier private material:

~~~sh
docker run --rm --pull=never --platform linux/arm64 --network supply-carrier \
  --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/.runtime/identities/carrier/carrier-admin1/msp,dst=/run/supply/msp,readonly" \
  --mount "type=bind,src=$PWD/.runtime/identities/carrier/carrier-peer0-tls/msp,dst=/run/supply/tls,readonly" \
  --mount "type=bind,src=$PWD/.runtime/trust/carrier-tls-ca.pem,dst=/run/supply/peer-tls-root.pem,readonly" \
  --entrypoint sh supply-tools:m0-fabric3.1.5-ca1.5.22 -ceu '
    set -- /run/supply/msp/keystore/*_sk
    test "$#" -eq 1 && test -f "$1"
    user_key=$1
    set -- /run/supply/tls/keystore/*_sk
    test "$#" -eq 1 && test -f "$1"
    exec discover --peerTLSCA /run/supply/peer-tls-root.pem \
      --tlsCert /run/supply/tls/signcerts/cert.pem --tlsKey "$1" \
      --userKey "$user_key" --userCert /run/supply/msp/signcerts/cert.pem \
      --MSP CarrierMSP peers --channel supplychannel \
      --server peer0.carrier.supply.test:7051
  '
~~~

For each actual result, require one SellerMSP, one BuyerMSP and one CarrierMSP record with the expected peer0.<org>.supply.test:7051 external endpoint. Check the returned Peer ECert identities against the channel MSP roots and the running node identities; compare reported heights with contemporaneous native getinfo results. The query contacts its own Peer; another organization's endpoint appearing in that answer is evidence of discovery membership, while a real cross-organization Peer connection and ongoing gossip still require live Peer log/connection evidence. If any member is missing, record FAIL or NOT RUN at its actual stage and inspect the current anchors, gossip connectivity and logs before retrying. Do not infer a new block from unchanged height 1.

No transaction is submitted by these read-only queries, so no txId or validation code is expected. The pending NET-07 run must record the actual source commit, version-lock checksum, Compose tier, canonical genesisHash, commands, UTC times, raw-output hashes, expected/actual member sets and verdict under SPEC.md §19.1. Keep #18 open until live results have been independently checked.
