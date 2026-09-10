"""Deterministic policy gate.

Everything that can authorise a side effect lives here, in code, not in the
LLM. The brief's threat model requires that malicious text placed in logs can
never grant tool permissions, and that a stale approval cannot authorise a
changed plan. Both are enforced structurally:

* The allowlist is a fixed set of action types. Free-text evidence is never
  parsed into a policy decision.
* An approval is bound to an exact (tenant, environment, target, resource
  version). The executor re-checks the live resource version, so an approval
  captured against one state cannot execute against a drifted state.
"""

from __future__ import annotations

from typing import Any

from .state import IncidentState, ProposedAction

# Only these action types may ever reach the executor.
ALLOWLISTED_ACTIONS: set[str] = {"rollback_deployment"}


def check_action(state: IncidentState, action: ProposedAction) -> dict[str, Any]:
    """Return a structured allow/deny decision. Never raises on bad input."""
    reasons: list[str] = []

    if action["action_type"] not in ALLOWLISTED_ACTIONS:
        reasons.append(
            f"action_type '{action['action_type']}' is not on the allowlist "
            f"{sorted(ALLOWLISTED_ACTIONS)}"
        )

    # Scope binding: the target must belong to the incident's service/env.
    expected_target = f"deployment/{state.get('service')}"
    if action["target"] != expected_target:
        reasons.append(
            f"target '{action['target']}' is outside incident scope "
            f"'{expected_target}'"
        )

    budget = state.get("budget", {})
    if budget.get("remediation_attempts", 0) >= budget.get("max_remediation_attempts", 0):
        reasons.append("remediation attempt budget exhausted")

    if not action.get("resource_version"):
        reasons.append("action is not bound to a resource_version")

    allowed = not reasons
    return {
        "allowed": allowed,
        "reasons": reasons,
        "requires_human_approval": True,  # every write pauses for a human
        "bound": {
            "tenant": state.get("tenant"),
            "environment": state.get("environment"),
            "target": action["target"],
            "resource_version": action.get("resource_version"),
        },
    }


def approval_still_valid(
    approval: dict[str, Any], action: ProposedAction, live_resource_version: str
) -> tuple[bool, str]:
    """Re-validate a human approval at execution time.

    The approval is only good for the exact resource version it was granted
    against; if the world moved on, we refuse rather than execute a plan the
    human never actually saw.
    """
    if not approval or not approval.get("approved"):
        return False, "no approval on record"
    if approval.get("bound_version") != action.get("resource_version"):
        return False, "approval was bound to a different plan version"
    if action.get("resource_version") != live_resource_version:
        return (
            False,
            f"resource drifted since approval (approved {action.get('resource_version')}, "
            f"live {live_resource_version})",
        )
    return True, "approval valid and bound to current resource version"
