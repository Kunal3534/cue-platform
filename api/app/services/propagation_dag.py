"""Static dependency DAG: entity table → set of view names that depend on it.

For v1 we over-invalidate (whole view, not incremental rows).
"""
from __future__ import annotations

ENTITY_VIEW_DEPS: dict[str, frozenset[str]] = {
    "scenes":              frozenset({"main_schedule", "scenes_matrix", "calendar", "cast_dood"}),
    "day_scenes":          frozenset({"main_schedule", "scenes_matrix", "calendar", "cast_dood"}),
    "scene_characters":    frozenset({"cast_dood", "scenes_matrix"}),
    "days":                frozenset({"main_schedule", "calendar", "cast_dood"}),
    "characters":          frozenset({"cast_dood", "scenes_matrix"}),
    "camera_units":        frozenset({"main_schedule", "calendar"}),
    "camera_day_uses":     frozenset({"main_schedule", "calendar"}),
    "junior_artist_calls": frozenset({"main_schedule", "calendar"}),
    "locations":           frozenset({"main_schedule", "calendar", "scenes_matrix"}),
    "picture_vehicles":    frozenset({"main_schedule"}),
    "vehicle_day_uses":    frozenset({"main_schedule"}),
    "scene_props":         frozenset({"main_schedule"}),
    "scene_vfx":           frozenset({"main_schedule"}),
    "scene_sfx":           frozenset({"main_schedule"}),
    "scene_stunts":        frozenset({"main_schedule"}),
    "scene_animals":       frozenset({"main_schedule"}),
}

ALL_VIEWS: frozenset[str] = frozenset(
    v for deps in ENTITY_VIEW_DEPS.values() for v in deps
)


def views_for_edits(edits: list[dict]) -> list[str]:
    """Return sorted list of view names affected by the given edit items."""
    affected: set[str] = set()
    for edit in edits:
        affected.update(ENTITY_VIEW_DEPS.get(edit.get("entity", ""), frozenset()))
    return sorted(affected)
