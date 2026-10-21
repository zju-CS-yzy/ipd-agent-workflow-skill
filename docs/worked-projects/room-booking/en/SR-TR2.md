---
instance_id: 'room-sr-tr2-en'
increment: 'mvp'
requirements: 'sr-01@1, sr-02@1, sr-03@1, sr-04@1, sr-05@1, sr-06@1'
owner: 'demo-doc-owner'
document_type: 'sr_spec'
template_id: 'ipd-starter.sr_spec'
template_version: '1.1.1'
template_sha256: 'e15323dde50b98e7f7dedafdf2e69b60762eb7712a915529734635f3c110e3f4'
locale: 'en'
scope: 'Synthetic standalone writing exercise; no governance acceptance'
---

# SR system requirements register — Offline single-room booking


> Completed synthetic teaching register, document revision 1; snapshot at TR2. Educational identifiers do not establish governance acceptance or approval.

<!-- ipd-section:guidance -->
## Entry rules and baselines

Inputs are [BRIEF@1](source-brief.md), [educational catalog@1](../catalog.json), and [TR2 overall document](TR2.md). Metadata requirements exactly match all rows. The single Owner is demo-doc-owner, an educational role label, not an authenticated identity. Later revisions preserve this snapshot.

<!-- ipd-section:register -->
## Requirements register

