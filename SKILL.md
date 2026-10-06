---
name: ipd-agent-workflow-skill
description: Tailor, progressively refine, and execute evidence-backed bilingual IPD workflows with TR/DCP gates, deliverable state, dashboards, Agent runtime, and read-only Git/SVN reconciliation. Use for engineering work governed by auditable IPD controls; do not use for generic task lists.
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

1. **Context:** Inspect the request, repository instructions, `.ipd/project_state.yaml`, `.ipd/tailored_process.yaml`, `.ipd/process_extensions.yaml`, the applicable policies, active claims, progressive-refinement status, and read-only Git/SVN status. Initialize state only when the task includes starting IPD tracking. If `refinement_due` is non-empty, prepare and preview an explicit plan before claiming child work; applying it requires an authorized human.
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

The project fact sources are `.ipd/task_profile.yaml`, `.ipd/process_extensions.yaml`, `.ipd/tailored_process.yaml`, `.ipd/project_state.yaml`, `.ipd/agent_runtime.yaml`, and `.ipd/artifact_bindings.yaml`. Their structural contracts are under [schemas/](schemas/); the runtime also checks dependency cycles, transitions, review authority, trace links, dashboard freshness, and repository reconciliation.

```bash
python -m ipdctl init . --name PROJECT_NAME --task-type software --locale en
python -m ipdctl tailor . --preview
python -m ipdctl tailor .
python -m ipdctl context .
python -m ipdctl refine . --plan refinement-plan.yaml --preview --json
python -m ipdctl adopt-baseline . --preview --json
python -m ipdctl claim DELIVERABLE --project-root .
python -m ipdctl close DELIVERABLE --project-root . --evidence evidence/DELIVERABLE/result.md
python -m ipdctl review DELIVERABLE --project-root . --reviewer REVIEWER
python -m ipdctl approve DELIVERABLE --project-root . --reviewer HUMAN --actor-type human --authorized --evidence evidence/DELIVERABLE/approval.md
python -m ipdctl refresh .
python -m ipdctl verify .
python -m ipdctl advance-phase .
python -m ipdctl repository .
python -m ipdctl reconcile .
python -m ipdctl validate . --json
```

The full command surface is `init`, `tailor`, `refine`, `context`, `adopt-baseline`, `claim`, `close`,
`review`, `approve`, `reject`, `advance-phase`, `refresh`, `verify`,
`repository`, `reconcile`, `validate`, and the `status` alias for `context`.
Use `init` only when no state exists. Do not use `--force` unless replacement
is explicitly intended. Use `claim --recover` only to recover an orphaned
`in_progress` deliverable identified by `context`; an unexpired claim owned by
another actor cannot be taken over. An Agent must never call final approval
while impersonating a human.

Treat the actionability fields in `context --json` as distinct causes:
`waiting_items` have unmet `depends_on` prerequisites, `explicit_blockers`
have lifecycle status `blocked`, and `governance_blockers` fail binding,
refinement, Claim-provenance, or protocol checks. `blocked_items` is only the
deduplicated Deliverable-scoped compatibility union; project-scoped protocol
entries remain exclusive to `governance_blockers`.

Tailoring compiles exactly four additive layers in order:
`core -> task_type -> capability -> project`. Select reusable capability packs
with `task_profile.yaml` at `capability_patterns`; use the canonical
`.ipd/process_extensions.yaml` only for project-owned Activities,
Deliverables, generic Gates, typed relations, TR/DCP criteria, and explicit
Deliverable, Gate, or dependency-correction migrations. The project layer
cannot delete or override an earlier entity.
Every compiled Phase, Activity, Deliverable, TR, DCP, and Gate records its
`provenance` layer/source and phase-derived `maturity`. Dependencies must be
acyclic and phase-monotonic: an earlier-Phase Deliverable cannot depend on a
later-Phase Deliverable.

The built-in capability catalog contains `sourced_component_integration`,
`module_decomposition_and_verification`,
`interface_contract_and_integration`, and
`release_and_lifecycle_assurance`. Capabilities are explicit opt-ins: an
omitted or empty `capability_patterns` list adds none of them. Use
`depends_on` for readiness and execution order. `supports` and `verifies` are
trace semantics for review and visualization; they never create execution
prerequisites.

