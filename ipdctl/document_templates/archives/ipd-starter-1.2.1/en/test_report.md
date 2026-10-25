---
instance_id: '{{instance_id}}'
increment: '{{increment}}'
requirements: '{{requirements}}'
owner: '{{owner}}'
document_type: 'test_report'
template_id: 'ipd-starter.test_report'
template_version: '1.0.0'
template_sha256: '{{template_sha256}}'
locale: 'en'
scope: '{{scope}}'
---

# Test report — {{title}}

> Draft. Replace every [[TODO: ...]] with project facts. Do not invent results or approval.

<!-- ipd-section:subject -->
## Test baseline and execution configuration

Record actual subject version, environment, tools, data and executor.

[[TODO: subject]]

<!-- ipd-section:results -->
## Actual case results

Record case version, actual result, outcome and immutable evidence; never mark unexecuted cases passed.

[[TODO: results]]

| Case version | Requirement / criterion | Actual result | Outcome (passed/failed/skipped/unknown) | Evidence digest |
| --- | --- | --- | --- | --- |
| [[TODO: results-1]] | [[TODO: results-2]] | [[TODO: results-3]] | [[TODO: results-4]] | [[TODO: results-5]] |

<!-- ipd-section:defects -->
## Defects, deviations and retests

Link defects, severity, disposition, fix versions and retest evidence.

[[TODO: defects]]

<!-- ipd-section:coverage -->
## Requirement coverage and limitations

Count passed, failed, skipped, unknown and uncovered requirements separately.

[[TODO: coverage]]

<!-- ipd-section:conclusion -->
## Conclusion and open decisions

Conclude only from actual evidence; human approval belongs to the governed Review.

[[TODO: conclusion]]

<!-- ipd-section:records -->
## Versioned records

| ID / version | Source / criterion | Outcome / disposition | Evidence / decision reference |
| --- | --- | --- | --- |
| [[TODO: id]] | [[TODO: criterion]] | [[TODO: unknown]] | [[TODO: evidence]] |

