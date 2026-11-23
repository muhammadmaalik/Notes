"""Tiny due-date parser: ISO dates, 'today', 'tomorrow', '+3d', weekday names."""

from __future__ import annotations

from datetime import datetime, timedelta

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_due(text: str, now: datetime | None = None) -> str:
    """Return 'YYYY-MM-DD HH:MM'. Default time is 23:59 when none is given."""
    now = now or datetime.now()
    s = text.strip().lower()
    time_part = "23:59"
    if " " in s and ":" in s.split()[-1]:
        s, time_part = s.rsplit(" ", 1)
    datetime.strptime(time_part, "%H:%M")  # validates

    if s == "today":
        d = now.date()
    elif s == "tomorrow":
        d = (now + timedelta(days=1)).date()
    elif s.startswith("+") and s.endswith("d") and s[1:-1].isdigit():
        d = (now + timedelta(days=int(s[1:-1]))).date()
    elif s in WEEKDAYS:
        ahead = (WEEKDAYS.index(s) - now.weekday()) % 7 or 7
        d = (now + timedelta(days=ahead)).date()
    else:
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(f"Can't read due date '{text}'. Use YYYY-MM-DD [HH:MM], today, tomorrow, +3d, or a weekday.") from e
    return f"{d.isoformat()} {time_part}"
