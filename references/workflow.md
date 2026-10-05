# Workflow and Gate Rules

Read this reference when deciding how to tailor an IPD flow, close evidence, or prepare a TR/DCP gate.

## Two independent progress dimensions

The project phase describes product maturity: `concept`, `plan`, `develop`, `qualify`, `launch`, or `lifecycle`.

The core workflow step describes the current unit of work. The runtime permits
only one active claim and enforces this serialized reviewable iteration:

`claim -> work -> close -> review -> human approve/reject -> refresh -> verify`

`context` establishes the starting facts; the human-decision commands execute
while the machine workflow step remains `review`:

1. `context` — establish scope, authority, state, repository facts, binding eligibility, and applicable policy.
2. `claim` — define a falsifiable result and evidence, then atomically record the current binding window before work begins.
3. `work` — produce or change the deliverable while maintaining dependencies and links.
4. `close` — submit evidence as `ready_for_review`.
5. `review` — record review facts; an Agent may recommend but not make a final decision.
6. human `approve` or `reject` — record the explicitly authorized decision and move to `refresh`.
7. `refresh` — regenerate derived dashboards and matrices and move to `verify`.
8. `verify` — independently check the result and reconcile the state.

After `verify`, a new claim may start only if the latest verification passed for
the current state revision and its complete input fingerprint is still current.
`close --status blocked` is the explicit aborted-work exception: it goes from
`work` to `refresh`, but still requires `refresh` and `verify` before another
claim. A product Phase changes only when project governance calls for it;
completing one Agent loop does not imply a Phase change.

If an `in_progress` deliverable has no active lease, `context --json` lists it
under `recoverable_claims`; recover it explicitly with
`claim <deliverable> --recover`. Expired leases are removed with an auditable
`claim_expired` event and may be reclaimed. An unexpired claim owned by another
actor cannot be taken over. A windowless v0.3.1 Claim requires an exact
authorized-human baseline adoption before its first recovery; that recovery
persists the migration window for every later lease recovery in the same
unfinished iteration.

Claim preflight consumes the same eligibility object shown by `context` and the
Dashboard. Missing or invalid bindings, conflicting critical owners, and
pre-existing changes without an accepted baseline remove affected work from
`available_tasks`; a failed preflight writes neither state nor runtime.

## Deliverables and evidence

A deliverable moves through `planned`, `in_progress`, `ready_for_review`,
`in_review`, `accepted`, `rejected`, `blocked`, and `superseded`. Rework may
move `rejected`, `blocked`, or review states back to `in_progress`. Acceptance
requires:

- at least one durable evidence reference;
- a latest authorized human decision of `approve`, with earlier decisions
  preserved as immutable review history;
- every `depends_on` deliverable in `accepted` state;
- no dependency cycle; and
- state validation after the transition.

`superseded` is terminal and requires a replacement deliverable plus an
explicit `supersedes` trace link.

Good evidence is reproducible and specific: a repository-relative document, test record, immutable commit/revision, approved review record, or stable external record identifier. A statement that work was checked is not itself evidence.

`tailor` maintains `.ipd/artifact_bindings.yaml`: it preserves user-authored
rules and regenerates one framework-managed, critical
`evidence/<deliverable-id>/**` rule for every tailored deliverable. These rules
cover durable evidence only. Ownership of real engineering paths is never
inferred; add explicit user rules such as:

```yaml
bindings:
  - id: runtime-source
    glob: src/runtime/**
    deliverable: develop.runtime
    critical: true
  - id: runtime-tests
    glob: tests/runtime/**
    deliverable: develop.runtime
    critical: true
```

Every actually changed critical path must resolve to exactly one Deliverable.
An omitted Binding `role` or explicit `role: owner` maps exactly one
`deliverable` and is the only role that authorizes a Claim. A
`role: shared_evidence` rule must use a `deliverables` list and
`critical: false`; it records evidence shared by several Deliverables but does
not authorize their Claims or satisfy a critical path's required Owner.
For a reviewed dirty working tree that predates v0.3.2, use
`adopt-baseline --preview` and then an explicitly authorized-human
`adopt-baseline` decision instead of fabricating a historical Claim. Each
successful verification stores the exact accepted artifact baseline for the
next serialized iteration.

