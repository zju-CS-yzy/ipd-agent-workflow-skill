# Architecture

[English](architecture.md) | [简体中文](architecture.zh-CN.md)

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
| `ipdctl.i18n` / `messages.yaml` | Resolve `en` or `zh-CN` presentation text from an immutable per-call translator | Translate machine contracts, mutate project facts, or keep process-global locale state |
| `ipdctl.dashboard` | Orchestrate and atomically publish the generated Dashboard tree and hashes | Become a writable source of truth |
| `ipdctl.dashboard_model` | Normalize process/state/runtime facts into canonical state and typed graph projections | Invent facts or mutate source state |
| `ipdctl.dashboard_svg` | Render deterministic hierarchical SVGs with swimlanes, typed nodes, and routed trace edges | Invoke Graphviz or read project files |
| `ipdctl.dashboard_html` | Render the offline Dashboard, matrices, filters, zoom, and node details | Persist edits or depend on hosted assets |
| `ipdctl.traceability` | Resolve global entity IDs and dangling links | Treat free text as a valid entity reference |
| `ipdctl.policy` | Load and validate safe tailoring policy | Permit non-negotiable controls to be disabled |
| `ipdctl.repository` | Read Git/SVN root, revision, and dirty state | Commit, update, tag, push, or modify VCS state |
| `ipdctl.reconcile` | Map changed paths to deliverables through explicit bindings | Guess authoritative ownership from filenames |
| `ipdctl.cli_v2` | Expose the full tailoring and execution lifecycle | Hide validation errors or overwrite state implicitly |

## Data flow

An Agent initializes a project, tailors a process from the task profile, reads context, claims eligible work, attaches evidence, and submits it for review. Deliverables and Gates are explicit review subjects. Authorized human decisions are appended rather than replaced; the latest authorized human decision governs the current outcome while the full history remains auditable. `advance-phase` succeeds only after the current phase's required Gate subjects satisfy their controls. Refresh derives dashboards from process/state facts. Verify checks process, state, evidence paths, output hashes, and repository reconciliation. Final deliverable and TR/DCP approval never comes from an Agent identity.

State writes use a temporary file in the destination directory followed by an atomic replacement. A successful engine operation increments `revision` exactly once and returns a new object, leaving the input unchanged.

Dashboard refresh builds a complete staging tree before replacing the previous
generated tree. `data/state.json` and `data/graph.json` are sanitized read-only
projections, not alternate state stores. SVG and HTML views consume those same
facts, and every managed file is covered by the Dashboard manifest.

Language is a presentation concern. `init --locale` writes
`task_profile.presentation.locale`; later commands resolve a translator for that
project and pass it explicitly to CLI and Dashboard rendering. A missing locale
in a v0.2 profile means `en` and does not trigger a profile rewrite. Changing
locale invalidates the generated Dashboard but must not re-tailor the process or
change state, evidence, reviews, claims, graph IDs, or topology.

## Contract boundaries

[schemas/project_state.schema.json](../schemas/project_state.schema.json) is the portable structural contract. Python validation adds global constraints that JSON Schema does not conveniently express, including dependency cycles, global entity-ID uniqueness, referential integrity, ordered authorized-human decision resolution, and phase-advance readiness.

[policies/default/tailoring_rules.yaml](../policies/default/tailoring_rules.yaml) preserves non-negotiable governance invariants. Generic task-type extensions live under `policies/task-types/`; PyYAML is used with safe loading and deterministic atomic writes.

The runtime automatically records UTC timestamps for events and claim leases. It does not infer reviewer authority or capture personal checkout paths in state. Callers may record approved external identifiers or immutable VCS revisions as evidence.

Commands, parameters, filenames, YAML/JSON keys, schema paths, IDs, statuses,
relations, and report codes remain English in every locale. Framework-owned
presentation labels may be localized; user-authored names, paths, evidence, and
descriptions are preserved verbatim. Machine-readable JSON retains stable
English fields and enums even when its optional display labels are localized.
