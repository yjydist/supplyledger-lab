#!/usr/bin/env python3
"""Offline mount controls for the Seller runtime checker; no Docker or secrets."""

import copy
import importlib.util
from pathlib import Path


source = Path(__file__).with_name("verify-m2-seller-couchdb-runtime.py")
module_spec = importlib.util.spec_from_file_location("seller_runtime", source)
module = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(module)
root = Path("/example/supplyledger-lab")


def fixture(component: str) -> dict:
    mounts = []
    for destination, (kind, expected_source, writable) in module.expected_mounts(root, component).items():
        mount = {"Type": "bind" if kind == "bind" else "volume",
                 "Destination": destination, "RW": writable}
        if kind == "bind":
            mount["Source"] = expected_source
        else:
            mount["Name"] = expected_source or "a" * 64
        mounts.append(mount)
    return {"Mounts": mounts}


def rejects(record: dict, component: str) -> None:
    try:
        module.check_mounts(record, root, component)
    except ValueError:
        return
    raise AssertionError("unsafe mount mutation was accepted")


db = fixture("couchdb")
peer = fixture("peer")
module.check_mounts(db, root, "couchdb")
module.check_mounts(peer, root, "peer")
desktop_peer = copy.deepcopy(peer)
next(m for m in desktop_peer["Mounts"] if m["Type"] == "bind")["Source"] = (
    "/host_mnt" + next(m for m in peer["Mounts"] if m["Type"] == "bind")["Source"])
module.check_mounts(desktop_peer, root, "peer")

extra_private = copy.deepcopy(peer)
extra_private["Mounts"].append({"Type": "bind", "Destination": "/run/other-org/msp",
                                "Source": "/example/supplyledger-lab/.runtime/identities/buyer/admin/msp",
                                "RW": False})
rejects(extra_private, "peer")
extra_db = copy.deepcopy(db)
extra_db["Mounts"].append({"Type": "bind", "Destination": "/run/private",
                            "Source": "/example/supplyledger-lab/.runtime/identities/carrier/admin/msp",
                            "RW": False})
rejects(extra_db, "couchdb")
wrong_source = copy.deepcopy(peer)
next(m for m in wrong_source["Mounts"] if m["Destination"] == "/run/supply/msp")["Source"] = (
    "/example/supplyledger-lab/.runtime/identities/buyer/admin/msp")
rejects(wrong_source, "peer")
writable_key = copy.deepcopy(peer)
next(m for m in writable_key["Mounts"] if m["Destination"] == "/run/supply/msp")["RW"] = True
rejects(writable_key, "peer")
wrong_volume = copy.deepcopy(db)
wrong_volume["Mounts"][0]["Name"] = "another-volume"
rejects(wrong_volume, "couchdb")
duplicate = copy.deepcopy(peer)
duplicate["Mounts"].append(copy.deepcopy(duplicate["Mounts"][0]))
rejects(duplicate, "peer")
wrong_anonymous = copy.deepcopy(peer)
next(m for m in wrong_anonymous["Mounts"] if m["Destination"] == "/var/hyperledger")[
    "Name"] = "supplyledger_peer0_buyer_ledger"
rejects(wrong_anonymous, "peer")
print("PASS: expected mounts and Docker Desktop sources; seven unsafe mount mutations rejected")
