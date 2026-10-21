---
instance_id: 'room-tr4-en'
increment: 'mvp'
requirements: 'ir-01@1, ir-02@1, ir-03@1, sr-01@1, sr-02@1, sr-03@1, sr-04@1, sr-05@1, sr-06@1, ar-01@1, ar-02@1, ar-03@1, ar-04@1, ar-05@1, ar-06@1, ar-07@1, ar-08@1, ar-09@1, ar-10@1, ar-11@1, ar-12@1'
owner: 'demo-doc-owner'
document_type: 'tr4_detail_implementation_test'
template_id: 'ipd-starter.tr4_detail_implementation_test'
template_version: '0.2.1'
template_sha256: '905f2ebeb8e92884abb1265e0b2985756b22edf7101d345dd961ba61cc74fba2'
locale: 'en'
scope: 'Synthetic standalone writing exercise; no governance acceptance'
---

# TR4 detailed design, implementation, testing and acceptance (discussion draft) — Offline single-room booking

> Completed synthetic teaching document, revision 1. Requirement IDs come from this example catalog.json and are not accepted governance facts in a real IPD project. No human approval is claimed. Each stage file is its completion snapshot; later outputs appear only in later stages.

<!-- ipd-section:baseline -->
## 1. Define delivery scope and design inputs

Inputs are [TR3@doc1](TR3.md), [AR-TR3@doc1](AR-TR3.md) and SR/IR snapshots. All 21 requirement contents remain @1; implementation results do not retroactively alter them. Actual IMPL-1 is [booking.py](../implementation/booking.py), SHA-256 `4c4dabae0c4b3e6028b8aecf83a04afd1efbc2badd39e8adfd4cf6609ef3afc4`.

Environment, execution time and both source digests are in [E1](../evidence/verification.json). E1 is actual execution with synthetic software inputs, not a user acceptance signature or IPD approval.

<!-- ipd-section:detail -->
## 2. Develop detailed design for each AR

<a id="impl-ar-01"></a>
### IMPL-AR-01 · ar-01@1

**Concrete design:** SR-01 needs a common integer representation: 08:00=480, 09:15=555, 18:00=1080. Reject missing zero in 9:00 and invalid minutes in 09:75 instead of permissive conversion.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::parse_time

**Satisfaction argument and limits:** Clock validity belongs here; operating hours belong to AR-02, keeping responsibilities separate. Expectation is C-AR-01; executed case V-AR-01 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<a id="impl-ar-02"></a>
### IMPL-AR-02 · ar-02@1

**Concrete design:** SR-01 defines the bounds and grid. 17:45=1065 to 18:00=1080 is a valid 15-minute booking; reject zero length, 07:45/18:15 boundary violations or off-grid 09:20.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::validate_window

**Satisfaction argument and limits:** Checking both endpoints makes the minimum positive duration 15 minutes without a separate floating duration threshold. Expectation is C-AR-02; executed case V-AR-02 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<a id="impl-ar-03"></a>
### IMPL-AR-03 · ar-03@1

**Concrete design:** With k successful creations, the next counter is k+1. Rejection adds no success and cancellation removes no historical success, preserving stable non-reused identifiers.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::Calendar.book

**Satisfaction argument and limits:** Use at least three digits, allowing growth beyond 999; at most 40 are active, but repeated cancel/rebook cycles are allowed. Expectation is C-AR-03; executed case V-AR-03 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<a id="impl-ar-04"></a>
### IMPL-AR-04 · ar-04@1

**Concrete design:** Prechecks before creation prevent rejected requests from leaving partial active entries. The first 08:00–09:00 confirmation is B001, 08:00, 09:00, 60, with exactly that entry in the agenda.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::Calendar.book/Booking.record

**Satisfaction argument and limits:** Guarantee serial behavior for expected input rejection, not durable transactions under memory exhaustion or power loss. Expectation is C-AR-04; executed case V-AR-04 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<a id="impl-ar-05"></a>
### IMPL-AR-05 · ar-05@1

**Concrete design:** Implement the SR-03 interval argument as a pure function: 480–540 against 540–555 is false; overlap, identical, contained and containing intervals are true; 465–480 is false.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::overlaps

**Satisfaction argument and limits:** Use strict rather than inclusive inequalities; inclusive comparison would wrongly reject adjacent bookings. Expectation is C-AR-05; executed case V-AR-05 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<a id="impl-ar-06"></a>
### IMPL-AR-06 · ar-06@1

