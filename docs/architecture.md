# Architecture

The repository has two coordinated surfaces: `SKILL.md` guides Agent decisions, while `ipdctl` supplies deterministic tailoring, state transitions, generated views, and local repository reconciliation.

## Components

| Component | Responsibility | Must not do |
| --- | --- | --- |
| `SKILL.md` and `references/` | Route IPD work, evidence decisions, and human-gate boundaries | Replace project facts or grant mutation authority |
| `ipdctl.state` | Create, load, and atomically persist state | Accept partial writes or silently repair invalid state |
| `ipdctl.validation` | Enforce structure, cross-references, evidence, closure, and gate invariants | Mutate state |
| `ipdctl.engine` | Return revised copies for legal transitions | Finalize a gate without recorded authorized-human approval |
| `ipdctl.process_model` / `tailoring` | Compile generic task profiles into stable IPD process facts | Embed project-instance data |
| `ipdctl.dependencies` | Find cycles and unmet deliverable dependencies | Infer missing dependencies |
| `ipdctl.runtime` | Record Agent claims, leases, and command events | Authenticate human identities or provide distributed locking |
| `ipdctl.dashboard` | Render HTML/JSON/Markdown views and hashes | Become a writable source of truth |
| `ipdctl.traceability` | Resolve global entity IDs and dangling links | Treat free text as a valid entity reference |
| `ipdctl.policy` | Load and validate safe tailoring policy | Permit non-negotiable controls to be disabled |
| `ipdctl.repository` | Read Git/SVN root, revision, and dirty state | Commit, update, tag, push, or modify VCS state |
| `ipdctl.reconcile` | Map changed paths to deliverables through explicit bindings | Guess authoritative ownership from filenames |
| `ipdctl.cli_v2` | Expose the full tailoring and execution lifecycle | Hide validation errors or overwrite state implicitly |

## Data flow

An Agent initializes a project, tailors a process from the task profile, reads context, claims eligible work, attaches evidence, and submits it for review. Authorized human review is recorded before acceptance. Refresh derives dashboards from process/state facts. Verify checks process, state, evidence paths, output hashes, and repository reconciliation. Final deliverable and TR/DCP approval never comes from an Agent identity.

State writes use a temporary file in the destination directory followed by an atomic replacement. A successful engine operation increments `revision` exactly once and returns a new object, leaving the input unchanged.

## Contract boundaries

[schemas/project_state.schema.json](../schemas/project_state.schema.json) is the portable structural contract. Python validation adds global constraints that JSON Schema does not conveniently express, including dependency cycles, global entity-ID uniqueness, referential integrity, and conflicts among gate reviews.

[policies/default/tailoring_rules.yaml](../policies/default/tailoring_rules.yaml) preserves non-negotiable governance invariants. Generic task-type extensions live under `policies/task-types/`; PyYAML is used with safe loading and deterministic atomic writes.

The runtime does not store timestamps automatically, infer reviewer authority, or capture personal checkout paths in state. Callers may record approved external identifiers or immutable VCS revisions as evidence.
