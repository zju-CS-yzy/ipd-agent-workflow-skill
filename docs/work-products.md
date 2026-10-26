# Supporting work and the unified Dashboard

[English](work-products.md) | [简体中文](work-products.zh-CN.md)

Version 0.5.5 projects requirements, Deliverables, document instances and supporting files into one read-only entity index. The stage work-product graph sits immediately below the dependency graph. Both graphs and the single matrix share identities, selection and details. Every core Deliverable remains visible, including work without a requirement association.

Machine IDs use lowercase ASCII letters, digits, dot, underscore and hyphen; start with a letter or digit. Titles and people may use either language.


## Choose the governance role first

| `usage` | Choose when | Node and status |
| --- | --- | --- |
| `deliverable` | Selection, feasibility or design work needs its own Claim, review and acceptance | Create or reference a real process Deliverable. The stage graph shows that Deliverable; its files remain available in details and the matrix |
| `attachment` | A calculation, diagram, source or test file belongs within one governed result | A material node points to its one Owner. File availability never inherits a separate approval |
| `reference` | A specification, local reference copy or optional source is consulted | A reference node declares its Owner, rationale and whether it is required. Existence does not imply acceptance |

Each file still has one Owner. Multiple units can reference shared work, with one consistent role within an increment. Availability, changed content and historical context remain separate from Owner acceptance. `required` controls readiness; `execution_dependency` is a separate explicit prerequisite decision. Support and ownership edges never authorize a Claim or silently change execution order.

## Redraw an existing project

Run `ipdctl render-dashboard PROJECT` with the new version. No contract adoption is needed and canonical state, Runtime, approvals, IDs and historical Owners remain unchanged. The view joins registered facts; it cannot infer professional Deliverables from arbitrary Markdown prose. Plan explicit bindings for unregistered files.

At a safe workflow boundary, `refresh` and then `verify` regenerate and check derived views. Verification checks renderer source fingerprints, outputs and the canonical entity projection. Do not repair facts by editing generated HTML or JSON.

## Explicit adoption in a new project or increment

First enable requirements and adopt organization 1.1 following the [stage guide](stage-organization.md). Before accepting any work, preview and authorize:

```json
{"request_id":"adopt-work-v055","operation":"adopt_work_products","reason":"Explicit professional work and attachment roles","roles":[]}
```

```bash
ipdctl requirements PROJECT --request adoption.json --json > adoption-plan.json
ipdctl requirements PROJECT --apply adoption-plan.json --actor MAINTAINER --authorized
```

When current supports already exist, `roles` must classify every one with `unit`, `kind`, `target` and `usage`. An empty list is valid only when there are no current supports. Adoption records schema 1.2 / contract 0.5.5 and a hashed prior snapshot. Old clients refuse writes. Preserve an already accepted increment; adopt at the safe boundary of a new increment.

## Plan independent supporting work

This request adds independent selection work as an explicit prerequisite of the consumer. Use project-relative paths.

```json
{
  "request_id":"sensor-selection", "reason":"Two IR branches share a sensor timing argument",
  "stage":"TR2", "consumer":"plan.integrated_plan",
  "materials":[{
    "id":"plan.sensor_selection", "title":"Sensor selection and timing budget",
    "path":"docs/analysis/sensor-selection.md", "usage":"deliverable",
    "required":true, "rationale":"Supports sampling and alarm decomposition",
    "execution_dependency":true
  }]
}
```

```bash
ipdctl work-plan PROJECT --request work-request.json --json > work-plan.json
ipdctl work-plan PROJECT --check-plan work-plan.json --json
```

Both commands are zero-write. Inspect issues, readiness, the process diff, candidate extensions, bindings and stage units. State revision and all input/material fingerprints bind the preview; regenerate after changes. Active Claims/reviews, existing history, Owner conflicts, missing prerequisites and closed phases prevent direct use of candidates.

A candidate is not accepted state or a new automatic apply protocol. After reviewing it, author the extension and binding inputs in the existing `.ipd/process_extensions.yaml` and `.ipd/artifact_bindings.yaml`. Run `tailor --preview --json`, apply through the existing migration/authorization rules, and use `adopt-baseline` where needed. Preserve history. Submit candidate units through existing previewed, authorized `stage_unit` requests. All current supports require an explicit `usage` under contract 1.2.

Complete professional work through the existing `context → claim → work → close → review → human approve/reject → refresh → verify` loop. Consumers then cite the accepted supporting version, derive children individually and consolidate the conclusion/register. TR4 joins detailed design, implementation and actual execution results. A stage conclusion does not replace the independent professional review.

## Read the views

- The dependency graph shows current process Deliverables plus registered materials and documents. Prerequisite, support and ownership edges have different meanings. Filtering only changes presentation.
- Expand stage units grouped by IR to see parent requirements, supporting work, conclusions/registers and child requirements. TR4 ends with layered verification. Zoom, select and follow usage links through the common detail panel.
- The single matrix supports requirement-tree or Deliverable grouping and phase, increment, type, responsible-person, status and text filters. Historical nodes retain context and baseline links rather than borrowing current Owner acceptance.
- Details retain raw records for audit. Requirement definition/decomposition, implementation, verification, file availability and human acceptance are separate dimensions. Unknown and skipped never mean passed.

Template pack 1.3.0 still supplies 23 Markdown types in both languages. Native DOCX/XLSX, automatic historical migration, authenticated approval mapping and concurrent governance are outside this version. Public synthetic qualification does not establish private Golden or real-project acceptance.
