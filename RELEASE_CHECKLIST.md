# GitHub Release Checklist

Use this checklist for every GitHub release. The target for this cycle is Python package `0.5.1b1` and public label `v0.5.1-beta`. No release may start until the upgrade and simulated-lifecycle gates below pass with no missing artifacts or severity-one workflow blockers.

## v0.5.1-beta release readiness

- [x] Confirm review, approval, and rejection are locked to one canonical `current_iteration_subject`, including Deliverable and Gate paths.
- [x] Confirm an actual `v0.5.0-beta` project paused mid-review fails closed without a subject and can recover only through an explicit authorized-human action with a recorded reason.
- [x] Confirm `render-dashboard` is byte-for-byte fact preserving, formal `refresh` rejects the review stage without writes, and one legal refresh increments state exactly once.
- [x] Confirm `governance.md` is derived from canonical facts and that version, Gate-ID, Gate-status, and content drift are reported by stable diagnostics.
- [x] Run the complete unit suite, compile check, Skill validator, lifecycle simulations, and `scripts/verify_v050_upgrade.py` from the final source.
- [x] Qualify the frozen external real-project Golden in independent copies, preserve known failures and historical facts, verify the original directory remains untouched, and keep private assets outside Git.
- [x] Pass the self-contained 300-node renderer regression and actual-browser bilingual file/HTTP checks, including all 32 relationship-filter combinations, file navigation, phase changes and keyboard interaction.
- [x] Build the wheel and sdist in isolation; install the Skill ZIP, wheel, and sdist in both locales; require the exact 16-file Dashboard inventory and passed verification.
- [x] Run `python -B scripts/release_check.py .`, `git diff --check`, and the final credential/project-output/source audit.
- [ ] Publish only after the protected pull request, default-branch, Tag-test, and Tag-release workflows pass; then verify public assets and record immutable SHAs, hashes, workflow runs, and download-smoke results below.

## Final v0.5.1-beta local qualification — 2026-10-09

The two Dashboard additions and replacement Golden gates are qualified from
one unchanged final program/test/script/schema input set on Windows x64:

- All 34 modules pass Python 3.10.22 / 3.14.8 × `en` / `zh-CN`, with 296 tests
  per combination, 1,184 executions in total, zero skips and zero failures.
  Capability lifecycle, full project lifecycle and two-round progressive
  refinement simulations complete their positive/negative governance paths.
  The standard full lifecycle follows the matrix locale. Capability/refinement
  retain fixture locale defaults; separate installed, model and browser checks
  provide explicit bilingual coverage.
- Five actual published-Tag upgrades pass on both Python endpoints: 10/10.
  Earlier intermediate orchestration timeouts were retried; the final complete
  upgrade run passes without timeouts.
- A frozen external real v0.5.0 project passes the replacement upgrade gate on
  both endpoint Pythons, including bilingual rendering, simulated authorized
  legacy-review recovery, cross-subject rejection, deterministic pure rendering,
  strict review-step refresh refusal and preservation of known diagnostics.
  Expected failed project verification remains failed; no baseline adoption or
  human approval was fabricated to make it green.
- Chrome/Edge × bilingual × local-file/HTTP × synthetic/real-copy fixtures pass
  16/16 browser cases. Each checks all 32 filter combinations, stable layout,
  phase selection, mandatory actual SVG click/keyboard routing, file links,
  clipboard/fallback behavior, zoom and unique DOM identifiers.
- Self-contained 300-node graph and all-six-task-type bilingual output checks
  pass. Original v1.4 resource identity or pixel equivalence is not claimed.
- Isolated builds and independent Skill ZIP/wheel/sdist installations pass
  12/12 endpoint/artifact/locale combinations, including canonical inline node
  identities and the exact 16-file/manifest-2.2 output contract.
- Compilation, Skill validation, nine Schema definitions, twelve generated fact
  validations, release hygiene and repository-configured whitespace checks pass.

