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
are errors; other unbound paths are warnings. Generated dashboards and VCS
metadata directories are ignored.

## Evidence references

Prefer immutable references:

- Git: full commit ID plus repository-relative path, test/check name, or review record.
- SVN: numeric revision plus repository-relative path.
- Working-tree evidence: clearly label it as uncommitted and capture the relevant validation output elsewhere; do not claim it is immutable.

Do not persist a personal absolute checkout path when a repository-relative path is sufficient. Never place remote credentials, embedded-token URLs, SSH private material, or private logs in project state.

## Mixed and unavailable repositories

Use the repository that owns the state file. If nested repositories or externals are material, record each immutable revision in approved evidence rather than guessing a single combined revision. When no VCS is available, keep `kind` as `none` and state that revision-backed verification is unavailable.
