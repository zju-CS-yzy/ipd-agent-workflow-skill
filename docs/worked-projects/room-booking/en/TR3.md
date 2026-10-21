---
instance_id: 'room-tr3-en'
increment: 'mvp'
requirements: 'sr-01@1, sr-02@1, sr-03@1, sr-04@1, sr-05@1, sr-06@1, ar-01@1, ar-02@1, ar-03@1, ar-04@1, ar-05@1, ar-06@1, ar-07@1, ar-08@1, ar-09@1, ar-10@1, ar-11@1, ar-12@1'
owner: 'demo-doc-owner'
document_type: 'tr3_high_level_design'
template_id: 'ipd-starter.tr3_high_level_design'
template_version: '0.2.1'
template_sha256: '3291a43bb14c7f79f9c90c10bed67de08b32870452256f77a8832607091fea16'
locale: 'en'
scope: 'Synthetic standalone writing exercise; no governance acceptance'
---

# TR3 high-level design and AR allocation (discussion draft) — Offline single-room booking

> Completed synthetic teaching document, revision 1. Requirement IDs come from this example catalog.json and are not accepted governance facts in a real IPD project. No human approval is claimed. Each stage file is its completion snapshot; later outputs appear only in later stages.

<!-- ipd-section:baseline -->
## 1. Define design scope and TR2 inputs

Inputs are [TR2@doc1](TR2.md), [SR-TR2@doc1](SR-TR2.md), D-SR-01…06 and C1–C6. There are no new objectives and all SR versions remain 1. Architecture analysis precedes twelve chapter 5 ARs and their teaching registration; drafting does not presume ARs already exist.

<!-- ipd-section:architecture -->
## 2. Select architecture and explain module responsibilities

One Calendar object owns the active set and monotonic counter; validation, presentation and metrics are logical units.

```text
book -> parse -> window/grid -> scan(active) -> create -> confirmation
cancel(id) -> remove active entry; counter stays monotonic
agenda/summary -> read active set -> fresh output
```

One active set keeps conflict checks and metrics consistent, without duplicate ledgers or a database. C4 excludes persistence/concurrency. This chapter maps to SRs, not yet-to-be-derived ARs.

| Component / module | Architecture view reference | Supported exact SR versions | Responsibility | Deployment / dependencies | Decision / rationale |
| --- | --- | --- | --- | --- | --- |
| validation | TR3 §2–3 | sr-01@1 | Clock/window | ledger | integer minutes |
| ledger | TR3 §2–4 | sr-02@1, sr-03@1, sr-04@1 | One active set/counter | serial process | precheck before mutation |
| presentation | TR3 §2–3 | sr-05@1 | Sort/format/copy | ledger | read only |
| metrics | TR3 §4 | sr-06@1 | Minutes/ratio | ledger; SR-03 | fixed 600 min |

<!-- ipd-section:behavior -->
## 3. Analyze interactions, data and mechanisms

Sequence: reject parse failure, window failure or conflict; add one entry and advance the ID only after all prechecks. Cancellation removes an active entry without rewinding the counter. Half-open 08:00–09:00 excludes 09:00, permitting adjacency; 08:45–09:15 satisfies both strict overlap inequalities. Fresh read objects prevent external mutation.

<!-- ipd-section:quality -->
## 4. Justify quality attributes, budgets and risks

There are 41 grid endpoints and at most 40 positive disjoint bookings. Conflict scans are O(n) and agenda sorting O(n log n), without inventing measured milliseconds. Occupancy U=Σ(end−start) satisfies 0≤U≤600 under the bounds/non-overlap invariant. Durations are multiples of 15, so U×1000/600 is an integer for exact percentage tenths. Precheck-before-mutation in one process is not a durable transaction guarantee.

<!-- ipd-section:decomposition -->
## 5. Derive and allocate each AR from its parent SR

<a id="d-ar-01"></a>
### D-AR-01 · ar-01@1

**Exact parent and objective:** sr-01@1 — Accept only HH:MM clock values satisfying 08:00≤start<end≤18:00 with both endpoints on the 15-minute grid.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-1; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Parse two-digit HH:MM with 0≤h≤23 and 0≤m≤59 to 60h+m; otherwise return an explicit format or clock error.