The original project received subsequent changes while tests ran. This task
used only enumeration, reads and hashes in that directory; no IPD/Git command,
write, rollback or upgrade ran there. The captured fixture stays unchanged.
Qualification covers that frozen baseline, not the later live project state.

Private fixtures, their durable local archive, filenames, paths, detailed logs
and screenshots remain outside Git and distributions. Local candidates are not
public assets. The working tree is uncommitted; protected PR/default-branch/Tag
workflows and public-download checks belong to the publication phase.

Publication preparation also makes the browser job a required dependency of
`governance-gate`. The release workflow waits for a successful test run of the
same release Tag before uploading public assets; workflow structure and narrow
read permissions were checked after this CI-only change.

## Earlier v0.5.1-beta qualification — before Dashboard navigation additions

The recovered working tree is a tested release candidate, not a published
release. On Windows x64, all 33 test modules passed in every combination of
Python 3.10.22 / 3.14.8 and `en` / `zh-CN`: 290 tests per combination, 1,160
test executions in total, zero skips. This includes the full project lifecycle,
capability lifecycle, and two-round progressive-refinement scenarios. The
complete runtime, test, script, policy, and schema input hashes remained
unchanged during the final matrix. The standard full-lifecycle scenario follows
the locale setting; the capability and refinement scenarios currently retain
their own fixture locale defaults. Installed all-capability bilingual smokes and the
explicit locale regression tests supply separate language coverage.

All five real published-Tag upgrade probes passed on both endpoint Python
versions (10/10). Isolated PEP 517 wheel/sdist builds and independent Skill ZIP,
wheel, and sdist installations passed both locales on both Python versions
(12/12 artifact/version/locale combinations). Each installation ran outside the
checkout, loaded all four Capability Policies, used explicit Owner bindings and
an authorized test-fixture baseline, exercised review plus expired-Claim
rendering/recovery, and finished with passed validation/verification and the
exact 16-file Dashboard. The complete runtime modules, nine Schemas, four
Capability Policies, message catalog, and applicable upgrade scripts were
checked in the distributions. Skill instructions and bilingual guidance are
supplied by the Skill ZIP; wheel/sdist install the Python execution surface.

The actual compile check, Skill validator, release hygiene audit, and whitespace
check passed. All nine JSON Schema definitions and twelve generated fact
instances also passed Draft 2020-12 validation. Candidate packages and per-case
logs are local qualification evidence, not public asset identifiers.

The original external v1.4 Golden fixture was not recovered and is absent from
the repository's Git object history. Its historical report remains explicitly
labelled as historical. Current Golden-harness unit tests passed, but they do
not constitute a fresh comparison against the missing original 286-node
fixture. The user has approved replacement of that external dependency with a frozen
local real-project Golden plus independent large-graph and browser regression
gates; the new final qualification is recorded separately below. The working tree also remains uncommitted, so protected
pull-request/default-branch and Tag workflows must still qualify the eventual
release commit before publication.

## Proposed follow-up priorities

- **Before v0.5.1 publication:** pass the replacement Golden and interaction
  gates, include all required untracked source
  files in the release commit, and pass the protected CI and Tag workflows.
- **v0.5.2:** unify the new local/CI qualification entry points and strengthen
  deterministic expected-fact fixtures, Windows CI,
  a real SVN fixture, configurable simulation locales, rendering-specific
  failure injection, and a read-only Owner-coverage preflight, and file-navigation scans restricted
  to explicit binding scopes for large repositories. Preserve the
  single-Claim and authorized-human boundaries.
- **v0.6.0:** add explicit, previewable Artifact/Evidence path migrations and
  scoped baseline adoption. Require exact before/after hashes, an identified
  authorized human and reason, preserved history/Owners/Claim trace links,
  bounded scope, stale-verification handling, and auditable idempotent replay.
- **v0.7.0:** add independent content-readiness review, immutable external
  evidence snapshots/digests, and versioned reusable domain capabilities.
  Structural validity, content readiness, and final human approval remain
  distinct; remote content changes must invalidate the relevant verification.

