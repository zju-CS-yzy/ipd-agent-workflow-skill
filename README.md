# IPD Agent Workflow Framework

[English](README.md) | [简体中文](README.zh-CN.md)

This repository combines one bilingual Codex Skill with a Python execution layer for evidence-backed Integrated Product Development (IPD). It generates a layered tailored process, controls deliverable and review state, renders project dashboards, and reconciles engineering changes with IPD facts. English and Simplified Chinese use the same code, schemas, policies, IDs, and state; machine contracts always remain English.

Current prerelease target: `v0.4.1-beta` (Python package `0.4.1b1`).

The runtime enforces a hard boundary: an AI agent can prepare and validate a gate, but final TR/DCP approval is valid only when an authorized human approval is recorded.

## Capabilities

- Generate Phase, TR, DCP, Gate, Activity, Deliverable, Dependency, and Review requirements from `task_profile.yaml`.
- Tailor for `software`, `hardware`, `embedded`, `robotics`, `ai_system`, and `material_change` work.
- Compile deterministic process facts in the fixed order `core -> task_type -> capability -> project`, with reusable `capability_patterns` and additive project extensions.
- Progressively refine a reviewed project Deliverable into explicit Activities and child Deliverables, including explicit placeholder intermediates for later refinement, without discarding parent history or inferring a project decomposition.
- Record node `provenance`, phase-derived `maturity`, independent TR/DCP criteria, and phase-monotonic dependencies.
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
- Distinguish the one Binding Owner that authorizes a Claim from non-critical `shared_evidence` references that may support several Deliverables.
- Preserve Claim traceability across re-tailoring, expose trace additions,
  removals, and redirects in preview, and fail closed before an unexplained
  Claim link can disappear.
- Support explicit migration from legacy generic Gates to canonical or
  project-owned Gates, plus authorized exact dependency corrections that
  preserve history and require affected work to be reviewed again.
- Persist YAML fact sources atomically and keep generated dashboards separate from source state.

This beta does not provide a hosted service, authenticated enterprise approval, or a writable web UI. It never commits, tags, pushes, pulls, fetches, updates, or otherwise mutates Git/SVN state.

## Quick start

Python 3.10 or newer is required. From this checkout:

```bash
git clone https://github.com/zju-CS-yzy/ipd-agent-workflow-skill.git
cd ipd-agent-workflow-skill
python -m pip install -e .
ipdctl init /path/to/project --name my-project --task-type software --locale en
ipdctl tailor /path/to/project --preview
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

The full CLI command surface is `init`, `tailor`, `refine`, `context`, `status`, `adopt-baseline`, `claim`,
`close`, `review`, `approve`, `reject`, `refresh`, `verify`, `advance-phase`,
`repository`, `reconcile`, and `validate`. `validate --json` emits a stable
machine-readable result while normal CLI and Dashboard presentation remains
locale-aware. Run `ipdctl COMMAND --help` for the exact options; the normative summary is in
[references/state-contract.md](references/state-contract.md).

## Layered process compilation

`task_profile.yaml` selects task types and optional reusable capabilities. For
example, this enables the generic three-stage sourced-component flow—candidate
validation, selection decision, and integration baseline—without embedding a
vendor, robot, sensor, repository path, or Owner assumption:

```yaml
capability_patterns:
  - sourced_component_integration
```

`ipdctl init` creates an empty canonical `.ipd/process_extensions.yaml` as the
project-owned fourth layer. It may add Activities, review-required Deliverables, typed relations
(`depends_on`, `supports`, `verifies`, `supersedes`), independent TR/DCP
criteria, project-owned generic Gates, explicit `replace` or `split`
Deliverable migration mappings, one-to-one `gate_migrations`, and exact
`dependency_corrections`. It cannot
delete or override facts from earlier layers. Duplicate IDs, dependency
cycles, unknown references, and an earlier-Phase Deliverable depending on a
later-Phase Deliverable fail validation.
For a pre-v0.4 project that does not yet have this file, `tailor --preview`
remains zero-write and the first successful actual `tailor` materializes the
canonical empty extension before publishing the schema `2.0` process.

Run `ipdctl tailor PATH --preview` before re-tailoring. Preview is read-only;
`--preview --json` returns the stable keys `added`, `removed`, `changed`,
`migrations`, and `ambiguous`. An active Claim blocks every actual re-tailor.
The same preview reports additions, removals, and redirects in
`state.traceability`; losing a Claim-linked relationship without a complete
migration is an `ambiguous` blocker. Process-owned relations are rebuilt from
the compiled process, while Claim-linked relations survive whenever both
endpoints still exist.
If a change removes a historical, non-superseded Deliverable, the project
extension must provide an explicit mapping and the first application requires
an explicitly authorized human command:

```bash
ipdctl tailor PATH --apply-migrations --actor HUMAN \
  --actor-type human --authorized --reason TEXT
