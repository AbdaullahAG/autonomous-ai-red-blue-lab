import hashlib
import json
import os
import time
from dataclasses import dataclass

TRUST_DOMAIN = "ai-red-blue-lab.local"
LOG_PATH = "logs/evidence_log.jsonl"

@dataclass
class AgentIdentity:
    role: str
    instance_id: str

    @property
    def spiffe_id(self) -> str:
        return f"spiffe://{TRUST_DOMAIN}/{self.role}/{self.instance_id}"


def _last_hash() -> str:
    if not os.path.exists(LOG_PATH) or os.path.getsize(LOG_PATH) == 0:
        return "0" * 64
    with open(LOG_PATH, "r") as f:
        lines = [line for line in f if line.strip()]
    if not lines:
        return "0" * 64
    return json.loads(lines[-1])["record_hash"]


def log_action(
    agent: AgentIdentity,
    declared_purpose: str,
    action_taken: str,
    scope_used: str,
    authority_basis: str,
    outcome: str,
) -> dict:
    os.makedirs("logs", exist_ok=True)
    prev_hash = _last_hash()

    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agent_id": agent.spiffe_id,
        "declared_purpose": declared_purpose,
        "action_taken": action_taken,
        "scope_used": scope_used,
        "authority_basis": authority_basis,
        "outcome": outcome,
        "prev_hash": prev_hash,
    }

    record_str = json.dumps(record, sort_keys=True)
    record_hash = hashlib.sha256((prev_hash + record_str).encode()).hexdigest()
    record["record_hash"] = record_hash

    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")

    return record


def verify_chain() -> bool:
    if not os.path.exists(LOG_PATH):
        return True
    prev_hash = "0" * 64
    with open(LOG_PATH) as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            stored_hash = record.pop("record_hash")
            expected = hashlib.sha256(
                (prev_hash + json.dumps(record, sort_keys=True)).encode()
            ).hexdigest()
            if expected != stored_hash:
                return False
            prev_hash = stored_hash
    return True


def log_kill_switch(reason, n, attempts_log_refs):
    """
    يسجل حدث توقف قسري (kill-switch) بحقول إضافية محددة،
    مربوط بنفس سلسلة hash-chain عبر إضافته كـ action_taken منظم.
    """
    import json as _json
    event = {
        "event": "kill_switch_triggered",
        "reason": reason,
        "n": n,
        "attempts_log_ref": attempts_log_refs,
    }
    return log_action(
        agent=AgentIdentity(role="orchestrator", instance_id="system"),
        declared_purpose="enforce_containment_limit",
        action_taken=_json.dumps(event, sort_keys=True),
        scope_used="global",
        authority_basis="lab-safety-policy",
        outcome="halted",
    )
