---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'test_procedure'
template_id: 'ipd-starter.test_procedure'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# Test procedure — {{title}}

> Draft. Replace every [[TODO: ...]] with project facts. Do not invent results or approval.

<!-- ipd-section:identity -->
## Case and requirement versions

Identify stable case ID/version, exact requirement versions and verification purpose.

[[TODO: identity]]

<!-- ipd-section:setup -->
## Environment and preconditions

Record tools, configuration, data, initial state and prerequisites.

[[TODO: setup]]

<!-- ipd-section:steps -->
## Inputs, steps and expected results

Specify input, action, observable expected result, tolerance and criterion for every step.

[[TODO: steps]]

| Step | Input / precondition | Action | Expected observable result | Tolerance / pass criterion |
| --- | --- | --- | --- | --- |
| [[TODO: steps-1]] | [[TODO: steps-2]] | [[TODO: steps-3]] | [[TODO: steps-4]] | [[TODO: steps-5]] |

<!-- ipd-section:evidence -->
## Evidence capture and cleanup

Define logs, captures, raw measurements, digests and cleanup/recovery.

[[TODO: evidence]]

<!-- ipd-section:exceptions -->
## Exceptions and retest rules

Define failure, interruption, skip and retest handling; expected results are not actual outcomes.

[[TODO: exceptions]]

<!-- ipd-section:records -->
## Versioned records

| ID / version | Source / criterion | Outcome / disposition | Evidence / decision reference |
| --- | --- | --- | --- |
| [[TODO: id]] | [[TODO: criterion]] | [[TODO: unknown]] | [[TODO: evidence]] |

