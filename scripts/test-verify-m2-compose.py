#!/usr/bin/env python3
"""Exercise M2 policy-checker fail-closed behavior in a temporary Compose copy."""

import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NETWORK = ROOT / "compose/network.yaml"
PEER_ENV = "    FABRIC_CFG_PATH: /etc/hyperledger/fabric\n"


def replace_once(source, old, new):
    assert old in source, f"missing mutation anchor: {old!r}"
    return source.replace(old, new, 1)


def peer_tls_off(source):
    assert source.count(PEER_ENV) == 2
    offset = source.rfind(PEER_ENV)
    return (source[:offset] + PEER_ENV + '    CORE_PEER_TLS_ENABLED: "false"\n'
            + source[offset + len(PEER_ENV):])


def swap_peer_volumes(source):
    assert source.count("source: peer0-seller-ledger") == 1
    assert source.count("source: peer0-buyer-ledger") == 1
    return (source.replace("source: peer0-seller-ledger", "source: temporary-ledger", 1)
            .replace("source: peer0-buyer-ledger", "source: peer0-seller-ledger", 1)
            .replace("source: temporary-ledger", "source: peer0-buyer-ledger", 1))


def run_checker(directory):
    return subprocess.run(("python3", "scripts/verify-m2-compose.py"), cwd=directory,
                          capture_output=True, text=True, check=False)


def main():
    original = NETWORK.read_text()
    mutations = (
        ("published Orderer port", "host port published",
         lambda text: replace_once(text, "  orderer0:\n    <<: *orderer\n",
                                   '  orderer0:\n    <<: *orderer\n    ports: ["7050:7050"]\n')),
        ("shared Peer volume", ("expected nine retained CA and nine separate M2 volumes",
                                "wrong or shared state volume"),
         lambda text: replace_once(text, "source: peer0-seller-ledger",
                                   "source: peer0-buyer-ledger")),
        ("misassigned Peer volumes", "wrong or shared state volume", swap_peer_volumes),
        ("cross-org Peer MSP", "unexpected source",
         lambda text: replace_once(text,
                                   "../.runtime/identities/seller/seller-peer0/msp",
                                   "../.runtime/identities/buyer/buyer-peer0/msp")),
        ("unlocked image pull", "image differs from measured version lock",
         lambda text: replace_once(text, "pull_policy: never", "pull_policy: always")),
        ("wrong Fabric network name", "wrong network name",
         lambda text: replace_once(text, "name: supply-fabric", "name: supply-public")),
        ("extra Docker-socket service", "unexpected or missing service",
         lambda text: replace_once(
             text, "services:\n  orderer0:",
             'services:\n  rogue:\n    image: busybox:1.36\n    networks: [fabric]\n'
             '    volumes: ["/var/run/docker.sock:/var/run/docker.sock"]\n  orderer0:')),
        ("Peer TLS-off environment override", "environment could override TLS/MSP",
         peer_tls_off),
        ("cross-org Peer credential file", "wrong private CouchDB credential file",
         lambda text: replace_once(text,
                                   "../.secrets/peer-couchdb/seller.env",
                                   "../.secrets/peer-couchdb/buyer.env")),
        ("wrong admin client trust root", "unexpected source",
         lambda text: replace_once(text,
                                   "../.runtime/trust/orderer-admin-tls-ca.pem",
                                   "../.runtime/trust/orderer-tls-ca.pem")),
        ("cross-org Peer TLS root", "unexpected source",
         lambda text: replace_once(text,
                                   "source: ../.runtime/trust/seller-tls-ca.pem\n"
                                   "        target: /run/supply/peer-tls-root.pem",
                                   "source: ../.runtime/trust/buyer-tls-ca.pem\n"
                                   "        target: /run/supply/peer-tls-root.pem")),
    )
    with tempfile.TemporaryDirectory(prefix="supply-m2-compose-test-") as dirname:
        directory = Path(dirname)
        (directory / "compose").mkdir()
        (directory / "scripts").mkdir()
        for relative in ("versions.lock.yaml", "compose/bootstrap.yaml", "compose/ca.yaml",
                         "scripts/verify-m2-compose.py"):
            shutil.copy2(ROOT / relative, directory / relative)
        target = directory / "compose/network.yaml"
        target.write_text(original)
        baseline = run_checker(directory)
        assert baseline.returncode == 0, baseline.stderr
        print("PASS: unmodified M2 Compose model accepted")
        for label, expected_error, mutate in mutations:
            target.write_text(mutate(original))
            result = run_checker(directory)
            expected_errors = ((expected_error,) if isinstance(expected_error, str)
                               else expected_error)
            assert result.returncode == 1 and any(error in result.stderr
                                                  for error in expected_errors), (
                label, result.returncode, result.stderr)
            print(f"PASS: checker rejected {label}")


if __name__ == "__main__":
    main()
