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
| `ipdctl.process_model` / `tailoring` | Compile `core -> task_type -> capability -> project` into stable IPD process facts and pure diffs | Embed project-instance data in reusable policies or infer migrations |
| `ipdctl.process_extensions` | Load and validate additive `.ipd/process_extensions.yaml` Activities, Deliverables, relations, criteria, and migrations | Delete or override earlier-layer entities |
| `ipdctl.refinement` | Validate fingerprinted `expand` plans, derive structural leaf closure, and merge reviewed additions into the project layer | Infer decomposition, mutate runtime state, or treat `refines` as execution order |
| `ipdctl.dependencies` | Find cycles and unmet deliverable dependencies | Infer missing dependencies |
| `ipdctl.runtime` | Record Agent claims, leases, and command events | Authenticate human identities or provide distributed locking |
| `ipdctl.transaction` | Serialize one project's CLI mutations and recover interrupted multi-file writes | Coordinate different clones or replace VCS locking |
| `ipdctl.i18n` / `messages.yaml` | Resolve `en` or `zh-CN` presentation text from an immutable per-call translator | Translate machine contracts, mutate project facts, or keep process-global locale state |
| `ipdctl.dashboard` | Orchestrate and atomically publish the generated Dashboard tree and hashes | Become a writable source of truth |
| `ipdctl.dashboard_model` | Normalize process/state/runtime facts into canonical state and typed graph projections | Invent facts or mutate source state |
| `ipdctl.dashboard_svg` | Render deterministic hierarchical SVGs with swimlanes, typed nodes, and routed trace edges | Invoke Graphviz or read project files |
| `ipdctl.dashboard_html` | Render the offline Dashboard, matrices, filters, zoom, and node details | Persist edits or depend on hosted assets |
| `ipdctl.governance_documents` | Deterministically render and verify the facts-derived governance registry and Gate plan | Parse arbitrary project prose or treat generated Markdown as authority |
| `ipdctl.traceability` | Resolve global entity IDs and dangling links | Treat free text as a valid entity reference |
| `ipdctl.policy` | Load and validate safe tailoring policy | Permit non-negotiable controls to be disabled |
| `ipdctl.repository` | Read Git/SVN root, revision, and dirty state | Commit, update, tag, push, or modify VCS state |
| `ipdctl.reconcile` | Validate bindings, capture exact path snapshots, and reconcile changed paths to one Deliverable owner | Guess authoritative ownership from filenames |
| `ipdctl.eligibility` | Project lifecycle and binding readiness into one shared context/Claim/Dashboard decision | Mutate state or authorize a human baseline decision |
| `ipdctl.cli_v2` | Expose the full tailoring and execution lifecycle | Hide validation errors or overwrite state implicitly |

## Data flow

An Agent initializes a project, compiles a process from the task profile and project extension, reads context, claims eligible work, attaches evidence, and submits it for review. Compilation is deterministic and additive in the fixed order `core -> task_type -> capability -> project`; every process node carries its layer/source provenance and phase-derived maturity, while TR and DCP keep independent criteria. Dependency validation rejects cycles and earlier-Phase Deliverables that depend on later-Phase Deliverables.

`tailor --preview` computes a pure five-part diff without writing. An actual re-tailor is blocked by an active Claim. A first effective removal of a historical Deliverable requires an explicit project migration mapping plus an authorized human application. The old state-only node retains its evidence and reviews as `superseded`; new targets start `planned`, and one append-only `process_migration` event records the decision. No heuristic redistributes historical acceptance.

The same boundary prevents an ordinary re-tailor from preserving old approval
while changing an existing Deliverable's semantics under the same ID. Such a
change requires a new ID and explicit migration. A semantic change that targets
an approved or already closed Phase—including TR/DCP criteria—is rejected
before writes; the preview remains available to design the controlled
replacement. A schema `1.0` process may receive only the deterministic core
provenance, maturity, and canonical readiness-criteria enrichment during its
schema `2.0` upgrade.

When an explicit project refinement trigger becomes due, `refine --preview`
validates a fingerprinted `expand` plan without writing. Authorized application
keeps the reviewed parent as an abstract historical aggregate and adds clean
planned children. Structural `refines` links are rendered and audited but do
not enter the `depends_on` graph. Gate readiness resolves abstract requirements
to concrete leaves; a changed leaf set invalidates the old approval, increments
the review epoch, and retains the earlier evidence as history. Binding impact
is reported, but Owner rules are never inferred or reassigned. Concrete
refined children require explicit user-authored Owners; placeholder and
abstract nodes remain non-claimable structural facts without Owner rules.

