---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'sr_decomposition'
template_id: 'ipd-starter.sr_decomposition'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# One SR to multiple ARs: allocation argument — {{title}}

Follow the reviewed stage plan. Fill with real facts; template completion does not grant approval.

<!-- ipd-section:parent -->
## Fix this one SR input

Identify one exact SR, its criteria and its canonical IR ancestry. Follow the stage plan’s IR/SR directory grouping. Use the accepted TR2 derivation and register as input; do not require the AR set to exist before analysis.

[[TODO: parent_sr]]

<!-- ipd-section:design -->
## Develop the design basis

Reference or develop the architecture, interactions, interfaces, selection evidence and resource budgets needed for this SR. Record assumptions, versions/digests and relevant sections. Explain shared cross-SR constraints in one controlled source while documenting their applicability here.

[[TODO: design_basis]]

<!-- ipd-section:derivation -->
## Derive and allocate every AR here

For EACH AR show SR criterion → selected design/interaction → module responsibility or budget → resulting AR statement and verification bound. Provide calculations, units, timing boundaries, diagrams, failure paths and alternatives. Allocate a number through the controller. A module name alone is not a requirement.

[[TODO: each_ar_derivation]]

<!-- ipd-section:register -->
## Register the chosen ARs

Create exact canonical AR versions after derivation, then fill the companion multi-row AR register with those children only. Match its parent column to this SR and link each row to a unique argument. Detailed implementation may still be planned; do not fabricate it to fill the table.

[[TODO: ar_register_reference]]

<!-- ipd-section:coverage -->
## Check composition and hand off to TR4

Justify how the children together meet the SR: check critical paths, sums, margins, interface interactions, normal and exceptional behavior. Record remaining gaps and the detailed-design/implementation/test work required at TR4. Individual module success does not establish SR or IR acceptance.

[[TODO: combined_sr_coverage]]
