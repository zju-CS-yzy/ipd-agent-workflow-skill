# Agent Runtime Protocol

The runtime serializes every reviewable deliverable iteration through one
auditable loop:

`context -> claim -> work -> close -> review -> human approve/reject -> refresh -> verify`

Only one claim may be active. The next claim cannot begin until the previous
iteration has reached `verify` and its latest passed verification still matches
the current state revision and verification-input fingerprint.

Every mutating `ipdctl` command serializes its complete read, preflight,
compute, and write cycle with a project-local recovery transaction. A second
concurrent mutation fails explicitly and should be retried after the active
command finishes. If a process terminates during a multi-file write, the next
command restores the pre-command bundle; a process loss after commit retirement
does not roll the committed facts back.

## Process compilation and migration

`ipdctl tailor` deterministically compiles
`core -> task_type -> capability -> project`. `task_profile.yaml` selects
`capability_patterns`; the final project layer is the canonical
`.ipd/process_extensions.yaml`. All layers are additive.
The project layer may add Activities, review-required Deliverables, typed
relations, independent TR/DCP criteria, and explicit migration mappings, but
cannot delete or override an earlier-layer entity. Compiled entities expose
their `provenance` layer/source and phase-derived `maturity`. A Deliverable
dependency must be acyclic and cannot point from an earlier Phase to a later
Phase.

`tailor --preview` performs no writes. With `--json`, it returns only the fixed
diff keys `added`, `removed`, `changed`, `migrations`, and `ambiguous`. Any
actual re-tailor fails while a Claim is active. Removing a historical,
non-superseded Deliverable requires an explicit `replace` or `split` mapping
plus `--apply-migrations`. On the first effective migration, an authorized
human Actor and reason are required. The old state-only node becomes
`superseded`, retains its evidence and review history, and links to every
replacement; replacement nodes remain `planned` with empty evidence and review
history. The runtime appends one `process_migration` event and does not repeat
it on an idempotent re-run. An absent, ambiguous, or invalid mapping fails
closed; the Agent must not invent one. Ordinary re-tailoring must not change
the semantic fields of a Deliverable with governed lifecycle history under the
same ID; use a new ID and the explicit migration path. Any process change that
targets a Phase with an approved Gate or an already closed Phase, including
TR/DCP criteria, also fails before writes. The only upgrade exception is
deterministic schema `1.0` enrichment with core provenance, maturity, and
canonical readiness criteria.

## Progressive refinement

Progressive refinement evolves the project layer after reviewed evidence has
made a declared decomposition requirement actionable. The canonical
`.ipd/process_extensions.yaml` declares each root, initial definition state,
trigger, and `all_children_accepted` completion policy. `ipdctl context --json`
reports the current `process_fingerprint` and `pending`, `due`, or `resolved`
refinement status.

`ipdctl refine --plan PLAN --preview --json` is deterministic and performs no
writes. A plan may only use `mode: expand`; it identifies its exact base
process, its evidence basis, Activities, child Deliverables (including explicit
placeholder intermediates for a later refinement round), and typed relations.
Only Deliverables may be refinement requirement roots. Applying a new plan is
forbidden while a Claim is active, before its trigger is satisfied, after its
base fingerprint becomes stale, or after the project has left the root's
Phase. The first application requires an
identified authorized human and reason and appends exactly one
`process_refinement_applied` event. Replaying the same ID, digest, and base is
a no-op; reusing an ID for different content fails closed. The applied process
record and runtime event must agree on the SHA-256 plan/base/result values,
root, children, and exact invalidated Gate set; field-level tampering makes the
project inconsistent before replay or verification.

Trigger subjects must be reachable before the root Gate. A Deliverable
`accepted` condition cannot point to a later Phase, and a Gate `approved`
condition must point to an earlier Phase. Each placeholder child must declare
its own executable refinement requirement and trigger; it cannot trigger
itself or use a Deliverable that depends on it. A nested refinement root stays
a leaf until a later, separately authorized Plan expands it. Applied and
currently due refinement lineage cannot be changed by ordinary `tailor` in
this Beta; use another reviewed `refine` plan. Before preview or apply,
`refine` proves the current profile and extension compile to the governed
process. Replay also requires the matching Agent runtime event.

The parent remains in state as an abstract aggregation node with its prior
evidence and review history. New children start at `planned` with no inherited
acceptance, evidence, or reviews. `refines` is a structural relation and never
enters dependency topology; only `depends_on` controls work order. A Gate uses
the concrete leaf closure of every abstract requirement. A changed closure
preserves prior review evidence but invalidates approval, increments
`review_epoch`, and requires a new authorized-human decision. New concrete
children require a user-authored artifact Owner before Claim. Placeholder and
abstract nodes are structural and require no Owner until a later Plan produces
concrete work; no parent or managed evidence rule is reassigned.
Downstream work also remains unclaimable with
`REFINEMENT_DEPENDENCY_REQUIRED` while a transitive prerequisite has pending or
due refinement. A Plan cannot reuse a historical Deliverable ID or rewrite
dependencies of an existing Deliverable with governed lifecycle history.

## Command contract

1. `ipdctl context` reads the current Phase, TR, DCP, Gate, available work,
   blockers, active claims, progressive-refinement status and process
   fingerprint, repository facts, and binding eligibility. A
   binding-blocked Deliverable is not available work even when its lifecycle
   dependencies are otherwise ready.
