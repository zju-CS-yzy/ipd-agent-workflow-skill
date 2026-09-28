"""Shared workflow constants."""

SCHEMA_VERSION = "1.0"

WORKFLOW_STEPS = ("context", "claim", "work", "close", "verify")
PROJECT_PHASES = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")

CLAIM_STATUSES = ("open", "supported", "rejected")
DELIVERABLE_STATUSES = (
    "planned",
    "in_progress",
    "blocked",
    "ready_for_review",
    "accepted",
)
GATE_KINDS = ("TR", "DCP")
GATE_STATUSES = ("planned", "ready", "approved", "rejected")
REVIEWER_TYPES = ("human", "agent")
REVIEW_DECISIONS = ("approve", "reject")
TRACE_RELATIONS = ("supports", "depends_on", "verifies", "supersedes")

DELIVERABLE_TRANSITIONS = {
    "planned": {"in_progress", "blocked"},
    "in_progress": {"blocked", "ready_for_review"},
    "blocked": {"in_progress"},
    "ready_for_review": {"in_progress", "accepted"},
    "accepted": set(),
}
