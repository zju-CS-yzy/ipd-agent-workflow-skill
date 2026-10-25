# 0.5.4: organize stage work by parent requirement

Adoption is explicit. Organized registries use schema 1.1 / contract 0.5.4; core state remains 2.0 and model-enabled Runtime remains 1.1. Legacy 0.5.3 registries retain their behavior. Parentage and authority are never inferred from names or directories.

## Start with the current context

Run `ipdctl context . --json` and identify the increment, Phase, active Claim, Gate and canonical Owner IDs. New projects still use init/tailor, explicitly enable requirements and complete the template draft, independent human review, authorized publication and pinning steps in [requirements and templates](requirements-and-templates.md). Prefer this organization for new requirements-enabled projects and explicitly adopt it during authorized setup; init alone does not accept the contract. Pack `ipd-starter@1.3.0` contains 23 types / 46 bilingual files. Pack 1.2.1 and earlier remain resolvable.

For an existing increment with accepted work or approved Gates, finish it under the existing process, then begin a new increment from its accepted delivery baseline. Before creating active instances, explicitly publish and pin the new pack. Adoption does not split old accepted documents or manufacture historical decisions.

Prepare this request, preview it, review its effects, then apply only with actual explicit human authorization. `--authorized` is a local assertion, not an authenticated platform identity.

```yaml
request_id: adopt-stage-organization
operation: adopt_organization
reason: Adopt per-parent organization for this increment
required_stages: [TR1, TR2, TR3, TR4]
```

```console
ipdctl requirements . --request organization.yaml --json > organization-plan.json
ipdctl requirements . --apply organization-plan.json --actor actual-maintainer --authorized
```

The plan preserves a hashed snapshot of prior registry/state/evidence/template inputs. It creates no Claim, permission or approval.

## Derive requirements and allocate numbers

`numbered_requirement` uses the existing requirement fields; a new requirement may omit `id` so the preview allocates it:

```yaml
request_id: measurement-ir
operation: numbered_requirement
reason: Register the clarified user goal
requirement:
  version: 1
  kind: IR
  title: Timely valid measurement
  statement: Within two seconds of a measurement request, show a valid current reading or explicit failure.
  source: Exact version of the project interview record
  rationale: Support a field decision without presenting an old reading as current.
  priority: high
  owner: systems-team
  module: measurement
  parent: null
  derived: false
  acceptance:
    - id: response
      criterion: Response takes at most two seconds under agreed conditions.
      method: test
  maturity: defined
  decomposition: open
```

The preview reports numbering. Only application registers the requirement. For SR use `kind: SR` and the exact IR parent, for example `ir-001@1`; an AR refers to its exact SR. Continue to use the existing `scope` operation to select this increment’s requirement versions and criteria. Candidate, registered, structurally complete and human accepted are different states.

Default numbers are `ir-001 → sr-001-001 → ar-001-001-001`. Sibling allocation advances beyond historical numbers, preserves gaps and expands beyond three digits. Content versions are separate, such as `sr-001-001@2`. For a revision, supply the existing stable ID and next consecutive version; omitting it would propose a different new requirement.

Existing IDs are retained. `organization.codes` maps each exact version to its readable hierarchy code. Reparenting may change the readable code while preserving identity and earlier mappings. The exact canonical `parent` remains authoritative. Explicitly derived requirements with no parent use their own space, such as `sr-d-001`, and require a design rationale.

## Plan the stage and write per-parent arguments

TR1 keeps an integrated source/feasibility document and multi-row IR register. TR2 has one `ir_decomposition` document per scoped IR and its multi-row SR register. TR3 has one `sr_decomposition` per scoped SR and its AR register, grouped under that SR’s IR directory. TR4 consumes ARs in `delivery_conclusion` and an updated AR trace-register snapshot, linking real implementation and executed verification; it creates no fourth requirement layer. Each stage also has a light `stage_index` for scope, shared work, cross-branch checks and navigation.

```yaml
request_id: plan-tr2
operation: stage_plan
reason: Plan per-parent derivation and shared supporting work
stage: TR2
owner: plan.integrated_plan
locale: en
```

The example Owner is from the default core process. Use the actual canonical Owner in the mapped Phase from `context`. `stage_plan.instances` contains proposed instance requests; `binding_issues` reports absent Owner coverage and conflicts. The plan creates no files, bindings or execution dependencies.

