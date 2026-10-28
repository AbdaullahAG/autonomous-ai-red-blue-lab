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


class SignedLogFixture(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)
        self.producer_public = _keygen(Path("producer.key"))
        _keygen(Path("anchor.key"))
        os.environ["LAB_SIGNING_KEY_FILE"] = "producer.key"
        red = identity.AgentIdentity(role="red-team", instance_id="test")
        for binary in ("nmap", "sqlmap", "curl"):
            identity.log_action(red, "scope_check", f"requested_binary={binary}",
                                "policy=red-team", "agent_scope.yaml", "permitted")
        identity.log_kill_switch("unsafe patch three times", 3, ["attempt-1", "attempt-2", "attempt-3"])

    def tearDown(self):
        os.environ.pop("LAB_SIGNING_KEY_FILE", None)
        os.chdir(self._cwd)
        self._tmp.cleanup()



class SignedLogTest(SignedLogFixture):
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
        os.environ.pop("LAB_SIGNING_KEY_FILE")
        identity.log_action(identity.AgentIdentity("red-team", "test"), "scope_check", "requested_binary=nmap",
                            "policy=red-team", "agent_scope.yaml", "permitted")
        self.assertFalse(os.path.exists(signed_log.SIGNED_LOG_PATH))


class VerifierFailsOnPurposeTest(SignedLogFixture):
    """Bad input is a rejection with a reason and a message on stderr, never a traceback."""

    def _run(self, case: Path):
        import subprocess, sys
        script = Path(self._cwd) / "core" / "verify_signed_log.py"
        return subprocess.run([sys.executable, str(script), str(case)], capture_output=True, text=True)

    def _case(self) -> Path:
        return signed_log.anchor("anchor.key", self.producer_public)

    def _assert_rejected(self, reason: str, case: Path):
        done = self._run(case)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertEqual(done.stdout.strip(), f"rejected {reason}")
        self.assertNotIn("Traceback", done.stderr)
        if reason.startswith(("input_", "key_")):
            self.assertTrue(done.stderr.strip(), "a message names the cause")

    def _edit_case(self, **changes) -> Path:
        case = self._case()
        data = json.loads(case.read_text())
        for key, value in changes.items():
            if value is None:
                data["keys"].pop(key, None)
            else:
                data["keys"][key] = value
        case.write_text(json.dumps(data))
        return case

    def test_missing_public_key(self):
        self._assert_rejected("key_missing", self._edit_case(producer=None))

    def test_invalid_public_key(self):
        self._assert_rejected("key_invalid", self._edit_case(anchor="not-hex"))

    def test_missing_case_file(self):
        self._assert_rejected("input_unreadable", Path("nowhere.json"))

    def test_unreadable_store(self):
        case = self._case()
        os.remove(signed_log.SIGNED_LOG_PATH)
        self._assert_rejected("input_unreadable", case)

    def test_malformed_line(self):
        case = self._case()
        with open(signed_log.SIGNED_LOG_PATH, "ab") as f:
            f.write(b"{this is not json\n")
        self._assert_rejected("input_malformed", case)

    def test_malformed_anchor(self):
        case = self._case()
        Path("logs/anchor.json").write_text("[]")
        self._assert_rejected("input_malformed", case)

    def test_bad_signature(self):
        case = self._case()
        path = Path(signed_log.SIGNED_LOG_PATH)
        envelope = json.loads(path.read_bytes().split(b"\n")[0])
        envelope["sig"] = "AAAA"
        lines = path.read_bytes().split(b"\n")
        lines[0] = signed_log.jcs(envelope)
        path.write_bytes(b"\n".join(lines))
        self._assert_rejected("signature_invalid", case)

    def test_missing_signing_key_file_is_a_clear_error(self):
        os.environ["LAB_SIGNING_KEY_FILE"] = "absent.key"
        with self.assertRaises(signed_log.SignedLogError) as caught:
            identity.log_action(identity.AgentIdentity("red-team", "test"), "p", "a", "s", "b", "permitted")
        self.assertIn("absent.key", str(caught.exception))

    def test_missing_signing_key_file_writes_no_unsigned_record(self):
        before = Path(identity.LOG_PATH).read_bytes()
        signed_before = Path(signed_log.SIGNED_LOG_PATH).read_bytes()
        os.environ["LAB_SIGNING_KEY_FILE"] = "absent.key"
        with self.assertRaises(signed_log.SignedLogError):
            identity.log_action(identity.AgentIdentity("red-team", "test"), "p", "a", "s", "b", "permitted")
        self.assertEqual(Path(identity.LOG_PATH).read_bytes(), before)
        self.assertEqual(Path(signed_log.SIGNED_LOG_PATH).read_bytes(), signed_before)

    def test_unreadable_and_malformed_key_files(self):
        Path("bad.key").write_text("zz\n")
        with self.assertRaises(signed_log.SignedLogError):
            signed_log.load_key("bad.key")
        os.chmod("producer.key", 0)
        try:
            if os.access("producer.key", os.R_OK):
                self.skipTest("running as a user that ignores file modes")
            with self.assertRaises(signed_log.SignedLogError):
                signed_log.load_key("producer.key")
        finally:
            os.chmod("producer.key", 0o600)

    def test_anchor_command_reports_a_missing_key_without_a_traceback(self):
        with contextlib.redirect_stderr(open(os.devnull, "w")):
            self.assertEqual(signed_log.main(["anchor", "--key", "absent.key", "--producer-public", "00"]), 1)


if __name__ == "__main__":
    unittest.main()