## v0.5.1-beta publication record

- [ ] Record the immutable release commit and annotated Tag object after publication.
- [ ] Record the successful branch, pull-request, default-branch, Tag-test, and Tag-release workflow runs.
- [ ] Confirm the public prerelease exposes exactly one bilingual Skill ZIP, one wheel, one sdist, and `SHA256SUMS.txt`, with matching payload hashes.
- [ ] Record all six public artifact/locale smoke results and removal of the temporary download root.

No publication identifiers or artifact hashes are recorded until those events have occurred.

## v0.5.0-beta repository baseline (historical)

- [x] Public capability claims map to implemented modules and behavior tests.
- [x] `SKILL.md` has valid frontmatter, a discriminating description, reference routing, and an explicit human-approval boundary.
- [x] Package, Skill, changelog, workflow, and intended release label consistently use `0.5.0b1` and `v0.5.0-beta`.
- [x] State and policy schemas reject unknown fields and document semantic checks performed by `ipdctl`.
- [x] Deliverable acceptance and final TR/DCP approval require an authorized human record; agents cannot finalize approval.
- [x] English and Simplified Chinese README, architecture, and deployment files are present and cross-linked.
- [x] The single package includes `ipdctl/messages.yaml`; no locale-specific package or long-lived language branch is required.
- [x] CI covers Python 3.10 and 3.14, both locales, clean package installation, retained v0.3.1/v0.3.2/v0.4.0 compatibility, and the direct v0.4.1 in-place upgrade.
- [x] From the final source, `python -B -m unittest discover -s tests -v` passes with no skipped release-critical checks.
- [x] From the final source, the Skill validator, compile check, CLI version, and `python -B -m ipdctl --help` pass (`ipdctl 0.5.0-beta`).
- [x] Wheel and sdist build into an isolated temporary directory, contain all four Capability Policies, the message catalog, process-extension template, and all schemas, and pass installed catalog plus lifecycle smoke tests.
- [x] `python -B scripts/release_check.py .` passes after generated caches and build metadata are removed.
- [x] `git diff --check` passes and `git status --short` contains only intended release source; line-ending notices are configuration warnings, not whitespace errors.
- [x] Review the final diff, untracked-file inventory, and recent repository history for credentials or unintended project data before publishing; confirm no credentials, project-instance data, generated Dashboard output, screenshots, caches, or unexpected binaries are present.

Recorded on 2026-10-06 from the final local development source: all 267 tests passed in 1671.655 seconds; the Skill validator, compile check, CLI version/help, isolated wheel and sdist installation tests, four-policy catalog smoke tests, both locale lifecycle smokes, v0.4.1 in-place upgrade probe, and release hygiene check passed. The final source audit found no credentials, project-instance data, generated Dashboard output, screenshots, caches, or unexpected binaries.

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

## v0.4.0 to v0.4.1 in-place upgrade gate

- [x] Build the fixture from the actual published `v0.4.0-beta` Tag and open it with v0.4.1 without rerunning `init`.
- [x] Prove `tailor --preview --json` is byte-for-byte zero-write and reports `state.traceability` additions, removals, and redirects through the existing five diff keys.
- [x] Preserve every Claim-linked relation whose endpoints survive; any unexplained Claim-link loss must appear in `ambiguous` and block application.
- [x] Migrate legacy generic Gate history only through an explicit one-to-one `gate_migrations` record; reject a missing, self, unknown, or ambiguous mapping.
- [x] Apply one evidence-bearing same-ID dependency correction only when exact `before` and `after` sets match, and only with an identified authorized human Actor and reason.
- [x] Preserve evidence and all review history, set corrected work to `blocked`, invalidate affected unapproved Gate readiness, require reapproval, and fail closed if an affected Gate is already approved.
- [x] Prove idempotent replay creates no duplicate `process_migration` event and changes no state on the second run.
- [x] Confirm root-anchored Binding globs, Windows UTF-8 Chinese output, and stable valid/invalid `validate --json` contracts.
- [x] Finish with `refresh`, `verify`, and all 15 Dashboard outputs present; record the exact assertion count and result here.

