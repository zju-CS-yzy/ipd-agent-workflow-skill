# Contributing

Contributions should keep the Skill instructions, runtime behavior, schemas, policy, and examples of CLI usage consistent.

## Development

Python 3.10 or newer is supported. The runtime uses PyYAML 6.x; behavior tests use `unittest`.

```bash
python -B -m unittest discover -s tests -v
python -B -m ipdctl --help
python -B scripts/release_check.py .
```

Build wheels only into a temporary directory. Do not commit virtual environments, caches, coverage files, package metadata, `.ipd/dashboard/`, reconciliation or verification reports, or built distributions.

## Contract changes

- Add tests for core transitions, evidence rules, dependency edges, or gate behavior before changing them.
- Preserve the rule that only an authorized human record can finalize TR/DCP approval.
- Treat schema changes as compatibility changes. Bump `schema_version` and document migration behavior when an existing valid state would become invalid.
- Keep `schemas/project_state.schema.json` aligned with `ipdctl.validation`; semantic checks may be stricter only when the difference is documented.
- Keep task-profile, tailored-process, and Agent Runtime schemas aligned with their runtime implementations.
- Keep the default policy and its schema aligned with `ipdctl.policy`.
- Keep `SKILL.md` concise and route conditional detail to `references/`.

## Pull requests

Explain the affected contract and observable behavior, include focused tests, update the changelog when user-visible behavior changes, and list any migration requirement. Run the full local verification once after the final change. Do not include credentials, personal paths, private review data, or generated results.

Target `main` through a pull request. The stable `governance-gate` check represents the complete release-contract suite and must pass before merge; all review conversations must be resolved. Do not force-push or delete `main`. Release tags matching `v*` are immutable after publication: correct a release with a new version instead of moving or deleting its tag.

This repository currently has one maintainer. Pull requests provide a reviewable change record, but an independent approving review cannot be required until a second trusted maintainer is available. Repository-owner bypass, when needed, is limited to pull requests so emergency changes still retain a PR and CI audit trail. Once a second maintainer is appointed, the ruleset should require one approval and dismiss stale approvals after reviewable changes.