Claim preflight and every read surface consume one binding-eligibility projection. Each new Claim records an exact binding window; successful verification carries an exact artifact baseline into the next iteration. Existing dirty projects use an append-only, explicitly human-authorized baseline-adoption event rather than a fabricated Claim or VCS mutation. Deliverables and Gates are explicit review subjects. Entering Review binds one canonical ID in `project.current_iteration_subject`; every review and decision command must match it until the human decision clears the lock. Authorized human decisions are appended rather than replaced; the latest authorized human decision governs the current outcome while the full history remains auditable. `advance-phase` succeeds only after the current phase's required Gate subjects satisfy their controls. `render-dashboard` derives a current view without changing state or runtime. Formal Refresh is restricted to safe workflow boundaries, synchronizes repository facts, increments the state revision once, and moves to Verify. Verify recompiles the expected process, checks process extensions, state, evidence paths, facts-derived governance content, output hashes, binding eligibility, and repository reconciliation. Final deliverable and TR/DCP approval never comes from an Agent identity.

State writes use a temporary file in the destination directory followed by an atomic replacement. A successful engine operation increments `revision` exactly once and returns a new object, leaving the input unchanged. A crash-released operating-system mutex keyed by the resolved project path covers recovery and the complete command; its hashed lock file lives in the current user's system temporary directory and is not a project artifact. Mutating CLI commands then hold a project-local journal across their complete read, preflight, compute, and write cycle. The journal first acquires its canonical name, then snapshots authority files and generated outputs before mutation, restores them after an exception or terminated process, and atomically retires its active name before post-commit cleanup. A concurrent project command in the same local user environment fails explicitly and may be retried after the active command finishes. Different operating-system accounts or temporary-directory namespaces must not operate the same checkout concurrently. If the operating system cannot establish whether a journal owner is still running, recovery fails closed and leaves the journal untouched.

Dashboard refresh builds a complete staging tree before replacing the previous
generated tree. `data/state.json` and `data/graph.json` are sanitized read-only
projections, not alternate state stores. SVG and HTML views consume those same
facts, and every managed file is covered by the Dashboard manifest.
`governance.md` is rendered in the same staging tree from canonical version,
process, state, Deliverable, and Gate facts. Validation reconstructs its exact
expected bytes instead of trusting the document or manifest hash.

Language is a presentation concern. `init --locale` writes
`task_profile.presentation.locale`; later commands resolve a translator for that
project and pass it explicitly to CLI and Dashboard rendering. A missing locale
in a v0.2 profile means `en` and does not trigger a profile rewrite. Changing
locale invalidates the generated Dashboard but must not re-tailor the process or
change state, evidence, reviews, claims, graph IDs, or topology.

## Contract boundaries

[schemas/project_state.schema.json](../schemas/project_state.schema.json), [schemas/tailored_process.schema.json](../schemas/tailored_process.schema.json), [schemas/process_extensions.schema.json](../schemas/process_extensions.schema.json), [schemas/refinement_plan.schema.json](../schemas/refinement_plan.schema.json), and [schemas/artifact_bindings.schema.json](../schemas/artifact_bindings.schema.json) are portable structural contracts. Python validation adds global constraints that JSON Schema does not conveniently express, including dependency and refinement cycles, phase monotonicity, global entity-ID uniqueness, referential integrity, ordered authorized-human decision resolution, explicit migration completeness, Gate leaf-closure epochs, actual changed-path owner conflicts, Claim-window provenance, and phase-advance readiness.

[policies/default/tailoring_rules.yaml](../policies/default/tailoring_rules.yaml) preserves non-negotiable governance invariants. Generic task-type extensions live under `policies/task-types/`; reusable, project-neutral capabilities live under `policies/capabilities/`. The sourced-component capability models candidate validation, selection decision, and integration baseline without instance paths or Owner inference. PyYAML is used with safe loading and deterministic atomic writes.

Binding roles remain separate from process provenance. A missing role or
`role: owner` maps one Deliverable and may authorize its Claim;
`role: shared_evidence` is non-critical, may cite several Deliverables, and
cannot authorize a Claim or satisfy a critical Owner requirement.

New compilation emits process schema `2.0`. Schema `1.0` remains readable when
its semantic projection still matches a profile without capabilities and an
empty project extension; enabling either requires preview and re-tailoring.

The runtime automatically records UTC timestamps for events and claim leases. It does not infer reviewer authority or capture personal checkout paths in state. Callers may record approved external identifiers or immutable VCS revisions as evidence.

Commands, parameters, filenames, YAML/JSON keys, schema paths, IDs, statuses,
relations, and report codes remain English in every locale. Framework-owned
presentation labels may be localized; user-authored names, paths, evidence, and
descriptions are preserved verbatim. Machine-readable JSON retains stable
English fields and enums even when its optional display labels are localized.
