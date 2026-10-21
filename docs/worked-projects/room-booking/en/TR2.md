---
instance_id: 'room-tr2-en'
increment: 'mvp'
requirements: 'ir-01@1, ir-02@1, ir-03@1, sr-01@1, sr-02@1, sr-03@1, sr-04@1, sr-05@1, sr-06@1'
owner: 'demo-doc-owner'
document_type: 'tr2_scenarios_allocation'
template_id: 'ipd-starter.tr2_scenarios_allocation'
template_version: '0.2.1'
template_sha256: '821546ec635e9ce0e9f62af1a0bd478920840d30a68d9e3e5334b809d023f5fc'
locale: 'en'
scope: 'Synthetic standalone writing exercise; no governance acceptance'
---

# TR2 scenario analysis and module allocation (discussion draft) — Offline single-room booking

> Completed synthetic teaching document, revision 1. Requirement IDs come from this example catalog.json and are not accepted governance facts in a real IPD project. No human approval is claimed. Each stage file is its completion snapshot; later outputs appear only in later stages.

<!-- ipd-section:baseline -->
## 1. Define scope and TR1 inputs

Inputs are [TR1@doc1](TR1.md), [IR snapshot@doc1](IR-TR1.md) and BRIEF@1. All three IRs are scoped, with no prior increment or actual approval. Analysis starts with IRs only; six SRs receive @1 teaching catalog versions after chapter 3, then document metadata is updated.

<!-- ipd-section:scenarios -->
## 2. Analyze scenarios and system boundaries

| Scenario | Source/objective | Normal and failure flow | Boundary/premises |
| --- | --- | --- | --- |
| SC-1 | U1 / ir-01@1 | Submit 08:00–09:00 and confirm; reject off-grid 09:20–10:00 | Empty day, strict format; boundary 17:45–18:00 is valid |
| SC-2 | U2 / ir-02@1 | With 08:00–09:00 active, accept adjacent 09:00 and reject overlapping 08:45; cancel then rebook | Unknown/repeated cancellation reports error without deleting the new ID |
| SC-3 | U3 / ir-03@1 | Book a later meeting first, then an earlier one; view time order and capacity | Empty/full day, recomputation after cancel, output copies |

The system boundary is a single-process Calendar API. Convert clocks to minutes, then validate the business window. Creation checks the active set; cancellation changes it; agenda/summary are read-only. SC-2 allows a shared 09:00 boundary. SC-3 includes gaps, so occupancy cannot be the first-to-last time span. These are premises; individual SRs are formed next.

<!-- ipd-section:decomposition -->
## 3. Derive each SR from its parent IR

<a id="d-sr-01"></a>
### D-SR-01 · sr-01@1

**Exact parent and objective:** ir-01@1 — Within the operating day, a user can create a booking on a 15-minute grid and receive confirmation; invalid inputs are explicitly rejected.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-1; TR2 chapter 2

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Accept only HH:MM clock values satisfying 08:00≤start<end≤18:00 with both endpoints on the 15-minute grid.

**Calculation / diagram / argument:** Convert SC-1 input to minutes m=60h+min. Capacity=(18−8)×60=600 minutes=600/15=40 slots. Endpoints are 480+15k for k=0…40, with start<end. Check format, clock validity and business window separately.

**Tradeoffs and applicability:** Use integer minutes to avoid floating boundaries; 09:20 is a valid clock value but not on the grid.

**Resulting requirement statement:** Accept only HH:MM clock values satisfying 08:00≤start<end≤18:00 with both endpoints on the 15-minute grid.

**Verification method and expected result:** test; C-SR-01; planned case V-SR-01. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-systems; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-sr-02"></a>
### D-SR-02 · sr-02@1

**Exact parent and objective:** ir-01@1 — Within the operating day, a user can create a booking on a 15-minute grid and receive confirmation; invalid inputs are explicitly rejected.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-1; TR2 chapter 2

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: A valid conflict-free request creates one active booking and returns a non-reused process-local ID, times and duration; rejection changes neither active state nor the next ID.

**Calculation / diagram / argument:** The user must associate confirmation with later cancellation, so return a stable ID and window rather than a bare success flag. Validate before mutation so rejected paths leave no booking or consumed ID.

**Tradeoffs and applicability:** A monotonic counter guarantees process-local uniqueness only, not uniqueness across restarts or durable transactions.

