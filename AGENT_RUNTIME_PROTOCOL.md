# Agent Runtime Protocol

The runtime serializes every reviewable deliverable iteration through one
auditable loop:

`context -> claim -> work -> close -> review -> human approve/reject -> refresh -> verify`

Only one claim may be active. The next claim cannot begin until the previous
iteration has reached `verify` and its latest passed verification still matches
the current state revision and verification-input fingerprint.

## Command contract

1. `ipdctl context` reads the current Phase, TR, DCP, Gate, available work,
   blockers, active claims, and repository facts.
2. `ipdctl claim <deliverable>` checks the current Phase and predecessor
   closure, records an Agent lease, and moves eligible work to `in_progress`.
   Its append-only Claim event records the Deliverable, Actor, UTC timestamp,
   and project state revision; incomplete or future-revision events are not
   valid provenance.
   An unexpired claim owned by another actor cannot be taken over. Use
   `claim <deliverable> --recover` only when `context` reports an orphaned
   `in_progress` deliverable; an expired lease is recovered auditably.
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

`close --status blocked` is an explicit aborted-work path: it records the
blocker and moves directly to `refresh`, but it still cannot be followed by a
new claim until `refresh` and `verify` complete.

## State ownership

- `.ipd/task_profile.yaml` describes the project and tailoring inputs.
- `.ipd/tailored_process.yaml` describes what the project is required to do.
- `.ipd/project_state.yaml` records completed work, reviews, and gate facts.
- `.ipd/agent_runtime.yaml` records temporary Agent claims and runtime events.
- `.ipd/artifact_bindings.yaml` maps repository paths to deliverables.
- `.ipd/dashboard/` is generated output and must not be edited as a fact source.

`tailor` preserves user-authored artifact rules and regenerates a framework-
managed `evidence/<deliverable-id>/**` rule for every current deliverable. It
does not guess which deliverable owns real source, test, documentation,
configuration, tool, firmware, or hardware paths; those require explicit
user-authored bindings. Reconciliation runs after the lease may have closed, so
it verifies changed-path ownership against retained `claim` events. A binding
without Claim provenance fails verification. Claim provenance is valid only
when its Deliverable, Actor, UTC timestamp, and non-future state revision pass
the runtime contract.

## Authority boundaries

- A claim is a local working-tree lease, not a distributed lock across clones.
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