Recorded on 2026-10-06 from the actual `v0.4.0-beta` Tag: all 15/15 qualification result fields matched; 10 Deliverables and 5 Claim-linked relations were preserved; preview reported 1 addition, 1 removal, and 3 redirects without writes; 3 generic Gates migrated; illegal Claim-link deletion failed closed; the evidence-bearing dependency correction preserved history and required reapproval; replay was idempotent; final validation and verification passed with all 15 Dashboard files.

## v0.4.1 to v0.5 in-place upgrade gate

- [x] Build the fixture from the actual published `v0.4.1-beta` Tag and open it with current v0.5 source without rerunning `init`.
- [x] Preserve accepted status, evidence, reviews, one applied refinement, the existing Runtime event prefix, and all 15 Dashboard files.
- [x] Prove a profile without `capability_patterns` remains readable and produces a strictly zero-diff, zero-write `tailor --preview --json` result.
- [x] Explicitly enable `interface_contract_and_integration` only in the preview candidate and report exactly its three added Deliverables with no removals or ambiguity.
- [x] Finish the unchanged project with passing `validate --json`, `refresh`, and `verify --json` results.

Recorded on 2026-10-06 from the actual `v0.4.1-beta` Tag: `init_replayed=false`; accepted evidence, reviews, one refinement record, and 8 existing Runtime events were preserved; the no-op preview reported zero changes and wrote nothing; explicit capability preview added exactly 3 Deliverables without writing; final validation and verification passed with all 15 Dashboard files.

## v0.5 capability catalog and actionability gate

- [x] Compile each of the four registered Capability Policies independently and together; require canonical order, unique IDs, valid provenance, complete bilingual labels, and synchronized Schema enums.
- [x] Prove missing and empty `capability_patterns` are equivalent and add no capability nodes.
- [x] Fail closed when an installed registry asset is missing or an unregistered Capability Policy appears.
- [x] Apply a reviewed module refinement without a duplicate project declaration, persist the policy-owned requirement, preserve the abstract root, and rewrite downstream `depends_on` edges to concrete leaves.
- [x] Keep `depends_on` as the only execution topology while `supports`, `verifies`, `supersedes`, and `refines` remain trace semantics.
- [x] Use one shared classifier for `waiting_items`, `explicit_blockers`, and `governance_blockers` in Context and Dashboard while retaining the deduplicated `blocked_items` compatibility field.
- [x] Complete the six-Phase capability-enabled lifecycle simulation with explicit Owner bindings, one applied module refinement, complete evidence/review history, Dashboard output, and passing final verification.

Recorded on 2026-10-06 from the final v0.5 development source: three opt-in capabilities; 20 initial and 22 final Deliverables; 21 concrete Deliverables accepted; 12 Gates approved; one authorized module refinement; required Owner fail-closed behavior and refined-binding baseline adoption; all three actionability categories; 15 Dashboard files; 72 graph nodes and 192 graph edges; passed final verification; and confirmed temporary-project cleanup. The isolated test completed in 719.137 seconds.

## v0.3.2 to v0.4 in-place upgrade gate

- [x] Build the fixture from the actual published `v0.3.2-beta` Tag and open it with v0.4 without rerunning `init`.
- [x] Verify the legacy process before re-tailoring and prove read-only commands leave `task_profile.yaml` and `tailored_process.yaml` byte-identical.
- [x] Prove `tailor --preview --json` writes nothing and reports no ambiguous migration.
- [x] Re-tailor to process schema `2.0` while preserving accepted status, evidence, and review history.
- [x] Enable `sourced_component_integration` and prove its three Deliverables begin at `planned` with Capability provenance in Dashboard data.
- [x] Prove the changed managed-binding contract fails closed with `BINDING_BASELINE_STALE`, then passes only after previewed, authorized-human baseline adoption.
- [x] Recorded local result on 2026-10-03: all 13 upgrade assertions passed, the canonical project extension was materialized, and final verification reported `passed`.

