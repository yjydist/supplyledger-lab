#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
lock_file="$repo_root/versions.lock.yaml"
compose_file="$repo_root/compose/bootstrap.yaml"
ca_compose_file="$repo_root/compose/ca.yaml"
project=supplyledger

tools_image=$(awk '
  /^  supplyTools:$/ { found = 1; next }
  found && /^  [^ ]/ { exit }
  found && $1 == "localTag:" { print $2; exit }
' "$lock_file")
expected_tools_digest=$(awk '
  /^  supplyTools:$/ { found = 1; next }
  found && /^  [^ ]/ { exit }
  found && $1 == "localIndexDigest:" { print $2; exit }
' "$lock_file")
expected_platform=$(awk '
  /^platform:$/ { found = 1; next }
  found && /^[^ ]/ { exit }
  found && $1 == "containers:" { print $2; exit }
' "$lock_file")
actual_tools_descriptor=$(docker image inspect "$tools_image" --format '{{.Descriptor.digest}}|{{.Os}}/{{.Architecture}}' 2>/dev/null) || {
  printf '%s\n' 'FAIL: locked supply-tools image is unavailable; reset cannot inspect the Compose volume model' >&2
  exit 1
}
if [[ -z "$tools_image" || -z "$expected_tools_digest" || -z "$expected_platform" ||
      "$actual_tools_descriptor" != "$expected_tools_digest|$expected_platform" ]]; then
  printf '%s\n' 'FAIL: local supply-tools image differs from versions.lock.yaml; reset stopped before volume selection' >&2
  exit 1
fi

compose=(docker compose -p "$project" -f "$compose_file" -f "$ca_compose_file" --profile '*')
config_json=$("${compose[@]}" config --format json)
volume_rows=$(printf '%s\n' "$config_json" |
  docker run --rm --pull=never --network none --read-only -i \
    --entrypoint jq "$tools_image" -r '
      (.volumes // {}) | to_entries[] |
      [.key, .value.name, ((.value.external // false) | tostring), ((.value.labels // {})["supplyledger.reset"] // "unmarked")] |
      @tsv
    ')
existing_volumes=$(docker volume ls --format '{{.Name}}')

targets=()
while IFS=$'\t' read -r logical actual external reset_label; do
  [[ -n "$logical" ]] || continue
  if [[ "$external" == true ]]; then
    printf 'Retained external volume: %s\n' "$actual"
    continue
  fi
  case "$logical:$actual" in
    *backup*|*Backup*|*BACKUP*)
      printf 'FAIL: backup-like volume must be external and is never a reset target: %s\n' "$actual" >&2
      exit 1 ;;
  esac
  if [[ "$reset_label" != allow ]]; then
    printf 'FAIL: non-external volume lacks supplyledger.reset=allow: %s\n' "$actual" >&2
    exit 1
  fi
  if [[ ! "$actual" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    printf 'FAIL: unsafe resolved volume name: %s\n' "$actual" >&2
    exit 1
  fi
  if ! printf '%s\n' "$existing_volumes" | grep -Fqx -- "$actual"; then
    continue
  fi
  project_label=$(docker volume inspect "$actual" --format '{{ index .Labels "com.docker.compose.project" }}')
  logical_label=$(docker volume inspect "$actual" --format '{{ index .Labels "com.docker.compose.volume" }}')
  reset_volume_label=$(docker volume inspect "$actual" --format '{{ index .Labels "supplyledger.reset" }}')
  if [[ "$project_label" != "$project" || "$logical_label" != "$logical" || "$reset_volume_label" != allow ]]; then
    printf 'FAIL: volume labels do not match the Compose target: %s\n' "$actual" >&2
    exit 1
  fi
  targets+=("$actual")
done <<< "$volume_rows"

printf 'Reset target named volumes (%s):\n' "${#targets[@]}"
if (( ${#targets[@]} == 0 )); then
  printf '%s\n' '  none'
else
  printf '  %s\n' "${targets[@]}"
fi
printf '%s\n' 'Backups are not selected or deleted.'

if [[ "${CONFIRM_DESTROY:-}" != "$project" ]]; then
  printf 'NOT RUN: reset requires CONFIRM_DESTROY=%s; no containers or volumes were changed.\n' "$project" >&2
  exit 2
fi

"${compose[@]}" down
for actual in "${targets[@]}"; do
  project_label=$(docker volume inspect "$actual" --format '{{ index .Labels "com.docker.compose.project" }}')
  reset_volume_label=$(docker volume inspect "$actual" --format '{{ index .Labels "supplyledger.reset" }}')
  if [[ "$project_label" != "$project" || "$reset_volume_label" != allow ]]; then
    printf 'FAIL: volume labels changed before deletion: %s\n' "$actual" >&2
    exit 1
  fi
  docker volume rm "$actual"
done
printf '%s\n' 'Reset complete for the exact listed volumes.'
