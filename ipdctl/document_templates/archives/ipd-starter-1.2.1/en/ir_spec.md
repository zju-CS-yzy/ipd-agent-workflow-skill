---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'ir_spec'
template_id: 'ipd-starter.ir_spec'
template_version: '1.1.1'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# IR initial requirements register — {{title}}

> Draft. This register covers multiple requirements, rather than one file per requirement. Two rows illustrate entry and merging; add or remove rows to match the increment. Do not invent results or approvals.

<!-- ipd-section:guidance -->
## Entry rules and baselines

Register scope and input baselines: [[TODO: register_scope_and_input_versions]]

Use one row per IR and an exact reference such as `ir-id@1`. Acceptance intent states the user outcome in its operating scenario and cites registered criterion IDs. Shared context and scenarios may span rows; retain distinct acceptance targets, owners and delivery commitments.

Use HTML `rowspan` inside Markdown to merge shared cells; update spans when adding or removing rows. Never merge requirement ID / version cells or conceal distinct criteria and responsibilities. Preserve `data-ipd-column` identifiers.

Each exact requirement reference must match the instance metadata's `requirements` list. `.ipd/requirements.yaml` holds canonical requirement facts; editing this table does not automatically change requirements, decomposition, verification results or approvals.

For downstream requirements, design, implementation or results not yet available at this stage, state not formed/not run, an owner and a planned stage; do not invent future IDs, versions or passes. Assign unique derivation record identifiers: SR scenario/constraint cells may reference TR2 rationale; AR design cells may reference TR3 rationale. Preserve stage snapshots or exact document revisions when adding later information; an unchanged requirement version does not imply an unchanged document revision.

<!-- ipd-section:register -->
## Requirements register

<table data-ipd-table="requirements">
<thead>
<tr>
<th data-ipd-column="requirement">IR ID / version</th>
<th data-ipd-column="shared_context">Source and shared context</th>
<th data-ipd-column="scenario_scope">User scenarios and scope</th>
<th data-ipd-column="statement">Initial requirement statement</th>
<th data-ipd-column="value">User value and objective</th>
<th data-ipd-column="acceptance_intent">Acceptance intent and criterion IDs</th>
<th data-ipd-column="priority">Priority and rationale</th>
<th data-ipd-column="owner">Requirement owner</th>
<th data-ipd-column="increment">Committed increment and deferred scope</th>
<th data-ipd-column="decomposition">Exact SR versions and decomposition status</th>
<th data-ipd-column="open_questions">Constraints, risks and open questions</th>
</tr>
</thead>
<tbody>
<tr>
<td>[[TODO: requirement_1]]</td>
<td rowspan="2">[[TODO: shared_context_shared]]</td>
<td rowspan="2">[[TODO: scenario_scope_shared]]</td>
<td>[[TODO: statement_1]]</td>
<td>[[TODO: value_1]]</td>
<td>[[TODO: acceptance_intent_1]]</td>
<td>[[TODO: priority_1]]</td>
<td>[[TODO: owner_1]]</td>
<td>[[TODO: increment_1]]</td>
<td>[[TODO: decomposition_1]]</td>
<td>[[TODO: open_questions_1]]</td>
</tr>
<tr>
<td>[[TODO: requirement_2]]</td>
<td>[[TODO: statement_2]]</td>
<td>[[TODO: value_2]]</td>
<td>[[TODO: acceptance_intent_2]]</td>
<td>[[TODO: priority_2]]</td>
<td>[[TODO: owner_2]]</td>
<td>[[TODO: increment_2]]</td>
<td>[[TODO: decomposition_2]]</td>
<td>[[TODO: open_questions_2]]</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## Changes, coverage and open items

Check this increment against the original sources. Explain each addition, revision, withdrawal and deferral, and link exact SR versions. Record gaps, owners and plans for incomplete decomposition; do not mark it complete.

[[TODO: coverage_changes_and_open_items]]

Explain inapplicable fields and assign owners and plans to open items. Shared content applies only to the rows covered by its span.

