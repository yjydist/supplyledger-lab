#!/usr/bin/env python3
"""Inspect public local-MSP certificates; emit no private material.

This is a read-only post-enrollment audit. It does not register or enroll an
identity. The inventory is an observation of the local files, not proof of a
channel MSP or a live Fabric authorization decision.
"""

import csv
import hashlib
import json
import re
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
IDENTITIES = ROOT / ".runtime" / "identities"
TRUST = ROOT / ".runtime" / "trust"
FIELDS = (
    "organization", "identity", "purpose", "issued_in", "ca_root",
    "ca_root_sha256", "issuer", "subject", "serial_hex", "aki_hex",
    "ski_hex", "san", "key_usage", "extended_key_usage", "not_before_utc",
    "not_after_utc", "cert_sha256", "public_key_sha256", "supply_user_id", "supply_role",
    "cert_path", "cert_owner_uid_gid", "cert_mode", "key_owner_uid_gid",
    "key_mode", "identity_dir_mode", "key_matches_cert", "local_root_copy",
    "chain_verifies",
)
BUSINESS_ATTRS = {
    ("seller", "operator1"): {"supply.userId": "seller.operator1", "supply.role": "operator"},
    ("seller", "seller-quality1"): {"supply.userId": "seller.quality1", "supply.role": "quality"},
    ("buyer", "buyer-operator1"): {"supply.userId": "buyer.operator1", "supply.role": "operator"},
    ("buyer", "buyer-quality1"): {"supply.userId": "buyer.quality1", "supply.role": "quality"},
    ("carrier", "carrier-operator1"): {"supply.userId": "carrier.operator1", "supply.role": "operator"},
}
EXPECTED_OU = {
    "seller": {
        "tls-registrar": "client", "enroll-server-tls": "client",
        "enroll-registrar": "client", "operator1": "client",
        "seller-quality1": "client", "seller-client1": "client",
        "seller-admin1": "admin", "seller-peer0": "peer",
        "seller-peer0-tls": "peer",
    },
    "buyer": {
        "tls-registrar": "client", "enroll-server-tls": "client",
        "enroll-registrar": "client", "buyer-operator1": "client",
        "buyer-quality1": "client", "buyer-client1": "client",
        "buyer-admin1": "admin", "buyer-peer0": "peer",
        "buyer-peer0-tls": "peer",
    },
    "carrier": {
        "tls-registrar": "client", "enroll-server-tls": "client",
        "enroll-registrar": "client", "carrier-operator1": "client",
        "carrier-client1": "client", "carrier-admin1": "admin",
        "carrier-peer0": "peer", "carrier-peer0-tls": "peer",
    },
    "orderer": {
        "tls-registrar": "client", "enroll-server-tls": "client",
        "enroll-registrar": "client", "admin-tls-registrar": "client",
        "orderer-admin1": "admin", "orderer0": "orderer",
        "orderer1": "orderer", "orderer2": "orderer",
        "orderer0-tls": "orderer", "orderer1-tls": "orderer",
        "orderer2-tls": "orderer", "orderer0-admin-server-tls": "orderer",
        "orderer1-admin-server-tls": "orderer",
        "orderer2-admin-server-tls": "orderer",
        "osnadmin-client1-tls": "client",
    },
}


def run(*args, input_bytes=None):
    result = subprocess.run(args, input=input_bytes, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(map(str, args))}")
    return result.stdout


def cert_lines(path):
    return run("openssl", "x509", "-in", str(path), "-noout", "-subject",
               "-issuer", "-nameopt", "RFC2253", "-serial", "-startdate",
               "-enddate", "-dateopt", "iso_8601", "-fingerprint", "-sha256").decode().splitlines()


def value(lines, prefix):
    matches = [line[len(prefix):].strip() for line in lines if line.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"expected one {prefix!r} in certificate output")
    return matches[0]


def extension(text, label):
    match = re.search(r"^\s+X509v3 " + re.escape(label) +
                      r"[^\n]*\n\s+([^\n]+)", text, re.MULTILINE)
    return match.group(1).strip() if match else "ABSENT"


def owner(path):
    details = path.stat()
    return f"{details.st_uid}:{details.st_gid}", f"{stat.S_IMODE(details.st_mode):04o}"


