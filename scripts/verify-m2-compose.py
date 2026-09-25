#!/usr/bin/env python3
"""Read-only M2 Compose policy check; live container inspection is separate."""

import json
import hashlib
import re
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ORG = ("seller", "buyer", "carrier")
ORDERERS = tuple(f"orderer{index}" for index in range(3))
PEERS = tuple(f"peer0-{org}" for org in ORG)
COUCHDBS = tuple(f"couchdb0-{org}" for org in ORG)
M2_SERVICES = ORDERERS + PEERS + COUCHDBS
CA_SERVICES = tuple(f"ca-{org}-{kind}" for org in (*ORG, "orderer")
                    for kind in ("tls", "enroll")) + ("ca-orderer-admin-tls",)
EXPECTED_SERVICES = set(("tools",) + CA_SERVICES + M2_SERVICES)
COMPOSE = (
    "docker", "compose", "-p", "supplyledger", "-f", "compose/bootstrap.yaml",
    "-f", "compose/ca.yaml", "-f", "compose/network.yaml", "--profile",
    "bootstrap", "--profile", "ca",
)
M2_BUILDER_HASHES = {
    "detect": "581ef8cf5c519b603a5b116aa4d7e48aff620249704d77b8458b7cb0074ae33f",
    "build": "d322c173f8f7708acf3691dd70aae39a9251662d2064aecae13e2066209fbc14",
    "release": "76377bfa9730dab505a56e7f525e9cca0fcb1edb90131a431a3e1649c5a6f587",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def locked_image(key):
    lock = (ROOT / "versions.lock.yaml").read_text()
    match = re.search(rf"(?m)^  {re.escape(key)}:\n    reference: (\S+)$", lock)
    require(match is not None, f"version lock has no image reference for {key}")
    return match.group(1)


def check_m2_builder():
    directory = ROOT / "builders/m2-chaincode-disabled"
    bin_dir = directory / "bin"
    for path in (directory, bin_dir):
        require(path.is_dir() and not path.is_symlink()
                and stat.S_IMODE(path.stat().st_mode) == 0o755,
                f"missing or linked M2 deny-all builder directory: {path}")
    require({path.name for path in directory.iterdir()} == {"bin"},
            "unexpected M2 deny-all builder root entry")
    require({path.name for path in bin_dir.iterdir()} == set(M2_BUILDER_HASHES),
            "unexpected M2 deny-all builder program")
    for name, expected_hash in M2_BUILDER_HASHES.items():
        path = bin_dir / name
        require(path.is_file() and not path.is_symlink()
                and stat.S_IMODE(path.stat().st_mode) == 0o755,
                f"unsafe M2 deny-all builder program mode: {name}")
        data = path.read_bytes()
        require(data.startswith(b"#!/bin/sh\n")
                and hashlib.sha256(data).hexdigest() == expected_hash,
                f"M2 deny-all builder program changed: {name}")
    print("PASS: three tracked M2 deny-all builder programs have pinned bytes and mode 0755")


def compose_model():
    result = subprocess.run((*COMPOSE, "config", "--no-env-resolution", "--format", "json"),
                            cwd=ROOT, capture_output=True, text=True, check=False)
    require(result.returncode == 0, f"Compose config failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def check_networks(model):
    networks = model["networks"]
    expected = {
        "fabric": ("supply-fabric", False),
        "seller": ("supply-seller", True),
        "buyer": ("supply-buyer", True),
        "carrier": ("supply-carrier", True),
        "orderer": ("supply-orderer", True),
    }
    require(set(networks) == set(expected), "unexpected or missing Docker network")
    for key, (name, internal) in expected.items():
        require(key in networks, f"missing network {key}")
        require(networks[key].get("name") == name, f"wrong network name for {key}")
        require(bool(networks[key].get("internal")) is internal,
                f"wrong internal setting for {key}")
    print("PASS: shared Fabric network and four separate internal organization networks")


def check_service_network(service, expected):
    networks = service.get("networks", {})
    require(set(networks) == set(expected), f"{service['name']}: wrong network membership")
    for network, host in expected.items():
        require(networks[network].get("aliases") == [host],
                f"{service['name']}: wrong {network} DNS alias")


def check_volumes(model):
    volumes = model["volumes"]
    require(len(volumes) == 18, "expected nine retained CA and nine separate M2 volumes")
    names = [volume.get("name") for volume in volumes.values()]
    require(len(set(names)) == len(names), "two logical volumes share one resolved name")
    for key, volume in volumes.items():
        require(not volume.get("external"), f"unexpected external data volume {key}")
        require(volume.get("labels", {}).get("supplyledger.reset") == "allow",
                f"reset allowlist label missing on {key}")
        require("backup" not in key.lower() and "backup" not in volume["name"].lower(),
                f"backup-like volume declared: {key}")
    print("PASS: 18 distinct, explicitly reset-labeled named volumes; no backup target")


def check_mounts(service, data_source, data_target, binds):
    mounts = service.get("volumes", [])
    require(len(mounts) == len(binds) + 1, f"{service['name']}: unexpected mount count")
    data = [mount for mount in mounts if mount.get("type") == "volume"]
    require(len(data) == 1 and data[0].get("source") == data_source
            and data[0].get("target") == data_target,
            f"{service['name']}: wrong or shared state volume")
    actual_binds = {mount.get("target"): mount for mount in mounts
                    if mount.get("type") == "bind"}
    require(set(actual_binds) == set(binds), f"{service['name']}: unexpected bind target")
    for target, relative_source in binds.items():
        mount = actual_binds[target]
        require(mount.get("source") == str(ROOT / relative_source),
                f"{service['name']}: unexpected source for {target}")
        require(mount.get("read_only") is True, f"{service['name']}: writable bind {target}")
        require(mount.get("bind", {}).get("create_host_path") is False,
                f"{service['name']}: missing bind source could be auto-created")
    for mount in mounts:
        require("docker.sock" not in str(mount), f"{service['name']}: Docker socket mount")


def check_nodes(model):
    services = model["services"]
    require(set(services) == EXPECTED_SERVICES,
            "unexpected or missing service in the M2 base Compose model")
    images = {
        "orderer": locked_image("fabricOrderer"),
        "peer": locked_image("fabricPeer"),
        "couchdb": locked_image("couchdb"),
    }
    for name in M2_SERVICES:
        require(name in services, f"missing M2 service {name}")
        service = dict(services[name], name=name)
        require(not service.get("profiles"), f"{name}: base service has a profile")
        require(not service.get("ports"), f"{name}: host port published")
        require(not service.get("depends_on"), f"{name}: startup dependency masks readiness")
        kind = "orderer" if name in ORDERERS else "peer" if name in PEERS else "couchdb"
        require(service.get("image") == images[kind] and service.get("pull_policy") == "never",
                f"{name}: image differs from measured version lock")
        if kind in ("orderer", "peer"):
            require(service.get("read_only") is True, f"{name}: writable node root filesystem")
            require(service.get("environment") == {"FABRIC_CFG_PATH": "/etc/hyperledger/fabric"},
                    f"{name}: environment could override TLS/MSP configuration")
            require(not service.get("command") and not service.get("entrypoint"),
                    f"{name}: unreviewed command or entrypoint override")

        if kind == "orderer":
            require(not service.get("env_file"), f"{name}: unreviewed environment file")
            host = f"{name}.orderer.supply.test"
            check_service_network(service, {"fabric": host, "orderer": host})
            check_mounts(service, f"{name}-ledger", "/var/hyperledger/production", {
                "/etc/hyperledger/fabric/orderer.yaml": f".runtime/network-config/{name}.yaml",
                "/run/supply/msp": f".runtime/identities/orderer/{name}/msp",
                "/run/supply/tls": f".runtime/identities/orderer/{name}-tls/msp",
                "/run/supply/admin-server-tls":
                    f".runtime/identities/orderer/{name}-admin-server-tls/msp",
                "/run/supply/admin-client-root.pem":
                    ".runtime/trust/orderer-admin-tls-ca.pem",
                **{f"/run/supply/client-roots/{org}.pem":
                       f".runtime/trust/{org}-tls-ca.pem"
                   for org in ("orderer",) + ORG},
            })
        elif kind == "peer":
            org = name.removeprefix("peer0-")
            host = f"peer0.{org}.supply.test"
            require(service.get("env_file") == [{
                "path": str(ROOT / f".secrets/peer-couchdb/{org}.env"),
                "required": False,
            }], f"{name}: wrong private CouchDB credential file")
            check_service_network(service, {"fabric": host, org: host})
            check_mounts(service, f"{name}-ledger", "/var/hyperledger/production", {
                "/etc/hyperledger/fabric/core.yaml": f".runtime/network-config/{name}.yaml",
                "/opt/supplyledger/m2-chaincode-disabled":
                    "builders/m2-chaincode-disabled",
                "/run/supply/msp": f".runtime/identities/{org}/{org}-peer0/msp",
                "/run/supply/tls": f".runtime/identities/{org}/{org}-peer0-tls/msp",
                "/run/supply/orderer-tls-root.pem": ".runtime/trust/orderer-tls-ca.pem",
                "/run/supply/peer-tls-root.pem": f".runtime/trust/{org}-tls-ca.pem",
                **{f"/run/supply/client-roots/{member}.pem":
                       f".runtime/trust/{member}-tls-ca.pem"
                   for member in ORG if member != org},
            })
        else:
            org = name.removeprefix("couchdb0-")
            check_service_network(service, {org: f"couchdb0.{org}.supply.test"})
            check_mounts(service, f"{name}-data", "/opt/couchdb/data", {})
            env_files = service.get("env_file", [])
            require(env_files == [{"path": str(ROOT / f".secrets/couchdb/{org}.env"),
                                   "required": False}],
                    f"{name}: wrong per-organization credential file")
            require(not service.get("environment"), f"{name}: credentials embedded in Compose")
    for name, service in services.items():
        require(not service.get("ports"), f"{name}: port published to host")
        require("docker.sock" not in str(service.get("volumes", [])),
                f"{name}: Docker socket mount")
    print("PASS: 3 Orderer, 3 Peer, 3 CouchDB; pinned images, exact DNS/networks, "
          "isolated state and read-only identity mounts, no host ports or docker.sock")


def main():
    check_m2_builder()
    model = compose_model()
    check_networks(model)
    check_volumes(model)
    check_nodes(model)
    print("NOT RUN: live Docker inspect/T-NET-02 and three CCaaS services await M2 #16/M3 #22")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(f"M2 Compose static check FAIL: {error}", file=sys.stderr)
        sys.exit(1)
