"""Reproduce independent expected/actual evidence for the synthetic worked project.

Prints JSON by default; --output writes only to the explicitly chosen file.
No real user acceptance, approval, repository writes or IPD Gate transitions.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path

from booking import Calendar, BookingError, overlaps, parse_time, validate_window


def error(call):
    try:
        call()
    except BookingError as exc:
        return str(exc)
    return "NO_ERROR"


def two_bookings():
    calendar = Calendar()
    calendar.book("08:00", "09:00")
    calendar.book("09:30", "10:30")
    return calendar


def record(identifier, start, end, duration):
    return {"id": identifier, "start": start, "end": end, "duration_min": duration}


def cases():
    def ar01():
        return [parse_time("08:00"), parse_time("09:15"), parse_time("18:00"),
                error(lambda: parse_time("9:00")), error(lambda: parse_time("09:75"))]

    def ar02():
        return [list(validate_window("17:45", "18:00")),
                error(lambda: validate_window("07:45", "08:15")),
                error(lambda: validate_window("09:00", "09:00")),
                error(lambda: validate_window("09:20", "10:00")),
                error(lambda: validate_window("17:45", "18:15"))]

    def ar03():
        calendar = two_bookings()
        return [item["id"] for item in calendar.agenda()]

    def ar04():
        calendar = Calendar()
        confirmation = calendar.book("08:00", "09:00")
        return {"confirmation": confirmation, "agenda": calendar.agenda()}

    def ar05():
        return [overlaps(480, 540, 540, 555), overlaps(480, 540, 525, 555),
                overlaps(480, 540, 480, 540), overlaps(480, 540, 495, 525),
                overlaps(480, 540, 465, 555), overlaps(480, 540, 465, 480)]

    def ar06():
        calendar = Calendar()
        calendar.book("08:00", "09:00")
        before = calendar.agenda()
        rejected = error(lambda: calendar.book("08:45", "09:15"))
        unchanged = before == calendar.agenda()
        next_id = calendar.book("09:30", "10:30")["id"]
        return [rejected, unchanged, next_id]

    def ar07():
        calendar = Calendar()
        calendar.book("08:00", "09:00")
        result = calendar.cancel("B001")
        return [result, calendar.agenda(), error(lambda: calendar.cancel("missing")), calendar.agenda()]

    def ar08():
        calendar = Calendar()
        calendar.book("08:00", "09:00")
        calendar.cancel("B001")
        current = calendar.book("08:00", "09:00")
        again = error(lambda: calendar.cancel("B001"))
        return [current["id"], again, [item["id"] for item in calendar.agenda()]]

    def ar09():
        calendar = Calendar()
        calendar.book("09:30", "10:30")
        calendar.book("08:00", "09:00")
        return [item["id"] for item in calendar.agenda()]

    def ar10():
        calendar = Calendar()
        reply = calendar.book("08:00", "09:00")
        reply["start"] = "00:00"
        view = calendar.agenda()
        view[0]["start"] = "01:00"
        view.append({"id": "ghost"})
        return calendar.agenda()

    def ar11():
        return two_bookings().occupied_minutes()

    def ar12():
        empty = Calendar().summary()
        calendar = Calendar()
        calendar.book("08:00", "18:00")
        return [empty, calendar.summary()]

    def sr01():
        calendar = Calendar()
        invalid = error(lambda: calendar.book("09:20", "10:00"))
        valid = calendar.book("17:45", "18:00")
        return [invalid, valid]

    def sr02():
        return ar04()  # Executes a fresh system flow; never reuses an AR pass flag.

    def sr03():
        calendar = Calendar()
        calendar.book("08:00", "09:00")
        calendar.book("09:00", "09:30")
        rejection = error(lambda: calendar.book("08:45", "09:15"))
        return [rejection, calendar.agenda()]

    def sr04():
        return ar08()

    def sr05():
        calendar = Calendar()
        calendar.book("09:30", "10:30")
        calendar.book("08:00", "09:00")
        view = calendar.agenda()
        view[0]["end"] = "18:00"
        return calendar.agenda()

    def sr06():
        calendar = two_bookings()
        before = calendar.summary()
        calendar.cancel("B001")
        return [before, calendar.summary()]

    def ir01():
        calendar = Calendar()
        confirmed = calendar.book("08:00", "09:00")
        rejected = error(lambda: calendar.book("09:20", "10:00"))
        return [confirmed, rejected, calendar.agenda()]

    def ir02():
        calendar = Calendar()
        calendar.book("08:00", "09:00")
        adjacent = calendar.book("09:00", "09:30")
        rejected = error(lambda: calendar.book("08:45", "09:15"))
        cancelled = calendar.cancel("B001")
        reused = calendar.book("08:00", "09:00")
        return [adjacent["id"], rejected, cancelled, reused["id"], len(calendar.agenda())]

    def ir03():
        calendar = Calendar()
        calendar.book("09:30", "10:30")
        calendar.book("08:00", "09:00")
        return {"agenda": calendar.agenda(), "summary": calendar.summary()}

    first = record("B001", "08:00", "09:00", 60)
    normal = {"confirmation": first, "agenda": [first]}
    empty = {"occupied_min": 0, "free_min": 600, "used_slots": 0, "free_slots": 40, "utilization_percent": "0.0"}
    full = {"occupied_min": 600, "free_min": 0, "used_slots": 40, "free_slots": 0, "utilization_percent": "100.0"}
    middle = {"occupied_min": 120, "free_min": 480, "used_slots": 8, "free_slots": 32, "utilization_percent": "20.0"}
    after = {"occupied_min": 60, "free_min": 540, "used_slots": 4, "free_slots": 36, "utilization_percent": "10.0"}
    ordered = [record("B002", "08:00", "09:00", 60), record("B001", "09:30", "10:30", 60)]
    return [
        ("ar-01", ar01, [480, 555, 1080, "INVALID_FORMAT", "INVALID_TIME"]),
        ("ar-02", ar02, [[1065, 1080], "INVALID_WINDOW", "INVALID_WINDOW", "INVALID_GRID", "INVALID_WINDOW"]),
        ("ar-03", ar03, ["B001", "B002"]), ("ar-04", ar04, normal),
        ("ar-05", ar05, [False, True, True, True, True, False]),
        ("ar-06", ar06, ["CONFLICT", True, "B002"]),
        ("ar-07", ar07, [{"id": "B001", "cancelled": True}, [], "NOT_FOUND", []]),
        ("ar-08", ar08, ["B002", "NOT_FOUND", ["B002"]]),
        ("ar-09", ar09, ["B002", "B001"]), ("ar-10", ar10, [first]),
        ("ar-11", ar11, 120), ("ar-12", ar12, [empty, full]),
        ("sr-01", sr01, ["INVALID_GRID", record("B001", "17:45", "18:00", 15)]),
        ("sr-02", sr02, normal),
        ("sr-03", sr03, ["CONFLICT", [first, record("B002", "09:00", "09:30", 30)]]),
        ("sr-04", sr04, ["B002", "NOT_FOUND", ["B002"]]),
        ("sr-05", sr05, ordered), ("sr-06", sr06, [middle, after]),
        ("ir-01", ir01, [first, "INVALID_GRID", [first]]),
        ("ir-02", ir02, ["B002", "CONFLICT", {"id": "B001", "cancelled": True}, "B003", 2]),
        ("ir-03", ir03, {"agenda": ordered, "summary": middle}),
    ]


def run():
    rows = []
    for identifier, scenario, expected in cases():
        try:
            actual = scenario()
            result = "passed" if actual == expected else "failed"
        except Exception as exc:
            actual, result = {"exception": type(exc).__name__, "message": str(exc)}, "failed"
        rows.append({"id": "V-" + identifier.upper(), "requirement": identifier + "@1",
                     "level": identifier[:2].upper(), "criterion": "C-" + identifier.upper(),
                     "expected": expected, "actual": actual, "result": result})
    source = Path(__file__).resolve().parent
    return {"schema": "worked-project-evidence/1", "kind": "synthetic-software-execution",
            "exercise_date": "2026-10-20", "executed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "environment": {"python": platform.python_version(), "os": platform.system()},
            "source_sha256": {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                              for name in ("booking.py", "verify_demo.py")},
            "human_acceptance": "not_performed", "governance_approval": "not_granted",
            "cases": rows, "passed": sum(row["result"] == "passed" for row in rows), "total": len(rows)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence = run()
    content = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"{evidence['passed']}/{evidence['total']} passed; wrote {args.output}")
    else:
        print(content, end="")
    raise SystemExit(evidence["passed"] != evidence["total"])
