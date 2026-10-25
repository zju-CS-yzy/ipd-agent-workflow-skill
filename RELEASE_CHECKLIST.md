# GitHub Release Checklist

Use this checklist for every GitHub release. The target for this cycle is Python package `0.5.4b1` and public label `v0.5.4-beta`. No release may start until the upgrade and simulated-lifecycle gates below pass with no missing artifacts or severity-one workflow blockers.

## v0.5.4-beta candidate scope — 2026-10-25

This section describes the candidate, not a completed release qualification.
Earlier sections below are historical source snapshots and must not be used to
claim that new source passed their tests.

- [x] Implement opt-in registry 1.1 / contract 0.5.4 with a prior-input snapshot; actual published v0.5.3 source rejects writing the adopted fixture without changing bytes.
- [x] Add hierarchical number allocation, stable identity/display mappings, per-parent stage plans, explicit support and child-argument references, and new-file draft revision.
- [x] Add starter pack 1.3.0 (23 bilingual types) and preserve pack 1.2.1. Add stage work-product JSON/UI and canonical input/freshness checks.
- [ ] Re-run final-source behavior tests, independent multi-parent/negative fixtures, both complete organized increments and both legacy increments. All applicable results must pass; missing or interrupted runs do not qualify.
- [ ] Pass historical upgrade gates, real isolated SVN fixtures, old/new Dashboard browser suites in file/HTTP modes, Windows/Linux and supported Python endpoint CI.
- [ ] Build and inspect Skill ZIP/wheel/sdist, validate byte identity against Git objects, and run isolated bilingual installation probes outside the checkout.
- [ ] Push only after local required checks pass, integrate only the qualified source, and require this release Tag's own successful CI before publication. Record actual public-download checks separately without moving the Tag.
- [x] Private Golden and real-project acceptance are not available as automated fixtures this cycle. Public synthetic test decisions do not stand in for human acceptance or authenticated repository approval mapping. Bulk historical path migration and native DOCX/XLSX remain outside this beta.

## v0.5.3-beta final candidate scope — 2026-10-22