2. `ipdctl claim <deliverable>` checks the current Phase and predecessor
   closure, records an Agent lease, and moves eligible work to `in_progress`.
   Its append-only Claim event records the Deliverable, Actor, UTC timestamp,
   project state revision, and an exact binding window. Incomplete,
   future-revision, legacy windowless, or stale-window events are not valid
   provenance for new path changes.
   An unexpired claim owned by another actor cannot be taken over. Use
   `claim <deliverable> --recover` only when `context` reports an orphaned
   `in_progress` deliverable; an expired lease is recovered auditably.
   An expired v0.3.1 Claim without a binding window remains fail-closed until
   an authorized human adopts the exact current migration baseline. Its first
   recovery derives one immutable window from that adoption; later lease
   recovery reuses the same window rather than reopening it on the dirty tree.
3. **work** is the authorized engineering activity performed outside the
   controller. The Agent must preserve the deliverable ID and produce durable
   evidence.
4. `ipdctl close <deliverable> --evidence <path>` submits the work as
   `ready_for_review`; it never accepts the deliverable.
5. `ipdctl review <subject>` starts review for a Deliverable, TR, DCP, or Gate.
   `tr.<phase>` and `dcp.<phase>` are resolved to their canonical
   `gate.tr.<phase>` and `gate.dcp.<phase>` state facts. Agent reviews may
   recommend a decision, but cannot create final approval.
6. `ipdctl approve <subject>` or `ipdctl reject <subject>` records an explicitly
   authorized human decision. An Agent identity is rejected for either final
   decision. All review records remain auditable; the latest authorized human
   decision controls the current outcome.
7. `ipdctl refresh` rebuilds dashboards, graphs, and matrices strictly from
   process and state facts, then moves the workflow to `verify`.
8. `ipdctl verify` validates schemas, dependencies, review authority,
   traceability, evidence paths, repository reconciliation, and
   generated-output freshness. It records the current state revision and a
   fingerprint of all verification inputs. Any later input change invalidates
   that verification for claim, Gate review, and phase advancement.
9. `ipdctl advance-phase` is a separate product-governance action. It requires
   every canonical Gate in the current Phase to be approved and the current
   revision plus fingerprint to match the latest passed verification. It
   advances exactly one Phase and leaves the workflow at `refresh`; run
   `refresh` and `verify` again before continuing governed work. Each successful
   transition appends `from_phase`, `to_phase`, timestamp, and state revision;
   current Phase must match that ordered history.

`ipdctl refine` is a governed process-evolution command between `context` and
the next Claim, not a substitute for the Deliverable execution loop. After an
application, run `refresh` and `verify` before relying on the Dashboard or
claiming any new child.

`close --status blocked` is an explicit aborted-work path: it records the
blocker and moves directly to `refresh`, but it still cannot be followed by a
new claim until `refresh` and `verify` complete.

## State ownership

- `.ipd/task_profile.yaml` describes the project and tailoring inputs.
- `.ipd/process_extensions.yaml` contains additive project-owned process facts and explicit migration mappings.
- `.ipd/tailored_process.yaml` describes what the project is required to do.
- `.ipd/project_state.yaml` records completed work, reviews, and gate facts.
- `.ipd/agent_runtime.yaml` records temporary Agent claims and runtime events.
- `.ipd/artifact_bindings.yaml` maps repository paths to deliverables.
- `.ipd/dashboard/` is generated output and must not be edited as a fact source.

`tailor` preserves user-authored artifact rules and regenerates a framework-
managed `evidence/<deliverable-id>/**` rule for every current deliverable. It
does not guess which deliverable owns real source, test, documentation,
configuration, tool, firmware, or hardware paths; those require explicit
user-authored bindings. Every actually changed critical path must resolve to
one known Deliverable owner. Reconciliation runs after the lease may have
closed, so it verifies changed-path ownership against the current iteration's
retained Claim binding window, not any Claim ever recorded for that
Deliverable. A binding without current Claim provenance fails verification.

A missing Binding `role` retains the existing Owner behavior. Explicit
`role: owner` also maps exactly one `deliverable` and is the only role that can
authorize its Claim. `role: shared_evidence` must be non-critical and may map
one path to several `deliverables`; it records supporting evidence only. It
cannot authorize a Claim or substitute for the Owner of a critical path.

An existing project may contain reviewed work that predates the runtime. In
that migration case, `ipdctl adopt-baseline` can record the exact changed-path
snapshot as an append-only `artifact_baseline_adopted` event. The operation
requires an explicitly authorized human Actor and reason, is idempotent for an
identical snapshot, creates no Claim, changes no Deliverable status, and never
mutates Git/SVN. A successful `verify` stores the exact verified artifact
baseline for the next iteration, so an intentionally dirty working tree does
not require a fabricated commit or historical Claim.

## Authority boundaries

- A claim is a local working-tree lease, not a distributed lock across clones.
- Baseline adoption is a human migration decision, not Agent self-approval,
  VCS history, or enterprise identity proof.
- `accepted` requires evidence and an authorized human approval review.
- A rejected deliverable remains auditable and may be reclaimed into
  `in_progress` for rework.
- Final TR/DCP approval requires the latest authorized human decision to be
  `approve`. Earlier rejections remain in history and must never be erased.
- Repository commands are read-only. The framework never commits, pushes,
  pulls, updates, tags, or rewrites history.

## Completion and language

When verification passes in the final `lifecycle` Phase and every Gate in that
Phase is approved, the runtime appends `lifecycle_complete` exactly once. This
is the terminal completion record; `advance-phase` cannot move beyond it.

Commands, options, paths, IDs, YAML/JSON keys, statuses, relations, event names,
and report codes are English machine contracts. User-facing CLI and generated
Dashboard text use `.ipd/task_profile.yaml` at `presentation.locale`, with
supported values `en` and `zh-CN`. A missing field defaults to `en`; changing
the locale changes presentation only and requires `refresh` followed by
`verify`.