If the project also contains an expired, windowless v0.3.1 active Claim, first
record that reviewed adoption, then run `claim <deliverable> --recover`. The
recovery fails if the adopted snapshot no longer exactly matches the current
bindings, repository revision, and governed path hashes.

Changed source or test paths under configured critical roots that have no
explicit binding make reconciliation, and therefore verification, fail.

## TR and DCP gates

- A Technical Review (`TR`) evaluates technical readiness or quality.
- A Decision Checkpoint (`DCP`) records a governed business or program decision.
- Each Phase evaluates its canonical TR before its canonical DCP. Any generic
  Gate follows both controls in deterministic ID order.
- A gate moves from `planned` to `ready` only after all required deliverables are accepted.
- Reviews may be prepared by humans or agents, but final `approved` state requires an explicitly authorized human approval record.
- The latest authorized human decision controls the current Gate outcome.
  A later approval may resolve an earlier rejection after rework, but the
  earlier rejection remains in review history.

The agent may assemble evidence, identify missing reviewers, record a supplied decision, and validate readiness. It must stop short of inventing the human decision or the reviewer's authorization.

State contains only canonical `gate.*` governance facts. Process-level
`tr.*` and `dcp.*` checkpoint IDs are accepted by the CLI as aliases and are
resolved to their linked Gate. `ipdctl advance-phase` advances one product
Phase only when every canonical Gate in the current Phase is approved, the
latest verification passed for the current state revision, and the stored
verification-input fingerprint still matches. Advancement moves exactly one
Phase and leaves the workflow at `refresh`; run `refresh` and `verify` before
claiming or reviewing more work.

Gate decisions derive the current control from tailored process and Gate
status facts. A stale or hand-edited `project.current_gate` pointer fails
closed and must be repaired through `tailor`, followed by `refresh` and
`verify`. The complete Phase/TR/DCP/Gate pointer bundle is also checked against
ordered `advance_phase` events; coordinated pointer edits cannot manufacture a
valid phase transition.

The final `lifecycle` Phase has no successor. When every Gate in that Phase is
approved and `verify` passes, the runtime appends one `lifecycle_complete`
event with the Phase and state revision. Re-running verification does not
duplicate the event.

## Tailoring

Tailoring compiles four additive layers in one fixed order:

`core -> task_type -> capability -> project`

`task_profile.yaml` selects task types and optional `capability_patterns`. The
built-in `sourced_component_integration` pack is deliberately generic and adds
candidate validation, selection decision, and integration baseline stages. It
does not contain vendor, robot, sensor, project path, or Owner data.

The canonical project layer is `.ipd/process_extensions.yaml`. It may add:

- Activities and review-required Deliverables;
- project-owned generic Gates that follow their phase's canonical TR and DCP;
- typed `depends_on`, `supports`, `verifies`, or `supersedes` relations;
- independent evidence-required criteria for a named `tr.<phase>` or
  `dcp.<phase>` checkpoint; and
- explicit `replace` or `split` migration mappings with
  `preserve_history: true`; and
- one-to-one `gate_migrations` and exact same-ID `dependency_corrections`; and
- explicit refinement requirements and the applied refinement lineage.

It cannot delete or override an earlier-layer entity. Duplicate IDs, unknown
references, cycles, and an earlier-Phase Deliverable depending on a
later-Phase Deliverable fail validation. Compiled Phase, Activity,
Deliverable, TR, DCP, and Gate nodes record `provenance.layer` and
`provenance.source_id`; phase-derived `maturity` provides a stable lifecycle
projection: `concept=defined`, `plan=selected`, `develop=integrated`,
`qualify=verified`, `launch=released`, and `lifecycle=monitored`. TR and DCP
retain separate criteria rather than sharing one generic Gate checklist.

