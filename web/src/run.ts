// The run model mirrors the real agent's output timeline (see the Python CLI).
// The frontend replays these steps with animation; it does not re-implement the
// agent, it visualises the exact same node sequence, hypotheses and outcomes.

export type NodeId =
  | "intake"
  | "plan"
  | "collect"
  | "diagnose"
  | "remediation_plan"
  | "policy_check"
  | "human_review"
  | "executor"
  | "verifier";

export type StepKind =
  | "info"
  | "telemetry"
  | "deploy"
  | "topology"
  | "diagnose"
  | "plan"
  | "remediate"
  | "policy"
  | "approve"
  | "exec"
  | "verify"
  | "escalate";

export interface Hypothesis {
  id: string;
  statement: string;
  status: "open" | "supported" | "contradicted" | "confirmed";
  confidence: number;
}

export interface Step {
  node: NodeId;
  kind: StepKind;
  label: string;
  detail: string;
  hypotheses: Hypothesis[];
  metrics?: { errorRate: number; p95: number };
  pause?: boolean; // human review
}

const H = (
  bad: Hypothesis["status"],
  badC: number,
  dep: Hypothesis["status"],
  depC: number
): Hypothesis[] => [
  {
    id: "bad_config",
    statement: "A recent config change on the active revision caused the errors",
    status: bad,
    confidence: badC,
  },
  {
    id: "dependency",
    statement: "A downstream dependency is failing",
    status: dep,
    confidence: depC,
  },
];

// Steps up to (and including) the human-review pause.
export const INVESTIGATION: Step[] = [
  {
    node: "intake",
    kind: "info",
    label: "intake",
    detail: "checkout · prod · tenant=acme — alert deduplicated (a214bbb9)",
    hypotheses: H("open", 0.2, "open", 0.2),
  },
  {
    node: "plan",
    kind: "plan",
    label: "plan → telemetry",
    detail: "select next discriminating check: telemetry",
    hypotheses: H("open", 0.2, "open", 0.2),
  },
  {
    node: "collect",
    kind: "telemetry",
    label: "collect · telemetry",
    detail: "error_rate = 38.0%, p95 = 920ms over 15m",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("open", 0.2, "open", 0.2),
  },
  {
    node: "diagnose",
    kind: "diagnose",
    label: "diagnose",
    detail: "errors elevated; cause not yet localised",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("open", 0.2, "open", 0.2),
  },
  {
    node: "plan",
    kind: "plan",
    label: "plan → deployment",
    detail: "select next discriminating check: deployment",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("open", 0.2, "open", 0.2),
  },
  {
    node: "collect",
    kind: "deploy",
    label: "collect · deployment",
    detail:
      "active = checkout-7f2c (rv 41) · config delta: CONN_POOL 50→5, FEATURE_NEW_TAX on",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("open", 0.2, "open", 0.2),
  },
  {
    node: "diagnose",
    kind: "diagnose",
    label: "diagnose",
    detail: "config delta coincides with error onset → bad_config supported",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("supported", 0.8, "contradicted", 0.15),
  },
  {
    node: "plan",
    kind: "plan",
    label: "plan → topology",
    detail: "confirm blast radius: topology",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("supported", 0.8, "contradicted", 0.15),
  },
  {
    node: "collect",
    kind: "topology",
    label: "collect · topology",
    detail: "depends_on = [payments, inventory] — dependencies healthy",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("supported", 0.8, "contradicted", 0.15),
  },
  {
    node: "remediation_plan",
    kind: "remediate",
    label: "remediation_plan",
    detail: "propose rollback → checkout-6a1b (last healthy revision)",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("supported", 0.8, "contradicted", 0.15),
  },
  {
    node: "policy_check",
    kind: "policy",
    label: "policy_check",
    detail: "allowlisted · in-scope · bound to rv=41 · within budget → ALLOW",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("supported", 0.8, "contradicted", 0.15),
  },
  {
    node: "human_review",
    kind: "approve",
    label: "human_review",
    detail: "awaiting approval — bound to the exact plan + resource version",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("supported", 0.8, "contradicted", 0.15),
    pause: true,
  },
];

export const APPROVED_TAIL: Step[] = [
  {
    node: "executor",
    kind: "exec",
    label: "executor",
    detail: "idempotent rollback applied — checkout → checkout-6a1b (rv 42)",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("confirmed", 0.9, "contradicted", 0.1),
  },
  {
    node: "verifier",
    kind: "verify",
    label: "verifier",
    detail: "synthetic checkout probe OK · error_rate 0.4% → RECOVERED",
    metrics: { errorRate: 0.004, p95: 180 },
    hypotheses: H("confirmed", 0.95, "contradicted", 0.1),
  },
];

export const REJECTED_TAIL: Step[] = [
  {
    node: "human_review",
    kind: "escalate",
    label: "human_review · rejected",
    detail: "operator declined — no write performed, incident escalated",
    metrics: { errorRate: 0.38, p95: 920 },
    hypotheses: H("supported", 0.8, "contradicted", 0.15),
  },
];

export interface NodeMeta {
  id: NodeId;
  title: string;
  x: number;
  y: number;
  role: "flow" | "gate" | "write" | "verify";
}

// Layout on a 1000 x 620 viewBox.
export const NODES: NodeMeta[] = [
  { id: "intake", title: "intake", x: 120, y: 70, role: "flow" },
  { id: "plan", title: "plan", x: 120, y: 200, role: "flow" },
  { id: "collect", title: "collect", x: 120, y: 330, role: "flow" },
  { id: "diagnose", title: "diagnose", x: 120, y: 460, role: "flow" },
  { id: "remediation_plan", title: "remediation_plan", x: 430, y: 460, role: "flow" },
  { id: "policy_check", title: "policy_check", x: 430, y: 330, role: "gate" },
  { id: "human_review", title: "human_review", x: 430, y: 200, role: "gate" },
  { id: "executor", title: "executor", x: 740, y: 200, role: "write" },
  { id: "verifier", title: "verifier", x: 740, y: 330, role: "verify" },
];

export interface Edge {
  from: NodeId;
  to: NodeId;
  label?: string;
}

export const EDGES: Edge[] = [
  { from: "intake", to: "plan" },
  { from: "plan", to: "collect", label: "need evidence" },
  { from: "collect", to: "diagnose" },
  { from: "diagnose", to: "plan", label: "loop" },
  { from: "diagnose", to: "remediation_plan", label: "done" },
  { from: "remediation_plan", to: "policy_check" },
  { from: "policy_check", to: "human_review", label: "allow" },
  { from: "human_review", to: "executor", label: "approve" },
  { from: "executor", to: "verifier" },
  { from: "verifier", to: "plan", label: "retry" },
];
