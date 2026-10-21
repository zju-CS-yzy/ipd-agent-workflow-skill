# Offline single-room booking: completed TR1–TR4 worked project

[中文](index.zh-CN.md) · [First-use walkthrough](walkthrough.md) · [Synthetic inputs](en/source-brief.md)

This project follows **3 IRs → 6 SRs → 12 ARs** through individual derivations, calculations/arguments, register consolidation, detailed design and actual software verification. Each overall document contains multiple derivations and each register multiple requirements, rather than one file per requirement.

Scope is one room and day, serial in-memory calls, 08:00–18:00, a 15-minute grid, half-open adjacency, cancellation, agenda and utilization. Inputs are author-created, not private data, interviews or real approval. [catalog@1](catalog.json) assigns educational IDs and is not a second canonical `.ipd/requirements.yaml`. No Claim, Gate, state revision or human approval is fabricated.

## Read by stage

| Stage | Completed overall document | Register snapshot | Work performed |
| --- | --- | --- | --- |
| TR1 | [Requirements and feasibility](en/TR1.md) / [中文](zh-CN/TR1.md) | [IR-TR1](en/IR-TR1.md) / [中文](zh-CN/IR-TR1.md) | Derive three IRs from U1/U2/U3; calculate 600 minutes/40 slots; no future SRs |
| TR2 | [Scenario analysis and allocation](en/TR2.md) / [中文](zh-CN/TR2.md) | [SR-TR2](en/SR-TR2.md) / [中文](zh-CN/SR-TR2.md) | Derive six SRs in chapter 3, consolidate in chapter 4; no ARs yet |
| TR3 | [High-level design and AR allocation](en/TR3.md) / [中文](zh-CN/TR3.md) | [AR-TR3](en/AR-TR3.md) / [中文](zh-CN/AR-TR3.md) | Derive twelve ARs in chapter 5 and consolidate in chapter 6; implementation/verification remain planned |
| TR4 | [Detailed design, implementation and test](en/TR4.md) / [中文](zh-CN/TR4.md) | [AR-TR4](en/AR-TR4.md) / [中文](zh-CN/AR-TR4.md) | Per-AR design and code mapping; execute twelve AR, six SR and three IR scenarios |

Start with `ir-02@1 → sr-03@1 → ar-05@1 / ar-06@1`: the user objective of adjacency without overlap leads to an interval formula, then a pure predicate and full active-set scan, then observed outputs. Follow `ir-03@1 → sr-06@1 → ar-11@1 / ar-12@1` to see why utilization depends on non-overlap.

## Independently checkable calculations

- Capacity: `(18−8)×60=600 min`, `600/15=40` slots. Positive disjoint bookings imply at most 40 active entries.
- Overlap: `[a,b)` and `[c,d)` are disjoint when `b≤c or d≤a`; negation gives `a<d and c<b`. Equal endpoints are permitted.
- Occupancy: 08:00–09:00 plus 09:30–10:30 gives 120 minutes, 480 free, 8 used/32 free slots and 20.0% utilization. The 150-minute span including a gap is not occupancy.
- Cancel the first entry to get 60/540 minutes, 4/36 slots and 10.0%. Empty/full days give 0.0%/100.0%. Each slot contributes exactly 2.5%, so integer percentage tenths require no rounding.

## Actual execution and limits

[booking.py](implementation/booking.py) uses the standard library. [verify_demo.py](implementation/verify_demo.py) executes 21 cases with independent expected values. [E1](evidence/verification.json) records expectations, observations, results, environment, execution time and source SHA-256. **21/21 software cases pass**. IR cases are automated scenario demonstrations; actual human acceptance and governance approval have not occurred.

Reproduce from the repository root without overwriting saved evidence:

```console
python docs/worked-projects/room-booking/implementation/verify_demo.py
python scripts/verify_room_booking_walkthrough.py --execute
```

The second command also checks sixteen template instances, bilingual relationships, derivation links, stage information boundaries, source digests and fresh-versus-saved case results. Structural lint does not grant human content acceptance. Template pins are in [document-instances.json](document-instances.json).
