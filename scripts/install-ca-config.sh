#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
service=${1:-}
case "$service" in
  ca-seller-tls|ca-seller-enroll|ca-buyer-tls|ca-buyer-enroll|ca-carrier-tls|ca-carrier-enroll|ca-orderer-tls|ca-orderer-enroll|ca-orderer-admin-tls) ;;
  *) printf 'Usage: %s <one CA service name>\n' "$0" >&2; exit 2 ;;
esac

name=${service#ca-}
template="$repo_root/config/ca/$name.yaml"
secret_file="$repo_root/.secrets/ca/$name.bootstrap"
if [[ ! -f "$template" || ! -f "$secret_file" ]]; then
  printf 'FAIL: template or private bootstrap secret is missing for %s\n' "$service" >&2
  exit 1
fi
bootstrap_secret=$(<"$secret_file")
if [[ ! "$bootstrap_secret" =~ ^[0-9a-f]{64}$ ]] ||
   [[ $(grep -c '^      pass: null$' "$template") -ne 1 ]]; then
  printf 'FAIL: expected a 64-character hex secret and one empty template password\n' >&2
  exit 1
fi

render() {
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == '      pass: null' ]]; then
      printf '      pass: "%s"\n' "$bootstrap_secret"
    else
      printf '%s\n' "$line"
    fi
  done < "$template"
}

render | docker compose -p supplyledger \
  -f "$repo_root/compose/bootstrap.yaml" -f "$repo_root/compose/ca.yaml" \
  --profile ca run --rm --no-deps -T --entrypoint sh "$service" -ceu '
    umask 077
    target=/etc/hyperledger/fabric-ca-server/fabric-ca-server-config.yaml
    test ! -e "$target"
    cat > "$target"
    chmod 600 "$target"
  '
printf 'Installed private CA config for %s; native CA init remains manual.\n' "$service"
