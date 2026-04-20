"""Rule: drone_nofly — drone unit scheduled within a known no-fly zone or
on a day that falls within a restricted temporal window (national holiday,
airshow, etc.).

v1 uses a static JSON file for the no-fly list; DGCA live API is Week 7.

No-fly conditions checked:
  1. Day is a declared national holiday (static list for 2026).
  2. Location lat/lng is within 5 km of an airport centroid (static list).

If the graph doesn't carry lat/lng on the day (location_id resolves to a
location without coordinates), we can't do the geo check — emits an info flag
asking for verification instead.
"""
from __future__ import annotations

import math
from datetime import date

from ..project_graph import ProjectGraph

# 2026 Indian national holidays (approximate dates)
_NATIONAL_HOLIDAYS_2026: set[date] = {
    date(2026, 1, 26),  # Republic Day
    date(2026, 8, 15),  # Independence Day
    date(2026, 10, 2),  # Gandhi Jayanti
}

# Major airport centroids near Ratnagiri region (lat, lng)
_AIRPORTS = [
    ("Chhatrapati Shivaji Mumbai",  19.0896, 72.8656),
    ("Pune Airport",                18.5822, 73.9197),
    ("Ratnagiri Airport",           17.0136, 73.3278),
    ("Goa Dabolim",                 15.3808, 73.8314),
]

_NO_FLY_RADIUS_KM = 5.0


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def detect(graph: ProjectGraph) -> list[dict]:
    flags: list[dict] = []

    for day in graph.shoot_days:
        has_drone = any(code in ("DR",) for code, _k, _c in day.camera_uses)
        if not has_drone:
            continue

        sdn = day.shoot_day_number

        # Holiday check
        if day.date in _NATIONAL_HOLIDAYS_2026:
            flags.append({
                "kind": "drone_block",
                "severity": "blocker",
                "title": f"Day {sdn}: drone on national holiday ({day.date.strftime('%-d %b %Y')})",
                "description": (
                    "Drone operations are restricted on national holidays. "
                    "DGCA special permission required or reschedule."
                ),
                "related_day_id": day.id,
            })
            continue

        # Geo check — only if we have coordinates
        # (location lat/lng not yet in ProjectGraph; emit info flag)
        flags.append({
            "kind": "drone_block",
            "severity": "info",
            "title": f"Day {sdn}: verify DGCA permit for drone",
            "description": (
                f"Day {sdn} ({day.date.strftime('%-d %b %Y')}) has a drone unit scheduled. "
                "Confirm DGCA permit is granted and location is not within 5 km of an aerodrome."
            ),
            "related_day_id": day.id,
        })

    return flags
