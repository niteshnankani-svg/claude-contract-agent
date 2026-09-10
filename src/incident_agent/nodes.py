"""The graph nodes.

Each node is a pure-ish function ``(state) -> partial_state``. Side effects on
the cluster happen only in ``executor``. The nodes map one-to-one onto the
LangGraph design in the decision brief:

1. intake            - authenticate scope, deduplicate the alert
2. plan              - pick the next discriminating check
3. collect           - run the chosen read tool (telemetry/deployment/topology)
4. diagnose          - update supported/contradicted hypotheses
5. remediation_plan  - propose an allowlisted action with a compensation
6. policy_check      - deterministic scope/version/budget gate
7. human_review      - durable interrupt for approval  (see graph.py)
8. executor          - idempotent apply + reconcile
9. verifier          - observe a recovery window via an app-level probe
"""

from __future__ import annotations

import hashlib
from typing import Any

from .environment import FakeCluster
from .policy import approval_still_valid, check_action
from .reasoner import Reasoner
from .state import IncidentState, new_budget
from .tools import (
    collect_deployment,
    collect_telemetry,
    collect_topology,
    execute_rollback,
    run_probe,
)


def _dedup_key(alert: dict[str, Any]) -> str:
    raw = f"{alert.get('service')}|{alert.get('signal')}|{alert.get('environment')}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


class Nodes:
    """Bundles the cluster + reasoner so nodes stay closures over injected deps."""

    def __init__(self, cluster: FakeCluster, reasoner: Reasoner):
        self.cluster = cluster
        self.reasoner = reasoner

    # 1 -------------------------------------------------------------------
    def intake(self, state: IncidentState) -> IncidentState:
        alert = state["alert"]
        dedup = _dedup_key(alert)
        return {
            "incident_id": state.get("incident_id") or f"INC-{dedup}",
            "dedup_key": dedup,
            "tenant": alert["tenant"],
            "environment": alert["environment"],
            "service": alert["service"],
            "time_window_minutes": alert.get("window_minutes", 15),
            "hypotheses": [],
            "budget": new_budget(),
            "status": "investigating",
            "timeline": [
                f"intake: {alert['service']} in {alert['environment']} "
                f"(tenant={alert['tenant']}), dedup={dedup}"
            ],
        }

    # 2 -------------------------------------------------------------------
    def plan(self, state: IncidentState) -> IncidentState:
        nxt = self.reasoner.plan_next_check(state)
        return {"next_check": nxt, "timeline": [f"plan: next_check={nxt}"]}

    # 3 -------------------------------------------------------------------
    def collect(self, state: IncidentState) -> IncidentState:
        kind = state.get("next_check")
        svc = state["service"]
        if kind == "telemetry":
            obs = collect_telemetry(self.cluster, svc, state["time_window_minutes"])
        elif kind == "deployment":
            obs = collect_deployment(self.cluster, svc)
        elif kind == "topology":
            obs = collect_topology(self.cluster, svc)
        else:  # defensive; router should not send us here
            return {"timeline": ["collect: nothing to do"]}
        budget = state.get("budget", {})
        return {
            "observations": [obs],
            "budget": {"investigation_steps": budget.get("investigation_steps", 0) + 1},
            "timeline": [f"collect[{kind}]: {obs['summary']}"],
        }

    # 4 -------------------------------------------------------------------
    def diagnose(self, state: IncidentState) -> IncidentState:
        hyps = self.reasoner.update_hypotheses(state)
        leading = max(hyps, key=lambda h: h["confidence"], default=None)
        line = (
            f"diagnose: leading={leading['id']}@{leading['confidence']:.2f} "
            f"({leading['status']})" if leading else "diagnose: no hypothesis yet"
        )
        return {"hypotheses": hyps, "timeline": [line]}

    # 5 -------------------------------------------------------------------
    def remediation_plan(self, state: IncidentState) -> IncidentState:
        action = self.reasoner.propose_remediation(state)
        if action is None:
            return {
                "status": "escalated",
                "outcome": "no confident, allowlisted remediation available",
                "timeline": ["remediation_plan: none -> escalate"],
            }
        return {
            "proposed_action": action,
            "timeline": [f"remediation_plan: {action['action_type']} -> {action['params']}"],
        }

    # 6 -------------------------------------------------------------------
    def policy_check(self, state: IncidentState) -> IncidentState:
        action = state["proposed_action"]
        decision = check_action(state, action)
        if not decision["allowed"]:
            return {
                "policy_decision": decision,
                "status": "escalated",
                "outcome": f"policy denied: {decision['reasons']}",
                "timeline": [f"policy_check: DENY {decision['reasons']}"],
            }
        return {
            "policy_decision": decision,
            "status": "awaiting_approval",
            "timeline": ["policy_check: allowed, pending human approval"],
        }

    # 8 -------------------------------------------------------------------
    def executor(self, state: IncidentState) -> IncidentState:
        action = state["proposed_action"]
        approval = state.get("approval") or {}
        live_rv = self.cluster.resource_version(state["service"])

        ok, why = approval_still_valid(approval, action, live_rv)
        if not ok:
            return {
                "status": "escalated",
                "outcome": f"execution blocked: {why}",
                "timeline": [f"executor: refused ({why})"],
            }

        # Deterministic idempotency key: same plan + same version => same key,
        # so a replay or restart de-duplicates instead of double-applying.
        idem = hashlib.sha1(
            f"{state['incident_id']}|{action['target']}|{action['resource_version']}"
            f"|{action['params']}".encode()
        ).hexdigest()[:16]

        record = execute_rollback(self.cluster, action, idem)
        budget = state.get("budget", {})
        status = "verifying" if record["status"] in ("succeeded", "deduplicated") else "escalated"
        return {
            "action_ledger": [record],
            "status": status,
            "budget": {"remediation_attempts": budget.get("remediation_attempts", 0) + 1},
            "timeline": [f"executor: {record['status']} - {record['detail']}"],
        }

    # 9 -------------------------------------------------------------------
    def verifier(self, state: IncidentState) -> IncidentState:
        # Fresh, application-level measurement — a control-plane 200 is not enough.
        probe = run_probe(self.cluster, state["service"])
        metrics = collect_telemetry(self.cluster, state["service"], state["time_window_minutes"])
        recovered = (
            probe["data"]["synthetic_checkout_ok"]
            and metrics["data"]["error_rate"] < 0.05
        )
        verification = {
            "recovered": recovered,
            "probe": probe["data"],
            "metrics": metrics["data"],
        }
        if recovered:
            return {
                "observations": [probe, metrics],
                "verification": verification,
                "status": "resolved",
                "outcome": "recovery confirmed by synthetic probe and error-rate window",
                "timeline": ["verifier: RECOVERED (probe ok, error_rate normal)"],
            }
        budget = state.get("budget", {})
        exhausted = budget.get("remediation_attempts", 0) >= budget.get("max_remediation_attempts", 0)
        return {
            "observations": [probe, metrics],
            "verification": verification,
            "status": "escalated" if exhausted else "investigating",
            "outcome": "remediation did not restore the probe" if exhausted else None,
            "timeline": [
                "verifier: NOT recovered -> "
                + ("escalate (budget exhausted)" if exhausted else "re-investigate")
            ],
        }
