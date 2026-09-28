---
name: ipd-agent-workflow-skill
description: Run evidence-backed IPD workflows with TR/DCP tailoring, deliverable dependencies, project state, review traceability, and Git/SVN context. Use for engineering work governed by IPD gates and auditable evidence; do not use for generic task lists without those controls.
---

# IPD Agent Workflow

Use the repository's state and evidence to move work through one loop:

`context -> claim -> work -> close -> verify`

Do not reorder or skip these meanings. Product phases such as `concept`, `develop`, and `launch` are separate from this per-task loop.

## Operating contract

1. **Context:** Inspect the request, repository instructions, `.ipd/project-state.json`, the applicable tailoring policy, and read-only Git/SVN status. Initialize state only when the task includes starting IPD tracking.
2. **Claim:** State the outcome to prove, its acceptance evidence, affected deliverables, and dependencies. Do not present an assumption as verified evidence.
3. **Work:** Make the authorized change. Preserve existing trace links and add links when a claim, deliverable, or gate depends on another tracked entity.
4. **Close:** Mark a claim supported or a deliverable accepted only when evidence exists and every required dependency is accepted.
5. **Verify:** Run the relevant product checks plus `ipdctl validate`. Reconcile the recorded state with repository status and report unresolved evidence or review needs.

## Non-negotiable boundaries

- Never approve a final TR or DCP as an agent. An approved gate must contain an authorized human approval record and no conflicting authorized human rejection.
- Never tailor out traceability, evidence for acceptance, dependency closure, or authorized-human gate approval.
- Do not invent reviewer authorization, evidence, repository revisions, or test results.
- Keep credentials and private content out of state, evidence fields, prompts, logs, and generated artifacts.
- Repository inspection is read-only. Committing, tagging, pushing, or changing SVN state requires authorization from the current task.

If validation fails, preserve the state file, report the exact paths returned by the validator, and fix only evidence-backed inconsistencies. Do not force an invalid transition.

## State and commands

The default state path is `.ipd/project-state.json`. Its structural contract is [schemas/project_state.schema.json](schemas/project_state.schema.json); the runtime also checks dependency cycles, cross-references, closure rules, and human gate approval.

```bash
python -m ipdctl init . --name PROJECT_NAME
python -m ipdctl validate . --policy policies/default/tailoring_rules.yaml
python -m ipdctl status .
python -m ipdctl repository .
```

Use `init` only when no state exists. Do not use `--force` unless replacing state is explicitly intended and the prior state is preserved or no longer needed.

## Read details only when needed

- For lifecycle, TR/DCP, evidence, or tailoring decisions, read [references/workflow.md](references/workflow.md).
- For state fields, transitions, validation errors, or CLI behavior, read [references/state-contract.md](references/state-contract.md).
- For Git/SVN revision evidence or repository boundaries, read [references/repository-integration.md](references/repository-integration.md).
- For implementation boundaries, read [docs/architecture.md](docs/architecture.md).

Finish with the verified outcome, remaining gate or evidence gaps, and the exact human decision needed, if any.
