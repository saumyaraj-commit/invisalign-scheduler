from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from .scheduler import Plan, TraySwitch, PlanInput


def _date_to_str(d: date) -> str:
    return d.isoformat()


def _date_from_str(s: str) -> date:
    return date.fromisoformat(s)


def serialize_plan(plan: Plan) -> Dict[str, Any]:
    return {
        "meta": {
            "version": "1.0",
        },
        "inputs": {
            "start_date": _date_to_str(plan.inputs.start_date),
            "n_trays": plan.inputs.n_trays,
            "estimated_ortho_date": _date_to_str(plan.inputs.estimated_ortho_date),
            "default_days_per_tray": plan.inputs.default_days_per_tray,
            "avoid_dates": sorted([_date_to_str(d) for d in plan.inputs.avoid_dates]),
            "buffer_days_before_ortho": plan.inputs.buffer_days_before_ortho,
        },
        "schedule": [
            {
                "tray": ts.tray,
                "start": _date_to_str(ts.start),
                "switch_on": _date_to_str(ts.switch_on),
            }
            for ts in plan.schedule
        ],
    }


def deserialize_plan(payload: Dict[str, Any]) -> Plan:
    inp = payload["inputs"]
    inputs = PlanInput(
        start_date=_date_from_str(inp["start_date"]),
        n_trays=int(inp["n_trays"]),
        estimated_ortho_date=_date_from_str(inp["estimated_ortho_date"]),
        default_days_per_tray=int(inp["default_days_per_tray"]),
        avoid_dates=set(_date_from_str(s) for s in inp.get("avoid_dates", [])),
        buffer_days_before_ortho=int(inp.get("buffer_days_before_ortho", 4)),
    )

    schedule = [
        TraySwitch(
            tray=int(row["tray"]),
            start=_date_from_str(row["start"]),
            switch_on=_date_from_str(row["switch_on"]),
        )
        for row in payload["schedule"]
    ]
    return Plan(inputs=inputs, schedule=schedule)


def load_plan(path: str | Path) -> Optional[Plan]:
    p = Path(path)
    if not p.exists():
        return None
    payload = json.loads(p.read_text(encoding="utf-8"))
    return deserialize_plan(payload)


def save_plan(plan: Plan, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = serialize_plan(plan)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