**Resulting requirement statement:** A valid conflict-free request creates one active booking and returns a non-reused process-local ID, times and duration; rejection changes neither active state nor the next ID.

**Verification method and expected result:** test; C-SR-02; planned case V-SR-02. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-systems; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-sr-03"></a>
### D-SR-03 · sr-03@1

**Exact parent and objective:** ir-02@1 — Active bookings must not overlap, adjacent bookings are allowed, and a cancelled slot can immediately be booked again.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-2; TR2 chapter 2

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Use half-open intervals [start,end): touching endpoints are allowed; reject any positive overlap without changing the active list.

**Calculation / diagram / argument:** Disjoint intervals satisfy b≤c or d≤a; negation gives a<d and c<b. Strict inequalities permit [08:00,09:00) next to [09:00,09:30), while containment and identical intervals still conflict.

**Tradeoffs and applicability:** Scan active bookings in O(n); at most 40 positive-length bookings fit, so an interval tree is unnecessary.

**Resulting requirement statement:** Use half-open intervals [start,end): touching endpoints are allowed; reject any positive overlap without changing the active list.

**Verification method and expected result:** test; C-SR-03; planned case V-SR-03. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-systems; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-sr-04"></a>
### D-SR-04 · sr-04@1

**Exact parent and objective:** ir-02@1 — Active bookings must not overlap, adjacent bookings are allowed, and a cancelled slot can immediately be booked again.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-2; TR2 chapter 2

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Cancelling an existing ID removes its active booking and releases the slot; unknown or repeated cancellation returns NOT_FOUND without affecting others, and old IDs are not reused.

**Calculation / diagram / argument:** Release means removing the entry from conflict scanning; immediately rebooking its exact window must succeed. Reusing IDs could make a delayed repeat cancel delete a new booking, so the counter stays monotonic after cancellation.

**Tradeoffs and applicability:** Report unknown cancellation explicitly rather than claiming it was cancelled again; no distributed idempotency protocol is introduced.

**Resulting requirement statement:** Cancelling an existing ID removes its active booking and releases the slot; unknown or repeated cancellation returns NOT_FOUND without affecting others, and old IDs are not reused.

**Verification method and expected result:** test; C-SR-04; planned case V-SR-04. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-systems; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-sr-05"></a>
### D-SR-05 · sr-05@1

**Exact parent and objective:** ir-03@1 — The user can view active bookings in time order and see occupied/free minutes, slot counts and daily utilization.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-3; TR2 chapter 2

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: List only active bookings sorted by start minute, end minute and ID, with normalized HH:MM and duration; mutating returned data must not alter system state.

**Calculation / diagram / argument:** SC-3 may book a later meeting first, so creation order is not agenda order. Render from the active set and return fresh dictionaries so viewing remains read-only.

**Tradeoffs and applicability:** Declare deterministic ordering. Equal starts cannot coexist in this non-overlapping single room, but secondary keys keep formatting deterministic.

**Resulting requirement statement:** List only active bookings sorted by start minute, end minute and ID, with normalized HH:MM and duration; mutating returned data must not alter system state.

**Verification method and expected result:** test; C-SR-05; planned case V-SR-05. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-systems; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

<a id="d-sr-06"></a>
### D-SR-06 · sr-06@1

**Exact parent and objective:** ir-03@1 — The user can view active bookings in time order and see occupied/free minutes, slot counts and daily utilization.

**Scenario / design premises:** BRIEF@1/C1–C5; SC-3; TR2 chapter 2

**Derivation and necessity:** Identify this observable system/module responsibility needed for the parent objective: Use a fixed 600-minute denominator to compute occupied/free minutes, 15-minute slots and utilization to one decimal; recompute after cancellation.

**Calculation / diagram / argument:** SR-03 guarantees disjoint active intervals, so union length=Σ(end−start). 08:00–09:00 plus 09:30–10:30 gives 60+60=120 occupied minutes, 480 free, 8 used slots, 32 free slots and 120/600×100=20.0% utilization.

**Tradeoffs and applicability:** Each slot is 15/600×100=2.5%, exactly representable to one decimal; never use the first-to-last booking span as denominator.

**Resulting requirement statement:** Use a fixed 600-minute denominator to compute occupied/free minutes, 15-minute slots and utilization to one decimal; recompute after cancellation.

