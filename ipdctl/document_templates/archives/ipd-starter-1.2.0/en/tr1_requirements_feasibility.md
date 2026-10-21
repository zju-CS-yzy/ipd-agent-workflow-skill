---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'tr1_requirements_feasibility'
template_id: 'ipd-starter.tr1_requirements_feasibility'
template_version: '0.2.0'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# TR1 initial requirements and feasibility analysis (discussion draft) — {{title}}

> Discussion draft 0.2.0 using this project's proposed TR1–TR4 convention for refinement together. Existing six-phase TR/DCP gates are not redefined. Fill with project facts; do not invent evidence or approval.

### First use: where to start

An IR expresses a user or business objective. This document develops candidate IRs from source material and examines their value and feasibility. An IR register need not exist when writing starts: establish context and scope, form candidate IRs in chapter 4, revise them through feasibility analysis, and consolidate them in chapter 6.

Each chapter states its purpose, inputs, writing steps and outputs. Inputs come from earlier analysis unless an existing file is actually available; later outputs need not exist in advance. Repeat individual records for the actual requirement count. Shared diagrams or calculations may have common identifiers, but explain each requirement's derivation. Distinguish candidates from registered `id@version` references; use the project's existing registration and approval processes. A registered identifier does not establish review or approval.

<!-- ipd-section:baseline -->
## 1. Define scope and source material

**Purpose:** Establish which product and increment the analysis covers and which material supports it.

**Inputs:** Project brief, elicitation records, field issues, existing product information and applicable decisions. A new project may have no prior requirement baseline.

**Writing steps:**

1. Identify the product, increment, document version, author and problem to address.
2. Assign locatable source identifiers and versions or dates; distinguish facts, assumptions and investigations.
3. For an iteration, identify the retained baseline and changes. List missing inputs without presuming conclusions.

**Output:** Scope, source index and missing-input list.

[[TODO: baseline]]

<!-- ipd-section:context -->
## 2. Analyze problems, users and shared context

**Purpose:** Explain why the need exists and whose work is affected.

**Inputs:** Source index from chapter 1.

**Writing steps:**

1. Describe current practice, user, operations and maintenance roles, and problems with source references.
2. Separate objectives from proposed solutions and unconfirmed guesses; a technology choice is not automatically a requirement.
3. Identify reusable context, sources and user groups for later analysis and register references.

**Output:** Source-supported problems, user objectives and shared context.

[[TODO: context]]

<!-- ipd-section:scope -->
## 3. Describe scenarios, boundaries and increment objectives

**Purpose:** Place broad objectives in operating situations and determine this increment's scope.

**Inputs:** Problems and objectives from chapter 2.

**Writing steps:**

1. Identify scenarios and describe users, environments, preconditions, triggers, normal and exceptional flows, and intended outcomes.
2. Describe product boundaries, external systems and explicit exclusions.
3. Separate MVP or increment commitments from future intentions and unresolved scope.

**Output:** Scenarios, a boundary description or diagram, and current versus future scope for candidate IR development.

[[TODO: scope]]

<!-- ipd-section:elicitation -->
## 4. Develop each candidate IR from its sources

**Purpose:** Actually formulate IRs here and explain their origins, rather than waiting for a completed register.

**Inputs:** Problems from chapter 2 and scenarios and scope from chapter 3.

**Writing steps:**

1. Repeat the record below for each candidate IR. Explain how duplicated or conflicting sources were combined or resolved.
2. Extract the intended user outcome, applicable scenarios and acceptance intent. Give sources, units and conditions for numeric objectives.
3. Identify candidates, priority rationale and open questions without presuming feasibility or approval.

**Output:** Candidates with sources, scenarios and acceptance intent for feasibility analysis.

[[TODO: elicitation]]

### Repeat for each candidate IR

- Source identifier, original statement and problem: [[TODO: source_and_problem]]
- Scenario, user objective and consolidation rationale: [[TODO: scenario_goal_rationale]]
- Candidate IR identifier and complete statement: [[TODO: candidate_ir_statement]]
- Acceptance intent, priority rationale and questions: [[TODO: acceptance_priority_questions]]

