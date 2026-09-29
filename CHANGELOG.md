# Changelog

This project follows Keep a Changelog conventions and uses PEP 440 package versions. The public label `v0.2.0-beta` maps to package version `0.2.0b1`.

## [Unreleased]

No changes yet.

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
