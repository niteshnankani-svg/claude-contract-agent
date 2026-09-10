"""The reasoning layer — deliberately pluggable.

The brief says to *begin with evaluation and tool execution, not fine-tuning*,
and to compare an open-weight model with a hosted tool-capable model on task
success, tool validity, cost and latency. So the graph never hard-codes a
model: it depends on the ``Reasoner`` protocol below.

* ``HeuristicReasoner`` — deterministic, no network, no key. It is the default
  so the whole graph runs offline and the tests are reproducible. It is also
  the honest baseline the brief demands: "compare the agent with a
  deterministic runbook and a single-agent baseline".
* ``AnthropicReasoner`` — used only if ``ANTHROPIC_API_KEY`` is set and the
  ``anthropic`` package is installed. It makes the *same* three decisions, so
  swapping reasoners is a one-line change and A/B comparison is apples-to-apples.

Crucially, the reasoner proposes; it never authorises. Its output always flows
through the deterministic policy gate (``policy.py``) before any side effect.
"""

from __future__ import annotations

import os
from typing import Optional, Protocol

from .state import Hypothesis, IncidentState, Observation, ProposedAction


class Reasoner(Protocol):
    def plan_next_check(self, state: IncidentState) -> Optional[str]:
        ...

    def update_hypotheses(self, state: IncidentState) -> list[Hypothesis]:
        ...

    def propose_remediation(self, state: IncidentState) -> Optional[ProposedAction]:
        ...


# ---------------------------------------------------------------------------
# Deterministic baseline
# ---------------------------------------------------------------------------

_CHECK_ORDER = ["telemetry", "deployment", "topology"]


class HeuristicReasoner:
    """A transparent runbook. Every decision is inspectable and testable."""

    name = "heuristic"

    def plan_next_check(self, state: IncidentState) -> Optional[str]:
        seen = {o["kind"] for o in state.get("observations", [])}
        for kind in _CHECK_ORDER:
            if kind not in seen:
                return kind
        return None  # all evidence gathered

    def update_hypotheses(self, state: IncidentState) -> list[Hypothesis]:
        obs = state.get("observations", [])
        telemetry = _latest(obs, "telemetry")
        deployment = _latest(obs, "deployment")

        hyps: dict[str, Hypothesis] = {h["id"]: dict(h) for h in state.get("hypotheses", [])}  # type: ignore[assignment]

        def ensure(hid: str, statement: str) -> Hypothesis:
            if hid not in hyps:
                hyps[hid] = Hypothesis(
                    id=hid, statement=statement, status="open",
                    confidence=0.2, evidence_for=[], evidence_against=[],
                )
            return hyps[hid]

        bad_config = ensure(
            "bad_config", "A recent config change on the active revision caused the errors"
        )
        dependency = ensure(
            "dependency", "A downstream dependency is failing"
        )

        elevated = bool(telemetry and telemetry["data"]["error_rate"] > 0.05)

        if deployment is not None:
            if deployment["data"].get("config_delta") and elevated:
                bad_config["status"] = "supported"
                bad_config["confidence"] = 0.8
                bad_config["evidence_for"] = [
                    f"config delta {deployment['data']['config_delta']} on active "
                    f"revision coincides with elevated error rate"
                ]
                # A clear deploy correlation makes a pure dependency cause less likely.
                dependency["status"] = "contradicted"
                dependency["confidence"] = 0.15
                dependency["evidence_against"] = [
                    "error onset aligns with local config change, not a shared dependency"
                ]
            elif not deployment["data"].get("config_delta"):
                bad_config["status"] = "contradicted"
                bad_config["confidence"] = 0.1
                bad_config["evidence_against"] = ["no config change on active revision"]

        return list(hyps.values())

    def propose_remediation(self, state: IncidentState) -> Optional[ProposedAction]:
        confirmed = _leading_hypothesis(state.get("hypotheses", []))
        if not confirmed or confirmed["id"] != "bad_config":
            return None
        if confirmed["confidence"] < 0.6:
            return None

        deployment = _latest(state.get("observations", []), "deployment")
        if not deployment:
            return None
        revisions = deployment["data"]["revisions"]
        active = deployment["data"]["active_revision"]
        prior_healthy = next(
            (r["name"] for r in reversed(revisions)
             if r["name"] != active and r["healthy_at_rollout"]),
            None,
        )
        if not prior_healthy:
            return None

        service = state["service"]
        return ProposedAction(
            action_type="rollback_deployment",
            target=f"deployment/{service}",
            params={"target_revision": prior_healthy},
            resource_version=deployment["data"]["resource_version"],
            rationale=(
                f"Roll {service} back to last healthy revision {prior_healthy}; "
                f"the active revision introduced {deployment['data'].get('config_delta')} "
                f"coincident with a {_error_rate(state):.0%} error rate."
            ),
            compensation=f"re-deploy {active} if rollback does not restore the probe",
        )


# ---------------------------------------------------------------------------
# Optional hosted reasoner (same decisions, LLM-backed)
# ---------------------------------------------------------------------------


class AnthropicReasoner(HeuristicReasoner):
    """Uses a hosted Claude model to narrate/justify while reusing the
    deterministic structure for the actual control decisions.

    This keeps the comparison honest: the *safety-relevant* choices (what to
    remediate, bound to which resource version) stay deterministic and
    testable, while the model adds natural-language triage. Extending the model
    to drive planning is a localised change here — the graph does not care.
    """

    name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-5"):
        from anthropic import Anthropic  # imported lazily; optional dependency

        self._client = Anthropic()
        self._model = model

    def propose_remediation(self, state: IncidentState) -> Optional[ProposedAction]:
        action = super().propose_remediation(state)
        if action is None:
            return None
        try:
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": (
                        "One sentence, on-call tone: justify rolling back "
                        f"{action['target']} to {action['params']['target_revision']} "
                        f"given evidence: {state.get('observations')}"
                    ),
                }],
            )
            action["rationale"] = msg.content[0].text.strip()  # type: ignore[union-attr]
        except Exception:  # pragma: no cover - network/credentials optional
            pass
        return action


def get_reasoner() -> Reasoner:
    """Select a reasoner from the environment. Defaults to the offline baseline."""
    if os.getenv("ANTHROPIC_API_KEY") and os.getenv("INCIDENT_AGENT_REASONER", "heuristic") == "anthropic":
        try:
            return AnthropicReasoner(os.getenv("INCIDENT_AGENT_MODEL", "claude-sonnet-5"))
        except Exception:  # pragma: no cover
            pass
    return HeuristicReasoner()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _latest(observations: list[Observation], kind: str) -> Optional[Observation]:
    for o in reversed(observations):
        if o["kind"] == kind:
            return o
    return None


def _leading_hypothesis(hyps: list[Hypothesis]) -> Optional[Hypothesis]:
    supported = [h for h in hyps if h["status"] in ("supported", "confirmed")]
    if not supported:
        return None
    return max(supported, key=lambda h: h["confidence"])


def _error_rate(state: IncidentState) -> float:
    t = _latest(state.get("observations", []), "telemetry")
    return t["data"]["error_rate"] if t else 0.0
