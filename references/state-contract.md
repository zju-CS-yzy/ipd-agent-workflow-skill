# State Contract

Read this reference when creating, changing, validating, or recovering `.ipd/project_state.yaml`.

## Top-level fields

- `schema_version`: canonical contract version `2.0`; the validator can still read v0.1 `1.0` JSON state for compatibility.
- `revision`: non-negative integer incremented once per runtime transition.
- `project`: name, task types, product phase, current workflow step, current TR/DCP/Gate, and optional repository metadata.
- `claims`: assertions with `open`, `supported`, or `rejected` status and evidence references.
- `deliverables`: work products, eight-state lifecycle, dependencies, evidence, review records, and optional compiled `provenance`, `maturity`, replacement, `definition_state`, trigger, and `refines` metadata.
- `gates`: TR/DCP readiness, required deliverables, review records, concrete-requirement fingerprint, review epoch, and stale state.
- `traceability`: typed links among claims, deliverables, and gates.

Entity IDs are globally unique lowercase identifiers. They may contain digits, `.`, `_`, and `-`. Unknown fields are rejected so misspellings cannot silently alter governance.

The JSON Schema performs structural validation. `ipdctl validate` additionally enforces global ID uniqueness, dependency existence and acyclicity, closure order, trace-link targets, gate prerequisites, and authorized-human final approval.

`.ipd/agent_runtime.yaml` is a separate runtime fact source. It records one or
zero `active_claims`, append-only command events, `last_refresh`, and
`last_verification`. A successful verification records `status`,
`state_revision`, and `input_fingerprint`; these fields do not replace the
project state or Dashboard manifest. Every new `claim` event contains a
non-empty Deliverable, Actor, timezone-aware timestamp, non-negative
`state_revision`, and an exact `binding_window`. Legacy events remain readable
history but cannot prove ownership for new path changes. Authorized migration
baselines are append-only `artifact_baseline_adopted` events.
An applied process migration appends one `process_migration` event with its
authorized human Actor, reason, state revision, old/new process schema
versions, and one or more explicit Deliverable `migrations`,
`gate_migrations`, or `dependency_corrections`. Re-running an already-applied
migration does not duplicate this event.
An applied progressive refinement appends one strict
`process_refinement_applied` event containing its plan ID/digest, base and
result process fingerprints, authorized human Actor and reason, root, child
IDs, state revision, and invalidated Gates. An exact replay is a no-op; an ID
reuse with a changed digest or base is a conflict.

The tailored process is a separate contract. New compilation emits process
schema `2.0`, where Phase, Activity, Deliverable, TR, DCP, and Gate nodes carry
`provenance` and `maturity`, TR/DCP contain independent criteria, and the
top-level `migrations` list records explicit replacement/split intent;
`gate_migrations` records one-to-one legacy Gate redirects and
`dependency_corrections` records exact same-ID dependency repair intent. The
runtime can continue to read schema `1.0` when its semantic projection matches
a profile without capabilities and an empty project extension.

## Safe persistence

The runtime writes each file through a same-directory temporary file and atomically replaces the destination. A crash-released operating-system mutex keyed by the resolved project path serializes recovery and all project command access; its hashed lock file stays outside the project in the system temporary directory. Mutating CLI commands also hold a project-local recovery journal across their complete read/preflight/compute/write cycle. The canonical journal name is acquired before its snapshot; the transaction restores its state, runtime, report, and Dashboard scope after an exception or terminated process, then retires the active journal name before cleaning a committed backup. Concurrent commands fail explicitly instead of applying stale computed state. Recovery fails closed if the journal owner's liveness cannot be established. A failed validation or transition therefore does not publish a partial project bundle. Do not hand-edit `revision` to conceal a change.

`.ipd/project_state.yaml` is source state and can be reviewed in version control. `.ipd/dashboard/`, reconciliation reports, and verification reports are generated views. The v0.1 `.ipd/project-state.json` path is discovered for read/validation compatibility but is never dual-written.

## CLI behavior