**Concrete design:** Checking only one entry can miss another occupied interval. Scan the whole active set before committing. After B001 and a rejected overlap, the next valid request must be B002, not B003.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::Calendar.book

**Satisfaction argument and limits:** With at most 40 active entries a linear scan is adequate and transparent, without extrapolating to a large concurrent service. Expectation is C-AR-06; executed case V-AR-06 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<a id="impl-ar-07"></a>
### IMPL-AR-07 · ar-07@1

**Concrete design:** SR-04 release is active-set removal of the target ID. After removing sole B001 the set is empty; cancelling missing keeps it empty and reports a clear error.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::Calendar.cancel

**Satisfaction argument and limits:** Locate by ID instead of approximate time matching to avoid deleting an adjacent booking. Expectation is C-AR-07; executed case V-AR-07 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<a id="impl-ar-08"></a>
### IMPL-AR-08 · ar-08@1

**Concrete design:** After removing B001 the same window accepts B002, proving removal from the conflict set. A repeat cancel(B001) must return NOT_FOUND while B002 remains, jointly checking release and non-reuse.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::Calendar.cancel/book

**Satisfaction argument and limits:** Combine monotonic identifiers with the active set; no second cancellation-state database is needed. Expectation is C-AR-08; executed case V-AR-08 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<a id="impl-ar-09"></a>
### IMPL-AR-09 · ar-09@1

**Concrete design:** Book 09:30–10:30 as B001 then 08:00–09:00 as B002: expect B002 then B001, not insertion order.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::Calendar.agenda

**Satisfaction argument and limits:** For n≤40, O(n log n) sorting is adequate; cancelled entries are absent from the input set. Expectation is C-AR-09; executed case V-AR-09 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<a id="impl-ar-10"></a>
### IMPL-AR-10 · ar-10@1

**Concrete design:** Render minute m using two-digit m//60 and m%60; duration=end−start. After mutating a returned time or appending ghost, rereading must return the original booking, demonstrating the read-only boundary.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::Booking.record/Calendar.agenda

**Satisfaction argument and limits:** Use immutable records and fresh output objects rather than copying the entire service. Expectation is C-AR-10; executed case V-AR-10 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<a id="impl-ar-11"></a>
### IMPL-AR-11 · ar-11@1

**Concrete design:** SR-03 ensures non-overlap, allowing direct summation. Two 60-minute intervals give 120; cancel one and obtain 60, not the entire 150-minute span from 08:00 to 10:30.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::Calendar.occupied_minutes

**Satisfaction argument and limits:** This explicitly depends on non-overlap; supporting overlapping bookings would require an interval-union algorithm. Expectation is C-AR-11; executed case V-AR-11 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<a id="impl-ar-12"></a>
### IMPL-AR-12 · ar-12@1

**Concrete design:** Each slot contributes 2.5%, so percentage tenths=occupied×1000/600 is an exact integer. Empty is 0/600=0.0%, full is 600/600=100.0%, and 120 minutes gives 20.0%.

**Algorithm/interface location:** [booking.py](../implementation/booking.py)::Calendar.summary

**Satisfaction argument and limits:** Use integer tenths to avoid floating display error; fixed nonzero capacity avoids division by zero on an empty agenda. Expectation is C-AR-12; executed case V-AR-12 is in chapter 4. This design location is content version IMPL-1 with its digest in chapter 1.

<!-- ipd-section:implementation -->
## 3. Record actual implementation, builds and integration

Actual code contains parse_time, validate_window, overlaps, immutable Booking and Calendar. Standard library only, with no network, database or UI. Reproduce from this directory:

```console
python ../implementation/verify_demo.py
```

Default JSON output leaves saved evidence unchanged. Use --output with an explicit temporary file to save a new run. Current E1 reports 21/21 passes; this is neither installer verification nor cross-platform qualification.

