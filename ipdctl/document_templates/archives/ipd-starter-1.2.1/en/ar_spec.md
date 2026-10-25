---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'ar_spec'
template_id: 'ipd-starter.ar_spec'
template_version: '1.1.1'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# AR allocated requirements register — {{title}}

> Draft. This register covers multiple requirements, rather than one file per requirement. Two rows illustrate entry and merging; add or remove rows to match the increment. Do not invent results or approvals.

<!-- ipd-section:guidance -->
## Entry rules and baselines

Register scope and input baselines: [[TODO: register_scope_and_input_versions]]

Use one row per AR and cite the exact parent SR version. TR3 records allocation and high-level design references; TR4 adds detailed design, implementation versions and actual verification evidence. Mark work not yet executed with its plan, never as passed. Keep expected criteria, actual results and evidence distinct.

Use HTML `rowspan` inside Markdown to merge shared cells; update spans when adding or removing rows. Never merge requirement ID / version cells or conceal distinct criteria and responsibilities. Preserve `data-ipd-column` identifiers.

Each exact requirement reference must match the instance metadata's `requirements` list. `.ipd/requirements.yaml` holds canonical requirement facts; editing this table does not automatically change requirements, decomposition, verification results or approvals.

For downstream requirements, design, implementation or results not yet available at this stage, state not formed/not run, an owner and a planned stage; do not invent future IDs, versions or passes. Assign unique derivation record identifiers: SR scenario/constraint cells may reference TR2 rationale; AR design cells may reference TR3 rationale. Preserve stage snapshots or exact document revisions when adding later information; an unchanged requirement version does not imply an unchanged document revision.

<!-- ipd-section:register -->
## Requirements register

<table data-ipd-table="requirements">
<thead>
<tr>
<th data-ipd-column="requirement">AR ID / version</th>
<th data-ipd-column="parent">Exact parent SR version</th>
<th data-ipd-column="assigned_module">Allocated module and shared design context</th>
<th data-ipd-column="responsibility">Responsibility boundary and owner</th>
<th data-ipd-column="behavior_constraints">Module behavior, inputs, outputs and constraints</th>
<th data-ipd-column="interfaces_budget">Interfaces, resource budgets and failure handling</th>
<th data-ipd-column="design_implementation">High-level / detailed design and implementation versions</th>
<th data-ipd-column="verification">Module verification methods, criterion IDs and expected values</th>
<th data-ipd-column="result_evidence">Actual results, evidence versions and defects</th>
<th data-ipd-column="regression">Impact and regression scope</th>
<th data-ipd-column="increment_status">Increment, maturity and deferred scope</th>
</tr>
</thead>
<tbody>
<tr>
<td>[[TODO: requirement_1]]</td>
<td rowspan="2">[[TODO: parent_shared]]</td>
<td rowspan="2">[[TODO: assigned_module_shared]]</td>
<td>[[TODO: responsibility_1]]</td>
<td>[[TODO: behavior_constraints_1]]</td>
<td>[[TODO: interfaces_budget_1]]</td>
<td>[[TODO: design_implementation_1]]</td>
<td>[[TODO: verification_1]]</td>
<td>[[TODO: result_evidence_1]]</td>
<td>[[TODO: regression_1]]</td>
<td>[[TODO: increment_status_1]]</td>
</tr>
<tr>
<td>[[TODO: requirement_2]]</td>
<td>[[TODO: responsibility_2]]</td>
<td>[[TODO: behavior_constraints_2]]</td>
<td>[[TODO: interfaces_budget_2]]</td>
<td>[[TODO: design_implementation_2]]</td>
<td>[[TODO: verification_2]]</td>
<td>[[TODO: result_evidence_2]]</td>
<td>[[TODO: regression_2]]</td>
<td>[[TODO: increment_status_2]]</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## Changes, coverage and open items

Check SR→AR allocation completeness and conflicting responsibilities. Record design, code and test versions, defects and regression scope. Passing AR verification does not establish SR system verification or IR user acceptance.

[[TODO: coverage_changes_and_open_items]]

Explain inapplicable fields and assign owners and plans to open items. Shared content applies only to the rows covered by its span.

