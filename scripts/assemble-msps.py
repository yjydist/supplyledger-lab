#!/usr/bin/env python3
"""Build and verify M1 local NodeOUs and public organization MSPs.

This consumes previously issued identities and pinned public CA roots. It never
registers, enrolls, renews, or copies a private key. Output is deployment
specific and remains under ignored .runtime/.
"""

import csv
import io
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".runtime"
IDENTITIES = RUNTIME / "identities"
TRUST = RUNTIME / "trust"
PUBLIC = RUNTIME / "public-msps"
PROBE = RUNTIME / "msp-probe" / "configtx.yaml"
ROOT_MANIFEST = ROOT / "network" / "msp" / "trust-root-fingerprints.csv"
IDENTITY_MANIFEST = ROOT / "evidence" / "m1" / "issue-10-certificates.csv"
ORGS = {"seller": "SellerMSP", "buyer": "BuyerMSP",
        "carrier": "CarrierMSP", "orderer": "OrdererMSP"}
ROLES = ("Client", "Peer", "Admin", "Orderer")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def regular_file(path):
    require(not path.is_symlink() and path.is_file(), f"expected regular file: {path}")
    return path.read_bytes()


def safe_dir(path):
    require(not path.is_symlink() and path.is_dir(), f"expected real directory: {path}")


def fingerprint(path):
    result = subprocess.run(["openssl", "x509", "-in", str(path), "-noout",
                             "-fingerprint", "-sha256"], capture_output=True, text=True)
    require(result.returncode == 0, f"cannot inspect public root: {path}")
    return result.stdout.strip().split("=", 1)[1]


def pin_roots():
    safe_dir(RUNTIME)
    safe_dir(TRUST)
    with ROOT_MANIFEST.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = {f"{org}-{kind}-ca" for org in ORGS for kind in ("enroll", "tls")}
    expected.add("orderer-admin-tls-ca")
    names = [row["ca_name"] for row in rows]
    require(len(rows) == 9 and set(names) == expected and len(set(names)) == 9,
            "root fingerprint manifest must list exactly the nine M1 CAs")
    roots = {}
    for row in rows:
        name = row["ca_name"]
        path = TRUST / f"{name}.pem"
        data = regular_file(path)
        require(data.startswith(b"-----BEGIN CERTIFICATE-----"), f"invalid root PEM: {path}")
        require(fingerprint(path) == row["sha256_fingerprint"],
                f"CA root fingerprint differs from the measured manifest: {name}")
        result = subprocess.run(["openssl", "verify", "-CAfile", str(path), str(path)],
                                capture_output=True, text=True)
        require(result.returncode == 0, f"root self-verification failed: {name}")
        roots[name] = data
    return roots, {row["ca_name"]: row["sha256_fingerprint"] for row in rows}


def inventory(expected_roots):
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "inspect-local-certs.py")],
                            capture_output=True, text=True)
    require(result.returncode == 0, "#10 local certificate audit failed: " + result.stderr.strip())
    current = list(csv.DictReader(io.StringIO(result.stdout)))
    with IDENTITY_MANIFEST.open(newline="") as stream:
        baseline = list(csv.DictReader(stream))
    def index(rows):
        return {(row["organization"], row["identity"]): row for row in rows}
    now, before = index(current), index(baseline)
    require(len(current) == len(baseline) == len(now) == len(before) == 41,
            "expected the 41 measured #10 local identities")
    require(now.keys() == before.keys(), "local identity set changed since #10")
    for identity, row in now.items():
        prior = before[identity]
        for field in ("cert_sha256", "public_key_sha256", "ca_root", "ca_root_sha256",
                      "subject", "supply_user_id", "supply_role"):
            require(row[field] == prior[field], f"unrecorded certificate change: {identity} {field}")
        require(row["ca_root_sha256"] == expected_roots[row["ca_root"]],
                f"identity uses an unpinned root: {identity}")
        require(row["key_mode"] == "0600" and row["identity_dir_mode"] == "0700",
                f"local key/directory permission failed: {identity}")
        require(row["key_owner_uid_gid"] == f"{os.getuid()}:{os.getgid()}",
                f"local signing key not owned by the current host user: {identity}")
    return current


def nodeous(root_relative):
    require(root_relative.startswith("cacerts/") and ".." not in root_relative,
            "NodeOUs root must be an MSP-local cacerts file")
    return ("NodeOUs:\n  Enable: true\n" + "".join(
        f"  {role}OUIdentifier:\n"
        f"    Certificate: {root_relative}\n"
        f"    OrganizationalUnitIdentifier: {role.lower()}\n"
        for role in ROLES)).encode()


