# Workflow and Gate Rules

Read this reference when deciding how to tailor an IPD flow, close evidence, or prepare a TR/DCP gate.

## Two independent progress dimensions

The project phase describes product maturity: `concept`, `plan`, `develop`, `qualify`, `launch`, or `lifecycle`.

The core workflow step describes the current unit of work. The runtime permits
only one active claim and enforces this serialized reviewable iteration:

`claim -> work -> close -> review -> human approve/reject -> refresh -> verify`

`context` establishes the starting facts; the human-decision commands execute
while the machine workflow step remains `review`:

1. `context` — establish scope, authority, state, repository facts, and applicable policy.
2. `claim` — define a falsifiable result and the evidence that would support it.
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
actor cannot be taken over.

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

Tailoring may add deliverables or reviewers, merge non-final reviews, and tighten evidence requirements. It must not remove traceability, accept work without evidence, close work with unmet dependencies, or delegate final gate approval to an agent. Re-tailoring regenerates only framework-managed evidence rules; user-authored source and test bindings remain intact.

Record a tailored choice in project documentation or policy evidence so that another reviewer can understand why the default flow changed.

## Language contract

Commands, options, paths, identifiers, YAML/JSON keys, statuses, relations,
event names, and report codes remain English. Framework-owned CLI and Dashboard
presentation follows `.ipd/task_profile.yaml` at `presentation.locale`
(`en` or `zh-CN`); user-authored names, evidence, paths, and descriptions are
preserved verbatim. A locale-only change requires `refresh` and `verify`, not
re-tailoring.
