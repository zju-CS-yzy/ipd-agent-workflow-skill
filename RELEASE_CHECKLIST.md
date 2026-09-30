# GitHub Release Checklist

Use this checklist for every GitHub release. The target for this cycle is Python package `0.3.0b1` and public label `v0.3.0-beta`. No release may start until the simulated lifecycle gate below passes with no missing artifacts or severity-one workflow blockers.

## Repository baseline

- [x] Public capability claims map to implemented modules and behavior tests.
- [x] `SKILL.md` has valid frontmatter, a discriminating description, reference routing, and an explicit human-approval boundary.
- [x] Package, Skill, changelog, and intended release label use `ipd-agent-workflow-skill`, `0.3.0b1`, and `v0.3.0-beta` consistently.
- [x] State and policy schemas reject unknown fields and document semantic checks performed by `ipdctl`.
- [x] Deliverable acceptance and final TR/DCP approval require an authorized human record; agents cannot finalize approval.
- [x] English and Simplified Chinese README, architecture, and deployment files are present and cross-linked.
- [x] The single package includes `ipdctl/messages.yaml`; no locale-specific package or long-lived language branch is required.
- [x] CI installs the package and runs both locales on Python 3.10 and 3.14, plus one clean-package job.
- [x] From the final source, run `python -B -m unittest discover -s tests -v` and record the passing test count (101 passed on 2026-09-30).
- [x] From the final source, run the Skill validator and `python -B -m ipdctl --help`.
- [x] Build wheel and sdist into a temporary directory, inspect their contents, and smoke-test installed `ipdctl` outside the checkout in both locales.
- [x] Run `python -B scripts/release_check.py .`; no cache, temporary files, build output, generated state output, credentials, personal paths, high-confidence secret patterns, version drift, or missing language resources are found.
- [x] Run `git diff --check` and inspect `git status --short`; all listed files are intended source.
- [x] Review the complete Git history and the final staged diff for secrets before publishing.

## Bilingual contract

- [x] `init --locale en` and `init --locale zh-CN` persist the requested locale; unsupported values fail explicitly.
- [x] A v0.2 profile without `presentation.locale` runs in English and is not rewritten merely by being read.
- [x] Machine contracts remain English: commands, parameters, filenames, YAML/JSON keys, schema paths, IDs, statuses, relations, and report codes.
- [x] English and Simplified Chinese message keys are complete and formatting placeholders agree.
- [x] Switching locale and refreshing does not change workflow facts, review history, evidence, claims, revisions beyond documented refresh behavior, or graph topology.
- [x] Dashboard manifest locale participates in freshness verification.
- [x] English and Simplified Chinese Dashboard Golden tests pass, including SVG layout and interactive detail checks (25/25 in each locale).

## Simulated lifecycle release gate

- [x] In an isolated realistic project, complete initialization, tailoring, context, claim, work evidence, close, review, authorized-human approval or rejection, refresh, repository inspection, reconciliation, and verify.
- [x] Repeat at least one rejected-and-reworked deliverable iteration and confirm status, runtime events, review history, evidence, revision, Dashboard, matrices, JSON projections, and verification reports update exactly once per accepted operation.
- [x] Confirm the complete rejection/rework/approval history remains present and the latest authorized human decision alone governs the current Deliverable or Gate outcome.
- [x] Exercise Deliverable and Gate review subjects plus `advance-phase`; premature phase advancement must fail without corrupting state, and a ready phase must advance exactly once.
- [x] Progress through every generated Phase/TR/DCP/Gate needed for a complete lifecycle; record every expected artifact and compare it with actual output.
- [x] Run the scenario in both locales or prove structural equivalence from the same facts; confirm user-facing text changes while machine facts and graph topology do not.
- [x] Record all observed gaps. The final rerun completed 6 Phases, 18/18 Deliverables, 12/12 Gates, 40 iteration checkpoints, 192 runtime events, and 15 Dashboard files with 0 missing outputs and 0 severity-one workflow issues.

## Version and release content

- [x] Freeze the release commit and confirm `pyproject.toml`, `ipdctl.__version__`, CLI version, changelog, tag, and GitHub Release title use `0.3.0b1` / `v0.3.0-beta` consistently.
- [x] Write release notes that call out beta compatibility, human approval requirements, supported Python versions, and known limitations.
- [x] Create the annotated tag from the reviewed clean commit; never reuse or silently move a published tag.
- [x] Attach one bilingual Skill ZIP, one wheel, one sdist, and checksums. Do not publish separate locale packages or commit build/generated output.
- [x] Test the published Skill ZIP, wheel, and sdist in clean temporary locations.

## GitHub and publication

- [x] Use `zju-CS-yzy/ipd-agent-workflow-skill` as the canonical GitHub repository and include its URLs in project metadata and documentation.
- [x] Confirm the canonical remote repository exists and is reachable.
- [x] Push the reviewed default branch and tag.
- [ ] Require CI and review on the default branch; restrict force pushes and tag mutation.
- [ ] Enable private vulnerability reporting and set a real private maintainer contact or security advisory process.
- [ ] Set repository description, topics, license display, Actions permissions, and release visibility.
- [x] Confirm GitHub Actions passes for the pushed commit and tag, and verify the published README, Skill files, license, workflow, and source archive.
- [x] After publication, install the public Skill ZIP, wheel, and sdist and run the `init` → `tailor` → `context` → `refresh` → `verify` smoke test in both locales; each run produces 15 Dashboard files and a passed verification report.
