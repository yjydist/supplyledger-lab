#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"
lock_file=$repo_root/versions.lock.yaml

pass() { printf 'PASS: %s\n' "$1"; }
die() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

lock_get() {
  awk -v wanted="$1" '
    /^[[:space:]]*($|#)/ { next }
    {
      match($0, /^ */)
      depth = int(RLENGTH / 2) + 1
      entry = substr($0, RLENGTH + 1)
      if (index(entry, ":") == 0) next
      key = entry
      sub(/:.*/, "", key)
      path[depth] = key
      for (i = depth + 1; i <= last_depth; i++) delete path[i]
      last_depth = depth
      current = path[1]
      for (i = 2; i <= depth; i++) current = current "." path[i]
      if (current == wanted) {
        sub(/^[^:]*:[[:space:]]*/, "", entry)
        sub(/^"/, "", entry)
        sub(/"$/, "", entry)
        print entry
        found = 1
        exit
      }
    }
    END { if (!found) exit 1 }
  ' "$lock_file"
}

locked() {
  local value
  value=$(lock_get "$1") || die "missing lock field: $1"
  [[ -n "$value" ]] || die "empty lock field: $1"
  printf '%s' "$value"
}

require_digest() {
  [[ "$2" =~ ^sha256:[[:xdigit:]]{64}$ ]] || die "invalid digest in $1"
}

for tool in bash awk cat docker git grep id sed sort tr uname; do
  command -v "$tool" >/dev/null 2>&1 || die "required host command unavailable: $tool"
done
[[ -f "$lock_file" ]] || die 'versions.lock.yaml is missing'
awk -f scripts/validate-version-lock.awk "$lock_file" || die 'version lock syntax or key uniqueness check failed'
pass 'version lock syntax and unique key paths'

expected_host=$(locked platform.host)
expected_platform=$(locked platform.containers)
[[ "$(locked platform.emulated)" == false ]] || die 'version lock requires an emulated container architecture'
host_os=$(uname -s | tr '[:upper:]' '[:lower:]')
host_arch=$(uname -m)
case "$host_arch" in aarch64) host_arch=arm64 ;; x86_64) host_arch=amd64 ;; esac
[[ "$host_os/$host_arch" == "$expected_host" ]] || die "host $host_os/$host_arch differs from lock $expected_host"
docker_arch=$(docker info --format '{{.Architecture}}') || die 'Docker Engine is unavailable'
case "$docker_arch" in aarch64) docker_arch=arm64 ;; x86_64) docker_arch=amd64 ;; esac
docker_os=$(docker info --format '{{.OSType}}') || die 'Docker Engine OS is unavailable'
[[ "$docker_os/$docker_arch" == "$expected_platform" && "$docker_arch" == "$host_arch" ]] || die 'Docker platform differs from the locked native architecture'
if command -v go >/dev/null 2>&1; then
  if host_go=$(go version 2>/dev/null); then
    printf 'INFO: host Go: %s; lock observation: go version %s (not a build gate)\n' "$host_go" "$(locked tools.hostGo)"
  else
    printf '%s\n' 'INFO: host Go version unavailable; pinned container builder remains the build gate'
  fi
else
  printf '%s\n' 'INFO: host Go absent; pinned container builder remains the build gate'
fi
[[ "$(docker version --format '{{.Client.Version}}')" == "$(locked tools.dockerClient.version)" ]] || die 'Docker client version differs from lock'
[[ "$(docker version --format '{{.Server.Version}}')" == "$(locked tools.dockerEngine.version)" ]] || die 'Docker Engine version differs from lock'
[[ "v$(docker compose version --short | sed 's/^v//')" == "$(locked tools.compose)" ]] || die 'Compose version differs from lock'
[[ "$(docker buildx version | awk '{print $2}')" == "$(locked tools.buildx)" ]] || die 'Buildx version differs from lock'
pass "host $expected_host; Docker $expected_platform; Docker/Compose/Buildx match lock"

bash scripts/doctor.sh || die 'M0 doctor failed'
docker compose -p supplyledger -f compose/bootstrap.yaml --profile bootstrap config --quiet || die 'bootstrap Compose config failed'
tools_image=$(locked images.supplyTools.localTag)
[[ "$(docker compose -p supplyledger -f compose/bootstrap.yaml --profile bootstrap config --images)" == "$tools_image" ]] || die 'bootstrap Compose image differs from lock'
pass 'bootstrap Compose configuration and locked tools image'