Parent input alone is enough to start: child outputs can initially be empty. When new parent branches enter scope, another stage-plan request with a new request ID extends the plan without overwriting existing units. Update existing units’ output sets explicitly with `stage_unit`.

Hold the relevant Owner Claim before passing a selected proposal as `instance` to the existing `instantiate` operation. A TR2/TR3 conclusion draft may initially reference just its parent. Actually derive each candidate child there, including unique argument anchors, assumptions, calculations/diagrams, sources, alternatives and verification criteria. Then register selected children and consolidate the register.

First use does not require pre-registering all children. A valid Claim holder
whose Owner maps uniquely to one TR1–TR3 plan may submit the existing authorized
requests to register version-1 requirements of that stage, add only their scope,
and complete the unit's parent decomposition. TR3 implementation links may bind
these requirements and their ancestors to that same Owner. Applying actors must
hold the Claim. Existing identity revisions, reductions or changes to committed
criteria, other stages, template pins and stage planning retain their safe-boundary
rules. TR4 does not use this path to create AR requirements. Preserve the initial
analysis draft through `revise_instance` when managed coverage expands.

The public synthetic qualification driver supports the complete organized workflow:

When managed coverage changes, use `revise_instance` with `old` and a new `instance`. Preserve Owner/type/key/locale, choose a new ID and path, and retain the prior file. Do not overwrite or edit the registry to fake metadata. A child register references only its output rows; its parent input is not another child row.

## Associate supporting work and conclusions

Read `organization.units` from `ipdctl requirements . --json`. Select a unit and submit its complete record as `unit` in a `stage_unit` request. Keep identity fields and explicitly update outputs, arguments, supports, conclusion/register IDs, finalized status and rationale. Each output needs an argument locator, such as `{"requirement":"sr-001-001@1","anchor":"derive-sr-001-001"}`. Its conclusion document must contain a unique explicit anchor such as `<a id="derive-sr-001-001"></a>`; a generic paragraph cannot stand in for every child derivation.

A supporting reference has this shape:

```json
{
  "kind": "artifact",
  "target": "docs/shared/selection.md",
  "owner": "plan.integrated_plan",
  "required": true,
  "rationale": "These interface and timing bounds justify the child requirements",
  "anchor": "timing-budget",
  "sha256": null
}
```

For `kind: instance`, target is an existing managed instance ID; for artifact it is a project-relative path. The controller hashes actual bytes rather than trusting caller-supplied digests. An Artifact may be planned before it exists, with a null digest, but missing/changed required work prevents readiness. Optional missing or stale references remain visible and are not passes.

Every actual path has one Owner; sharing creates references and consumers, not extra ownership. A required different Owner’s work needs an explicit core prerequisite or prior acceptance. Support edges never silently create `depends_on`. Work and conclusion under one Owner can be reviewed together without self-dependency.

Set `finalized: true` only after checking derivations, complete scoped child sets, registers and required support. This makes the unit available for the existing Deliverable/Gate checks; it grants no approval. Conclusions can be drafted early and iterated before final consolidation.

Architecture, interface specifications, test plans and hardware selection remain professional work products when applicable. Store shared work once. Keep real code, hardware and tests in their normal project locations and link versions/digests at TR4; a summary cannot replace implementation or execution.

## Dashboard and checks

The existing distinction between `refresh` and `render-dashboard` remains. Adoption adds a stage work-product panel and `data/requirement_flow.json`; the original process graph keeps its execution meaning. Grouping follows actual IR ancestry, with stage/increment/search filters and expandable inputs, support, conclusions and children.

Requirement links locate exact records; usage links jump to the next consuming unit. Supporting work lists all consumers and links back to the core Deliverable matrix. Historical units open immutable baseline content rather than current files. Unassociated professional deliverables remain visible.

Definition, decomposition, material completeness, Owner acceptance, implementation and verification are separate dimensions. Wrong parentage, missing outputs/indexes, required stale support, unfinished units or unknown impact cannot manufacture a pass. Changed materials and relations participate in review and verification contexts.

## Qualification and scope

```console
python -B scripts/simulate_incremental_development.py --organized --locale en
python -B scripts/simulate_incremental_development.py --organized --locale zh-CN
```

Its two increments use explicit synthetic human decisions and fresh software execution, not production acceptance. Native DOCX/XLSX, bulk historical path migration, concurrent Claims and independent content-correctness review remain separate work.
