"""Rule: continuity — scene ordering / D-N continuity issues.

Checks:
  1. Two consecutive scenes in a shoot day with the same scene_number (duplicate).
  2. A 'night' scene immediately followed by a 'day' scene on the SAME day
     (shoot-order implies a time-travel — may be intentional but worth flagging).
  3. A scene whose dn == 'night' scheduled on a day where shift_start < 16:00
     (night scene in an early-morning shift without a split-call note).
"""
from __future__ import annotations

from datetime import time

from ..project_graph import ProjectGraph

_NIGHT_SHIFT_THRESHOLD = time(16, 0)  # night scenes expected to start ≥ 16:00


def detect(graph: ProjectGraph) -> list[dict]:
    flags: list[dict] = []

    for day in graph.shoot_days:
        sdn = day.shoot_day_number or "?"
        scenes = day.scenes

        # Duplicate scene numbers within a day
        seen: set[str] = set()
        for sc in scenes:
            if sc.scene_number in seen:
                flags.append({
                    "kind": "continuity",
                    "severity": "warning",
                    "title": f"Day {sdn}: duplicate scene {sc.scene_number}",
                    "description": (
                        f"Scene {sc.scene_number} appears more than once on Day {sdn}. "
                        "Check day_scenes for duplicate entries."
                    ),
                    "related_day_id": day.id,
                })
            seen.add(sc.scene_number)

        # Night → Day ordering within same day
        for i in range(len(scenes) - 1):
            if scenes[i].dn == "night" and scenes[i + 1].dn in ("day", "day_int"):
                flags.append({
                    "kind": "continuity",
                    "severity": "info",
                    "title": (
                        f"Day {sdn}: night scene {scenes[i].scene_number} "
                        f"before day scene {scenes[i + 1].scene_number}"
                    ),
                    "description": (
                        "A NIGHT scene is ordered before a DAY scene on the same shoot day. "
                        "This is valid for split-calls but verify with the 1st AD."
                    ),
                    "related_day_id": day.id,
                })

        # Night scene with early shift
        if day.shift_start and day.shift_start < _NIGHT_SHIFT_THRESHOLD:
            night_scenes = [sc for sc in scenes if sc.dn in ("night", "night_int")]
            if night_scenes and not day.banner_text:
                flags.append({
                    "kind": "continuity",
                    "severity": "info",
                    "title": f"Day {sdn}: night scenes in early-start shift ({day.shift_start.strftime('%H:%M')})",
                    "description": (
                        f"Day {sdn} shift starts at {day.shift_start.strftime('%H:%M')} "
                        f"but includes {len(night_scenes)} night scene(s). "
                        "Add a banner note if a split call is intended."
                    ),
                    "related_day_id": day.id,
                })

    return flags