## Simulated lifecycle release gate

- [x] In an isolated realistic project, complete initialization, tailoring, context, Claim, work evidence, close, review, authorized-human approval or rejection, refresh, repository inspection, reconciliation, and verify.
- [x] Repeat rejected-and-reworked work and confirm status, runtime events, review history, evidence, revisions, Dashboard, matrices, JSON projections, and reports update exactly once per accepted operation.
- [x] Confirm complete rejection, rework, and approval history remains present and the latest authorized-human decision alone governs current outcome.
- [x] Exercise Deliverable and Gate review subjects plus `advance-phase`; premature advancement fails without corrupting state and a ready phase advances exactly once.
- [x] Complete every generated Phase/TR/DCP/Gate and compare every expected artifact with actual output.
- [x] Run both locales and prove structural equivalence from the same facts; presentation changes while machine facts and topology do not.
- [x] Confirm zero missing outputs and zero severity-one workflow blockers for the v0.4 capability-enabled, project-extension-enabled scenario. Recorded from the final source in both locales on 2026-10-05: 22/22 Deliverables accepted, 12/12 Gates approved, 5 phase advances, 44 verified iterations, 216 Runtime events, 15 Dashboard files, zero missing outputs, and zero severe issues in each locale.
- [x] Independently verify a three-level cross-phase dependency chain: canonical JSON is `dependent -> prerequisite` and dependency SVG is `prerequisite -> dependent` with no unrelated edge types.

## Progressive refinement release gate

- [x] Declare an explicit project refinement requirement, accept its concrete root through the public lifecycle, and confirm `context` plus Dashboard change it from `pending` to `due` without template or domain inference.
- [x] Prove two identical `refine --preview --json` calls are deterministic and byte-for-byte zero-write, while a stale base, pending trigger, active Claim, or missing human authority fails closed.
- [x] Apply two nested `expand` plans through the public CLI and prove parent/intermediate evidence and review history remain intact while every new child starts `planned` with empty evidence and reviews.
- [x] Prove a managed evidence rule and parent Owner do not authorize a new concrete child: preview, context, verify, Dashboard, and Claim expose `REFINEMENT_OWNER_REQUIRED` until a user-authored Owner binding is added.
- [x] Confirm `refines` is same-Phase acyclic structural ancestry only, `depends_on` remains the sole execution topology, and recursive root/intermediate concrete leaf closures are correct after two rounds.
- [x] Confirm each changed Gate requirement fingerprint increments `review_epoch`, preserves old evidence, invalidates old approval, and requires a current-epoch authorized-human decision.
- [x] Confirm exactly two strict `process_refinement_applied` events, exact replay no-op, plan-ID conflict rejection, ordinary `tailor` lineage-bypass rejection, and verification fingerprint invalidation.
- [x] After each round, run `refresh` and `verify`; confirm all 15 Dashboard outputs, hierarchy/status/impact details, graph relations, matrices, and machine projections are present and consistent.

Recorded again on 2026-10-06 from final source, installed wheel, and installed sdist: two authorized refinement events, two nested leaf closures, Gate review epoch 2, parent/intermediate history preserved, deterministic replay, all four preflight failures, plan-ID conflict, input/runtime tamper, duplicate event, ordinary-tailor bypass, historical ID/dependency rewrite, downstream Claim, and missing Owner protections all behaved fail-closed; each successful round regenerated all 15 Dashboard files and ended with a passed verification. The installed wheel and sdist also passed capability-enabled smoke tests in `en` and `zh-CN`; explicit full-lifecycle locale runs passed 2/2 in 670.865 seconds and 678.754 seconds respectively.

## Version and release content

