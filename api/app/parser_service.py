"""Wraps the cue_engine parser for API use: file bytes → dict ready for DB."""
from __future__ import annotations
import io
import tempfile
from dataclasses import asdict
from typing import Any
import openpyxl

from .cue_engine import parser as engine_parser


def parse_xlsx_bytes(data: bytes) -> dict[str, Any]:
    """Parse an uploaded master breakdown. Returns a JSON-serializable dict.

    The parser expects a filesystem path, so we write the bytes to a temp file.
    """
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=True) as tmp:
        tmp.write(data); tmp.flush()
        project = engine_parser.load_breakdown(tmp.name)

    # Convert dataclass graph → JSON-safe dict
    # (the parser exposes ShootSpec dataclasses; we flatten for storage)
    days = []
    for d in project.days:
        days.append({
            "row_idx": d.row_idx,
            "date_raw": d.date_raw,
            "day_label": d.day_label,
            "is_shoot": d.is_shoot,
            "shoot_day_no": d.shoot_day_no,
            "location": d.location,
            "film_location": d.film_location,
            "shift": d.shift,
            "units": d.units,
            "cast": d.cast,
            "supporting_cast": d.supporting_cast,
            "picture_vehicles": d.picture_vehicles,
            "extras": d.extras,
            "notes": d.notes,
        })

    # Unit cols ordering preserved from v2 parser
    # (note: parser doesn't expose unit_cols, we infer from day units)
    unit_cols = []
    seen = set()
    for d in project.days:
        for code in d.units.keys():
            if code not in seen:
                seen.add(code); unit_cols.append(code)

    return {
        "title": project.title,
        "window": project.window,
        "days": days,
        "unit_cols": unit_cols,
        "cast_map": {k: v for k, v in project.cast_map.items()},
    }


def project_from_dict(data: dict[str, Any]):
    """Rebuild a minimal Project-like object that the engine reports can consume."""
    from types import SimpleNamespace

    def mk_day(d: dict) -> SimpleNamespace:
        return SimpleNamespace(**d)

    days = [mk_day(d) for d in data.get("days", [])]
    shoot_days = [d for d in days if d.is_shoot]

    title = data.get("title", "Untitled")
    window = data.get("window", "")
    unit_cols = data.get("unit_cols", [])

    # Use a Project class compatible with our engine reports' duck-typed access.
    # Note: reports/_common.write_title_block expects a project with .title / .window / .day_label().
    class _Project:
        def __init__(self):
            self.title = title
            self.window = window
            self.days = days
            self.unit_cols = unit_cols
            self.cast_map = data.get("cast_map", {})
            self.scenes_by_day = {}   # none in v1
        @property
        def shoot_days(self):
            return shoot_days
        def day_label(self, i):
            # engine reports don't use this path often, keep simple
            return self.days[i].date_raw if i < len(self.days) else ""

    return _Project()
