# Enabling products and main-product adoption

Recorder and Replay can have independent release histories while enabling the
same main-product algorithm, data evaluation or test work. A release baseline
records one exact product version. An adoption records the purpose and
conditions under which the main product may use a set of releases. A controlled
dataset records which Recorder version and configuration produced it.

## Enable the contract

Use the existing requirements preview/apply commands, or the equivalent
`products . --request request.json` and `products . --apply plan.json --actor NAME --authorized`.
Every request contains `request_id`, `reason` and `operation`. Previews write
no project facts. Apply rechecks source fingerprints under the project mutex
and uses the existing rollback journal. Request IDs support exact retry.

After enabling the requirements registry, apply `adopt_product_governance`.
An organized project first adopts the existing work-role contract. This
explicit upgrade creates registry 1.3 / contract 0.5.7 and preserves a hashed
pre-upgrade snapshot. Existing projects can redraw without this upgrade.
Earlier clients reject writing the new registry.

## Register and release each tool

Use `product_register` with `product` containing `id`, `title` and `scope`.
Recorder and Replay each receive a stable product ID.

A release record contains `id`, `product`, `version`, `scope`, `source`,
`protocol`, `environments`, `capabilities`, `requirements` and `artifacts`.
Each artifact uses `{"path":"relative/path","sha256":"..."}`. Source contains
`backend`, `repository`, `revision` and `path`. Git uses a full commit,
SVN a numeric revision, and content sources the digest of the artifact manifest.
Repository citations are declared provenance. Local content hashes are checked.
Keep adopted tool artifacts at versioned paths that remain available. Changing
an adopted file in place marks that input unavailable until its exact bytes are
restored or a new adoption is accepted.

For an existing approved tool version, use `product_import` with `import`
containing the release, `approver`, an approval evidence path/hash, and
`identity_source: historical-local-declaration`. This preserves the old
approval scope. Project adoption still requires its own applicability review.

For a new version, claim its existing canonical Deliverable Owner. After
writing the artifacts, use `product_work` with `kind: release`, `owner`
and the release `record`. All new evidence paths must belong to that Owner.
Then close, review and obtain the authorized human decision through the normal
CLI. Apply `product_accept` with the work ID after approval. It checks that
the current work was included in that exact review. The main increment can
continue while several tool releases are accepted serially.

## Verify data and compatibility

Use the same work/review/accept route for `kind: dataset`. Record the exact
`recorder`, `protocol`, `environment`, `configuration`, `calibration`,
`time_basis`, data `files`, and `quality`. Quality contains cases and an
evidence path/hash. A tool's approval and the quality of its output data have
separate evidence.

For `kind: compatibility`, record exact `releases`, `datasets`,
`protocol`, `environment`, `cases` and `evidence`. Each case has an
`id`, `criterion`, `expected`, `observed` and `result`. Failed,
unknown or skipped cases can remain in a draft and block acceptance. Use
representative round-trip data and define format, timing, channel, integrity
and environment criteria appropriate to the intended use.

An adoption needs an accepted check of its exact version combination, protocol,
environment and required datasets. Evidence for a developer PC applies to that
environment. Test-PC use requires its corresponding evidence.

## Adopt for a purpose and upgrade deliberately

Create `kind: adoption` work under an existing applicability Owner, with
`id`, stable purpose `key`, `purpose`, exact `releases`, `datasets`,
`checks`, `protocol`, `environment`, `consumers`, `evidence`,
`prior` and `assessments`. Add an explicit execution dependency from each
consumer to the applicability Owner before registering this work.

One adoption can serve several consumers under the same conditions. Capture
can use a Recorder-only adoption when its acceptance criteria permit it.
Playback or evaluation uses a verified Recorder/Replay combination as needed.
The first adoption uses `prior: null` and empty assessments. A replacement
pins its previous adoption ID and assesses every old/new consumer using
`target`, `action: reverify|unaffected` and `rationale`. Accepted consumers
need a new increment for a changed adoption.

`products . --impact OLD --replacement NEW` previews changed source,
artifacts, protocol, environments and scope, plus affected datasets,
compatibility checks, consumers and requirement links. It changes no pins.
Requirement/scope previews also report downstream work and verification impact.
Acceptance switches the selected adoption. New releases alone leave each
existing selection pinned to its exact versions.

File drift, an incompatible combination, missing target-environment evidence,
or `product_withdraw` suspends affected uses. Old acceptance records remain
auditable. Requirement verification binds adopted inputs so an upgrade or
changed evidence requires applicable re-verification.

## Prepare legacy-work drafts

`products . --handoff-plan request.json` previews explicit source/target file
mappings with `request_id`, `reason`, `source_owner`, `target_owner`
and `files: [{"source":"old.md","target":"docs/new.md"}]`. It reports
content hashes, old review digests, target Owner conflicts and candidate binding
rules. Review and accept target bindings before taking the target Owner Claim.

Use `handoff_instance` with `source`, `source_owner`, `sha256`,
`editor` and a normal new `instance` under that Claim. It creates a new
pinned-template draft, includes the source text and records provenance.
Fill its template before closing. The source file and old Owner reviews stay
available. Path relocation and removal have their own later migration scope.

## Dashboard and boundaries

The shared matrix and dependency graph show selected releases, data, checks,
adoption and consuming Deliverables. Details identify imported versus governed
approval and expose the exact context and diagnostics. Core execution continues
to enforce one Claim and one review subject.

This version validates declared cases, evidence identities and governance.
Independent content readiness and authenticated platform approval mapping
retain their separate planned scopes. Large artifact/data payloads stay in
their controlled repository paths; product history records manifests and
hashes. Existing main-project snapshot limits still apply to ordinary review
evidence included in a complete increment baseline.

The public test scenario in `tests/test_product_governance.py` uses the normal
CLI to accept a new Recorder, executes actual recording and replay subprocesses,
reviews the resulting dataset and compatibility report, adopts the exact
versions, and claims the main consumer. Run it with
`python -B -m unittest tests.test_product_governance -v`.
