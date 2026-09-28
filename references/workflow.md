# Workflow and Gate Rules

Read this reference when deciding how to tailor an IPD flow, close evidence, or prepare a TR/DCP gate.

## Two independent progress dimensions

The project phase describes product maturity: `concept`, `plan`, `develop`, `qualify`, `launch`, or `lifecycle`.

The agent workflow step describes the current unit of work:

1. `context` — establish scope, authority, state, repository facts, and applicable policy.
2. `claim` — define a falsifiable result and the evidence that would support it.
3. `work` — produce or change the deliverable while maintaining dependencies and links.
4. `close` — satisfy acceptance criteria and attach evidence.
5. `verify` — independently check the result and reconcile the state.

After `verify`, a new unit of work may return to `context`. A product phase changes only when project governance calls for it; completing one agent loop does not imply a phase change.

## Deliverables and evidence

A deliverable moves through `planned`, `in_progress`, `blocked`, `ready_for_review`, and `accepted`. Rework may move `ready_for_review` back to `in_progress`. Acceptance requires:

- at least one durable evidence reference;
- every `depends_on` deliverable in `accepted` state;
- no dependency cycle; and
- state validation after the transition.

Good evidence is reproducible and specific: a repository-relative document, test record, immutable commit/revision, approved review record, or stable external record identifier. A statement that work was checked is not itself evidence.

## TR and DCP gates

- A Technical Review (`TR`) evaluates technical readiness or quality.
- A Decision Checkpoint (`DCP`) records a governed business or program decision.
- A gate moves from `planned` to `ready` only after all required deliverables are accepted.
- Reviews may be prepared by humans or agents, but final `approved` state requires an explicitly authorized human approval record.
- Any authorized human rejection conflicts with `approved` state and must be resolved rather than overwritten.

The agent may assemble evidence, identify missing reviewers, record a supplied decision, and validate readiness. It must stop short of inventing the human decision or the reviewer's authorization.

## Tailoring

Tailoring may add deliverables or reviewers, merge non-final reviews, and tighten evidence requirements. It must not remove traceability, accept work without evidence, close work with unmet dependencies, or delegate final gate approval to an agent.

Record a tailored choice in project documentation or policy evidence so that another reviewer can understand why the default flow changed.
