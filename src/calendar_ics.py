from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from .scheduler import TraySwitch


def _format_ics_date(d: date) -> str:
    # All-day event
    return d.strftime("%Y%m%d")


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def write_ics(
    schedule: Iterable[TraySwitch],
    out_path: str | Path,
    calendar_name: str = "Invisalign Tray Schedule",
    event_prefix: str = "Tray",
    description: Optional[str] = None,
) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    # Use a stable-ish DTSTAMP
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//invisalign-scheduler//EN")
    lines.append(f"X-WR-CALNAME:{_escape(calendar_name)}")

    for ts in schedule:
        start = ts.switch_on
        end = start + timedelta(days=1)  # all-day events use end-exclusive

        summary = f"{event_prefix} {ts.tray:02d} — switch aligner"
        desc = description or "Reminder to switch to the next tray. Follow your orthodontist’s instructions."

        uid = f"invisalign-scheduler-tray-{ts.tray:02d}-{start.isoformat()}"

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{_escape(uid)}")
        lines.append(f"DTSTAMP:{dtstamp}")
        lines.append(f"SUMMARY:{_escape(summary)}")
        lines.append(f"DESCRIPTION:{_escape(desc)}")
        lines.append(f"DTSTART;VALUE=DATE:{_format_ics_date(start)}")
        lines.append(f"DTEND;VALUE=DATE:{_format_ics_date(end)}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p