def purpose(identity):
    if identity in {"tls-registrar", "enroll-registrar", "admin-tls-registrar"}:
        return "CA registrar"
    if identity == "enroll-server-tls":
        return "Enrollment CA HTTPS server"
    if identity.endswith("-admin-server-tls"):
        return "Orderer admin HTTPS server"
    if identity == "osnadmin-client1-tls":
        return "Orderer admin mTLS client"
    if identity.endswith("-peer0-tls"):
        return "Peer TLS node"
    if re.fullmatch(r"orderer[0-2]-tls", identity):
        return "Orderer TLS node"
    if "operator" in identity or "quality" in identity:
        return "business user ECert"
    if identity.endswith("-client1"):
        return "attribute-free client ECert"
    if identity.endswith("-admin1"):
        return "organization admin ECert"
    if identity.endswith("-peer0"):
        return "Peer node ECert"
    if re.fullmatch(r"orderer[0-2]", identity):
        return "Orderer node ECert"
    raise ValueError(f"unclassified identity: {identity}")


def inspect(path, roots):
    identity_dir = path.parents[2]
    org, identity = identity_dir.parent.name, identity_dir.name
    expected_ou = EXPECTED_OU.get(org, {}).get(identity)
    if expected_ou is None:
        raise ValueError(f"unexpected identity: {org}/{identity}")
    if path.is_symlink() or path.parent.is_symlink() or identity_dir.is_symlink():
        raise ValueError(f"symlinked identity path for {org}/{identity}")
    lines = cert_lines(path)
    issuer = value(lines, "issuer=")
    root_matches = [(name, pem, fingerprint) for name, pem, subject, fingerprint in roots
                    if subject == issuer]
    if len(root_matches) != 1:
        raise ValueError(f"ambiguous or unknown issuer for {org}/{identity}")
    root_name, root_pem, root_fingerprint = root_matches[0]
    if identity in {"admin-tls-registrar", "osnadmin-client1-tls"}:
        expected_root = "orderer-admin-tls-ca"
    elif identity == "tls-registrar" or identity.endswith("-tls"):
        expected_root = f"{org}-tls-ca"
    else:
        expected_root = f"{org}-enroll-ca"
    if root_name != expected_root:
        raise ValueError(f"unexpected CA root for {org}/{identity}: {root_name}")
    subject = value(lines, "subject=")
    if not re.search(r"(?:^|,)OU=" + re.escape(expected_ou) + r"(?:,|$)", subject):
        raise ValueError(f"unexpected subject OU for {org}/{identity}: {subject}")
    expected_cn = f"{org}-{identity}" if identity in {
        "tls-registrar", "enroll-registrar", "enroll-server-tls",
        "admin-tls-registrar", "operator1",
    } else identity
    if not re.search(r"(?:^|,)CN=" + re.escape(expected_cn) + r"(?:,|$)", subject):
        raise ValueError(f"unexpected subject CN for {org}/{identity}: {subject}")

    msp = identity_dir / "msp"
    keys = list((msp / "keystore").glob("*_sk"))
    if len(keys) != 1:
        raise ValueError(f"expected one signing key for {org}/{identity}")
    key = keys[0]
    if key.is_symlink() or key.parent.is_symlink():
        raise ValueError(f"symlinked signing key for {org}/{identity}")
    cert_pub = run("openssl", "x509", "-in", str(path), "-pubkey", "-noout")
    cert_der = run("openssl", "pkey", "-pubin", "-outform", "DER", input_bytes=cert_pub)
    key_der = run("openssl", "pkey", "-in", str(key), "-pubout", "-outform", "DER")
    key_matches = hashlib.sha256(cert_der).digest() == hashlib.sha256(key_der).digest()
    if not key_matches:
        raise ValueError(f"key mismatch for {org}/{identity}")
    if owner(key)[1] != "0600" or owner(identity_dir)[1] != "0700":
        raise ValueError(f"unsafe local key/directory mode for {org}/{identity}")

    copies = list((msp / "cacerts").glob("*.pem")) + list((msp / "tlscacerts").glob("*.pem"))
    local_root_copy = any(copy.read_bytes() == root_pem.read_bytes() for copy in copies)
    if not local_root_copy:
        raise ValueError(f"local MSP root copy missing for {org}/{identity}")
    run("openssl", "verify", "-CAfile", str(root_pem), str(path))

    details = run("openssl", "x509", "-in", str(path), "-text", "-noout").decode()
    attributes_match = re.search(r"^\s+1\.2\.3\.4\.5\.6\.7\.8\.1:\s*\n\s+(\{[^\n]+\})",
                                 details, re.MULTILINE)
    if "1.2.3.4.5.6.7.8.1:" in details and not attributes_match:
        raise ValueError(f"unparseable attribute extension for {org}/{identity}")
    attributes = json.loads(attributes_match.group(1)).get("attrs", {}) if attributes_match else {}
    if not isinstance(attributes, dict):
        raise ValueError(f"invalid attribute extension for {org}/{identity}")
    supply_attrs = {key: value for key, value in attributes.items() if key.startswith("supply.")}
    if supply_attrs != BUSINESS_ATTRS.get((org, identity), {}):
        raise ValueError(f"unexpected business attributes for {org}/{identity}")
    san = extension(details, "Subject Alternative Name")
    if identity.endswith("-peer0-tls"):
        expected_san = f"DNS:peer0.{org}.supply.test"
    elif identity == "osnadmin-client1-tls":
        expected_san = "DNS:osnadmin-client1.orderer.supply.test"
    elif re.fullmatch(r"orderer[0-2](-admin-server)?-tls", identity):
        expected_san = f"DNS:{identity.split('-')[0]}.orderer.supply.test"
    else:
        expected_san = None
    if expected_san is not None and san != expected_san:
        raise ValueError(f"unexpected TLS SAN for {org}/{identity}: {san}")
    key_usage = extension(details, "Key Usage")
    extended_key_usage = extension(details, "Extended Key Usage")
    if root_name.endswith("-tls-ca"):
        if "Digital Signature" not in key_usage:
            raise ValueError(f"TLS signing key usage missing for {org}/{identity}")
        required_eku = set()
        if identity == "enroll-server-tls" or identity.endswith("-admin-server-tls"):
            required_eku.add("TLS Web Server Authentication")
        elif identity == "osnadmin-client1-tls":
            required_eku.add("TLS Web Client Authentication")
        elif identity.endswith("-peer0-tls") or re.fullmatch(r"orderer[0-2]-tls", identity):
            required_eku.update(("TLS Web Server Authentication", "TLS Web Client Authentication"))
        if any(usage not in extended_key_usage for usage in required_eku):
            raise ValueError(f"required TLS extended key usage missing for {org}/{identity}")
    elif key_usage != "Digital Signature" or extended_key_usage != "ABSENT":
        raise ValueError(f"unexpected ECert key usage for {org}/{identity}")
    cert_owner, cert_mode = owner(path)
    key_owner, key_mode = owner(key)
    if cert_owner != key_owner:
        raise ValueError(f"certificate/key owner differs for {org}/{identity}")
    return dict(
        organization=org, identity=identity, purpose=purpose(identity),
        issued_in="M1 #9" if identity in {"tls-registrar", "enroll-server-tls"}
        or (org == "seller" and identity in {"enroll-registrar", "operator1"})
        else "M1 #10",
        ca_root=root_name, ca_root_sha256=root_fingerprint,
        issuer=issuer, subject=subject,
        serial_hex=value(lines, "serial="),
        aki_hex=extension(details, "Authority Key Identifier"),
        ski_hex=extension(details, "Subject Key Identifier"),
        san=san,
        key_usage=key_usage, extended_key_usage=extended_key_usage,
        not_before_utc=value(lines, "notBefore="),
        not_after_utc=value(lines, "notAfter="),
        cert_sha256=value(lines, "sha256 Fingerprint="),
        public_key_sha256=hashlib.sha256(cert_der).hexdigest(),
        supply_user_id=attributes.get("supply.userId", ""),
        supply_role=attributes.get("supply.role", ""),
        cert_path=str(path.relative_to(ROOT)),
        cert_owner_uid_gid=cert_owner, cert_mode=cert_mode,
        key_owner_uid_gid=key_owner, key_mode=key_mode,
        identity_dir_mode=owner(identity_dir)[1],
        key_matches_cert="PASS", local_root_copy="PASS", chain_verifies="PASS",
    )


