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
contain an explicit rule that binds that path to the Deliverable already held
by the Agent's active claim. Do not infer ownership from a directory name. For
example, the Agent first runs
`ipdctl claim develop.runtime --actor runtime-agent`, then the project can add
this user-owned rule:

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

Only after both the claim and binding exist may the Agent modify
`src/runtime/**`. A different critical path needs its own explicit binding;
the framework never guesses that `docs/**`, `src/**`, or `tests/**` belongs to
a particular Deliverable.

Reconciliation normally runs after `close`, when the active lease has already
ended. It therefore validates each mapped changed path against the auditable
`claim` events retained in `.ipd/agent_runtime.yaml`. A binding to a known
Deliverable that has no Claim provenance fails with
`BINDING_UNCLAIMED_DELIVERABLE`; merely naming another Deliverable in the YAML
does not establish ownership. A provenance event is valid only when it records
the Deliverable, Actor, timezone-aware timestamp, and a non-negative project
state revision no newer than the current state.

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