Use `ipdctl tailor --preview` before changing an existing process. Preview is
zero-write and `--json` returns `added`, `removed`, `changed`, `migrations`,
and `ambiguous`. The same fixed keys expose `state.traceability` additions,
removals, and redirects; a Claim link that cannot be preserved or explicitly
migrated appears as an `ambiguous` blocker. Any actual re-tailor fails while a Claim is active. Removing a
historical non-superseded Deliverable requires an explicit mapping and
`--apply-migrations`; the first effective migration additionally requires an
authorized human Actor and reason. The old node remains in state as
`superseded`, preserving evidence and reviews, while replacement nodes remain
`planned` without copied evidence or acceptance. A migration must never be
inferred from similar names or content.

An ordinary re-tailor cannot reinterpret an existing Deliverable with governed
status, evidence, or reviews under the same ID. Model the replacement with a
new ID and the explicit migration contract. Changes targeting a Phase with an
approved Gate or a Phase earlier than the current Phase—including TR/DCP
criteria—also fail closed before any authority file is written; inspect them
through the zero-write preview. A schema `1.0` process may receive only the
deterministic core provenance, maturity, and canonical readiness-criteria
enrichment needed for schema `2.0`.

A legacy generic Gate requires one unambiguous `gate_migrations` mapping to a
candidate canonical or project Gate. The first effective redirect uses the
same authorized-human migration command and preserves Gate and Claim-link
history. A historical Deliverable may receive a same-ID dependency repair only
through `dependency_corrections` whose exact `before` set matches state and
whose `after` set matches the candidate process. `preserve_history` and
`require_reapproval` must both be true. The correction retains evidence and
reviews, blocks the Deliverable for rework, and invalidates affected unapproved
Gates; an approved affected Gate makes the change fail closed.

## Progressive refinement

Use progressive refinement when accepted project evidence determines a
same-Phase module, function, or work-package structure that could not be known
from the reusable template. The project extension declares the root and
trigger; it must not embed a guessed decomposition in a task-type policy.

First inspect `context --json`. When the root is `due`, prepare a separate
schema `1.0` plan with `mode: expand`, the exact current
`base_process_fingerprint`, an auditable reason and evidence basis, Activities,
review-required child Deliverables, and explicit relations. Run
`refine --preview --json` and review its process diff, Gate impact, and Binding
impact. Preview must not modify any authority file or runtime event.

Only an authorized human may apply the reviewed plan. Application is blocked
by any active Claim, a pending trigger, a stale base fingerprint, or a root
outside the current Phase. The parent becomes `abstract` but retains all prior
evidence and reviews. Children start `planned` with empty evidence and review
history. A child can itself declare a later refinement trigger, allowing
multiple controlled rounds; each plan ID is append-only and replay-safe.

Treat `refines` as structural ancestry only. It must be same-Phase and acyclic,
and it never satisfies or creates an execution dependency. Use `depends_on`
explicitly for execution order. Gate readiness uses concrete leaf closure. If
that closure changes, preserve old Gate evidence but invalidate approval and
require a current review epoch. Do not copy or split an Owner Binding: each new
concrete child that requires ownership remains unclaimable until a human has
provided an explicit user-authored Owner rule. Placeholder and abstract nodes
are structural and do not require an Owner until concrete work is materialized.

Tailoring may add deliverables or reviewers, merge non-final reviews, and
tighten evidence requirements. It must not remove traceability, accept work
without evidence, close work with unmet dependencies, or delegate final gate
approval to an agent. Re-tailoring regenerates only framework-managed evidence
rules; user-authored source and test bindings remain intact.

Newly compiled process files use schema `2.0`. A schema `1.0` process remains
readable only while it semantically matches a profile without enabled
capabilities and an empty project extension. Preview and re-tailor before
enabling either layer.

Record a tailored choice in project documentation or policy evidence so that another reviewer can understand why the default flow changed.

## Language contract

Commands, options, paths, identifiers, YAML/JSON keys, statuses, relations,
event names, and report codes remain English. Framework-owned CLI and Dashboard
presentation follows `.ipd/task_profile.yaml` at `presentation.locale`
(`en` or `zh-CN`); user-authored names, evidence, paths, and descriptions are
preserved verbatim. A locale-only change requires `refresh` and `verify`, not
re-tailoring.
