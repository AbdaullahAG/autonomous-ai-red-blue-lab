#!/usr/bin/env python3
"""Verify a signed, anchored evidence log.

Usage: verify_signed_log.py CASE_JSON [--json]

CASE_JSON names the signed log (``store``), the anchor (``anchor``), the chain
identity (``chain``) and the two public keys a reader trusts (``keys.producer``
for the records, ``keys.anchor`` for the anchor). ``core/signed_log.py anchor``
writes one for this lab's log. The same file shape is the external-verifier
contract of the vectors-anchored-chain corpus in agent-evidence-vectors, so CI
runs this script against that corpus.

The checks run in this order and the first that fails is the reason:

1. every record's signature verifies under the producer key (signature_invalid)
2. the anchor's signature verifies under the anchor key (anchor_signature_invalid)
3. every record names this chain (record_from_other_chain)
4. every record names the SHA-256 of the line before it (chain_link_broken)
5. the record the anchor names is still in the log (anchored_head_missing)
6. that record's SHA-256 is the one the anchor signed (anchored_head_mismatch)

A log that passes all six prints ``verified`` with ``chain_anchored``, or with
``records_after_last_anchor`` when records follow the anchored one: those are
covered by the chain links only, until the next anchor. Exit 0 for verified,
1 for rejected.
"""

import base64
import hashlib
import json
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

GENESIS = "0" * 64


def jcs(value) -> bytes:
    """RFC 8785 bytes for the JSON this log holds: objects, arrays, strings,
    integers, booleans and null. Floats are refused rather than guessed at."""

    def check(v):
        if isinstance(v, float):
            raise ValueError("floats are not used in signed records")
        if isinstance(v, dict):
            for item in v.values():
                check(item)
        elif isinstance(v, list):
            for item in v:
                check(item)

    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def signed(envelope, body_key: str, public_hex: str) -> bool:
    if not isinstance(envelope, dict) or not isinstance(envelope.get(body_key), dict):
        return False
    try:
        signature = base64.b64decode(str(envelope.get("sig", "")), validate=True)
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex))
        key.verify(signature, jcs(envelope[body_key]))
    except (ValueError, InvalidSignature):
        return False
    return True


def verify(case_path: Path) -> dict:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    base = case_path.parent
    lines = [line for line in (base / case["store"]).read_bytes().split(b"\n") if line]
    anchor = json.loads((base / case["anchor"]).read_text(encoding="utf-8"))
    envelopes = [json.loads(line) for line in lines]
    producer, anchor_key = case["keys"]["producer"], case["keys"]["anchor"]

    if not all(signed(env, "record", producer) for env in envelopes):
        return {"decision": "rejected", "reason": "signature_invalid"}
    if not signed(anchor, "anchor", anchor_key):
        return {"decision": "rejected", "reason": "anchor_signature_invalid"}
    if any(env["record"].get("chain") != case["chain"] for env in envelopes):
        return {"decision": "rejected", "reason": "record_from_other_chain"}
    for i, env in enumerate(envelopes):
        if env["record"].get("prev") != (GENESIS if i == 0 else sha256_hex(lines[i - 1])):
            return {"decision": "rejected", "reason": "chain_link_broken"}
    index = anchor["anchor"]["index"]
    if index >= len(lines):
        return {"decision": "rejected", "reason": "anchored_head_missing"}
    if sha256_hex(lines[index]) != anchor["anchor"]["head"]:
        return {"decision": "rejected", "reason": "anchored_head_mismatch"}
    after = len(lines) - 1 - index
    return {"decision": "verified", "reason": "records_after_last_anchor" if after else "chain_anchored"}


def main(argv) -> int:
    args = [a for a in argv if a != "--json"]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    answer = verify(Path(args[0]))
    print(json.dumps(answer, sort_keys=True) if "--json" in argv else f"{answer['decision']} {answer['reason']}")
    return 0 if answer["decision"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