def local_configs(rows, roots):
    safe_dir(IDENTITIES)
    expected = {}
    tls_profiles = []
    for row in rows:
        org, identity = row["organization"], row["identity"]
        msp = IDENTITIES / org / identity / "msp"
        safe_dir(msp.parent.parent)
        safe_dir(msp.parent)
        safe_dir(msp)
        cacerts, tlscacerts = msp / "cacerts", msp / "tlscacerts"
        require(not cacerts.is_symlink() and not tlscacerts.is_symlink(),
                f"symlinked MSP root directory: {org}/{identity}")
        ca_files = list(cacerts.iterdir()) if cacerts.is_dir() else []
        tls_files = list(tlscacerts.iterdir()) if tlscacerts.is_dir() else []
        require(not (ca_files and tls_files), f"mixed ECert/TLS roots: {org}/{identity}")
        if ca_files:
            candidates = ca_files
            require(len(candidates) == 1 and candidates[0].suffix == ".pem",
                    f"expected exactly one local ECert root: {org}/{identity}")
            ca_copy = candidates[0]
            require(regular_file(ca_copy) == roots[row["ca_root"]],
                    f"local root bytes differ from pinned root: {org}/{identity}")
            expected[msp / "config.yaml"] = nodeous(f"cacerts/{ca_copy.name}")
        else:
            candidates = tls_files
            require(len(candidates) == 1 and candidates[0].suffix == ".pem",
                    f"expected exactly one TLS-profile root: {org}/{identity}")
            require(regular_file(candidates[0]) == roots[row["ca_root"]],
                    f"TLS-profile root bytes differ: {org}/{identity}")
            require(not (msp / "config.yaml").exists(),
                    f"TLS transport identity unexpectedly has NodeOUs: {org}/{identity}")
            tls_profiles.append((org, identity))
    require(len(expected) == 27 and len(tls_profiles) == 14,
            "expected 27 non-TLS local MSPs and 14 separate TLS profiles")
    return expected


def public_files(org, roots):
    enroll = f"{org}-enroll-ca"
    tls = f"{org}-tls-ca"
    return {
        f"cacerts/{enroll}.pem": roots[enroll],
        f"tlscacerts/{tls}.pem": roots[tls],
        "config.yaml": nodeous(f"cacerts/{enroll}.pem"),
    }


def file_mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def check_file(path, expected, mode):
    require(regular_file(path) == expected, f"file bytes differ: {path}")
    require(file_mode(path) == mode, f"unexpected file mode: {path}")
    require((path.stat().st_uid, path.stat().st_gid) == (os.getuid(), os.getgid()),
            f"unexpected file owner/group: {path}")


def check_public_dir(msp, expected):
    safe_dir(msp)
    actual = set()
    for path in msp.rglob("*"):
        require(not path.is_symlink(), f"symlink forbidden in public MSP: {path}")
        actual.add(str(path.relative_to(msp)))
    allowed = set(expected) | {"cacerts", "tlscacerts"}
    require(actual == allowed, f"public MSP file allowlist violation: {msp}; "
            f"missing={sorted(allowed-actual)} extra={sorted(actual-allowed)}")
    for subdir in ("cacerts", "tlscacerts"):
        safe_dir(msp / subdir)
        require(file_mode(msp / subdir) == 0o755, f"public directory not 0755: {msp/subdir}")
    require(file_mode(msp) == 0o755, f"public MSP directory not 0755: {msp}")
    for relative, data in expected.items():
        path = msp / relative
        check_file(path, data, 0o644)
        require(b"PRIVATE KEY" not in data, f"secret marker in public MSP: {path}")
        if relative.endswith(".pem"):
            require(data.startswith(b"-----BEGIN CERTIFICATE-----"),
                    f"expected public certificate: {path}")
        else:
            require(b"BEGIN CERTIFICATE" not in data,
                    f"unexpected certificate in NodeOUs config: {path}")


