---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'ir_decomposition'
template_id: 'ipd-starter.ir_decomposition'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# One IR to multiple SRs: decomposition argument — {{title}}

Follow the reviewed stage plan. Fill with real facts; template completion does not grant approval.

<!-- ipd-section:parent -->
## Understand this one parent IR

Identify exactly one IR version, its original statement, selected criteria, users, boundaries and deferred scope. Obtain it from the stage plan and canonical registry. Read the shared TR1 context by reference rather than copying it. The SRs may not exist yet.

[[TODO: parent_ir]]

<!-- ipd-section:support -->
## Analyze scenarios and supporting facts

Identify normal, exceptional and boundary scenarios. For every source, selection, prototype or design assumption record its version/digest, relevant section, result, limitation and why it supports this IR’s decomposition. Reuse a shared controlled instance instead of duplicating it.

[[TODO: supporting_analysis]]

<!-- ipd-section:derivation -->
## Derive each candidate SR here

Repeat a uniquely identified argument for EACH child: parent objective → scenario and assumptions → system responsibility or measurable bound → proposed SR statement → verification criterion. Give units, formulae, data sources, diagrams or logical argument as appropriate. Explain alternatives and open questions. Ask the numbering plan for a child code; registration and approval are separate.

[[TODO: each_sr_derivation]]

<!-- ipd-section:register -->
## Register and consolidate the SR set

After derivation, register the chosen candidates and cite their exact id@version values. Fill the companion multi-row SR register with ONLY these children; its parent column must match the canonical IR. Link every row back to its argument anchor. Inputs and output rows are different sets. If the conclusion draft’s coverage grows, explicitly revise the managed instance into a new file.

[[TODO: sr_register_reference]]

<!-- ipd-section:coverage -->
## Justify combined coverage and finalize

Show how the selected children together address this IR’s applicable normal, exceptional and boundary criteria. Identify omissions, overlap, conflicts, system dependencies and deferred criteria. Resolve required support gaps before finalization. The file can be drafted early and revised; its final version is the stage conclusion, not an automatic human approval.

[[TODO: combined_ir_coverage]]