- [x] Source version references are prepared for `0.5.0b1` / `v0.5.0-beta`.
- [x] Release notes document upgrade behavior, beta compatibility, approval boundaries, Python support, capability selection, and known limitations.
- [x] Confirm no conflicting remote `v0.5.0-beta` Tag exists at freeze time.
- [x] Freeze the reviewed release commit and create a new annotated `v0.5.0-beta` Tag; never reuse or move a published Tag.
- [x] Attach one bilingual Skill ZIP, one wheel, one sdist, and checksums; do not commit build or generated project output.
- [x] Install the published ZIP, wheel, and sdist in clean temporary locations and run both locale smoke tests.

## GitHub and publication

- [x] Use `zju-CS-yzy/ipd-agent-workflow-skill` as the canonical GitHub repository and include its URLs in project metadata and documentation.
- [x] Confirm the canonical remote repository exists and is reachable.
- [x] Push the reviewed default branch and `v0.5.0-beta` Tag.
- [x] Require pull requests, the current `governance-gate`, an up-to-date branch, and resolved conversations on the default branch; restrict default-branch deletion and force pushes and published `v*` Tag mutation.
- [ ] Require one independent approving review after a second trusted maintainer is appointed; until then, keep the owner bypass limited to pull requests so a single maintainer cannot push directly to the protected default branch.
- [x] Enable private vulnerability reporting and point `SECURITY.md` to the canonical private security advisory process.
- [x] Set the repository description and topics; confirm the Apache-2.0 license display, read-only default Actions permissions, immutable Action revisions, and public prerelease visibility.
- [x] Confirm GitHub Actions passes for the pushed commit and Tag, and verify the published README, Skill files, license, workflow, and source archive.
- [x] After publication, install the public Skill ZIP, wheel, and sdist and run the capability-enabled `init` → `tailor` → add reviewed single-Owner bindings → `validate --json` → authorized-human `adopt-baseline` → `context` → `refresh` → `verify` smoke test in both locales; each run must produce 15 Dashboard files and a passed verification report.

## v0.5.0-beta publication record

- [x] Record the immutable release commit and annotated Tag object after publication.
- [x] Record the successful branch, pull-request, default-branch, Tag-test, and Tag-release workflow runs.
- [x] Confirm the public prerelease exposes exactly one bilingual Skill ZIP, one wheel, one sdist, and `SHA256SUMS.txt`, with matching payload hashes.
- [x] Record all six public artifact/locale capability-enabled smoke results and removal of the temporary download root.

- Release pull request: [`#7`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/pull/7). Release commit: `7ec12624138f9cf0cc3db6aede29f43015f2abed`.
- Annotated Tag object: `56b5e2425c18605ab467e8cd6645fd2d5d0f6968`; `v0.5.0-beta` resolves to the release commit above.
- GitHub Actions: development-branch run [`37436907128`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37436907128), pull-request run [`37438140389`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37438140389), default-branch run [`37439271780`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37439271780), Tag test run [`37441306527`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37441306527), and Tag release run [`37441306523`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37441306523) all completed successfully on 2026-10-06.
- The public [`v0.5.0-beta` prerelease](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/releases/tag/v0.5.0-beta) exposes exactly one bilingual Skill ZIP, one wheel, one sdist, and `SHA256SUMS.txt`. Published SHA-256 values match all three downloads: Skill ZIP `95254e58ee77079be9f924258219b9b9ae283eb1e8d1734f4fd8ec67e76d591c`, wheel `40f551ca199063aaf7dad42b4f503283ea8cd4faa04edefbd17d09037b8514d4`, and sdist `f0b2969b31aaad75b4a7dd28f240821f324c75a1c95a8afbc94938fcb889689f`.
- Public-download qualification passed all six artifact/locale combinations (`skill-zip`, wheel, and sdist × `en` and `zh-CN`). Every installed artifact reported `ipdctl 0.5.0-beta`, tailored and validated all four Capability Policies, adopted three reviewed single-Owner bindings through an authorized-human baseline, passed final verification, and generated the exact 15-file Dashboard inventory in both locales.
- The Skill ZIP contains the expected bilingual README, Skill contract, Apache-2.0 license, message catalog, four Capability Policies, Schemas, lifecycle/refinement scripts, and pinned workflows. On Windows, installing the extracted source from an intentionally deep temporary path reached the legacy path-length limit; the same verified ZIP installed and passed from a shorter extraction root, while the wheel and sdist installed directly.
- The public-download temporary root was removed after verification, and the repository remained free of generated project output and build artifacts.

