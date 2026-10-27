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
1 for rejected. A missing or unreadable file, a malformed line or a missing or invalid
public key is also a rejection (input_unreadable, input_malformed, key_missing,
key_invalid) with the cause on stderr, never a traceback.
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


class Rejected(Exception):
    """Input the verifier cannot check: reported as a rejection, never as a traceback."""

    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason, self.detail = reason, detail


def _read(path: Path, what: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as err:
        raise Rejected("input_unreadable", f"cannot read {what} {path}: {err.strerror or err}")


def _json(data: bytes, what: str):
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as err:
        raise Rejected("input_malformed", f"{what} is not valid JSON: {err}")


def _public_key(case: dict, name: str) -> str:
    keys = case.get("keys") if isinstance(case, dict) else None
    value = keys.get(name) if isinstance(keys, dict) else None
    if value is None or value == "":
        raise Rejected("key_missing", f"case.json has no {name} public key")
    try:
        if not isinstance(value, str) or len(bytes.fromhex(value)) != 32:
            raise ValueError
    except ValueError:
        raise Rejected("key_invalid", f"the {name} public key is not 64 hex characters")
    return value


def _load(case_path: Path):
    case = _json(_read(case_path, "case file"), "case file")
    if not isinstance(case, dict) or not all(isinstance(case.get(k), str) for k in ("store", "anchor", "chain")):
        raise Rejected("input_malformed", "case file needs string fields store, anchor and chain")
    producer, anchor_key = _public_key(case, "producer"), _public_key(case, "anchor")
    base = case_path.parent
    lines = [line for line in _read(base / case["store"], "signed log").split(b"\n") if line]
    envelopes = []
    for number, line in enumerate(lines, 1):
        envelope = _json(line, f"signed log line {number}")
        if not isinstance(envelope, dict):
            raise Rejected("input_malformed", f"signed log line {number} is not a JSON object")
        envelopes.append(envelope)
    anchor = _json(_read(base / case["anchor"], "anchor file"), "anchor file")
    body = anchor.get("anchor") if isinstance(anchor, dict) else None
    if not isinstance(body, dict) or not isinstance(body.get("index"), int) or not isinstance(body.get("head"), str):
        raise Rejected("input_malformed", "anchor file needs an anchor object with integer index and string head")
    return case, lines, envelopes, anchor, producer, anchor_key


def verify(case_path: Path) -> dict:
    try:
        return _verify(case_path)
    except Rejected as err:
        return {"decision": "rejected", "reason": err.reason, "detail": err.detail}


def _verify(case_path: Path) -> dict:
    case, lines, envelopes, anchor, producer, anchor_key = _load(case_path)

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
    detail = answer.pop("detail", None)
    print(json.dumps(answer, sort_keys=True) if "--json" in argv else f"{answer['decision']} {answer['reason']}")
    if detail:
        print(f"verify_signed_log: {detail}", file=sys.stderr)
    return 0 if answer["decision"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