**Calculation / diagram / argument:** SR-01 needs a common integer representation: 08:00=480, 09:15=555, 18:00=1080. Reject missing zero in 9:00 and invalid minutes in 09:75 instead of permissive conversion.

**Tradeoffs and applicability:** Clock validity belongs here; operating hours belong to AR-02, keeping responsibilities separate.

**Resulting requirement statement:** Parse two-digit HH:MM with 0≤h≤23 and 0≤m≤59 to 60h+m; otherwise return an explicit format or clock error.

**Verification method and expected result:** test; C-AR-01; planned case V-AR-01. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-ar-02"></a>
### D-AR-02 · ar-02@1

**Exact parent and objective:** sr-01@1 — Accept only HH:MM clock values satisfying 08:00≤start<end≤18:00 with both endpoints on the 15-minute grid.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-1; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Enforce 480≤start<end≤1080 and (start−480)%15=(end−480)%15=0 before creation.

**Calculation / diagram / argument:** SR-01 defines the bounds and grid. 17:45=1065 to 18:00=1080 is a valid 15-minute booking; reject zero length, 07:45/18:15 boundary violations or off-grid 09:20.

**Tradeoffs and applicability:** Checking both endpoints makes the minimum positive duration 15 minutes without a separate floating duration threshold.

**Resulting requirement statement:** Enforce 480≤start<end≤1080 and (start−480)%15=(end−480)%15=0 before creation.

**Verification method and expected result:** test; C-AR-02; planned case V-AR-02. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-ar-03"></a>
### D-AR-03 · ar-03@1

**Exact parent and objective:** sr-02@1 — A valid conflict-free request creates one active booking and returns a non-reused process-local ID, times and duration; rejection changes neither active state nor the next ID.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-1; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Allocate increasing B001, B002… only for successful creations; rejection does not advance and cancellation does not rewind the counter.

**Calculation / diagram / argument:** With k successful creations, the next counter is k+1. Rejection adds no success and cancellation removes no historical success, preserving stable non-reused identifiers.

**Tradeoffs and applicability:** Use at least three digits, allowing growth beyond 999; at most 40 are active, but repeated cancel/rebook cycles are allowed.

**Resulting requirement statement:** Allocate increasing B001, B002… only for successful creations; rejection does not advance and cancellation does not rewind the counter.

**Verification method and expected result:** test; C-AR-03; planned case V-AR-03. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-ar-04"></a>
### D-AR-04 · ar-04@1

**Exact parent and objective:** sr-02@1 — A valid conflict-free request creates one active booking and returns a non-reused process-local ID, times and duration; rejection changes neither active state nor the next ID.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-1; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: After input and conflict prechecks, add exactly one booking and return ID, normalized times and end−start minutes; rejected paths do not mutate the ledger.

**Calculation / diagram / argument:** Prechecks before creation prevent rejected requests from leaving partial active entries. The first 08:00–09:00 confirmation is B001, 08:00, 09:00, 60, with exactly that entry in the agenda.

**Tradeoffs and applicability:** Guarantee serial behavior for expected input rejection, not durable transactions under memory exhaustion or power loss.

**Resulting requirement statement:** After input and conflict prechecks, add exactly one booking and return ID, normalized times and end−start minutes; rejected paths do not mutate the ledger.

**Verification method and expected result:** test; C-AR-04; planned case V-AR-04. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-ar-05"></a>
### D-AR-05 · ar-05@1

**Exact parent and objective:** sr-03@1 — Use half-open intervals [start,end): touching endpoints are allowed; reject any positive overlap without changing the active list.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-2; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: For validated positive-length intervals, return start<other_end and other_start<end; equality at a boundary is not a conflict.

**Calculation / diagram / argument:** Implement the SR-03 interval argument as a pure function: 480–540 against 540–555 is false; overlap, identical, contained and containing intervals are true; 465–480 is false.

