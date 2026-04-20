"""
01 - Main Schedule.

Day-wise shoot schedule. Each shoot day is a banner row followed by one line
describing location, shift, unit counts, and cast. If scene-level data is
provided (Project.scenes_by_day) we render scene-wise rows under each day
in the Nirmal Pathak style.
"""
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment
from ._common import (
    apply_print_settings,
    write_title_block, autosize, FONT_TITLE, FONT_HEADER, FONT_HEADER_WHITE,
    FONT_BODY, FONT_BODY_BOLD, FONT_BREAK, FILL_TITLE, FILL_HEADER_GRAY,
    FILL_GREEN_SOFT, FILL_DAY_BANNER, FILL_SECTION_HDR, CENTER, LEFT, BORDER,
)


def generate(project, out_path: str):
    wb = Workbook()
    ws = wb.active
    ws.title = "Main Schedule"

    has_scenes = bool(project.scenes_by_day)

    if has_scenes:
        _render_scene_wise(ws, project)
    else:
        _render_day_wise(ws, project)

    apply_print_settings(ws)

    wb.save(out_path)


# ----------------------- day-wise (default) -----------------------

def _render_day_wise(ws, project):
    headers = ["DATE", "DAY", "LOCATION", "FILM LOCATION", "SHIFT", "CAST",
               "SUPPORTING CAST", "PICTURE VEHICLES", "EXTRAS / MOB", "NOTES"]
    write_title_block(ws, project.title + " — MAIN SCHEDULE",
                      subtitle=project.window, n_cols=len(headers))

    # header row 3
    for c, h in enumerate(headers, 1):
        cell = ws.cell(3, c)
        cell.value = h
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER_GRAY
        cell.alignment = CENTER
        cell.border = BORDER
    ws.row_dimensions[3].height = 22

    r = 4
    for day in project.days:
        if not day.is_shoot:
            # break / rehearsal — single banner
            ws.cell(r, 1).value = day.date_raw
            ws.cell(r, 2).value = day.day_label
            for c in range(1, len(headers) + 1):
                ws.cell(r, c).fill = FILL_GREEN_SOFT
                ws.cell(r, c).font = FONT_BREAK
                ws.cell(r, c).alignment = CENTER
                ws.cell(r, c).border = BORDER
            ws.merge_cells(start_row=r, end_row=r, start_column=3, end_column=len(headers))
            r += 1
            continue

        vals = [
            day.date_raw,
            day.day_label,
            day.location,
            day.film_location,
            day.shift,
            ", ".join(day.cast),
            ", ".join(day.supporting_cast),
            ", ".join(day.picture_vehicles),
            day.extras,
            day.notes,
        ]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(r, c)
            cell.value = v
            cell.font = FONT_BODY_BOLD if c in (1, 2) else FONT_BODY
            cell.alignment = LEFT if c >= 3 else CENTER
            cell.border = BORDER
        r += 1

    # column widths
    widths = {1: 12, 2: 14, 3: 18, 4: 32, 5: 12, 6: 40, 7: 32, 8: 30, 9: 28, 10: 40}
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.freeze_panes = "A4"


# ----------------------- scene-wise (if Scenes sheet given) -----------------------

def _render_scene_wise(ws, project):
    headers = ["SC", "DESCRIPTION", "LOC", "SUB-LOC", "D/N", "I/E",
               "CHARACTERS", "PC", "TIME", "CAM", "SPL EQUIP", "CODE"]
    write_title_block(ws, project.title + " — MAIN SCHEDULE",
                      subtitle=project.window, n_cols=len(headers))

    r = 3
    for day in project.days:
        if not day.is_shoot:
            for c in range(1, len(headers) + 1):
                ws.cell(r, c).fill = FILL_GREEN_SOFT
                ws.cell(r, c).font = FONT_BREAK
                ws.cell(r, c).alignment = CENTER
                ws.cell(r, c).border = BORDER
            ws.cell(r, 1).value = f"{day.date_raw} — {day.day_label}"
            ws.merge_cells(start_row=r, end_row=r, start_column=1, end_column=len(headers))
            r += 1
            continue

        # day banner
        banner = ws.cell(r, 1)
        banner.value = (f"{day.date_raw} · {day.day_label} · {day.location} "
                        f"→ {day.film_location} · {day.shift}")
        banner.font = FONT_HEADER
        banner.fill = FILL_DAY_BANNER
        banner.alignment = CENTER
        banner.border = BORDER
        ws.merge_cells(start_row=r, end_row=r, start_column=1, end_column=len(headers))
        ws.row_dimensions[r].height = 22
        r += 1

        # section headers
        for c, h in enumerate(headers, 1):
            cell = ws.cell(r, c)
            cell.value = h
            cell.font = FONT_HEADER_WHITE
            cell.fill = FILL_SECTION_HDR
            cell.alignment = CENTER
            cell.border = BORDER
        r += 1

        scenes = project.scenes_by_day.get(day.day_label) \
                 or project.scenes_by_day.get(f"Day {day.shoot_day_no}") or []
        if not scenes:
            # fallback: single row summarising the day
            summary = f"{day.shift}  ·  Cast: {', '.join(day.cast)}"
            cell = ws.cell(r, 2)
            cell.value = summary
            cell.font = FONT_BODY
            cell.alignment = LEFT
            r += 1
        else:
            for sc in scenes:
                vals = [sc["sc"], sc["description"], sc["loc"], sc["sub_loc"],
                        sc["dn"], sc["ie"], sc["characters"], sc["pc"],
                        sc["time"], sc["cam"], sc["spl_equip"], sc["code"]]
                for c, v in enumerate(vals, 1):
                    cell = ws.cell(r, c)
                    cell.value = v
                    cell.font = FONT_BODY_BOLD if c == 1 else FONT_BODY
                    cell.alignment = LEFT if c == 2 else CENTER
                    cell.border = BORDER
                r += 1

    widths = {1: 10, 2: 52, 3: 16, 4: 20, 5: 6, 6: 6, 7: 30, 8: 6,
              9: 18, 10: 12, 11: 18, 12: 20}
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.freeze_panes = "A4"
