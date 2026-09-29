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

## Safe persistence

The runtime writes state through a same-directory temporary file and atomically replaces the destination. A failed validation or transition returns an error and does not write a partial state. Do not hand-edit `revision` to conceal a change.

`.ipd/project_state.yaml` is source state and can be reviewed in version control. `.ipd/dashboard/`, reconciliation reports, and verification reports are generated views. The v0.1 `.ipd/project-state.json` path is discovered for read/validation compatibility but is never dual-written.

## CLI behavior

```bash
ipdctl init [DIRECTORY] [--name NAME] [--task-type TYPE]
ipdctl tailor [DIRECTORY]
ipdctl context [DIRECTORY] [--json]
ipdctl claim DELIVERABLE [--project-root DIRECTORY]
ipdctl close DELIVERABLE --evidence PATH [--project-root DIRECTORY]
ipdctl review DELIVERABLE --reviewer NAME [--project-root DIRECTORY]
ipdctl approve|reject DELIVERABLE --reviewer NAME --actor-type human --authorized --evidence PATH
ipdctl refresh [DIRECTORY]
ipdctl verify [DIRECTORY]
ipdctl repository [PATH] [--json]
```

`init` refuses to replace existing state unless `--force` is explicit. State-changing commands validate before writing. `context` refuses to summarize invalid state. `verify` exits non-zero for state, process, evidence, dashboard, or reconciliation errors. `repository` is read-only and degrades to `kind: none` when neither Git nor SVN is available.

The Python engine exposes validated transitions for integrations. Callers should write the returned revised copy only after the operation succeeds.
