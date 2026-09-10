# Agent project selection: market and hiring evidence

Research date: 9 September 2026. This is a replacement decision brief, not a claim that the proposed replacement has been built or validated.

## Conclusion

Recommend an incident investigation and controlled remediation agent for Kubernetes-based applications as the strongest next project for demonstrating applied agent engineering. The objective is to reduce the time an on-call engineer spends assembling evidence, testing hypotheses, and safely restoring service. A successful run must demonstrate recovery in a running environment.

Order/shipment exception resolution is the strongest alternative for reusing this portfolio's commerce and export experience. Neither recommendation establishes product-market fit. Public hiring descriptions establish desired skills; vendor releases establish investment and competition; customer interviews and pilots would establish willingness to pay.

The earlier Casework project does not meet this new scope. Its excerpt selection and whole-job persistence are not substitutes for a reasoning/tool loop, node-level checkpoints, and verified external actions.

## Hiring evidence inspected

These are employer-hosted descriptions accessible during this research, not a representative labor-market survey or verified interview question bank. Posting dates are not consistently available. Several roles are senior: a portfolio can demonstrate skills but cannot replace their experience requirements.

| Employer and role | Explicit requirements relevant to the project | Scope caveat |
|---|---|---|
| [6sense: Principal AI Architect, Bengaluru](https://job-boards.greenhouse.io/6sense/jobs/5636812) | Typed LangGraph state, subgraphs, checkpointing, replay, human review, MCP, safe execution, evaluation and recovery | Principal role requiring substantial production experience |
| [Distru: AI Product Engineer, remote worldwide](https://jobs.lever.co/distru/b7bb8662-3ede-4b41-bc98-b8ca5678f8d3) | LangGraph-based agents operating across business tools; MCP integrations; permissions, observability and product ownership | Requires professional experience and production agent work |
| [Phizenix: LLM / Agentic Evaluation Rig Engineer, Hyderabad](https://job-boards.greenhouse.io/phizenix/jobs/5398766008) | Ground-truth/adversarial datasets, multi-step evaluation, source verification and quality gates | Specialized evaluation role |
| [BLEN: AI Engineer](https://jobs.lever.co/blencorp/4b2e3689-9720-4785-b0fe-d09bd5325f74) | Planning/tool use, MCP, Python APIs, retrieval, model tradeoffs and evals | US work/residency requirements; evidence of skills, not an India job recommendation |

My interpretation: build demonstrable workflow completion, controlled tool execution and failure recovery. Increasing the count of named agents alone does not demonstrate these skills.

Suggested interview demonstrations, inferred from these requirements rather than claimed as actual interview questions:

- Kill the worker during execution and show what resumes, what is revalidated, and which writes are prevented from repeating.
- Give the agent contradictory evidence and demonstrate a justified additional investigation or escalation.
- Replay the same alert and show deduplication and a single authorized change.
- Place malicious instructions in logs and show that they cannot grant tool permissions.
- Compare the agent with a deterministic runbook and a single-agent baseline using an independent test partition.
- Show cost per successful resolution, including failures and retries.

## Three credible problem areas

### 1. Incident investigation and controlled remediation — recommended for portfolio depth

[PagerDuty's 24 June 2026 engineering account](https://www.pagerduty.com/eng/inside-pagerdutys-sre-agent-how-we-built-deep-incident-investigation/) describes extended investigations across logs, metrics and deployments with live human collaboration. Its [5 August 2026 update](https://www.pagerduty.com/blog/ai/sre-agent-enhancements-faster-triage-greater-access-controls-deeper-system-connectivity/) describes further SRE Agent integration and access-control work. These are vendor accounts, not independent performance evaluations.

Buyer hypothesis: platform/SRE leads responsible for Kubernetes applications. Pain: fragmented telemetry and deployment history delay diagnosis and make remediation risky. Proposed outcome metrics: time to correct diagnosis, verified recovery rate, engineer intervention time and unsafe-action rate.

Competition is established. A credible initial scope is a small set of incident classes with inspectable evidence and constrained remediation, not a general replacement for an SRE team. Public live fault environments make the outcome demonstrable without inventing customer savings.

### 2. Order and shipment exception resolution — strongest portfolio reuse

[C.H. Robinson's 12 June 2025 account](https://www.chrobinson.com/en-us/about-us/newsroom/news/2025/ch-robinson-scales-fleet-of-ai-agents-past-30/) describes agents across quoting, orders, freight classification, appointments and tracking. Distru's role above independently shows hiring around agents connected to operational business systems.

Buyer hypothesis: operations teams at distributors/exporters. Proposed workflow: ingest an order, reconcile product/customer identifiers, detect missing stock or document mismatches, collect missing information, propose a valid alternative, obtain approval, update the system of record and verify the resulting state.

This would connect naturally to `niryat-ai` and the BargainAI integration projects. However, real catalog, inventory, shipment and exception data are needed. A fabricated ERP demo alone would not validate commercial usefulness.

### 3. Invoice exception resolution — clear operational workflow, harder domain validation

[Oracle's matching documentation](https://docs.oracle.com/en/cloud/saas/procurement/26b/oapro/match-approval-level-options.html) defines invoice/PO/receipt matching, while its [tolerance documentation](https://docs.oracle.com/en/cloud/saas/financials/26b/faipp/invoice-tolerances.html) describes holds for mismatches. These establish a concrete operational process. Oracle's agent roadmap also shows competitive activity, but no future release is treated here as already available.

Buyer hypothesis: accounts-payable teams. Proposed workflow: extract invoice fields, match supplier and line items, investigate discrepancies, obtain missing receipts, route exceptions, and prepare an authorized accounting-system update. Arithmetic and payment eligibility remain deterministic. Public invoice extraction data does not by itself evaluate exception resolution or payment correctness.

## Proposed incident agent: the work it would actually do

Example acceptance scenario: a checkout service starts returning errors after a configuration change. The agent receives an alert, establishes the affected service and time window, checks telemetry and deployment differences, investigates competing causes, proposes a scoped reversal, pauses for approval, performs the allowed change, and tests whether transactions recover. If recovery fails, it reassesses within a fixed budget or escalates with evidence.

The recovery check must use fresh measurements and an application-level probe. A successful Kubernetes API response is not enough to close the incident. Approval must bind to the exact environment, resource version and proposed action; stale approval cannot authorize a changed plan.

Proposed LangGraph design:

1. Intake and incident deduplication establish authenticated tenant, environment and resource scope.
2. A planning node selects the next evidence needed from a typed hypothesis ledger.
3. Separate telemetry, deployment and topology subgraphs collect bounded observations. Independent reads may run concurrently.
4. A diagnostic loop updates supported and contradicted hypotheses and requests another discriminating check when needed.
5. A remediation planner proposes allowlisted actions with preconditions and a compensation plan where possible.
6. Deterministic policy checks constrain scope, credentials, resource versions and action budgets.
7. A durable human-review interrupt suspends execution for actions requiring approval.
8. The executor records intent, executes with deduplication/preconditions, and reconciles uncertain results before retrying.
9. A verifier observes a defined recovery window; it closes, re-plans, compensates if appropriate, or escalates.

[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) and [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) provide graph-state recovery and pause/resume primitives. They do not automatically make an external side effect exactly-once. The action ledger and resource-specific reconciliation still have to be engineered.

The interface should show the incident timeline, supporting/contradicting observations, current hypotheses, proposed change, approval state, and recovery measurements. Chunking belongs to versioned runbooks and source files. Logs, metrics and traces should be queried by time, service and topology, not indiscriminately embedded as document chunks.

## Dataset, repository and model selection

- [IBM ITBench-Lite on Hugging Face](https://huggingface.co/datasets/ibm-research/ITBench-Lite): card lists 35 SRE snapshot scenarios within 65 total scenarios; Apache-2.0. Use for diagnosis evaluation. Snapshots cannot establish live remediation success. The HF viewer currently reports a schema error; loaders need validation against raw files. The listed full size is 31 GB, so do not silently download the full corpus to this low-space machine.
- [ITBench](https://github.com/itbench-hub/ITBench): framework linked by IBM's dataset card; candidate for live evaluation integration, not a completed product to relabel.
- [Microsoft AIOpsLab](https://github.com/microsoft/AIOpsLab): MIT-licensed framework for deploying test services, injecting faults and evaluating agents. Use as an external interactive benchmark candidate. Requires infrastructure setup and scenario compatibility validation.
- [Microsoft OpenRCA](https://github.com/microsoft/OpenRCA): secondary diagnosis benchmark, with substantial published storage/memory requirements. Diagnosis scores do not establish successful repair. A recent community baseline critique warrants scrutiny before adopting headline scores; its claims were not reproduced here.
- [Microsoft AgentRx](https://huggingface.co/datasets/microsoft/AgentRx/tree/main): optional trajectory-failure analysis resource; gated access and CC-BY-4.0 shown. No files accessed or access terms accepted. It is not an incident-remediation training set.
- [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B): Apache-2.0 open-weight model candidate to compare with a hosted tool-capable model. The card is not evidence of performance on our incidents. Do not call it the best model or promise it runs on the user's current hardware. Final model choice requires task-success, tool validity, cost and latency measurements.

Begin with evaluation and tool execution, not fine-tuning. Consider training only after repeated failure analysis identifies a learnable deficit and there are enough licensed, verified trajectories with separated train/test incident families. Ground-truth fault labels must never enter the agent's accessible evidence store.

## Reassessment of the user's portfolio

The existing [portfolio audit](production-agent/docs/PORTFOLIO_AUDIT.md) inventories all 26 accessible GitHub repositories and 18 public HF assets. It inspects selected source from nine relevant repositories; it does not read every line, run every repository or execute every hosted model. Private/unlisted HF artifacts remain unverified.

`agent-company` supplies orchestration design experience; `Multi_agent_ticketing_system` supplies intake/escalation experience; `legal-rag-chatbot` supplies source/section handling. These are possible design inputs, not proven reusable incident code. `niryat-ai` and BargainAI are more directly relevant to the alternative operational-commerce project.

The public HF complaint models are binary sentiment classifiers, and the legal datasets are legal retrieval artifacts. Neither is suitable for incident diagnosis or authorizing infrastructure actions. Their availability must not dictate a mismatched use case.

## Acceptance bar before claiming success

- Demonstrate several distinct fault classes in a real isolated application environment, including wrong hypotheses, failed remediation and unavailable tools.
- Freeze independent scenario families and compare with deterministic and single-agent baselines; avoid training on the test incident templates.
- Measure correct diagnosis, actual recovery, unnecessary changes, duplicate writes, escalation quality, latency and total inference cost.
- Test restart during approval and action execution, expired authorization, concurrent changes, malicious telemetry and tenant boundary violations.
- Show an unsuccessful run honestly. Neither a polished UI nor a passing unit suite proves business effectiveness.

No replacement application was implemented, benchmark downloaded, paid inference invoked, production system changed or customer contacted during this research. The deliverable is an evidence-backed direction and concrete evaluation scope, so the next implementation does not repeat the previous premature product choice.
