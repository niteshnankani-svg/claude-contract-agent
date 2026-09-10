"""Typed graph state, hypothesis ledger, and action ledger.

The state is the single source of truth that LangGraph checkpoints after every
node. Because it is durable, a killed worker resumes from the last committed
node rather than restarting the incident (see ``graph.py``).

Design note (from the decision brief): logs/metrics/traces are queried by time,
service and topology and stored as *typed observations* — they are never
embedded as free-text document chunks that could smuggle instructions into the
reasoning loop.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, Optional, TypedDict

# ---------------------------------------------------------------------------
# Value objects (plain dicts kept JSON-serialisable so any checkpointer works)
# ---------------------------------------------------------------------------

HypothesisStatus = Literal["open", "supported", "contradicted", "confirmed"]
IncidentStatus = Literal[
    "new",
    "investigating",
    "awaiting_approval",
    "executing",
    "verifying",
    "resolved",
    "escalated",
    "failed",
]


class Hypothesis(TypedDict):
    id: str
    statement: str
    status: HypothesisStatus
    confidence: float  # 0..1
    evidence_for: list[str]
    evidence_against: list[str]


class Observation(TypedDict):
    """A single bounded read from a tool. ``source`` records provenance so the
    UI can show *why* the agent believes something, and so untrusted telemetry
    text is never confused with agent instructions."""

    kind: Literal["telemetry", "deployment", "topology", "probe"]
    service: str
    summary: str
    data: dict[str, Any]
    trusted_for_reasoning: bool  # metrics: True; free-text log bodies: False


class ActionRecord(TypedDict):
    """One entry in the append-only action ledger. The ``idempotency_key`` plus
    the executor's reconcile step is what makes an external side effect
    effectively exactly-once even across a mid-execution restart."""

    idempotency_key: str
    action_type: str
    target: str
    resource_version: str
    status: Literal["intended", "succeeded", "failed", "deduplicated"]
    detail: str


class ProposedAction(TypedDict):
    action_type: str  # must be on the policy allowlist
    target: str  # e.g. "deployment/checkout"
    params: dict[str, Any]
    resource_version: str  # binds approval to an exact observed state
    rationale: str
    compensation: Optional[str]  # how to undo, when known


def _merge_dict(left: dict, right: dict) -> dict:
    out = dict(left or {})
    out.update(right or {})
    return out


class IncidentState(TypedDict, total=False):
    # --- scope / identity (established at intake) -------------------------
    incident_id: str
    dedup_key: str
    tenant: str
    environment: str
    service: str
    time_window_minutes: int
    alert: dict[str, Any]

    # --- reasoning ledgers ------------------------------------------------
    hypotheses: list[Hypothesis]
    observations: Annotated[list[Observation], operator.add]
    next_check: Optional[str]  # what the planner wants next

    # --- remediation ------------------------------------------------------
    proposed_action: Optional[ProposedAction]
    policy_decision: Optional[dict[str, Any]]
    approval: Optional[dict[str, Any]]  # {approved: bool, by: str, bound_version: str}
    action_ledger: Annotated[list[ActionRecord], operator.add]

    # --- verification -----------------------------------------------------
    verification: Optional[dict[str, Any]]

    # --- control ----------------------------------------------------------
    status: IncidentStatus
    outcome: Optional[str]
    budget: Annotated[dict[str, int], _merge_dict]  # counters + limits
    timeline: Annotated[list[str], operator.add]


def new_budget() -> dict[str, int]:
    return {
        "investigation_steps": 0,
        "max_investigation_steps": 6,
        "remediation_attempts": 0,
        "max_remediation_attempts": 2,
    }