**Tradeoffs and applicability:** Use strict rather than inclusive inequalities; inclusive comparison would wrongly reject adjacent bookings.

**Resulting requirement statement:** For validated positive-length intervals, return start<other_end and other_start<end; equality at a boundary is not a conflict.

**Verification method and expected result:** test; C-AR-05; planned case V-AR-05. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-ar-06"></a>
### D-AR-06 · ar-06@1

**Exact parent and objective:** sr-03@1 — Use half-open intervals [start,end): touching endpoints are allowed; reject any positive overlap without changing the active list.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-2; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Check all active bookings before creation; any conflict returns CONFLICT without changing the active list or the next successful ID.

**Calculation / diagram / argument:** Checking only one entry can miss another occupied interval. Scan the whole active set before committing. After B001 and a rejected overlap, the next valid request must be B002, not B003.

**Tradeoffs and applicability:** With at most 40 active entries a linear scan is adequate and transparent, without extrapolating to a large concurrent service.

**Resulting requirement statement:** Check all active bookings before creation; any conflict returns CONFLICT without changing the active list or the next successful ID.

**Verification method and expected result:** test; C-AR-06; planned case V-AR-06. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-ar-07"></a>
### D-AR-07 · ar-07@1

**Exact parent and objective:** sr-04@1 — Cancelling an existing ID removes its active booking and releases the slot; unknown or repeated cancellation returns NOT_FOUND without affecting others, and old IDs are not reused.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-2; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Cancel only an existing target ID and return confirmation; an absent ID returns NOT_FOUND without affecting other entries.

**Calculation / diagram / argument:** SR-04 release is active-set removal of the target ID. After removing sole B001 the set is empty; cancelling missing keeps it empty and reports a clear error.

**Tradeoffs and applicability:** Locate by ID instead of approximate time matching to avoid deleting an adjacent booking.

**Resulting requirement statement:** Cancel only an existing target ID and return confirmation; an absent ID returns NOT_FOUND without affecting other entries.

**Verification method and expected result:** test; C-AR-07; planned case V-AR-07. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-ar-08"></a>
### D-AR-08 · ar-08@1

**Exact parent and objective:** sr-04@1 — Cancelling an existing ID removes its active booking and releases the slot; unknown or repeated cancellation returns NOT_FOUND without affecting others, and old IDs are not reused.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-2; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: After cancellation the same window can be rebooked with a new ID; repeating the old cancellation must not remove the new entry.

**Calculation / diagram / argument:** After removing B001 the same window accepts B002, proving removal from the conflict set. A repeat cancel(B001) must return NOT_FOUND while B002 remains, jointly checking release and non-reuse.

**Tradeoffs and applicability:** Combine monotonic identifiers with the active set; no second cancellation-state database is needed.

**Resulting requirement statement:** After cancellation the same window can be rebooked with a new ID; repeating the old cancellation must not remove the new entry.

**Verification method and expected result:** test; C-AR-08; planned case V-AR-08. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-ar-09"></a>
### D-AR-09 · ar-09@1

**Exact parent and objective:** sr-05@1 — List only active bookings sorted by start minute, end minute and ID, with normalized HH:MM and duration; mutating returned data must not alter system state.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-3; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Generate the agenda from the active set sorted by (start,end,id), regardless of creation order.

**Calculation / diagram / argument:** Book 09:30–10:30 as B001 then 08:00–09:00 as B002: expect B002 then B001, not insertion order.

**Tradeoffs and applicability:** For n≤40, O(n log n) sorting is adequate; cancelled entries are absent from the input set.

**Resulting requirement statement:** Generate the agenda from the active set sorted by (start,end,id), regardless of creation order.

**Verification method and expected result:** test; C-AR-09; planned case V-AR-09. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-ar-10"></a>
### D-AR-10 · ar-10@1

**Exact parent and objective:** sr-05@1 — List only active bookings sorted by start minute, end minute and ID, with normalized HH:MM and duration; mutating returned data must not alter system state.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-3; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Return normalized HH:MM, integer duration and fresh dictionaries; mutating confirmations or agenda lists must not affect internal bookings.

