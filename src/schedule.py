from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

@dataclass(frozen=True)
class TraySwitch:
    tray: int
    start: date
    switch_on: date

def build_schedule(
    n_trays: int,
    start_date: date,
    days_per_tray: int = 14,
    tray_durations: Optional[List[int]] = None,
) -> List[TraySwitch]:
    if n_trays <= 0:
        raise ValueError("n_trays must be positive.")
    if days_per_tray <= 0:
        raise ValueError("days_per_tray must be positive.")
    if tray_durations is not None and len(tray_durations) != n_trays:
        raise ValueError("tray_durations must have length n_trays.")

    durations = tray_durations if tray_durations is not None else [days_per_tray] * n_trays
    out: List[TraySwitch] = []

    cur = start_date
    for i, d in enumerate(durations, start=1):
        switch_on = cur + timedelta(days=int(d))
        out.append(TraySwitch(tray=i, start=cur, switch_on=switch_on))
        cur = switch_on
    return out
