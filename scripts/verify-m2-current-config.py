#!/usr/bin/env python3
"""Audit six decoded CONFIG JSON inputs against an approved decoded baseline."""

import argparse
import base64
import binascii
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path


NODES = ("orderer0", "orderer1", "orderer2",
         "peer0-seller", "peer0-buyer", "peer0-carrier")
INITIAL_SCRIPT = Path(__file__).with_name("verify-m2-initial-block.py")
spec = importlib.util.spec_from_file_location("m2_initial_block", INITIAL_SCRIPT)
initial_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(initial_audit)
require = initial_audit.require


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def decimal(value, label):
    require(not isinstance(value, bool) and str(value).isdigit(),
            f"{label}: expected nonnegative decimal")
    return int(value)


def der_length(length):
    if length < 128:
        return bytes((length,))
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes((0x80 | len(encoded),)) + encoded


def der_part(tag, content):
    return bytes((tag,)) + der_length(len(content)) + content


def block_header_hash(number, previous_hash, data_hash):
    encoded_number = number.to_bytes(max(1, (number.bit_length() + 7) // 8), "big")
    if encoded_number[0] & 0x80:
        encoded_number = b"\x00" + encoded_number
    sequence = (der_part(0x02, encoded_number) + der_part(0x04, previous_hash)
                + der_part(0x04, data_hash))
    return hashlib.sha256(der_part(0x30, sequence)).hexdigest()


def load_config_block(path, label):
    block = json.loads(path.read_text(), object_pairs_hook=unique_pairs)
    header = block["header"]
    number = decimal(header["number"], f"{label} block number")
    previous_hash = base64.b64decode(header["previous_hash"], validate=True)
    data_hash = base64.b64decode(header["data_hash"], validate=True)
    require(len(previous_hash) == (0 if number == 0 else 32)
            and len(data_hash) == 32, f"{label}: malformed block header hashes")
    envelopes = block["data"]["data"]
    require(len(envelopes) == 1, f"{label}: expected one CONFIG envelope")
    payload = envelopes[0]["payload"]
    channel_header = payload["header"]["channel_header"]
    require(channel_header["channel_id"] == "supplychannel"
            and channel_header["type"] == 1,
            f"{label}: wrong channel ID or envelope type")
    config = payload["data"]["config"]
    sequence = decimal(config["sequence"], f"{label} config sequence")
    require((number == 0) == (sequence == 0),
            f"{label}: block number/config sequence disagree on genesis status")
    group = config["channel_group"]
    require(set(group["groups"]) == {"Orderer", "Application"}
            and "Consortium" not in group["values"],
            f"{label}: not the expected application channel")
    return {
        "number": number,
        "sequence": sequence,
        "header": header,
        "header_hash": block_header_hash(number, previous_hash, data_hash),
        "data": block["data"],
        "group": group,
    }


def audit_approved_config(approved, m1_runtime, consenter_certs, inventory):
    channel = approved["group"]
    initial_audit.check_organizations(channel, m1_runtime / "public-msps")
    values = channel["groups"]["Orderer"]["values"]
    timeout = values["BatchTimeout"]["value"]["timeout"]
    require(isinstance(timeout, str) and re.fullmatch(r"[1-9][0-9]*(ms|s|m)", timeout),
            "approved BatchTimeout is not a positive duration")
    initial_audit.check_orderer(channel, consenter_certs, m1_runtime, inventory,
                                expected_batch_timeout=timeout)
    initial_audit.check_policies(channel)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initial-inspect", type=Path, required=True)
    parser.add_argument("--initial-sha256", required=True,
                        help="previously recorded SHA-256 of the original decoded block-0 JSON")
    parser.add_argument("--genesis-hash", required=True,
                        help="previously recorded Fabric block-0 header hash, not block-file SHA")
    parser.add_argument("--approved-config", type=Path, required=True,
                        help="decoded CONFIG block approved independently of these six fetches")
    parser.add_argument("--approved-sha256", required=True,
                        help="recorded SHA-256 of the approved decoded CONFIG block JSON")
    parser.add_argument("--current-dir", type=Path, required=True,
                        help="directory with <node>.config.json for exactly the six named nodes")
    parser.add_argument("--m1-runtime-dir", type=Path, required=True)
    parser.add_argument("--consenter-certs", type=Path, required=True)
    parser.add_argument("--inventory", type=Path,
                        default=Path("evidence/m1/issue-10-certificates.csv"))
    args = parser.parse_args()

    require(re.fullmatch(r"[0-9a-f]{64}", args.approved_sha256) is not None,
            "approved SHA-256 must be 64 lowercase hex digits")
    for name, value in (("initial SHA-256", args.initial_sha256),
                        ("genesis hash", args.genesis_hash)):
        require(re.fullmatch(r"[0-9a-f]{64}", value) is not None,
                f"{name} must be 64 lowercase hex digits")
    actual_sha = hashlib.sha256(args.approved_config.read_bytes()).hexdigest()
    require(actual_sha == args.approved_sha256, "approved CONFIG JSON hash differs")
    require(hashlib.sha256(args.initial_inspect.read_bytes()).hexdigest()
            == args.initial_sha256, "original decoded block-0 JSON hash differs")
    initial = load_config_block(args.initial_inspect, "original initial block")
    require(initial["number"] == 0 and initial["sequence"] == 0,
            "original initial input is not block 0/config sequence 0")
    require(initial["header_hash"] == args.genesis_hash,
            "original block-0 header hash differs from recorded genesis identity")
    approved = load_config_block(args.approved_config, "approved CONFIG block")
    if approved["number"] == 0:
        require(approved["header"] == initial["header"]
                and approved["data"] == initial["data"],
                "approved block 0 header/data differ from original #17 block")
    audit_approved_config(approved, args.m1_runtime_dir, args.consenter_certs,
                          initial_audit.cert_inventory(args.inventory))
    print("PASS: approved decoded CONFIG JSON SHA-256 pin, M1 public trust "
          "and M2 governance structure")

    expected_paths = [args.current_dir / f"{name}.config.json" for name in NODES]
    require(all(path.is_file() for path in expected_paths),
            "one or more of six decoded current CONFIG blocks is missing")
    require(len({(path.stat().st_dev, path.stat().st_ino)
                 for path in [args.approved_config, *expected_paths]}) == 7,
            "approved/config node inputs must be seven distinct files")
    for name, path in zip(NODES, expected_paths):
        current = load_config_block(path, name)
        require(current["number"] == approved["number"]
                and current["sequence"] == approved["sequence"],
                f"{name}: current CONFIG height or sequence differs from approved block")
        require(current["header"] == approved["header"]
                and current["data"] == approved["data"],
                f"{name}: current CONFIG header or data differs from approved block")
    print("PASS: six named decoded CONFIG JSON inputs match approved "
          f"block {approved['number']}, sequence {approved['sequence']}, "
          f"header hash {approved['header_hash']}")
    print("SCOPE: decoded JSON comparison only; raw BlockDataHash and raw-block-to-JSON "
          "provenance are not independently verified. Native fetch/decode evidence "
          "and independent review are required for a live PASS")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError,
            binascii.Error, AttributeError) as error:
        print(f"M2 current-CONFIG audit FAIL: {error}", file=sys.stderr)
        sys.exit(1)
