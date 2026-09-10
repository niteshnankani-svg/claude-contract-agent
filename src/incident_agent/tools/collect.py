"""Read-only evidence collectors. Each returns a typed Observation."""

from __future__ import annotations

from ..environment import FakeCluster
from ..state import Observation


def collect_telemetry(cluster: FakeCluster, service: str, window: int) -> Observation:
    m = cluster.get_metrics(service, window)
    summary = (
        f"error_rate={m['error_rate']:.1%}, p95={m['p95_latency_ms']}ms "
        f"over {window}m"
    )
    return Observation(
        kind="telemetry",
        service=service,
        summary=summary,
        data=m,
        trusted_for_reasoning=True,
    )


def collect_deployment(cluster: FakeCluster, service: str) -> Observation:
    d = cluster.get_deployments(service)
    active = d["active_revision"]
    prior = [r for r in d["revisions"] if r["name"] != active]
    changed = None
    if prior:
        last = prior[-1]
        added = {
            k: v for k, v in _active_config(d).items() if last["config"].get(k) != v
        }
        changed = added or None
    summary = f"active={active} rv={d['resource_version']}"
    if changed:
        summary += f"; config delta vs prior: {changed}"
    return Observation(
        kind="deployment",
        service=service,
        summary=summary,
        data={**d, "config_delta": changed},
        trusted_for_reasoning=True,
    )


def _active_config(deployments: dict) -> dict:
    active = deployments["active_revision"]
    return next(r["config"] for r in deployments["revisions"] if r["name"] == active)


def collect_topology(cluster: FakeCluster, service: str) -> Observation:
    t = cluster.get_topology(service)
    return Observation(
        kind="topology",
        service=service,
        summary=f"depends_on={t['depends_on']}",
        data=t,
        trusted_for_reasoning=True,
    )


def run_probe(cluster: FakeCluster, service: str) -> Observation:
    p = cluster.probe(service)
    return Observation(
        kind="probe",
        service=service,
        summary=f"synthetic_checkout_ok={p['synthetic_checkout_ok']}",
        data=p,
        trusted_for_reasoning=True,
    )
