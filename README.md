# IPD Agent Workflow Skill

`0.1.0a1` is an alpha release of a Codex Skill and dependency-free Python runtime for evidence-backed Integrated Product Development (IPD) work. It keeps claims, deliverables, dependencies, reviews, and TR/DCP gates in a versioned project-state contract.

The runtime enforces a hard boundary: an AI agent can prepare and validate a gate, but final TR/DCP approval is valid only when an authorized human approval is recorded.

## Capabilities

- Run one canonical agent loop: `context -> claim -> work -> close -> verify`.
- Tailor reviews and deliverables without removing evidence, dependency, traceability, or human-approval invariants.
- Detect missing dependencies, dependency cycles, dangling trace links, and unsupported closure claims.
- Persist state atomically in `.ipd/project-state.json` and reject unknown contract fields.
- Inspect Git or SVN revision and dirty-state metadata without mutating the repository.

This alpha does not provide a hosted service, a graphical interface, or autonomous approval. It also does not commit, tag, push, or modify SVN state.

## Quick start

Python 3.10 or newer is required. From this checkout:

```bash
git clone https://github.com/zju-CS-yzy/ipd-agent-workflow-skill.git
cd ipd-agent-workflow-skill
python -m pip install -e .
ipdctl init /path/to/project --name my-project
ipdctl validate /path/to/project --policy policies/default/tailoring_rules.yaml
ipdctl status /path/to/project
ipdctl repository /path/to/project
```

Without installation, run the same commands as `python -m ipdctl ...` from the repository root.

To make the Skill discoverable by Codex, place this checkout at `$CODEX_HOME/skills/ipd-agent-workflow-skill` (or the equivalent user Skill directory). Invoke it as `$ipd-agent-workflow-skill` or let normal Skill discovery select it for IPD-governed work.

## State contract

`.ipd/project-state.json` is intentional, reviewable project state and may be version-controlled. `.ipd/generated/` is runtime output and is ignored. The structural contract is [schemas/project_state.schema.json](schemas/project_state.schema.json); `ipdctl validate` adds cross-reference and semantic checks that JSON Schema alone cannot express.

The default policy at [policies/default/tailoring_rules.yaml](policies/default/tailoring_rules.yaml) uses JSON-compatible YAML so the runtime needs no third-party YAML parser. Its contract is [schemas/tailoring_policy.schema.json](schemas/tailoring_policy.schema.json).

Never place tokens, passwords, private keys, or private review content in project state. Evidence entries should be repository-relative paths, immutable revision references, or approved external record identifiers.

## Repository layout

```text
SKILL.md                         Skill entry point
agents/openai.yaml               Codex UI metadata
references/                      Conditional Skill guidance
ipdctl/                          Python state, policy, engine, and VCS runtime
schemas/                         State and tailoring-policy contracts
policies/default/                Safe default tailoring policy
scripts/release_check.py         Release hygiene and secret-pattern audit
tests/                           Standard-library behavior tests
docs/                            Architecture and deployment guidance
RELEASE_CHECKLIST.md             GitHub publication checklist
```

## Verification

```bash
python -B -m unittest discover -s tests -v
python -B -m ipdctl --help
python -B scripts/release_check.py .
```

See [docs/architecture.md](docs/architecture.md) for module boundaries, [docs/deployment.md](docs/deployment.md) for installation and release verification, and [CONTRIBUTING.md](CONTRIBUTING.md) before changing a contract.

## Status and license

The state schema and Python API may still change before `1.0`. Changes are recorded in [CHANGELOG.md](CHANGELOG.md). Security reports should follow [SECURITY.md](SECURITY.md).

Licensed under Apache-2.0. See [LICENSE](LICENSE).

Canonical repository: [github.com/zju-CS-yzy/ipd-agent-workflow-skill](https://github.com/zju-CS-yzy/ipd-agent-workflow-skill)
