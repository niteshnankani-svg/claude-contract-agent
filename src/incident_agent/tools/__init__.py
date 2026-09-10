"""Tool functions the agent may call.

Each tool takes the ``FakeCluster`` (or a real client with the same interface)
and returns a typed ``Observation``. Reads are side-effect free and may run
concurrently; the only write path is ``remediation.execute_rollback``.
"""

from .collect import collect_deployment, collect_telemetry, collect_topology, run_probe
from .remediation import execute_rollback

__all__ = [
    "collect_telemetry",
    "collect_deployment",
    "collect_topology",
    "run_probe",
    "execute_rollback",
]
