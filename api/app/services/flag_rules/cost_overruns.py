"""Rule: cost_overruns — VFX shots with extended bids or large JR counts.

Checks:
  1. Any VFX shot with bid_status == 'extended' → warning.
  2. Any single day with junior_artist_calls.count > 100 → warning (mob scene risk).
  3. Any animal with no handler assigned → info.
"""
from __future__ import annotations

from ..project_graph import ProjectGraph

_JR_THRESHOLD = 100


def detect(graph: ProjectGraph) -> list[dict]:
    flags: list[dict] = []

    # VFX extended bids
    for shot in graph.vfx_shots:
        if shot.bid_status == "extended":
            flags.append({
                "kind": "cost_overrun",
                "severity": "warning",
                "title": f"VFX {shot.shot_number}: bid extended",
                "description": (
                    f"VFX shot {shot.shot_number} ({shot.shot_type}) has an extended bid. "
                    "Review with VFX supervisor and update budget estimate."
                ),
            })

    # Large JR counts
    for jr in graph.jr_calls:
        if jr.count > _JR_THRESHOLD:
            flags.append({
                "kind": "cost_overrun",
                "severity": "warning",
                "title": f"Day {jr.shoot_day_number}: {jr.count} JA ({jr.grade})",
                "description": (
                    f"Day {jr.shoot_day_number} has {jr.count} {jr.grade} junior artists — "
                    "above the 100-person threshold. Confirm vendor capacity and permits."
                ),
            })

    # Animals without handlers
    for animal in graph.animals:
        if not animal.handler_name:
            flags.append({
                "kind": "cost_overrun",
                "severity": "info",
                "title": f"Animal ({animal.species}): no handler assigned",
                "description": (
                    f"{animal.species} has no handler name recorded. "
                    "AWBI welfare compliance requires a named, certified handler on set."
                ),
            })

    return flags
