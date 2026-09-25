#!/usr/bin/env python3
"""Validate old/new Seller CouchDB env pairs without displaying credentials.

This is an offline input check. It does not inspect containers, contact CouchDB,
replace files, or prove that the running admin password has changed.
"""

import argparse
import re
import stat
import sys
from pathlib import Path


PASSWORD_RE = re.compile(r"[A-Za-z0-9_-]{40,}\Z")
DB_KEYS = {"COUCHDB_USER", "COUCHDB_PASSWORD"}
PEER_KEYS = {
    "CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME",
    "CORE_LEDGER_STATE_COUCHDBCONFIG_PASSWORD",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def private_dir(path: Path) -> None:
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700,
            f"directory must be real and mode 0700: {path}")


def read_env(path: Path, keys: set[str]) -> dict[str, str]:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600,
            f"file must be regular and mode 0600: {path}")
    try:
        raw = path.read_bytes().decode("ascii")
    except UnicodeError as exc:
        raise ValueError(f"non-ASCII credential file: {path}") from exc
    require(raw.endswith("\n"), f"missing final newline: {path}")
    lines = raw.splitlines()
    require(len(lines) == len(keys), f"unexpected credential line count: {path}")
    values: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition("=")
        require(separator and key in keys and key not in values and value,
                f"unexpected or duplicate credential key: {path}")
        values[key] = value
    require(set(values) == keys, f"missing credential key: {path}")
    return values


def seller_pair(root: Path) -> str:
    private_dir(root)
    private_dir(root / "couchdb")
    private_dir(root / "peer-couchdb")
    db = read_env(root / "couchdb/seller.env", DB_KEYS)
    peer = read_env(root / "peer-couchdb/seller.env", PEER_KEYS)
    require(db["COUCHDB_USER"] == "supply_seller"
            and peer["CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME"] == "supply_seller",
            "Seller CouchDB account name differs from the pinned deployment name")
    password = db["COUCHDB_PASSWORD"]
    require(PASSWORD_RE.fullmatch(password) is not None,
            "Seller CouchDB password does not match the generated-secret format")
    require(peer["CORE_LEDGER_STATE_COUCHDBCONFIG_PASSWORD"] == password,
            "Seller CouchDB and Peer password files differ")
    return password


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-root", type=Path, required=True,
                        help="private directory containing couchdb/ and peer-couchdb/ before rotation")
    parser.add_argument("--after-root", type=Path, required=True,
                        help="private directory containing the candidate or active rotated pair")
    args = parser.parse_args()
    try:
        require(args.before_root.resolve() != args.after_root.resolve(),
                "before and after roots must differ")
        before = seller_pair(args.before_root)
        after = seller_pair(args.after_root)
        require(before != after, "Seller CouchDB password did not change")
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("PASS: two private Seller env pairs are well formed, matched, and different")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
