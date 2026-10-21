# BRIEF@1: synthetic inputs for offline single-room booking

The author constructed these inputs for teaching; they are not interviews, client authorization or approval records. They exercise requirement development without production data.

<a id="u1"></a>
## U1: create and confirm

“I want to book one room on a fixed time grid and know whether it succeeded; invalid input must not silently create a booking.”

<a id="u2"></a>
## U2: conflicts and cancellation

“Meetings must not contend for the same time. The next can start when the previous ends. A cancelled slot should be reusable and an old cancellation must not delete a new booking.”

<a id="u3"></a>
## U3: agenda and utilization

“I need active bookings in time order and occupied/free minutes, slot counts and daily utilization.”

## Explicit scope and assumptions

- C1: one room, one day, 08:00–18:00, fixed capacity 600 minutes.
- C2: strict HH:MM, a 15-minute grid and positive duration; confirmations contain ID, normalized times and duration.
- C3: half-open intervals permit touching endpoints. Cancellation removes active entries; process-local IDs are never reused.
- C4: one process, serial calls, in-memory state. Exclude concurrency, multiple rooms, cross-day state, persistence, authentication and GUI.
- C5: return agenda copies and show percentage to one decimal. No latency or byte-memory budget is promised.
- C6: roles are educational labels. No actual human acceptance or governance approval occurs. catalog@1 registers IDs for this exercise; real Skill projects still require canonical registration and acceptance.

Requirement content versions are all @1. Each stage document is doc rev 1 of its distinct snapshot. A final teaching bundle containing TR4 does not make its passing results available at TR1.