```bash
ipdctl init [TARGET] [--name NAME] [--task-type TYPE ...] [--locale en|zh-CN] [--force]
ipdctl tailor [TARGET] [--profile PATH] [--output PATH] [--preview] [--json] [--apply-migrations] [--actor HUMAN --actor-type human --authorized --reason TEXT]
ipdctl refine [TARGET] --plan PATH [--preview | --apply] [--json] [--actor HUMAN --actor-type human --authorized --reason TEXT]
ipdctl context [TARGET] [--json]
ipdctl status [TARGET] [--json]
ipdctl adopt-baseline [TARGET] [--preview] [--json] [--actor HUMAN --actor-type human --authorized --reason TEXT]
ipdctl claim DELIVERABLE [--project-root TARGET] [--actor NAME] [--lease-minutes N] [--recover]
ipdctl close DELIVERABLE --evidence PATH [--evidence PATH ...] [--project-root TARGET] [--actor NAME] [--status ready_for_review|blocked] [--note TEXT]
ipdctl review SUBJECT --reviewer NAME [--project-root TARGET] [--actor-type agent|human] [--authorized] [--decision approve|reject] [--evidence PATH]
ipdctl approve SUBJECT --reviewer NAME --actor-type human --authorized --evidence PATH [--project-root TARGET]
ipdctl reject SUBJECT --reviewer NAME --actor-type human --authorized --evidence PATH [--project-root TARGET]
ipdctl refresh [TARGET]
ipdctl verify [TARGET] [--json]
ipdctl advance-phase [TARGET]
ipdctl repository [TARGET] [--json]
ipdctl reconcile [TARGET] [--bindings PATH] [--json]
ipdctl validate [TARGET] [--policy PATH] [--json]
```

`status` is an alias for `context`. `init` refuses to replace existing state
unless `--force` is explicit. `tailor --output`, when supplied, must resolve to
the canonical `.ipd/tailored_process.yaml`. `tailor --preview` is read-only;
its JSON form uses the fixed keys `added`, `removed`, `changed`, `migrations`,
and `ambiguous`. State-changing commands validate
before writing. `context` refuses to summarize invalid state. `verify` exits
non-zero for state, process, runtime, evidence, Dashboard, or reconciliation
errors. `repository` and repository inspection within reconciliation are
read-only and degrade to `kind: none` when neither Git nor SVN is available.
`validate --json` writes one stable English-keyed result to standard output for
both valid and invalid input; it includes status, scope, target, state metadata,
checks, and issues. Human-readable output remains locale-aware. The Windows CLI
configures its real console streams for UTF-8 so Chinese text remains intact
when redirected or captured.

`refine` defaults to preview unless `--apply` is explicit. Preview is
zero-write and returns the plan/base/result fingerprints, semantic diff, Gate
impact, Binding impact, blockers, and applicability. Application requires a
`due` trigger, current-Phase root, no active Claim, an exact base fingerprint,
and an authorized human Actor and reason. It preserves the parent history,
adds children at `planned` with empty evidence and reviews, and never infers an
Owner binding. A child requiring an artifact Owner is not claimable until a
user-authored Owner rule exists.

The reviewable iteration is strictly serialized:

`claim -> work -> close -> review -> human approve/reject -> refresh -> verify`

Only one active claim is valid. A new claim may start from `context`, or from
`verify` only when the latest verification is still current. Use
`claim --recover` for an orphaned `in_progress` deliverable reported by
`context`; expired leases may be reclaimed, but an unexpired claim owned by a
different actor cannot be taken over. `close --status blocked` is the explicit
aborted-work path to `refresh` and still requires `refresh` plus `verify` before
the next claim.

`SUBJECT` may be a Deliverable ID, canonical `gate.*` ID, or a process-level
`tr.*` / `dcp.*` alias. State stores only canonical Gate facts. Every review is
retained, while the latest authorized human decision determines whether a
Deliverable or Gate is currently rejected or approved. `advance-phase` never
skips a Phase. Within each Phase the canonical decision order is TR, then DCP;
generic Gates follow both in deterministic ID order. A stale hand-edited
`current_gate` pointer is rejected rather than trusted. The current Phase must
also match the ordered `advance_phase` event history, so changing the complete
Phase/TR/DCP/Gate pointer bundle cannot bypass governance. Advancement requires
all current-Phase canonical Gates to be approved,
`last_verification.status` to be `passed`, the verified revision to equal the
current state revision, and a freshly calculated verification-input fingerprint
to match. The fingerprint covers the profile, canonical project process
extension, tailored process, project state, artifact bindings, active claim,
Claim history, local evidence content,
Phase advancement and refinement history, Dashboard manifest and outputs, repository facts,
and engineering changed
paths. Advancement leaves
the workflow at `refresh`; the new Phase must be refreshed and verified before
work continues.

