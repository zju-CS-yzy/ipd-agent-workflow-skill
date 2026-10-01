# IPD Agent Workflow Framework

[English](README.md) | [简体中文](README.zh-CN.md)

`v0.3.2-beta` combines one bilingual Codex Skill with a Python execution layer for evidence-backed Integrated Product Development (IPD). It generates a tailored process, controls deliverable and review state, renders project dashboards, and reconciles engineering changes with IPD facts. English and Simplified Chinese use the same code, schemas, policies, IDs, and state; machine contracts always remain English.

The runtime enforces a hard boundary: an AI agent can prepare and validate a gate, but final TR/DCP approval is valid only when an authorized human approval is recorded.

## Capabilities

- Generate Phase, TR, DCP, Gate, Activity, Deliverable, Dependency, and Review requirements from `task_profile.yaml`.
- Tailor for `software`, `hardware`, `embedded`, `robotics`, `ai_system`, and `material_change` work.
- Run one serialized Agent protocol: `context -> claim -> work -> close -> review -> human approve/reject -> refresh -> verify`.
- Enforce the eight-state deliverable lifecycle, dependency closure, evidence, review records, and authorized-human acceptance.
- Preserve every review decision while using the latest authorized human decision as the current outcome, allowing rejected work to be corrected, reviewed, and approved without erasing its history.
- Review Deliverable or Gate subjects explicitly and advance phases only after required governance checks pass.
- Generate an offline interactive Dashboard with hierarchical phase swimlanes,
  typed SVG process/dependency views, node details, Deliverable Matrix, Gate
  Matrix, and canonical JSON projections under `.ipd/dashboard/`.
- Present CLI and Dashboard text in `en` or `zh-CN` without changing YAML/JSON keys, IDs, statuses, relations, or graph topology.
- Inspect Git or SVN branch/revision/dirty/remote metadata and reconcile changed paths without mutating the repository.
- Enforce single-owner critical artifact bindings, per-iteration Claim windows, and explicitly authorized migration baselines for existing dirty projects.
- Persist YAML fact sources atomically and keep generated dashboards separate from source state.

This beta does not provide a hosted service, authenticated enterprise approval, or a writable web UI. It never commits, tags, pushes, pulls, fetches, updates, or otherwise mutates Git/SVN state.

## Quick start

Python 3.10 or newer is required. From this checkout:

```bash
git clone https://github.com/zju-CS-yzy/ipd-agent-workflow-skill.git
cd ipd-agent-workflow-skill
python -m pip install -e .
ipdctl init /path/to/project --name my-project --task-type software --locale en
ipdctl tailor /path/to/project
ipdctl context /path/to/project
ipdctl refresh /path/to/project
ipdctl verify /path/to/project
```

Without installation, run the same commands as `python -m ipdctl ...` from the repository root.

To make the Skill discoverable by Codex, place this checkout at `$CODEX_HOME/skills/ipd-agent-workflow-skill` (or the equivalent user Skill directory). Invoke it as `$ipd-agent-workflow-skill` or let normal Skill discovery select it for IPD-governed work.

## Governed execution

The runtime permits one active claim. A normal acceptance or rework iteration
must follow this order without skipping commands:

```bash
ipdctl claim DELIVERABLE --project-root /path/to/project
# perform the authorized work
ipdctl close DELIVERABLE --project-root /path/to/project --evidence evidence/DELIVERABLE/result.md
ipdctl review DELIVERABLE --project-root /path/to/project --reviewer REVIEWER
ipdctl approve DELIVERABLE --project-root /path/to/project --reviewer HUMAN --actor-type human --authorized --evidence evidence/DELIVERABLE/approval.md
ipdctl refresh /path/to/project
ipdctl verify /path/to/project
```

Use `reject` instead of `approve` to record a real authorized rejection. An
Agent may prepare a review, but may not impersonate the human making either
final decision. `close --status blocked` is the explicit aborted-work path; it
still requires `refresh` and `verify` before another claim. `context --json`
reports an orphaned `in_progress` deliverable in `recoverable_claims`; resume it
with `claim DELIVERABLE --recover`. An unexpired lease owned by another actor
cannot be taken over. For an expired v0.3.1 Claim that has no binding window,
record the exact authorized-human migration baseline first; its first recovery
creates an immutable migration window that later recoveries reuse.

`advance-phase` requires all current-Phase Gates to be approved and the latest
passed verification to match both the current state revision and the freshly
calculated verification-input fingerprint. It advances one Phase and leaves
the workflow at `refresh`; run `refresh` and `verify` again before claiming or
reviewing more work. A successful verification in the final `lifecycle` Phase,
with all its Gates approved, records one `lifecycle_complete` runtime event.
Within every Phase, canonical decisions are ordered TR then DCP; stale
hand-edited Gate pointers are rejected. The current Phase must also match its
ordered `advance_phase` event history, so editing all Phase pointers together
cannot skip governance.

The full CLI command surface is `init`, `tailor`, `context`, `status`, `adopt-baseline`, `claim`,
`close`, `review`, `approve`, `reject`, `refresh`, `verify`, `advance-phase`,
`repository`, `reconcile`, and `validate`. Run `ipdctl COMMAND --help` for the
exact options; the normative summary is in
[references/state-contract.md](references/state-contract.md).

