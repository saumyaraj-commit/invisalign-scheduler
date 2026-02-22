import argparse
from datetime import date
from src.schedule import build_schedule

def _parse_date(s: str) -> date:
    return date.fromisoformat(s)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--trays", type=int, required=True)
    p.add_argument("--start", type=_parse_date, required=True)
    p.add_argument("--days", type=int, default=14)
    args = p.parse_args()

    sched = build_schedule(args.trays, args.start, args.days)
    for row in sched:
        print(f"Tray {row.tray:02d}: {row.start} -> switch on {row.switch_on}")

if __name__ == "__main__":
    main()