`tailor` preserves user-authored bindings and regenerates one managed critical
`evidence/<deliverable-id>/**` binding for every current deliverable. It never
infers ownership for real source, test, documentation, configuration, tool,
firmware, or hardware paths; add explicit rules for those paths in
`.ipd/artifact_bindings.yaml`. Unbound changes under critical roots fail
reconciliation and verification, and an actually changed critical path cannot
resolve to multiple Deliverable owners. A mapped changed path also fails when
it is outside the current iteration's valid Claim binding window. A reviewed
dirty project that predates this protocol uses one explicitly authorized
`adopt-baseline` migration decision instead of a fabricated Claim. Successful
verification stores the exact artifact baseline for the next iteration.

Artifact Binding roles are distinct. A missing `role` preserves legacy Owner
semantics; explicit `role: owner` also uses one `deliverable` and may authorize
that Deliverable's Claim. `role: shared_evidence` uses a `deliverables` list,
must set `critical: false`, and only records shared supporting evidence. It
cannot authorize a Claim or satisfy the required Owner of a critical path.

Tailoring itself compiles `core -> task_type -> capability -> project`.
`task_profile.capability_patterns` selects reusable capability policies; the
canonical `.ipd/process_extensions.yaml` adds project Activities,
review-required Deliverables, generic Gates, typed relations, TR/DCP criteria,
and explicit Deliverable, Gate, and dependency-correction migrations plus
declared/applied refinements. Layers are additive and cannot override duplicate entity
or criterion IDs. Dependencies must be acyclic and phase-monotonic.

Any actual re-tailor is rejected while a Claim is active. Removing a historical
non-superseded Deliverable requires an explicit `replace`/`split` mapping and
`--apply-migrations`; the first effective migration also requires an
authorized human Actor and reason. The old Deliverable remains as a state-only
`superseded` node with preserved evidence/reviews and `replacement` plus full
`replacements` metadata. New targets remain `planned` and receive no copied
evidence, reviews, or approval. Missing or ambiguous mappings fail closed.
The same fail-closed boundary applies to in-place semantic changes of any
Deliverable with governed lifecycle history: a new ID plus explicit migration
is required. Ordinary re-tailoring also rejects changes to a Phase with an
approved Gate or an already closed Phase, including checkpoint criteria, while
leaving preview available and all authority files unchanged. The only upgrade
exception is first-time deterministic schema `1.0` enrichment with core
provenance, maturity, and canonical readiness criteria.

Candidate traceability starts from compiled process relations and preserves
state-owned Claim links whenever both endpoints survive. Explicit
`gate_migrations` may redirect one legacy Gate endpoint to one candidate Gate.
Preview reports trace additions/removals through `added`/`removed`, redirects
through `changed`, and unexplained Claim-link loss through `ambiguous`; apply
fails closed while any such blocker remains.

An exact same-ID dependency correction is permitted only when its declared
`before` set matches the current state and its `after` set matches the compiled
candidate. It requires `preserve_history: true`, `require_reapproval: true`,
`--apply-migrations`, and an authorized human Actor and reason on first apply.
Evidence and reviews remain attached, the affected Deliverable becomes
`blocked`, affected unapproved Gates become stale with a new review epoch, and
an affected approved Gate rejects the change instead of reopening implicitly.

A refinement requirement declares a Deliverable root, its initial concrete or
placeholder definition state, an `all_of` trigger over accepted Deliverables
or approved Gates, and `all_children_accepted` completion. A reviewed plan uses
`mode: expand` and the current process fingerprint. Applying it changes the
root to an abstract aggregate and adds same-Phase child Activities and
Deliverables. `refines` is acyclic structural ancestry and does not affect
dependency order. Gate readiness replaces abstract roots with their concrete
leaf closure. A changed closure invalidates approval and advances the Gate's
`review_epoch` without deleting prior evidence or reviews.
Every concrete refined child requires a user-authored artifact Owner before
Claim; placeholder and abstract nodes are structural and do not require one.

When `verify` passes in the final `lifecycle` Phase and every Gate in that Phase
is approved, `.ipd/agent_runtime.yaml` receives one `lifecycle_complete` event.
The event is idempotent and includes the Phase and current state revision;
there is no phase-advance command beyond it.

Machine contracts remain English: commands, options, filenames, identifiers,
YAML/JSON keys, statuses, relations, event names, and report codes. User-facing
CLI and generated Dashboard text use `task_profile.presentation.locale`
(`en` or `zh-CN`). A missing locale defaults to `en`; a locale-only change
requires `refresh` and `verify`, not `tailor`.

The Python engine exposes validated transitions for integrations. Callers should write the returned revised copy only after the operation succeeds.