## Language contract

Initialize a Simplified Chinese project with `--locale zh-CN`. The choice is stored in `.ipd/task_profile.yaml`:

```yaml
presentation:
  locale: zh-CN
```

Before initialization, the Skill follows the user's conversation language. After initialization, user-facing CLI and generated Dashboard text follow `presentation.locale`. Older v0.2 profiles without this field remain valid, use English, and are not rewritten automatically.

Commands, parameters, filenames, IDs, YAML/JSON keys, schema paths, status values such as `in_progress`, and relations such as `depends_on` stay English. User-supplied names, evidence, paths, and descriptions are preserved as entered. JSON output remains a stable machine contract.

To switch only the presentation language of an existing project, edit `presentation.locale`, then run `ipdctl refresh` and `ipdctl verify`. Do not re-run `tailor` merely to change language; workflow facts, reviews, evidence, claims, and state history must remain unchanged.

## Project contract

The authoritative files are `.ipd/task_profile.yaml`, `.ipd/tailored_process.yaml`, `.ipd/project_state.yaml`, `.ipd/agent_runtime.yaml`, and `.ipd/artifact_bindings.yaml`. `.ipd/dashboard/`, reconciliation reports, and verification reports are derived views.

Each `tailor` run preserves user-authored artifact rules and regenerates one
framework-managed `evidence/<deliverable-id>/**` binding per tailored
deliverable. This binds durable evidence, not the implementation itself. Add
explicit user-authored bindings for real `src/**`, `tests/**`, documentation,
configuration, firmware, hardware, and tool paths; ownership is never inferred,
and unbound changes under critical roots fail verification. An actually changed
critical path may resolve to only one Deliverable owner. New Claim events record
an exact binding window; an old historical Claim is not permanent ownership
evidence for later changes.

When upgrading an existing project whose governed files are already dirty,
first validate explicit single-owner rules, then preview and record an
authorized-human migration baseline with `ipdctl adopt-baseline`. The baseline
stores exact path hashes in append-only runtime history; it creates no Claim and
does not modify Git/SVN. If governed files change before a legacy Claim is
recovered, an authorized human may adopt the newly reviewed exact baseline;
stale adoptions remain history but do not block the later matching record. A
successful verification carries the exact artifact baseline into the next
iteration.

Mutating CLI commands serialize the complete read, preflight, compute, and
write cycle with a project-local recovery journal. Concurrent mutations fail
explicitly and may be retried; an interrupted multi-file command is restored
before the next command reads project facts.

The Dashboard entry point is `.ipd/dashboard/index.html`. Its standalone assets
live under `assets/`, phase views under `phases/`, matrices under `matrices/`,
and machine-readable projections under `data/`. `manifest.json` records the
locale, binding/eligibility hashes, and hashes every managed output so
`ipdctl verify` can detect stale or modified views.

The structural contracts live in [schemas/](schemas/). Runtime validation additionally enforces dependency cycles, referential integrity, legal transitions, review authority, evidence presence, dashboard freshness, and repository reconciliation.

The non-negotiable policy remains at [policies/default/tailoring_rules.yaml](policies/default/tailoring_rules.yaml). Generic task-type policies are under [policies/task-types/](policies/task-types/) and are included in installed distributions.

Never place tokens, passwords, private keys, or private review content in project state. Evidence entries should be repository-relative paths, immutable revision references, or approved external record identifiers.

## Repository layout

```text
SKILL.md                         Skill entry point
agents/openai.yaml               Codex UI metadata
references/                      Conditional Skill guidance
AGENT_RUNTIME_PROTOCOL.md        Agent execution and authority contract
ipdctl/                          Runtime modules and bundled messages.yaml catalog
schemas/                         Profile, process, state, and runtime contracts
policies/default/                Non-negotiable governance policy
policies/task-types/             Generic task-type tailoring policies
templates/project/               Project scaffold reference
templates/hooks/                 Optional, non-installing verification guards
scripts/release_check.py         Release hygiene and secret-pattern audit
tests/                           Standard-library behavior tests
docs/                            English and Simplified Chinese guidance
RELEASE_CHECKLIST.md             Publication and simulation gate
```

## Verification

```bash
python -B -m compileall -q ipdctl tests scripts
python -B -m unittest discover -s tests -v
python -B -m ipdctl --help
python -B scripts/release_check.py .
```

See [docs/architecture.md](docs/architecture.md) for module boundaries, [docs/deployment.md](docs/deployment.md) for installation and release verification, and [CONTRIBUTING.md](CONTRIBUTING.md) before changing a contract. Simplified Chinese guidance starts at [README.zh-CN.md](README.zh-CN.md).

## Status and license

The state schema and Python API may still change before `1.0`. Changes are recorded in [CHANGELOG.md](CHANGELOG.md). Security reports should follow [SECURITY.md](SECURITY.md).

Licensed under Apache-2.0. See [LICENSE](LICENSE).

Canonical repository: [github.com/zju-CS-yzy/ipd-agent-workflow-skill](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill)
