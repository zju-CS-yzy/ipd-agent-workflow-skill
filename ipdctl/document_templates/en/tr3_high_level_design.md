---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'tr3_high_level_design'
template_id: 'ipd-starter.tr3_high_level_design'
template_version: '0.2.1'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# TR3 high-level design and AR allocation (discussion draft) — {{title}}

> Discussion draft 0.2.1 using this project's proposed TR1–TR4 convention for refinement together. Existing six-phase TR/DCP gates are not redefined. Fill with project facts; do not invent evidence or approval.

### First use: where to start

This document develops a high-level design from TR2 SRs and module allocation, then derives ARs: verifiable requirements assigned to modules or responsibility units. ARs do not appear without explanation and are not module names relabeled as requirements. Chapters 2–4 establish architecture, mechanisms and constraints; chapter 5 derives each AR from its SR; chapter 6 consolidates the AR register. Design and allocation may iterate. Detailed design and implementation follow in TR4.

Each chapter states its purpose, inputs, writing steps and outputs. Inputs come from earlier analysis unless an existing file is actually available; later outputs need not exist in advance. Repeat individual records for the actual requirement count. Shared diagrams or calculations may have common identifiers, but explain each requirement's derivation. Distinguish candidates from registered `id@version` references; use the project's existing registration and approval processes. A registered identifier does not establish review or approval.

Distinguish stage snapshots from later updates. Start the front-matter `requirements` list with known inputs and add child references after their registration; it describes document coverage at that stage, not requirements that must already exist before writing. Give each derivation record a unique identifier and include its candidate or exact requirement reference in the heading for unambiguous register links. Preserve earlier table snapshots or immutable version references when later stages add information; early documents must not point to results that appeared later.

<!-- ipd-section:baseline -->
## 1. Define design scope and TR2 inputs

**Purpose:** Establish the system objectives and constraints this increment's design must satisfy.

**Inputs:** TR2 document, SR register, IR traceability, module allocation, scenarios, interfaces and decisions.

**Writing steps:**

1. Identify exact SR versions, conditions, criteria and parent objectives.
2. Pin input paths and versions, allocation, interfaces, budgets, changes and open issues.
3. Clarify ambiguous SRs through requirement analysis instead of silently filling missing information with accepted ARs.

**Output:** SR design inputs, constraints and clarification list.

[[TODO: baseline]]

<!-- ipd-section:architecture -->
## 2. Select architecture and explain module responsibilities

**Purpose:** Propose a structure satisfying SRs as the design basis for later AR allocation.

**Inputs:** SRs from chapter 1 and TR2 scenarios and module allocation.

**Writing steps:**

1. Describe composition, hardware and software deployment, responsibilities and dependencies with identified views tied to SRs.
2. Compare alternatives and explain selection, constraints and costs. Explain changes to TR2 module boundaries and their effects.
3. Relate the design to SRs here; ARs are formed through chapter 5, not presumed available in advance.

**Output:** Architecture views, module responsibilities and tradeoffs.

[[TODO: architecture]]

| Component / module | Architecture view reference | Supported exact SR versions | Responsibility | Deployment / dependencies | Decision / rationale |
| --- | --- | --- | --- | --- | --- |
| [[TODO: component]] | [[TODO: view_reference]] | [[TODO: sr_versions]] | [[TODO: responsibility]] | [[TODO: deployment_dependencies]] | [[TODO: decision_rationale]] |

<!-- ipd-section:behavior -->
## 3. Analyze interactions, data and mechanisms

**Purpose:** Show how the structure operates in scenarios and identify required module behavior and limits.

**Inputs:** Architecture, TR2 scenarios and SR criteria.

**Writing steps:**

1. Describe cross-module sequences, states, data lifecycle and failure recovery in normal, boundary and failure scenarios, using diagrams where useful.
2. Analyze processing paths, concurrency, queues, latency, resources and interfaces. State conditions, assumptions, units and data sources.
3. Record required responsibilities, constraints and risks as chapter 5 inputs. A structure diagram alone does not establish sufficient allocation.

**Output:** Identified mechanisms, calculations or diagrams and responsibilities to allocate.

[[TODO: behavior]]

<!-- ipd-section:quality -->
## 4. Justify quality attributes, budgets and risks

**Purpose:** Provide a basis for relevant quality objectives beyond functional flows.

**Inputs:** SR quality and performance targets and architecture and behavior from chapters 2–3.

**Writing steps:**

1. Analyze applicable performance, reliability, safety, security, maintainability and testability with calculations, estimates, prototypes or source evidence.
2. Separate known results from unverified assumptions, including budgets, margin, failure conditions and tradeoffs.
3. Carry constraints, budgets and risks into chapter 5; unsupported measures cannot establish feasibility.

**Output:** Quality and budget arguments, limitations and investigation needs.

[[TODO: quality]]

<!-- ipd-section:decomposition -->
## 5. Derive and allocate each AR from its parent SR

**Purpose:** Actually formulate every candidate AR from an SR and the selected design.

**Inputs:** Each SR's criteria and the architecture, mechanisms, budgets and constraints from chapters 1–4.

**Writing steps:**

