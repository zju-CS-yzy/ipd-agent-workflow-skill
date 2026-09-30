# Dashboard Golden Test Report

**Overall result: PASS** — en: 25/25; zh-CN: 25/25.

## Scope and limitation

The v1.4 Golden Reference is read directly from the external `quadruped_perception_fusion/generated` directory. No Golden artifact is copied into this repository. The surviving example does not include its original task profile, tailored process, project state, or dashboard renderer. Therefore, this is an output-derived structural renderer test plus a separate current-version CLI lifecycle test; it is not claimed to be a same-source end-to-end reproduction.

Legacy graph source: external v1.4 Golden Reference `generated/deliverable_dependency_graph.json`

The hashes below identify the exact external fixture used for this run. They are evidence of fixture identity, not a claim that the missing v1.4 source inputs were reconstructed.

- Dependency graph SHA-256: `a3aa76dc6c37335e5ba1831311134c01b21e53052f79f44c4091986d099e155e`
- Generated inventory SHA-256: `d3b76bba1fa899897929ce7cd84df0190f49d3b8780ae135b3a910a6a1d5f50e`
- Fingerprinted inventory entries: 6

## Golden Reference inventory

| Metric | Observed | Expected |
| --- | ---: | ---: |
| Files | 6 | 6 |
| Html | 1 | 1 |
| Json | 1 | 1 |
| Markdown | 1 | 1 |
| Svg | 3 | 3 |
| Png | 0 | 0 |

## Graph scale

| Metric | Observed | Expected |
| --- | ---: | ---: |
| Nodes | 286 | 286 |
| Internal Edges | 144 | 144 |
| External Prerequisites | 31 | 31 |

The normalized Golden graph is rendered in memory through the current custom SVG renderer. External prerequisites are counted but are not fabricated into nodes, preserving the 286-node render scale.

## Locale summary

| Locale | Result | Passed | Total | Structure fingerprint |
| --- | --- | ---: | ---: | --- |
| `en` | PASS | 25 | 25 | `c5b717a38ed189ba8b540e0a7060927c70b5479604f14ce983211204b52f401b` |
| `zh-CN` | PASS | 25 | 25 | `c5b717a38ed189ba8b540e0a7060927c70b5479604f14ce983211204b52f401b` |

## Locale `en`

**PASS — 25 of 25 checks passed.**

### Current dashboard results

- Structure fingerprint: `c5b717a38ed189ba8b540e0a7060927c70b5479604f14ce983211204b52f401b`
- Files: 15
- File types: `{".html": 3, ".json": 3, ".svg": 9}`
- SVG: 9
- HTML: 3
- JSON: 3
- Graph nodes: 48
- Graph edges: 87
- Node types: `Activity, DCP, Deliverable, Gate, Phase, TR`
- Relations: `depends_on, supports, verifies`
- Declared relation capability: `depends_on, supersedes, supports, verifies`
- Statuses: `in_progress, planned`

### Check results

| Result | Check | Evidence |
| --- | --- | --- |
| PASS | Legacy artifact inventory | files=6, html=1, json=1, markdown=1, svg=3, png=0 |
| PASS | Legacy graph scale | nodes=286, internal_edges=144, external_prerequisites=31 |
| PASS | Golden SVG parses as XML | ElementTree parse |
| PASS | Golden SVG is custom-rendered | No Graphviz signature |
| PASS | Golden SVG has no same-lane node overlaps | bbox_nodes=286, overlaps=0 |
| PASS | CLI lifecycle: software | init -> tailor -> refresh -> verify |
| PASS | CLI lifecycle: hardware | init -> tailor -> refresh -> verify |
| PASS | CLI lifecycle: embedded | init -> tailor -> refresh -> verify |
| PASS | CLI lifecycle: robotics | init -> tailor -> refresh -> verify |
| PASS | CLI lifecycle: ai_system | init -> tailor -> refresh -> verify |
| PASS | CLI lifecycle: material_change | init -> tailor -> refresh -> verify |
| PASS | Target dashboard inventory | files=15 |
| PASS | Required SVG set | required=8, actual=9; additional lifecycle views are allowed |
| PASS | Dashboard HTML structure | html=3 |
| PASS | SVG XML validity | errors=0 |
| PASS | No Graphviz signature | files=[] |
| PASS | No same-lane overlap | files=[] |
| PASS | Generated text matches selected locale | locale=en, violations=[] |
| PASS | No unresolved localization keys | files=[] |
| PASS | Dashboard manifest locale | expected=en, actual=en |
| PASS | Localized HTML, SVG, and Matrix markers | locale=en |
| PASS | Interactive node details | {'node_links': True, 'hash_navigation': True, 'detail_panel': True, 'dependencies': True, 'evidence': True, 'review_history': True} |
| PASS | Typed graph nodes | ['Activity', 'DCP', 'Deliverable', 'Gate', 'Phase', 'TR'] |
| PASS | Typed graph relation capability | declared=['depends_on', 'supersedes', 'supports', 'verifies']; observed=['depends_on', 'supports', 'verifies'] |
| PASS | State is displayed | ['in_progress', 'planned'] |