```

The old state node remains as `superseded` with its evidence and review
history; new target nodes remain `planned` and do not inherit acceptance,
evidence, or reviews. Additive and already-applied changes stay idempotent and
do not require repeated authorization.

A legacy generic Gate may move only through a one-to-one `gate_migrations`
record whose target exists in the candidate process and whose history is
preserved. A same-ID dependency correction for a historical Deliverable must
declare the exact `before` and `after` sets, preserve history, and require
reapproval. Its first effective application uses the same authorized-human
`--apply-migrations` boundary, moves the affected work to `blocked`, invalidates
affected unapproved Gate readiness, and keeps all evidence and reviews. An
approved affected Gate fails closed instead of being reopened implicitly.

Ordinary re-tailoring cannot change the process meaning of an existing
Deliverable that already has governed status, evidence, or reviews while
retaining the same ID. Introduce a new Deliverable ID and use the explicit
migration path instead. Changes that target a Phase with an approved Gate or an
already closed Phase—including TR/DCP criteria—also fail closed; the preview
remains available for review and no authority file is changed. A legacy schema
`1.0` process is allowed only the deterministic core provenance, maturity, and
canonical readiness-criteria enrichment required by schema `2.0`.

Newly compiled process files use schema `2.0`. The runtime can still read a
schema `1.0` tailored process when its semantic projection matches a profile
without capabilities and an empty project extension. Before enabling a
capability or adding extension content, preview and re-tailor the process.

## Progressive refinement

Projects may declare a `refinement_requirements` entry in
`.ipd/process_extensions.yaml` for a known Deliverable. The declaration fixes
the root, its initial `definition_state`, an explicit trigger, and the
`all_children_accepted` completion policy. No task-type policy guesses the
project's modules or functions: an Agent prepares a separate reviewed plan only
after project evidence makes the requirement `due`.

Only Deliverables may be refinement requirement roots. Trigger subjects must
be reachable before the root's Gate: an accepted Deliverable may not be in a
later Phase, and an approved Gate must be in an earlier Phase. A plan may add
concrete children and explicit `placeholder` intermediates; every placeholder
must declare its own executable refinement requirement and trigger. A
placeholder cannot trigger itself or use a Deliverable that depends on that
placeholder. A nested refinement root must remain a leaf in the current Plan;
its descendants require a later, separately authorized Plan.

```bash
ipdctl context PATH --json
ipdctl refine PATH --plan refinement-plan.yaml --preview --json
ipdctl refine PATH --plan refinement-plan.yaml --apply \
  --actor HUMAN --actor-type human --authorized --reason TEXT
