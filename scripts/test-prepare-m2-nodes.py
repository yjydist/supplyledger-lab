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
