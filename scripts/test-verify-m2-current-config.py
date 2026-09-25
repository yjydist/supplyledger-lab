#!/usr/bin/env python3
"""Synthetic decoded-CONFIG structure controls, not valid raw Fabric block fixtures."""

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


NODES = ("orderer0", "orderer1", "orderer2",
         "peer0-seller", "peer0-buyer", "peer0-carrier")
GENESIS_HASH = "5c68bf099e95b934b6034a4d7aa8c52442751c30bc8b56fcbbde9b0138e38ba7"


def config_group(block):
    return block["data"]["data"][0]["payload"]["data"]["config"]["channel_group"]


def write(path, block):
    path.write_text(json.dumps(block, sort_keys=True))


def case(label, initial_path, m1_runtime, consenter_certs, expected_mutation=None,
         node_mutation=None, success=False, failure_text="", synthetic_update=False,
         missing_node=False, bad_approved_hash=False, duplicate_node_key=False):
    initial = json.loads(initial_path.read_text())
    expected = copy.deepcopy(initial)
    if synthetic_update:
        expected["header"]["number"] = "2"
        expected["header"]["previous_hash"] = "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="
        expected["data"]["data"][0]["payload"]["data"]["config"]["sequence"] = 1
        expected["data"]["data"][0]["payload"]["data"]["last_update"] = {}
    if expected_mutation:
        expected_mutation(expected)
    with tempfile.TemporaryDirectory(prefix="supply-current-config-test-") as tmp:
        directory = Path(tmp)
        approved_path = directory / "approved.json"
        write(approved_path, expected)
        fetch_dir = directory / "fetch"
        fetch_dir.mkdir()
        for name in NODES:
            if missing_node and name == "peer0-carrier":
                continue
            node = copy.deepcopy(expected)
            if node_mutation and name == "peer0-carrier":
                node_mutation(node)
            node_path = fetch_dir / f"{name}.config.json"
            write(node_path, node)
            if duplicate_node_key and name == "peer0-carrier":
                node_path.write_text(node_path.read_text().replace(
                    '{"data":', '{"data": {}, "data":', 1))
        approved_sha = hashlib.sha256(approved_path.read_bytes()).hexdigest()
        if bad_approved_hash:
            approved_sha = "0" * 64
        command = [sys.executable, "scripts/verify-m2-current-config.py",
                   "--initial-inspect", str(initial_path),
                   "--initial-sha256", hashlib.sha256(initial_path.read_bytes()).hexdigest(),
                   "--genesis-hash", GENESIS_HASH,
                   "--approved-config", str(approved_path),
                   "--approved-sha256", approved_sha,
                   "--current-dir", str(fetch_dir),
                   "--m1-runtime-dir", str(m1_runtime),
                   "--consenter-certs", str(consenter_certs)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if success:
            assert result.returncode == 0, (label, result.stderr)
        else:
            assert result.returncode == 1 and failure_text in result.stderr, (
                label, result.returncode, result.stderr)
    print(f"PASS: synthetic {label} {'accepted' if success else 'rejected'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initial-inspect", type=Path, required=True)
    parser.add_argument("--m1-runtime-dir", type=Path, required=True)
    parser.add_argument("--consenter-certs", type=Path, required=True)
    args = parser.parse_args()
    base = (args.initial_inspect, args.m1_runtime_dir, args.consenter_certs)
    case("six matching block-0 fixtures", *base, success=True)
    case("decoded-only later CONFIG number/sequence structure", *base,
         synthetic_update=True, success=True)
    case("decoded-only 2s timeout governance structure (stale data_hash)", *base,
         synthetic_update=True, success=True,
         expected_mutation=lambda b: config_group(b)["groups"]["Orderer"]["values"]
         ["BatchTimeout"]["value"].update(timeout="2s"))
    case("wrong channel", *base, failure_text="wrong channel ID",
         node_mutation=lambda b: b["data"]["data"][0]["payload"]["header"]
         ["channel_header"].update(channel_id="otherchannel"))
    case("non-CONFIG envelope", *base, failure_text="envelope type",
         node_mutation=lambda b: b["data"]["data"][0]["payload"]["header"]
         ["channel_header"].update(type=2))
    case("different node block number", *base, failure_text="malformed block header hashes",
         node_mutation=lambda b: b["header"].update(number="1"))
    case("different node config sequence", *base, failure_text="genesis status",
         node_mutation=lambda b: b["data"]["data"][0]["payload"]["data"]
         ["config"].update(sequence=1))
    case("one-node batch timeout drift", *base, failure_text="data differs",
         node_mutation=lambda b: config_group(b)["groups"]["Orderer"]["values"]
         ["BatchTimeout"]["value"].update(timeout="2s"))
    case("missing Peer fetch", *base, failure_text="six decoded current CONFIG blocks is missing",
         missing_node=True)
    case("unapproved baseline hash", *base, failure_text="approved CONFIG JSON hash differs",
         bad_approved_hash=True)
    case("genesis CONFIG envelope tx ID drift", *base,
         failure_text="approved block 0 header/data differ",
         expected_mutation=lambda b: b["data"]["data"][0]["payload"]
         ["header"]["channel_header"].update(tx_id="forged-genesis-envelope"))
    case("duplicate decoded JSON key", *base, failure_text="duplicate JSON key",
         duplicate_node_key=True)
    case("approved ACL drift", *base, synthetic_update=True,
         failure_text="peer/Propose ACL",
         expected_mutation=lambda b: config_group(b)["groups"]["Application"]
         ["values"]["ACLs"]["value"]["acls"]["peer/Propose"].update(
             policy_ref="/Channel/Application/Writers"))
    case("approved mod_policy drift", *base, synthetic_update=True,
         failure_text="wrong group mod_policy",
         expected_mutation=lambda b: config_group(b)["groups"]["Application"].update(
             mod_policy="Writers"))
    case("approved consenter drift", *base, synthetic_update=True,
         failure_text="wrong Raft endpoint",
         expected_mutation=lambda b: config_group(b)["groups"]["Orderer"]
         ["values"]["ConsensusType"]["value"]["metadata"]["consenters"][0].update(
             host="other.orderer.supply.test"))
    case("approved founder omission", *base, synthetic_update=True,
         failure_text="wrong founder",
         expected_mutation=lambda b: config_group(b)["groups"]["Application"]
         ["groups"].pop("CarrierMSP"))
    case("approved extra Channel policy", *base, synthetic_update=True,
         failure_text="unexpected Channel policies",
         expected_mutation=lambda b: config_group(b)["policies"].update(
             Backdoor=copy.deepcopy(config_group(b)["policies"]["Readers"])))
    case("approved SHA3 Channel hashing", *base, synthetic_update=True,
         failure_text="wrong Channel hashing algorithm",
         expected_mutation=lambda b: config_group(b)["values"]
         ["HashingAlgorithm"]["value"].update(name="SHA3"))
    case("approved block-data hashing width drift", *base, synthetic_update=True,
         failure_text="wrong Channel block-data hashing structure",
         expected_mutation=lambda b: config_group(b)["values"]
         ["BlockDataHashingStructure"]["value"].update(width=7))
    case("approved Orderer ChannelRestrictions drift", *base, synthetic_update=True,
         failure_text="unexpected Orderer ChannelRestrictions value",
         expected_mutation=lambda b: config_group(b)["groups"]["Orderer"]
         ["values"]["ChannelRestrictions"].update(value={"max_count": 2}))


if __name__ == "__main__":
    main()
