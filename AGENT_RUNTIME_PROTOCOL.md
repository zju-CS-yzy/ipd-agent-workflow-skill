# Agent Runtime Protocol

The runtime uses one auditable loop for every deliverable:

`context -> claim -> work -> close -> review -> refresh -> verify`

## Command contract

1. `ipdctl context` reads the current Phase, TR, DCP, Gate, available work,
   blockers, active claims, and repository facts.
2. `ipdctl claim <deliverable>` checks predecessor closure, records an Agent
   lease, and moves eligible work to `in_progress`.
3. **work** is the authorized engineering activity performed outside the
   controller. The Agent must preserve the deliverable ID and produce durable
   evidence.
4. `ipdctl close <deliverable> --evidence <path>` submits the work as
   `ready_for_review`; it never accepts the deliverable.
5. `ipdctl review <deliverable>` starts review. Agent reviews may recommend a
   decision, but cannot create final approval.
6. `ipdctl approve` or `ipdctl reject` records an explicitly authorized human
   decision. An Agent identity is rejected for either final decision.
7. `ipdctl refresh` rebuilds dashboards, graphs, and matrices strictly from
   process and state facts.
8. `ipdctl verify` validates schemas, dependencies, review authority,
   traceability, repository reconciliation, and generated-output freshness.

## State ownership

- `.ipd/task_profile.yaml` describes the project and tailoring inputs.
- `.ipd/tailored_process.yaml` describes what the project is required to do.
- `.ipd/project_state.yaml` records completed work, reviews, and gate facts.
- `.ipd/agent_runtime.yaml` records temporary Agent claims and runtime events.
- `.ipd/dashboard/` is generated output and must not be edited as a fact source.

## Authority boundaries

- A claim is a local working-tree lease, not a distributed lock across clones.
- `accepted` requires evidence and an authorized human approval review.
- A rejected deliverable remains auditable and may be reclaimed into
  `in_progress` for rework.
- Final TR/DCP approval also requires an authorized human approval record and
  no conflicting authorized human rejection.
- Repository commands are read-only. The framework never commits, pushes,
  pulls, updates, tags, or rewrites history.
