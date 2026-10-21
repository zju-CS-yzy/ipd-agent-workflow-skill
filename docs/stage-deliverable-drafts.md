# TR1–TR4 overall documents and requirements register drafts

Updated 2026-10-20. These **0.2.1 discussion drafts** follow the stage convention proposed for this project. They are not original Huawei QA templates and do not redefine the existing six-phase TR/DCP gates. The new types can be inspected and instantiated through `ipdctl templates`; the proposed two-document minimum is not an automatic gate rule.

See the completed [offline room-booking project](worked-projects/room-booking/index.md): 3IR→6SR→12AR, sixteen bilingual documents, individual derivations and 21 executed software cases. Its [first-use walkthrough](worked-projects/room-booking/walkthrough.md) explains added guidance for unique derivation IDs, progressive metadata and stage snapshots.

## The four overall documents

| Stage | Overall organizing document | Companion register | Focus |
| --- | --- | --- | --- |
| TR1 | [Initial requirements and feasibility](../ipdctl/document_templates/en/tr1_requirements_feasibility.md) / [中文](../ipdctl/document_templates/zh-CN/tr1_requirements_feasibility.md) | [IR register](../ipdctl/document_templates/en/ir_spec.md) / [中文](../ipdctl/document_templates/zh-CN/ir_spec.md) | Sources, context, users, scenarios, scope, alternatives, feasibility and increment objectives; establish IRs |
| TR2 | [Scenario analysis and module allocation](../ipdctl/document_templates/en/tr2_scenarios_allocation.md) / [中文](../ipdctl/document_templates/zh-CN/tr2_scenarios_allocation.md) | [SR register](../ipdctl/document_templates/en/sr_spec.md) / [中文](../ipdctl/document_templates/zh-CN/sr_spec.md) | Analyze normal and exceptional scenarios, boundaries, responsibilities and allocation from IRs; establish SRs |
| TR3 | [High-level design and AR allocation](../ipdctl/document_templates/en/tr3_high_level_design.md) / [中文](../ipdctl/document_templates/zh-CN/tr3_high_level_design.md) | [AR register](../ipdctl/document_templates/en/ar_spec.md) / [中文](../ipdctl/document_templates/zh-CN/ar_spec.md) | Architecture, interactions, interfaces, budgets, AR allocation and next-stage planning based on TR2 |
| TR4 | [Detailed design, implementation, testing and acceptance](../ipdctl/document_templates/en/tr4_detail_implementation_test.md) / [中文](../ipdctl/document_templates/zh-CN/tr4_detail_implementation_test.md) | Update the same [AR register](../ipdctl/document_templates/en/ar_spec.md) with implementation and verification traceability | Detailed design index, implementation, build, integration, AR verification, SR system verification, IR acceptance, defects and regression |

The overall document explains analysis, tradeoffs, relationships and stage conclusions. Registers manage individual specifications and traceability. Connect them through paths and exact versions instead of repeating shared context in a file per requirement. IR/SR/AR remain three requirement levels; TR4 adds no fourth level.

Each overall draft has a deliverable manifest for IDs, paths, exact versions or digests, covered scope, owners and gaps. The proposed minimum is the overall document plus its register. Actual design, implementation and verification evidence remain necessary for applicable scope; two documents do not replace them. Hardware selection, interface design and experiments are optional additions according to project needs. Large analyses or designs can be split by module, with an overall index and complete increment coverage.

## First-use writing sequence

Each draft explains where to start, and each chapter states its purpose, inputs, writing steps and outputs. A downstream register need not exist when writing begins: develop candidates through analysis, then register and consolidate them through the project's process.

| Stage | Where analysis and requirement development happen | Where results are consolidated |
| --- | --- | --- |
| TR1 | Chapters 2–3 analyze problems and scenarios; chapter 4 develops each candidate IR from sources; chapter 5 examines feasibility and revises candidates | Chapter 6 consolidates IRs and checks source coverage |
| TR2 | Chapter 2 establishes scenarios and boundaries; **chapter 3 derives each SR from its IR** | Chapter 4 records SRs, points back to individual derivations and checks IR coverage |
| TR3 | Chapters 2–4 establish architecture, mechanisms and budgets; **chapter 5 derives and allocates each AR from its SR** | Chapter 6 records ARs, points back to derivations and checks combined SR coverage |
| TR4 | Chapter 2 develops detailed design against ARs; chapter 3 records actual implementation and builds; chapters 4–5 execute distinct verification levels | Chapter 4 updates the same AR register with design, implementation and evidence traceability |

