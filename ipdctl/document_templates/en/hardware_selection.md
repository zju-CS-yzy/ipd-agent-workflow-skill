---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'hardware_selection'
template_id: 'ipd-starter.hardware_selection'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# Hardware selection evidence — {{title}}

Follow the reviewed stage plan. Fill with real facts; template completion does not grant approval.

<!-- ipd-section:constraints -->
## Derive selection constraints

Start with exact input requirements, operating conditions, interfaces and budgets. Identify mandatory bounds and assumptions before comparing parts.

[[TODO: selection_constraints]]

<!-- ipd-section:comparison -->
## Compare evidence for candidates

Record candidate revisions, datasheet/test sources and content digests. Compare relevant limits under the actual conditions; distinguish measured facts, specifications and estimates.

[[TODO: candidate_evidence]]

<!-- ipd-section:decision -->
## Explain the selected option

Show calculations, tradeoffs, margins, interfaces and risks. Explain which IR→SR or SR→AR conclusions this evidence supports and link every consuming unit. Selection alone does not approve the requirements.

[[TODO: selection_argument]]

<!-- ipd-section:validation -->
## State validation and open work

Record actual prototype evidence where available, uncertainty, owner and planned verification. An unperformed check remains unperformed.

[[TODO: selection_validation]]
