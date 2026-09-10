"""A small in-memory stand-in for a running Kubernetes application.

The decision brief is emphatic that a successful run must demonstrate recovery
in a *running* environment, and that a green Kubernetes API response is not
enough — the verifier must use fresh measurements and an application-level
probe. This module provides exactly that surface so the agent's remediation
has a real effect that a probe can independently confirm.

It is intentionally *not* a mock that returns canned strings. State mutates:
a bad rollout raises the error rate, and rolling back to the last healthy
revision actually restores it. Swap this class for real Datadog / Prometheus /
kube-apiserver clients behind the same method names to run against live infra.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Revision:
    name: str
    healthy: bool
    config: dict[str, Any]


@dataclass
class ServiceState:
    name: str
    revisions: list[Revision]
    active_revision: str
    resource_version: int
    dependencies: list[str] = field(default_factory=list)


class FakeCluster:
    """A tiny fault-injected cluster. Thread of truth for metrics + a probe."""

    def __init__(self, spec: dict[str, Any]):
        self._services: dict[str, ServiceState] = {}
        for svc in spec["services"]:
            self._services[svc["name"]] = ServiceState(
                name=svc["name"],
                revisions=[Revision(**r) for r in svc["revisions"]],
                active_revision=svc["active_revision"],
                resource_version=svc.get("resource_version", 1),
                dependencies=svc.get("dependencies", []),
            )
        # Idempotency: remember which mutation keys we have already applied.
        self._applied_keys: dict[str, str] = {}

    # -- read surface ------------------------------------------------------
    def _active(self, service: str) -> Revision:
        s = self._services[service]
        return next(r for r in s.revisions if r.name == s.active_revision)

    def resource_version(self, service: str) -> str:
        return str(self._services[service].resource_version)

    def get_metrics(self, service: str, window_minutes: int) -> dict[str, Any]:
        """Error rate / latency reflect whether the active revision is healthy."""
        healthy = self._active(service).healthy
        return {
            "service": service,
            "window_minutes": window_minutes,
            "error_rate": 0.004 if healthy else 0.38,
            "p95_latency_ms": 180 if healthy else 920,
            "requests_per_min": 5400,
        }

    def get_deployments(self, service: str) -> dict[str, Any]:
        s = self._services[service]
        return {
            "service": service,
            "active_revision": s.active_revision,
            "resource_version": str(s.resource_version),
            "revisions": [
                {"name": r.name, "healthy_at_rollout": r.healthy, "config": r.config}
                for r in s.revisions
            ],
        }

    def get_topology(self, service: str) -> dict[str, Any]:
        s = self._services[service]
        return {"service": service, "depends_on": list(s.dependencies)}

    def probe(self, service: str) -> dict[str, Any]:
        """Application-level synthetic transaction. This is what the verifier
        trusts to close an incident, not a control-plane 200."""
        healthy = self._active(service).healthy
        return {
            "service": service,
            "synthetic_checkout_ok": healthy,
            "checked_at": time.time(),
        }

    def last_healthy_revision(self, service: str) -> Optional[str]:
        s = self._services[service]
        for r in reversed(s.revisions):
            if r.name != s.active_revision and r.healthy:
                return r.name
        return None

    # -- write surface (guarded, idempotent) -------------------------------
    def apply_rollback(
        self,
        service: str,
        target_revision: str,
        expected_resource_version: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Roll ``service`` back to ``target_revision``.

        Enforces an optimistic-concurrency precondition on resource_version and
        de-duplicates on the idempotency key, so a retried or replayed execution
        cannot double-apply the change.
        """
        if idempotency_key in self._applied_keys:
            return {"status": "deduplicated", "detail": self._applied_keys[idempotency_key]}

        s = self._services[service]
        if expected_resource_version != str(s.resource_version):
            return {
                "status": "precondition_failed",
                "detail": (
                    f"resource_version changed: approved for "
                    f"{expected_resource_version}, live is {s.resource_version}"
                ),
            }
        if not any(r.name == target_revision for r in s.revisions):
            return {"status": "failed", "detail": f"unknown revision {target_revision}"}

        s.active_revision = target_revision
        s.resource_version += 1
        detail = f"rolled {service} back to {target_revision} (rv={s.resource_version})"
        self._applied_keys[idempotency_key] = detail
        return {"status": "succeeded", "detail": detail}

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(
            {name: vars(s) for name, s in self._services.items()}
        )
