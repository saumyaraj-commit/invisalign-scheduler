from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Optional, Set

from .calendar_ics import write_ics
from .scheduler import PlanInput, build_plan, reschedule_from
from .storage import load_plan, save_plan


PLAN_PATH = Path("plan.json")
OUT_DIR = Path("output")
ICS_PATH = OUT_DIR / "tray_schedule.ics"
CSV_PATH = OUT_DIR / "tray_schedule.csv"


WELCOME = """Welcome to Invisalign Scheduler.

Transparency:
- This tool is not medical advice.
- It uses your estimated next orthodontist appointment date as a checkpoint and tries to start your final tray ~4 days before that date.
  Rationale: many people wear their last tray while waiting for the next set/refinements, so the buffer helps avoid awkward timing.
- If your orthodontist’s instructions differ, follow them.

If you miss a scheduled switch:
- Switch when you can, then re-run this tool and choose “reschedule”.
- You’ll only need to confirm your current tray and the most recent actual switch date; the tool will rebuild the rest (make sure you are running code from same directory).
"""


def _prompt_date(msg: str) -> date:
    while True:
        s = input(f"{msg} (YYYY-MM-DD): ").strip()
        try:
            return date.fromisoformat(s)
        except ValueError:
            print("Please use YYYY-MM-DD, e.g., 2026-02-22.")


def _prompt_int(msg: str, min_value: int = 1, default: Optional[int] = None) -> int:
    while True:
        suffix = f" [default {default}]" if default is not None else ""
        s = input(f"{msg}{suffix}: ").strip()
        if s == "" and default is not None:
            return default
        try:
            v = int(s)
            if v < min_value:
                print(f"Please enter an integer ≥ {min_value}.")
                continue
            return v
        except ValueError:
            print("Please enter an integer.")


def _prompt_avoid_dates() -> Set[date]:
    print("\nOptional: enter dates you want to avoid switching trays (painful/important days).")
    print("Enter as YYYY-MM-DD separated by commas, or press Enter to skip.")
    s = input("Avoid dates: ").strip()
    if not s:
        return set()
    out = set()
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(date.fromisoformat(part))
        except ValueError:
            print(f"Skipping invalid date: {part}")
    return out


def _write_csv(schedule, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tray", "start_date", "switch_on"])
        for ts in schedule:
            w.writerow([ts.tray, ts.start.isoformat(), ts.switch_on.isoformat()])


def _print_schedule(schedule) -> None:
    print("\nGenerated schedule:")
    for ts in schedule:
        print(f"Tray {ts.tray:02d}: start {ts.start.isoformat()}  -> switch on {ts.switch_on.isoformat()}")


def main() -> None:
    print(WELCOME)

    existing = load_plan(PLAN_PATH)

    if existing:
        print(f"Found an existing plan at {PLAN_PATH}.")
        choice = input("Type 'n' for new plan, or 'r' to reschedule after a missed/changed date [r]: ").strip().lower()
        if choice == "n":
            existing = None
        else:
            # Reschedule flow
            current_tray = _prompt_int("What tray are you currently wearing?", min_value=1)
            actual_switch_date = _prompt_date("What date did you actually switch INTO your current tray?")
            change_ortho = input("Has your estimated orthodontist appointment date changed? (y/N): ").strip().lower()
            new_ortho_date = None
            if change_ortho == "y":
                new_ortho_date = _prompt_date("New estimated orthodontist appointment date")

            extra_avoid = _prompt_avoid_dates()
            updated = reschedule_from(
                existing=existing,
                current_tray=current_tray,
                actual_switch_date=actual_switch_date,
                new_estimated_ortho_date=new_ortho_date,
                additional_avoid_dates=extra_avoid,
            )

            _print_schedule(updated.schedule)

            desc = "Switch to the next Invisalign tray (scheduling convenience only; follow your orthodontist’s instructions)."
            write_ics(updated.schedule, ICS_PATH, description=desc)
            _write_csv(updated.schedule, CSV_PATH)
            save_plan(updated, PLAN_PATH)

            print(f"\nSaved updated plan to {PLAN_PATH}")
            print(f"Wrote calendar file: {ICS_PATH}  (import into Apple/Google Calendar)")
            print(f"Wrote CSV: {CSV_PATH}")
            print(f"Open the output folder in Finder (Mac): open {OUT_DIR.resolve()}")
            return

    # New plan flow
    start_date = _prompt_date("Start date (date you switched into Tray 1)")
    n_trays = _prompt_int("How many trays are in your set?", min_value=1)
    ortho_date = _prompt_date("Estimated next orthodontist appointment date")
    default_days = _prompt_int("Default days per tray", min_value=1, default=14)
    avoid = _prompt_avoid_dates()

    inp = PlanInput(
        start_date=start_date,
        n_trays=n_trays,
        estimated_ortho_date=ortho_date,
        default_days_per_tray=default_days,
        avoid_dates=avoid,
        buffer_days_before_ortho=4,
    )
    plan = build_plan(inp)

    _print_schedule(plan.schedule)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    desc = (
        "Switch to the next Invisalign tray (scheduling convenience only; follow your orthodontist’s instructions). "
        "This plan targets starting your final tray ~4 days before your estimated appointment as a buffer."
    )
    write_ics(plan.schedule, ICS_PATH, description=desc)
    _write_csv(plan.schedule, CSV_PATH)
    save_plan(plan, PLAN_PATH)

    print(f"\nSaved plan to {PLAN_PATH}")
    print(f"Wrote calendar file: {ICS_PATH}  (import into Apple/Google Calendar)")
    print(f"Wrote CSV: {CSV_PATH}")

    print("\nHow to use the calendar export:")
    print("- Apple Calendar: open the .ics file to import it.")
    print("- Google Calendar: Settings → Import & export → Import the .ics file.")


if __name__ == "__main__":
    main()
