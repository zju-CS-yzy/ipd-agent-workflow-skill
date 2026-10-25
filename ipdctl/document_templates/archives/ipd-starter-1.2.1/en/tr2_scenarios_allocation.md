---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'tr2_scenarios_allocation'
template_id: 'ipd-starter.tr2_scenarios_allocation'
template_version: '0.2.1'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# TR2 scenario analysis and module allocation (discussion draft) — {{title}}

> Discussion draft 0.2.1 using this project's proposed TR1–TR4 convention for refinement together. Existing six-phase TR/DCP gates are not redefined. Fill with project facts; do not invent evidence or approval.

### First use: where to start

This document derives SRs, verifiable system behavior, performance or constraints under stated conditions, from TR1 IRs, user or business objectives. SRs need not exist at the start: chapter 2 develops scenarios and boundaries, chapter 3 derives each candidate SR, and chapter 4 consolidates the register. Allocation, interfaces and verification planning follow. Scenarios supply premises and the register summarizes specifications; neither replaces the individual derivations.

Each chapter states its purpose, inputs, writing steps and outputs. Inputs come from earlier analysis unless an existing file is actually available; later outputs need not exist in advance. Repeat individual records for the actual requirement count. Shared diagrams or calculations may have common identifiers, but explain each requirement's derivation. Distinguish candidates from registered `id@version` references; use the project's existing registration and approval processes. A registered identifier does not establish review or approval.

Distinguish stage snapshots from later updates. Start the front-matter `requirements` list with known inputs and add child references after their registration; it describes document coverage at that stage, not requirements that must already exist before writing. Give each derivation record a unique identifier and include its candidate or exact requirement reference in the heading for unambiguous register links. Preserve earlier table snapshots or immutable version references when later stages add information; early documents must not point to results that appeared later.

<!-- ipd-section:baseline -->
## 1. Define scope and TR1 inputs

**Purpose:** Determine which user objectives to decompose and which accepted facts apply.

**Inputs:** TR1 document, IR register, scenarios, feasibility analysis and applicable decisions.

**Writing steps:**

1. Identify each scoped exact IR version, objective and acceptance intent; distinguish current, deferred and unresolved scope.
2. Pin input paths and versions or digests, changes and open issues.
3. List missing material and its effects instead of presuming SRs or allocation already exist.

**Output:** IR decomposition scope, input index and issue list.

[[TODO: baseline]]

<!-- ipd-section:scenarios -->
## 2. Analyze scenarios and system boundaries

**Purpose:** Identify situations and conditions the system must handle as premises for SR derivation.

**Inputs:** Scoped IRs, TR1 scenarios, user, environment and external interface information.

**Writing steps:**

1. For each IR, identify scenarios and analyze actors, preconditions, triggers, normal and exceptional flows, inputs, outputs, environment and boundaries.
2. Use flow, sequence or state diagrams or prose to locate boundaries, dependencies, bottlenecks and safety or quality constraints; identify sources and assumptions.
3. State the system problems exposed by each scenario for chapter 3. These conclusions are not yet presumed existing SRs.

**Output:** Identified scenarios, boundaries and analysis conclusions. Shared scenarios may be written once; each SR must explain its applicability.

[[TODO: scenarios]]

<!-- ipd-section:decomposition -->
## 3. Derive each SR from its parent IR

**Purpose:** Actually formulate every candidate SR and explain why it is needed to satisfy an IR.

**Inputs:** Each IR objective and acceptance intent from chapter 1, plus scenarios and constraints from chapter 2.

**Writing steps:**

1. For each IR identify system responsibilities, measures and failure handling, then repeat the derivation record for every candidate SR. One IR may produce several SRs; a single overall summary is insufficient.
2. Explain the chain from IR objective through scenario and conditions to system responsibility or measure and resulting statement. For quantities show assumptions, variables, units, formulae, data sources and results. For rules or interfaces use flows, states, diagrams, counterexamples or logical arguments.
3. Explain thresholds, alternatives, verification approach and missing evidence. Shared calculations or diagrams may be referenced, but each SR must explain how they support its own content.
4. For every parent IR, assess whether the whole SR set covers normal, exceptional and boundary objectives; identify gaps, conflicts and duplication. Unsupported items remain candidates or open issues.

**Output:** Individual SR derivations and coverage arguments by IR for consolidation in chapter 4.

[[TODO: decomposition]]

### Repeat for each candidate SR: derivation record

- Candidate identifier or registered exact version: [[TODO: sr_reference]]
- Exact parent IR version, original text and objective: [[TODO: parent_ir_goal]]
- Scenario, boundaries, source facts and assumptions: [[TODO: scenario_conditions_sources]]
- Derivation steps and necessity: [[TODO: sr_derivation_steps]]
- Calculation, diagram or argument, with conditions, units, sources and conclusion: [[TODO: sr_calculation_diagram_argument]]
- Threshold choices, tradeoffs and limitations: [[TODO: sr_threshold_tradeoffs_limits]]
- Resulting complete candidate SR statement: [[TODO: sr_resulting_statement]]
- Verification method, conditions and expected criteria: [[TODO: sr_verification_intent]]
- Questions, owner and relationships to other SRs: [[TODO: sr_questions_owner_relations]]

