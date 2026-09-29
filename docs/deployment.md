# Deployment and Release Verification

## Source checkout

Use Python 3.10 or newer. The runtime depends on PyYAML 6.x for safe, human-readable workflow state and policy files.

```bash
python -m pip install -e .
python -B -m unittest discover -s tests -v
python -B -m ipdctl --help
python -B scripts/release_check.py .
```

Install this repository as a Codex Skill by placing the checkout at `$CODEX_HOME/skills/ipd-agent-workflow-skill` or the equivalent user Skill directory. Keep `SKILL.md`, `references/`, `schemas/`, `policies/`, and the Python package together.

## Clean package verification

Build outside the repository so packaging does not leave `build/`, `dist/`, or `*.egg-info/` residue in the release tree:

```bash
python -m pip wheel . --no-deps --wheel-dir <temporary-directory>
python -m pip install --force-reinstall <temporary-wheel>
ipdctl --help
```

Run the installed CLI smoke test from a directory other than this checkout. This confirms the console entry point resolves from the wheel rather than the source tree.

## GitHub release

Complete [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) before creating a tag. The source commit must be clean, CI must pass, package version and changelog must agree, and the release hygiene check must find no cache, build output, generated runtime data, credential-like files, or high-confidence secret patterns.

The canonical repository is [github.com/zju-CS-yzy/ipd-agent-workflow-skill](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill). Configure branch protection, security reporting, tag, and release settings on that repository before publishing `v0.2.0-beta` (Python package version `0.2.0b1`).

For this beta, publish source archives and an optional wheel. Do not commit built artifacts. If a release is withdrawn, mark it as withdrawn in GitHub and the changelog; do not reuse or silently move the released tag.