<table data-ipd-table="requirements">
<thead>
<tr>
<th data-ipd-column="requirement">SR ID / version</th>
<th data-ipd-column="parent">Exact parent IR version</th>
<th data-ipd-column="scenario_scope">Scenarios, triggers and exceptions</th>
<th data-ipd-column="system_behavior">System behavior and outputs</th>
<th data-ipd-column="measures_limits">Measures and boundary conditions</th>
<th data-ipd-column="interfaces_constraints">Interfaces, constraints and quality requirements</th>
<th data-ipd-column="module_allocation">Module allocation and collaboration</th>
<th data-ipd-column="verification">System verification methods and criteria</th>
<th data-ipd-column="priority_owner">Priority, rationale and owner</th>
<th data-ipd-column="increment_status">Increment, maturity and deferred scope</th>
<th data-ipd-column="child_ar">Exact AR versions and allocation gaps</th>
</tr>
</thead>
<tbody>
<tr>
<td>sr-01@1</td>
<td rowspan="2">ir-01@1</td>
<td>SC-1; <a href="TR2.md#d-sr-01">D-SR-01</a></td>
<td>Accept only HH:MM clock values satisfying 08:00≤start&lt;end≤18:00 with both endpoints on the 15-minute grid.</td>
<td>Convert SC-1 input to minutes m=60h+min. Capacity=(18−8)×60=600 minutes=600/15=40 slots. Endpoints are 480+15k for k=0…40, with start&lt;end. Check format, clock validity and business window separately.</td>
<td>Use integer minutes to avoid floating boundaries; 09:20 is a valid clock value but not on the grid.</td>
<td>validation</td>
<td>test / C-SR-01 / V-SR-01</td>
<td>high / demo-systems</td>
<td>mvp; defined; execution awaits TR4</td>
<td>AR not formed; demo-dev allocates in TR3</td>
</tr>
<tr>
<td>sr-02@1</td>
<td>SC-1; <a href="TR2.md#d-sr-02">D-SR-02</a></td>
<td>A valid conflict-free request creates one active booking and returns a non-reused process-local ID, times and duration; rejection changes neither active state nor the next ID.</td>
<td>The user must associate confirmation with later cancellation, so return a stable ID and window rather than a bare success flag. Validate before mutation so rejected paths leave no booking or consumed ID.</td>
<td>A monotonic counter guarantees process-local uniqueness only, not uniqueness across restarts or durable transactions.</td>
<td>ledger</td>
<td>test / C-SR-02 / V-SR-02</td>
<td>high / demo-systems</td>
<td>mvp; defined; execution awaits TR4</td>
<td>AR not formed; demo-dev allocates in TR3</td>
</tr>
<tr>
<td>sr-03@1</td>
<td rowspan="2">ir-02@1</td>
<td>SC-2; <a href="TR2.md#d-sr-03">D-SR-03</a></td>
<td>Use half-open intervals [start,end): touching endpoints are allowed; reject any positive overlap without changing the active list.</td>
<td>Disjoint intervals satisfy b≤c or d≤a; negation gives a&lt;d and c&lt;b. Strict inequalities permit [08:00,09:00) next to [09:00,09:30), while containment and identical intervals still conflict.</td>
<td>Scan active bookings in O(n); at most 40 positive-length bookings fit, so an interval tree is unnecessary.</td>
<td>ledger</td>
<td>test / C-SR-03 / V-SR-03</td>
<td>high / demo-systems</td>
<td>mvp; defined; execution awaits TR4</td>
<td>AR not formed; demo-dev allocates in TR3</td>
</tr>
<tr>
<td>sr-04@1</td>
<td>SC-2; <a href="TR2.md#d-sr-04">D-SR-04</a></td>
<td>Cancelling an existing ID removes its active booking and releases the slot; unknown or repeated cancellation returns NOT_FOUND without affecting others, and old IDs are not reused.</td>
<td>Release means removing the entry from conflict scanning; immediately rebooking its exact window must succeed. Reusing IDs could make a delayed repeat cancel delete a new booking, so the counter stays monotonic after cancellation.</td>
<td>Report unknown cancellation explicitly rather than claiming it was cancelled again; no distributed idempotency protocol is introduced.</td>
<td>ledger</td>
<td>test / C-SR-04 / V-SR-04</td>
<td>high / demo-systems</td>
<td>mvp; defined; execution awaits TR4</td>
<td>AR not formed; demo-dev allocates in TR3</td>
</tr>
<tr>
<td>sr-05@1</td>
<td rowspan="2">ir-03@1</td>
<td>SC-3; <a href="TR2.md#d-sr-05">D-SR-05</a></td>
<td>List only active bookings sorted by start minute, end minute and ID, with normalized HH:MM and duration; mutating returned data must not alter system state.</td>
<td>SC-3 may book a later meeting first, so creation order is not agenda order. Render from the active set and return fresh dictionaries so viewing remains read-only.</td>
<td>Declare deterministic ordering. Equal starts cannot coexist in this non-overlapping single room, but secondary keys keep formatting deterministic.</td>
<td>presentation</td>
<td>test / C-SR-05 / V-SR-05</td>
<td>high / demo-systems</td>
<td>mvp; defined; execution awaits TR4</td>
<td>AR not formed; demo-dev allocates in TR3</td>
</tr>
<tr>
<td>sr-06@1</td>
<td>SC-3; <a href="TR2.md#d-sr-06">D-SR-06</a></td>
<td>Use a fixed 600-minute denominator to compute occupied/free minutes, 15-minute slots and utilization to one decimal; recompute after cancellation.</td>
<td>SR-03 guarantees disjoint active intervals, so union length=Σ(end−start). 08:00–09:00 plus 09:30–10:30 gives 60+60=120 occupied minutes, 480 free, 8 used slots, 32 free slots and 120/600×100=20.0% utilization.</td>
<td>Each slot is 15/600×100=2.5%, exactly representable to one decimal; never use the first-to-last booking span as denominator.; SR-06 shares SR-03 non-overlap</td>
<td>metrics</td>
<td>test / C-SR-06 / V-SR-06</td>
<td>high / demo-systems</td>
<td>mvp; defined; execution awaits TR4</td>
<td>AR not formed; demo-dev allocates in TR3</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## Changes, coverage and open items

This snapshot contains 6 SR rows, with no duplicate IDs, omitted rows or unfinished placeholders. Shared context or parents never merge identity, criteria or responsibilities. Six SRs cover three IRs. ARs do not yet exist here; later allocation is in TR3 chapter 5.
