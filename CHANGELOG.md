# Changelog

This project follows Keep a Changelog conventions and uses PEP 440 package versions. The public label `v0.3.2-beta` maps to package version `0.3.2b1`.

## [Unreleased]

## [0.3.2b1] - 2026-10-02

### Added

- Added a portable artifact-binding schema plus semantic validation for unique
  rules, safe project-relative patterns, known Deliverable owners, and actual
  critical-path ownership conflicts.
- Added one shared binding-eligibility projection for context, Claim preflight,
  reconciliation, Dashboard actionability, refresh, and verification.
- Added an explicitly human-authorized, append-only `adopt-baseline` migration
  path for already-dirty files in existing projects.
- Added Claim binding windows and exact post-verification artifact baselines so
  path ownership is limited to the current iteration without requiring the
  framework to create commits.
- Added a project-local recovery transaction spanning each mutating command's
  complete read, preflight, compute, and write cycle, including bootstrap and
  force initialization.

### Changed

- Legacy Claim events remain readable audit history but no longer permanently
  authorize future repository changes.
- Binding blockers now remove affected work from `available_tasks` and appear
  consistently in CLI context, Dashboard data, reconciliation, and verification.
- Dashboard manifest freshness now covers binding and eligibility projections.
- Dashboard verification now rejects altered Manifest 2.1 identity, source,
  file-list, output-directory, and view-routing fields before regenerating it.
- Expired v0.3.1 windowless Claims may be recovered only after an exact,
  authorized-human baseline adoption. The resulting immutable migration window
  is retained across later lease recovery instead of reopening on a dirty tree.
- Concurrent mutations fail explicitly instead of applying stale computed
  state. A crash-released cross-process mutex serializes recovery and command
  execution; the canonical journal lock is acquired before snapshots are
  taken, interrupted multi-file writes recover on the next command, and an
  owner whose liveness cannot be proven is treated as active rather than rolled
  back.
- Legacy windowless Claim recovery skips stale baseline-adoption records and
  accepts only a later authorized adoption that exactly matches the current
  revision, bindings, repository revision, and governed path snapshot.

### Compatibility

- v0.3.1 projects upgrade in place without reinitialization or re-tailoring.
  Projects with pre-existing dirty critical files need one reviewed baseline
  adoption after their explicit single-owner bindings validate.
- This maintenance release retains the single-Claim lifecycle and does not add
  capability patterns, process overlays, compound Claims, or domain policies.

## [0.3.1b1] - 2026-10-01

### Fixed

- Render `depends_on` edges in execution order from prerequisite to dependent
  while preserving the canonical machine contract where the dependent is the
  edge source and the prerequisite is the edge target.
- Restrict the Deliverable dependency view and its topology calculation to
  `depends_on`; traceability relations such as `supports`, `verifies`, and
  `supersedes` no longer distort execution order.
- Separate explicit lifecycle `blocked` state from dependency readiness so a
  planned Deliverable waiting on prerequisites is no longer presented as a
  red blocked item.

### Changed

- Added explicit SVG relation direction metadata, localized dependency-reading
  guidance, and regression coverage for dependency direction, filtering,
  readiness, and deterministic layout.
- Added clean bilingual smoke testing of the Skill source ZIP to the automated
  GitHub prerelease pipeline in addition to wheel and sdist verification.

### Compatibility

- Workflow facts, schemas, IDs, lifecycle state, and canonical graph edge
  semantics are unchanged from `0.3.0b1`. Existing projects do not need to be
  re-tailored; run `ipdctl refresh` followed by `ipdctl verify` after upgrading.

## [0.3.0b1] - 2026-09-30

### Added

- One bundled `messages.yaml` catalog and locale-aware runtime presentation for
  English (`en`) and Simplified Chinese (`zh-CN`).
- `init --locale`, persisted as `task_profile.presentation.locale`, with
  backward-compatible English behavior for v0.2 profiles that omit it.
- Simplified Chinese README, architecture, and deployment guidance.
- Locale-aware CLI, HTML, SVG, matrix, report, freshness, package, and Golden
  tests while preserving English machine contracts.
- Explicit Deliverable/Gate review subjects, latest-authorized-human-decision
  resolution with full review history, and governed phase advancement.
- Strict single-claim Agent iterations, expired-claim recovery, verification
  fingerprints, canonical TR/DCP/Gate pointers, and one-time lifecycle completion
  records.
- Fail-closed Gate ordering, pointer and Phase-transition-history validation,
  plus Claim provenance that requires Actor, timestamp, and a non-future
  project state revision.
- Managed Deliverable evidence bindings with explicit source/test path binding for
  repository reconciliation.

### Changed

- Versioned the single bilingual Skill and Python distribution as
  `v0.3.0-beta` / `0.3.0b1`; no locale-specific code packages are published.
- Restored the Dashboard rendering pipeline with a canonical nested output
  tree, deterministic hierarchical SVGs, phase swimlanes, typed workflow nodes,
  relation-specific edges, interactive details, searchable matrices, and
  output-derived v1.4 Golden testing.
- Dashboard refresh now atomically replaces its managed output tree and
  verification enforces the required files and manifest boundary.
- Dashboard manifests now record locale, and changing presentation language
  invalidates only generated views rather than workflow facts.
- Phase advancement now requires a fresh successful verification and starts the
  next phase at `refresh`; rejected work cannot skip the refresh/verify loop.
- Common lifecycle failures are fully localized in Chinese while IDs, phases,
  statuses, commands, and machine reports remain English.

## [0.2.0b1] - 2026-09-29

### Added

- Deterministic IPD Tailor Engine for software, hardware, embedded, robotics, AI-system, and material-change task profiles.
- Versioned task-profile, tailored-process, project-state, and Agent Runtime contracts.
- Full lifecycle CLI: `init`, `tailor`, `context`, `claim`, `close`, `review`, `approve`, `reject`, `refresh`, `verify`, `repository`, and `reconcile`.
- Deliverable state machine with dependency, evidence, review-record, and authorized-human approval enforcement.
- Self-contained HTML, JSON, and Markdown dashboards for process, dependency, deliverable, and gate views.
- Read-only Git/SVN metadata inspection, artifact reconciliation, project scaffolding, and optional hook templates.
- Agent Runtime protocol and tests covering the complete temporary-project workflow.

### Changed

- Canonical project state is now `.ipd/project_state.yaml`; the v0.1 JSON path remains readable for compatibility.
- The package is positioned as a reusable IPD Agent Workflow Framework rather than a project-specific example.

### Excluded

- v1.4 project instances, robotics data, generated dashboards, screenshots, test reports, and platform-specific CI examples.

## [0.1.0a1] - 2026-09-29

### Added

- Valid Codex Skill entry point, UI metadata, and progressive workflow references.
- Dependency-free `ipdctl` CLI with state initialization, validation, summaries, and read-only Git/SVN inspection.
- Atomic state persistence, canonical workflow transitions, dependency-cycle checks, traceability validation, and evidence-backed closure.
- Enforced authorized-human approval for final TR/DCP gates.
- Versioned project-state and tailoring-policy schemas plus a safe default policy.
- Behavior tests, GitHub Actions CI, and a release hygiene scanner.
- Architecture, deployment, contribution, security, and GitHub release guidance.

### Removed

- Non-functional CLI and documentation scaffolds.
