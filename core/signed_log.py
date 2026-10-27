"""Signed copy of the evidence log, and the anchor over it.

log_action() in core/identity.py writes every record to logs/evidence_log.jsonl
as before. When LAB_SIGNING_KEY_FILE names a producer key file, it also appends the
record to logs/signed_log.jsonl inside an Ed25519 envelope:

    {"kid": "producer", "record": {...the record, "chain": ..., "prev": ...}, "sig": ...}

``prev`` is the SHA-256 of the previous signed line, and the signature covers the
RFC 8785 bytes of ``record``. Someone who can edit the log but does not hold the
key can no longer change a record and recompute the chain: the edited record's
signature fails.

Signatures alone do not catch a deleted tail or a log rolled back to an older
copy, because every remaining record is still genuine. The anchor does: it signs
the digest and position of the newest record with a second key. Keep the anchor
key outside the container the agents run in, and take the anchor from there:

    python3 -m core.signed_log keygen producer.key   # prints the public key
    python3 -m core.signed_log keygen anchor.key
    LAB_SIGNING_KEY_FILE=producer.key python3 orchestrator.py
    python3 -m core.signed_log anchor --key anchor.key --producer-public <hex>
    python3 core/verify_signed_log.py logs/case.json

Key files hold a 32-byte Ed25519 seed as 64 hex characters.
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.verify_signed_log import GENESIS, jcs, sha256_hex

CHAIN = "spiffe://ai-red-blue-lab.local/evidence-log"
SIGNED_LOG_PATH = "logs/signed_log.jsonl"


class SignedLogError(Exception):
    """A key or log problem to report to the operator, not a bug."""


def load_key(path) -> Ed25519PrivateKey:
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
        seed = bytes.fromhex(text)
    except OSError as err:
        raise SignedLogError(f"cannot read key file {path}: {err.strerror or err}")
    except ValueError:
        raise SignedLogError(f"{path}: expected a 32-byte seed as 64 hex characters")
    if len(seed) != 32:
        raise SignedLogError(f"{path}: expected a 32-byte seed as 64 hex characters")
    return Ed25519PrivateKey.from_private_bytes(seed)


def public_hex(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return raw.hex()


def _envelope(body_key: str, body: dict, kid: str, key: Ed25519PrivateKey) -> bytes:
    signature = key.sign(jcs(body))
    return jcs({"kid": kid, body_key: body, "sig": base64.b64encode(signature).decode()})


def _lines(path) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        return [line for line in f.read().split(b"\n") if line]


def append(record: dict, key_path, log_path=SIGNED_LOG_PATH, chain=CHAIN) -> bytes:
    """Sign one record and append it to the signed log; returns the line written."""
    lines = _lines(log_path)
    body = dict(record, chain=chain, prev=sha256_hex(lines[-1]) if lines else GENESIS)
    line = _envelope("record", body, "producer", load_key(key_path))
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "ab") as f:
        f.write(line + b"\n")
    return line


def anchor(key_path, producer_public: str, log_path=SIGNED_LOG_PATH, chain=CHAIN) -> Path:
    """Sign the newest record's digest and position; write anchor.json and case.json beside the log."""
    lines = _lines(log_path)
    if not lines:
        raise SignedLogError(f"{log_path} holds no records to anchor")
    key = load_key(key_path)
    body = {
        "anchored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chain": chain,
        "head": sha256_hex(lines[-1]),
        "index": len(lines) - 1,
    }
    out = Path(log_path).parent
    (out / "anchor.json").write_bytes(_envelope("anchor", body, "anchor", key) + b"\n")
    case = {
        "anchor": "anchor.json",
        "chain": chain,
        "keys": {"anchor": public_hex(key), "producer": producer_public},
        "store": Path(log_path).name,
    }
    case_path = out / "case.json"
    case_path.write_text(json.dumps(case, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return case_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Signed evidence log keys and anchors")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("keygen", help="write a new Ed25519 seed and print its public key")
    gen.add_argument("path")
    anc = sub.add_parser("anchor", help="anchor the newest record of the signed log")
    anc.add_argument("--key", required=True, help="anchor key file")
    anc.add_argument("--producer-public", required=True, help="producer public key, hex")
    anc.add_argument("--log", default=SIGNED_LOG_PATH)
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (SignedLogError, FileExistsError) as err:
        print(f"signed_log: {err}", file=sys.stderr)
        return 1


def _run(args) -> int:
    if args.command == "keygen":
        key = Ed25519PrivateKey.generate()
        seed = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                 serialization.NoEncryption())
        fd = os.open(args.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(seed.hex() + "\n")
        print(public_hex(key))
        return 0
    print(anchor(args.key, args.producer_public, args.log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
