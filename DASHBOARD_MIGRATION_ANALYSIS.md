# Dashboard Rendering Pipeline Migration Analysis

## Scope and conclusion

The v1.4 quadruped perception example is a Golden Reference for information
hierarchy, layout language, and interaction behavior. It is not a reusable
runtime dependency. The current framework therefore restores the rendering
pipeline from contracts and observable output characteristics without copying
the example's generated HTML, JSON, SVG, or screenshots.

The surviving v1.4 package does not contain the original Dashboard renderer.
It contains callers, an output contract, and generated artifacts. The restored
pipeline must consequently be a clean implementation that preserves the
Golden Reference's visual grammar while using the current canonical process,
project state, Agent runtime, and task-profile locale as its source of truth.

## v1.4 Dashboard generation chain

The recoverable chain is:

1. A project deployment wrapper prepared the project workspace.
2. `scripts/tailor_ipd.py` was expected to compile a task profile against an
   IPD master model and tailoring rules.
3. `scripts/update_project_state.py refresh` was expected to reconcile process,
   state, runtime, repository, and evidence facts.
4. The missing refresh renderer produced the project Dashboard and dependency
   graph artifacts.
5. `scripts/ipdctl.py` could inject an Agent claim panel into an already
   generated Dashboard; it was not the primary renderer.

The deployment wrapper references the following missing implementation inputs:

- `scripts/tailor_ipd.py`
- `scripts/update_project_state.py`
- `references/ipd_master_model.yaml`
- `references/tailoring_rules.yaml`

`references/output_contract_v1_4.yaml` confirms that the Dashboard was a
derived view of process, state, and runtime facts. It does not preserve the
layout implementation.

## Golden Reference inventory

`examples/quadruped_perception_fusion/generated/` contains six files:

- one Dashboard HTML document;
- one dependency graph JSON document;
- one Markdown graph index;
- three SVG dependency graphs;
- no PNG files.

The adjacent review demonstration adds another Dashboard HTML document and one
SVG. These are generated project outputs and remain outside this framework.

The reusable high-volume data source is the dependency graph JSON. It contains
286 deliverables and 144 hard dependency edges across four legacy stages. The
original task profile, tailored process, project state, and artifact bindings
are absent, so the v1.4 example cannot be replayed through `ipdctl init`,
`tailor`, and `refresh` with identical source inputs.

## Observable rendering behavior

The v1.4 Dashboard establishes the following visual and interaction baseline:

- a wide project header and compact status summary;
- stage navigation with a clearly emphasized current stage;
- a phase-oriented IPD flow with swimlanes;
- distinct TR, DCP, and Gate shapes;
- status color, border, and badge semantics;
- a current-stage deliverable dependency view;
- Gate/TR/DCP and deliverable matrices;
- click-through navigation from graph nodes to matching detail rows;
- phase, status, type, and text filters;
- graph zoom controls and an in-diagram legend.

The overview flow is a hand-positioned SVG. The standalone legacy deliverable
graphs contain Graphviz 2.42.4 signatures. The restored implementation does
not invoke Graphviz because the migration requirement explicitly calls for a
controlled hierarchical layout rather than the default Graphviz layout.

## Missing modules in v0.2 before restoration

The pre-restoration v0.2 Dashboard implementation is a deterministic, hashed,
read-only projection, but it lacks the execution-quality presentation layer:

- no canonical nested Dashboard output tree;
- no standalone SVG assets;
- no unified typed graph for Phase, TR, DCP, Gate, Activity, and Deliverable;
- no stage swimlanes or hierarchical rank assignment;
- no text measurement or wrapping strategy;
- no crossing reduction or orthogonal edge routing;
- no node-type shapes, relation styles, status palette, or legend;
- no current-phase, blocker, or next-task visual emphasis;
- no node detail interaction;
- no review-history presentation;
- no large-graph Golden test adapter;
- no stale-output cleanup at the Dashboard tree boundary.

## Restoration plan

The restored pipeline is divided into four deterministic layers:

1. **Projection model** — normalize tailored process, project state, and Agent
   runtime facts into `data/state.json` and a typed `data/graph.json`.
2. **Layout and SVG rendering** — assign phase swimlanes and hierarchy ranks,
   reduce crossings deterministically, route orthogonal edges, wrap labels,
   render special checkpoint shapes, and include an explicit legend.
3. **HTML presentation** — reproduce the Golden Reference's information
   hierarchy with status summary, process and current-state diagrams, phase
   views, matrices, filters, zoom, and accessible detail navigation.
4. **Publishing and verification** — render a complete staging tree, hash all
   managed outputs in `manifest.json`, replace stale generated content, and
   retain byte-for-byte determinism.

The canonical output is `.ipd/dashboard/` with the requested `assets/`,
`phases/`, `matrices/`, and `data/` subdirectories. It contains fourteen
managed outputs plus `manifest.json`, for fifteen files in total. The manifest
records the presentation locale, source revision, and managed-output hashes so
`ipdctl verify` can detect missing, modified, or stale output.

Phase files are generated from the tailored process. All six framework Phase
files (`concept`, `plan`, `develop`, `qualify`, `launch`, and `lifecycle`) are
required outputs. The final Phase is therefore visible rather than being
silently dropped from the Dashboard.

## Language policy

Language is a presentation choice, not a second contract. Framework-owned CLI,
HTML, SVG, legend, matrix, and status labels use
`.ipd/task_profile.yaml` at `presentation.locale`; supported values are `en`
and `zh-CN`, and a missing field defaults to `en`. The selected locale is
recorded in `manifest.json` and changing it requires `refresh` followed by
`verify`.

Commands, options, filenames, IDs, JSON/YAML keys, enum values, statuses,
relations, event names, graph topology, and report codes remain English in both
locales. User-authored names, descriptions, paths, and evidence are preserved
verbatim rather than machine-translated. This allows the Chinese v1.4 Golden
artifacts to be used for structural comparison without copying their text into
new generated output.

## Golden comparison policy

The Golden test compares structure and capability rather than byte or pixel
identity:

- inventory and file types;
- SVG and Dashboard structure;
- source and rendered node/edge counts;
- current state and blocker presentation;
- interaction targets and detail completeness;
- non-overlapping layout metadata;
- deterministic output and manifest integrity;
- high-cardinality rendering using the external legacy JSON in memory.

The test does not copy the legacy instance into this repository and does not
claim an end-to-end v1.4 replay because the original source inputs are missing.

## v0.5.1 replacement qualification policy

The unavailable original v1.4 fixture is a historical migration reference, not
an active release dependency. The current release gate uses a frozen external
real v0.5.0 project with `scripts/verify_local_golden.py`, preserving its known
verification failures and governance history in independent copies. Fixtures,
expected private facts and detailed results remain outside Git. A self-contained
300-node renderer regression and bilingual actual-browser checks independently
cover scale and interaction behavior in CI. These gates do not claim identity
with, or reconstruction of, the original external reference.