### Repeat for each parent IR: assess the whole decomposition

[[TODO: ir_to_sr_coverage_argument]]

> Illustrative reasoning only, not project facts: an IR for a valid current reading within two seconds of a button press can yield a response-time SR from the normal sequence and an SR forbidding stale data being presented as a valid current reading from the acquisition-failure scenario. Explain which goal and scenario each supports; two identifiers alone are insufficient. Actual thresholds and responses still require project sources and rationale.

<!-- ipd-section:sr -->
## 4. Consolidate SR specifications and check IR coverage

**Purpose:** Turn chapter 3's reasoned results into maintainable, traceable register rows.

**Inputs:** Individual derivations and IR coverage arguments from chapter 3.

**Writing steps:**

1. Register selected SRs through the project's process and obtain exact versions, then fill one row per SR. Filling the table does not replace derivation.
2. Populate scenarios, behavior, measures, constraints, responsibility and criteria. Cite this document's chapter 3 record identifier or heading in relevant scenario or constraint cells for two-way traceability.
3. Check that every row has a derivation and every scoped IR has coverage or an explicit gap. Distinguish candidates, deferrals and uncertainties. Explain source and necessity for parentless derived SRs rather than inventing parent links.

**Output:** Pinned SR register, IR→SR mapping and gaps for allocation in chapter 5.

[[TODO: sr]]

<!-- ipd-section:allocation -->
## 5. Define modules and allocate system responsibilities

**Purpose:** Explain how modules will collaborate on SRs as input to TR3, without presuming ARs exist yet.

**Inputs:** SR register and scenarios and boundaries from chapters 2 and 4.

**Writing steps:**

1. Propose hardware and software module boundaries, responsibilities and allocation alternatives, mapping SRs to participating modules.
2. Explain collaboration, interfaces, resource or performance budgets and tradeoffs. One SR may need several modules; requirement counts do not determine module boundaries.
3. Identify missing or overlapping responsibilities and dependencies, with owners and plans for unresolved allocation.

**Output:** Module responsibilities, allocation rationale and open items.

[[TODO: allocation]]

| Module | Exact SR versions | Responsibility and boundary | Collaborating modules / interfaces | Budget / rationale | Gaps / owner |
| --- | --- | --- | --- | --- | --- |
| [[TODO: module]] | [[TODO: sr_versions]] | [[TODO: responsibility_boundary]] | [[TODO: collaboration_interfaces]] | [[TODO: budget_rationale]] | [[TODO: gaps_owner]] |

<!-- ipd-section:interfaces -->
## 6. Define interfaces and cross-module constraints

**Purpose:** Provide collaboration conditions that TR3 design can use.

**Inputs:** Module allocation and scenario and SR analysis from chapters 2–5.

**Writing steps:**

1. Describe responsibilities, data or control flows, boundary conditions and failure responses for internal and external interfaces.
2. Check support for related SRs. If a new system requirement emerges, derive it in chapter 3 and update chapter 4 rather than silently adding it in an interface table.
3. Pin existing interface or hardware selection documents; mark unfinished design as planned.

**Output:** Interface and constraint analysis, document index and analysis to revisit.

[[TODO: interfaces]]

<!-- ipd-section:verification -->
## 7. Plan SR verification and IR user validation

**Purpose:** Define what evidence will establish system and user objectives.

**Inputs:** SR criteria, IR acceptance intent, scenarios and allocation.

**Writing steps:**

1. Map SRs to test, analysis, inspection or demonstration, specifying object, environment, conditions and expected values.
2. Retain separate IR user acceptance plans, including combined, performance-boundary and failure scenarios.
3. Identify environment and evidence preparation gaps. This is planning, not unexecuted passing results.

**Output:** Traceable verification and validation plans for TR3/TR4 refinement.

[[TODO: verification]]

<!-- ipd-section:deliverables -->
## 8. Compile deliverables, risks and open items

**Purpose:** Make analysis, specifications, allocation and remaining issues locatable.

**Inputs:** Results of chapters 1–7 and actual attachments.

**Writing steps:**

1. List this overall document and the SR register, with the IR baseline as input. Add separate scenario, interface, hardware selection or verification plans as needed.
2. Identify impact, owner and next action for unfinished analysis, allocation or inputs.

**Output:** Stage manifest and actionable open items.

[[TODO: deliverables]]

| Type / proposed necessity | Document ID / path | Exact version / digest | Requirements / scope | Owner | Status / gaps |
| --- | --- | --- | --- | --- | --- |
| [[TODO: artifact_type]] | [[TODO: artifact_path]] | [[TODO: artifact_version]] | [[TODO: covered_requirements]] | [[TODO: artifact_owner]] | [[TODO: artifact_status]] |

<!-- ipd-section:review -->
## 9. Summarize review inputs and TR3 design handoff

**Purpose:** Distinguish usable design inputs from merely populated SR rows.

**Inputs:** Derivations, coverage, allocation, plans and manifests from chapters 3–8.

**Writing steps:**

1. Summarize the sufficiency of derivation premises, parent coverage, allocation maturity and pre-design questions.
2. List proposed TR3 SR versions, scenarios, modules, interfaces and budgets. Reference actual decisions without creating approval.

**Output:** Review summary and explicit TR3 input package.

[[TODO: review]]

