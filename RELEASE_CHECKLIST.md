# GitHub Release Checklist

Use this checklist for every GitHub release. The target for this cycle is Python package `0.3.2b1` and public label `v0.3.2-beta`. No release may start until the upgrade and simulated-lifecycle gates below pass with no missing artifacts or severity-one workflow blockers.

## Repository baseline

- [x] Public capability claims map to implemented modules and behavior tests.
- [x] `SKILL.md` has valid frontmatter, a discriminating description, reference routing, and an explicit human-approval boundary.
- [x] Package, Skill, changelog, workflow, and intended release label consistently use `0.3.2b1` and `v0.3.2-beta`.
- [x] State and policy schemas reject unknown fields and document semantic checks performed by `ipdctl`.
- [x] Deliverable acceptance and final TR/DCP approval require an authorized human record; agents cannot finalize approval.
- [x] English and Simplified Chinese README, architecture, and deployment files are present and cross-linked.
- [x] The single package includes `ipdctl/messages.yaml`; no locale-specific package or long-lived language branch is required.
- [x] CI covers Python 3.10 and 3.14, both locales, clean package installation, and the v0.3.1 in-place upgrade.
- [x] From the final source, `python -B -m unittest discover -s tests -v` passed 142/142 tests in 1024.615 seconds on 2026-10-02.
- [x] From the final source, the Skill validator, compile check, CLI version, and `python -B -m ipdctl --help` pass.
- [x] Wheel and sdist build in a temporary directory, contain the message and binding-schema package data, and each passes installed `init` → `tailor` → `context` → `validate` → `refresh` → `verify` smoke tests in both locales with 15 Dashboard files.
- [x] `python -B scripts/release_check.py .` passes after generated caches and build metadata are removed (99 text files scanned).
- [x] `git diff --check` passes and `git status --short` contains only intended release source; line-ending notices are configuration warnings, not whitespace errors.
- [x] Review the final diff, untracked-file inventory, and recent repository history for credentials or unintended project data before publishing; no high-confidence secret pattern or project-instance output was found.

## Artifact binding and Claim provenance

- [x] `artifact_bindings.yaml` validates unique rule IDs, project-relative patterns, known Deliverable owners, and single-owner critical changes.
- [x] Context, Claim preflight, reconciliation, Dashboard, refresh, and verify consume the same normalized eligibility result.
- [x] Baseline adoption requires an authorized human actor and reason, is previewable and idempotent, records exact hashes, and creates neither a Claim nor a VCS commit.
- [x] Every v0.3.2 Claim records a binding window; rejected or recovered work inherits its original unfinished-iteration window.
- [x] Successful verification advances the exact artifact baseline; failed verification preserves the last successful baseline while immediately blocking Claim actionability.
- [x] Two consecutive verifies over an intentionally dirty but valid iteration remain fresh and consistent across CLI and Dashboard.
- [x] State, runtime, report, and Dashboard mutations use a crash-recoverable project transaction; injected write failure and process exit restore the prior bundle.
- [x] A crash after commit retirement preserves committed facts; the canonical journal lock is acquired before snapshotting, and deterministic pre-lock plus staggered concurrent Claim tests prove a losing command cannot overwrite audit history.
- [x] A dead preparing journal is discarded without rollback, while unknown owner liveness fails closed and preserves the journal.
- [x] A crash-released OS mutex covers recovery through journal retirement; deterministic dual-recovery testing proves one process cannot retire another process's replacement journal.
- [x] One Claim command uses one fixed instant for lease expiry and takeover decisions.

## Bilingual contract

- [x] `init --locale en` and `init --locale zh-CN` persist the requested locale; unsupported values fail explicitly.
- [x] A v0.2 profile without `presentation.locale` runs in English and is not rewritten merely by being read.
- [x] Machine contracts remain English: commands, parameters, filenames, YAML/JSON keys, schema paths, IDs, statuses, relations, and report codes.
- [x] English and Simplified Chinese message keys are complete and formatting placeholders agree.
- [x] Switching locale and refreshing does not change workflow facts, review history, evidence, claims, revisions beyond documented refresh behavior, or graph topology.
- [x] Dashboard manifest locale participates in freshness verification.
- [x] English and Simplified Chinese Dashboard Golden tests pass, including recursive prerequisite closure, SVG dependency direction, layout, and interactive detail checks (27/27 in each locale).
- [x] Waiting on prerequisites, explicit blocking, rejected rework, orphan claims, and terminal superseded Deliverables remain distinguishable in machine data and Dashboard summaries.

## v0.3.1 in-place upgrade gate

- [x] Build a project with the actual `v0.3.1-beta` Tag, then use current code without rerunning current `init` or `tailor`.
- [x] Keep `task_profile.yaml` and `tailored_process.yaml` byte-identical throughout the upgrade.
- [x] Add an explicit single-owner critical binding, preview and record authorized baseline adoptions, and prove each adoption creates zero Claims.
- [x] Expire a real v0.3.1 windowless active Claim, prove recovery fails before adoption and after stale S1, then recover it only through a later exact authorized-human S2 baseline.
- [x] Complete the recovered reject/rework iteration and one accepted iteration with two distinct v0.3.2 Claim windows.
- [x] Final context and Dashboard eligibility are true, reconciliation and the latest verification pass, and all 15 Dashboard files exist.
- [x] Recorded result on 2026-10-02: stale S1 plus exact S2 adoption, 3 Claims (1 legacy, 2 windowed), 1 Claim expiry, 2 passed verifications, unchanged profile/process hashes, and 15 Dashboard files.

## Simulated lifecycle release gate

