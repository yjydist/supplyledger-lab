#!/usr/bin/env python3
"""Audit the native Fabric 3.1.5 initial CONFIG block without a running channel."""

import argparse
import base64
import csv
import hashlib
import itertools
import json
import ssl
import sys
from pathlib import Path


FOUNDERS = ("SellerMSP", "BuyerMSP", "CarrierMSP")
ORG_NAMES = {"SellerMSP": "seller", "BuyerMSP": "buyer",
             "CarrierMSP": "carrier", "OrdererMSP": "orderer"}
ORDERERS = tuple(f"orderer{number}" for number in range(3))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decoded(value):
    return base64.b64decode(value, validate=True)


def config_group(block):
    require(block["header"]["number"] == "0" and block["header"]["previous_hash"] == "",
            "input is not an initial block 0")
    require(len(block["data"]["data"]) == 1, "expected one CONFIG envelope")
    payload = block["data"]["data"][0]["payload"]
    header = payload["header"]["channel_header"]
    require(header["channel_id"] == "supplychannel" and header["type"] == 1,
            "wrong channel ID or envelope type")
    require(payload["data"].get("last_update") is None, "unexpected channel update")
    group = payload["data"]["config"]["channel_group"]
    require(set(group["groups"]) == {"Orderer", "Application"},
            "not an application channel with exactly Orderer and Application groups")
    require("Consortium" not in group["values"] and "Consortiums" not in group["groups"],
            "system-channel consortium material is present")
    print("PASS: supplychannel initial CONFIG block 0; no consortium or system channel")
    return group


def signature_policy(group, name, expected_identities, allowed):
    policy = group["policies"][name]["policy"]
    require(policy["type"] == 1, f"{name}: expected Signature policy")
    value = policy["value"]
    identities = []
    for item in value["identities"]:
        require(item["principal_classification"] == "ROLE",
                f"{name}: non-role principal")
        principal = item["principal"]
        identities.append((principal["msp_identifier"], principal["role"]))
    require(len(identities) == len(set(identities))
            and set(identities) == set(expected_identities),
            f"{name}: wrong or duplicate signature principals")

    def permits(rule, signers):
        if set(rule) == {"signed_by"}:
            index = rule["signed_by"]
            require(0 <= index < len(identities), f"{name}: invalid signed_by index")
            return identities[index] in signers
        require(set(rule) == {"n_out_of"}, f"{name}: unknown signature rule")
        threshold = rule["n_out_of"]
        require(0 <= threshold["n"] <= len(threshold["rules"]),
                f"{name}: invalid threshold")
        return sum(permits(child, signers) for child in threshold["rules"]) >= threshold["n"]

    for size in range(len(identities) + 1):
        for subset in itertools.combinations(identities, size):
            signers = set(subset)
            require(permits(value["rule"], signers) == allowed(signers),
                    f"{name}: encoded signature threshold differs for {sorted(signers)}")


def implicit_policy(group, name, rule, sub_policy):
    policy = group["policies"][name]["policy"]
    require(policy["type"] == 3
            and policy["value"] == {"rule": rule, "sub_policy": sub_policy},
            f"{name}: wrong ImplicitMeta policy")


def assert_mod_policies(group, label="Channel"):
    require(group["mod_policy"] == "Admins", f"{label}: wrong group mod_policy")
    for kind in ("policies", "values"):
        for name, entry in group.get(kind, {}).items():
            require(entry["mod_policy"] == "Admins",
                    f"{label}/{kind}/{name}: wrong mod_policy")
    for name, child in group.get("groups", {}).items():
        assert_mod_policies(child, f"{label}/{name}")


def cert_inventory(path):
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    return {row["identity"]: row for row in rows}


def check_msp(group, msp_id, public_msps):
    msp = group["values"]["MSP"]["value"]
    require(msp["type"] == 0, f"{msp_id}: wrong MSP type")
    config = msp["config"]
    require(config["name"] == msp_id, f"{msp_id}: encoded MSP name differs")
    require(config["signing_identity"] is None and config["admins"] == [],
            f"{msp_id}: signer/admin leaf embedded in public MSP")
    for key in ("intermediate_certs", "tls_intermediate_certs", "revocation_list"):
        require(config[key] == [], f"{msp_id}: unexpected {key}")
    org = ORG_NAMES[msp_id]
    root = (public_msps / msp_id / "msp" / "cacerts"
            / f"{org}-enroll-ca.pem").read_bytes()
    tls_root = (public_msps / msp_id / "msp" / "tlscacerts"
                / f"{org}-tls-ca.pem").read_bytes()
    require([decoded(item) for item in config["root_certs"]] == [root],
            f"{msp_id}: encoded Enrollment root differs")
    require([decoded(item) for item in config["tls_root_certs"]] == [tls_root],
            f"{msp_id}: encoded TLS root differs")
    node_ous = config["fabric_node_ous"]
    require(node_ous["enable"] is True, f"{msp_id}: NodeOUs disabled")
    for role in ("client", "peer", "admin", "orderer"):
        item = node_ous[f"{role}_ou_identifier"]
        require(decoded(item["certificate"]) == root and item["organizational_unit_identifier"] == role,
                f"{msp_id}: {role} OU is not bound to its Enrollment root")


