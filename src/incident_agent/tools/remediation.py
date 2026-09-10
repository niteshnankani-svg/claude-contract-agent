"""The single write tool: an idempotent, precondition-guarded rollback."""

from __future__ import annotations

from ..environment import FakeCluster
from ..state import ActionRecord, ProposedAction


def execute_rollback(
    cluster: FakeCluster, action: ProposedAction, idempotency_key: str
) -> ActionRecord:
    result = cluster.apply_rollback(
        service=action["target"].split("/", 1)[1],
        target_revision=action["params"]["target_revision"],
        expected_resource_version=action["resource_version"],
        idempotency_key=idempotency_key,
    )
    status_map = {
        "succeeded": "succeeded",
        "deduplicated": "deduplicated",
        "precondition_failed": "failed",
        "failed": "failed",
    }
    return ActionRecord(
        idempotency_key=idempotency_key,
        action_type=action["action_type"],
        target=action["target"],
        resource_version=action["resource_version"],
        status=status_map.get(result["status"], "failed"),  # type: ignore[arg-type]
        detail=result["detail"],
    )
