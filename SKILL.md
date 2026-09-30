---
name: ipd-agent-workflow-skill
description: Tailor and execute evidence-backed bilingual IPD workflows with TR/DCP gates, deliverable state, dashboards, Agent runtime, and read-only Git/SVN reconciliation. Use for engineering work governed by auditable IPD controls; do not use for generic task lists.
---

# IPD Agent Workflow

Use the repository's state and evidence to move work through one serialized
protocol:

`context -> claim -> work -> close -> review -> human approve/reject -> refresh -> verify`

Do not reorder or skip these meanings. The controller allows at most one active
claim. `approve` and `reject` are human-decision commands executed while the
workflow step remains `review`. Product phases such as `concept`, `develop`,
and `launch` are separate from this per-deliverable loop.

## Language contract

- Before project initialization, communicate in the user's conversation language.
- After initialization, use `.ipd/task_profile.yaml` at `presentation.locale` for user-facing CLI and generated Dashboard text. Supported values are `en` and `zh-CN`; an older profile without this field uses `en` without being rewritten.
- Keep commands, filenames, IDs, YAML/JSON keys, schema paths, statuses, relations, and other machine contracts in English. Localize only presentation text. Preserve user-provided names, evidence, paths, and descriptions as entered.
- A locale change affects presentation only. Regenerate derived views with `refresh`; never re-tailor or alter workflow facts merely to change language.

## Operating contract

1. **Context:** Inspect the request, repository instructions, `.ipd/project_state.yaml`, `.ipd/tailored_process.yaml`, the applicable policy, active claims, and read-only Git/SVN status. Initialize state only when the task includes starting IPD tracking.
2. **Claim:** State the outcome to prove, its acceptance evidence, affected deliverables, and dependencies. Do not present an assumption as verified evidence.
3. **Work:** Make the authorized change. Preserve existing trace links and add links when a claim, deliverable, or gate depends on another tracked entity.
4. **Close:** Submit work with durable evidence as `ready_for_review`; closing never accepts it.
5. **Review:** Append review evidence. An Agent may recommend a decision but may not make the final decision.
6. **Human decision:** Record an explicitly authorized human `approve` or `reject`. Preserve the complete review history; the latest authorized human decision is the current governance decision, so an earlier rejection remains auditable but does not permanently block approved rework.
7. **Refresh:** Regenerate the interactive Dashboard, typed SVG graphs, and matrices from source facts; never edit generated views directly.
8. **Verify:** Run the relevant product checks plus `ipdctl verify`. Reconcile recorded state with repository changes and report unresolved evidence or review needs. A new claim may start from `verify` only while the latest passed verification still matches the current state revision and complete verification-input fingerprint.

## Non-negotiable boundaries

- Never approve a final TR or DCP as an agent. An approved gate must have an authorized human approval as its latest authorized human decision.
- Never tailor out traceability, evidence for acceptance, dependency closure, or authorized-human gate approval.
- Do not invent reviewer authorization, evidence, repository revisions, or test results.
- Keep credentials and private content out of state, evidence fields, prompts, logs, and generated artifacts.
- Repository inspection is read-only. Committing, tagging, pushing, or changing SVN state requires authorization from the current task.

If validation fails, preserve the state file, report the exact paths returned by the validator, and fix only evidence-backed inconsistencies. Do not force an invalid transition.

## State and commands

The project fact sources are `.ipd/task_profile.yaml`, `.ipd/tailored_process.yaml`, `.ipd/project_state.yaml`, `.ipd/agent_runtime.yaml`, and `.ipd/artifact_bindings.yaml`. Their structural contracts are under [schemas/](schemas/); the runtime also checks dependency cycles, transitions, review authority, trace links, dashboard freshness, and repository reconciliation.

```bash
python -m ipdctl init . --name PROJECT_NAME --task-type software --locale en
python -m ipdctl tailor .
python -m ipdctl context .
python -m ipdctl claim DELIVERABLE --project-root .
python -m ipdctl close DELIVERABLE --project-root . --evidence evidence/DELIVERABLE/result.md
python -m ipdctl review DELIVERABLE --project-root . --reviewer REVIEWER
python -m ipdctl approve DELIVERABLE --project-root . --reviewer HUMAN --actor-type human --authorized --evidence evidence/DELIVERABLE/approval.md
python -m ipdctl refresh .
python -m ipdctl verify .
python -m ipdctl advance-phase .
python -m ipdctl repository .
python -m ipdctl reconcile .
python -m ipdctl validate .
```

The full command surface is `init`, `tailor`, `context`, `claim`, `close`,
`review`, `approve`, `reject`, `advance-phase`, `refresh`, `verify`,
`repository`, `reconcile`, `validate`, and the `status` alias for `context`.
Use `init` only when no state exists. Do not use `--force` unless replacement
is explicitly intended. Use `claim --recover` only to recover an orphaned
`in_progress` deliverable identified by `context`; an unexpired claim owned by
another actor cannot be taken over. An Agent must never call final approval
while impersonating a human.

`tailor` preserves user-authored artifact rules and regenerates one managed
`evidence/<deliverable-id>/**` binding for every tailored deliverable. It does
not infer ownership for real source, firmware, hardware, test, documentation,
configuration, or tool paths. Add explicit user-authored rules in
`.ipd/artifact_bindings.yaml` for those paths before relying on reconciliation.
Reconciliation also requires every mapped changed Deliverable to have an
auditable `claim` event in Agent Runtime; a binding without Claim provenance is
not ownership evidence.

Use `advance-phase` only after every current-phase Gate is approved and the
latest passed verification matches both the current state revision and the
current verification-input fingerprint. Advancement changes exactly one phase
and returns the workflow to `refresh`; run `refresh` and `verify` before any new
claim or Gate review. In the final `lifecycle` phase, a successful verification
with all phase Gates approved records one `lifecycle_complete` runtime event;
there is no further phase to advance to.

After `refresh`, use `.ipd/dashboard/index.html` for human inspection and
`.ipd/dashboard/data/state.json` plus `data/graph.json` for automation. A graph
or matrix is a derived view; never use it to override the YAML fact sources.

## Read details only when needed

- For lifecycle, TR/DCP, evidence, or tailoring decisions, read [references/workflow.md](references/workflow.md).
- For state fields, transitions, validation errors, or CLI behavior, read [references/state-contract.md](references/state-contract.md).
- For Git/SVN revision evidence or repository boundaries, read [references/repository-integration.md](references/repository-integration.md).
- For implementation boundaries, read [docs/architecture.md](docs/architecture.md).
- For the execution command contract, read [AGENT_RUNTIME_PROTOCOL.md](AGENT_RUNTIME_PROTOCOL.md).

Finish with the verified outcome, remaining gate or evidence gaps, and the exact human decision needed, if any.
