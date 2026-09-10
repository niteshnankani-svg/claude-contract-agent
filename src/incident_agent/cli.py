"""Run an incident scenario end to end from the command line.

    python -m incident_agent.cli scenarios/checkout_bad_config.json
    python -m incident_agent.cli scenarios/checkout_bad_config.json --reject
    python -m incident_agent.cli scenarios/checkout_bad_config.json --simulate-crash

The run pauses at the human-review interrupt and prints the exact proposed
action; ``--auto-approve`` (default) resumes with an approval, ``--reject``
resumes with a rejection, and ``--simulate-crash`` throws away the in-memory
graph object *after* the interrupt and rebuilds it against the same checkpointer
to prove the run resumes from the durable checkpoint rather than the top.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from .environment import FakeCluster
from .graph import build_graph
from .reasoner import get_reasoner


def _print_timeline(state: dict) -> None:
    print("\n── incident timeline " + "─" * 40)
    for line in state.get("timeline", []):
        print(f"  • {line}")


def _print_summary(state: dict) -> None:
    print("\n── summary " + "─" * 50)
    print(f"  incident : {state.get('incident_id')}")
    print(f"  status   : {state.get('status')}")
    print(f"  outcome  : {state.get('outcome')}")
    v = state.get("verification")
    if v:
        print(f"  recovered: {v['recovered']}  probe={v['probe'].get('synthetic_checkout_ok')} "
              f"error_rate={v['metrics'].get('error_rate')}")
    if state.get("action_ledger"):
        print("  actions  :")
        for a in state["action_ledger"]:
            print(f"     - {a['action_type']} {a['target']} -> {a['status']} ({a['detail']})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path, help="path to a scenario JSON file")
    parser.add_argument("--reject", action="store_true", help="reject the remediation")
    parser.add_argument("--auto-approve", action="store_true", default=True)
    parser.add_argument("--simulate-crash", action="store_true",
                        help="rebuild the graph after the interrupt to prove durable resume")
    args = parser.parse_args(argv)

    spec = json.loads(args.scenario.read_text())
    cluster = FakeCluster(spec["cluster"])
    checkpointer = MemorySaver()
    graph = build_graph(cluster, get_reasoner(), checkpointer=checkpointer)

    config = {"configurable": {"thread_id": spec.get("thread_id", "demo-1")}}
    initial = {"alert": spec["alert"]}

    print(f"▶ running scenario: {args.scenario.name}")
    result = graph.invoke(initial, config=config)

    # Paused at the human-review interrupt?
    interrupts = result.get("__interrupt__")
    if interrupts:
        payload = interrupts[0].value
        print("\n⏸  HUMAN REVIEW REQUIRED")
        print(json.dumps(payload["proposed_action"], indent=2))
        print(f"   policy: {payload['policy_decision']['allowed']} "
              f"bound to rv={payload['proposed_action']['resource_version']}")

        if args.simulate_crash:
            print("\n💥 simulating worker crash: discarding graph object, rebuilding "
                  "against the same checkpointer…")
            graph = build_graph(cluster, get_reasoner(), checkpointer=checkpointer)

        approved = not args.reject
        decision = {"approved": approved, "by": "oncall@demo"}
        print(f"\n▶ resuming with approval={approved}")
        result = graph.invoke(Command(resume=decision), config=config)

    _print_timeline(result)
    _print_summary(result)
    return 0 if result.get("status") in ("resolved", "escalated") else 1


if __name__ == "__main__":
    sys.exit(main())
