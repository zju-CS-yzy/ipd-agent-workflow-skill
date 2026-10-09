# Deployment and Release Verification

[English](deployment.md) | [简体中文](deployment.zh-CN.md)

## Source checkout

Use Python 3.10 or newer. The runtime depends on PyYAML 6.x for safe, human-readable workflow state and policy files.

```bash
python -m pip install -e .
python -B -m unittest discover -s tests -v
python -B -m ipdctl --help
python -B scripts/release_check.py .
```

Install this repository as a Codex Skill by placing the checkout at `$CODEX_HOME/skills/ipd-agent-workflow-skill` or the equivalent user Skill directory. Keep `SKILL.md`, `references/`, `schemas/`, `policies/`, and the Python package together.

This repository publishes one bilingual package, not separate English and
Chinese distributions. Select presentation language per project with
`ipdctl init ... --locale en` or `--locale zh-CN`.

## Clean package verification

Choose the distribution for the surface you want to install:

| Distribution | Installed surface |
| --- | --- |
| Skill ZIP or source checkout | Complete Skill instructions, bilingual guidance, and Python runtime; place the tree in the Skill directory |
| Wheel | Python CLI, message catalog, policies, schemas, and runtime templates; install with pip |
| Sdist | Sources for building and installing the Python CLI and its runtime resources with pip |

Build outside the repository so packaging does not leave `build/`, `dist/`, or `*.egg-info/` residue in the release tree:

```bash
python -m pip wheel . --no-deps --wheel-dir <temporary-directory>
python -m pip install --force-reinstall <temporary-wheel>
ipdctl --help
```

Run English and Simplified Chinese lifecycle smoke tests from a directory other
than this checkout. This confirms the console entry point and bundled
`ipdctl/messages.yaml` resolve from the wheel rather than the source tree.

The clean-package check must confirm that wheel and sdist include the same
runtime code and message catalog. Locale-specific source archives or wheels are
not release artifacts.

## GitHub release

Complete [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) before creating a tag. The source commit must be clean, CI must pass, package version and changelog must agree, and the release hygiene check must find no cache, build output, generated runtime data, credential-like files, or high-confidence secret patterns.

The canonical repository is [github.com/zju-CS-yzy/ipd-agent-workflow-skill](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill). Configure branch protection, security reporting, tag, and release settings on that repository before publishing `v0.5.1-beta` (Python package version `0.5.1b1`).

The direct previous-version gate must build a governed project with the real
`v0.5.0-beta` Tag and open it under v0.5.1 without reinitializing. It must prove
that a legacy mid-review state fails closed until an authorized human restores
the exact review subject, every other subject remains blocked without writes,
`render-dashboard` preserves state and Runtime bytes, active-review `refresh`
is a zero-write failure, and one legal refresh advances exactly one revision.
It must also upgrade Dashboard manifest `2.1` to `2.2`, generate the 16-file
inventory, detect governance version/Gate/content drift, preserve Profile and
Process bytes, and finish with passing `validate --json` plus `verify`.

Retain the v0.4.1-to-v0.5 capability gate as a longer-horizon compatibility
regression. It must continue to prove that capabilities are never enabled
implicitly, preview is zero-write, and explicit capability selection adds only
the expected nodes and provenance.

Retain the v0.3.2-to-v0.4 process-schema upgrade gate as a longer-horizon
compatibility regression. It must still preserve accepted state, evidence, and
review history; add only planned capability work; expose provenance; and remain
fail-closed until a changed Binding baseline is explicitly adopted by an
authorized human.

Retain the longer-horizon in-place v0.3.1 compatibility regression with
pre-existing dirty critical files: validate single-owner bindings, preview and
record an authorized baseline adoption, expire and recover one real v0.3.1
windowless active Claim, run two complete Claim iterations, and
prove that context, Dashboard, reconciliation, and verification report the same
eligibility. The adoption must not create a Claim or mutate Git/SVN.

Do not publish until the simulated end-to-end project lifecycle in
[RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) completes with no missing
artifacts or severity-one workflow blockers. Publish one Skill ZIP, one wheel,
one sdist, and checksums. Do not commit built artifacts. If a release is
withdrawn, mark it as withdrawn in GitHub and the changelog; do not reuse or
silently move the released tag.