Repeat TR2/TR3 records for the actual number of child requirements. Each record identifies the parent version and objective, scenario or design premises, derivation steps, calculation/diagram/argument, thresholds and tradeoffs, resulting statement, verification criteria and open questions. Quantities need assumptions, variables, units and sources. Rules, interfaces and failure handling may use states, sequences or counterexamples rather than meaningless formulae. Shared analysis can be written once, but each child must explain how it supports its content.

Also assess the entire child set against each parent. For example, reconcile timing totals or critical paths and margin; separately passing ARs do not automatically establish an SR. Short examples illustrate reasoning, not project facts, budgets or results. Structural lint checks sections, columns and filled content; it does not establish correct or sufficient reasoning.

## Multi-row specifications

`ir_spec/sr_spec/ar_spec` are now **1.1.1 register templates**. Two starter rows illustrate entry; projects may add or remove rows without a fixed count or a separate file per requirement. Each row has one exact `id@version`, and the instance metadata's `requirements` list includes every covered version.

- IR columns cover source and shared context, user scenarios and scope, statement, value, acceptance intent, priority, owner, increment and SR decomposition.
- SR columns cover parent IR, scenarios, behavior, measures and bounds, interfaces, constraints, module allocation, system verification, responsibilities and AR allocation.
- AR columns cover parent SR, allocated module, responsibility, behavior and constraints, interfaces and budgets, design and implementation, verification criteria, actual results and evidence, and regression.

Markdown pipe tables do not support merged cells, so these `.md` assets embed HTML tables. Use `rowspan` for shared context, scenarios or parent references and update spans when adding, deleting or splitting rows. Never merge requirement ID/version cells or obscure distinct criteria, outcomes, owners or commitments. Share only content that actually applies to every covered row. Rendering needs a Markdown viewer that permits HTML. Lint expands spans before checking columns and requirement references.

Use `<br>` for line breaks inside cells and escape literal `<`, `>` and `&` as HTML entities. Do not rely on Markdown syntax being rendered within HTML cells.

`.ipd/requirements.yaml` remains canonical. Registers are versioned analysis and delivery documents; editing their text does not automatically modify canonical requirements, execute verification or record approval. Structure, actual results and stage decisions remain separate. Unresolved, not run, failed, skipped and stale work must not be described as passed.

## Versions and use

The active `ipd-starter@1.2.1` pack contains 18 types and 36 bilingual files: three registers, four overall stage drafts and eleven existing specialized types. Packs `1.0.0`, `1.1.0` and `1.2.0` remain archived unchanged for existing pins. Stage drafts have template version `0.2.1`, registers `1.1.1`, and other unchanged types `1.0.0`. Packs do not switch automatically after instance creation; adoption follows existing pinning and increment boundaries.

```console
ipdctl templates --type ir_spec --locale en
ipdctl templates --type tr1_requirements_feasibility --locale en
ipdctl templates --type tr3_high_level_design --locale zh-CN
```

See [requirements and templates](requirements-and-templates.md) for operations. Further discussion can refine chapter depth, hardware differences and review checklists before adopting formal stage obligations.

## Public references and limits

These original drafts draw on publicly accessible outlines and document requirements:

- [NASA annotated ConOps outline](https://www.nasa.gov/reference/appendix-s-concept-of-operations-annotated-outline/): operating context, stakeholders, scenarios, boundaries, alternatives and impacts for TR1.
- [ECSS technical requirements specification and Annex A document requirements](https://ecss.nl/standard/ecss-e-st-10-06c-technical-requirements-specification/): purpose, input references and specification structure.
- [NASA public software design description outline](https://swehb.nasa.gov/spaces/SWEHBVC/pages/50888776/5.13%2B-%2BSwDD%2B-%2BSoftware%2BDesign%2BDescription): architecture, modules, interfaces, rationale, detailed design and traceability for TR3/TR4. Internal restricted templates mentioned there were neither retrieved nor copied.
- [NASA requirements verification matrix](https://www.nasa.gov/reference/appendix-d-requirements-verification-matrix/): exact requirement identifiers and verification traceability.
- [Huawei CodeArts Req concepts](https://support.huaweicloud.com/intl/zh-cn/productdesc-projectman/codeartsreq_07_2008.html): IR/SR/AR hierarchy.

The references do not establish a universal TR1–TR4 mapping or certify this Skill. The stage convention comes from the user's training experience and remains open for refinement.
