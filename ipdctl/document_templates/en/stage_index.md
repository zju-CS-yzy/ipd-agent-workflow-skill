---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'stage_index'
template_id: 'ipd-starter.stage_index'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# Stage scope and work-product index — {{title}}

Follow the reviewed stage plan. Fill with real facts; template completion does not grant approval.

<!-- ipd-section:scope -->
## Establish the stage inputs

Start with the accepted parent versions and this increment’s selected criteria. List future or deferred branches separately. At TR1, record original sources while IRs are still being analyzed. This index may initially have no registered requirements; it does not invent downstream outputs.

[[TODO: scope_inputs]]

<!-- ipd-section:products -->
## Plan the work products

For each input, identify the analysis, experiments, architecture, interfaces or selection evidence actually needed. Record each instance, exact path/version or digest, Owner, role, intended conclusion and whether it is required. Shared material has one canonical instance and one Owner; list all consumers. Generate the per-parent decomposition files and registers from the reviewed stage plan.

[[TODO: work_product_plan]]

<!-- ipd-section:cross_checks -->
## Check the whole system

Review cross-parent interfaces, combined budgets, shared assumptions and conflicts. Keep the actual system architecture or budget analysis as a referenced work product. This index summarizes its conclusions; it must not concatenate all branch derivations.

[[TODO: cross_branch_checks]]

<!-- ipd-section:decisions -->
## Consolidate the stage conclusion

Link each per-parent derivation and register with exact versions and unresolved gaps. At TR4 link real implementation and executed verification, including applicable SR/IR checks. Distinguish planned, registered, structurally ready and human accepted. A complete index grants no approval.

[[TODO: stage_conclusion]]