**Calculation / diagram / argument:** Render minute m using two-digit m//60 and m%60; duration=end−start. After mutating a returned time or appending ghost, rereading must return the original booking, demonstrating the read-only boundary.

**Tradeoffs and applicability:** Use immutable records and fresh output objects rather than copying the entire service.

**Resulting requirement statement:** Return normalized HH:MM, integer duration and fresh dictionaries; mutating confirmations or agenda lists must not affect internal bookings.

**Verification method and expected result:** test; C-AR-10; planned case V-AR-10. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-ar-11"></a>
### D-AR-11 · ar-11@1

**Exact parent and objective:** sr-06@1 — Use a fixed 600-minute denominator to compute occupied/free minutes, 15-minute slots and utilization to one decimal; recompute after cancellation.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-3; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Sum end−start over the active set for occupied minutes, with zero for an empty set and no cancelled entries.

**Calculation / diagram / argument:** SR-03 ensures non-overlap, allowing direct summation. Two 60-minute intervals give 120; cancel one and obtain 60, not the entire 150-minute span from 08:00 to 10:30.

**Tradeoffs and applicability:** This explicitly depends on non-overlap; supporting overlapping bookings would require an interval-union algorithm.

**Resulting requirement statement:** Sum end−start over the active set for occupied minutes, with zero for an empty set and no cancelled entries.

**Verification method and expected result:** test; C-AR-11; planned case V-AR-11. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-ar-12"></a>
### D-AR-12 · ar-12@1

**Exact parent and objective:** sr-06@1 — Use a fixed 600-minute denominator to compute occupied/free minutes, 15-minute slots and utilization to one decimal; recompute after cancellation.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-3; TR3 chapters 2–4 and the parent SR conditions

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: With fixed capacity 600 compute free=600−occupied, used_slots=occupied/15, free_slots=free/15 and utilization to one decimal with that denominator.

**Calculation / diagram / argument:** Each slot contributes 2.5%, so percentage tenths=occupied×1000/600 is an exact integer. Empty is 0/600=0.0%, full is 600/600=100.0%, and 120 minutes gives 20.0%.

**Tradeoffs and applicability:** Use integer tenths to avoid floating display error; fixed nonzero capacity avoids division by zero on an empty agenda.

**Resulting requirement statement:** With fixed capacity 600 compute free=600−occupied, used_slots=occupied/15, free_slots=free/15 and utilization to one decimal with that denominator.

**Verification method and expected result:** test; C-AR-12; planned case V-AR-12. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-dev; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

### Check the whole AR combination by SR

| Parent | All child versions | Combined coverage argument | Gaps / next step |
| --- | --- | --- | --- |
| sr-01@1 | ar-01@1, ar-02@1 | Parse to one unit, then check bounds/grid; both must pass before creation. | No scoped decomposition gap; execution awaits TR4 |
| sr-02@1 | ar-03@1, ar-04@1 | Non-reused IDs plus prechecked creation/confirmation jointly cover response and state; execute a separate system case in TR4. | No scoped decomposition gap; execution awaits TR4 |
| sr-03@1 | ar-05@1, ar-06@1 | Correct predicate plus scanning all active entries; testing the predicate alone cannot prove caller coverage. | No scoped decomposition gap; execution awaits TR4 |
| sr-04@1 | ar-07@1, ar-08@1 | Delete by ID plus rebooking and old-ID isolation cover cancellation state and subsequent behavior. | No scoped decomposition gap; execution awaits TR4 |
| sr-05@1 | ar-09@1, ar-10@1 | Numeric sorting plus normalized fresh output objects cover order, readable fields and read-only behavior. | No scoped decomposition gap; execution awaits TR4 |
| sr-06@1 | ar-11@1, ar-12@1 | Sum disjoint intervals plus fixed-600 conversion: 120+480=600, 8+32=40 and 20.0% is correct. | No scoped decomposition gap; execution awaits TR4 |

<!-- ipd-section:ar -->
## 6. Consolidate AR specifications and check SR coverage

