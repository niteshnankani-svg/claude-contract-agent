import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Graph from "./components/Graph";
import {
  APPROVED_TAIL,
  INVESTIGATION,
  REJECTED_TAIL,
  type Hypothesis,
  type NodeId,
  type Step,
} from "./run";

type Phase =
  | "idle"
  | "investigating"
  | "awaiting_approval"
  | "executing"
  | "resolved"
  | "escalated";

const STEP_MS = 950;

const kindColor: Record<string, string> = {
  telemetry: "#fb7185",
  deploy: "#a78bfa",
  topology: "#38bdf8",
  diagnose: "#2dd4bf",
  plan: "#8b98a5",
  remediate: "#fbbf24",
  policy: "#fbbf24",
  approve: "#fbbf24",
  exec: "#fb7185",
  verify: "#2dd4bf",
  escalate: "#fb7185",
  info: "#8b98a5",
};

export default function App() {
  const [log, setLog] = useState<Step[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const consoleRef = useRef<HTMLDivElement>(null);

  // Drive the investigation phase.
  useEffect(() => {
    if (phase !== "investigating") return;
    if (log.length >= INVESTIGATION.length) {
      const t = setTimeout(() => setPhase("awaiting_approval"), 400);
      return () => clearTimeout(t);
    }
    const t = setTimeout(
      () => setLog((l) => [...l, INVESTIGATION[l.length]]),
      STEP_MS
    );
    return () => clearTimeout(t);
  }, [phase, log.length]);

  // Drive the post-approval execution phase.
  useEffect(() => {
    if (phase !== "executing") return;
    const played = log.length - INVESTIGATION.length;
    if (played >= APPROVED_TAIL.length) {
      const t = setTimeout(() => setPhase("resolved"), 400);
      return () => clearTimeout(t);
    }
    const t = setTimeout(
      () => setLog((l) => [...l, APPROVED_TAIL[l.length - INVESTIGATION.length]]),
      STEP_MS
    );
    return () => clearTimeout(t);
  }, [phase, log.length]);

  useEffect(() => {
    consoleRef.current?.scrollTo({ top: 1e6, behavior: "smooth" });
  }, [log.length]);

  const current = log[log.length - 1];
  const prev = log[log.length - 2];
  const visited = useMemo(() => new Set(log.map((s) => s.node)), [log]);
  const activeEdge: [NodeId, NodeId] | null =
    prev && prev.node !== current?.node ? [prev.node, current.node] : null;
  const hyps: Hypothesis[] = current?.hypotheses ?? INVESTIGATION[0].hypotheses;
  const metrics = current?.metrics ?? { errorRate: 0, p95: 0 };

  const start = () => {
    setLog([INVESTIGATION[0]]);
    setPhase("investigating");
  };
  const reset = () => {
    setLog([]);
    setPhase("idle");
  };
  const approve = () => setPhase("executing");
  const reject = () => {
    setLog((l) => [...l, REJECTED_TAIL[0]]);
    setPhase("escalated");
  };

  return (
    <div className="min-h-screen grid-noise">
      <div className="max-w-6xl mx-auto px-5 py-10 md:py-16">
        <Hero phase={phase} onStart={start} onReset={reset} running={phase !== "idle"} />

        <div className="grid lg:grid-cols-5 gap-5 mt-10">
          {/* Graph + status */}
          <section className="lg:col-span-3 rounded-2xl border border-ink-700/70 bg-ink-900/60 backdrop-blur p-5">
            <PanelTitle
              eyebrow="LangGraph state machine"
              title="Node graph"
              accent="#2dd4bf"
            />
            <Graph
              activeNode={current?.node ?? null}
              visited={visited}
              activeEdge={activeEdge}
            />
            <Legend />
          </section>

          {/* Console */}
          <section className="lg:col-span-2 rounded-2xl border border-ink-700/70 bg-ink-900/60 backdrop-blur p-5 flex flex-col">
            <PanelTitle eyebrow="stdout" title="Incident timeline" accent="#a78bfa" />
            <div
              ref={consoleRef}
              className="scroll-slim font-mono text-[12.5px] leading-relaxed h-[320px] overflow-y-auto pr-1"
            >
              <AnimatePresence initial={false}>
                {log.map((s, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="mb-2"
                  >
                    <span style={{ color: kindColor[s.kind] }}>●</span>{" "}
                    <span className="text-ink-100 text-slate-200">{s.label}</span>
                    <div className="text-slate-500 pl-4">{s.detail}</div>
                  </motion.div>
                ))}
              </AnimatePresence>
              {phase === "idle" && (
                <div className="text-slate-600">
                  press <span className="text-teal">Run incident</span> to begin…
                </div>
              )}
            </div>
          </section>
        </div>

        <div className="grid lg:grid-cols-5 gap-5 mt-5">
          <Metrics metrics={metrics} phase={phase} />
          <Ledger hyps={hyps} />
        </div>

        <Footer />
      </div>

      <AnimatePresence>
        {phase === "awaiting_approval" && (
          <ApprovalGate onApprove={approve} onReject={reject} />
        )}
      </AnimatePresence>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function Hero({
  phase,
  onStart,
  onReset,
  running,
}: {
  phase: Phase;
  onStart: () => void;
  onReset: () => void;
  running: boolean;
}) {
  return (
    <header>
      <div className="flex items-center gap-2 text-xs font-mono text-teal mb-4">
        <span className="h-2 w-2 rounded-full bg-teal animate-pulseGlow" />
        incident mission control
      </div>
      <h1 className="font-display font-bold text-4xl md:text-6xl tracking-tight leading-[1.05]">
        claude&#8288;-&#8288;contract&#8288;-&#8288;agent
      </h1>
      <p className="mt-4 max-w-2xl text-slate-400 text-lg leading-relaxed">
        A <span className="text-teal">LangGraph</span> incident investigation &amp;
        controlled remediation agent for Kubernetes. It investigates over a
        hypothesis ledger, proposes a scoped fix, pauses for your approval, and{" "}
        <span className="text-violet">verifies real recovery</span> — not just a
        green control-plane response.
      </p>

      <div className="flex flex-wrap items-center gap-3 mt-7">
        <button
          onClick={onStart}
          disabled={running && phase !== "resolved" && phase !== "escalated"}
          className="group relative rounded-xl px-6 py-3 font-medium bg-teal text-ink-950 shadow-glow transition hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {phase === "idle" ? "▶ Run incident" : "▶ Re-run"}
        </button>
        <button
          onClick={onReset}
          className="rounded-xl px-5 py-3 font-medium border border-ink-600 text-slate-300 hover:bg-ink-800 transition"
        >
          Reset
        </button>
        <a
          href="https://github.com/niteshnankani-svg/claude-contract-agent"
          target="_blank"
          rel="noreferrer"
          className="rounded-xl px-5 py-3 font-medium border border-ink-600 text-slate-300 hover:bg-ink-800 transition"
        >
          ★ GitHub
        </a>
        <StatusPill phase={phase} />
      </div>
    </header>
  );
}

function StatusPill({ phase }: { phase: Phase }) {
  const map: Record<Phase, { t: string; c: string }> = {
    idle: { t: "ready", c: "#8b98a5" },
    investigating: { t: "investigating…", c: "#2dd4bf" },
    awaiting_approval: { t: "awaiting approval", c: "#fbbf24" },
    executing: { t: "remediating…", c: "#fb7185" },
    resolved: { t: "✓ resolved — recovery verified", c: "#2dd4bf" },
    escalated: { t: "escalated — no change made", c: "#fb7185" },
  };
  const s = map[phase];
  return (
    <span
      className="ml-1 text-sm font-mono px-3 py-1.5 rounded-lg border"
      style={{ color: s.c, borderColor: s.c + "55", background: s.c + "12" }}
    >
      {s.t}
    </span>
  );
}

function PanelTitle({
  eyebrow,
  title,
  accent,
}: {
  eyebrow: string;
  title: string;
  accent: string;
}) {
  return (
    <div className="mb-4">
      <div className="text-[11px] uppercase tracking-widest font-mono" style={{ color: accent }}>
        {eyebrow}
      </div>
      <div className="font-display font-semibold text-lg text-slate-100">{title}</div>
    </div>
  );
}

function Legend() {
  const items = [
    ["#2dd4bf", "flow"],
    ["#fbbf24", "gate ⏸"],
    ["#fb7185", "write ⚡"],
    ["#a78bfa", "verify"],
  ];
  return (
    <div className="flex gap-4 mt-3 text-xs font-mono text-slate-500">
      {items.map(([c, l]) => (
        <span key={l} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />
          {l}
        </span>
      ))}
    </div>
  );
}

function Metrics({
  metrics,
  phase,
}: {
  metrics: { errorRate: number; p95: number };
  phase: Phase;
}) {
  const healthy = metrics.errorRate < 0.05;
  const pct = (metrics.errorRate * 100).toFixed(1);
  return (
    <section className="lg:col-span-2 rounded-2xl border border-ink-700/70 bg-ink-900/60 backdrop-blur p-5">
      <PanelTitle eyebrow="checkout · prod" title="Live telemetry" accent="#fb7185" />
      <div className="grid grid-cols-2 gap-4">
        <Stat
          label="error rate"
          value={phase === "idle" ? "—" : `${pct}%`}
          color={healthy ? "#2dd4bf" : "#fb7185"}
        />
        <Stat
          label="p95 latency"
          value={phase === "idle" ? "—" : `${metrics.p95}ms`}
          color={metrics.p95 < 300 ? "#2dd4bf" : "#fbbf24"}
        />
      </div>
      <div className="mt-4 h-2 rounded-full bg-ink-800 overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: healthy ? "#2dd4bf" : "#fb7185" }}
          animate={{ width: phase === "idle" ? "0%" : `${Math.min(metrics.errorRate * 200, 100)}%` }}
          transition={{ type: "spring", stiffness: 120, damping: 20 }}
        />
      </div>
      <div className="text-xs text-slate-500 mt-2 font-mono">
        recovery threshold &lt; 5% · verified by synthetic probe
      </div>
    </section>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="rounded-xl bg-ink-850/70 border border-ink-700/60 p-4">
      <div className="text-xs uppercase tracking-wider text-slate-500 font-mono">{label}</div>
      <div className="font-display text-3xl mt-1" style={{ color }}>
        {value}
      </div>
    </div>
  );
}

function Ledger({ hyps }: { hyps: Hypothesis[] }) {
  const statusColor: Record<string, string> = {
    open: "#8b98a5",
    supported: "#2dd4bf",
    confirmed: "#2dd4bf",
    contradicted: "#fb7185",
  };
  return (
    <section className="lg:col-span-3 rounded-2xl border border-ink-700/70 bg-ink-900/60 backdrop-blur p-5">
      <PanelTitle eyebrow="reasoning" title="Hypothesis ledger" accent="#2dd4bf" />
      <div className="space-y-4">
        {hyps.map((h) => (
          <div key={h.id}>
            <div className="flex items-center justify-between text-sm">
              <span className="font-mono text-slate-300">{h.id}</span>
              <span
                className="text-xs font-mono px-2 py-0.5 rounded"
                style={{ color: statusColor[h.status], background: statusColor[h.status] + "18" }}
              >
                {h.status} · {(h.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="text-xs text-slate-500 mt-1 mb-1.5">{h.statement}</div>
            <div className="h-1.5 rounded-full bg-ink-800 overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ background: statusColor[h.status] }}
                animate={{ width: `${h.confidence * 100}%` }}
                transition={{ type: "spring", stiffness: 140, damping: 20 }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ApprovalGate({
  onApprove,
  onReject,
}: {
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-950/70 backdrop-blur-sm"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div
        className="w-full max-w-lg rounded-2xl border border-amber/40 bg-ink-850 p-6 shadow-glow"
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, y: 20 }}
        transition={{ type: "spring", stiffness: 260, damping: 22 }}
      >
        <div className="flex items-center gap-2 text-amber font-mono text-sm">
          <span>⏸</span> human_review — durable interrupt
        </div>
        <h3 className="font-display text-2xl mt-2 text-slate-100">
          Approve remediation?
        </h3>
        <div className="mt-4 rounded-xl bg-ink-900/80 border border-ink-700 p-4 font-mono text-[12.5px] leading-relaxed">
          <div className="text-slate-400">action_type <span className="text-slate-200">rollback_deployment</span></div>
          <div className="text-slate-400">target      <span className="text-slate-200">deployment/checkout</span></div>
          <div className="text-slate-400">to_revision <span className="text-teal">checkout-6a1b</span></div>
          <div className="text-slate-400">bound_to    <span className="text-amber">resource_version=41</span></div>
          <div className="text-slate-400">compensation<span className="text-slate-200"> re-deploy 7f2c if probe fails</span></div>
        </div>
        <p className="text-xs text-slate-500 mt-3">
          Approval binds to this exact plan and resource version. If the cluster
          drifts before execution, the executor refuses — a stale approval can
          never authorise a changed plan.
        </p>
        <div className="flex gap-3 mt-5">
          <button
            onClick={onApprove}
            className="flex-1 rounded-xl px-4 py-3 font-medium bg-teal text-ink-950 hover:brightness-110 transition"
          >
            ✓ Approve &amp; execute
          </button>
          <button
            onClick={onReject}
            className="flex-1 rounded-xl px-4 py-3 font-medium border border-rose/50 text-rose hover:bg-rose/10 transition"
          >
            ✕ Reject
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

function Footer() {
  return (
    <footer className="mt-14 pt-6 border-t border-ink-800 text-sm text-slate-500 flex flex-wrap items-center justify-between gap-3">
      <span>
        Built with Vite · React · Tailwind · Framer Motion — visualising the
        Python LangGraph agent.
      </span>
      <span className="font-mono text-xs">
        safety in code, not the model · Apache-2.0
      </span>
    </footer>
  );
}
