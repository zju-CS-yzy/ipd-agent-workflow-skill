# Progressive requirements, increments and Markdown templates

The v0.5.3-beta version adds an explicit opt-in IR/SR/AR registry. Existing projects keep their current behavior. Release qualification is recorded separately in RELEASE_CHECKLIST.md; this cycle uses public synthetic fixtures because no private Golden project was available.

## Inspect the starter templates

```console
ipdctl templates --type interface_spec --locale en
ipdctl templates --type interface_spec --locale zh-CN
ipdctl templates --json
```

The installed resources are under `ipdctl/document_templates/en/` and `zh-CN/`. Both locales share machine IDs, versions, section IDs, fields and table meanings, with independently pinned content digests. The 18 types include `ir_spec`, `sr_spec`, `ar_spec`, `architecture_design`, `detailed_design`, `interface_spec`, `implementation_record`, `test_plan`, `test_procedure`, `test_report`, `system_verification_report`, `acceptance_report`, `change_impact`, `trace_review`, and four overall stage drafts listed in [TR1–TR4 deliverables](stage-deliverable-drafts.md).

IR/SR/AR templates now hold multiple requirements in a register, with HTML `rowspan` for shared cells and a separate ID/version per requirement. Overall documents explain analysis and design; registers maintain individual specifications.

Each template contains versioned metadata, dedicated sections and tables suited to its type. Individual specifications belong in registers; overall analysis belongs in stage documents. Fill every `[[TODO: ...]]` with project facts. Removing placeholders without adding content fails lint. Preserve section order, headings, table columns and metadata. Cells must be filled; an inapplicable item needs its rationale and applicable human decision reference. No template invents passing results or signatures. Structural completeness does not establish content readiness or human approval.

## Facts and progressive gates

`.ipd/requirements.yaml` is authoritative; the Dashboard and generated requirement lists are projections. A requirement has a stable ID, append-only content version, kind, exact parent version, source, rationale, priority, owner, module, acceptance criteria and verification methods. Definition maturity and decomposition maturity are separate from implementation and verification. `defined` and `complete` are declarations to be reviewed, not approvals.

Use IR→SR→AR for the main tree. Derived SR/AR may explicitly omit a parent with a rationale; the governing Deliverable/Gate reviews the version manifest. Typed `shared_constraint`, `allocated_to`, and `satisfied_by` links are separate from executable `depends_on` and same-phase deliverable `refines`. Decomposition maturity may change through an explicit `decomposition` request without changing requirement content.

The default reference mapping is concept→TR1, plan→TR2, develop→TR3, and qualify/launch/lifecycle→TR4. All existing TR/DCP Gates remain. Configure every canonical Gate ID with `stage_map` before any Gate is approved. This reference mapping is a project convention, not a universal Huawei stage definition.

| Stage | Additional requirement checks |
| --- | --- |
| TR1 | Scoped IR definitions; future AR are not required yet |
| TR2 | Scoped IR decomposition and SR definitions with measurable criteria |
| TR3 | Scoped SR decomposition, AR definitions and explicit implementation allocation |
| TR4 | Separate passed results and matching evidence for each committed IR/SR/AR criterion |

AR success never establishes SR verification or IR user validation. Failed, skipped, unknown, absent and stale results remain distinct. Scope selects exact requirement versions and criterion IDs, allowing an IR to be delivered over several increments without claiming its whole scope is satisfied.

`context --json` includes the requirement projection. A successful structural
`verify` does not declare unfinished requirements passed: its separate
`requirements.acceptance`, diagnostics and coverage fields describe increment
readiness, while the Gate and human decision remain mandatory.

## Request, preview, apply

Every request includes `request_id`, `operation`, and `reason`. Unknown fields fail closed. Save preview stdout unchanged as UTF-8 JSON and apply that saved plan:

```console
ipdctl requirements PROJECT --request request.yaml --json
ipdctl requirements PROJECT --apply request.plan.json --actor maintainer --authorized
ipdctl requirements PROJECT --json
```

Keep request files outside the project or in its designated private request directory. Preview does not write project files. The plan binds the state revision and all relevant facts, template and evidence digests. A stale plan is rejected. Identical retries create no duplicate file or event; changed input needs a new request ID. Authorization uses the existing explicit caller-assertion boundary, not authenticated platform identity.

Enable the model with:

