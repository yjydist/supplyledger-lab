FROM docker.io/library/ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

ARG TARGETARCH

RUN set -eu; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      bash=5.2.21-2ubuntu4 \
      ca-certificates=20260601~24.04.1 \
      coreutils=9.4-3ubuntu6.3 \
      curl=8.5.0-2ubuntu10.13 \
      gzip=1.12-1ubuntu3.2 \
      jq=1.7.1-3ubuntu0.24.04.2 \
      openssl=3.0.13-0ubuntu3.15 \
      tar=1.35+dfsg-3ubuntu0.4; \
    rm -rf /var/lib/apt/lists/*

RUN set -eu; \
    case "$TARGETARCH" in \
      arm64) \
        fabric_sha=4a42cad740a7e0373eda6bf1e27c86e9b06132f9bb751daf7f0f7dc1d1bbfed9; \
        ca_sha=a2d8f5bf607dc38ce271d456244d754eb8f0a605332749285fcd1073ed19284f ;; \
      amd64) \
        fabric_sha=b9c31fd490991e76f8acb1835dee09fc19fee5428cb13e190ee6e0bdd2c37858; \
        ca_sha=7f52ab98481ac0e4bfcf5b5aabfb403fa692ee100ae3b2ca3bf3f2152851573d ;; \
      *) echo "Unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    fabric_archive="hyperledger-fabric-linux-${TARGETARCH}-3.1.5.tar.gz"; \
    ca_archive="hyperledger-fabric-ca-linux-${TARGETARCH}-1.5.22.tar.gz"; \
    mkdir -p /tmp/supply-releases/fabric /tmp/supply-releases/ca; \
    curl --fail --location --silent --show-error --retry 3 \
      "https://github.com/hyperledger/fabric/releases/download/v3.1.5/${fabric_archive}" \
      --output /tmp/supply-releases/fabric.tar.gz; \
    printf '%s  %s\n' "$fabric_sha" /tmp/supply-releases/fabric.tar.gz | sha256sum --check; \
    curl --fail --location --silent --show-error --retry 3 \
      "https://github.com/hyperledger/fabric-ca/releases/download/v1.5.22/${ca_archive}" \
      --output /tmp/supply-releases/ca.tar.gz; \
    printf '%s  %s\n' "$ca_sha" /tmp/supply-releases/ca.tar.gz | sha256sum --check; \
    tar -xzf /tmp/supply-releases/fabric.tar.gz -C /tmp/supply-releases/fabric \
      bin/peer bin/orderer bin/configtxgen bin/configtxlator bin/osnadmin bin/discover; \
    tar -xzf /tmp/supply-releases/ca.tar.gz -C /tmp/supply-releases/ca \
      bin/fabric-ca-client; \
    for binary in peer orderer configtxgen configtxlator osnadmin discover; do \
      install -m 0755 "/tmp/supply-releases/fabric/bin/$binary" /usr/local/bin/; \
    done; \
    install -m 0755 /tmp/supply-releases/ca/bin/fabric-ca-client /usr/local/bin/; \
    rm -rf /tmp/supply-releases

WORKDIR /work
CMD ["bash"]