def check_organizations(channel, public_msps):
    application = channel["groups"]["Application"]
    orderer = channel["groups"]["Orderer"]
    require(set(application["groups"]) == set(FOUNDERS)
            and set(orderer["groups"]) == {"OrdererMSP"},
            "wrong founder/Orderer organization set")
    for msp_id in FOUNDERS:
        group = application["groups"][msp_id]
        require(set(group["values"]) == {"MSP", "AnchorPeers"},
                f"{msp_id}: unexpected organization value")
        require(set(group["policies"]) == {"Readers", "Writers", "Admins", "Endorsement"},
                f"{msp_id}: unexpected organization policy")
        check_msp(group, msp_id, public_msps)
        org = ORG_NAMES[msp_id]
        require(group["values"]["AnchorPeers"]["value"] == {
            "anchor_peers": [{"host": f"peer0.{org}.supply.test", "port": 7051}]},
            f"{msp_id}: wrong anchor Peer")
        readers_writers = [(msp_id, role) for role in ("ADMIN", "CLIENT", "PEER")]
        for policy in ("Readers", "Writers"):
            signature_policy(group, policy, readers_writers, lambda signers: bool(signers))
        signature_policy(group, "Admins", [(msp_id, "ADMIN")], lambda signers: bool(signers))
        signature_policy(group, "Endorsement", [(msp_id, "PEER")], lambda signers: bool(signers))
    group = orderer["groups"]["OrdererMSP"]
    require(set(group["values"]) == {"MSP", "Endpoints"},
            "OrdererMSP: unexpected organization value")
    require(set(group["policies"]) == {"Readers", "Writers", "Admins", "Endorsement"},
            "OrdererMSP: unexpected organization policy")
    check_msp(group, "OrdererMSP", public_msps)
    require(group["values"]["Endpoints"]["value"] == {
        "addresses": [f"{name}.orderer.supply.test:7050" for name in ORDERERS]},
        "Orderer endpoints differ from three consenters")
    for policy in ("Readers", "Writers"):
        signature_policy(group, policy,
                         [("OrdererMSP", "ADMIN"), ("OrdererMSP", "ORDERER")],
                         lambda signers: bool(signers))
    signature_policy(group, "Admins", [("OrdererMSP", "ADMIN")],
                     lambda signers: bool(signers))
    signature_policy(group, "Endorsement", [("OrdererMSP", "ORDERER")],
                     lambda signers: bool(signers))
    print("PASS: four public MSPs match M1 roots and NodeOUs; three exact anchor Peers and Orderer endpoints")


def check_orderer(channel, consenter_certs, m1_runtime, inventory,
                  expected_batch_timeout="1s"):
    orderer = channel["groups"]["Orderer"]
    values = orderer["values"]
    require(set(values) == {"BatchSize", "BatchTimeout", "Capabilities",
                            "ChannelRestrictions", "ConsensusType"},
            "Orderer values differ from reviewed initial set")
    require(values["ChannelRestrictions"]["value"] is None,
            "unexpected Orderer ChannelRestrictions value")
    require(values["BatchTimeout"]["value"] == {"timeout": expected_batch_timeout},
            "wrong BatchTimeout")
    require(values["BatchSize"]["value"] == {
        "max_message_count": 20, "preferred_max_bytes": 524288,
        "absolute_max_bytes": 10485760}, "wrong Orderer batch limits")
    require(set(values["Capabilities"]["value"]["capabilities"]) == {"V2_0"},
            "wrong Orderer capability")
    consensus = values["ConsensusType"]["value"]
    require(consensus["type"] == "etcdraft" and consensus["state"] == "STATE_NORMAL",
            "not normal Raft consensus")
    metadata = consensus["metadata"]
    require(metadata["options"] == {
        "tick_interval": "500ms", "election_tick": 10, "heartbeat_tick": 1,
        "max_inflight_blocks": 5, "snapshot_interval_size": 16777216},
        "unexpected Raft options")
    consenters = metadata["consenters"]
    require(len(consenters) == 3, "expected three Raft consenters")
    for name, consenter in zip(ORDERERS, consenters):
        expected_host = f"{name}.orderer.supply.test"
        pem = (consenter_certs / f"{name}.pem").read_bytes()
        original_pem = (m1_runtime / "identities" / "orderer" / f"{name}-tls"
                        / "msp" / "signcerts" / "cert.pem").read_bytes()
        require(pem == original_pem, f"{name}: staged PEM differs from M1 signcert bytes")
        require(consenter["host"] == expected_host and consenter["port"] == 7050,
                f"{name}: wrong Raft endpoint")
        require(decoded(consenter["client_tls_cert"]) == pem
                and decoded(consenter["server_tls_cert"]) == pem,
                f"{name}: consenter client/server certificate bytes differ from M1 leaf")
        row = inventory[f"{name}-tls"]
        der = ssl.PEM_cert_to_DER_cert(pem.decode("ascii"))
        require(hashlib.sha256(der).hexdigest() == row["cert_sha256"].replace(":", "").lower()
                and row["san"] == f"DNS:{expected_host}"
                and "TLS Web Server Authentication" in row["extended_key_usage"]
                and "TLS Web Client Authentication" in row["extended_key_usage"],
                f"{name}: M1 certificate pin, SAN or TLS use differs")
    print("PASS: three byte-pinned Raft client/server cert pairs; "
          f"{expected_batch_timeout}/20/512KiB/10MiB batch limits")