for image_key in ubuntuBase fabricPeer fabricOrderer fabricCA couchdb postgres goBuilder; do
  reference=$(locked "images.$image_key.reference")
  index_digest=$(locked "images.$image_key.manifestDigest")
  platform_digest=$(locked "images.$image_key.platformDigest")
  platform=$(locked "images.$image_key.platform")
  require_digest "images.$image_key.manifestDigest" "$index_digest"
  require_digest "images.$image_key.platformDigest" "$platform_digest"
  [[ "$reference" == *@"$index_digest" && "$platform" == "$expected_platform" ]] || die "image $image_key reference/platform differs from lock"
  [[ "$(docker image inspect "$reference" --format '{{.Descriptor.digest}}')" == "$index_digest" ]] || die "image $image_key index digest differs from lock"
  [[ "$(docker image inspect --platform "$platform" "$reference" --format '{{.Descriptor.digest}} {{.Os}}/{{.Architecture}}')" == "$platform_digest $platform" ]] || die "image $image_key platform digest differs from lock"
done
base_reference=$(locked images.ubuntuBase.reference)
[[ "$(awk '$1 == "FROM" { print $2; exit }' docker/tools/Dockerfile)" == "$base_reference" ]] || die 'tools Dockerfile base differs from lock'
pass 'seven official image references, local index descriptors, and platform descriptors match lock'

tools_index=$(locked images.supplyTools.localIndexDigest)
tools_platform=$(locked images.supplyTools.localPlatformDigest)
require_digest images.supplyTools.localIndexDigest "$tools_index"
require_digest images.supplyTools.localPlatformDigest "$tools_platform"
[[ "$(docker image inspect "$tools_image" --format '{{.Descriptor.digest}} {{.Os}}/{{.Architecture}}')" == "$tools_index $expected_platform" ]] || die 'local tools image index digest differs from lock'
[[ "$(docker image inspect --platform "$expected_platform" "$tools_image" --format '{{.Descriptor.digest}} {{.Os}}/{{.Architecture}}')" == "$tools_platform $expected_platform" ]] || die 'local tools image platform digest differs from lock'
[[ "$(locked images.supplyTools.publishedManifestDigest)" == 'NOT RUN' ]] || die 'published tools manifest needs separate registry verification'
pass 'self-built local tools image index/platform digests match lock; publication NOT RUN'

{
  for binary in peer orderer configtxgen configtxlator osnadmin discover; do
    printf '%s  /usr/local/bin/%s\n' "$(locked "releases.fabric.binariesSha256.$binary")" "$binary"
  done
  printf '%s  /usr/local/bin/fabric-ca-client\n' "$(locked releases.fabricCA.binariesSha256.fabric-ca-client)"
} | docker run -i --rm --pull=never --platform "$expected_platform" --network none --read-only \
  --entrypoint sha256sum "$tools_image" --check || die 'tools CLI binary SHA-256 mismatch'
docker run --rm --pull=never --platform "$expected_platform" --network none --read-only \
  -e FABRIC_VERSION="$(locked releases.fabric.version)" \
  -e CA_VERSION="$(locked releases.fabricCA.version)" \
  -e CONTAINER_PLATFORM="$expected_platform" \
  --entrypoint bash "$tools_image" -euc '
    for binary in peer orderer configtxgen configtxlator osnadmin discover fabric-ca-client bash jq openssl curl tar gzip; do
      command -v "$binary" >/dev/null
    done
    for binary in peer orderer configtxgen configtxlator; do
      if [[ "$binary" == configtxgen ]]; then output=$($binary -version); else output=$($binary version); fi
      grep -Fq "Version: $FABRIC_VERSION" <<< "$output"
      grep -Fq "OS/Arch: $CONTAINER_PLATFORM" <<< "$output"
    done
    output=$(fabric-ca-client version)
    grep -Fq "Version: $CA_VERSION" <<< "$output"
    grep -Fq "OS/Arch: $CONTAINER_PLATFORM" <<< "$output"
    osnadmin --help >/dev/null 2>&1
    discover --help >/dev/null 2>&1
  ' || die 'tools CLI versions, platform, or required commands differ from lock'
package_sha=$(docker run --rm --pull=never --platform "$expected_platform" --network none --read-only \
  --entrypoint bash "$tools_image" -euc "dpkg-query -W -f='\${Package}=\${Version}\\n' | LC_ALL=C sort | sha256sum | awk '{print \$1}'") || die 'tools OS package query failed'
