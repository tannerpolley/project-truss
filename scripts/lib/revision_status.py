"""Pure state evaluation for the required post-revision loop."""
from __future__ import annotations

from typing import Any, Mapping


def evaluate_revision_status(evidence: Mapping[str, Any]) -> dict[str, Any]:
    gates = [
        (not evidence.get("validation_current"), "validation-required", "run-validation"),
        (bool(evidence.get("source_dirty")) or not evidence.get("source_committed"), "commit-required", "commit-source"),
        (not evidence.get("deployment_current"), "deployment-stale", "sync-live"),
        (not evidence.get("installation_current"), "installation-stale", "refresh-plugin"),
        (not evidence.get("cleanup_current"), "cleanup-required", "run-cleanup"),
        (not evidence.get("fresh_session_acknowledged"), "fresh-session-required", "start-fresh-session"),
    ]
    for active, state, next_gate in gates:
        if active:
            return {
                "state": state,
                "next_gate": next_gate,
                "fresh_session_required": state == "fresh-session-required",
                "evidence": dict(evidence),
            }
    return {"state": "complete", "next_gate": None, "fresh_session_required": False, "evidence": dict(evidence)}
