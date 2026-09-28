# Contributing

Contributions should keep the Skill instructions, runtime behavior, schemas, policy, and examples of CLI usage consistent.

## Development

Python 3.10 or newer is supported. The test suite uses only the standard library.

```bash
python -B -m unittest discover -s tests -v
python -B -m ipdctl --help
python -B scripts/release_check.py .
```

Build wheels only into a temporary directory. Do not commit virtual environments, caches, coverage files, package metadata, `.ipd/generated/`, or built distributions.

## Contract changes

- Add tests for core transitions, evidence rules, dependency edges, or gate behavior before changing them.
- Preserve the rule that only an authorized human record can finalize TR/DCP approval.
- Treat schema changes as compatibility changes. Bump `schema_version` and document migration behavior when an existing valid state would become invalid.
- Keep `schemas/project_state.schema.json` aligned with `ipdctl.validation`; semantic checks may be stricter only when the difference is documented.
- Keep the default policy and its schema aligned with `ipdctl.policy`.
- Keep `SKILL.md` concise and route conditional detail to `references/`.

## Pull requests

Explain the affected contract and observable behavior, include focused tests, update the changelog when user-visible behavior changes, and list any migration requirement. Run the full local verification once after the final change. Do not include credentials, personal paths, private review data, or generated results.