## v0.4.1-beta publication record

- [x] Record the immutable release commit and annotated Tag object after publication.
- [x] Record the successful default-branch, Tag-test, and Tag-release workflow runs.
- [x] Confirm the public prerelease exposes exactly one bilingual Skill ZIP, one wheel, one sdist, and `SHA256SUMS.txt`, with matching payload hashes.
- [x] Record all six public artifact/locale smoke results, the direct v0.4.0 upgrade qualification, and removal of the temporary download root.

- Release commit: `3637b6af183140413385b4fc77034792f80c96e3`.
- Annotated Tag object: `d8ad5680adfa3a59e8f314042a298aa3f8892954`; the Tag resolves to the release commit above.
- GitHub Actions: default-branch test run [`37377369656`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37377369656), Tag test run [`37377922904`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37377922904), and Tag release run [`37377922878`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37377922878) all completed successfully on 2026-10-06.
- The public [`v0.4.1-beta` prerelease](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/releases/tag/v0.4.1-beta) exposes exactly one bilingual Skill ZIP, one wheel, one sdist, and `SHA256SUMS.txt`. Published SHA-256 values match all three downloads: Skill ZIP `3cb411814e03eade9cd7ba702b02ff0e3b4694b86ae5665c20cf3443e8b77e1c`, wheel `0b0e8b4ff4e2c326c4b4ebabf0927b28f4a02fc50aee218fbf56768f75a91a52`, and sdist `0edc25e9a82efa2d2735d1db7e79394369a29bffdf7b9edfbc5e8cafdd206981`.
- Public-download qualification passed all six artifact/locale combinations (`skill-zip`, wheel, and sdist × `en` and `zh-CN`) plus the progressive-refinement simulation for every artifact. Every smoke run reported `ipdctl 0.4.1-beta`, passed `validate --json` and `verify --json`, and generated the exact 15-file Dashboard inventory; every progressive simulation passed with cleanup confirmed and 15 Dashboard files.
- Direct `v0.4.0-beta` in-place upgrade qualification matched all 15/15 result fields and preserved the audited process history described in the upgrade-gate record above. The public Tag source archive contains the expected README, Skill contract, Apache-2.0 license, and pinned workflows.
- The public-download and source-inspection temporary roots were removed after verification, and the repository remained clean with no generated project or build output.

## v0.4.0-beta publication record

- Release commit: `c247786f81aa4972982a7aa0d507fe31479031e3`.
- Annotated Tag object: `dd1d0941c073f46b0082fc3f01ac6da29868b023`; the Tag resolves to the release commit above.
- GitHub Actions: default-branch test run [`37330373664`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37330373664), Tag test run [`37330851567`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37330851567), and Tag release run [`37330851735`](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37330851735) all completed successfully on 2026-10-05.
- The public [`v0.4.0-beta` prerelease](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/releases/tag/v0.4.0-beta) exposes exactly one bilingual Skill ZIP, one wheel, one sdist, and `SHA256SUMS.txt`; all three payload hashes match the published checksum file.
- Public-download qualification passed all six artifact/locale combinations (`skill-zip`, wheel, and sdist × `en` and `zh-CN`), plus the progressive-refinement simulation for every artifact. Every smoke run reported `ipdctl 0.4.0-beta`, generated the exact 15-file Dashboard inventory, and wrote `verify_report.json` with status `passed`.
- The public-download temporary root was removed after verification, and the repository remained clean with no generated project or build output.

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
