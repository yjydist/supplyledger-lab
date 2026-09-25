#!/usr/bin/env python3
"""Exercise M2 node preparation against existing M1 material in a temporary directory."""

import argparse
import base64
import hashlib
import json
import os
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PREPARE = ROOT / "scripts/prepare-m2-nodes.py"


def run(action, m1_runtime, output_runtime, secrets_dir, inspect_block=None):
    command = (
        sys.executable, str(PREPARE), action,
        "--m1-runtime", str(m1_runtime),
        "--output-runtime", str(output_runtime),
        "--secrets-dir", str(secrets_dir),
    )
    if inspect_block is not None:
        command += ("--inspect-block", str(inspect_block))
    return subprocess.run(command, capture_output=True, text=True, check=False)


def signature(paths):
    return {str(path): (hashlib.sha256(path.read_bytes()).hexdigest(),
                        path.stat().st_mtime_ns)
            for path in paths}


def expect_field_rejection(path, original_fragment, changed_fragment, fields,
                           output_runtime, keys, expected_error):
    original = path.read_bytes()
    assert original.count(original_fragment) == 1
    path.write_bytes(original.replace(original_fragment, changed_fragment, 1))
    try:
        try:
            fields(output_runtime, keys)
        except ValueError as error:
            assert expected_error in str(error), str(error)
        else:
            raise AssertionError(f"unsafe node field accepted: {path}")
    finally:
        path.write_bytes(original)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m1-runtime", type=Path, default=ROOT / ".runtime")
    parser.add_argument("--inspect-block", type=Path)
    args = parser.parse_args()
    m1_runtime = args.m1_runtime.resolve()
    if not m1_runtime.is_dir():
        print("NOT RUN: existing ignored M1 runtime is required", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="supply-m2-node-test-") as temporary:
        test_root = Path(temporary)
        output_runtime = test_root / "runtime"
        secrets_dir = test_root / "secrets"
        initial = run("prepare", m1_runtime, output_runtime, secrets_dir)
        assert initial.returncode == 0, initial.stderr
        files = sorted((output_runtime / "network-config").glob("*.yaml"))
        files += sorted(secrets_dir.rglob("*.env"))
        assert len(files) == 12
        password = (secrets_dir / "couchdb/seller.env").read_text().split(
            "COUCHDB_PASSWORD=", 1)[1].strip()
        assert password not in initial.stdout and password not in initial.stderr
        before = signature(files)
        repeated = run("prepare", m1_runtime, output_runtime, secrets_dir)
        assert repeated.returncode == 0, repeated.stderr
        assert signature(files) == before, "preparation changed existing private files"
        checked = run("verify", m1_runtime, output_runtime, secrets_dir,
                      args.inspect_block)
        assert checked.returncode == 0, checked.stderr
        print("PASS: prepare, verify and repeated prepare preserve six configs and six env files")
        preflight = runpy.run_path(str(PREPARE))
        keys = preflight["key_names"](m1_runtime)
        fields = preflight["check_node_fields"]
        expect_field_rejection(
            output_runtime / "network-config/peer0-seller.yaml",
            b'bootstrap: ""', b'bootstrap: "peer0.buyer.supply.test:7051"',
            fields, output_runtime, keys, "wrong node field peer.gossip.bootstrap")
        print("PASS: cross-organization gossip bootstrap rejected")
        peer_rendered = output_runtime / "network-config/peer0-seller.yaml"
        expect_field_rejection(
            peer_rendered, b"  BCCSP:\n    Default: SW\n",
            b"", fields, output_runtime, keys,
            "wrong node field peer.BCCSP.Default")
        expect_field_rejection(
            peer_rendered, b"    Default: SW\n", b"    Default: PKCS11\n",
            fields, output_runtime, keys,
            "wrong node field peer.BCCSP.Default")
        expect_field_rejection(
            peer_rendered, b"        KeyStore: /run/supply/msp/keystore\n",
            b"        KeyStore: /run/supply/other-org/msp/keystore\n",
            fields, output_runtime, keys,
            "wrong node field peer.BCCSP.SW.FileKeyStore.KeyStore")
        print("PASS: missing, non-SW and cross-organization Peer BCCSP keystore rejected")
        builder = (b"    - {name: m2-chaincode-disabled, "
                   b"path: /opt/supplyledger/m2-chaincode-disabled}\n")
        for replacement in (b"", builder.replace(
                b"/opt/supplyledger/m2-chaincode-disabled", b"/opt/unknown")):
            expect_field_rejection(peer_rendered, builder, replacement,
                                   fields, output_runtime, keys,
                                   "wrong M2 deny-all external builder")
        delivery = b"  deliveryclient:\n    blockGossipEnabled: false\n"
        expect_field_rejection(peer_rendered, delivery, b"",
                               fields, output_runtime, keys,
                               "wrong node field peer.deliveryclient.blockGossipEnabled")
        expect_field_rejection(peer_rendered, b"    blockGossipEnabled: false\n",
                               b"    blockGossipEnabled: true\n",
                               fields, output_runtime, keys,
                               "wrong node field peer.deliveryclient.blockGossipEnabled")
        expect_field_rejection(peer_rendered, b"ledger:\n",
                               b"deliveryclient:\n  blockGossipEnabled: false\nledger:\n",
                               fields, output_runtime, keys,
                               "root-level deliveryclient is ignored")
        tls_flag = (b"  deliveryclient:\n    blockGossipEnabled: false\n"
                    b"  tls:\n    enabled: true\n    clientAuthRequired: true\n")
        for replacement in (
            tls_flag.replace(b"    clientAuthRequired: true\n",
                             b"    clientAuthRequired: false\n"),
            tls_flag.replace(b"    clientAuthRequired: true\n", b""),
        ):
            expect_field_rejection(peer_rendered, tls_flag, replacement,
                                   fields, output_runtime, keys,
                                   "wrong node field peer.tls.clientAuthRequired")
        tls_roots = (b"    clientRootCAs:\n      files:\n"
                     b"        - /run/supply/peer-tls-root.pem\n"
                     b"        - /run/supply/client-roots/buyer.pem\n"
                     b"        - /run/supply/client-roots/carrier.pem\n")
        for replacement in (
            b"", tls_roots.replace(b"        - /run/supply/client-roots/buyer.pem\n", b""),
            tls_roots + b"        - /run/supply/client-roots/orderer.pem\n",
            tls_roots.replace(b"/run/supply/client-roots/buyer.pem",
                              b"/run/supply/client-roots/seller.pem"),
        ):
            expect_field_rejection(peer_rendered, tls_roots, replacement,
                                   fields, output_runtime, keys,
                                   "wrong peer.tls.clientRootCAs.files")
        rendered_client_key = (
            f"    clientKey:\n      file: /run/supply/tls/keystore/"
            f"{keys[('peer0-seller', 'tls')]}\n").encode()
        for original_fragment, replacement in (
            (b"    clientCert:\n      file: /run/supply/tls/signcerts/cert.pem\n", b""),
            (b"    clientCert:\n      file: /run/supply/tls/signcerts/cert.pem\n",
             b"    clientCert:\n      file: /run/supply/other-org/signcerts/cert.pem\n"),
            (rendered_client_key, b""),
            (rendered_client_key, rendered_client_key.replace(
                b"/run/supply/tls/keystore/", b"/run/supply/other-org/keystore/")),
        ):
            expect_field_rejection(peer_rendered, original_fragment, replacement,
                                   fields, output_runtime, keys,
                                   "wrong node field peer.tls.client")
        print("PASS: rendered Peer mTLS flag, exact business roots and paired client paths enforced")
        expect_field_rejection(peer_rendered, b"chaincode:\n",
                               b"vm:\n  endpoint: unix:///var/run/docker.sock\nchaincode:\n",
                               fields, output_runtime, keys,
                               "Docker VM endpoint is forbidden")
        print("PASS: missing/wrong M2 builder, wrong/root delivery and Docker VM endpoint rejected")
        system_block = (b"  system:\n    _lifecycle: enable\n"
                        b"    cscc: enable\n    qscc: enable\n")
        for original_fragment, replacement in (
            (system_block, b""),
            (b"    _lifecycle: enable\n", b""),
            (b"    cscc: enable\n", b"    cscc: disable\n"),
            (b"    qscc: enable\n", b""),
            (b"    qscc: enable\n", b"    qscc: enable\n    lscc: enable\n"),
            (b"ledger:\n", b"system:\n  cscc: enable\nledger:\n"),
        ):
            expect_field_rejection(peer_rendered, original_fragment, replacement,
                                   fields, output_runtime, keys,
                                   "chaincode.system must enable only")
        print("PASS: missing/disabled/extra/root-level system chaincodes rejected in rendered Peer")
        expect_field_rejection(
            output_runtime / "network-config/orderer0.yaml",
            b"  Cluster:\n    ClientCertificate:",
            b"  Cluster:\n    ListenAddress: 0.0.0.0\n    ClientCertificate:",
            fields, output_runtime, keys, "unexpected or incomplete separate Raft listener")
        print("PASS: partial separate Raft listener rejected")
        for replacement in (b"", b"  MaxRequestBodySize: 0\n"):
            expect_field_rejection(
                output_runtime / "network-config/orderer0.yaml",
                b"  MaxRequestBodySize: 1 MB\n", replacement,
                fields, output_runtime, keys,
                "wrong node field ChannelParticipation.MaxRequestBodySize")
        print("PASS: omitted and zero rendered channel join body limits rejected")
        source_root = test_root / "source"
        source_template = source_root / "network/config/orderer0.yaml"
        source_template.parent.mkdir(parents=True)
        original_source = (ROOT / "network/config/orderer0.yaml").read_bytes()
        assert original_source.count(b"  MaxRequestBodySize: 1 MB\n") == 1
        source_template.write_bytes(original_source.replace(
            b"  MaxRequestBodySize: 1 MB\n", b"  MaxRequestBodySize: 0\n", 1))
        render = preflight["rendered_config"]
        render_globals = render.__globals__
        original_root = render_globals["ROOT"]
        try:
            render_globals["ROOT"] = source_root
            try:
                render("orderer0", keys)
            except ValueError as error:
                assert "source MaxRequestBodySize must be 1 MB" in str(error), str(error)
            else:
                raise AssertionError("zero source channel join body limit accepted")
        finally:
            render_globals["ROOT"] = original_root
        print("PASS: zero source channel join body limit rejected")
        peer_source = source_root / "network/config/peer0-seller.yaml"
        original_peer_source = (ROOT / "network/config/peer0-seller.yaml").read_bytes()
        for original_fragment, replacement, field in (
            (b"  BCCSP:\n    Default: SW\n", b"",
             "peer.BCCSP.Default"),
            (b"    Default: SW\n", b"    Default: PKCS11\n",
             "peer.BCCSP.Default"),
            (b"        KeyStore: /run/supply/msp/keystore\n",
             b"        KeyStore: /run/supply/other-org/msp/keystore\n",
             "peer.BCCSP.SW.FileKeyStore.KeyStore"),
        ):
            assert original_peer_source.count(original_fragment) == 1
            peer_source.write_bytes(original_peer_source.replace(
                original_fragment, replacement, 1))
            try:
                render_globals["ROOT"] = source_root
                try:
                    render("peer0-seller", keys)
                except ValueError as error:
                    assert f"wrong source node field {field}" in str(error), str(error)
                else:
                    raise AssertionError(f"unsafe source Peer BCCSP accepted: {field}")
            finally:
                render_globals["ROOT"] = original_root
        print("PASS: missing, non-SW and cross-organization source Peer BCCSP rejected")
        for original_fragment, replacement, expected_error in (
            (builder, b"", "source must select only the M2 deny-all external builder"),
            (builder, builder.replace(
                b"/opt/supplyledger/m2-chaincode-disabled", b"/opt/unknown"),
             "source must select only the M2 deny-all external builder"),
            (b"ledger:\n", b"deliveryclient:\n  blockGossipEnabled: false\nledger:\n",
             "source peer.deliveryclient.blockGossipEnabled must be false"),
            (b"    blockGossipEnabled: false\n", b"    blockGossipEnabled: true\n",
             "source peer.deliveryclient.blockGossipEnabled must be false"),
            (b"chaincode:\n",
             b"vm:\n  endpoint: unix:///var/run/docker.sock\nchaincode:\n",
             "source Docker VM endpoint is forbidden"),
            (tls_flag, tls_flag.replace(b"    clientAuthRequired: true\n",
                                        b"    clientAuthRequired: false\n"),
             "source peer.tls.clientAuthRequired must be true"),
            (tls_flag, tls_flag.replace(b"    clientAuthRequired: true\n", b""),
             "source peer.tls.clientAuthRequired must be true"),
            (tls_roots, b"", "wrong source peer.tls.clientRootCAs.files"),
            (tls_roots, tls_roots.replace(b"/run/supply/client-roots/buyer.pem",
                                          b"/run/supply/client-roots/seller.pem"),
             "wrong source peer.tls.clientRootCAs.files"),
            (tls_roots, tls_roots + b"        - /run/supply/client-roots/orderer.pem\n",
             "wrong source peer.tls.clientRootCAs.files"),
            (b"    clientCert:\n      file: /run/supply/tls/signcerts/cert.pem\n",
             b"", "source outbound Peer TLS client pair must be complete"),
            (b"    clientKey:\n      file: /run/supply/tls/keystore/__PEER_TLS_KEY__\n",
             b"", "source outbound Peer TLS client pair must be complete"),
        ):
            assert original_peer_source.count(original_fragment) == 1
            peer_source.write_bytes(original_peer_source.replace(
                original_fragment, replacement, 1))
            try:
                render_globals["ROOT"] = source_root
                try:
                    render("peer0-seller", keys)
                except ValueError as error:
                    assert expected_error in str(error), str(error)
                else:
                    raise AssertionError(f"unsafe source Peer setting accepted: {expected_error}")
            finally:
                render_globals["ROOT"] = original_root
        print("PASS: source M2 builder, delivery, Peer mTLS roots/client pair and absent VM enforced")
        for original_fragment, replacement in (
            (system_block, b""),
            (b"    _lifecycle: enable\n", b""),
            (b"    cscc: enable\n", b"    cscc: disable\n"),
            (b"    qscc: enable\n", b""),
            (b"    qscc: enable\n", b"    qscc: enable\n    lscc: enable\n"),
            (b"ledger:\n", b"system:\n  cscc: enable\nledger:\n"),
        ):
            assert original_peer_source.count(original_fragment) == 1
            peer_source.write_bytes(original_peer_source.replace(
                original_fragment, replacement, 1))
            try:
                render_globals["ROOT"] = source_root
                try:
                    render("peer0-seller", keys)
                except ValueError as error:
                    assert "source chaincode.system must enable only" in str(error), str(error)
                else:
                    raise AssertionError("unsafe source Peer system chaincode setting accepted")
            finally:
                render_globals["ROOT"] = original_root
        print("PASS: missing/disabled/extra/root-level system chaincodes rejected in source Peer")
        if args.inspect_block:
            assert "three effective Raft TLS cert paths and PEM bytes" in checked.stdout
            print("PASS: rendered Orderer TLS certs match native decoded #17 block")
            for variant, expected_error in (
                ("number", "expected initial CONFIG block 0"),
                ("channel", "wrong channel ID or envelope type"),
                ("type", "wrong channel ID or envelope type"),
                ("envelopes", "expected one CONFIG envelope"),
            ):
                altered_block = json.loads(args.inspect_block.read_text())
                if variant == "number":
                    altered_block["header"]["number"] = "5"
                elif variant == "channel":
                    altered_block["data"]["data"][0]["payload"]["header"][
                        "channel_header"]["channel_id"] = "otherchannel"
                elif variant == "type":
                    altered_block["data"]["data"][0]["payload"]["header"][
                        "channel_header"]["type"] = 2
                else:
                    envelopes = altered_block["data"]["data"]
                    envelopes.append(envelopes[0])
                changed_block = test_root / f"wrong-{variant}-block.json"
                changed_block.write_text(json.dumps(altered_block))
                rejected = run("verify", m1_runtime, output_runtime,
                               secrets_dir, changed_block)
                assert rejected.returncode == 1 and expected_error in rejected.stderr
            print("PASS: nonzero, wrong-channel, non-CONFIG and multiple-envelope blocks rejected")
            altered_block = json.loads(args.inspect_block.read_text())
            consenters = altered_block["data"]["data"][0]["payload"]["data"]["config"][
                "channel_group"]["groups"]["Orderer"]["values"]["ConsensusType"][
                    "value"]["metadata"]["consenters"]
            consenters[0]["client_tls_cert"] = base64.b64encode(b"wrong cert").decode()
            changed_block = test_root / "wrong-initial-block.json"
            changed_block.write_text(json.dumps(altered_block))
            rejected = run("verify", m1_runtime, output_runtime, secrets_dir, changed_block)
            assert rejected.returncode == 1 and "effective Raft client/server cert differs" in rejected.stderr
            print("PASS: changed consenter client certificate rejected")

        peer = secrets_dir / "peer-couchdb/seller.env"
        original = peer.read_bytes()
        peer.write_bytes(original.replace(password.encode(), b"wrong-password"))
        mismatch = run("verify", m1_runtime, output_runtime, secrets_dir)
        assert mismatch.returncode == 1 and "credentials differ" in mismatch.stderr
        assert password not in mismatch.stderr
        peer.write_bytes(original)
        print("PASS: mismatched Peer/CouchDB secret rejected without disclosure")
        for override in (b"CORE_VM_ENDPOINT=unix:///var/run/docker.sock\n",
                         b"CORE_CHAINCODE_EXTERNALBUILDERS=[]\n",
                         b"CORE_CHAINCODE_SYSTEM_CSCC=disable\n",
                         b"CORE_PEER_TLS_CLIENTAUTHREQUIRED=false\n",
                         b"CORE_PEER_TLS_CLIENTCERT_FILE=/run/other/cert.pem\n",
                         b"CORE_PEER_TLS_CLIENTKEY_FILE=/run/other/key.pem\n"):
            peer.write_bytes(original + override)
            rejected = run("verify", m1_runtime, output_runtime, secrets_dir)
            assert rejected.returncode == 1 and "unexpected private env key" in rejected.stderr
        peer.write_bytes(original)
        print("PASS: private Peer env cannot override VM, builder, system chaincodes or TLS pair")

        rendered = output_runtime / "network-config/orderer0.yaml"
        original = rendered.read_bytes()
        rendered.write_bytes(original.replace(b"7050", b"7052", 1))
        changed = run("verify", m1_runtime, output_runtime, secrets_dir)
        assert changed.returncode == 1 and "rendered node config changed" in changed.stderr
        rendered.write_bytes(original)
        print("PASS: modified runtime node config rejected")

        os.chmod(peer, 0o644)
        unsafe_mode = run("verify", m1_runtime, output_runtime, secrets_dir)
        assert unsafe_mode.returncode == 1 and "file must be 0600" in unsafe_mode.stderr
        os.chmod(peer, 0o600)
        print("PASS: readable secret file rejected")

        untracked_output = ROOT / "network/m2-unignored-probe"
        assert not untracked_output.exists()
        unsafe_output = run("prepare", m1_runtime, untracked_output, secrets_dir)
        assert unsafe_output.returncode == 1 and "not Git-ignored" in unsafe_output.stderr
        assert not untracked_output.exists()
        print("PASS: unignored deployment output rejected before writing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
