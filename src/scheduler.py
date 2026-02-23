from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Set, Tuple


@dataclass(frozen=True)
class TraySwitch:
    tray: int
    start: date
    switch_on: date  # the day you move to next tray (or to tray N if tray-1)


@dataclass(frozen=True)
class PlanInput:
    start_date: date
    n_trays: int
    estimated_ortho_date: date
    default_days_per_tray: int = 14
    avoid_dates: Set[date] = None  # dates to avoid switching trays
    buffer_days_before_ortho: int = 4  # target: tray N starts ~ buffer days before appt


@dataclass(frozen=True)
class Plan:
    inputs: PlanInput
    schedule: List[TraySwitch]


def _validate_inputs(inp: PlanInput) -> None:
    if inp.n_trays <= 0:
        raise ValueError("Number of trays must be positive.")
    if inp.default_days_per_tray <= 0:
        raise ValueError("Default days per tray must be positive.")
    if inp.estimated_ortho_date <= inp.start_date:
        raise ValueError("Estimated orthodontist date must be after the start date.")
    if inp.buffer_days_before_ortho < 0:
        raise ValueError("Buffer days must be non-negative.")


def _deadline_for_final_tray_start(inp: PlanInput) -> date:
    # We target the *start* of the final tray around (ortho_date - buffer_days).
    return inp.estimated_ortho_date - timedelta(days=inp.buffer_days_before_ortho)


def _compute_durations_to_hit_deadline(
    n_trays: int,
    start_date: date,
    deadline_final_tray_start: date,
    default_days: int,
) -> List[int]:
    """
    AUTO-FIT MODE:
    Fit trays 1..(N-1) into the available window so that tray N starts by deadline_final_tray_start.

    We compute:
      available_days = (deadline_final_tray_start - start_date).days
      intervals = N-1

    Then distribute available_days across intervals as evenly as possible:
      base = available_days // intervals
      remainder = available_days % intervals

    durations for trays 1..(N-1):
      [base+1] for 'remainder' trays, then [base] for the rest

    Tray N duration uses default_days (doesn't affect tray N start target).
    We also clamp durations into a reasonable range; if clamping makes an exact fit impossible,
    we still return a best-effort schedule.
    """
    if n_trays == 1:
        return [default_days]

    intervals = n_trays - 1
    available_days = (deadline_final_tray_start - start_date).days

    # If deadline is too close / invalid, fall back to default durations
    if available_days <= 0:
        return [default_days] * n_trays

    # Evenly distribute the available days across N-1 intervals
    base = available_days // intervals
    rem = available_days % intervals

    durations = []
    for i in range(intervals):
        d = base + (1 if i < rem else 0)
        durations.append(d)

    # Reasonable bounds (tunable). We try to keep within these.
    MIN_DAYS, MAX_DAYS = 7, 21

    # Clamp with best-effort correction to preserve total where possible
    total_target = sum(durations)
    durations = [max(MIN_DAYS, min(MAX_DAYS, d)) for d in durations]

    # Try to correct total back toward target within bounds
    def can_inc(i): return durations[i] < MAX_DAYS
    def can_dec(i): return durations[i] > MIN_DAYS

    diff = total_target - sum(durations)  # positive means we need to add days back; negative means remove
    # Add days back
    while diff > 0:
        changed = False
        for i in range(len(durations)):
            if can_inc(i):
                durations[i] += 1
                diff -= 1
                changed = True
                if diff == 0:
                    break
        if not changed:
            break

    # Remove extra days
    while diff < 0:
        changed = False
        for i in range(len(durations)):
            if can_dec(i):
                durations[i] -= 1
                diff += 1
                changed = True
                if diff == 0:
                    break
        if not changed:
            break

    # Tray N duration doesn't affect tray N start target
    durations.append(default_days)

    return durations


def _shift_off_avoid_dates(
    d: date,
    avoid: Set[date],
    search_window_days: int = 3,
) -> date:
    """
    If d is in avoid set, shift to the nearest acceptable date within +/- search_window_days.
    Preference: shift forward (pain-days often precede events), then backward.
    """
    if not avoid or d not in avoid:
        return d

    for k in range(1, search_window_days + 1):
        forward = d + timedelta(days=k)
        if forward not in avoid:
            return forward
    for k in range(1, search_window_days + 1):
        backward = d - timedelta(days=k)
        if backward not in avoid:
            return backward

    # If everything is blocked, return original
    return d