Record the twelve chapter 5 ARs in [AR-TR3.md](AR-TR3.md), with unique D-AR links. Two ARs per SR is only this example’s outcome. Detailed design, implementation and results remain planned/not run; do not prefill final source digests or passes. Preserve this snapshot and create AR-TR4.md later.

<!-- ipd-section:implementation_plan -->
## 7. Plan TR4 detailed design, implementation and integration

TR4 implements validation, ledger, presentation and metrics, with one planned booking.py rather than a file per AR. Start with pure parsing/interval functions, then state changes, read views and summary. Use SHA-256 for actual implementation versions later; no future digest is referenced here.

<!-- ipd-section:verification -->
## 8. Design AR verification and regression scope

| Planned case | AR version | Independent expectation | Method/status |
| --- | --- | --- | --- |
| V-AR-01 | ar-01@1 | Parse two-digit HH:MM with 0≤h≤23 and 0≤m≤59 to 60h+m; otherwise return an explicit format or clock error. | test; not run until TR4 |
| V-AR-02 | ar-02@1 | Enforce 480≤start<end≤1080 and (start−480)%15=(end−480)%15=0 before creation. | test; not run until TR4 |
| V-AR-03 | ar-03@1 | Allocate increasing B001, B002… only for successful creations; rejection does not advance and cancellation does not rewind the counter. | test; not run until TR4 |
| V-AR-04 | ar-04@1 | After input and conflict prechecks, add exactly one booking and return ID, normalized times and end−start minutes; rejected paths do not mutate the ledger. | test; not run until TR4 |
| V-AR-05 | ar-05@1 | For validated positive-length intervals, return start<other_end and other_start<end; equality at a boundary is not a conflict. | test; not run until TR4 |
| V-AR-06 | ar-06@1 | Check all active bookings before creation; any conflict returns CONFLICT without changing the active list or the next successful ID. | test; not run until TR4 |
| V-AR-07 | ar-07@1 | Cancel only an existing target ID and return confirmation; an absent ID returns NOT_FOUND without affecting other entries. | test; not run until TR4 |
| V-AR-08 | ar-08@1 | After cancellation the same window can be rebooked with a new ID; repeating the old cancellation must not remove the new entry. | test; not run until TR4 |
| V-AR-09 | ar-09@1 | Generate the agenda from the active set sorted by (start,end,id), regardless of creation order. | test; not run until TR4 |
| V-AR-10 | ar-10@1 | Return normalized HH:MM, integer duration and fresh dictionaries; mutating confirmations or agenda lists must not affect internal bookings. | test; not run until TR4 |
| V-AR-11 | ar-11@1 | Sum end−start over the active set for occupied minutes, with zero for an empty set and no cancelled entries. | test; not run until TR4 |
| V-AR-12 | ar-12@1 | With fixed capacity 600 compute free=600−occupied, used_slots=occupied/15, free_slots=free/15 and utilization to one decimal with that denominator. | test; not run until TR4 |

Also execute V-SR-01…06 and V-IR-01…03 independently. Parent results must not be an AND of child pass flags. Regression includes adjacency, containment, repeat cancellation, read copies and empty/full days.

<!-- ipd-section:deliverables -->
## 9. Compile deliverables and design gaps

This document and the AR snapshot are primary outputs. Architecture and rationale are included here rather than split to inflate file counts. Actual code/test evidence is not yet available. demo-dev owns the planned TR4 work.

| Type / proposed necessity | Document ID / path | Exact version / digest | Requirements / scope | Owner | Status / gaps |
| --- | --- | --- | --- | --- | --- |
| Overall document; necessary | [TR3.md](TR3.md) | doc rev 1 | TR3 / mvp | demo-doc-owner | Filled; not approved |
| Register; necessary | [AR-TR3.md](AR-TR3.md) | doc rev 1 | 12 AR | demo-doc-owner | Stage snapshot |

<!-- ipd-section:review -->
## 10. Summarize review inputs and TR4 handoff

All six SRs have individual ARs and combined coverage arguments; all twelve ARs have criteria, modules and owners. TR4 receives this design, AR-TR3@doc1 and the verification plan. This is a teaching draft ready for detailed design, not human approval.

