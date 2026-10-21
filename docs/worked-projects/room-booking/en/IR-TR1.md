---
instance_id: 'room-ir-tr1-en'
increment: 'mvp'
requirements: 'ir-01@1, ir-02@1, ir-03@1'
owner: 'demo-doc-owner'
document_type: 'ir_spec'
template_id: 'ipd-starter.ir_spec'
template_version: '1.1.1'
template_sha256: '17a731e3871d038bbf0fb7abe9b795aa32568694c1dd8a8dda137512aded0937'
locale: 'en'
scope: 'Synthetic standalone writing exercise; no governance acceptance'
---

# IR initial requirements register — Offline single-room booking


> Completed synthetic teaching register, document revision 1; snapshot at TR1. Educational identifiers do not establish governance acceptance or approval.

<!-- ipd-section:guidance -->
## Entry rules and baselines

Inputs are [BRIEF@1](source-brief.md), [educational catalog@1](../catalog.json), and [TR1 overall document](TR1.md). Metadata requirements exactly match all rows. The single Owner is demo-doc-owner, an educational role label, not an authenticated identity. Later revisions preserve this snapshot.

<!-- ipd-section:register -->
## Requirements register

<table data-ipd-table="requirements">
<thead>
<tr>
<th data-ipd-column="requirement">IR ID / version</th>
<th data-ipd-column="shared_context">Source and shared context</th>
<th data-ipd-column="scenario_scope">User scenarios and scope</th>
<th data-ipd-column="statement">Initial requirement statement</th>
<th data-ipd-column="value">User value and objective</th>
<th data-ipd-column="acceptance_intent">Acceptance intent and criterion IDs</th>
<th data-ipd-column="priority">Priority and rationale</th>
<th data-ipd-column="owner">Requirement owner</th>
<th data-ipd-column="increment">Committed increment and deferred scope</th>
<th data-ipd-column="decomposition">Exact SR versions and decomposition status</th>
<th data-ipd-column="open_questions">Constraints, risks and open questions</th>
</tr>
</thead>
<tbody>
<tr>
<td>ir-01@1</td>
<td rowspan="3">BRIEF@1/U1–U3; one room/day</td>
<td rowspan="3">SC-1/SC-2/SC-3; 08:00–18:00, 15 min</td>
<td>Within the operating day, a user can create a booking on a 15-minute grid and receive confirmation; invalid inputs are explicitly rejected.</td>
<td>BRIEF@1/U1 requests booking with a clear outcome. C1/C2 bound it to one room, 08:00–18:00 and a 15-minute grid. Consolidate the need into acceptance of valid input and explicit rejection of invalid input.</td>
<td>C-IR-01；Within the operating day, a user can create a booking on a 15-minute grid and receive confirmation; invalid inputs are explicitly rejected.</td>
<td>High; MVP necessary</td>
<td>demo-systems</td>
<td>mvp; No multi-room/cross-day</td>
<td>Not yet decomposed; demo-systems plans TR2; <a href="TR1.md#d-ir-01">D-IR-01</a></td>
<td>Use a command/API demonstration rather than a GUI; promise neither interaction latency nor persistence.</td>
</tr>
<tr>
<td>ir-02@1</td>
<td>Active bookings must not overlap, adjacent bookings are allowed, and a cancelled slot can immediately be booked again.</td>
<td>BRIEF@1/U2 concerns contention and availability after cancellation. C3 permits touching boundaries and C4 limits calls to serial execution in one process, yielding conflict control and cancellation/release objectives.</td>
<td>C-IR-02；Active bookings must not overlap, adjacent bookings are allowed, and a cancelled slot can immediately be booked again.</td>
<td>High; MVP necessary</td>
<td>demo-systems</td>
<td>mvp; No multi-room/cross-day</td>
<td>Not yet decomposed; demo-systems plans TR2; <a href="TR1.md#d-ir-02">D-IR-02</a></td>
<td>Do not extend this to concurrent locking or authentication; adjacency semantics are an explicit input, not a code assumption.</td>
</tr>
<tr>
<td>ir-03@1</td>
<td>The user can view active bookings in time order and see occupied/free minutes, slot counts and daily utilization.</td>
<td>BRIEF@1/U3 supports planning later meetings. C1 fixes capacity. The agenda and utilization answer when the room is free and how much is used; a percentage alone is insufficient.</td>
<td>C-IR-03；The user can view active bookings in time order and see occupied/free minutes, slot counts and daily utilization.</td>
<td>High; MVP necessary</td>
<td>demo-systems</td>
<td>mvp; No multi-room/cross-day</td>
<td>Not yet decomposed; demo-systems plans TR2; <a href="TR1.md#d-ir-03">D-IR-03</a></td>
<td>Summarize one day in the current process only; exclude cross-day analytics and personal data.</td>
</tr>
</tbody>
</table>

<!-- ipd-section:coverage -->
## Changes, coverage and open items

This snapshot contains 3 IR rows, with no duplicate IDs, omitted rows or unfinished placeholders. Shared context or parents never merge identity, criteria or responsibilities. TR1 has no SRs yet; do not backfill future versions into this snapshot. See TR2 chapter 3 for later decomposition.
