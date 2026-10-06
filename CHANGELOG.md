# Changelog

This project follows Keep a Changelog conventions and uses PEP 440 package versions. The public label `v0.5.0-beta` maps to package version `0.5.0b1`.

## [Unreleased]

## [0.5.0b1] - 2026-10-06

### Added

- Expanded the explicit opt-in Capability Catalog with domain-neutral module
  decomposition and verification, interface contract and integration, and
  release and lifecycle assurance policies. Each policy contributes governed
  Activities, Deliverables, typed trace relations, checkpoint criteria, and
  capability provenance without embedding project-instance data.
- Added a policy-owned progressive-refinement root for the module
  implementation baseline. Once the approved decomposition satisfies its
  trigger, a reviewed `ipdctl refine` plan materializes concrete project-owned
  module Deliverables while retaining structural lineage and rewriting
  downstream execution dependencies to concrete leaves.
- Added explicit `waiting_items`, `explicit_blockers`, and
  `governance_blockers` projections to context and Dashboard machine data while
  retaining the deduplicated, Deliverable-scoped `blocked_items` compatibility
  field.

### Changed

- Capability policy discovery now validates every registry asset in source,
  wheel, and sdist installations and fails closed on a partial catalog.
- Capability policies use stricter identifier, activity-reference, dependency,
  criterion, and refinement-trigger validation. Catalog order is canonical, so
  equivalent selections compile byte-for-byte identically.
- Dashboard and CLI summaries now distinguish work waiting on prerequisites
  from lifecycle-blocked work and governance failures; the same shared
  classifier drives both projections.
- Bilingual workflow resources and documentation now cover every built-in
  capability. Only `depends_on` participates in readiness and execution order;
  `supports`, `verifies`, and `supersedes` remain trace semantics.

### Compatibility

- Capability selection remains opt-in. A v0.4.1 profile with no
  `capability_patterns` field and one with `capability_patterns: []` compile to
  the same process.
- Existing v0.4.1 projects remain readable without rerunning `init`; enabling a
  new capability is a reviewed re-tailoring decision, not an automatic upgrade.
- Process and capability schema versions remain unchanged; the single-Claim
  lifecycle, authorized-human approval boundary, and read-only Git/SVN
  integration remain intact.

## [0.4.1b1] - 2026-10-06

### Added

- Added project-owned generic Gates, explicit one-to-one
  `gate_migrations`, and exact same-ID `dependency_corrections` to the process
  extension, compiled process, schema, and runtime audit contracts.
- Added stable machine-readable `ipdctl validate --json` output for valid,
  invalid, policy-invalid, and malformed state inputs.

### Fixed

- Re-tailoring now preserves state-owned Claim traceability whenever both
  endpoints survive. Preview exposes `state.traceability` additions, removals,
  and redirects through its existing five keys and fails closed before an
  unexplained Claim-linked relationship can disappear.
- Authorized dependency correction now requires exact `before` and `after`
  sets, preserves evidence and review history, blocks the corrected work for
  reapproval, invalidates affected unapproved Gate readiness, and rejects an
  implicit rewrite of an approved Gate.
- Artifact-binding globs are now project-root anchored: a bare filename no
  longer matches an arbitrary nested file, `*` does not cross directories, and
  a complete `**` segment supplies recursive matching on both POSIX and Windows
  paths.
- The Windows CLI configures real standard streams for UTF-8 so Chinese output
  remains intact when redirected or captured.

### Compatibility

- v0.4.0 projects upgrade in place without rerunning `init`. Existing state,
  Claim links, evidence, reviews, process/refinement history, and Dashboard
  sources remain readable.
- A normal additive re-tailor remains authorization-free. Only a first
  effective Deliverable, Gate, or dependency-correction migration requires
  `--apply-migrations` with an identified authorized human Actor and reason.
- The serialized single-Claim model, authorized-human final approval boundary,
  public schemas, and read-only Git/SVN behavior remain unchanged.

## [0.4.0b1] - 2026-10-05

### Added

- Added deterministic four-layer process compilation in the order
  `core -> task_type -> capability -> project`, with explicit
  `capability_patterns` and a constrained `.ipd/process_extensions.yaml`.
- Added the reusable `sourced_component_integration` capability for candidate
  validation, an authorized selection decision, and a controlled integration
  baseline without embedding project, supplier, or robotics instance data.
- Added node provenance, phase-derived maturity, independent TR/DCP criteria,
  and phase-monotonic dependency validation to the process, state, and
  Dashboard contracts.
- Added `tailor --preview`, explicit replace/split migration mappings, and
  authorized-human process-migration audit events.
- Added explicit artifact-binding roles for the single Claim-authorizing
  `owner` and non-critical multi-Deliverable `shared_evidence`.
- Added the human-reviewable Progressive Refinement Kernel: declared triggers,
  fingerprinted `expand` plans, zero-write preview, authorized apply, replay-safe
  runtime events, structural `refines` lineage, and recursive concrete leaf
  closure.
- Added Gate requirement fingerprints and review epochs so a changed refined
  leaf set preserves evidence but invalidates the old approval.
- Added refinement and Binding impact to context, Dashboard projections,
  interactive details, graphs, and matrices; refined concrete children require
  explicit user-authored Owner bindings before Claim.

### Changed

- Re-tailoring now fails while a Claim is active and fails closed when governed
  history would be removed without a complete migration mapping.
- Ordinary re-tailoring now rejects in-place semantic rewrites of a
  Deliverable with governed lifecycle history and rejects changes targeting a
  Phase with an approved Gate or an already closed Phase, including TR/DCP
  criteria. Zero-write preview remains available; deterministic schema `1.0`
  core metadata and canonical readiness-criteria enrichment is the only
  compatibility exception.
- Migrated historical Deliverables remain as `superseded` state records with
  their evidence and review history; replacement Deliverables start at
  `planned` and never inherit acceptance or evidence automatically.
- Dashboard node details now expose provenance, maturity, TR/DCP criteria, and
  replacement targets while preserving bilingual interactive JavaScript.
- Verification fingerprints now include project process extensions and verify
  the tailored process against all four source layers, including applied
  refinement history.
- `ipdctl refine` now defaults to a deterministic preview; applying a new plan
  is blocked by an active Claim, pending trigger, closed Phase, stale process
  fingerprint, or missing human authorization.
- Refinement triggers must be reachable before the governed root Gate;
  placeholder children must carry their next executable requirement, and only
  Deliverables may own refinement requirements.
- Applied and currently due refinement lineage is protected from ordinary
  re-tailoring. Refinement preview, apply, and replay fail closed when source
  inputs or Agent runtime provenance diverge from the governed process.
- Nested refinement roots remain leaves until a later authorized Plan;
  downstream Claims wait for prerequisite refinement, and plans cannot reuse
  historical Deliverable IDs or rewrite dependencies of governed history.
- Every concrete refined child requires an explicit user-authored Owner;
  placeholder and abstract nodes remain structural and do not require one.
- Applied refinement records now bind the exact result process fingerprint and
  invalidated Gate set to the strict authorized runtime event; malformed
  digests or field-level runtime tampering fail consistency and replay checks.

### Compatibility

- v0.3.2 projects and legacy process schema `1.0` remain readable before
  re-tailoring. The qualified in-place upgrade preserves accepted state,
  evidence, and review records.
- Capability enablement may add framework-managed evidence bindings. The
  changed binding contract remains fail-closed until an authorized human
  reviews and adopts the replacement artifact baseline.
- The serialized single-Claim execution model and authorized-human final
  approval boundary remain unchanged.

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
