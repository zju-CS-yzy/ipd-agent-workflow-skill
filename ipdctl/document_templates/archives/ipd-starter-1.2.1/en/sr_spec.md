---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'sr_spec'
template_id: 'ipd-starter.sr_spec'
template_version: '1.1.1'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# SR system requirements register — {{title}}

> Draft. This register covers multiple requirements, rather than one file per requirement. Two rows illustrate entry and merging; add or remove rows to match the increment. Do not invent results or approvals.

<!-- ipd-section:guidance -->
## Entry rules and baselines

Register scope and input baselines: [[TODO: register_scope_and_input_versions]]

Use one row per SR and cite the exact parent IR version. Translate scenarios into verifiable system behavior, performance bounds and module allocation. State criterion IDs, conditions and expected values for system verification; module tests alone do not establish system verification. Explain registered derived SRs rather than inventing parent links.

Use HTML `rowspan` inside Markdown to merge shared cells; update spans when adding or removing rows. Never merge requirement ID / version cells or conceal distinct criteria and responsibilities. Preserve `data-ipd-column` identifiers.

Each exact requirement reference must match the instance metadata's `requirements` list. `.ipd/requirements.yaml` holds canonical requirement facts; editing this table does not automatically change requirements, decomposition, verification results or approvals.

For downstream requirements, design, implementation or results not yet available at this stage, state not formed/not run, an owner and a planned stage; do not invent future IDs, versions or passes. Assign unique derivation record identifiers: SR scenario/constraint cells may reference TR2 rationale; AR design cells may reference TR3 rationale. Preserve stage snapshots or exact document revisions when adding later information; an unchanged requirement version does not imply an unchanged document revision.

<!-- ipd-section:register -->
## Requirements register

<table data-ipd-table="requirements">
<thead>
<tr>
<th data-ipd-column="requirement">SR ID / version</th>
<th data-ipd-column="parent">Exact parent IR version</th>
<th data-ipd-column="scenario_scope">Scenarios, triggers and exceptions</th>
<th data-ipd-column="system_behavior">System behavior and outputs</th>
<th data-ipd-column="measures_limits">Measures and boundary conditions</th>
<th data-ipd-column="interfaces_constraints">Interfaces, constraints and quality requirements</th>
<th data-ipd-column="module_allocation">Module allocation and collaboration</th>
<th data-ipd-column="verification">System verification methods and criteria</th>
<th data-ipd-column="priority_owner">Priority, rationale and owner</th>
<th data-ipd-column="increment_status">Increment, maturity and deferred scope</th>
<th data-ipd-column="child_ar">Exact AR versions and allocation gaps</th>
</tr>
</thead>
<tbody>
<tr>
<td>[[TODO: requirement_1]]</td>
<td rowspan="2">[[TODO: parent_shared]]</td>
<td rowspan="2">[[TODO: scenario_scope_shared]]</td>
<td>[[TODO: system_behavior_1]]</td>
<td>[[TODO: measures_limits_1]]</td>
<td>[[TODO: interfaces_constraints_1]]</td>
<td>[[TODO: module_allocation_1]]</td>
<td>[[TODO: verification_1]]</td>
<td>[[TODO: priority_owner_1]]</td>
<td>[[TODO: increment_status_1]]</td>
<td>[[TODO: child_ar_1]]</td>
</tr>
<tr>
<td>[[TODO: requirement_2]]</td>
<td>[[TODO: system_behavior_2]]</td>
<td>[[TODO: measures_limits_2]]</td>
<td>[[TODO: interfaces_constraints_2]]</td>
<td>[[TODO: module_allocation_2]]</td>
<td>[[TODO: verification_2]]</td>
<td>[[TODO: priority_owner_2]]</td>
<td>[[TODO: increment_status_2]]</td>
<td>[[TODO: child_ar_2]]</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## Changes, coverage and open items

Check SR coverage, missing scenarios and conflicts against this increment's IRs. Record allocation rationale, cross-module interfaces and AR gaps. Row counts do not establish coverage.

[[TODO: coverage_changes_and_open_items]]

Explain inapplicable fields and assign owners and plans to open items. Shared content applies only to the rows covered by its span.