1. For each SR identify responsible modules, collaboration paths and conditions, then repeat the record for each candidate AR. One SR can yield multiple ARs and one module can own several ARs.
2. Explain the chain from SR objective through the selected design or path to module responsibility or budget and the AR statement. Use calculations, sequence or state diagrams, resource allocation, failure propagation or logical arguments with thresholds and responsibility boundaries.
3. Check combined AR satisfaction of each SR: reconcile totals, critical paths and margin for quantities, and collaboration, failures, interfaces and boundary conditions for behavior. Individual module success does not establish system success.
4. Explain alternatives, shared constraints and gaps. Revisit chapters 2–4 if design changes. Explain parentless derived ARs separately rather than inventing SR parent links.

**Output:** Individual AR derivations and allocation arguments, plus combined coverage by SR, for chapter 6.

[[TODO: decomposition]]

### Repeat for each candidate AR: derivation and allocation record

- Candidate identifier or registered exact version: [[TODO: ar_reference]]
- Exact parent SR version, original statement and criteria: [[TODO: parent_sr_criterion]]
- Selected architecture, module, mechanism and conditions: [[TODO: architecture_module_conditions]]
- Derivation from system objective to module responsibility: [[TODO: ar_derivation_steps]]
- Calculation, diagram or argument, with budgets, units, sources and conclusion: [[TODO: ar_calculation_diagram_argument]]
- Allocation rationale, interface collaboration, tradeoffs and limits: [[TODO: ar_allocation_tradeoffs_limits]]
- Resulting complete candidate AR statement and owner: [[TODO: ar_resulting_statement_owner]]
- Verification methods, conditions and expected criteria: [[TODO: ar_verification_intent]]
- Questions and impacts on related ARs or SRs: [[TODO: ar_questions_related_impact]]

### Repeat for each parent SR: assess combined satisfaction

[[TODO: sr_to_ar_combination_argument]]

> Illustrative calculation only, not project budgets: for a serial path required to finish within 2 seconds, consider acquisition 0.8 s, processing 0.6 s, communication 0.3 s and display 0.1 s, retaining 0.2 s margin: 0.8 + 0.6 + 0.3 + 0.1 + 0.2 = 2.0 s. Candidate module ARs must justify the budgets, measurement boundaries and interface overhead. Margin is not an invented extra AR. Concurrency or queues require an appropriate critical-path or other model, not copying this sum or these values.

<!-- ipd-section:ar -->
## 6. Consolidate AR specifications and check SR coverage

**Purpose:** Record reasoned module requirements with a trace back from every row to its design basis.

**Inputs:** Individual derivations and combined SR coverage from chapter 5.

**Writing steps:**

1. Register selected ARs through the project's process and obtain exact versions. Fill behavior, inputs, outputs, constraints, responsibilities and verifiable criteria in the AR register.
2. Reference the chapter 5 record identifier or heading in relevant design and implementation cells. Mark detailed design, implementation and actual verification not yet available as planned or not run.
3. Check a rationale for every AR and a combination argument or explicit gap for every scoped SR. Retain exact primary parents and shared impact references for shared constraints rather than conflicting duplicate specifications.

**Output:** Pinned AR register, SR→AR mapping and gaps for TR4 detailed design.

[[TODO: ar]]

<!-- ipd-section:implementation_plan -->
## 7. Plan TR4 detailed design, implementation and integration

**Purpose:** Translate module requirements into executable follow-up work.

**Inputs:** AR register, high-level design and unresolved design issues.

**Writing steps:**

1. Identify detailed design content, owners, implementation tasks and dependencies by module and AR.
2. Define builds, interface integration, integration order, configuration identifiers and completion criteria, separating plans from completed work.

**Output:** TR4 work plan and detailed design entry, not a claim of completed implementation.

[[TODO: implementation_plan]]

<!-- ipd-section:verification -->
## 8. Design AR verification and regression scope

**Purpose:** Plan evidence for ARs while preserving system and user objectives.

**Inputs:** AR criteria, SR combination arguments and TR2 verification plans.

**Writing steps:**

1. Identify normal, boundary and failure cases, environments, inputs, expected results, evidence and responsibility for each AR.
2. Identify required SR combined verification, IR user acceptance and regression beyond module tests. Unexecuted work remains planned.

**Output:** AR verification and regression design linked to higher-level verification.

[[TODO: verification]]

<!-- ipd-section:deliverables -->
## 9. Compile deliverables and design gaps

**Purpose:** Make the design, specifications and supporting files locatable.

**Inputs:** Results of chapters 1–8 and actual attachments.

**Writing steps:**

1. List this document and the AR register with the SR baseline as input; add architecture views, interfaces, analyses, hardware selection and budgets as needed.
2. Identify assumptions, allocation gaps and TR4 follow-up issues, owners and plans.

**Output:** Deliverable manifest and design issue list.

[[TODO: deliverables]]

| Type / proposed necessity | Document ID / path | Exact version / digest | Requirements / scope | Owner | Status / gaps |
| --- | --- | --- | --- | --- | --- |
| [[TODO: artifact_type]] | [[TODO: artifact_path]] | [[TODO: artifact_version]] | [[TODO: covered_requirements]] | [[TODO: artifact_owner]] | [[TODO: artifact_status]] |

<!-- ipd-section:review -->
## 10. Summarize review inputs and TR4 handoff

**Purpose:** Explain readiness to enter detailed design based on the actual design and allocation.

**Inputs:** Derivations, AR coverage, verification plans and manifest.

**Writing steps:**

1. Summarize design evidence, combined SR coverage, AR responsibilities, unverified assumptions and open issues separately.
2. Identify proposed TR4 design and AR versions and plans. Reference actual decisions; populated tables or diagrams do not grant approval.

**Output:** Review summary and TR4 input package.

[[TODO: review]]

