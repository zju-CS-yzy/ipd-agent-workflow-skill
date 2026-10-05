"""Shared workflow and state-machine constants."""

SCHEMA_VERSION = "2.0"

WORKFLOW_STEPS = (
    "context",
    "claim",
    "work",
    "close",
    "review",
    "refresh",
    "verify",
)
PROJECT_PHASES = ("concept", "plan", "develop", "qualify", "launch", "lifecycle")

CLAIM_STATUSES = ("open", "supported", "rejected")
DELIVERABLE_STATUSES = (
    "planned",
    "in_progress",
    "ready_for_review",
    "in_review",
    "accepted",
    "rejected",
    "blocked",
    "superseded",
)
GATE_KINDS = ("TR", "DCP", "Gate")
GATE_STATUSES = ("planned", "ready", "approved", "rejected")
REVIEWER_TYPES = ("human", "agent")
REVIEW_DECISIONS = ("approve", "reject")
TRACE_RELATIONS = ("supports", "depends_on", "verifies", "supersedes", "refines")

DELIVERABLE_TRANSITIONS = {
    "planned": {"in_progress", "blocked", "superseded"},
    "in_progress": {"ready_for_review", "blocked", "superseded"},
    "ready_for_review": {"in_review", "in_progress", "blocked", "superseded"},
    "in_review": {"accepted", "rejected", "in_progress", "blocked", "superseded"},
    "accepted": {"superseded"},
    "rejected": {"in_progress", "superseded"},
    "blocked": {"in_progress", "superseded"},
    "superseded": set(),
}

TASK_TYPES = (
    "software",
    "hardware",
    "embedded",
    "robotics",
    "ai_system",
    "material_change",
)
