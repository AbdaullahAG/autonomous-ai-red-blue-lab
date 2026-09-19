import os
import yaml
from core.identity import log_action

_POLICY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_scope.yaml")

with open(_POLICY_PATH) as f:
    _POLICY = yaml.safe_load(f)


class ScopeViolation(Exception):
    pass


def check_binary_allowed(agent, binary_name, target_url=""):
    """
    يتحقق أن binary/script معيّن مسموح لهذا الوكيل قبل أي subprocess.run.
    يسجل المحاولة دائماً (مسموحة أو مرفوضة) — القرار نفسه دليل Traceability.
    """
    rules = _POLICY.get(agent.role, {})
    denied = binary_name in rules.get("denied_binaries", [])
    allowed = binary_name in rules.get("allowed_binaries", [])

    permitted = allowed and not denied

    log_action(
        agent=agent,
        declared_purpose="scope_check",
        action_taken=f"requested_binary={binary_name} target={target_url}",
        scope_used=f"policy={agent.role}",
        authority_basis="agent_scope.yaml",
        outcome="permitted" if permitted else "denied_out_of_scope",
    )

    if not permitted:
        raise ScopeViolation(
            f"Agent '{agent.role}' is not permitted to use '{binary_name}'. "
            f"Denied by agent_scope.yaml — action blocked, not executed."
        )
    return True


def check_write_allowed(agent, file_path):
    """يتحقق أن الوكيل مسموح له يكتب على هذا الملف بالضبط قبل أي كتابة فعلية."""
    rules = _POLICY.get(agent.role, {})
    allowed_paths = rules.get("write_paths", [])
    denied_paths = rules.get("denied_paths", [])

    rel_path = os.path.relpath(file_path)

    is_denied = any(rel_path.startswith(d) for d in denied_paths)
    is_allowed = any(rel_path == a or rel_path.startswith(a) for a in allowed_paths)

    permitted = is_allowed and not is_denied

    log_action(
        agent=agent,
        declared_purpose="scope_check",
        action_taken=f"requested_write={rel_path}",
        scope_used=f"policy={agent.role}",
        authority_basis="agent_scope.yaml",
        outcome="permitted" if permitted else "denied_out_of_scope",
    )

    if not permitted:
        raise ScopeViolation(
            f"Agent '{agent.role}' is not permitted to write to '{rel_path}'. "
            f"Denied by agent_scope.yaml — write blocked, not executed."
        )
    return True
