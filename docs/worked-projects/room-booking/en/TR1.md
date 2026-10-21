---
instance_id: 'room-tr1-en'
increment: 'mvp'
requirements: 'ir-01@1, ir-02@1, ir-03@1'
owner: 'demo-doc-owner'
document_type: 'tr1_requirements_feasibility'
template_id: 'ipd-starter.tr1_requirements_feasibility'
template_version: '0.2.1'
template_sha256: '042732fcbc5ef871cbb7582014c827ee05d3277bd10482939c516378e96cb900'
locale: 'en'
scope: 'Synthetic standalone writing exercise; no governance acceptance'
---

# TR1 initial requirements and feasibility analysis (discussion draft) — Offline single-room booking

> Completed synthetic teaching document, revision 1. Requirement IDs come from this example catalog.json and are not accepted governance facts in a real IPD project. No human approval is claimed. Each stage file is its completion snapshot; later outputs appear only in later stages.

<!-- ipd-section:baseline -->
## 1. Define scope and source material

Project offline-room-booking, increment mvp, document revision 1. The sole starting input is [BRIEF@1](source-brief.md); no prior product, interview or approved baseline exists. [catalog@1](../catalog.json) is educational data, not an alternate canonical `.ipd/requirements.yaml`. No SR, AR, code or test result is presumed available at the start.

<!-- ipd-section:context -->
## 2. Analyze problems, users and shared context

Shared context BG-1 is serial in-memory booking for one room/day. U1 concerns input and confirmation, U2 conflicts and cancellation, and U3 agenda and utilization. There is no real market research conclusion; C1–C5 are explicit exercise premises. A database is not presumed a requirement. Chapter 4 develops the three objectives into IR-01/02/03.

<!-- ipd-section:scope -->
## 3. Describe scenarios, boundaries and increment objectives

| Scenario | Source/objective | Normal and failure flow | Boundary/premises |
| --- | --- | --- | --- |
| SC-1 | U1 / ir-01@1 | Submit 08:00–09:00 and confirm; reject off-grid 09:20–10:00 | Empty day, strict format; boundary 17:45–18:00 is valid |
| SC-2 | U2 / ir-02@1 | With 08:00–09:00 active, accept adjacent 09:00 and reject overlapping 08:45; cancel then rebook | Unknown/repeated cancellation reports error without deleting the new ID |
| SC-3 | U3 / ir-03@1 | Book a later meeting first, then an earlier one; view time order and capacity | Empty/full day, recomputation after cancel, output copies |

Include create/reject/cancel, read-only agenda and summary. Exclude C4 extensions; MVP promises neither retention across restarts nor interaction latency. Shared scenarios are described once here and referenced by applicable IRs.

<!-- ipd-section:elicitation -->
## 4. Develop each candidate IR from its sources

<a id="d-ir-01"></a>
### D-IR-01 · ir-01@1

**Source and consolidation:** BRIEF@1/U1 requests booking with a clear outcome. C1/C2 bound it to one room, 08:00–18:00 and a 15-minute grid. Consolidate the need into acceptance of valid input and explicit rejection of invalid input.

**Resulting IR:** Within the operating day, a user can create a booking on a 15-minute grid and receive confirmation; invalid inputs are explicitly rejected.

**Acceptance intent and tradeoff:** C-IR-01 — Use a command/API demonstration rather than a GUI; promise neither interaction latency nor persistence.

<a id="d-ir-02"></a>
### D-IR-02 · ir-02@1

**Source and consolidation:** BRIEF@1/U2 concerns contention and availability after cancellation. C3 permits touching boundaries and C4 limits calls to serial execution in one process, yielding conflict control and cancellation/release objectives.

**Resulting IR:** Active bookings must not overlap, adjacent bookings are allowed, and a cancelled slot can immediately be booked again.

**Acceptance intent and tradeoff:** C-IR-02 — Do not extend this to concurrent locking or authentication; adjacency semantics are an explicit input, not a code assumption.

<a id="d-ir-03"></a>
### D-IR-03 · ir-03@1

**Source and consolidation:** BRIEF@1/U3 supports planning later meetings. C1 fixes capacity. The agenda and utilization answer when the room is free and how much is used; a percentage alone is insufficient.

**Resulting IR:** The user can view active bookings in time order and see occupied/free minutes, slot counts and daily utilization.

**Acceptance intent and tradeoff:** C-IR-03 — Summarize one day in the current process only; exclude cross-day analytics and personal data.

The three high-priority candidates correspond to U1/U2/U3; each is needed for this bounded MVP. The teaching catalog assigns ir-01@1…ir-03@1; this is sample bookkeeping, not governance acceptance. Feasibility analysis leaves content unchanged, so versions remain 1.

<!-- ipd-section:feasibility -->
## 5. Analyze feasibility and compare alternatives

Capacity=(18−8)×60=600 min; 600/15=40 slots. Each positive booking uses at least one slot, so at most 40 can be active. Integer minutes and an active set can implement the objectives. This is premise-based feasibility reasoning, not a measured performance claim. Plan validation, ledger, presentation and metrics work units without inventing measured effort.

| Alternative | Supported IRs / scenarios | Calculation / experiment / rationale | Cost / schedule / resources | Limitations and risks | Investigations / owner |
| --- | --- | --- | --- | --- | --- |
| Integer minutes + in-memory dictionary (selected) | IR1/2/3 | 600/15=40; O(n≤40) scan | Standard library; four planned work units | No persistence/concurrency | Actual TR4 verification; demo-dev |
| File/database storage (deferred) | IR1/2/3 | Could add recovery, not required by inputs | Additional format/recovery/transaction work | Outside C4 | Reassess against future requirements |

<!-- ipd-section:ir -->
## 6. Consolidate the IR register and check source coverage

Consolidate the three candidates into [IR-TR1.md](IR-TR1.md). Merge common context and operating scope across three rows, retaining individual identities, statements, criteria and owners. U1→ir-01@1, U2→ir-02@1, U3→ir-03@1: no source is omitted. The SR column states not decomposed, demo-systems plans TR2, without future versions.

<!-- ipd-section:risks -->
## 7. Consolidate risks, dependencies and open decisions

R1: state loss on exit is an explicit C4 limit; demo-systems must define recovery requirements before persistence. R2: API behavior does not prove real user usability; demo-QA retains human acceptance as not performed. R3: inclusive interval logic would break adjacency, so TR2 must specify the rule. No additional hidden scope assumptions remain.

<!-- ipd-section:deliverables -->
## 8. Compile stage deliverables

This document and the IR snapshot form the minimum stage pair. BRIEF and catalog are public synthetic inputs, containing no private Golden, credentials or production files.

| Type / proposed necessity | Document ID / path | Exact version / digest | Requirements / scope | Owner | Status / gaps |
| --- | --- | --- | --- | --- | --- |
| Overall document; necessary | [TR1.md](TR1.md) | doc rev 1 | TR1 / mvp | demo-doc-owner | Filled; not approved |
| Register; necessary | [IR-TR1.md](IR-TR1.md) | doc rev 1 | 3 IR | demo-doc-owner | Stage snapshot |

<!-- ipd-section:review -->
## 9. Summarize review inputs and TR2 handoff

Source coverage is 3/3, with explicit feasibility and capacity premises. Handoff to TR2 consists of three IRs, SC-1/2/3 and C1–C6. No SRs, ARs or passing evidence exist at this stage. The result is a teaching draft ready for further analysis, not simulated human or Gate approval.