- [x] In an isolated realistic project, complete initialization, tailoring, context, Claim, work evidence, close, review, authorized-human approval or rejection, refresh, repository inspection, reconciliation, and verify.
- [x] Repeat rejected-and-reworked work and confirm status, runtime events, review history, evidence, revisions, Dashboard, matrices, JSON projections, and reports update exactly once per accepted operation.
- [x] Confirm complete rejection, rework, and approval history remains present and the latest authorized-human decision alone governs current outcome.
- [x] Exercise Deliverable and Gate review subjects plus `advance-phase`; premature advancement fails without corrupting state and a ready phase advances exactly once.
- [x] Complete every generated Phase/TR/DCP/Gate and compare every expected artifact with actual output.
- [x] Run both locales and prove structural equivalence from the same facts; presentation changes while machine facts and topology do not.
- [x] Confirm zero missing outputs and zero severity-one workflow blockers. Recorded result: 40 verified iterations; 6 phases; 18/18 accepted Deliverables; 12/12 approved Gates; final `lifecycle`; state revision 307; runtime revision/events 192; 15 Dashboard files; 66 graph nodes; 153 graph edges; 0 active Claims; cleanup confirmed.
- [x] Independently verify a three-level cross-phase dependency chain: canonical JSON is `dependent -> prerequisite` and dependency SVG is `prerequisite -> dependent` with no unrelated edge types.

## Version and release content

- [x] Source version references were prepared for `0.3.2b1` / `v0.3.2-beta`, and no conflicting release Tag existed at freeze time.
- [x] Release notes document upgrade behavior, beta compatibility, approval boundaries, Python support, transaction behavior, and known limitations.
- [x] Freeze the reviewed release commit and create a new annotated `v0.3.2-beta` Tag; never reuse or move a published Tag.
- [x] Attach one bilingual Skill ZIP, one wheel, one sdist, and checksums; do not commit build or generated project output.
- [x] Install the published ZIP, wheel, and sdist in clean temporary locations and run both locale smoke tests.

## GitHub and publication

- [x] Use `zju-CS-yzy/ipd-agent-workflow-skill` as the canonical GitHub repository and include its URLs in project metadata and documentation.
- [x] Confirm the canonical remote repository exists and is reachable.
- [x] Push the reviewed default branch and `v0.3.2-beta` Tag.
- [x] Require pull requests, the current `governance-gate`, an up-to-date branch, and resolved conversations on the default branch; restrict default-branch deletion and force pushes and published `v*` Tag mutation.
- [ ] Require one independent approving review after a second trusted maintainer is appointed; until then, keep the owner bypass limited to pull requests so a single maintainer cannot push directly to the protected default branch.
- [x] Enable private vulnerability reporting and point `SECURITY.md` to the canonical private security advisory process.
- [x] Set the repository description and topics; confirm the Apache-2.0 license display, read-only default Actions permissions, immutable Action revisions, and public prerelease visibility.
- [x] Confirm GitHub Actions passes for the pushed commit and Tag, and verify the published README, Skill files, license, workflow, and source archive.
- [x] After publication, install the public Skill ZIP, wheel, and sdist and run the `init` → `tailor` → `context` → `validate` → `refresh` → `verify` smoke test in both locales; each run must produce 15 Dashboard files and a passed verification report.

## v0.3.2-beta publication record

- Release commit: `1d02261314ac005d8d138b9ea9de86046838c2f1`.
- Annotated Tag object: `6b15f4caf978abe84641e5ea086eedc3f5e3bb56`; the Tag resolves to the release commit above.
- GitHub Actions: default-branch test run `36939492008`, Tag test run `36939906301`, and Tag release run `36939906420` all completed successfully on 2026-10-02.
- The public prerelease exposes exactly the bilingual Skill ZIP, wheel, sdist, and `SHA256SUMS.txt` described above. All three payload checksums match the published checksum file.
- Public-download qualification passed all six artifact/locale combinations (`skill-zip`, wheel, and sdist × `en` and `zh-CN`); every run reported `ipdctl 0.3.2-beta`, generated 15 Dashboard files, and wrote `verify_report.json` with status `passed`.
- Both prepublication and public-download temporary roots were removed after verification; the repository contains no generated project or build output.

## GitHub governance record

- Governance baseline commit `be4b320ed5f2a164f19b5d5a42152da320e6db55` introduced the stable `governance-gate`, the private vulnerability reporting route, contributor policy, and pull request template. Action-pinning commit `1a408fa9155ef3cf6d3264143b95b93fe40d5096` pinned every workflow Action to an immutable full commit SHA and extended the release contract checks.
- Default-branch ruleset [`Protect default branch`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/rules/24341050) requires pull requests, an up-to-date successful `governance-gate`, and resolved review conversations; it blocks deletion and non-fast-forward updates. The owner bypass is pull-request-only.
- Release-tag ruleset [`Protect release tags`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/rules/24341081) blocks updates and deletion for `refs/tags/v*` while allowing new release Tags to be created.
- GitHub Actions remains enabled with read-only default workflow permissions, pull request approval disabled, and full-SHA pinning required. Only the release workflow declares the narrow write permission it needs.
- Private vulnerability reporting is enabled through the repository security advisory form. The public repository has its canonical description and topics, Apache-2.0 is recognized, and `v0.3.2-beta` remains a public non-draft prerelease with four release assets.
- Governance validation runs [`36942399851`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/36942399851) and [`36944356586`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/36944356586) completed successfully, including the required `governance-gate`.
- Independent approval intentionally remains deferred until a second trusted maintainer is available; requiring one approval from a single maintainer would make the ordinary pull request path unusable.
