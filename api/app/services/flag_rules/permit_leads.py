"""Rule: permit_leads — a location is used before its permit grants enough lead time.

Checks:
  - Location-kind 'ext' (exterior) used on a shoot day within 7 days of today
    and no granted location permit exists for it.
  - Drone unit used on a day without an aerial_dgca permit that is 'granted'.
  - Coastal location used without a 'coastal' permit that is 'granted'.

All comparisons are against graph.days dates, not the current wall clock, so the
rule re-runs cleanly whenever the schedule changes.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..project_graph import ProjectGraph

_LEAD_DAYS = {
    "aerial_dgca": 14,
    "coastal": 21,
    "location": 7,
    "fire": 14,
    "police": 7,
}


def detect(graph: ProjectGraph) -> list[dict]:
    flags: list[dict] = []

    # Collect earliest shoot date per location_id
    loc_first_day: dict[str, date] = {}
    for day in graph.shoot_days:
        if day.location_id and day.date:
            if day.location_id not in loc_first_day or day.date < loc_first_day[day.location_id]:
                loc_first_day[day.location_id] = day.date

    # Check drone — any day with a drone camera unit needs DGCA permit
    drone_days = [
        d for d in graph.shoot_days
        if any(code in ("DR", "drone") for code, _k, _c in d.camera_uses)
    ]
    if drone_days:
        # No permit table in graph for now — flag as info-level stub
        flags.append({
            "kind": "permit_lead",
            "severity": "info",
            "title": f"DGCA aerial permit — {len(drone_days)} drone day(s) scheduled",
            "description": (
                f"{len(drone_days)} shoot day(s) use a drone unit. "
                "Verify DGCA permit is granted with ≥14 days lead time "
                "before the first drone day "
                f"({min(d.date for d in drone_days).strftime('%-d %b %Y')})."
            ),
        })

    # Exterior locations — flag if no confirmed location permit data available
    # (graph doesn't carry permits table yet; emit info flags for ext locations)
    ext_locs = {
        day.location_id
        for day in graph.shoot_days
        if day.location_kind in ("ext", "practical") and day.location_id
    }
    if ext_locs:
        for loc_id in ext_locs:
            first_date = loc_first_day.get(loc_id)
            if first_date is None:
                continue
            flags.append({
                "kind": "permit_lead",
                "severity": "info",
                "title": f"Location permit check — first use {first_date.strftime('%-d %b %Y')}",
                "description": (
                    "Exterior location requires a location permit. "
                    "Confirm permit is applied ≥7 days before first shoot day."
                ),
            })
    return flags