<!-- ipd-section:feasibility -->
## 5. Analyze feasibility and compare alternatives

**Purpose:** Establish whether objectives have a credible implementation basis and at what cost and risk.

**Inputs:** Candidate IRs from chapter 4 and available technology, resource, cost and schedule information.

**Writing steps:**

1. Compare technical, hardware and software alternatives against applicable resource, cost, schedule, manufacturing and maintenance constraints.
2. Support important conclusions with calculations, experiments, prototypes, diagrams or reasoned source evidence; state assumptions, data and limits. Keep unsupported matters unresolved.
3. Explain recommendations to retain, revise, split, defer or investigate IRs and update chapter 4 accordingly.

**Output:** Alternative analysis, feasibility rationale and revised candidates; no automatic approval.

[[TODO: feasibility]]

| Alternative | Supported IRs / scenarios | Calculation / experiment / rationale | Cost / schedule / resources | Limitations and risks | Investigations / owner |
| --- | --- | --- | --- | --- | --- |
| [[TODO: alternative]] | [[TODO: ir_scenarios]] | [[TODO: feasibility_basis]] | [[TODO: cost_schedule_resources]] | [[TODO: limitations_risks]] | [[TODO: investigations_owner]] |

<!-- ipd-section:ir -->
## 6. Consolidate the IR register and check source coverage

**Purpose:** Record the results of the preceding analysis in a consistent specification without omitting their origins.

**Inputs:** Candidate IRs from chapter 4 and dispositions from chapter 5.

**Writing steps:**

1. Register selected requirements through the project's process, obtain exact IDs and versions, and add one IR per register row. Clearly distinguish candidates from registered references.
2. Fill context, scenario, statement, value, acceptance intent, priority, owner, increment and open items, pointing back to their development records.
3. Check every source against an IR or an explained exclusion. Pin the register path and version and list gaps.

**Output:** IR register, source-to-IR mapping and remaining gaps for TR2 decomposition.

[[TODO: ir]]

<!-- ipd-section:risks -->
## 7. Consolidate risks, dependencies and open decisions

**Purpose:** Give unresolved scope or feasibility issues actionable follow-up.

**Inputs:** Issues from chapters 1–6.

**Writing steps:**

1. Consolidate duplicates while retaining affected IRs and analysis locations.
2. Assign impact, owner, action, target resolution point and increment disposition to each item.

**Output:** Actionable issues; unknown conclusions remain unknown.

[[TODO: risks]]

<!-- ipd-section:deliverables -->
## 8. Compile stage deliverables

**Purpose:** Enable reviewers to find the files supporting the conclusions.

**Inputs:** This document, the IR register and actual attachments.

**Writing steps:**

1. Record paths, versions or digests, scope, owners and gaps.
2. Proposed minimum: this document plus the IR register. Add elicitation records, prototypes or preliminary hardware selection as needed.

**Output:** Locatable, versioned stage manifest.

[[TODO: deliverables]]

| Type / proposed necessity | Document ID / path | Exact version / digest | Requirements / scope | Owner | Status / gaps |
| --- | --- | --- | --- | --- | --- |
| [[TODO: artifact_type]] | [[TODO: artifact_path]] | [[TODO: artifact_version]] | [[TODO: covered_requirements]] | [[TODO: artifact_owner]] | [[TODO: artifact_status]] |

<!-- ipd-section:review -->
## 9. Summarize review inputs and TR2 handoff

**Purpose:** Explain what was analyzed, what remains missing and what the next stage can use.

**Inputs:** IR register, issue list and manifest from chapters 6–8.

**Writing steps:**

1. Summarize source coverage, feasibility evidence, proposed scope and open issues separately.
2. Identify proposed TR2 IR versions, scenarios and constraints. Reference actual decisions when available; completing a template creates no approval.

**Output:** Review summary and explicit TR2 input list.

[[TODO: review]]