| Module / AR version | Detailed design version | Implementation version / configuration | Build environment and result | Integration status | Deviation / decision reference |
| --- | --- | --- | --- | --- | --- |
| validation / ar-01@1 | IMPL-AR-01 / doc1 | IMPL-1 / parse_time | Python 3.12.14 / V-AR-01 | Executed with synthetic inputs | No observed deviation; no approval |
| validation / ar-02@1 | IMPL-AR-02 / doc1 | IMPL-1 / validate_window | Python 3.12.14 / V-AR-02 | Executed with synthetic inputs | No observed deviation; no approval |
| ledger / ar-03@1 | IMPL-AR-03 / doc1 | IMPL-1 / Calendar.book | Python 3.12.14 / V-AR-03 | Executed with synthetic inputs | No observed deviation; no approval |
| ledger / ar-04@1 | IMPL-AR-04 / doc1 | IMPL-1 / Calendar.book/Booking.record | Python 3.12.14 / V-AR-04 | Executed with synthetic inputs | No observed deviation; no approval |
| ledger / ar-05@1 | IMPL-AR-05 / doc1 | IMPL-1 / overlaps | Python 3.12.14 / V-AR-05 | Executed with synthetic inputs | No observed deviation; no approval |
| ledger / ar-06@1 | IMPL-AR-06 / doc1 | IMPL-1 / Calendar.book | Python 3.12.14 / V-AR-06 | Executed with synthetic inputs | No observed deviation; no approval |
| ledger / ar-07@1 | IMPL-AR-07 / doc1 | IMPL-1 / Calendar.cancel | Python 3.12.14 / V-AR-07 | Executed with synthetic inputs | No observed deviation; no approval |
| ledger / ar-08@1 | IMPL-AR-08 / doc1 | IMPL-1 / Calendar.cancel/book | Python 3.12.14 / V-AR-08 | Executed with synthetic inputs | No observed deviation; no approval |
| presentation / ar-09@1 | IMPL-AR-09 / doc1 | IMPL-1 / Calendar.agenda | Python 3.12.14 / V-AR-09 | Executed with synthetic inputs | No observed deviation; no approval |
| presentation / ar-10@1 | IMPL-AR-10 / doc1 | IMPL-1 / Booking.record/Calendar.agenda | Python 3.12.14 / V-AR-10 | Executed with synthetic inputs | No observed deviation; no approval |
| metrics / ar-11@1 | IMPL-AR-11 / doc1 | IMPL-1 / Calendar.occupied_minutes | Python 3.12.14 / V-AR-11 | Executed with synthetic inputs | No observed deviation; no approval |
| metrics / ar-12@1 | IMPL-AR-12 / doc1 | IMPL-1 / Calendar.summary | Python 3.12.14 / V-AR-12 | Executed with synthetic inputs | No observed deviation; no approval |

<!-- ipd-section:ar_verification -->
## 4. Execute AR verification and update the register

Execute twelve AR cases with independently specified values/sequences, not copied implementation returns. Rows show observations and may contain several assertions per AR. Update [AR-TR4.md](AR-TR4.md) without overwriting the TR3 not-run snapshot.

| Exact AR version / criterion ID | Case / environment version | Implementation configuration | Expected result | Actual result / status | Evidence version / defect |
| --- | --- | --- | --- | --- | --- |
| ar-01@1 / C-AR-01 | V-AR-01 / Python 3.12.14 | IMPL-1 | `[480,555,1080,"INVALID_FORMAT","INVALID_TIME"]` | `[480,555,1080,"INVALID_FORMAT","INVALID_TIME"]` / passed | [E1](../evidence/verification.json) / V-AR-01 |
| ar-02@1 / C-AR-02 | V-AR-02 / Python 3.12.14 | IMPL-1 | `[[1065,1080],"INVALID_WINDOW","INVALID_WINDOW","INVALID_GRID","INVALID_WINDOW"]` | `[[1065,1080],"INVALID_WINDOW","INVALID_WINDOW","INVALID_GRID","INVALID_WINDOW"]` / passed | [E1](../evidence/verification.json) / V-AR-02 |
| ar-03@1 / C-AR-03 | V-AR-03 / Python 3.12.14 | IMPL-1 | `["B001","B002"]` | `["B001","B002"]` / passed | [E1](../evidence/verification.json) / V-AR-03 |
| ar-04@1 / C-AR-04 | V-AR-04 / Python 3.12.14 | IMPL-1 | `{"confirmation":{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"agenda":[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]}` | `{"confirmation":{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"agenda":[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]}` / passed | [E1](../evidence/verification.json) / V-AR-04 |
| ar-05@1 / C-AR-05 | V-AR-05 / Python 3.12.14 | IMPL-1 | `[false,true,true,true,true,false]` | `[false,true,true,true,true,false]` / passed | [E1](../evidence/verification.json) / V-AR-05 |
| ar-06@1 / C-AR-06 | V-AR-06 / Python 3.12.14 | IMPL-1 | `["CONFLICT",true,"B002"]` | `["CONFLICT",true,"B002"]` / passed | [E1](../evidence/verification.json) / V-AR-06 |
| ar-07@1 / C-AR-07 | V-AR-07 / Python 3.12.14 | IMPL-1 | `[{"id":"B001","cancelled":true},[],"NOT_FOUND",[]]` | `[{"id":"B001","cancelled":true},[],"NOT_FOUND",[]]` / passed | [E1](../evidence/verification.json) / V-AR-07 |
| ar-08@1 / C-AR-08 | V-AR-08 / Python 3.12.14 | IMPL-1 | `["B002","NOT_FOUND",["B002"]]` | `["B002","NOT_FOUND",["B002"]]` / passed | [E1](../evidence/verification.json) / V-AR-08 |
| ar-09@1 / C-AR-09 | V-AR-09 / Python 3.12.14 | IMPL-1 | `["B002","B001"]` | `["B002","B001"]` / passed | [E1](../evidence/verification.json) / V-AR-09 |
| ar-10@1 / C-AR-10 | V-AR-10 / Python 3.12.14 | IMPL-1 | `[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]` | `[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]` / passed | [E1](../evidence/verification.json) / V-AR-10 |
| ar-11@1 / C-AR-11 | V-AR-11 / Python 3.12.14 | IMPL-1 | `120` | `120` / passed | [E1](../evidence/verification.json) / V-AR-11 |
| ar-12@1 / C-AR-12 | V-AR-12 / Python 3.12.14 | IMPL-1 | `[{"occupied_min":0,"free_min":600,"used_slots":0,"free_slots":40,"utilization_percent":"0.0"},{"occupied_min":600,"free_min":0,"used_slots":40,"free_slots":0,"utilization_percent":"100.0"}]` | `[{"occupied_min":0,"free_min":600,"used_slots":0,"free_slots":40,"utilization_percent":"0.0"},{"occupied_min":600,"free_min":0,"used_slots":40,"free_slots":0,"utilization_percent":"100.0"}]` / passed | [E1](../evidence/verification.json) / V-AR-12 |

