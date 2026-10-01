# Repository Integration

Read this reference when repository revisions, dirty state, or VCS-specific evidence affect an IPD decision.

## Detection

`ipdctl repository PATH` checks for an enclosing Git worktree first and then an SVN working copy. It reports kind, root, branch where applicable, revision, dirty state, and a credential-sanitized remote. An unborn Git branch has no revision and is still a valid Git repository.

Detection and reconciliation are local and read-only. They never fetch, pull,
update, add, commit, switch branches, tag, push, lock, or modify SVN
properties. Optional hook templates only delegate to `ipdctl verify`; the
framework does not install them automatically.

`ipdctl reconcile` maps locally changed paths through
`.ipd/artifact_bindings.yaml`. Unbound paths under configured critical roots
are errors; other unbound paths are warnings. The complete `.ipd/**` tree is
ignored by repository reconciliation because framework state and generated
views are validated by their own schema, transition, freshness, and audit
checks. VCS metadata directories are also ignored.

## Binding project paths before work

Before a real Agent changes a path under `critical_roots`, the project must
contain an explicit rule that binds that path to the Deliverable the Agent will
claim. Configure and validate ownership before Claim; do not infer ownership
from a directory name. For example:

```yaml
critical_roots:
  - src/**
  - tests/**
bindings:
  - id: runtime-owner
    glob: src/runtime/**
    deliverable: develop.runtime
    critical: true
    review_required: true
```

Only after the binding validates and the matching Claim exists may the Agent modify
`src/runtime/**`. A different critical path needs its own explicit binding;
the framework never guesses that `docs/**`, `src/**`, or `tests/**` belongs to
a particular Deliverable.

Reconciliation normally runs after `close`, when the active lease has already
ended. It therefore validates each mapped changed path against the current
iteration's auditable Claim binding window retained in
`.ipd/agent_runtime.yaml`. A binding to a known Deliverable that has no current
Claim provenance fails with `BINDING_UNCLAIMED_DELIVERABLE`; merely naming a
Deliverable in YAML or having claimed it in an older iteration does not
establish ownership. Actual overlap between critical rules is allowed only
when all matching rules resolve to the same owner.

## Adopting an existing working-tree baseline

Do not create a fake Claim for files that were already modified before the IPD
runtime was installed. First add explicit single-owner bindings and inspect the
read-only preview:

```bash
ipdctl adopt-baseline . --preview --json
```

After a human verifies the files and ownership, record the migration decision:

```bash
ipdctl adopt-baseline . --actor HUMAN --actor-type human --authorized \
  --reason "Adopt the reviewed pre-v0.3.2 working tree"
```

The authoritative record is an append-only `artifact_baseline_adopted` Agent
Runtime event containing exact path hashes and repository identity. The same
snapshot is idempotent. A changed path, changed Binding digest, or changed
repository identity is not covered by an older adoption. This command creates
no Claim, does not change Deliverable state, and never stages, commits, updates,
or otherwise writes Git/SVN.

`ipdctl tailor` manages one deterministic rule per current Deliverable for
`evidence/<deliverable-id>/**`. Re-tailoring updates those framework-managed
evidence rules and removes only framework-managed rules for Deliverables that
no longer exist. Hand-authored binding rules are preserved.

## Evidence references

Prefer immutable references:

- Git: full commit ID plus repository-relative path, test/check name, or review record.
- SVN: numeric revision plus repository-relative path.
- Working-tree evidence: clearly label it as uncommitted and capture the relevant validation output elsewhere; do not claim it is immutable.

Do not persist a personal absolute checkout path when a repository-relative path is sufficient. Never place remote credentials, embedded-token URLs, SSH private material, or private logs in project state.

## Mixed and unavailable repositories

Use the repository that owns the state file. If nested repositories or externals are material, record each immutable revision in approved evidence rather than guessing a single combined revision. When no VCS is available, keep `kind` as `none` and state that revision-backed verification is unavailable.
