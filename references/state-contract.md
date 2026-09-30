# State Contract

Read this reference when creating, changing, validating, or recovering `.ipd/project_state.yaml`.

## Top-level fields

- `schema_version`: canonical contract version `2.0`; the validator can still read v0.1 `1.0` JSON state for compatibility.
- `revision`: non-negative integer incremented once per runtime transition.
- `project`: name, task types, product phase, current workflow step, current TR/DCP/Gate, and optional repository metadata.
- `claims`: assertions with `open`, `supported`, or `rejected` status and evidence references.
- `deliverables`: work products, eight-state lifecycle, dependencies, evidence, and review records.
- `gates`: TR/DCP readiness, required deliverables, and review records.
- `traceability`: typed links among claims, deliverables, and gates.

Entity IDs are globally unique lowercase identifiers. They may contain digits, `.`, `_`, and `-`. Unknown fields are rejected so misspellings cannot silently alter governance.

The JSON Schema performs structural validation. `ipdctl validate` additionally enforces global ID uniqueness, dependency existence and acyclicity, closure order, trace-link targets, gate prerequisites, and authorized-human final approval.

`.ipd/agent_runtime.yaml` is a separate runtime fact source. It records one or
zero `active_claims`, append-only command events, `last_refresh`, and
`last_verification`. A successful verification records `status`,
`state_revision`, and `input_fingerprint`; these fields do not replace the
project state or Dashboard manifest. Every `claim` event must contain a
non-empty Deliverable, Actor, timezone-aware timestamp, and non-negative
`state_revision` that does not exceed the current project revision.

## Safe persistence

The runtime writes state through a same-directory temporary file and atomically replaces the destination. A failed validation or transition returns an error and does not write a partial state. Do not hand-edit `revision` to conceal a change.

`.ipd/project_state.yaml` is source state and can be reviewed in version control. `.ipd/dashboard/`, reconciliation reports, and verification reports are generated views. The v0.1 `.ipd/project-state.json` path is discovered for read/validation compatibility but is never dual-written.

## CLI behavior

```bash
ipdctl init [TARGET] [--name NAME] [--task-type TYPE ...] [--locale en|zh-CN] [--force]
ipdctl tailor [TARGET] [--profile PATH] [--output PATH]
ipdctl context [TARGET] [--json]
ipdctl status [TARGET] [--json]
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
ipdctl validate [TARGET] [--policy PATH]
```

`status` is an alias for `context`. `init` refuses to replace existing state
unless `--force` is explicit. `tailor --output`, when supplied, must resolve to
the canonical `.ipd/tailored_process.yaml`. State-changing commands validate
before writing. `context` refuses to summarize invalid state. `verify` exits
non-zero for state, process, runtime, evidence, Dashboard, or reconciliation
errors. `repository` and repository inspection within reconciliation are
read-only and degrade to `kind: none` when neither Git nor SVN is available.

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
to match. The fingerprint covers the profile, tailored process, project state,
artifact bindings, active claim, Claim history, local evidence content,
Phase advancement history, Dashboard manifest and outputs, repository facts,
and engineering changed
paths. Advancement leaves
the workflow at `refresh`; the new Phase must be refreshed and verified before
work continues.

`tailor` preserves user-authored bindings and regenerates one managed critical
`evidence/<deliverable-id>/**` binding for every current deliverable. It never
infers ownership for real source, test, documentation, configuration, tool,
firmware, or hardware paths; add explicit rules for those paths in
`.ipd/artifact_bindings.yaml`. Unbound changes under critical roots fail
reconciliation and verification. A mapped changed path also fails when its
Deliverable has no auditable `claim` event in Agent Runtime.
An incomplete, malformed, or future-revision Claim event does not satisfy this
provenance check.

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