def org_probe_config():
    # This org-only fixture lets configtxgen parse MSPs without a channel profile.
    # OrdererEndpoints selects the orderer organization parser in Fabric 3.1.5.
    return ("Capabilities:\n  Channel:\n    V3_0: true\nOrganizations:\n" + "".join(
        f"  - Name: {mspid}\n    ID: {mspid}\n"
        f"    MSPDir: /work/public-msps/{mspid}/msp\n"
        "    Policies:\n"
        f"      Readers: {{Type: Signature, Rule: \"OR('{mspid}.admin', '{mspid}.peer', '{mspid}.client')\"}}\n"
        f"      Writers: {{Type: Signature, Rule: \"OR('{mspid}.admin', '{mspid}.client')\"}}\n"
        f"      Admins: {{Type: Signature, Rule: \"OR('{mspid}.admin')\"}}\n"
        f"      Endorsement: {{Type: Signature, Rule: \"OR('{mspid}.peer')\"}}\n"
        + ("    OrdererEndpoints:\n"
           + "".join(f"      - orderer{i}.orderer.supply.test:7050\n" for i in range(3))
           if mspid == "OrdererMSP" else "")
        for mspid in ORGS.values())).encode()


def preflight(existing, public_expected, probe):
    for path, data in existing.items():
        if path.exists() or path.is_symlink():
            check_file(path, data, 0o600)
    if PUBLIC.exists() or PUBLIC.is_symlink():
        safe_dir(PUBLIC)
        children = {path.name for path in PUBLIC.iterdir()}
        require(children <= set(ORGS.values()), "unexpected public MSP directory")
        for mspid, expected in public_expected.items():
            if mspid in children:
                orgdir = PUBLIC / mspid
                safe_dir(orgdir)
                require({path.name for path in orgdir.iterdir()} == {"msp"},
                        f"unexpected public organization files: {orgdir}")
                check_public_dir(orgdir / "msp", expected)
    if PROBE.exists() or PROBE.is_symlink():
        check_file(PROBE, probe, 0o644)


def write_exclusive(path, data, mode):
    with path.open("xb") as stream:
        stream.write(data)
    path.chmod(mode)


def build(local_expected, public_expected, probe):
    preflight(local_expected, public_expected, probe)
    for path, data in local_expected.items():
        if not path.exists():
            write_exclusive(path, data, 0o600)
    PUBLIC.mkdir(mode=0o755, exist_ok=True)
    PUBLIC.chmod(0o755)
    for mspid, expected in public_expected.items():
        orgdir = PUBLIC / mspid
        if orgdir.exists():
            continue
        orgdir.mkdir(mode=0o755)
        orgdir.chmod(0o755)
        with tempfile.TemporaryDirectory(prefix=".msp-stage-", dir=PUBLIC) as temporary:
            staging = Path(temporary) / "msp"
            staging.mkdir(mode=0o755)
            staging.chmod(0o755)
            for subdir in ("cacerts", "tlscacerts"):
                (staging / subdir).mkdir(mode=0o755)
                (staging / subdir).chmod(0o755)
            for relative, data in expected.items():
                write_exclusive(staging / relative, data, 0o644)
            os.rename(staging, orgdir / "msp")
    PROBE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    safe_dir(PROBE.parent)
    if not PROBE.exists():
        write_exclusive(PROBE, probe, 0o644)


def verify(local_expected, public_expected, probe):
    safe_dir(PUBLIC)
    require(file_mode(PUBLIC) == 0o755, f"public MSP root directory not 0755: {PUBLIC}")
    require({path.name for path in PUBLIC.iterdir()} == set(ORGS.values()),
            "public MSP organization set differs from the four founding orgs")
    for path, data in local_expected.items():
        check_file(path, data, 0o600)
    for mspid, expected in public_expected.items():
        orgdir = PUBLIC / mspid
        safe_dir(orgdir)
        require(file_mode(orgdir) == 0o755, f"public organization directory not 0755: {orgdir}")
        require({path.name for path in orgdir.iterdir()} == {"msp"},
                f"unexpected public organization files: {orgdir}")
        check_public_dir(orgdir / "msp", expected)
    check_file(PROBE, probe, 0o644)
    print("PASS: 27 local NodeOUs configs; 14 separate TLS profiles; "
          "four public MSPs contain exactly Enrollment root, ordinary TLS root, NodeOUs")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"build", "verify"}:
        raise ValueError("usage: python3 scripts/assemble-msps.py build|verify")
    os.umask(0o077)
    roots, root_fingerprints = pin_roots()
    rows = inventory(root_fingerprints)
    local_expected = local_configs(rows, roots)
    public_expected = {mspid: public_files(org, roots) for org, mspid in ORGS.items()}
    require(all(roots["orderer-admin-tls-ca"] not in files.values()
                for files in public_expected.values()),
            "dedicated Orderer admin-client TLS root leaked into public MSP")
    probe = org_probe_config()
    if sys.argv[1] == "build":
        build(local_expected, public_expected, probe)
    verify(local_expected, public_expected, probe)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"MSP assembly FAIL: {error}", file=sys.stderr)
        sys.exit(1)
