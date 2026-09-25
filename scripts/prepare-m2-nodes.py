#!/usr/bin/env python3
"""Prepare or verify M2 node inputs without altering M1 identities or starting Fabric."""

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ORGS = ("seller", "buyer", "carrier")
MSPIDS = {"seller": "SellerMSP", "buyer": "BuyerMSP", "carrier": "CarrierMSP"}
ORDERERS = tuple(f"orderer{i}" for i in range(3))
PASSWORD_RE = re.compile(r"[A-Za-z0-9_-]{40,}")
KEY_RE = re.compile(r"[0-9a-f]{64}_sk")
CERT_INVENTORY = ROOT / "evidence/m1/issue-10-certificates.csv"
PEER_BCCSP = {
    ("peer", "BCCSP", "Default"): "SW",
    ("peer", "BCCSP", "SW", "Hash"): "SHA2",
    ("peer", "BCCSP", "SW", "Security"): "256",
    ("peer", "BCCSP", "SW", "FileKeyStore", "KeyStore"):
        "/run/supply/msp/keystore",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def safe_directory(path, create=False):
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(path.is_dir() and not path.is_symlink(), f"unsafe or missing directory: {path}")
    require(mode(path) == 0o700, f"directory must be 0700: {path}")


def safe_file(path, expected_mode):
    require(path.is_file() and not path.is_symlink(), f"unsafe or missing file: {path}")
    require(mode(path) == expected_mode, f"file must be {expected_mode:04o}: {path}")


def native(*args):
    result = subprocess.run(args, capture_output=True, check=False)
    require(result.returncode == 0, f"openssl failed while checking {args[-1]}")
    return result.stdout


def inventory():
    with CERT_INVENTORY.open(newline="") as file:
        rows = list(csv.DictReader(file))
    lookup = {(row["organization"], row["identity"]): row for row in rows}
    require(len(rows) == 41 and len(lookup) == 41, "unexpected M1 certificate inventory")
    return lookup


def checked_identity(m1_runtime, org, identity, rows):
    msp = m1_runtime / "identities" / org / identity / "msp"
    require(msp.is_dir() and not msp.is_symlink(), f"missing M1 MSP: {org}/{identity}")
    cert = msp / "signcerts/cert.pem"
    require(cert.is_file() and not cert.is_symlink(), f"missing M1 certificate: {org}/{identity}")
    keystore = msp / "keystore"
    require(keystore.is_dir() and not keystore.is_symlink(), f"missing M1 keystore: {org}/{identity}")
    keys = list(keystore.iterdir())
    require(len(keys) == 1 and KEY_RE.fullmatch(keys[0].name),
            f"expected exactly one unmodified M1 signing key: {org}/{identity}")
    key = keys[0]
    safe_file(key, 0o600)
    row = rows.get((org, identity))
    require(row is not None, f"identity absent from M1 inventory: {org}/{identity}")
    cert_der = native("openssl", "x509", "-in", str(cert), "-outform", "DER")
    actual_fingerprint = hashlib.sha256(cert_der).hexdigest()
    expected_fingerprint = row["cert_sha256"].replace(":", "").lower()
    require(actual_fingerprint == expected_fingerprint,
            f"M1 certificate differs from pinned inventory: {org}/{identity}")
    public_pem = native("openssl", "x509", "-in", str(cert), "-pubkey", "-noout")
    public_der = subprocess.run(("openssl", "pkey", "-pubin", "-outform", "DER"),
                                input=public_pem, capture_output=True, check=False)
    require(public_der.returncode == 0, f"invalid M1 certificate key: {org}/{identity}")
    key_der = native("openssl", "pkey", "-in", str(key), "-pubout", "-outform", "DER")
    require(public_der.stdout == key_der, f"M1 cert/key mismatch: {org}/{identity}")
    return key.name


def key_names(m1_runtime):
    rows = inventory()
    found = {}
    for name in ORDERERS:
        checked_identity(m1_runtime, "orderer", name, rows)
        found[(name, "tls")] = checked_identity(m1_runtime, "orderer", f"{name}-tls", rows)
        found[(name, "admin")] = checked_identity(
            m1_runtime, "orderer", f"{name}-admin-server-tls", rows)
    for org in ORGS:
        checked_identity(m1_runtime, org, f"{org}-peer0", rows)
        found[(f"peer0-{org}", "tls")] = checked_identity(
            m1_runtime, org, f"{org}-peer0-tls", rows)
    return found


def read_env(path, expected_keys):
    safe_file(path, 0o600)
    values = {}
    for line in path.read_text().splitlines():
        require("=" in line and not line.startswith("#"), f"invalid private env line: {path}")
        key, value = line.split("=", 1)
        require(key in expected_keys and key not in values, f"unexpected private env key: {path}")
        require(value and "\n" not in value, f"empty private env value: {path}")
        values[key] = value
    require(set(values) == set(expected_keys), f"incomplete private env file: {path}")
    return values


def write_new(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def require_ignored_output(path):
    """Refuse deployment output inside this checkout unless Git ignores it."""
    try:
        path.absolute().relative_to(ROOT)
    except ValueError:
        return
    result = subprocess.run(("git", "check-ignore", "--no-index", "--quiet", str(path)),
                            cwd=ROOT, capture_output=True, check=False)
    require(result.returncode == 0, f"deployment output is not Git-ignored: {path}")


def credential_files(secrets_dir, prepare):
    couchdb_dir = secrets_dir / "couchdb"
    peer_dir = secrets_dir / "peer-couchdb"
    safe_directory(secrets_dir, create=prepare)
    safe_directory(couchdb_dir, create=prepare)
    safe_directory(peer_dir, create=prepare)
    passwords = []
    for org in ORGS:
        couchdb_file = couchdb_dir / f"{org}.env"
        peer_file = peer_dir / f"{org}.env"
        require_ignored_output(couchdb_file)
        require_ignored_output(peer_file)
        username = f"supply_{org}"
        if couchdb_file.exists() or couchdb_file.is_symlink():
            couchdb = read_env(couchdb_file, ("COUCHDB_USER", "COUCHDB_PASSWORD"))
        else:
            require(prepare, f"missing private CouchDB credentials: {org}")
            password = secrets.token_urlsafe(32)
            couchdb = {"COUCHDB_USER": username, "COUCHDB_PASSWORD": password}
            write_new(couchdb_file,
                      f"COUCHDB_USER={username}\nCOUCHDB_PASSWORD={password}\n".encode())
        require(couchdb["COUCHDB_USER"] == username
                and PASSWORD_RE.fullmatch(couchdb["COUCHDB_PASSWORD"]),
                f"invalid private CouchDB credentials: {org}")
        passwords.append(couchdb["COUCHDB_PASSWORD"])
        if peer_file.exists() or peer_file.is_symlink():
            peer = read_env(peer_file, (
                "CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME",
                "CORE_LEDGER_STATE_COUCHDBCONFIG_PASSWORD",
            ))
        else:
            require(prepare, f"missing private Peer CouchDB credentials: {org}")
            write_new(peer_file, (
                f"CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME={username}\n"
                f"CORE_LEDGER_STATE_COUCHDBCONFIG_PASSWORD={couchdb['COUCHDB_PASSWORD']}\n"
            ).encode())
            peer = read_env(peer_file, (
                "CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME",
                "CORE_LEDGER_STATE_COUCHDBCONFIG_PASSWORD",
            ))
        require(peer["CORE_LEDGER_STATE_COUCHDBCONFIG_USERNAME"] == username
                and peer["CORE_LEDGER_STATE_COUCHDBCONFIG_PASSWORD"]
                == couchdb["COUCHDB_PASSWORD"],
                f"Peer/CouchDB private credentials differ: {org}")
    require(len(set(passwords)) == len(ORGS), "CouchDB passwords are not distinct")
    print("PASS: three ignored, distinct CouchDB secrets match their own Peer handoffs")


def rendered_config(name, keys):
    template = ROOT / "network/config" / f"{name}.yaml"
    require(template.is_file() and not template.is_symlink(), f"missing node template: {name}")
    if name in ORDERERS:
        source_scalars, _ = yaml_fields(template)
        require(source_scalars.get(("ChannelParticipation", "MaxRequestBodySize")) == "1 MB",
                f"{name}: source MaxRequestBodySize must be 1 MB")
    else:
        source_scalars, _ = yaml_fields(template)
        for field, value in PEER_BCCSP.items():
            require(source_scalars.get(field) == value,
                    f"{name}: wrong source node field {'.'.join(field)}")
    data = template.read_text()
    replacements = (
        {"__ORDERER_TLS_KEY__": keys[(name, "tls")],
         "__ORDERER_ADMIN_TLS_KEY__": keys[(name, "admin")]}
        if name in ORDERERS else
        {"__PEER_TLS_KEY__": keys[(name, "tls")]}
    )
    counts = (
        {"__ORDERER_TLS_KEY__": 2, "__ORDERER_ADMIN_TLS_KEY__": 2}
        if name in ORDERERS else {"__PEER_TLS_KEY__": 3}
    )
    for marker, key_name in replacements.items():
        require(data.count(marker) == counts[marker],
                f"unexpected key-path marker count in {name}")
        data = data.replace(marker, key_name)
    require("__" not in data, f"unexpanded marker in {name}")
    return data.encode()


def config_files(output_runtime, keys, prepare):
    safe_directory(output_runtime, create=prepare)
    target_dir = output_runtime / "network-config"
    safe_directory(target_dir, create=prepare)
    for name in ORDERERS + tuple(f"peer0-{org}" for org in ORGS):
        target = target_dir / f"{name}.yaml"
        require_ignored_output(target)
        expected = rendered_config(name, keys)
        if target.exists() or target.is_symlink():
            safe_file(target, 0o600)
            require(target.read_bytes() == expected,
                    f"rendered node config changed; review before replacement: {name}")
        else:
            require(prepare, f"missing rendered node config: {name}")
            write_new(target, expected)
    require({file.name for file in target_dir.iterdir()}
            == {f"{name}.yaml" for name in ORDERERS
                + tuple(f"peer0-{org}" for org in ORGS)},
            "unexpected file in ignored M2 node config directory")
    print("PASS: six ignored configs select measured M1 certs and exact private key paths")


def yaml_fields(path):
    """Read the simple mapping/list subset used by our generated node YAMLs."""
    scalars, lists, parents = {}, {}, []
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        require("\t" not in line, f"tab in generated config: {path}")
        indent = len(line) - len(line.lstrip(" "))
        require(indent % 2 == 0, f"odd YAML indentation: {path}")
        while parents and parents[-1][0] >= indent:
            parents.pop()
        item = line.strip()
        if item.startswith("- "):
            require(parents, f"orphan YAML list item: {path}")
            key = tuple(name for _, name in parents)
            lists.setdefault(key, []).append(item[2:])
            continue
        require(":" in item, f"unexpected YAML source line: {path}")
        name, value = item.split(":", 1)
        require(re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", name) is not None,
                f"unexpected YAML key: {path}")
        key = tuple(name for _, name in parents) + (name,)
        require(key not in scalars, f"duplicate YAML key: {path}")
        scalars[key] = value.strip()
        parents.append((indent, name))
    return scalars, lists


def check_node_fields(output_runtime, keys):
    for name in ORDERERS:
        scalars, lists = yaml_fields(output_runtime / "network-config" / f"{name}.yaml")
        tls_cert = "/run/supply/tls/signcerts/cert.pem"
        tls_key = f"/run/supply/tls/keystore/{keys[(name, 'tls')]}"
        admin_cert = "/run/supply/admin-server-tls/signcerts/cert.pem"
        admin_key = f"/run/supply/admin-server-tls/keystore/{keys[(name, 'admin')]}"
        expected = {
            ("General", "ListenAddress"): "0.0.0.0",
            ("General", "ListenPort"): "7050",
            ("General", "LocalMSPID"): "OrdererMSP",
            ("General", "LocalMSPDir"): "/run/supply/msp",
            ("General", "TLS", "Enabled"): "true",
            ("General", "TLS", "ClientAuthRequired"): "true",
            ("General", "TLS", "Certificate"): tls_cert,
            ("General", "TLS", "PrivateKey"): tls_key,
            ("General", "Cluster", "ClientCertificate"): tls_cert,
            ("General", "Cluster", "ClientPrivateKey"): tls_key,
            ("FileLedger", "Location"): "/var/hyperledger/production/orderer",
            ("Operations", "ListenAddress"): "0.0.0.0:9444",
            ("Operations", "TLS", "Enabled"): "true",
            ("Operations", "TLS", "ClientAuthRequired"): "true",
            ("Operations", "TLS", "Certificate"): admin_cert,
            ("Operations", "TLS", "PrivateKey"): admin_key,
            ("Metrics", "Provider"): "prometheus",
            ("Admin", "ListenAddress"): "0.0.0.0:9443",
            ("Admin", "TLS", "Enabled"): "true",
            ("Admin", "TLS", "ClientAuthRequired"): "true",
            ("Admin", "TLS", "Certificate"): admin_cert,
            ("Admin", "TLS", "PrivateKey"): admin_key,
            ("ChannelParticipation", "Enabled"): "true",
            ("ChannelParticipation", "MaxRequestBodySize"): "1 MB",
            ("Consensus", "WALDir"): "/var/hyperledger/production/orderer/etcdraft/wal",
            ("Consensus", "SnapDir"): "/var/hyperledger/production/orderer/etcdraft/snapshot",
        }
        for field, value in expected.items():
            require(scalars.get(field) == value,
                    f"{name}: wrong node field {'.'.join(field)}")
        require(lists.get(("General", "TLS", "RootCAs"))
                == ["/run/supply/client-roots/orderer.pem"],
                f"{name}: wrong Raft outbound TLS root")
        require(lists.get(("General", "TLS", "ClientRootCAs"))
                == [f"/run/supply/client-roots/{org}.pem"
                    for org in ("orderer",) + ORGS],
                f"{name}: wrong transaction/Raft client TLS roots")
        for endpoint in ("Admin", "Operations"):
            require(lists.get((endpoint, "TLS", "ClientRootCAs"))
                    == ["/run/supply/admin-client-root.pem"],
                    f"{name}: {endpoint} trusts a root other than dedicated admin-client CA")
        separate_listener = (
            "ListenAddress", "ListenPort", "ServerCertificate", "ServerPrivateKey"
        )
        require(all(("General", "Cluster", field) not in scalars
                    for field in separate_listener),
                f"{name}: unexpected or incomplete separate Raft listener")

    for org in ORGS:
        name = f"peer0-{org}"
        scalars, lists = yaml_fields(output_runtime / "network-config" / f"{name}.yaml")
        host = f"peer0.{org}.supply.test"
        tls_cert = "/run/supply/tls/signcerts/cert.pem"
        tls_key = f"/run/supply/tls/keystore/{keys[(name, 'tls')]}"
        expected = {
            ("peer", "id"): host,
            ("peer", "listenAddress"): "0.0.0.0:7051",
            ("peer", "address"): f"{host}:7051",
            ("peer", "mspConfigPath"): "/run/supply/msp",
            ("peer", "localMspId"): MSPIDS[org],
            ("peer", "fileSystemPath"): "/var/hyperledger/production",
            ("peer", "gateway", "enabled"): "true",
            ("peer", "gossip", "externalEndpoint"): f"{host}:7051",
            ("peer", "gossip", "bootstrap"): '""',
            ("peer", "gossip", "orgLeader"): "true",
            ("peer", "gossip", "useLeaderElection"): "false",
            ("peer", "gossip", "state", "enabled"): "false",
            ("peer", "tls", "enabled"): "true",
            ("peer", "tls", "clientAuthRequired"): "false",
            ("peer", "tls", "cert", "file"): tls_cert,
            ("peer", "tls", "key", "file"): tls_key,
            ("peer", "tls", "rootcert", "file"):
                "/run/supply/peer-tls-root.pem",
            ("peer", "tls", "clientCert", "file"): tls_cert,
            ("peer", "tls", "clientKey", "file"): tls_key,
            ("deliveryclient", "blockGossipEnabled"): "false",
            ("ledger", "state", "stateDatabase"): "CouchDB",
            ("ledger", "state", "couchDBConfig", "couchDBAddress"):
                f"couchdb0.{org}.supply.test:5984",
            ("ledger", "snapshots", "rootDir"): "/var/hyperledger/production/snapshots",
            ("operations", "listenAddress"): "0.0.0.0:9444",
            ("operations", "tls", "enabled"): "true",
            ("operations", "tls", "clientAuthRequired"): "true",
            ("operations", "tls", "cert", "file"): tls_cert,
            ("operations", "tls", "key", "file"): tls_key,
            ("metrics", "provider"): "prometheus",
        }
        expected.update(PEER_BCCSP)
        for field, value in expected.items():
            require(scalars.get(field) == value,
                    f"{name}: wrong node field {'.'.join(field)}")
        require(("ledger", "state", "couchDBConfig", "username") not in scalars
                and ("ledger", "state", "couchDBConfig", "password") not in scalars,
                f"{name}: CouchDB credentials embedded in YAML")
        require(lists.get(("operations", "tls", "clientRootCAs", "files"))
                == ["/run/supply/peer-tls-root.pem"],
                f"{name}: wrong operations client TLS root")
    print("PASS: six node YAMLs enforce MSP, TLS, CouchDB, gossip, Gateway and volume paths")


def check_initial_block(inspect_block, m1_runtime, output_runtime, keys):
    block = json.loads(inspect_block.read_text())
    require(block["header"]["number"] == "0"
            and block["header"]["previous_hash"] == "",
            "expected initial CONFIG block 0")
    envelopes = block["data"]["data"]
    require(len(envelopes) == 1, "expected one CONFIG envelope")
    payload = envelopes[0]["payload"]
    channel_header = payload["header"]["channel_header"]
    require(channel_header["channel_id"] == "supplychannel"
            and channel_header["type"] == 1,
            "wrong channel ID or envelope type")
    group = payload["data"]["config"]["channel_group"]
    consenters = group["groups"]["Orderer"]["values"]["ConsensusType"]["value"][
        "metadata"]["consenters"]
    require(len(consenters) == 3, "initial block does not have three Raft consenters")
    for name, consenter in zip(ORDERERS, consenters):
        host = f"{name}.orderer.supply.test"
        require(consenter["host"] == host and consenter["port"] == 7050,
                f"{name}: configured Raft endpoint differs from initial block")
        cert_path = (m1_runtime / "identities/orderer" / f"{name}-tls"
                     / "msp/signcerts/cert.pem")
        cert = cert_path.read_bytes()
        require(base64.b64decode(consenter["client_tls_cert"], validate=True) == cert
                and base64.b64decode(consenter["server_tls_cert"], validate=True) == cert,
                f"{name}: effective Raft client/server cert differs from initial block")
        rendered = output_runtime / "network-config" / f"{name}.yaml"
        scalars, lists = yaml_fields(rendered)
        tls_cert = "/run/supply/tls/signcerts/cert.pem"
        tls_key = f"/run/supply/tls/keystore/{keys[(name, 'tls')]}"
        admin_cert = "/run/supply/admin-server-tls/signcerts/cert.pem"
        admin_key = f"/run/supply/admin-server-tls/keystore/{keys[(name, 'admin')]}"
        expected = {
            ("General", "ListenPort"): "7050",
            ("General", "TLS", "Enabled"): "true",
            ("General", "TLS", "ClientAuthRequired"): "true",
            ("General", "TLS", "Certificate"): tls_cert,
            ("General", "TLS", "PrivateKey"): tls_key,
            ("General", "Cluster", "ClientCertificate"): tls_cert,
            ("General", "Cluster", "ClientPrivateKey"): tls_key,
            ("Admin", "TLS", "Enabled"): "true",
            ("Admin", "TLS", "ClientAuthRequired"): "true",
            ("Admin", "TLS", "Certificate"): admin_cert,
            ("Admin", "TLS", "PrivateKey"): admin_key,
        }
        for field, value in expected.items():
            require(scalars.get(field) == value, f"{name}: wrong effective node field {'.'.join(field)}")
        require(all(("General", "Cluster", field) not in scalars
                    for field in ("ListenAddress", "ListenPort",
                                  "ServerCertificate", "ServerPrivateKey")),
                f"{name}: separate cluster listener would change effective server TLS cert")
        require(lists.get(("Admin", "TLS", "ClientRootCAs"))
                == ["/run/supply/admin-client-root.pem"],
                f"{name}: admin trusts a root other than dedicated admin-client CA")
    print("PASS: three effective Raft TLS cert paths and PEM bytes match decoded block 0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("--m1-runtime", type=Path, default=ROOT / ".runtime")
    parser.add_argument("--output-runtime", type=Path, default=ROOT / ".runtime")
    parser.add_argument("--secrets-dir", type=Path, default=ROOT / ".secrets")
    parser.add_argument("--inspect-block", type=Path,
                        help="optional native #17 decoded initial block JSON")
    args = parser.parse_args()
    m1_runtime = args.m1_runtime.resolve()
    output_runtime = args.output_runtime.absolute()
    secrets_dir = args.secrets_dir.absolute()
    require(m1_runtime.is_dir(), "M1 runtime is missing")
    for org in ORGS:
        require_ignored_output(secrets_dir / "couchdb" / f"{org}.env")
        require_ignored_output(secrets_dir / "peer-couchdb" / f"{org}.env")
    for name in ORDERERS + tuple(f"peer0-{org}" for org in ORGS):
        require_ignored_output(output_runtime / "network-config" / f"{name}.yaml")
    keys = key_names(m1_runtime)
    credential_files(secrets_dir, args.action == "prepare")
    config_files(output_runtime, keys, args.action == "prepare")
    check_node_fields(output_runtime, keys)
    if args.inspect_block:
        check_initial_block(args.inspect_block, m1_runtime, output_runtime, keys)
    else:
        print("NOT RUN: #17 initial-block-to-node certificate byte comparison")
    print("NOT RUN: this preflight did not start or inspect live Orderer, Peer, CouchDB, channel or TLS endpoints")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"M2 node preflight FAIL: {error}", file=sys.stderr)
        sys.exit(1)
