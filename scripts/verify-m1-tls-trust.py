#!/usr/bin/env python3
"""Check the M1 TLS certificate trust boundary without starting Fabric nodes.

Only public certificates are read. Successful certificate validation does not
prove that a future Peer, Orderer, admin API, or CCaaS process uses this policy.
"""

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
OPENSSL = "openssl"
ROOT_FINGERPRINTS = {
    # Measured CA root certificate fingerprints in evidence/m1/issue-9.md.
    "seller-tls-ca": "2455d735b3b8a6f576ab7338b6580574adc5506e259508d08a18ecb6bd5cdf77",
    "buyer-tls-ca": "5ec8ad97976e496506dd69459a63d105429c36a019aade50de323fa3c240c354",
    "carrier-tls-ca": "3d3ffc658f1cb63fd181e44f7723ec2e6c2ec6a107b334506bd4ccb59e4cf96a",
    "orderer-tls-ca": "25d0a6ef0bcf77f1e7ff8585708d883f79ccca81fe866aabd913e849b7d036d4",
    "orderer-admin-tls-ca": "71cee5b98df4a0134922384dc912c5c8e6f4ccf783b5dc05fb80e6ff76df6b72",
}


@dataclass(frozen=True)
class Server:
    name: str
    host: str
    root: str
    certificate: str
    client_auth: bool = False


def server_cases():
    cases = []
    for org in ("seller", "buyer", "carrier", "orderer"):
        root = f"{org}-tls-ca"
        cases.extend((
            Server(f"{org} TLS CA", f"ca-tls.{org}.supply.test", root,
                   f"trust/{org}-tls-server.pem"),
            Server(f"{org} Enrollment CA", f"ca-enroll.{org}.supply.test", root,
                   f"trust/{org}-enroll-server.pem"),
        ))
    cases.append(Server("Orderer admin-client CA", "ca-admin-tls.orderer.supply.test",
                        "orderer-admin-tls-ca", "trust/orderer-admin-tls-server.pem"))
    for org in ("seller", "buyer", "carrier"):
        cases.append(Server(f"{org} Peer Gateway", f"peer0.{org}.supply.test",
                            f"{org}-tls-ca",
                            f"identities/{org}/{org}-peer0-tls/msp/signcerts/cert.pem",
                            client_auth=True))
    for index in range(3):
        host = f"orderer{index}.orderer.supply.test"
        cases.extend((
            Server(f"Orderer {index} transport/Raft", host, "orderer-tls-ca",
                   f"identities/orderer/orderer{index}-tls/msp/signcerts/cert.pem",
                   client_auth=True),
            Server(f"Orderer {index} admin server", host, "orderer-tls-ca",
                   f"identities/orderer/orderer{index}-admin-server-tls/msp/signcerts/cert.pem"),
        ))
    return cases


def openssl(*args):
    return subprocess.run((OPENSSL, *map(str, args)), capture_output=True,
                          text=True, check=False)


def select_openssl(explicit):
    candidates = ([explicit] if explicit else
                  [shutil.which("openssl"), "/opt/homebrew/bin/openssl",
                   "/usr/local/bin/openssl"])
    for candidate in dict.fromkeys(filter(None, candidates)):
        try:
            version = subprocess.run((candidate, "version"), capture_output=True,
                                     text=True, check=False)
            help_text = subprocess.run((candidate, "verify", "-help"),
                                       capture_output=True, text=True, check=False)
        except OSError:
            continue
        if version.returncode == 0 and version.stdout.startswith("OpenSSL 3.") \
                and "-verify_hostname" in help_text.stdout + help_text.stderr:
            return candidate, version.stdout.strip()
    raise RuntimeError("OpenSSL 3 with verify -verify_hostname is required; "
                       "pass --openssl /path/to/openssl if installed elsewhere")