def build_plan(inp: PlanInput) -> Plan:
    """
    Build a schedule with:
    - Mostly default durations
    - Adjustments so tray N starts ~ (ortho_date - buffer)
    - Switch dates shifted off avoid-days
    """
    if inp.avoid_dates is None:
        object.__setattr__(inp, "avoid_dates", set())  # not typical; we'll handle below
    avoid = inp.avoid_dates or set()

    _validate_inputs(inp)

    deadline = _deadline_for_final_tray_start(inp)

    durations = _compute_durations_to_hit_deadline(
        n_trays=inp.n_trays,
        start_date=inp.start_date,
        deadline_final_tray_start=deadline,
        default_days=inp.default_days_per_tray,
    )

    schedule: List[TraySwitch] = []
    cur = inp.start_date

    for tray in range(1, inp.n_trays + 1):
        switch_on = cur + timedelta(days=int(durations[tray - 1]))

        # We only create "switch" events for trays 1..N-1 (switching into next tray),
        # but it's still useful to show the end date for tray N as well.
        switch_on = _shift_off_avoid_dates(switch_on, avoid)

        schedule.append(TraySwitch(tray=tray, start=cur, switch_on=switch_on))
        cur = switch_on

    return Plan(inputs=PlanInput(
        start_date=inp.start_date,
        n_trays=inp.n_trays,
        estimated_ortho_date=inp.estimated_ortho_date,
        default_days_per_tray=inp.default_days_per_tray,
        avoid_dates=avoid,
        buffer_days_before_ortho=inp.buffer_days_before_ortho,
    ), schedule=schedule)


def reschedule_from(
    existing: Plan,
    current_tray: int,
    actual_switch_date: date,
    new_estimated_ortho_date: Optional[date] = None,
    additional_avoid_dates: Optional[Set[date]] = None,
) -> Plan:
    """
    Reschedule forward without re-entering everything.

    - current_tray: tray they are currently wearing (1-indexed)
    - actual_switch_date: the date they actually switched INTO current_tray
    """
    if current_tray < 1 or current_tray > existing.inputs.n_trays:
        raise ValueError("current_tray must be within [1, n_trays].")

    # Remaining trays include current_tray..N
    remaining = existing.inputs.n_trays - current_tray + 1
    if remaining <= 0:
        raise ValueError("No trays remaining to schedule.")

    avoid = set(existing.inputs.avoid_dates or set())
    if additional_avoid_dates:
        avoid |= set(additional_avoid_dates)

    inp = PlanInput(
        start_date=actual_switch_date,
        n_trays=remaining,
        estimated_ortho_date=new_estimated_ortho_date or existing.inputs.estimated_ortho_date,
        default_days_per_tray=existing.inputs.default_days_per_tray,
        avoid_dates=avoid,
        buffer_days_before_ortho=existing.inputs.buffer_days_before_ortho,
    )
    new_plan = build_plan(inp)

    # Re-label tray numbers to match original numbering
    relabeled = []
    for i, ts in enumerate(new_plan.schedule):
        relabeled.append(TraySwitch(
            tray=current_tray + i,
            start=ts.start,
            switch_on=ts.switch_on,
        ))

    return Plan(
        inputs=PlanInput(
            start_date=existing.inputs.start_date,
            n_trays=existing.inputs.n_trays,
            estimated_ortho_date=inp.estimated_ortho_date,
            default_days_per_tray=inp.default_days_per_tray,
            avoid_dates=avoid,
            buffer_days_before_ortho=inp.buffer_days_before_ortho,
        ),
        schedule=_merge_past_and_future(existing.schedule, relabeled, current_tray),
    )


def _merge_past_and_future(old: List[TraySwitch], new_future: List[TraySwitch], current_tray: int) -> List[TraySwitch]:
    """
    Keep old history for trays < current_tray, replace trays >= current_tray.
    """
    past = [ts for ts in old if ts.tray < current_tray]
    return past + new_future
