"""Assemble the LangGraph state machine.

Key LangGraph features exercised (each maps to an interview demonstration the
brief calls out):

* ``MemorySaver`` checkpointing        -> kill the worker mid-run and resume.
* ``interrupt()`` at human_review      -> durable pause for approval; the exact
                                          proposed plan + version is surfaced.
* conditional edges                    -> the diagnostic loop asks for another
                                          discriminating check or moves on.
* a single guarded write node          -> replay/dedup show one authorised change.

Swap ``MemorySaver`` for ``SqliteSaver``/``PostgresSaver`` to make the durability
survive process death on disk; the graph wiring is unchanged.
"""

from __future__ import annotations

from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .environment import FakeCluster
from .nodes import Nodes
from .reasoner import Reasoner, get_reasoner
from .state import IncidentState


def _route_after_plan(state: IncidentState) -> str:
    """If the planner still wants evidence, collect it; else diagnose is done
    gathering and we try to remediate."""
    return "collect" if state.get("next_check") else "remediation_plan"


def _route_after_diagnose(state: IncidentState) -> str:
    """Continue the investigation loop until evidence is exhausted or budget hit."""
    budget = state.get("budget", {})
    if budget.get("investigation_steps", 0) >= budget.get("max_investigation_steps", 6):
        return "remediation_plan"
    return "plan"


def _route_after_policy(state: IncidentState) -> str:
    return "human_review" if state.get("status") == "awaiting_approval" else END


def _route_after_remediation_plan(state: IncidentState) -> str:
    return "policy_check" if state.get("proposed_action") else END


def _route_after_verify(state: IncidentState) -> str:
    """Recovered -> done. Otherwise re-plan within budget, or end (escalated)."""
    if state.get("status") == "investigating":
        return "plan"
    return END


def build_graph(
    cluster: FakeCluster,
    reasoner: Optional[Reasoner] = None,
    checkpointer: Optional[Any] = None,
):
    nodes = Nodes(cluster, reasoner or get_reasoner())

    def human_review(state: IncidentState) -> IncidentState:
        """Durable interrupt. Execution suspends here and the caller resumes
        with ``Command(resume={"approved": bool, "by": str})``. The approval is
        bound to the exact resource version the human saw."""
        action = state["proposed_action"]
        decision = interrupt(
            {
                "incident_id": state["incident_id"],
                "proposed_action": action,
                "policy_decision": state["policy_decision"],
                "hypotheses": state["hypotheses"],
                "ask": "Approve this remediation? resume with {approved, by}.",
            }
        )
        approved = bool(decision.get("approved"))
        approval = {
            "approved": approved,
            "by": decision.get("by", "unknown"),
            "bound_version": action["resource_version"],
        }
        if not approved:
            return {
                "approval": approval,
                "status": "escalated",
                "outcome": "human rejected the proposed remediation",
                "timeline": [f"human_review: REJECTED by {approval['by']}"],
            }
        return {
            "approval": approval,
            "status": "executing",
            "timeline": [f"human_review: APPROVED by {approval['by']}"],
        }

    g = StateGraph(IncidentState)
    g.add_node("intake", nodes.intake)
    g.add_node("plan", nodes.plan)
    g.add_node("collect", nodes.collect)
    g.add_node("diagnose", nodes.diagnose)
    g.add_node("remediation_plan", nodes.remediation_plan)
    g.add_node("policy_check", nodes.policy_check)
    g.add_node("human_review", human_review)
    g.add_node("executor", nodes.executor)
    g.add_node("verifier", nodes.verifier)

    g.add_edge(START, "intake")
    g.add_edge("intake", "plan")
    g.add_conditional_edges("plan", _route_after_plan, ["collect", "remediation_plan"])
    g.add_edge("collect", "diagnose")
    g.add_conditional_edges("diagnose", _route_after_diagnose, ["plan", "remediation_plan"])
    g.add_conditional_edges(
        "remediation_plan", _route_after_remediation_plan, ["policy_check", END]
    )
    g.add_conditional_edges("policy_check", _route_after_policy, ["human_review", END])
    # After the interrupt resumes: approved -> executor, rejected -> END.
    g.add_conditional_edges(
        "human_review",
        lambda s: "executor" if s.get("status") == "executing" else END,
        ["executor", END],
    )
    g.add_edge("executor", "verifier")
    g.add_conditional_edges("verifier", _route_after_verify, ["plan", END])

    return g.compile(checkpointer=checkpointer or MemorySaver())