```yaml
request_id: enable-mvp
operation: enable
reason: Explicitly adopt progressive requirements
increment: mvp
product_version: '0.1'
```

Enable preserves a hashed migration snapshot of the previous state, Runtime, process and available evidence. Finish an active Claim/Review first. Original IDs and history are preserved, and unmapped deliverables are listed. No IR/SR/AR or approval is inferred from filenames.

An example requirement payload for `operation: requirement`:

```yaml
requirement:
  id: ir-1
  version: 1
  kind: IR
  title: Fast field measurement
  statement: The product shall return a measurement within two seconds.
  source: customer-interview-1
  rationale: Support timely field decisions
  priority: high
  owner: systems-team
  module: sensor
  parent: null
  derived: false
  acceptance:
    - id: response
      criterion: Elapsed time is at most 2 seconds at 20 degrees C.
      method: test
  maturity: defined
  decomposition: open
```

SR uses `kind: SR`, `parent: ir-1@1`; AR references an exact SR version. Methods are `test`, `analysis`, `inspection`, or `demonstration`.

| Operation | Additional request fields |
| --- | --- |
| `enable` | `increment`, `product_version` |
| `requirement` | `requirement`: append a content version |
| `scope` | `scope: [{requirement: ir-1@1, criteria: [response]}]` |
| `decomposition` | `requirement`, `status: open/complete` |
| `stage_map` | `stage_map: {canonical Gate ID: TR1/TR2/TR3/TR4}` |
| `link` | `link: {requirement, relation, target, rationale}` |
| `obligation` | `obligation: {id, requirement, owner, document_type, keys}` |
| `instantiate` | `instance`, as illustrated below |
| `verification` | `verification: {id, requirement, criterion, method, case, environment, result, evidence}` |
| `assess` | `change` request ID; `assessments: [{target, action, rationale}]`, using `reverify/unaffected/defer` |
| `pin_templates` | `path`: a local pack directory; empty string selects the bundled pack |
| `baseline` | `id`, `source: {backend, repository, revision, path}` |
| `begin` | `increment`, `product_version`, `base_baseline`, `scope` |
| `reuse_verification` | `baseline`, `result`, `id` |
| `retire` | No additional fields; no active increment may remain |

Changed requirements produce an impact set covering ancestors, descendants, typed shared constraints, linked artifacts, instances and Gates. Assess every target explicitly. Unknown or deferred applicability blocks the related decision. Historical approvals are retained. Accepted scope cannot silently shrink; Verify detects changed governed inputs. Use explicit increment and change boundaries to handle changes to already governed scope.

`reverify` creates an outstanding verification obligation. Accepted assessments receive an `assessment_revision`; new results receive a Skill-generated `context_sha256` binding the requirement, scoped criteria, pinned pack, direct links/document inputs and applicable re-verification epochs. Requirement, instance, core Owner Deliverable and Gate targets apply to their related requirements. Reassessing `reverify` starts another epoch. Results recorded before assessment, failed results and old baseline evidence cannot discharge it. Execute the actual checks, then register a new `verification` result against current inputs; registration itself does not execute tests or prove caller-supplied observations.

An explicitly `unaffected` object is not invalidated merely because another requirement changes, but changes to its own inputs still invalidate old results. `reuse_verification` requires matching historical inputs and re-verification context; copying evidence is not re-execution. Future versions outside scope do not affect the current increment, while adopting a later version cannot bypass an earlier applicable re-verification epoch.

Registry schema 1.0 accepts the two new fields optionally when reading older records. New writes generate them internally; callers cannot supply a context digest. An old result without context remains readable but produces `VERIFICATION_CONTEXT_UNKNOWN` for current readiness. Run the checks and append a new result; do not backfill proof or rewrite frozen baselines.

Each SR/AR register `parent` cell must contain exactly its canonical parent version, optionally wrapped in an HTML link. Shared cells are expanded before checking each row. Missing references, wrong levels, mismatched parents and missing canonical context fail closed. A pinned historical version remains valid when newer versions exist. A derived requirement must explicitly declare `derived: true`, `parent: null` in the registry and use `derived: reason` in its parent cell; free-text N/A does not waive a normal parent relationship. Direct Python lint calls must pass `canonical={exact_reference: canonical_record}`; project preflight supplies the registry automatically.

