---
instance_id: 'room-ar-tr3-en'
increment: 'mvp'
requirements: 'ar-01@1, ar-02@1, ar-03@1, ar-04@1, ar-05@1, ar-06@1, ar-07@1, ar-08@1, ar-09@1, ar-10@1, ar-11@1, ar-12@1'
owner: 'demo-doc-owner'
document_type: 'ar_spec'
template_id: 'ipd-starter.ar_spec'
template_version: '1.1.1'
template_sha256: '0bcfaa12a67f4b92fa782a53dcedbf5ffb497572b4d8f3ac72f74b0bfe4bfc3d'
locale: 'en'
scope: 'Synthetic standalone writing exercise; no governance acceptance'
---

# AR allocated requirements register — Offline single-room booking


> Completed synthetic teaching register, document revision 1; snapshot at TR3. Educational identifiers do not establish governance acceptance or approval.

<!-- ipd-section:guidance -->
## Entry rules and baselines

Inputs are [BRIEF@1](source-brief.md), [educational catalog@1](../catalog.json), and [TR3 overall document](TR3.md). Metadata requirements exactly match all rows. The single Owner is demo-doc-owner, an educational role label, not an authenticated identity. Later revisions preserve this snapshot.

<!-- ipd-section:register -->
## Requirements register

<table data-ipd-table="requirements">
<thead>
<tr>
<th data-ipd-column="requirement">AR ID / version</th>
<th data-ipd-column="parent">Exact parent SR version</th>
<th data-ipd-column="assigned_module">Allocated module and shared design context</th>
<th data-ipd-column="responsibility">Responsibility boundary and owner</th>
<th data-ipd-column="behavior_constraints">Module behavior, inputs, outputs and constraints</th>
<th data-ipd-column="interfaces_budget">Interfaces, resource budgets and failure handling</th>
<th data-ipd-column="design_implementation">High-level / detailed design and implementation versions</th>
<th data-ipd-column="verification">Module verification methods, criterion IDs and expected values</th>
<th data-ipd-column="result_evidence">Actual results, evidence versions and defects</th>
<th data-ipd-column="regression">Impact and regression scope</th>
<th data-ipd-column="increment_status">Increment, maturity and deferred scope</th>
</tr>
</thead>
<tbody>
<tr>
<td>ar-01@1</td>
<td rowspan="2">sr-01@1</td>
<td>validation; SC-1</td>
<td>demo-dev; Clock validity belongs here; operating hours belong to AR-02, keeping responsibilities separate.</td>
<td>Parse two-digit HH:MM with 0≤h≤23 and 0≤m≤59 to 60h+m; otherwise return an explicit format or clock error.</td>
<td>SR-01 needs a common integer representation: 08:00=480, 09:15=555, 18:00=1080. Reject missing zero in 9:00 and invalid minutes in 09:75 instead of permissive conversion.</td>
<td><a href="TR3.md#d-ar-01">D-AR-01</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-01 / V-AR-01</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
<tr>
<td>ar-02@1</td>
<td>validation; SC-1</td>
<td>demo-dev; Checking both endpoints makes the minimum positive duration 15 minutes without a separate floating duration threshold.</td>
<td>Enforce 480≤start&lt;end≤1080 and (start−480)%15=(end−480)%15=0 before creation.</td>
<td>SR-01 defines the bounds and grid. 17:45=1065 to 18:00=1080 is a valid 15-minute booking; reject zero length, 07:45/18:15 boundary violations or off-grid 09:20.</td>
<td><a href="TR3.md#d-ar-02">D-AR-02</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-02 / V-AR-02</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
<tr>
<td>ar-03@1</td>
<td rowspan="2">sr-02@1</td>
<td>ledger; SC-1</td>
<td>demo-dev; Use at least three digits, allowing growth beyond 999; at most 40 are active, but repeated cancel/rebook cycles are allowed.</td>
<td>Allocate increasing B001, B002… only for successful creations; rejection does not advance and cancellation does not rewind the counter.</td>
<td>With k successful creations, the next counter is k+1. Rejection adds no success and cancellation removes no historical success, preserving stable non-reused identifiers.</td>
<td><a href="TR3.md#d-ar-03">D-AR-03</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-03 / V-AR-03</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
<tr>
<td>ar-04@1</td>
<td>ledger; SC-1</td>
<td>demo-dev; Guarantee serial behavior for expected input rejection, not durable transactions under memory exhaustion or power loss.</td>
<td>After input and conflict prechecks, add exactly one booking and return ID, normalized times and end−start minutes; rejected paths do not mutate the ledger.</td>
<td>Prechecks before creation prevent rejected requests from leaving partial active entries. The first 08:00–09:00 confirmation is B001, 08:00, 09:00, 60, with exactly that entry in the agenda.</td>
<td><a href="TR3.md#d-ar-04">D-AR-04</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-04 / V-AR-04</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
<tr>
<td>ar-05@1</td>
<td rowspan="2">sr-03@1</td>
<td>ledger; SC-2</td>
<td>demo-dev; Use strict rather than inclusive inequalities; inclusive comparison would wrongly reject adjacent bookings.</td>
<td>For validated positive-length intervals, return start&lt;other_end and other_start&lt;end; equality at a boundary is not a conflict.</td>
<td>Implement the SR-03 interval argument as a pure function: 480–540 against 540–555 is false; overlap, identical, contained and containing intervals are true; 465–480 is false.</td>
<td><a href="TR3.md#d-ar-05">D-AR-05</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-05 / V-AR-05</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
<tr>
<td>ar-06@1</td>
<td>ledger; SC-2</td>
<td>demo-dev; With at most 40 active entries a linear scan is adequate and transparent, without extrapolating to a large concurrent service.</td>
<td>Check all active bookings before creation; any conflict returns CONFLICT without changing the active list or the next successful ID.</td>
<td>Checking only one entry can miss another occupied interval. Scan the whole active set before committing. After B001 and a rejected overlap, the next valid request must be B002, not B003.</td>
<td><a href="TR3.md#d-ar-06">D-AR-06</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-06 / V-AR-06</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
<tr>
<td>ar-07@1</td>
<td rowspan="2">sr-04@1</td>
<td>ledger; SC-2</td>
<td>demo-dev; Locate by ID instead of approximate time matching to avoid deleting an adjacent booking.</td>
<td>Cancel only an existing target ID and return confirmation; an absent ID returns NOT_FOUND without affecting other entries.</td>
<td>SR-04 release is active-set removal of the target ID. After removing sole B001 the set is empty; cancelling missing keeps it empty and reports a clear error.</td>
<td><a href="TR3.md#d-ar-07">D-AR-07</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-07 / V-AR-07</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
<tr>
<td>ar-08@1</td>
<td>ledger; SC-2</td>
<td>demo-dev; Combine monotonic identifiers with the active set; no second cancellation-state database is needed.</td>
<td>After cancellation the same window can be rebooked with a new ID; repeating the old cancellation must not remove the new entry.</td>
<td>After removing B001 the same window accepts B002, proving removal from the conflict set. A repeat cancel(B001) must return NOT_FOUND while B002 remains, jointly checking release and non-reuse.</td>
<td><a href="TR3.md#d-ar-08">D-AR-08</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-08 / V-AR-08</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
<tr>
<td>ar-09@1</td>
<td rowspan="2">sr-05@1</td>
<td>presentation; SC-3</td>
<td>demo-dev; For n≤40, O(n log n) sorting is adequate; cancelled entries are absent from the input set.</td>
<td>Generate the agenda from the active set sorted by (start,end,id), regardless of creation order.</td>
<td>Book 09:30–10:30 as B001 then 08:00–09:00 as B002: expect B002 then B001, not insertion order.</td>
<td><a href="TR3.md#d-ar-09">D-AR-09</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-09 / V-AR-09</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
<tr>
<td>ar-10@1</td>
<td>presentation; SC-3</td>
<td>demo-dev; Use immutable records and fresh output objects rather than copying the entire service.</td>
<td>Return normalized HH:MM, integer duration and fresh dictionaries; mutating confirmations or agenda lists must not affect internal bookings.</td>
<td>Render minute m using two-digit m//60 and m%60; duration=end−start. After mutating a returned time or appending ghost, rereading must return the original booking, demonstrating the read-only boundary.</td>
<td><a href="TR3.md#d-ar-10">D-AR-10</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-10 / V-AR-10</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
<tr>
<td>ar-11@1</td>
<td rowspan="2">sr-06@1</td>
<td>metrics; SC-3</td>
<td>demo-dev; This explicitly depends on non-overlap; supporting overlapping bookings would require an interval-union algorithm.</td>
<td>Sum end−start over the active set for occupied minutes, with zero for an empty set and no cancelled entries.</td>
<td>SR-03 ensures non-overlap, allowing direct summation. Two 60-minute intervals give 120; cancel one and obtain 60, not the entire 150-minute span from 08:00 to 10:30.</td>
<td><a href="TR3.md#d-ar-11">D-AR-11</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-11 / V-AR-11</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
<tr>
<td>ar-12@1</td>
<td>metrics; SC-3</td>
<td>demo-dev; Use integer tenths to avoid floating display error; fixed nonzero capacity avoids division by zero on an empty agenda.</td>
<td>With fixed capacity 600 compute free=600−occupied, used_slots=occupied/15, free_slots=free/15 and utilization to one decimal with that denominator.</td>
<td>Each slot contributes 2.5%, so percentage tenths=occupied×1000/600 is an exact integer. Empty is 0/600=0.0%, full is 600/600=100.0%, and 120 minutes gives 20.0%.</td>
<td><a href="TR3.md#d-ar-12">D-AR-12</a>; detailed design/implementation not formed, planned TR4</td>
<td>test / C-AR-12 / V-AR-12</td>
<td>Not run; demo-dev executes in TR4</td>
<td>Rerun related AR, parent SR and IR scenarios; 21 cases</td>
<td>mvp; defined; not approved</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## Changes, coverage and open items

This snapshot contains 12 AR rows, with no duplicate IDs, omitted rows or unfinished placeholders. Shared context or parents never merge identity, criteria or responsibilities. Twelve ARs cover six SRs; actual verification is not run. TR4 results are a separate AR-TR4.md snapshot.
