# Repository Integration

Read this reference when repository revisions, dirty state, or VCS-specific evidence affect an IPD decision.

## Detection

`ipdctl repository PATH` checks for an enclosing Git worktree first and then an SVN working copy. It reports the VCS kind, root, revision when available, and dirty state. An unborn Git branch has no revision and is still a valid Git repository.

Detection is read-only. It does not add files, commit, update, switch branches, tag, push, lock, or modify SVN properties.

## Evidence references

Prefer immutable references:

- Git: full commit ID plus repository-relative path, test/check name, or review record.
- SVN: numeric revision plus repository-relative path.
- Working-tree evidence: clearly label it as uncommitted and capture the relevant validation output elsewhere; do not claim it is immutable.

Do not persist a personal absolute checkout path when a repository-relative path is sufficient. Never place remote credentials, embedded-token URLs, SSH private material, or private logs in project state.

## Mixed and unavailable repositories

Use the repository that owns the state file. If nested repositories or externals are material, record each immutable revision in approved evidence rather than guessing a single combined revision. When no VCS is available, keep `kind` as `none` and state that revision-backed verification is unavailable.