### CLI commands

- `software`: `ipdctl init . --name Golden software --task-type software --locale en -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)
- `hardware`: `ipdctl init . --name Golden hardware --task-type hardware --locale en -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)
- `embedded`: `ipdctl init . --name Golden embedded --task-type embedded --locale en -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)
- `robotics`: `ipdctl init . --name Golden robotics --task-type robotics --locale en -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)
- `ai_system`: `ipdctl init . --name Golden ai_system --task-type ai_system --locale en -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)
- `material_change`: `ipdctl init . --name Golden material_change --task-type material_change --locale en -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)

## Locale `zh-CN`

**PASS — 25 of 25 checks passed.**

### Current dashboard results

- Structure fingerprint: `c5b717a38ed189ba8b540e0a7060927c70b5479604f14ce983211204b52f401b`
- Files: 15
- File types: `{".html": 3, ".json": 3, ".svg": 9}`
- SVG: 9
- HTML: 3
- JSON: 3
- Graph nodes: 48
- Graph edges: 87
- Node types: `Activity, DCP, Deliverable, Gate, Phase, TR`
- Relations: `depends_on, supports, verifies`
- Declared relation capability: `depends_on, supersedes, supports, verifies`
- Statuses: `in_progress, planned`

### Check results

| Result | Check | Evidence |
| --- | --- | --- |
| PASS | Legacy artifact inventory | files=6, html=1, json=1, markdown=1, svg=3, png=0 |
| PASS | Legacy graph scale | nodes=286, internal_edges=144, external_prerequisites=31 |
| PASS | Golden SVG parses as XML | ElementTree parse |
| PASS | Golden SVG is custom-rendered | No Graphviz signature |
| PASS | Golden SVG has no same-lane node overlaps | bbox_nodes=286, overlaps=0 |
| PASS | CLI lifecycle: software | init -> tailor -> refresh -> verify |
| PASS | CLI lifecycle: hardware | init -> tailor -> refresh -> verify |
| PASS | CLI lifecycle: embedded | init -> tailor -> refresh -> verify |
| PASS | CLI lifecycle: robotics | init -> tailor -> refresh -> verify |
| PASS | CLI lifecycle: ai_system | init -> tailor -> refresh -> verify |
| PASS | CLI lifecycle: material_change | init -> tailor -> refresh -> verify |
| PASS | Target dashboard inventory | files=15 |
| PASS | Required SVG set | required=8, actual=9; additional lifecycle views are allowed |
| PASS | Dashboard HTML structure | html=3 |
| PASS | SVG XML validity | errors=0 |
| PASS | No Graphviz signature | files=[] |
| PASS | No same-lane overlap | files=[] |
| PASS | Generated text matches selected locale | locale=zh-CN, violations=[] |
| PASS | No unresolved localization keys | files=[] |
| PASS | Dashboard manifest locale | expected=zh-CN, actual=zh-CN |
| PASS | Localized HTML, SVG, and Matrix markers | locale=zh-CN |
| PASS | Interactive node details | {'node_links': True, 'hash_navigation': True, 'detail_panel': True, 'dependencies': True, 'evidence': True, 'review_history': True} |
| PASS | Typed graph nodes | ['Activity', 'DCP', 'Deliverable', 'Gate', 'Phase', 'TR'] |
| PASS | Typed graph relation capability | declared=['depends_on', 'supersedes', 'supports', 'verifies']; observed=['depends_on', 'supports', 'verifies'] |
| PASS | State is displayed | ['in_progress', 'planned'] |

### CLI commands

- `software`: `ipdctl init . --name Golden software --task-type software --locale zh-CN -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)
- `hardware`: `ipdctl init . --name Golden hardware --task-type hardware --locale zh-CN -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)
- `embedded`: `ipdctl init . --name Golden embedded --task-type embedded --locale zh-CN -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)
- `robotics`: `ipdctl init . --name Golden robotics --task-type robotics --locale zh-CN -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)
- `ai_system`: `ipdctl init . --name Golden ai_system --task-type ai_system --locale zh-CN -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)
- `material_change`: `ipdctl init . --name Golden material_change --task-type material_change --locale zh-CN -> ipdctl tailor -> ipdctl refresh -> ipdctl verify` (PASS)

## Conclusion

**PASS** — en: 25/25; zh-CN: 25/25.

Reproduce the bilingual formal report with one command:

```text
python scripts/dashboard_golden_test.py --legacy-root <v1.4-example-or-generated-directory> --locale both
```

Use `--locale en` or `--locale zh-CN` only when a single-locale diagnostic report is desired.
