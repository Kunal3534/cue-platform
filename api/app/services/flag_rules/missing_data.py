"""Rule: missing_data — structural gaps that will break downstream outputs.

Checks:
  1. Shoot day with no scenes scheduled.
  2. Scene with no characters linked.
  3. Principal character with no actor name set.
  4. Shoot day with no primary location.
  5. Scene with page_eighths == 0 or None.
"""
from __future__ import annotations

from ..project_graph import ProjectGraph


def detect(graph: ProjectGraph) -> list[dict]:
    flags: list[dict] = []

    for day in graph.shoot_days:
        sdn = day.shoot_day_number or "?"

        if not day.scenes:
            flags.append({
                "kind": "missing_data",
                "severity": "warning",
                "title": f"Day {sdn}: no scenes scheduled",
                "description": (
                    f"Shoot day {sdn} ({day.date.strftime('%-d %b %Y')}) "
                    "has no scenes in the breakdown. "
                    "Add scenes or change the day kind to 'prep' / 'buffer'."
                ),
                "related_day_id": day.id,
            })

        if not day.location_id:
            flags.append({
                "kind": "missing_data",
                "severity": "info",
                "title": f"Day {sdn}: no primary location set",
                "description": (
                    f"Shoot day {sdn} has no primary location assigned. "
                    "Call sheets cannot be completed without a location."
                ),
                "related_day_id": day.id,
            })

        for sc in day.scenes:
            if not sc.characters:
                flags.append({
                    "kind": "missing_data",
                    "severity": "info",
                    "title": f"Scene {sc.scene_number}: no cast linked",
                    "description": (
                        f"Scene {sc.scene_number} has no characters in the breakdown. "
                        "DOOD and call sheet cast sections will be incomplete."
                    ),
                })
            if not sc.page_eighths:
                flags.append({
                    "kind": "missing_data",
                    "severity": "info",
                    "title": f"Scene {sc.scene_number}: page count is zero",
                    "description": (
                        f"Scene {sc.scene_number} has no page count. "
                        "Schedule totals and call-sheet page summaries will be wrong."
                    ),
                })

    for char in graph.characters:
        if char.is_principal and not char.actor_name:
            flags.append({
                "kind": "missing_data",
                "severity": "warning",
                "title": f"{char.display_name}: no actor assigned",
                "description": (
                    f"Principal character {char.display_name} has no actor name. "
                    "Call sheets and DOOD reports will be incomplete."
                ),
                "related_character_id": char.id,
            })

    return flags