A private or early SR/AR format without managed requirement/parent columns returns `DOCUMENT_PARENT_COLUMN`; prose structure alone cannot prove reference integrity. Original packs remain resolvable and frozen history is not rewritten. Use the explicit `replace_templates` conversion described below for a single active Owner; use a new increment for multiple Owners. Do not silently repin, overwrite reviewed files or disable validation.

## Multiple documents for one requirement

Declare an obligation for `ar-1@1`, type `interface_spec`, keys `[northbound, southbound]`, owned by an existing core Deliverable. Then create two distinct instances with the same pinned type/version:

```yaml
instance:
  id: interface-northbound
  key: northbound
  requirements: [ar-1@1]
  owner: develop.solution_baseline
  document_type: interface_spec
  path: docs/mvp/interface-northbound.md
  title: Northbound measurement interface
  scope: MVP measurement service
  locale: en
```

The second instance uses another ID, `key: southbound`, and a different path. Change `locale` to `zh-CN` for the Chinese equivalent. A single instance may reference several requirements, while its file keeps exactly one Owner.

Creation requires an unexpired Owner Claim, the matching actor and existing explicit artifact bindings. Files must be new paths under `docs/`. Traversal, symlinks, Windows junctions, duplicate keys, path collisions and overwrite are rejected. New files, registry, state and Runtime share one recoverable transaction. Templates perform controlled substitution only; they execute no code, macros, scripts or network access. Close/Review enforce structural lint; acceptance still requires the original human decision protocol.

## QA packs, baselines and reuse

`ipd-starter@1.2.1` is the public pack, containing 18 types and 36 bilingual files including four overall stage discussion drafts. The `1.0.0`, `1.1.0` and `1.2.0` packs are archived unchanged for existing pins. A project explicitly pins one effective pack with a `core`, `organization`, or `project` layer; resolution is explicit rather than a silent per-file overlay. QA can copy the pack locally, change its ID/version, applicability, sections and content, and recalculate per-template SHA-256 digests. Changed content requires a new version. Normal pinning cannot change a pack after instance creation; the controlled replacement operation below creates new files and preserves old instances. Missing versions, tampered files, incompatible contracts and unavailable type/locale combinations block affected writes. Private packs are never fetched or bundled automatically.

Delivery baselines differ from `adopt-baseline` reconciliation baselines. They require all six phases, approved Gates and current Verify. Read-only Git/SVN commands compare specified immutable source revisions with governance facts. Git needs a full commit ID; SVN needs a numeric revision and project path. Runtime refresh/verification caches may be regenerated after the source is accepted; authoritative Claim/Review events must match. The authorized maintainer identifies the accepted source; trusted platform approval mapping belongs to v0.6.1.

Snapshots retain requirement versions, increment scope, process configuration, template content, state, Runtime and local evidence bytes. Each file is limited to 16 MiB and total evidence to 100 MiB; exceeding either limit fails explicitly. Remote URLs do not become immutable local evidence. Snapshots can contain private project data and must remain within its authorized repository, outside public release artifacts and public Golden fixtures.

Beginning the next increment regenerates pending core state from the current process with a monotonically increasing state revision. Earlier core IDs and complete histories remain resolvable in hashed snapshots; old phases are not reopened. Evidence reuse requires an explicit baseline/result reference, the unchanged exact requirement version, a passed result and matching stored bytes. The current implementation materializes UTF-8 evidence; binary originals remain inside snapshots. Mutable current paths never prove old evidence.

The Dashboard includes requirement hierarchy, increment/version/module/owner/priority/maturity filters, document/template links, change impacts and independent verification outcomes. The JSON `coverage` projection distinguishes definition, decomposition, implementation, verification and accepted criteria. Partial IR delivery remains `partial` until all its criteria have accepted evidence.

## Public design references

These templates are original project skeletons, not copies of private Huawei QA documents. Sources informed field selection and structure; they do not endorse this Skill.

