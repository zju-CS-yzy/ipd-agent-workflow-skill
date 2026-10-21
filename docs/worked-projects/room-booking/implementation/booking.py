"""Synthetic offline, one-room, one-day booking core; standard library only."""

from dataclasses import dataclass
import re

OPEN = 8 * 60
CLOSE = 18 * 60
SLOT = 15
CAPACITY = CLOSE - OPEN


class BookingError(ValueError):
    pass


def parse_time(text: str) -> int:
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]{2}:[0-9]{2}", text):
        raise BookingError("INVALID_FORMAT")
    hour, minute = map(int, text.split(":"))
    if hour > 23 or minute > 59:
        raise BookingError("INVALID_TIME")
    return hour * 60 + minute


def validate_window(start: str, end: str) -> tuple[int, int]:
    first, last = parse_time(start), parse_time(end)
    if not OPEN <= first < last <= CLOSE:
        raise BookingError("INVALID_WINDOW")
    if (first - OPEN) % SLOT or (last - OPEN) % SLOT:
        raise BookingError("INVALID_GRID")
    return first, last


def overlaps(first: int, last: int, other_first: int, other_last: int) -> bool:
    """Positive half-open intervals overlap exactly when both inequalities hold."""
    return first < other_last and other_first < last


def format_time(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


@dataclass(frozen=True)
class Booking:
    id: str
    start: int
    end: int

    def record(self) -> dict:
        return {"id": self.id, "start": format_time(self.start),
                "end": format_time(self.end), "duration_min": self.end - self.start}


class Calendar:
    def __init__(self):
        self._active = {}
        self._next = 1

    def book(self, start: str, end: str) -> dict:
        first, last = validate_window(start, end)
        if any(overlaps(first, last, item.start, item.end) for item in self._active.values()):
            raise BookingError("CONFLICT")
        identifier = f"B{self._next:03d}"
        item = Booking(identifier, first, last)
        # All expected input/overlap rejections precede this in-memory update.
        self._active[identifier] = item
        self._next += 1
        return item.record()

    def cancel(self, identifier: str) -> dict:
        if not isinstance(identifier, str) or identifier not in self._active:
            raise BookingError("NOT_FOUND")
        del self._active[identifier]
        return {"id": identifier, "cancelled": True}

    def agenda(self) -> list[dict]:
        ordered = sorted(self._active.values(), key=lambda item: (item.start, item.end, item.id))
        return [item.record() for item in ordered]

    def occupied_minutes(self) -> int:
        return sum(item.end - item.start for item in self._active.values())

    def summary(self) -> dict:
        occupied = self.occupied_minutes()
        # Every duration is a multiple of 15: percentage tenths are exact integers.
        tenths = occupied * 1000 // CAPACITY
        return {"occupied_min": occupied, "free_min": CAPACITY - occupied,
                "used_slots": occupied // SLOT, "free_slots": (CAPACITY - occupied) // SLOT,
                "utilization_percent": f"{tenths // 10}.{tenths % 10}"}