<!-- ipd-section:system_acceptance -->
## 5. Execute SR verification and IR user acceptance

The six SR and three IR cases each drive fresh service scenarios and assert expected outputs. They never infer parent outcomes from AR pass flags. IR cases are automated scenario demonstrations; actual human validation, content review and approval are not performed.

| Level / exact requirement version | Criterion / scenario | Configuration / environment | Expected | Actual result / status | Evidence / decision reference |
| --- | --- | --- | --- | --- | --- |
| SR / sr-01@1 | C-SR-01 / SC-1 | IMPL-1 / Python 3.12.14 | `["INVALID_GRID",{"id":"B001","start":"17:45","end":"18:00","duration_min":15}]` | `["INVALID_GRID",{"id":"B001","start":"17:45","end":"18:00","duration_min":15}]` / passed (software) | V-SR-01; [E1](../evidence/verification.json); no human approval |
| SR / sr-02@1 | C-SR-02 / SC-1 | IMPL-1 / Python 3.12.14 | `{"confirmation":{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"agenda":[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]}` | `{"confirmation":{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"agenda":[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]}` / passed (software) | V-SR-02; [E1](../evidence/verification.json); no human approval |
| SR / sr-03@1 | C-SR-03 / SC-2 | IMPL-1 / Python 3.12.14 | `["CONFLICT",[{"id":"B001","start":"08:00","end":"09:00","duration_min":60},{"id":"B002","start":"09:00","end":"09:30","duration_min":30}]]` | `["CONFLICT",[{"id":"B001","start":"08:00","end":"09:00","duration_min":60},{"id":"B002","start":"09:00","end":"09:30","duration_min":30}]]` / passed (software) | V-SR-03; [E1](../evidence/verification.json); no human approval |
| SR / sr-04@1 | C-SR-04 / SC-2 | IMPL-1 / Python 3.12.14 | `["B002","NOT_FOUND",["B002"]]` | `["B002","NOT_FOUND",["B002"]]` / passed (software) | V-SR-04; [E1](../evidence/verification.json); no human approval |
| SR / sr-05@1 | C-SR-05 / SC-3 | IMPL-1 / Python 3.12.14 | `[{"id":"B002","start":"08:00","end":"09:00","duration_min":60},{"id":"B001","start":"09:30","end":"10:30","duration_min":60}]` | `[{"id":"B002","start":"08:00","end":"09:00","duration_min":60},{"id":"B001","start":"09:30","end":"10:30","duration_min":60}]` / passed (software) | V-SR-05; [E1](../evidence/verification.json); no human approval |
| SR / sr-06@1 | C-SR-06 / SC-3 | IMPL-1 / Python 3.12.14 | `[{"occupied_min":120,"free_min":480,"used_slots":8,"free_slots":32,"utilization_percent":"20.0"},{"occupied_min":60,"free_min":540,"used_slots":4,"free_slots":36,"utilization_percent":"10.0"}]` | `[{"occupied_min":120,"free_min":480,"used_slots":8,"free_slots":32,"utilization_percent":"20.0"},{"occupied_min":60,"free_min":540,"used_slots":4,"free_slots":36,"utilization_percent":"10.0"}]` / passed (software) | V-SR-06; [E1](../evidence/verification.json); no human approval |
| IR / ir-01@1 | C-IR-01 / SC-1 | IMPL-1 / Python 3.12.14 | `[{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"INVALID_GRID",[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]]` | `[{"id":"B001","start":"08:00","end":"09:00","duration_min":60},"INVALID_GRID",[{"id":"B001","start":"08:00","end":"09:00","duration_min":60}]]` / passed (software) | V-IR-01; [E1](../evidence/verification.json); no human approval |
| IR / ir-02@1 | C-IR-02 / SC-2 | IMPL-1 / Python 3.12.14 | `["B002","CONFLICT",{"id":"B001","cancelled":true},"B003",2]` | `["B002","CONFLICT",{"id":"B001","cancelled":true},"B003",2]` / passed (software) | V-IR-02; [E1](../evidence/verification.json); no human approval |
| IR / ir-03@1 | C-IR-03 / SC-3 | IMPL-1 / Python 3.12.14 | `{"agenda":[{"id":"B002","start":"08:00","end":"09:00","duration_min":60},{"id":"B001","start":"09:30","end":"10:30","duration_min":60}],"summary":{"occupied_min":120,"free_min":480,"used_slots":8,"free_slots":32,"utilization_percent":"20.0"}}` | `{"agenda":[{"id":"B002","start":"08:00","end":"09:00","duration_min":60},{"id":"B001","start":"09:30","end":"10:30","duration_min":60}],"summary":{"occupied_min":120,"free_min":480,"used_slots":8,"free_slots":32,"utilization_percent":"20.0"}}` / passed (software) | V-IR-03; [E1](../evidence/verification.json); no human approval |