def checked_output(*args):
    result = openssl(*args)
    if result.returncode:
        raise RuntimeError(f"openssl {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def verify(cert, root, purpose=None, host=None):
    args = ["verify", "-no-CApath", "-no-CAstore", "-CAfile", root]
    if purpose:
        args.extend(("-purpose", purpose))
    if host:
        args.extend(("-verify_hostname", host))
    args.append(cert)
    return openssl(*args)


def require_pass(result, label):
    if result.returncode:
        raise RuntimeError(f"{label}: expected verification success; "
                           f"got {result.returncode}: {result.stderr.strip()}")


def require_reject(result, label, reason):
    if not result.returncode:
        raise RuntimeError(f"{label}: unexpectedly accepted")
    if reason not in (result.stdout + result.stderr).lower():
        raise RuntimeError(f"{label}: rejected for an unexpected reason: "
                           f"{result.stderr.strip()}")


def root_path(runtime, name):
    return runtime / "trust" / f"{name}.pem"


def require_eku(cert, label, *required):
    extension = checked_output("x509", "-in", cert, "-noout", "-ext",
                               "extendedKeyUsage")
    if not extension.startswith("X509v3 Extended Key Usage:"):
        raise RuntimeError(f"{label}: explicit TLS EKU extension is missing")
    values = {value.strip() for value in extension.split("\n", 1)[1].split(",")}
    missing = set(required) - values
    if missing:
        raise RuntimeError(f"{label}: required TLS EKU missing: {sorted(missing)}")


def require_key_usage(cert, label):
    extension = checked_output("x509", "-in", cert, "-noout", "-ext", "keyUsage")
    if not extension.startswith("X509v3 Key Usage:"):
        raise RuntimeError(f"{label}: explicit TLS key-usage extension is missing")
    values = {value.strip() for value in extension.split("\n", 1)[1].split(",")}
    if "Digital Signature" not in values:
        raise RuntimeError(f"{label}: Digital Signature key usage is missing")


def inspect_root(runtime, name, expected):
    path = root_path(runtime, name)
    binary = subprocess.run((OPENSSL, "x509", "-in", str(path), "-outform", "DER"),
                            capture_output=True, check=False)
    if binary.returncode or hashlib.sha256(binary.stdout).hexdigest() != expected:
        raise RuntimeError(f"root fingerprint differs from M1 #9: {name}")
    require_pass(openssl("verify", "-check_ss_sig", "-no-CApath", "-no-CAstore",
                         "-CAfile", path, path), f"self-signed CA root {name}")
    print(f"PASS root {name}: measured M1 #9 fingerprint")


def inspect_server(runtime, case):
    cert = runtime / case.certificate
    root = root_path(runtime, case.root)
    san = checked_output("x509", "-in", cert, "-noout", "-ext", "subjectAltName")
    names = re.findall(r"DNS:([^,\s]+)", san)
    if names != [case.host]:
        raise RuntimeError(f"{case.name}: expected exact DNS SAN {case.host}; got {names}")
    require_key_usage(cert, case.name)
    required = ["TLS Web Server Authentication"]
    if case.client_auth:
        required.append("TLS Web Client Authentication")
    require_eku(cert, case.name, *required)
    require_pass(verify(cert, root, "sslserver", case.host), case.name)
    if case.client_auth:
        require_pass(verify(cert, root, "sslclient"), f"{case.name} client TLS purpose")
    wrong_root = "orderer-admin-tls-ca" if case.root == "orderer-tls-ca" else "orderer-tls-ca"
    require_reject(verify(cert, root_path(runtime, wrong_root), "sslserver", case.host),
                   f"{case.name} wrong root", "unable to get local issuer certificate")
    require_reject(verify(cert, root, "sslserver", "wrong.supply.test"),
                   f"{case.name} wrong hostname", "hostname mismatch")
    print(f"PASS certificate {case.name}: SAN, acceptable purpose, root; "
          "wrong root/hostname rejected offline")


def inspect_admin_client(runtime):
    cert = runtime / "identities/orderer/osnadmin-client1-tls/msp/signcerts/cert.pem"
    dedicated = root_path(runtime, "orderer-admin-tls-ca")
    require_key_usage(cert, "Orderer admin mTLS client")
    require_eku(cert, "Orderer admin mTLS client", "TLS Web Client Authentication")
    require_pass(verify(cert, dedicated, "sslclient"), "Orderer admin mTLS client")
    for name in ROOT_FINGERPRINTS:
        if name == "orderer-admin-tls-ca":
            continue
        require_reject(verify(cert, root_path(runtime, name), "sslclient"),
                       f"Orderer admin mTLS client against {name}",
                       "unable to get local issuer certificate")
    print("PASS admin-client certificate: dedicated root and acceptable client purpose; "
          "all four other TLS roots rejected offline")


def inspect_missing_eku_control(runtime):
    cert = runtime / "identities/seller/operator1/msp/signcerts/cert.pem"
    root = root_path(runtime, "seller-enroll-ca")
    require_pass(verify(cert, root, "sslserver"),
                 "OpenSSL sslserver purpose negative control")
    try:
        require_eku(cert, "Seller operator ECert", "TLS Web Server Authentication")
    except RuntimeError as error:
        if "explicit TLS EKU extension is missing" not in str(error):
            raise
    else:
        raise RuntimeError("Seller operator ECert unexpectedly passed explicit TLS EKU check")
    print("PASS negative control: ECert accepted by OpenSSL sslserver purpose alone, "
          "but rejected for absent TLS EKU")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openssl", help="OpenSSL 3 executable; auto-detected by default")
    parser.add_argument("--runtime-dir", type=Path, default=REPO / ".runtime",
                        help="existing ignored M1 runtime directory (default: repo/.runtime)")
    args = parser.parse_args()
    global OPENSSL
    OPENSSL, version = select_openssl(args.openssl)
    print(f"OpenSSL tool: {OPENSSL} ({version})")
    runtime = args.runtime_dir.resolve()
    if not runtime.is_dir():
        raise RuntimeError(f"M1 runtime directory missing: {runtime}")
    for name, fingerprint in ROOT_FINGERPRINTS.items():
        inspect_root(runtime, name, fingerprint)
    cases = server_cases()
    for case in cases:
        inspect_server(runtime, case)
    inspect_admin_client(runtime)
    inspect_missing_eku_control(runtime)
    print(f"PASS: {len(ROOT_FINGERPRINTS)} pinned roots, {len(cases)} service certificate files, "
          "one dedicated admin-client certificate file, one missing-EKU negative control")
    print("NOT RUN: live Peer/Orderer/admin API/CCaaS handshakes and full T-NET-05")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"M1 TLS trust check FAIL: {error}", file=sys.stderr)
        sys.exit(1)