def check_policies(channel):
    application = channel["groups"]["Application"]
    orderer = channel["groups"]["Orderer"]
    require(set(channel["policies"]) == {"Readers", "Writers", "Admins"},
            "unexpected Channel policies")
    require(set(orderer["policies"]) == {"Readers", "Writers", "Admins", "BlockValidation"},
            "unexpected Orderer policies")
    require(set(application["policies"]) == {"Readers", "Writers", "Admins",
                                              "Endorsement", "LifecycleEndorsement"},
            "unexpected Application policies")
    require(set(channel["values"]) == {"Capabilities", "HashingAlgorithm",
                                       "BlockDataHashingStructure"},
            "unexpected Channel values")
    require(set(application["values"]) == {"Capabilities", "ACLs"},
            "unexpected Application values")
    require(channel["values"]["HashingAlgorithm"]["value"] == {"name": "SHA256"},
            "wrong Channel hashing algorithm")
    require(channel["values"]["BlockDataHashingStructure"]["value"] == {
        "width": 4294967295}, "wrong Channel block-data hashing structure")
    require(set(channel["values"]["Capabilities"]["value"]["capabilities"]) == {"V3_0"},
            "wrong Channel capability")
    require(set(application["values"]["Capabilities"]["value"]["capabilities"]) == {"V2_5"},
            "wrong Application capability")
    require(application["values"]["ACLs"]["value"] == {
        "acls": {"peer/Propose": {"policy_ref": "/Channel/Application/Readers"}}},
            "peer/Propose ACL differs from Readers")
    for group in (channel, application, orderer):
        implicit_policy(group, "Readers", "ANY", "Readers")
        implicit_policy(group, "Writers", "ANY", "Writers")
    implicit_policy(orderer, "BlockValidation", "ANY", "Writers")
    founder_admins = [(name, "ADMIN") for name in FOUNDERS]
    founder_peers = [(name, "PEER") for name in FOUNDERS]
    signature_policy(application, "Admins", founder_admins,
                     lambda signers: len(signers) >= 2)
    signature_policy(application, "LifecycleEndorsement", founder_peers,
                     lambda signers: len(signers) >= 2)
    signature_policy(application, "Endorsement", founder_peers[:2],
                     lambda signers: len(signers) == 2)
    signature_policy(orderer, "Admins", [("OrdererMSP", "ADMIN")],
                     lambda signers: bool(signers))
    signature_policy(channel, "Admins", founder_admins + [("OrdererMSP", "ADMIN")],
                     lambda signers: ("OrdererMSP", "ADMIN") in signers
                     and len(signers.intersection(founder_admins)) >= 2)
    assert_mod_policies(channel)
    print("PASS: V3_0/V2_0/V2_5, founder governance/endorsement, Readers ACL and all mod_policy=Admins")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect-block", type=Path, required=True)
    parser.add_argument("--m1-runtime-dir", type=Path, required=True)
    parser.add_argument("--consenter-certs", type=Path, required=True)
    parser.add_argument("--inventory", type=Path,
                        default=Path("evidence/m1/issue-10-certificates.csv"))
    args = parser.parse_args()
    block = json.loads(args.inspect_block.read_text())
    channel = config_group(block)
    check_organizations(channel, args.m1_runtime_dir / "public-msps")
    check_orderer(channel, args.consenter_certs, args.m1_runtime_dir,
                  cert_inventory(args.inventory))
    check_policies(channel)
    print("NOT RUN: current channel config, live MSP enforcement and full T-NET-03 await #18")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as error:
        print(f"M2 initial-block audit FAIL: {error}", file=sys.stderr)
        sys.exit(1)
