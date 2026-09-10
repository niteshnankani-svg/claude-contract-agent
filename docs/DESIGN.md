# Design

This agent implements the recommendation in `AGENT_MARKET_RESEARCH.md`: an
**incident investigation and controlled remediation agent for Kubernetes-based
applications**, built on **LangGraph**. The goal is to shorten the time an
on-call engineer spends assembling evidence, testing hypotheses, and safely
restoring service — and to *prove* recovery in a running environment rather than
declaring success from a snapshot.

## Why LangGraph

The brief's hiring evidence repeatedly names the exact primitives LangGraph
provides and the role demands: typed state, subgraphs, **checkpointing**,
**replay**, **human review**, and safe execution. LangGraph gives us:

- durable state checkpoints after every node (restart / resume),
- first-class `interrupt()` for human-in-the-loop approval,
- conditional edges for a real diagnostic loop (not a fixed script).

Everything safety-relevant that could authorise a side effect is kept in
deterministic Python (`policy.py`), *outside* the model. The model proposes;
policy disposes.

## Node graph

```
START → intake → plan ─┬─(need evidence)→ collect → diagnose ─┬─(keep looking)→ plan
                       │                                       │
                       └───────────────(done)──────────────────┴→ remediation_plan
remediation_plan ─(action?)→ policy_check ─(allowed)→ human_review ⏸
   │(none)→ END(escalate)        │(deny)→ END(escalate)     │(reject)→ END(escalate)
                                                            │(approve)
                                                            ▼
                                                        executor → verifier ─┬→ END(resolved)
                                                                              └─(retry budget)→ plan
```

| # | Node | Responsibility | Brief mapping |
|---|------|----------------|----------------|
| 1 | `intake` | authenticate tenant/env/service scope, dedup the alert | intake & deduplication |
| 2 | `plan` | choose the next discriminating check from the hypothesis ledger | planning node |
| 3 | `collect` | run one read tool (telemetry / deployment / topology) | bounded observation subgraphs |
| 4 | `diagnose` | update supported / contradicted hypotheses | diagnostic loop |
| 5 | `remediation_plan` | propose an allowlisted action + compensation | remediation planner |
| 6 | `policy_check` | scope, resource-version, budget gate (deterministic) | deterministic policy checks |
| 7 | `human_review` | **durable interrupt** for approval, bound to exact plan | human-review interrupt |
| 8 | `executor` | idempotent apply + reconcile | executor with dedup/preconditions |
| 9 | `verifier` | app-level probe over a recovery window | verifier |

## The four hard guarantees

These are the properties the brief says an interviewer would probe, and where
each lives in the code:

1. **Restart is safe.** State is checkpointed by `MemorySaver` (swap for
   Sqlite/Postgres). Killing the worker at the approval interrupt and rebuilding
   the graph resumes from the checkpoint — `test_restart_during_approval_resumes_from_checkpoint`.
2. **Writes are effectively exactly-once.** The executor derives a deterministic
   idempotency key from `(incident, target, resource_version, params)`; the
   cluster de-duplicates on it — `test_write_is_idempotent_on_replay`.
3. **Stale approval cannot execute.** Approval binds to a resource version; the
   executor re-checks the live version and refuses on drift —
   `test_stale_approval_is_refused`.
4. **Untrusted telemetry cannot grant permissions.** Policy is by *allowlist*;
   evidence text is stored as typed observations and never parsed into a policy
   decision — `test_malicious_telemetry_cannot_grant_permissions`.

## Recovery is verified, not assumed

`environment.py` is a *stateful* fault-injected cluster, not a canned mock. A
bad rollout genuinely raises the error rate; the rollback genuinely restores it.
`verifier` closes the incident only when a fresh **synthetic probe** succeeds
*and* the error-rate window is normal — a control-plane 200 is explicitly not
enough.

## Swapping in real infrastructure

- `FakeCluster` → real clients (Prometheus/Datadog reads, `kubectl rollout undo`
  writes) behind the same method names.
- `HeuristicReasoner` → `AnthropicReasoner` (or any `Reasoner`) via
  `INCIDENT_AGENT_REASONER=anthropic`. The deterministic baseline stays as the
  honest comparison the brief requires.
- `MemorySaver` → `SqliteSaver`/`PostgresSaver` for on-disk durability.

## What this is *not*

Per the brief's honesty bar: this is a working reference implementation and
evaluation harness on a simulated environment, **not** a validated product with
demonstrated product-market fit. The next step is wiring it to a real interactive
benchmark (IBM ITBench / Microsoft AIOpsLab) and measuring correct diagnosis,
actual recovery, unnecessary changes, duplicate writes, escalation quality,
latency and cost against deterministic and single-agent baselines.
