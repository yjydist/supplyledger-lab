#!/usr/bin/env bash
set -uo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd) || {
  printf '%s\n' 'FAIL: repository directory could not be resolved' >&2
  exit 1
}
lock_file="$repo_root/versions.lock.yaml"
compose_file="$repo_root/compose/bootstrap.yaml"
failures=0
probe_dir=

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; failures=$((failures + 1)); }
info() { printf 'INFO: %s\n' "$1"; }

cleanup() {
  if [[ -n "$probe_dir" && -d "$probe_dir" ]]; then
    if [[ -e "$probe_dir/from-container" ]]; then rm "$probe_dir/from-container" || return 1; fi
    if [[ -e "$probe_dir/executable.sh" ]]; then rm "$probe_dir/executable.sh" || return 1; fi
    rmdir "$probe_dir" || return 1
  fi
}
trap 'cleanup || { printf "%s\n" "FAIL: doctor probe cleanup failed" >&2; exit 1; }' EXIT

normalize_arch() {
  case "$1" in
    arm64|aarch64) printf 'arm64' ;;
    amd64|x86_64) printf 'amd64' ;;
    *) printf '%s' "$1" ;;
  esac
}

locked_tools_field() {
  awk -v key="$1" '
    /^  supplyTools:$/ { found = 1; next }
    found && /^  [^ ]/ { exit }
    found && $1 == key ":" { print $2; exit }
  ' "$lock_file"
}

locked_container_platform() {
  awk '
    /^platform:$/ { found = 1; next }
    found && /^[^ ]/ { exit }
    found && $1 == "containers:" { print $2; exit }
  ' "$lock_file"
}

file_owner() {
  if [[ "$(uname -s)" == Darwin ]]; then
    stat -f '%u:%g' "$1"
  else
    stat -c '%u:%g' "$1"
  fi
}

for command_name in docker git make bash awk grep mktemp stat df date uname id tr cat chmod rm rmdir; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    fail "required host command unavailable: $command_name"
  fi
done
if (( failures > 0 )); then
  exit 1
fi
pass 'required host commands available'

if [[ ! -f "$lock_file" ]]; then
  fail 'versions.lock.yaml is missing'
  exit 1
fi
tools_image=$(locked_tools_field localTag)
expected_tools_digest=$(locked_tools_field localIndexDigest)
expected_platform=$(locked_container_platform)
if [[ -z "$tools_image" || -z "$expected_tools_digest" || -z "$expected_platform" ]]; then
  fail 'tools image or platform is missing from versions.lock.yaml'
  exit 1
fi

host_os=$(uname -s | tr '[:upper:]' '[:lower:]')
host_arch=$(normalize_arch "$(uname -m)")
info "host platform: $host_os/$host_arch"
if [[ "$host_os/$host_arch" == "$(awk '/^  host:/ { print $2; exit }' "$lock_file")" ]]; then
  pass 'host platform matches version lock'
else
  fail 'host platform differs from the measured version lock'
fi

if ! docker_info=$(docker info --format '{{.OSType}}/{{.Architecture}}|{{.NCPU}}|{{.MemTotal}}' 2>/dev/null) || [[ -z "$docker_info" ]]; then
  fail 'Docker Engine is unavailable'
  exit 1