- [Huawei CodeArts Req concepts](https://support.huaweicloud.com/intl/zh-cn/productdesc-projectman/codeartsreq_07_2008.html): IR/SR/AR terminology and hierarchy.
- [NASA requirements management](https://www.nasa.gov/reference/6-2-requirements-management/): hierarchical traceability and change impact.
- [NASA requirements verification matrix](https://www.nasa.gov/reference/appendix-d-requirements-verification-matrix/): stable identifiers, sources and verification approaches.
- [NASA software design description guidance](https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695674/5.13+-+SwDD+-+Software+Design+Description): architecture, interfaces, rationale and design traceability.

## Draft, review, publication and controlled conversion

The built-in pack selected by `enable` is a provisional source, not a completed QA decision. Every pack, including the built-in one, requires three independently previewed and authorized requests before managed instance creation. Apply each saved plan using `--actor` equal to its declared actor. Authors and reviewers must differ. These example identities are placeholders for actual authorized project personnel.

```yaml
request_id: qa-draft-request
operation: draft_templates
reason: QA submits the bilingual template pack
id: qa-draft-1
path: '' # Built-in pack; use a project-relative directory for a private pack
actor: qa-author
actor_type: human
```

```yaml
request_id: qa-review-request
operation: review_templates
reason: Reviewed bilingual structure, applicability, fields and writing guidance
id: qa-review-1
source: qa-draft-1
actor: qa-reviewer
actor_type: human
decision: approved # Or rejected; rejection cannot be published
```

```yaml
request_id: qa-publish-request
operation: publish_templates
reason: Authorize publication of this exact reviewed pack
id: qa-publication-1
source: qa-review-1
actor: qa-publisher
actor_type: human
```

Then select the same `path` with `pin_templates`. Immutable files in `.ipd/template_publications/` bind pack ID/version/manifest digest, predecessor, declared people, decision, reason and accepted state revision. Registry hashes, delivery snapshots and repository source checks cover these files. Changed bytes under the same version, a newer rejection, missing/tampered history, stale plans and a mismatched applying actor fail closed. Exact retries do not append records. These are explicit local declarations, not authenticated platform approvals; old packs acquire no fabricated historical QA decision.

For an active old format, first review and publish the target pack. Human QA may record these three stages during the current Owner work step without changing the Claim or effective pack. Review remains locked against input changes. During the existing Owner Claim's `work` step, preview `replace_templates`:

```yaml
request_id: convert-current-documents
operation: replace_templates
reason: Add controlled parent-reference columns to an early format
path: ''
replacements:
  - old: old-sr-instance
    instance:
      id: new-sr-instance
      key: system
      requirements: [sr-1@1]
      owner: plan.integrated_plan
      document_type: sr_spec
      path: docs/mvp/SR-v2.md
      title: System requirement register
      scope: Committed system requirements for this increment
      locale: en
```

List every live instance in the current increment. They must belong to one current Owner; preserve each key, requirements, Owner, type and locale. Preview includes new content and hashes. Authorized application creates fresh unfilled files and records `supersedes`; original files/records remain intact. Only replacement instances count toward current document obligations. Fill and validate them before Close/Review. Multiple Owners or completed approvals require a new increment: complete and freeze the old cycle with its original tools before upgrading, then select the new pack in the next cycle. Direct conversion of an unfinished development-era increment spanning multiple Owners is unsupported. This operation creates files and does not move old paths or implement general path migration.

## Increment audit and stage inputs

Model-enabled Runtime uses `1.1`. Every new event carries `increment_context`: increment ID, base delivery baseline and the exact scope SHA-256. The full scope remains in canonical increments and frozen snapshots. `increment_context_start` marks the new-event boundary; earlier events remain verbatim. Claim, Close, Review, approval, phase advancement, Refresh, Verify, lifecycle completion and requirement operations use the same rule. Baseline acceptance retains its accepted increment; the next cycle names its predecessor baseline; retirement is separate.

Projects without the model retain Runtime `1.0`. Older tools reject `1.1` rather than continuing writes; do not manually downgrade schemas. Registries without `template_records` remain readable, but new/continued managed documents require explicit publication. Historical result reuse still requires matching input context.

Owner/Gate approval binds stage-appropriate inputs: TR1 does not require future SR/AR decomposition; TR2 does not require future implementation allocation; TR3 binds implementation links; TR4 binds verification results. Changing earlier requirement content or shared constraints still invalidates affected approvals. The current Claim holder may record actual verification results during `work`, after writing documents and executing cases and before Close/Review. Another actor is rejected; review input changes remain blocked.

Run `python -B scripts/simulate_incremental_development.py --locale en` (or `zh-CN`) for the complete two-increment synthetic qualification. It executes the booking implementation, creates overall stage documents and registers, completes both six-phase lifecycles and B1/B2, then separately retires the product. Human decisions are explicit test declarations and do not claim production or actual QA acceptance.
