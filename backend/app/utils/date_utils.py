from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Generator

import pytz

from app.models.appointment import TimeRange, TimeSlot


def parse_work_time(hhmm: str, tz: pytz.BaseTzInfo, on_date: date) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    naive = datetime.combine(on_date, time(h, m))
    return tz.localize(naive)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return pytz.utc.localize(dt)
    return dt.astimezone(pytz.utc)


def format_slot_label(start_utc: datetime, end_utc: datetime, tz_name: str) -> str:
    tz = pytz.timezone(tz_name)
    start_local = start_utc.astimezone(tz)
    end_local = end_utc.astimezone(tz)
    day_str = start_local.strftime("%A, %b %-d")
    time_str = f"{start_local.strftime('%-I:%M %p')} – {end_local.strftime('%-I:%M %p')}"
    abbr = start_local.strftime("%Z")
    return f"{day_str} · {time_str} {abbr}"


def generate_candidate_slots(
    on_date: date,
    duration_minutes: int,
    work_start: str,
    work_end: str,
    tz_name: str,
    granularity_minutes: int = 30,
) -> Generator[TimeSlot, None, None]:
    """Yield candidate slots of `duration_minutes` length within working hours."""
    tz = pytz.timezone(tz_name)
    current = parse_work_time(work_start, tz, on_date)
    end_of_day = parse_work_time(work_end, tz, on_date)
    delta = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=granularity_minutes)

    while current + delta <= end_of_day:
        start_utc = to_utc(current)
        end_utc = to_utc(current + delta)
        label = format_slot_label(start_utc, end_utc, tz_name)
        yield TimeSlot(start=start_utc, end=end_utc, display_label=label)
        current += step


def filter_available_slots(
    candidates: list[TimeSlot],
    busy_times: list[TimeRange],
    not_before: datetime | None = None,
) -> list[TimeSlot]:
    """Return slots that are free and start strictly after `not_before` (defaults to now)."""
    cutoff = not_before if not_before is not None else datetime.now(tz=pytz.utc)
    return [
        slot for slot in candidates
        if slot.start > cutoff
        and not any(slot.overlaps(busy) for busy in busy_times)
    ]