def main():
    roots = []
    for pem in sorted(TRUST.glob("*-ca.pem")):
        lines = cert_lines(pem)
        roots.append((pem.stem, pem, value(lines, "subject="),
                      value(lines, "sha256 Fingerprint=")))
    if len(roots) != 9:
        raise ValueError(f"expected nine measured CA roots, found {len(roots)}")
    paths = sorted(IDENTITIES.glob("*/*/msp/signcerts/cert.pem"))
    expected = {(org, identity) for org, identities in EXPECTED_OU.items()
                for identity in identities}
    found = {(path.parents[2].parent.name, path.parents[2].name) for path in paths}
    if found != expected or len(paths) != len(expected):
        raise ValueError(f"expected exact {len(expected)} local identity signcerts; "
                         f"missing={sorted(expected - found)}, extra={sorted(found - expected)}")
    rows = [inspect(path, roots) for path in paths]
    if len({row["public_key_sha256"] for row in rows}) != len(rows):
        raise ValueError("duplicate identity public key across local certificates")
    if sum(row["issued_in"] == "M1 #10" for row in rows) != 31:
        raise ValueError("expected 31 M1 #10 signcerts: 27 identities and four registrars")
    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"local certificate inspection FAIL: {error}", file=sys.stderr)
        sys.exit(1)