**Verification method and expected result:** test; C-SR-06; planned case V-SR-06. Assert the stated requirement conditions; this stage has no executed pass result.

**Owner and open issues:** demo-systems; derivation complete for the synthetic inputs; verification awaits TR4, with no approval claimed.

### Check the whole child set by IR

| Parent | All child versions | Combined coverage argument | Gaps / next step |
| --- | --- | --- | --- |
| ir-01@1 | sr-01@1, sr-02@1 | Input validity plus confirmation/state consistency cover create and reject, without adding a latency promise. | No scoped decomposition gap; execution awaits TR4 |
| ir-02@1 | sr-03@1, sr-04@1 | Conflict scanning plus cancellation/release cover contention, adjacency and reuse; cancellation success alone does not establish conflict safety. | No scoped decomposition gap; execution awaits TR4 |
| ir-03@1 | sr-05@1, sr-06@1 | Active agenda plus fixed-capacity summary cover time placement and quantity; summary depends on SR-03 non-overlap. | No scoped decomposition gap; execution awaits TR4 |

<!-- ipd-section:sr -->
## 4. Consolidate SR specifications and check IR coverage

Record all six chapter 3 SRs in [SR-TR2.md](SR-TR2.md), linking scenario/constraint cells to unique D-SR records. Parent IR cells may span two rows, never child identity cells. The 3→6 count is this example’s outcome, not a mandatory two-SR-per-IR rule. AR cells remain not formed, with demo-dev assigned TR3 allocation.

<!-- ipd-section:allocation -->
## 5. Define modules and allocate system responsibilities

Select four logical responsibility units, which may share one source file. Modules are neither file counts nor AR counts. Conflict/create/cancel share one active set. Utilization depends on SR-03 non-overlap without changing SR-06’s primary IR parent.

| Module | Exact SR versions | Responsibility and boundary | Collaborating modules / interfaces | Budget / rationale | Gaps / owner |
| --- | --- | --- | --- | --- | --- |
| validation | sr-01@1 | Parsing/business window | ledger | 600 min / 15 min | demo-dev |
| ledger | sr-02@1, sr-03@1, sr-04@1 | Create/conflict/cancel/IDs | validation/presentation | n≤40; serial | demo-dev |
| presentation | sr-05@1 | Sorting/read-only objects | ledger | O(n log n); n≤40 | demo-dev |
| metrics | sr-06@1 | Occupancy/ratio | ledger | 600 min; 40 slots | demo-dev |

<!-- ipd-section:interfaces -->
## 6. Define interfaces and cross-module constraints

API: book(start,end) returns confirmation or explicit error; cancel(id) returns confirmation or NOT_FOUND; agenda() returns a fresh list; summary() a fresh summary object. Input/conflict rejection precedes mutation. There are no network, repository lock or platform identity interfaces. Cancel/create preserve ID non-reuse and read views expose no writable internals.

<!-- ipd-section:verification -->
## 7. Plan SR verification and IR user validation

Plan independent system cases V-SR-01…06 instead of inferring from AR pass flags: input/grid bounds; confirmation/state; adjacency/overlap; cancel/rebook; ordered read-only output after out-of-order creation; 120/600 utilization and 60/600 after cancellation. Separately plan three V-IR scenarios. These are planned cases, not executed results.

<!-- ipd-section:deliverables -->
## 8. Compile deliverables, risks and open items

Primary outputs are the analysis and SR snapshot. SR-01/02 cover IR-01, SR-03/04 IR-02, and SR-05/06 IR-03, with no unresolved parents. C4 limits remain; human acceptance remains unperformed.

| Type / proposed necessity | Document ID / path | Exact version / digest | Requirements / scope | Owner | Status / gaps |
| --- | --- | --- | --- | --- | --- |
| Overall document; necessary | [TR2.md](TR2.md) | doc rev 1 | TR2 / mvp | demo-doc-owner | Filled; not approved |
| Register; necessary | [SR-TR2.md](SR-TR2.md) | doc rev 1 | 6 SR | demo-doc-owner | Stage snapshot |

<!-- ipd-section:review -->
## 9. Summarize review inputs and TR3 design handoff

Handoff: six SRs, individual D-SR arguments, four modules, interfaces and the 600-minute/40-slot bounds. Parent coverage is 3/3; no content approval occurs. ARs, actual implementation versions and executed results are not yet available.

