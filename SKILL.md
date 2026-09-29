---
name: ipd-agent-workflow-skill
description: Tailor and execute evidence-backed IPD workflows with TR/DCP gates, deliverable state, dashboards, Agent runtime, and read-only Git/SVN reconciliation. Use for engineering work governed by auditable IPD controls; do not use for generic task lists.
---

# IPD Agent Workflow

Use the repository's state and evidence to move work through one protocol:

`context -> claim -> work -> close -> review -> refresh -> verify`

Do not reorder or skip these meanings. Product phases such as `concept`, `develop`, and `launch` are separate from this per-task loop.

## Operating contract

1. **Context:** Inspect the request, repository instructions, `.ipd/project_state.yaml`, `.ipd/tailored_process.yaml`, the applicable policy, active claims, and read-only Git/SVN status. Initialize state only when the task includes starting IPD tracking.
2. **Claim:** State the outcome to prove, its acceptance evidence, affected deliverables, and dependencies. Do not present an assumption as verified evidence.
3. **Work:** Make the authorized change. Preserve existing trace links and add links when a claim, deliverable, or gate depends on another tracked entity.
4. **Close:** Submit work with durable evidence as `ready_for_review`; closing never accepts it.
5. **Review:** Record review evidence. Final acceptance requires an explicitly authorized human approval.
6. **Refresh:** Regenerate dashboards, graphs, and matrices from source facts; never edit generated views directly.
7. **Verify:** Run the relevant product checks plus `ipdctl verify`. Reconcile recorded state with repository changes and report unresolved evidence or review needs.

## Non-negotiable boundaries

- Never approve a final TR or DCP as an agent. An approved gate must contain an authorized human approval record and no conflicting authorized human rejection.
- Never tailor out traceability, evidence for acceptance, dependency closure, or authorized-human gate approval.
- Do not invent reviewer authorization, evidence, repository revisions, or test results.
- Keep credentials and private content out of state, evidence fields, prompts, logs, and generated artifacts.
- Repository inspection is read-only. Committing, tagging, pushing, or changing SVN state requires authorization from the current task.

If validation fails, preserve the state file, report the exact paths returned by the validator, and fix only evidence-backed inconsistencies. Do not force an invalid transition.

## State and commands

The project fact sources are `.ipd/task_profile.yaml`, `.ipd/tailored_process.yaml`, `.ipd/project_state.yaml`, and `.ipd/agent_runtime.yaml`. Their structural contracts are under [schemas/](schemas/); the runtime also checks dependency cycles, transitions, review authority, trace links, dashboard freshness, and repository reconciliation.

```bash
python -m ipdctl init . --name PROJECT_NAME --task-type software
python -m ipdctl tailor .
python -m ipdctl context .
python -m ipdctl refresh .
python -m ipdctl verify .
python -m ipdctl repository .
```

Use `init` only when no state exists. Do not use `--force` unless replacement is explicitly intended. Use `claim`, `close`, `review`, `approve`, and `reject` for deliverable state; an Agent must never call final approval while impersonating a human.

## Read details only when needed

- For lifecycle, TR/DCP, evidence, or tailoring decisions, read [references/workflow.md](references/workflow.md).
- For state fields, transitions, validation errors, or CLI behavior, read [references/state-contract.md](references/state-contract.md).
- For Git/SVN revision evidence or repository boundaries, read [references/repository-integration.md](references/repository-integration.md).
- For implementation boundaries, read [docs/architecture.md](docs/architecture.md).
- For the execution command contract, read [AGENT_RUNTIME_PROTOCOL.md](AGENT_RUNTIME_PROTOCOL.md).

Finish with the verified outcome, remaining gate or evidence gaps, and the exact human decision needed, if any.
