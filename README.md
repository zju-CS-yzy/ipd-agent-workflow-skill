# IPD Agent Workflow Framework

`v0.2.0-beta` combines a Codex Skill with a Python execution layer for evidence-backed Integrated Product Development (IPD). It generates a tailored process, controls deliverable and review state, renders project dashboards, and reconciles engineering changes with IPD facts.

The runtime enforces a hard boundary: an AI agent can prepare and validate a gate, but final TR/DCP approval is valid only when an authorized human approval is recorded.

## Capabilities

- Generate Phase, TR, DCP, Gate, Activity, Deliverable, Dependency, and Review requirements from `task_profile.yaml`.
- Tailor for `software`, `hardware`, `embedded`, `robotics`, `ai_system`, and `material_change` work.
- Run the Agent protocol `context -> claim -> work -> close -> review -> refresh -> verify`.
- Enforce the eight-state deliverable lifecycle, dependency closure, evidence, review records, and authorized-human acceptance.
- Generate process, dependency, Deliverable Matrix, and Gate Matrix views as HTML, JSON, and Markdown under `.ipd/dashboard/`.
- Inspect Git or SVN branch/revision/dirty/remote metadata and reconcile changed paths without mutating the repository.
- Persist YAML fact sources atomically and keep generated dashboards separate from source state.

This beta does not provide a hosted service, authenticated enterprise approval, or a writable web UI. It never commits, tags, pushes, pulls, fetches, updates, or otherwise mutates Git/SVN state.

## Quick start

Python 3.10 or newer is required. From this checkout:

```bash
git clone https://github.com/zju-CS-yzy/ipd-agent-workflow-skill.git
cd ipd-agent-workflow-skill
python -m pip install -e .
ipdctl init /path/to/project --name my-project --task-type software
ipdctl tailor /path/to/project
ipdctl context /path/to/project
ipdctl refresh /path/to/project
ipdctl verify /path/to/project
```

Without installation, run the same commands as `python -m ipdctl ...` from the repository root.

To make the Skill discoverable by Codex, place this checkout at `$CODEX_HOME/skills/ipd-agent-workflow-skill` (or the equivalent user Skill directory). Invoke it as `$ipd-agent-workflow-skill` or let normal Skill discovery select it for IPD-governed work.

## Project contract

The authoritative files are `.ipd/task_profile.yaml`, `.ipd/tailored_process.yaml`, `.ipd/project_state.yaml`, `.ipd/agent_runtime.yaml`, and optional `.ipd/artifact_bindings.yaml`. `.ipd/dashboard/`, reconciliation reports, and verification reports are derived views.

The structural contracts live in [schemas/](schemas/). Runtime validation additionally enforces dependency cycles, referential integrity, legal transitions, review authority, evidence presence, dashboard freshness, and repository reconciliation.

The non-negotiable policy remains at [policies/default/tailoring_rules.yaml](policies/default/tailoring_rules.yaml). Generic task-type policies are under [policies/task-types/](policies/task-types/) and are included in installed distributions.

Never place tokens, passwords, private keys, or private review content in project state. Evidence entries should be repository-relative paths, immutable revision references, or approved external record identifiers.

## Repository layout

```text
SKILL.md                         Skill entry point
agents/openai.yaml               Codex UI metadata
references/                      Conditional Skill guidance
AGENT_RUNTIME_PROTOCOL.md        Agent execution and authority contract
ipdctl/                          Tailoring, state, dashboard, runtime, and VCS modules
schemas/                         Profile, process, state, and runtime contracts
policies/default/                Non-negotiable governance policy
policies/task-types/             Generic task-type tailoring policies
templates/project/               Project scaffold reference
templates/hooks/                 Optional, non-installing verification guards
scripts/release_check.py         Release hygiene and secret-pattern audit
tests/                           Standard-library behavior tests
docs/                            Architecture and deployment guidance
RELEASE_CHECKLIST.md             GitHub publication checklist
```

## Verification

```bash
python -B -m compileall -q ipdctl tests scripts
python -B -m unittest discover -s tests -v
python -B -m ipdctl --help
python -B scripts/release_check.py .
```

See [docs/architecture.md](docs/architecture.md) for module boundaries, [docs/deployment.md](docs/deployment.md) for installation and release verification, and [CONTRIBUTING.md](CONTRIBUTING.md) before changing a contract.

## Status and license

The state schema and Python API may still change before `1.0`. Changes are recorded in [CHANGELOG.md](CHANGELOG.md). Security reports should follow [SECURITY.md](SECURITY.md).

Licensed under Apache-2.0. See [LICENSE](LICENSE).

Canonical repository: [github.com/zju-CS-yzy/ipd-agent-workflow-skill](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill)
