# Architecture

The repository has two coordinated surfaces: `SKILL.md` guides agent decisions, while the dependency-free `ipdctl` package supplies deterministic state and validation behavior.

## Components

| Component | Responsibility | Must not do |
| --- | --- | --- |
| `SKILL.md` and `references/` | Route IPD work, evidence decisions, and human-gate boundaries | Replace project facts or grant mutation authority |
| `ipdctl.state` | Create, load, and atomically persist state | Accept partial writes or silently repair invalid state |
| `ipdctl.validation` | Enforce structure, cross-references, evidence, closure, and gate invariants | Mutate state |
| `ipdctl.engine` | Return revised copies for legal transitions | Finalize a gate without recorded authorized-human approval |
| `ipdctl.dependencies` | Find cycles and unmet deliverable dependencies | Infer missing dependencies |
| `ipdctl.traceability` | Resolve global entity IDs and dangling links | Treat free text as a valid entity reference |
| `ipdctl.policy` | Load and validate safe tailoring policy | Permit non-negotiable controls to be disabled |
| `ipdctl.repository` | Read Git/SVN root, revision, and dirty state | Commit, update, tag, push, or modify VCS state |
| `ipdctl.cli` | Expose init, validate, status, and repository inspection | Hide validation errors or overwrite state implicitly |

## Data flow

An agent first reads repository instructions, project state, applicable policy, and repository metadata. It forms a claim and performs authorized work. Before closure, the runtime validates dependencies, evidence, and trace links. Gate preparation uses the same state, but final TR/DCP approval becomes valid only after an authorized human approval record exists.

State writes use a temporary file in the destination directory followed by an atomic replacement. A successful engine operation increments `revision` exactly once and returns a new object, leaving the input unchanged.

## Contract boundaries

[schemas/project_state.schema.json](../schemas/project_state.schema.json) is the portable structural contract. Python validation adds global constraints that JSON Schema does not conveniently express, including dependency cycles, global entity-ID uniqueness, referential integrity, and conflicts among gate reviews.

[policies/default/tailoring_rules.yaml](../policies/default/tailoring_rules.yaml) is JSON-compatible YAML. That constrained representation keeps the runtime dependency-free and still allows standard YAML tools to read it. Policy validation refuses to disable traceability, evidence, dependency closure, or human gate approval.

The runtime does not store timestamps automatically, infer reviewer authority, or capture personal checkout paths in state. Callers may record approved external identifiers or immutable VCS revisions as evidence.
