"""The signed log catches the edits the unsigned hash chain cannot.

Run from the repository root: python3 -m unittest discover -s tests -t .
"""

import contextlib
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from core import identity, signed_log
from core.verify_signed_log import verify


def _keygen(path: Path) -> str:
    with open(os.devnull, "w") as quiet, contextlib.redirect_stdout(quiet):
        signed_log.main(["keygen", str(path)])
    return signed_log.public_hex(signed_log.load_key(path))


class SignedLogTest(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)
        self.producer_public = _keygen(Path("producer.key"))
        _keygen(Path("anchor.key"))
        os.environ["LAB_SIGNING_KEY"] = "producer.key"
        red = identity.AgentIdentity(role="red-team", instance_id="test")
        for binary in ("nmap", "sqlmap", "curl"):
            identity.log_action(red, "scope_check", f"requested_binary={binary}",
                                "policy=red-team", "agent_scope.yaml", "permitted")
        identity.log_kill_switch("unsafe patch three times", 3, ["attempt-1", "attempt-2", "attempt-3"])

    def tearDown(self):
        os.environ.pop("LAB_SIGNING_KEY", None)
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def _anchor_and_verify(self) -> dict:
        case = signed_log.anchor("anchor.key", self.producer_public)
        return verify(case)

    def test_honest_log_verifies(self):
        self.assertTrue(identity.verify_chain())
        self.assertEqual(self._anchor_and_verify(), {"decision": "verified", "reason": "chain_anchored"})

    def test_rechained_kill_switch_edit_passes_the_hash_chain_and_fails_the_signature(self):
        # The edit: the kill-switch record's outcome changed from halted to permitted, and both
        # chains recomputed from that record on, as anyone who can write the log can do.
        case = signed_log.anchor("anchor.key", self.producer_public)
        records = [json.loads(line) for line in Path(identity.LOG_PATH).read_text().splitlines() if line]
        signed_path = Path(signed_log.SIGNED_LOG_PATH)
        envelopes = [json.loads(line) for line in signed_path.read_bytes().split(b"\n") if line]
        self.assertEqual([r["outcome"] for r in records].count("halted"), 1)
        prev_hash, lines, edited = "0" * 64, [], []
        for record, envelope in zip(records, envelopes):
            record.pop("record_hash")
            record["prev_hash"] = prev_hash
            if record["outcome"] == "halted":
                record["outcome"] = "permitted"
            record["record_hash"] = hashlib.sha256((prev_hash + json.dumps(record, sort_keys=True)).encode()).hexdigest()
            prev_hash = record["record_hash"]
            edited.append(json.dumps(record, sort_keys=True))
            body = dict(record, chain=signed_log.CHAIN,
                        prev=signed_log.sha256_hex(lines[-1]) if lines else signed_log.GENESIS)
            # Without the producer key the old signature is all the editor has.
            lines.append(signed_log.jcs({"kid": "producer", "record": body, "sig": envelope["sig"]}))
        Path(identity.LOG_PATH).write_text("".join(line + "\n" for line in edited))
        signed_path.write_bytes(b"".join(line + b"\n" for line in lines))
        self.assertTrue(identity.verify_chain(), "the unsigned hash chain accepts the edit")
        self.assertEqual(verify(case), {"decision": "rejected", "reason": "signature_invalid"})

    def test_tail_removal_before_the_anchor_is_caught_by_the_anchor(self):
        case = signed_log.anchor("anchor.key", self.producer_public)
        path = Path(signed_log.SIGNED_LOG_PATH)
        path.write_bytes(b"".join(line + b"\n" for line in path.read_bytes().split(b"\n")[:-2] if line))
        self.assertEqual(verify(case), {"decision": "rejected", "reason": "anchored_head_missing"})

    def test_records_after_the_anchor_are_reported(self):
        case = signed_log.anchor("anchor.key", self.producer_public)
        identity.log_action(identity.AgentIdentity("blue-team", "test"), "patch", "wrote webapp/app.py",
                            "policy=blue-team", "agent_scope.yaml", "permitted")
        self.assertEqual(verify(case), {"decision": "verified", "reason": "records_after_last_anchor"})

    def test_no_signed_log_without_a_key(self):
        os.remove(signed_log.SIGNED_LOG_PATH)
        os.environ.pop("LAB_SIGNING_KEY")
        identity.log_action(identity.AgentIdentity("red-team", "test"), "scope_check", "requested_binary=nmap",
                            "policy=red-team", "agent_scope.yaml", "permitted")
        self.assertFalse(os.path.exists(signed_log.SIGNED_LOG_PATH))


if __name__ == "__main__":
    unittest.main()
