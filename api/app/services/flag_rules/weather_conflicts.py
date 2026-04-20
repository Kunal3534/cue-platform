"""Rule: weather_conflicts — exterior shoot day has a weather-hold indicator.

v1 stub: the days.weather JSONB column is populated externally (weather API
integration is out of scope for v1).  This rule fires if:
  - day.weather is not None AND
  - day.weather.get("hold") is True AND
  - day.kind == "shoot" AND location_kind in ("ext", "practical")

Without real weather data this produces no flags; it's the hook point for Week 7.
"""
from __future__ import annotations

from ..project_graph import ProjectGraph


def detect(graph: ProjectGraph) -> list[dict]:
    # Full implementation requires day.weather JSONB field in ProjectGraph;
    # the graph loader does not yet expose it (added when weather API lands).
    # Return empty until then — this is the documented stub hook.
    return []