fi
docker_platform_raw=${docker_info%%|*}
docker_os=${docker_platform_raw%%/*}
docker_arch=$(normalize_arch "${docker_platform_raw#*/}")
docker_platform="$docker_os/$docker_arch"
docker_remainder=${docker_info#*|}
docker_cpus=${docker_remainder%%|*}
docker_memory=${docker_remainder#*|}
info "Docker platform: $docker_platform; CPUs: $docker_cpus; memory bytes: $docker_memory"
if [[ "$docker_platform" == "$expected_platform" && "$docker_arch" == "$host_arch" ]]; then
  pass 'Docker runs the locked native Linux architecture'
else
  fail "Docker platform differs from $expected_platform or requires emulation"
fi

docker_versions_ok=true
docker_client=$(docker version --format '{{.Client.Version}}' 2>/dev/null) || docker_versions_ok=false
docker_server=$(docker version --format '{{.Server.Version}}' 2>/dev/null) || docker_versions_ok=false
compose_version=$(docker compose version --short 2>/dev/null) || docker_versions_ok=false
buildx_version=$(docker buildx version 2>/dev/null) || docker_versions_ok=false
buildx_release=$(printf '%s\n' "$buildx_version" | awk '{ print $2 }')
if [[ "$docker_versions_ok" == true && -n "$docker_client" && -n "$docker_server" && -n "$compose_version" && -n "$buildx_release" ]]; then
  pass "Docker client/server $docker_client/$docker_server, Compose $compose_version, buildx $buildx_release"
else
  fail 'Docker version, Compose CLI, or buildx cannot be queried'
fi

host_memory=
if [[ "$host_os" == darwin ]]; then
  host_memory=$(sysctl -n hw.memsize 2>/dev/null) || host_memory=
elif [[ "$host_os" == linux && -r /proc/meminfo ]]; then
  host_memory=$(awk '/^MemTotal:/ { print $2 * 1024; exit }' /proc/meminfo) || host_memory=
fi
disk_available_kib=$(df -Pk "$repo_root" | awk 'NR == 2 { print $4 }') || disk_available_kib=
if [[ "$host_memory" =~ ^[0-9]+$ && "$docker_cpus" =~ ^[0-9]+$ && "$docker_memory" =~ ^[0-9]+$ && "$disk_available_kib" =~ ^[0-9]+$ ]]; then
  info "host memory bytes: $host_memory; workspace free KiB: $disk_available_kib"
  pass 'host, Docker, and disk resources measured'
  if (( host_memory < 16 * 1024 * 1024 * 1024 || docker_memory < 8 * 1024 * 1024 * 1024 || disk_available_kib < 50 * 1024 * 1024 )); then
    info 'below the suggested §2.3 dev resource budget; bootstrap may still work'
  fi
else
  fail 'host memory or workspace free disk could not be measured'
fi

if docker compose -p supplyledger -f "$compose_file" --profile bootstrap config --quiet; then
  pass 'M0 bootstrap Compose config parses'
else
  fail 'M0 bootstrap Compose config is invalid'
fi
if compose_images=$(docker compose -p supplyledger -f "$compose_file" --profile bootstrap config --images 2>/dev/null) && [[ "$compose_images" == "$tools_image" ]]; then
  pass 'bootstrap Compose uses the locked tools image tag'
else
  fail 'bootstrap Compose image differs from the version lock'
fi
info 'formal §3.5 network Compose: NOT RUN'

LC_ALL=C grep -q $'\r' "$repo_root/Makefile" "$compose_file" "$repo_root/scripts/doctor.sh" "$repo_root/scripts/reset.sh"
line_ending_status=$?
if [[ -x "$repo_root/scripts/doctor.sh" && -x "$repo_root/scripts/reset.sh" && "$line_ending_status" -eq 1 ]]; then
  pass 'script executable modes and LF line endings'
else
  fail 'script executable modes or LF line endings are invalid'
fi

if tools_descriptor=$(docker image inspect "$tools_image" --format '{{.Descriptor.digest}}|{{.Os}}/{{.Architecture}}' 2>/dev/null) &&
   [[ "$tools_descriptor" == "$expected_tools_digest|$expected_platform" ]]; then
  pass "locked local tools image $tools_image is available"
else
  fail "local tools image is absent or differs from lock; run make tools-build and remeasure if needed"
  exit 1
fi

if docker run --rm --pull=never --platform "$expected_platform" --network none --read-only \
     --entrypoint bash "$tools_image" -euc '
       for binary in peer orderer configtxgen configtxlator osnadmin discover fabric-ca-client jq openssl curl tar gzip; do
         command -v "$binary" >/dev/null
       done
       peer version >/dev/null
       orderer version >/dev/null
       configtxgen -version >/dev/null
       configtxlator version >/dev/null
       fabric-ca-client version >/dev/null
       osnadmin --help >/dev/null
       discover --help >/dev/null
     ' >/dev/null 2>&1; then
  pass 'locked Fabric, CA, and diagnostic commands execute in tools image'
else
  fail 'a required tools-image command is unavailable or fails'
fi

if ! probe_dir=$(mktemp -d /tmp/supplyledger-doctor.XXXXXX) || [[ -z "$probe_dir" || ! -d "$probe_dir" ]]; then
  fail 'temporary doctor probe directory could not be created'
  exit 1
fi
if ! printf '#!/bin/sh\nexit 0\n' > "$probe_dir/executable.sh" || ! chmod 755 "$probe_dir/executable.sh"; then
  fail 'temporary executable probe could not be prepared'
  exit 1
fi
host_uid=$(id -u) || host_uid=
host_gid=$(id -g) || host_gid=
host_timezone=$(date +%z) || host_timezone=
if [[ ! "$host_uid" =~ ^[0-9]+$ || ! "$host_gid" =~ ^[0-9]+$ || ! "$host_timezone" =~ ^[+-][0-9]{4}$ ]]; then
  fail 'host UID/GID or UTC offset could not be measured'
  exit 1
fi
if probe_result=$(docker run --rm --pull=never --platform "$expected_platform" --network none --read-only \
  --user "$host_uid:$host_gid" -e TZ=UTC \
  --mount "type=bind,src=$probe_dir,dst=/probe" \
  --entrypoint bash "$tools_image" -euc '
    test -x /probe/executable.sh
    /probe/executable.sh
    printf "supplyledger-doctor\n" > /probe/from-container
    printf "%s:%s %s\n" "$(id -u)" "$(id -g)" "$(date +%z)"
  ' 2>/dev/null) && [[ -f "$probe_dir/from-container" ]] &&
   probe_contents=$(cat "$probe_dir/from-container") && [[ "$probe_contents" == supplyledger-doctor ]]; then
  container_identity=${probe_result%% *}
  container_timezone=${probe_result#* }
  file_identity=$(file_owner "$probe_dir/from-container")
  info "host UID:GID $host_uid:$host_gid; container UID:GID $container_identity; bind-file owner $file_identity"
  info "host UTC offset $host_timezone; container UTC offset $container_timezone (TZ=UTC)"
  if [[ "$file_identity" != "$host_uid:$host_gid" ]]; then
    info 'bind-mounted file group differs from host GID; Docker Desktop may remap the group'
  fi
  if [[ "$container_identity" == "$host_uid:$host_gid" && "${file_identity%%:*}" == "$host_uid" && "$container_timezone" == +0000 ]]; then
    pass 'read/write bind mount, executable mode, process UID/GID, file UID, and UTC time zone'
  else
    fail 'bind mount, UID/GID mapping, or UTC time zone differs from expected behavior'
  fi
else
  fail 'temporary bind mount or container execution failed'
fi

if cleanup; then
  probe_dir=
  trap - EXIT
else
  fail 'temporary doctor probe cleanup failed'
fi

if (( failures > 0 )); then
  printf 'Doctor: FAIL (%s checks)\n' "$failures" >&2
  exit 1
fi
printf '%s\n' 'Doctor: PASS for M0 bootstrap checks; formal network readiness NOT RUN'