[[ "$package_sha" == "$(locked images.supplyTools.osPackageManifestSha256)" ]] || die 'tools OS package manifest differs from lock'
pass 'Fabric/CA CLI versions, binary SHA-256, diagnostics, and OS package manifest match lock'

{
  for module in chaincode app; do
    for suffix in Mod Sum; do
      file=$(locked "modules.$module.go$suffix")
      digest=$(locked "modules.$module.go${suffix}Sha256")
      printf '%s  /work/%s\n' "$digest" "$file"
    done
  done
} | docker run -i --rm --pull=never --platform "$expected_platform" --network none --read-only \
  --mount "type=bind,src=$repo_root,dst=/work,readonly" \
  --entrypoint sha256sum "$tools_image" --check || die 'Go module lock-file SHA-256 mismatch'
[[ "$(locked tools.buildGo.version)" == "go1.26.8 $expected_platform" && "$(locked tools.buildGo.GOTOOLCHAIN)" == local ]] || die 'locked Go build toolchain differs from M0 requirement'
builder_image=$(locked images.goBuilder.reference)
docker run --rm --pull=never --platform "$expected_platform" --read-only \
  --user "$(id -u):$(id -g)" --mount "type=bind,src=$repo_root,dst=/work,readonly" \
  --tmpfs /tmp:rw,exec,size=2g,mode=1777 --workdir /work \
  -e GOTOOLCHAIN=local -e GOCACHE=/tmp/go-build -e GOMODCACHE=/tmp/go-mod \
  -e GOPROXY=https://proxy.golang.org,direct -e GOSUMDB=sum.golang.org \
  -e EXPECTED_GO="$(locked tools.buildGo.version)" \
  --entrypoint bash "$builder_image" -euc '
    [[ "$(go version)" == "go version $EXPECTED_GO" ]]
    [[ "$(go env GOTOOLCHAIN)" == local ]]
    for module in chaincode app; do
      printf "INFO: Go %s build, test, vet, and module verification\n" "$module"
      cd "/work/$module"
      go build -mod=readonly ./...
      go test -mod=readonly ./...
      go vet -mod=readonly ./...
      go mod verify
    done
  ' || die 'locked Go build/test/vet/module verification failed'
pass 'Go 1.26.8 with GOTOOLCHAIN=local built, tested, vetted, and verified both locked modules'

forbidden_pattern='fabric-''samples|test-''network|network[.]sh|fabric-''tools'
forbidden_matches=$(git grep -n -E "$forbidden_pattern" -- Makefile scripts compose docker chaincode app) && forbidden_status=0 || forbidden_status=$?
if (( forbidden_status == 0 )); then
  printf '%s\n' "$forbidden_matches" >&2
  die 'sample network or prebuilt tools dependency found in executable paths'
fi
(( forbidden_status == 1 )) || die 'executable dependency scan failed'
submodules=$(git submodule status) || die 'submodule inventory failed'
[[ -z "$submodules" ]] || die 'repository has an unreviewed submodule dependency'
pass 'no sample network, prebuilt tools image, or submodule dependency in executable paths'

[[ "$(cat docker/tools/.dockerignore)" == $'**\n!Dockerfile\n!.dockerignore' ]] || die 'tools build context allowlist changed'
tracked_paths=$(git ls-files) || die 'tracked path inventory failed'
secret_paths=$(printf '%s\n' "$tracked_paths" | grep -E '(^|/)([.]env$|[.]secrets/|[.]runtime/|backups?/|keystore/)|[.](key|p12|pfx|db|sqlite3)$') && path_status=0 || path_status=$?
if (( path_status == 0 )); then
  printf '%s\n' "$secret_paths" >&2
  die 'tracked secret or runtime artifact path found'
fi
(( path_status == 1 )) || die 'tracked secret path scan failed'
private_key_pattern='BEGIN (RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY'
key_matches=$(git grep -n -I -E "$private_key_pattern") && key_status=0 || key_status=$?
if (( key_status == 0 )); then
  printf '%s\n' "$key_matches" >&2
  die 'tracked private-key material marker found'
fi
(( key_status == 1 )) || die 'tracked private-key scan failed'
pass 'tracked secret path/key-marker scan and tools build-context allowlist'

printf '%s\n' 'M0 exit: PASS for toolchain, locked observed inputs, bootstrap configuration, and repository scan'
printf '%s\n' 'NOT RUN: formal Fabric CA/network, genesis, channel, chaincode, transactions, and later-stage security/fault tests'
