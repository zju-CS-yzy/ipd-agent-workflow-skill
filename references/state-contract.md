# State Contract

Read this reference when creating, changing, validating, or recovering `.ipd/project-state.json`.

## Top-level fields

- `schema_version`: contract version; this release accepts `1.0`.
- `revision`: non-negative integer incremented once per runtime transition.
- `project`: project name, product phase, current agent workflow step, and optional repository metadata.
- `claims`: assertions with `open`, `supported`, or `rejected` status and evidence references.
- `deliverables`: work products, statuses, dependencies, and evidence references.
- `gates`: TR/DCP readiness, required deliverables, and review records.
- `traceability`: typed links among claims, deliverables, and gates.

Entity IDs are globally unique lowercase identifiers. They may contain digits, `.`, `_`, and `-`. Unknown fields are rejected so misspellings cannot silently alter governance.

The JSON Schema performs structural validation. `ipdctl validate` additionally enforces global ID uniqueness, dependency existence and acyclicity, closure order, trace-link targets, gate prerequisites, and authorized-human final approval.

## Safe persistence

The runtime writes state through a same-directory temporary file and atomically replaces the destination. A failed validation or transition returns an error and does not write a partial state. Do not hand-edit `revision` to conceal a change.

`.ipd/project-state.json` is source state and can be reviewed in version control. `.ipd/generated/` is disposable output and must not be committed.

## CLI behavior

```bash
ipdctl init [DIRECTORY_OR_JSON] [--name NAME]
ipdctl validate [DIRECTORY_OR_JSON] [--policy POLICY]
ipdctl status [DIRECTORY_OR_JSON] [--json]
ipdctl repository [PATH] [--json]
```

`init` refuses to replace existing state unless `--force` is explicit. `validate` exits non-zero and reports stable JSON-style paths for every detected issue. `status` refuses to summarize invalid state. `repository` is read-only and degrades to `kind: none` when neither Git nor SVN is available.

The Python engine exposes validated transitions for integrations. Callers should write the returned revised copy only after the operation succeeds.
