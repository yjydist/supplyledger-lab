#!/usr/bin/env python3
"""Compare Seller container env with private files without emitting values."""

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


SPECS = {
    "couchdb": {
        "container": "supplyledger-couchdb0-seller-1",
        "file": "couchdb/seller.env",
        "keys": {"COUCHDB_USER", "COUCHDB_PASSWORD"},
        "networks": {"supply-seller"},
    },
    "peer": {
        "container": "supplyledger-peer0-seller-1",
        "file": "peer-couchdb/seller.env",
        "keys": {
            "CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME",
            "CORE_LEDGER_STATE_COUCHDBCONFIG_PASSWORD",
        },
        "networks": {"supply-fabric", "supply-seller"},
    },
}


def require(condition: bool) -> None:
    if not condition:
        raise ValueError


def private_file(path: Path, keys: set[str]) -> dict[str, str]:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600)
    values: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        key, separator, value = line.partition("=")
        require(bool(separator) and key in keys and key not in values and bool(value))
        values[key] = value
    require(set(values) == keys)
    return values


def container_record(name: str) -> dict:
    result = subprocess.run(["docker", "inspect", name], capture_output=True,
                            text=True, check=False)
    require(result.returncode == 0)
    records = json.loads(result.stdout)
    require(isinstance(records, list) and len(records) == 1)
    return records[0]


def normalized_host_source(source: str) -> str:
    require(source.startswith("/"))
    if source.startswith("/host_mnt/"):
        source = source[len("/host_mnt"):]
    return os.path.normpath(source)


def expected_mounts(deployment_root: Path, component: str) -> dict[str, tuple]:
    if component == "couchdb":
        return {
            "/opt/couchdb/data": ("volume", "supplyledger_couchdb0_seller_data", True),
        }
    bind_sources = {
        "/etc/hyperledger/fabric/core.yaml": ".runtime/network-config/peer0-seller.yaml",
        "/opt/supplyledger/m2-chaincode-disabled": "builders/m2-chaincode-disabled",
        "/run/supply/msp": ".runtime/identities/seller/seller-peer0/msp",
        "/run/supply/tls": ".runtime/identities/seller/seller-peer0-tls/msp",
        "/run/supply/orderer-tls-root.pem": ".runtime/trust/orderer-tls-ca.pem",
        "/run/supply/peer-tls-root.pem": ".runtime/trust/seller-tls-ca.pem",
        "/run/supply/client-roots/buyer.pem": ".runtime/trust/buyer-tls-ca.pem",
        "/run/supply/client-roots/carrier.pem": ".runtime/trust/carrier-tls-ca.pem",
    }
    result = {
        "/var/hyperledger": ("anonymous-volume", None, True),
        "/etc/hyperledger/fabric": ("anonymous-volume", None, True),
        "/var/hyperledger/production": ("volume", "supplyledger_peer0_seller_ledger", True),
    }
    result.update({destination: ("bind", str(deployment_root / relative), False)
                   for destination, relative in bind_sources.items()})
    return result


def check_mounts(record: dict, deployment_root: Path, component: str) -> None:
    mounts = record["Mounts"]
    expected = expected_mounts(deployment_root, component)
    require(len(mounts) == len(expected))
    require({mount["Destination"] for mount in mounts} == set(expected))
    for mount in mounts:
        kind, source, writable = expected[mount["Destination"]]
        require(mount["RW"] is writable)
        if kind == "bind":
            require(mount["Type"] == "bind")
            require(normalized_host_source(mount["Source"]) == source)
        else:
            require(mount["Type"] == "volume")
            require(isinstance(mount.get("Name"), str) and bool(mount["Name"]))
            if kind == "volume":
                require(mount["Name"] == source)
            else:
                require(re.fullmatch(r"[0-9a-f]{64}", mount["Name"]) is not None)


def check_component(root: Path, deployment_root: Path, component: str) -> None:
    spec = SPECS[component]
    source = private_file(root / spec["file"], spec["keys"])
    record = container_record(spec["container"])
    require(record["State"]["Running"] is True)
    environment: dict[str, str] = {}
    for item in record["Config"]["Env"]:
        key, separator, value = item.partition("=")
        require(bool(separator) and key not in environment)
        environment[key] = value
    require(all(environment.get(key) == value for key, value in source.items()))
    check_mounts(record, deployment_root, component)
    require(set(record["NetworkSettings"]["Networks"]) == spec["networks"])
    require(not record["HostConfig"].get("PortBindings"))
    require(not any(bindings for bindings in record["NetworkSettings"].get("Ports", {}).values()))
    print(f"PASS: {spec['container']} required env keys match private source; "
          "running, exact expected mounts/networks and no host port")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secrets-root", type=Path, default=Path(".secrets"))
    parser.add_argument("--deployment-root", type=Path, default=Path.cwd())
    parser.add_argument("--component", choices=("couchdb", "peer", "both"),
                        required=True)
    args = parser.parse_args()
    try:
        components = ("couchdb", "peer") if args.component == "both" else (args.component,)
        for component in components:
            check_component(args.secrets_root, args.deployment_root.resolve(), component)
    except Exception:
        print("FAIL: Seller runtime env/mount check; inspect private inputs locally",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