Always run `tailor --preview` before changing an existing process. Preview is
read-only; `--json` returns `added`, `removed`, `changed`, `migrations`, and
`ambiguous`, including `state.traceability` additions, removals, and redirects.
A Claim-linked relation whose surviving endpoint cannot be preserved or
explicitly migrated is an `ambiguous` blocker. A re-tailor is forbidden while
a Claim is active. Removing a
historical, non-superseded Deliverable requires an explicit `replace` or
`split` mapping, `--apply-migrations`, and an authorized human Actor and
reason. The old state node becomes `superseded` and retains its evidence and
reviews; replacement nodes start `planned` with no copied evidence or review
decision. Ordinary re-tailoring cannot reinterpret a Deliverable that already
has lifecycle history under the same ID; introduce a new ID and use the
explicit migration path. It also cannot add or change process facts in an
approved or already closed Phase, including TR/DCP criteria. The only upgrade
exception is deterministic schema `1.0` enrichment with core provenance,
maturity, and canonical readiness criteria. Do not infer a migration mapping
or reopen a Phase implicitly.

Move legacy generic Gate history only through an explicit one-to-one
`gate_migrations` record whose target exists in the candidate process. Correct
the `depends_on` set of a historical Deliverable under the same ID only through
an exact `dependency_corrections` record with reviewed `before` and `after`
sets, `preserve_history: true`, and `require_reapproval: true`. Both operations
use `--apply-migrations` and explicit authorized-human Actor and reason on their
first effective application. A dependency correction preserves evidence and
reviews, blocks the affected Deliverable for rework, and invalidates affected
unapproved Gate readiness; it must not silently reopen an approved Gate.

New compilation writes tailored-process schema `2.0`. A schema `1.0` process
remains readable only while it semantically matches a profile without enabled
capabilities and the canonical project extension is empty. Preview and
re-tailor before enabling a capability or adding project extension content.

Progressive refinement is a separate, additive decision. A canonical
`refinement_requirements` entry, or a selected capability's policy-owned
placeholder, declares the root and trigger. The
`module_decomposition_and_verification` capability deliberately adds
`module.implementation_baseline` as a placeholder; accepting
`module.decomposition_baseline` makes its refinement due. Expand it through
`ipdctl refine` rather than treating the placeholder as executable module
work. The plan must use `mode: expand` and the current
`process_fingerprint`. Always run
`refine --preview --json` first. Apply only the reviewed plan, with an
identified human Actor, `--authorized`, and a reason, while there is no active
Claim and the root belongs to the current Phase. Never infer child modules,
copy parent acceptance to children, or rewrite Owner bindings. Every new
concrete child requires a user-authored artifact Owner; placeholder and
abstract nodes do not become claimable artifacts. The parent
becomes an abstract aggregate and retains its history; new children start
`planned` with empty evidence and reviews. `refines` is structural ancestry,
while only `depends_on` affects execution. If concrete Gate requirements
change, treat old approval as stale and require the new review epoch.
The applied process record and runtime event must agree on the plan, base and
result SHA-256 values, root, children, and invalidated Gate set.

`tailor` preserves user-authored artifact rules and regenerates one managed
`evidence/<deliverable-id>/**` binding for every tailored deliverable. It does
not infer ownership for real source, firmware, hardware, test, documentation,
configuration, or tool paths. Add explicit user-authored rules in
`.ipd/artifact_bindings.yaml` for those paths before relying on reconciliation.
Every actually changed critical path must resolve to one Deliverable owner.
An omitted Binding `role` retains this owner behavior; explicit `role: owner`
also authorizes only its single `deliverable`. A `role: shared_evidence` rule
must be non-critical and may reference several `deliverables`, but it neither
authorizes a Claim nor satisfies the required owner for a critical path.
New Claim events capture a binding window, so a historical Claim cannot
authorize unrelated later changes.

Treat artifact-binding globs as project-root anchored. A pattern such as
`README.md` matches only the root file; `*` does not cross `/`, and only a full
`**` path segment can span zero or more directories.

For an existing project whose governed paths were already dirty before this
protocol was installed, first validate explicit bindings, then let an
authorized human run `adopt-baseline` with an Actor and reason. An Agent may
preview the snapshot but must not self-authorize adoption. Adoption records
exact hashes in append-only runtime history; it creates no Claim and never
mutates Git or SVN. After any binding or source change, run `refresh` and
`verify` before relying on the Dashboard or beginning the next iteration.

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