- [x] GitHub HTTPS login is available. Candidate source and qualification records are pushed in [PR #12](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/pull/12).
- [x] The project owner confirmed that no authorized private Golden fixture is currently available. Private Golden and real-project acceptance remain **unexecuted**, rather than passed. This beta is qualified through public synthetic fixtures; planned private Golden coverage and the remaining P1/v0.5.2 backlog are retained as outstanding work. TR1–TR4 overview documents remain drafts and stage obligations need explicit project configuration.
- [x] Local source, failure/recovery, two-increment, historical-upgrade, package and browser evidence is retained in `docs/qualification/`. The 200 frozen production inputs and all 140 template assets are unchanged.
- [x] Reproduce the Windows CI worked-example failure: `core.autocrlf=true` changes executable fixture bytes and breaks the saved SHA-256. Pin only those Python fixtures to LF, retaining byte-exact evidence validation. A real Git-worktree regression covers both checkout modes; the fast example gate now precedes long behavior tests. The failed candidate is not qualified for publication; its successor must pass the full matrix.
- [ ] Require the final candidate's complete Windows/Linux × Python 3.10/3.14 × English/Chinese CI, packaging, historical upgrades, browser job and `governance-gate` to pass. [PR checks](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/pull/12/checks) provide the current commit's results. Superseded or cancelled runs are not passes.
- [ ] Integrate the qualified candidate, create the release Tag on the accepted commit, and require that Tag's own test run to succeed before publication. The release workflow enforces this separate Tag gate.
- [ ] Verify the four published assets, GitHub digests and `SHA256SUMS.txt`, then install the public downloads in isolated projects. Record publication separately without moving the release Tag.

This is the prepublication scope record. Earlier dated sections are historical observations; their unavailable-credential and missing-fixture statements describe those earlier attempts.

## v0.5.3-beta candidate commit and real SVN — 2026-10-21

- [x] Commit the candidate as `f2c532a5c593a3a33d6c6b7d082c884e707d0be7`; exclude the local roadmap and qualification workspaces. The remote `main` still matches the candidate's base, `7def7636efdf5473a0a29abc56df70d5d39cf421`.
- [x] Real SVN 1.15.0, both locales, two working copies per local repository: reproduce accepted facts, reject unaccepted governance bytes, map Unicode/space/`@` paths, classify unbound changes, and retain repository/working-copy bytes during every adapter operation. Each locale recorded 77 read commands, including 32 revision-pinned `cat` calls. This covers local `file://`, not remote authentication, mixed-revision detection or team writes.
- [x] Add the isolated SVN check to the configured OS/Python/locale CI matrix and the release workflow; require it in release-tree validation. Eight supplementary release-check/governance-document tests pass. All 200 previously frozen production files remain unchanged.
- [x] From committed source `577893d0ebdd099ad7e1310b180dd84dfdc4a52d`, rerun all six historical-tag gates (v0.3.1 through v0.5.1), the bilingual worked-project checker, and clean-source hygiene. Rebuild candidate ZIP/wheel/sdist through `git archive`; all three contain the same 200 normalized production inputs and 140 template assets, with local planning/test data excluded. Install the new wheel in a standard venv and pass both locale probes. These are local candidate artifacts, not published downloads. See [committed-source evidence](docs/qualification/v0.5.3-beta-committed-artifacts.json).
- [ ] Push the candidate and observe successful accepted-commit Windows/Linux, Python 3.10/3.14 CI. SSH host trust and HTTPS credentials are unavailable on this host; user login/configuration is pending.
- [ ] Run the authorized private Golden in independent copies once its local path is available; record actual applicability before publication.
- [ ] Close remaining applicable qualification gates before tagging or publishing. No release tag or public release has been created.

See [post-commit evidence](docs/qualification/v0.5.3-beta-post-commit.json). Earlier candidate and audit sections below are historical snapshots.

## v0.5.3-beta R2/R3 candidate qualification — 2026-10-21

R2/R3 implementations, final-source workflows, package installation and browser checks passed locally. See [qualification evidence](docs/qualification/v0.5.3-beta-release-candidate.json) and the [scope report](docs/release-readiness-v0.5.3-beta.zh-CN.md). This qualifies a candidate for commit and CI; it does not close unexecuted publication gates. This is an uncommitted local candidate; no tag, push or publication has occurred. Earlier sections below describe earlier source and are retained as history.

- [x] Runtime 1.1 increment audit context; immutable historical events and old-client write rejection.
- [x] Immutable template draft, independent human review and explicit publication; exact digest binding and bilingual diagnostics.
- [x] Controlled single-Owner conversion preserves old files; target QA can finish during work without releasing the Claim.
- [x] Failed writes and abrupt process exit recover without duplicate records; exact retry is idempotent.
- [x] Frozen-source general regressions: 349 passed; five long regression cases passed in this session (354 unique tests total), zero failures/errors/skips. Both final-source locales completed two full lifecycles and B1/B2, preserving prior bytes and exact increment context.
- [x] Candidate ZIP/wheel/sdist contents and private-data exclusion; six standard-venv locale/format probes. Chrome/Edge × both locales × file/HTTP: eight cases, 256 graph-toggle combinations, no page errors.
- [ ] Accepted commit, supported CI matrix and final release approval.

## v0.5.3-beta R1/R4 fixes — 2026-10-21

**R1 and R4 are closed locally. Publication remains blocked by R2/R3 and the
outstanding final-source qualification.** [Fix evidence](docs/qualification/v0.5.3-beta-gate-fixes.json)
records source hashes, test scope and compatibility limits. The earlier audit
below remains evidence for its historical source.

- [x] Bind new results to direct requirement/document inputs and accepted
  re-verification epochs. Reject old/preassessment proof, mismatched reuse and
  caller-stamped context. Explicit unaffected decisions and future out-of-scope
  candidates preserve their intended boundaries; reassessment and later versions
  cannot bypass an applicable outstanding epoch.
- [x] Gate preflight and current Dashboard coverage reject stale/unbound results;
  exact replay creates no new proof. Matching historical reuse remains possible
  after explicitly establishing the same current links and inputs.
- [x] Validate bilingual SR/AR parent cells against canonical requirements after
  expanding shared cells. Cover missing parents, wrong levels/versions/relations,
  missing context, explicit derived rows and missing controlled parent columns.
  Registered-document/Gate rejection leaves project facts unchanged.
- [x] Final broad regression: 339 tests in 212.391 seconds, zero failures/errors/
  skips, with the six changed runtime modules unchanged during the run. The
  governed baseline/reuse scenario passed separately in 280.032 seconds; an
  additional exact-replay case passed separately. These are 341 unique passing
  tests out of 344 currently discovered. The three legacy long simulations were
  not rerun after this fix; their earlier results are not final-source evidence.
- [x] Published v0.5.1 model adoption still passed with zero preview writes and
  prior facts/Runtime retained. The worked-project checker passed 16 documents,
  306 local links and 21 freshly executed software cases in both languages.
- [x] A temporary wheel contains the new validation module and updated registry
  Schema; its independent installed smoke rejects bad bilingual parent references.
  All 140 template assets/manifests retain their earlier digests. This wheel is a
  local fix candidate, not a publication artifact.
- [x] Skill validation, Python 3.10 grammar parsing (92 files) and diff checks
  passed. Grammar parsing does not establish Python 3.10 runtime coverage.
- [ ] Implement R2 increment audit context and R3 explicit template review/
  publication records. Their [design/test discussion](docs/release-readiness-v0.5.3-beta.zh-CN.md)
  also requires a controlled active-project path for early/private formats without
  managed parent columns. Old immutable history remains readable; protection
  must not be disabled to avoid a migration problem.
- [ ] Complete final accepted-source CI, B2, platform/backend, browser/install,
  private Golden and publication gates before declaring release readiness.

## v0.5.3-beta readiness audit — 2026-10-21 (before R1/R4 fixes)

**Publication is blocked.** See the [scope comparison and reproducible findings](docs/release-readiness-v0.5.3-beta.zh-CN.md).
This is a local candidate audit, not an accepted-commit or publication record.

- [x] Reproduced a requirement preflight defect through synthetic public fixtures:
  after an AR revision, marking every affected object `reverify` still lets old
  IR/SR results satisfy TR4 and the Gate requirement preflight. This is a defect
  finding, not a successful release gate; explicit approval remains separate.
- [x] Reproduced a separate reference-integrity gap without changing the example:
  replacing an SR register's parent `ir-01@1` with nonexistent `missing-ir@999`
  in memory still returns an empty lint diagnostic list. The normal project
  readiness path does not compare these parent cells with canonical facts.
- [x] Re-executed the bilingual worked-project checker: sixteen documents,
  3 IR / 6 SR / 12 AR, 306 local links and 21 fresh software cases passed.
- [x] Real historical-tag qualifications passed for v0.3.1, v0.3.2, v0.4.0,
  v0.4.1 and v0.5.0. Explicit v0.5.1 model adoption passed after making its
  synthetic project an independent Git repository, verifying before Claim,
  and creating work evidence after Claim. The migration retained prior facts
  and Runtime history, preview wrote zero files, and revision increased by one.
- [x] The unchanged Capability lifecycle passed on Windows/Python 3.12.14.
  A first general-suite attempt was interrupted after non-Git fixtures inherited
  the surrounding checkout. Those errors are not counted as product failures;
  repeat qualification uses an explicit Git search ceiling for the temporary root.
- [x] The corrected general-suite run passed 326/326 tests in 932.906 seconds,
  with zero failures, errors or skips. Together with the separately passed
  Capability lifecycle, all 327 existing tests passed locally. Full lifecycle
  used zh-CN; Capability used en; progressive refinement used the en default.
  This does not establish a complete bilingual simulation matrix. The additional
  R1/R4 negative probes reproduce gaps not covered by those existing tests.
- [x] A temporary candidate source copy passed release hygiene and built wheel
  and sdist with 36 active and 100 archived templates each, excluding local
  planning files. Installed-wheel bilingual template smoke passed. These are
  scoped candidate artifacts, built before the audit documentation and fixture
  correction; they are not final publication artifacts.
- [x] Skill validation passed. The local roadmap remains ignored.
- [x] Recorded local environment, input digests, scoped artifact hashes, upgrade
  results, test counts and negative-probe observations in the
  [machine-readable local audit](docs/qualification/v0.5.3-beta-local-audit.json).
  Ninety Python sources also parsed with the Python 3.10 grammar; this is not
  Python 3.10 runtime qualification.
- [ ] Close R1 re-verification enforcement, R2 increment event context, R3
  explicit template review/publication records and R4 register-parent reference
  validation; then run their independent cases.
- [ ] Complete a second governed increment through B2, template-upgrade/history
  cases, process-interruption recovery and the outstanding final-source matrix.
- [ ] Observe final-source endpoint/OS CI, real SVN, authorized private Golden,
  complete browser/install qualification, accepted commit and Tag gates.
  The worked-project checker must also become an explicit CI/release step.

## v0.5.3-beta worked-project checks — 2026-10-20

The room-booking case is a public synthetic teaching project, not a private
Golden or a record of human approval. These are scoped document and software
checks; the full release qualification remains outstanding.

- [x] Completed sixteen bilingual template instances with 3 IRs, 6 SRs and 12 ARs,
  plus bilingual source briefs, indexes and first-use reports. Every instance
  passes pinned template lint. The independent checker validates parent versions,
  all per-requirement rationale records, 306 local links, stage-snapshot boundaries,
  code symbols, source digests and fresh-versus-saved observations.
- [x] Executed 21 independent-expectation software cases: 12 AR, 6 SR and 3 IR
  automated scenarios. Saved evidence includes expected/actual values, execution
  environment/time and both source digests. Actual human acceptance remains
  not performed and governance approval remains not granted.
- [x] Twelve targeted template/requirement tests passed on Windows/Python 3.12.14,
  including historical pack 1.2.0. Stage 0.2.1 and register 1.1.1 guidance address
  unique rationale IDs, progressive metadata and immutable stage snapshots.
- [x] Actual Chrome preview traversed all 22 Markdown documents in both languages,
  checked 3/6/12-row registers and followed Chinese SR / English AR rationale links.
  Index and derivation screenshots were visually inspected.
- [x] Temporary wheel/sdist builds include 36 active and 100 archived templates;
  the sdist also contains the 22 worked-project Markdown files, software, evidence
  and checker. Installed-wheel active/historical pin smoke and copied-source
  walkthrough execution passed. Windows needed a short writable build/temp path
  after initial long-path/default-temp failures.
  Wheel SHA-256: `96e68207bcd7dc2b908d664d0ecfc7c79d9b53752036780c15246f25ac8d9732`.
  Sdist SHA-256: `ebce4467f441c7800616293f090f27bd08a8a6ab5e26cb1e9720cd163b506f01`.
- [x] Skill validation and release-tree hygiene passed; the local roadmap remains
  ignored and excluded from artifacts.
- [ ] Final accepted-source qualification and publication gates. No release was
  published and no CI, private Golden or production-readiness coverage is claimed.

## v0.5.3-beta stage drafting checks — 2026-10-20 (earlier source)

Stage documents are now 0.2.0 in pack 1.2.0. These are targeted document/resource
checks, not a completed release qualification. The earlier results below apply
to their historical sources.

- [x] Windows/Python 3.12.14: 12 targeted tests passed, covering template
  instantiation and lint, bilingual pack/schema parity, no-write preview,
  multi-requirement registers, tampering and both historical pack pins.
  The first fixture attempt could not create project directories in the sandbox's
  default temporary directory; the full targeted run passed using a designated
  writable validation directory instead.
- [x] Actual local Chrome rendered all eight updated stage drafts and checked
  version, chapter count and per-chapter guidance in both locales. Chinese TR2
  and TR3 derivation/consolidation screenshots were visually inspected.
- [x] The complete 1.1.0 pack is archived with its original bytes and digests;
  original 1.0.0 pins remain usable. Active register templates remain 1.1.0.
- [x] Skill validation, template digest/section consistency, local guide links and
  release-tree hygiene passed. The private roadmap remains ignored.
- [ ] Rebuild final publication artifacts and rerun remaining release gates from
  final accepted source. No new release or publication qualification is claimed.

## v0.5.3-beta template revision checks — 2026-10-18 (historical source)

This narrower revision changes the requirement registers and adds stage document
drafts. The results below do not complete the outstanding release matrix. The
2026-10-17 results qualify that earlier source only.

- [x] Windows/Python 3.12.14 and PyYAML 6.0.3: 52 targeted tests passed, covering
  requirement operations (excluding the long two-increment lifecycle), seven new
  table/pack tests, localization, release hygiene and governance documents.
  The register integration test creates one document covering two requirements.
  Table cases cover 1/2/12 rows in IR/SR/AR and both locales, shared spans, missing
  or duplicate exact references, malformed spans, merged identities, empty cells,
  changed headers and immutable old-pack resolution.
- [x] Actual local Chrome rendered all 14 revised bilingual drafts/registers;
  all six registers retained 11 columns, two independent identity rows and two
  correctly merged shared cells. Both locale screenshots were visually checked.
- [x] Temporary source copy built wheel and sdist with setuptools 84.0.0;
  both artifacts contain 36 active templates, 28 archived templates and the
  table checker, while excluding the private roadmap. Installed-wheel smoke
  checks passed for both locales and old/new pack resolution.
  Wheel SHA-256: `492b746a814e40d8dc5ea2eb4457e263a76e4bec3f18febb0b3f2c71eaf234c1`.
  Sdist SHA-256: `6bd4001ec24a8cab34105ad9161132ec2c97b1872fe1eac64cee4b02d76c6abe`.
- [x] Python 3.10 syntax parsing, manifest section/digest consistency, local guide
  links, Skill validation and source-tree hygiene passed. No release was published.
- [ ] Rebuild publication artifacts and complete the final-source release matrix
  after the discussion drafts and remaining implementation scope are accepted.

## v0.5.3-beta development qualification — 2026-10-17 (historical source)

This is an implementation candidate, not a publication record. Prior v0.5.1 results
below remain historical and do not qualify the new source.

- [x] Local Windows/Python 3.12.14: 292 legacy behavior tests and 22 requirement/template
  cases, including the six-phase MVP→baseline→next-increment scenario, passed.
  Targeted localization, multi-instance and Markdown/JSON-content checks were
  repeated after their final changes. PyYAML 6.0.3 was used.
- [x] Actual published v0.4.1 and v0.5.0 upgrades, plus explicit model adoption from
  a v0.5.1 project, passed without replaying init or dropping prior history.
- [x] Temporary isolated build environment with setuptools 84.0.0, wheel/sdist
  inspection, and two independent install environments passed. Both locales and
  all 28 template resources were checked; local planning files were excluded.
- [x] Actual local Chromium: English/Chinese requirement tree collapse/expand,
  combined filtering, reset and escaped requirement text passed without page errors.
- [x] Python syntax, schema parity, Skill validation and release-tree hygiene passed.
- [ ] Complete final-source long lifecycle, Capability and progressive-refinement matrix.
  Earlier development runs are not counted as final-source qualification.
- [ ] Supported Python 3.10/3.14 endpoints, Linux/Windows CI matrix and complete
  existing Dashboard browser regression. CI configuration is present; it has not
  been dispatched or observed green from this local task.
- [ ] Real isolated SVN source acceptance fixture; only the read-command contract
  was mocked locally because no SVN client was available. Git used real repositories.
- [ ] Authorized private Golden fixtures, remaining historical-tag gates and final
  publication artifact inspection. No private fixture path was supplied for this run.

Unexecuted, skipped or unavailable gates remain pending. No GitHub release, tag or
push is authorized by completing local implementation.

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
- [x] Publish only after the protected pull request, default-branch, Tag-test, and Tag-release workflows pass; then verify public assets and record immutable SHAs, hashes, workflow runs, and download-smoke results below.

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
public assets. At local qualification the working tree was uncommitted; protected PR/default-branch/Tag
workflows and public-download checks belong to the publication phase.

Publication preparation also makes the browser job a required dependency of
`governance-gate`. The release workflow waits for a successful test run of the
same release Tag before uploading public assets; workflow structure and narrow
read permissions were checked after this CI-only change.

## v0.5.1-beta publication record — 2026-10-09

- Release pull request: [#9](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/pull/9).
  Release commit: `9c21717e079edc4393d9dd207c70de1d7d3041a4`.
- Annotated Tag object: `a0c514807997a000cbc343eefb0325f4eca04a0e`;
  `v0.5.1-beta` resolves to the release commit above. Its file tree equals the
  qualified development commit `ef100996dc27f71e9765baca47bf81994a40abea`.
- Successful GitHub Actions runs: development branch
  [37916075849](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37916075849),
  pull request [37916107777](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37916107777),
  default branch [37916999994](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37916999994),
  Tag tests [37917844839](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37917844839),
  and Tag release [37917844831](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/actions/runs/37917844831).
  The browser job is part of the required `governance-gate`; public upload waits
  for this Tag's successful test run.
- The public [v0.5.1-beta prerelease](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill/releases/tag/v0.5.1-beta)
  exposes exactly one bilingual Skill ZIP, one wheel, one sdist and
  `SHA256SUMS.txt`. All downloaded payloads match both the published checksum
  file and GitHub's asset digests:
  - Skill ZIP: `201b2c4c60b1c293f110ccc46bb56473d79a8acd8e1d54e4befbd37073cabae5`.
  - Wheel: `5bc8b032f202749ecfd1f400fe6ad31653051db30ff6b1f5eeced06776b15564`.
  - Sdist: `a25798c1c60017ac7c1a19779e979235013147edfd4ce9eb4aef552397971e87`.
- Public-download qualification passed all 12 artifact/Python/locale
  combinations: Skill ZIP/wheel/sdist × Python 3.10/3.14 × `en`/`zh-CN`.
  Each installed package reports `ipdctl 0.5.1-beta`, loads all four Capability
  Policies, uses explicit test-fixture Owner bindings and baseline adoption,
  exercises review plus expired-Claim rendering/recovery, and finishes with
  passed validation/verification and the exact 16-file Dashboard. File navigation,
  relationship controls and canonical inline node identities are checked.
- Downloaded packages passed the private-project/output audit. Real-project
  Golden data, paths, logs and screenshots remain local outside Git and releases.
  Independent install projects and the public-download temporary root were
  removed after verification; the real project and installed personal Skill
  were not upgraded.
- This post-publication record changes documentation only; it does not move
  the published Tag or replace its assets.

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

## v0.5.1-beta publication checklist

- [x] Record the immutable release commit and annotated Tag object after publication.
- [x] Record the successful branch, pull-request, default-branch, Tag-test, and Tag-release workflow runs.
- [x] Confirm the public prerelease exposes exactly one bilingual Skill ZIP, one wheel, one sdist, and `SHA256SUMS.txt`, with matching payload hashes.
- [x] Record all twelve public artifact/Python/locale smoke results and removal of the temporary download root.

Completed identifiers, hashes and public-download results are recorded in the
dated v0.5.1-beta publication record above; historical records below remain intact.

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
