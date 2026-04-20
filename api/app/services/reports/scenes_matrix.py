"""03 — Scene Matrix xlsx report."""
from openpyxl import Workbook

from ._common import (
    write_title_block, apply_print_settings, set_col_widths,
    FONT_HEADER_WHITE, FONT_BODY, FONT_BODY_BOLD,
    FILL_SECTION_HDR, FILL_DAY_BANNER, CENTER, LEFT, BORDER,
)
from ..project_graph import ProjectGraph, fmt_pages


def generate(pg: ProjectGraph, out_path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Scene Matrix"

    headers = ["SC#", "TITLE", "LOC", "D/N", "PAGES", "SETUPS", "CHARACTERS", "SHOOT DAY"]
    n = len(headers)
    write_title_block(ws, f"{pg.project.title} — SCENE MATRIX", subtitle=pg.project.window or "", n_cols=n)

    for c, h in enumerate(headers, 1):
        cell = ws.cell(3, c)
        cell.value = h
        cell.font = FONT_HEADER_WHITE
        cell.fill = FILL_SECTION_HDR
        cell.alignment = CENTER
        cell.border = BORDER
    ws.row_dimensions[3].height = 22

    # Build scene → shoot_day_number lookup
    scene_to_sdn: dict[str, int | None] = {}
    for day in pg.shoot_days:
        for sc in day.scenes:
            scene_to_sdn[sc.id] = day.shoot_day_number

    # Collect all scenes from shoot days in script order (de-dup)
    seen_scene_ids: set[str] = set()
    all_scenes = []
    for day in pg.days:
        for sc in day.scenes:
            if sc.id not in seen_scene_ids:
                seen_scene_ids.add(sc.id)
                all_scenes.append(sc)

    r = 4
    for sc in all_scenes:
        sdn = scene_to_sdn.get(sc.id)
        row_vals = [
            sc.scene_number,
            sc.title or "",
            sc.location_name or "",
            sc.dn.upper() if sc.dn else "",
            fmt_pages(sc.page_eighths),
            sc.setups_est or "",
            ", ".join(sc.characters),
            str(sdn) if sdn is not None else "Unscheduled",
        ]
        for c, v in enumerate(row_vals, 1):
            cell = ws.cell(r, c)
            cell.value = v
            cell.font = FONT_BODY_BOLD if c == 1 else FONT_BODY
            cell.alignment = LEFT
            cell.border = BORDER
        r += 1

    set_col_widths(ws, {1: 8, 2: 44, 3: 22, 4: 8, 5: 8, 6: 8, 7: 40, 8: 12})
    ws.freeze_panes = "A4"
    apply_print_settings(ws)
    wb.save(out_path)
