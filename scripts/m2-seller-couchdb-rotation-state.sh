#!/usr/bin/env bash
# Source at the start of every separate Seller rotation command file.
set -euo pipefail
umask 077

rotation_marker=.runtime/m2-seller-couchdb-rotation-active
if [[ ! -f "$rotation_marker" || -L "$rotation_marker" ]]; then
  printf '%s\n' 'FAIL: missing or unsafe Seller rotation marker' >&2
  return 1
fi
ROTATION_DIR=$(cat "$rotation_marker")
if [[ ! "$ROTATION_DIR" =~ ^\.runtime/m2-seller-couchdb-rotation-[0-9]{8}T[0-9]{6}Z$ ]] ||
   [[ ! -d "$ROTATION_DIR" || -L "$ROTATION_DIR" ]]; then
  printf '%s\n' 'FAIL: invalid Seller rotation directory' >&2
  return 1
fi
python3 - "$rotation_marker" "$ROTATION_DIR" <<'PY'
import stat
import sys
from pathlib import Path

for raw, kind, mode in (
    (".runtime", stat.S_ISDIR, 0o700),
    (sys.argv[1], stat.S_ISREG, 0o600),
    (sys.argv[2], stat.S_ISDIR, 0o700),
):
    info = Path(raw).lstat()
    if not kind(info.st_mode) or stat.S_IMODE(info.st_mode) != mode:
        raise SystemExit("FAIL: Seller rotation state has unsafe type or mode")
PY
export ROTATION_DIR