ipdctl refresh PATH
ipdctl verify PATH
```

A plan uses `mode: expand` and the exact `process_fingerprint` returned by
`context`. Preview is deterministic and writes nothing. Apply is blocked by an
active Claim, a pending trigger, a stale base fingerprint, or a root outside
the current Phase. It appends the new nodes to the project extension, changes
the root into an abstract aggregate, creates child Deliverables as `planned`
with empty evidence and review history, and records one authorized
`process_refinement_applied` event. Replaying the same plan is a no-op; reusing
its ID with changed content is a conflict.

The applied or currently due refinement lineage is protected from ordinary
`tailor`. In this Beta, changes to that lineage—including migration—must use a
new reviewed `refine` plan; direct extension edits fail closed. `refine` also
proves that the current profile and extension still compile to the governed
process and that replay history matches the Agent runtime event.

A Deliverable whose transitive prerequisite still has a `pending` or `due`
refinement cannot be claimed and reports `REFINEMENT_DEPENDENCY_REQUIRED`.
Plans cannot reuse a historical Deliverable ID or rewrite dependencies of an
existing Deliverable that already has governed lifecycle history.

`refines` represents structural ancestry and never becomes an execution
prerequisite. Only `depends_on` controls execution order. Gates evaluate the
concrete leaf closure of an abstract root. If that closure changes, prior Gate
evidence remains audit history, but the approval is invalidated and a new
review epoch is required. Every new concrete child requires an explicit
user-authored Owner binding before it can be claimed. Placeholder and abstract
nodes are structural and do not require an artifact Owner until a later Plan
materializes concrete children; managed evidence bindings and parent bindings
are never silently reassigned.

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

The authoritative files are `.ipd/task_profile.yaml`, `.ipd/process_extensions.yaml`, `.ipd/tailored_process.yaml`, `.ipd/project_state.yaml`, `.ipd/agent_runtime.yaml`, and `.ipd/artifact_bindings.yaml`. `.ipd/dashboard/`, reconciliation reports, and verification reports are derived views.

Each `tailor` run preserves user-authored artifact rules and regenerates one
framework-managed `evidence/<deliverable-id>/**` binding per tailored
deliverable. This binds durable evidence, not the implementation itself. Add
explicit user-authored bindings for real `src/**`, `tests/**`, documentation,
configuration, firmware, hardware, and tool paths; ownership is never inferred,
and unbound changes under critical roots fail verification. An actually changed
critical path may resolve to only one Deliverable owner. New Claim events record
an exact binding window; an old historical Claim is not permanent ownership
evidence for later changes.

A Binding with no `role`, or with `role: owner`, preserves the single-owner
contract and uses one `deliverable`. `role: shared_evidence` instead uses a
`deliverables` list and must set `critical: false`; it records supporting
evidence relationships only. Shared evidence cannot authorize a Claim, cannot
satisfy the Owner required for a critical path, and does not weaken owner
conflict checks.

Artifact-binding globs are rooted at the project root. For example,
`README.md` matches only the root file, `docs/*.md` matches one directory
level, and a full `**` path segment may cross zero or more directories.

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

The non-negotiable policy remains at [policies/default/tailoring_rules.yaml](policies/default/tailoring_rules.yaml). Generic task-type policies are under [policies/task-types/](policies/task-types/), reusable capability policies are under [policies/capabilities/](policies/capabilities/), and both are included in installed distributions.

Never place tokens, passwords, private keys, or private review content in project state. Evidence entries should be repository-relative paths, immutable revision references, or approved external record identifiers.

## Repository layout

```text
SKILL.md                         Skill entry point
agents/openai.yaml               Codex UI metadata
references/                      Conditional Skill guidance
AGENT_RUNTIME_PROTOCOL.md        Agent execution and authority contract
ipdctl/                          Runtime modules and bundled messages.yaml catalog
schemas/                         Profile, process, refinement, state, and runtime contracts
policies/default/                Non-negotiable governance policy
policies/task-types/             Generic task-type tailoring policies
policies/capabilities/           Reusable capability policies
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
python -B scripts/simulate_progressive_refinement.py --json
python -B -m ipdctl --help
python -B scripts/release_check.py .
```

See [docs/architecture.md](docs/architecture.md) for module boundaries, [docs/deployment.md](docs/deployment.md) for installation and release verification, and [CONTRIBUTING.md](CONTRIBUTING.md) before changing a contract. Simplified Chinese guidance starts at [README.zh-CN.md](README.zh-CN.md).

## Status and license

The state schema and Python API may still change before `1.0`. Changes are recorded in [CHANGELOG.md](CHANGELOG.md). Security reports should follow [SECURITY.md](SECURITY.md).

Licensed under Apache-2.0. See [LICENSE](LICENSE).

Canonical repository: [github.com/zju-CS-yzy/ipd-agent-workflow-skill](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill)