<!-- ipd-section:regression -->
## 6. Address defects, requirement changes and regression

All 21 independent-expectation cases match; no fictitious closed-defect record was created. Coverage includes clock/grid, adjacency/overlap/containment, rejection state preservation, cancel/rebook/repeat cancel, sorted copies, the 120-minute example and empty/full days. Changing overlap logic affects AR-05/06, SR-03 and IR-02 and may invalidate SR-06 summation, so rerun all 21. Excluded concurrency, persistence and real GUI usability are not claimed tested.

<!-- ipd-section:delivery -->
## 7. Compile delivery configuration and files

Deliver the standard-library core, runner, E1 and bilingual stage documents/snapshots. The normal case is 120 occupied, 480 free, 8/32 slots, 20.0%; cancel B001 and obtain 60, 540, 4/36, 10.0%. Deliver the input constraints and limits with the bundle.

| Type / proposed necessity | Document ID / path | Exact version / digest | Requirements / scope | Owner | Status / gaps |
| --- | --- | --- | --- | --- | --- |
| Overall document; necessary | [TR4.md](TR4.md) | doc rev 1 | TR4 / mvp | demo-doc-owner | Filled; not approved |
| Register; necessary | [AR-TR4.md](AR-TR4.md) | doc rev 1 | 12 AR | demo-doc-owner | Stage snapshot |
| Actual implementation/evidence | [../implementation/booking.py](../implementation/booking.py) | E1 / source SHA-256 | mvp | demo-dev | Executed; synthetic inputs |
| Actual implementation/evidence | [../implementation/verify_demo.py](../implementation/verify_demo.py) | E1 / source SHA-256 | mvp | demo-dev | Executed; synthetic inputs |
| Actual implementation/evidence | [../evidence/verification.json](../evidence/verification.json) | E1 / source SHA-256 | mvp | demo-dev | Executed; synthetic inputs |

<!-- ipd-section:review -->
## 8. Summarize completion and acceptance inputs

Writing/traceability coverage is 3IR→6SR→12AR with locatable derivations, designs and cases. Software results: 12 AR + 6 SR + 3 IR scenarios = 21/21 passed. Human acceptance: not performed; governance/content approval: not granted; deployment/publication: not performed. This establishes an executable synthetic example and its document chain, not production readiness.

