"""Build the GQ MOTY export pack: every Excel view + a call sheet PDF per
working day, written to /app/export_pack (→ api/export_pack on the host).

Run inside the api container:
    docker compose exec api python -m scripts.export_pack
"""
from __future__ import annotations

import asyncio
import os
import re

import sqlalchemy as sa

from app.db import AsyncSessionLocal
from app.services import storage
from app.services.call_sheet_generator import CallSheetGenerator
from app.services.project_graph import ProjectGraph
from app.services.reports import (
    calendar, main_schedule, cast_dood, scenes_matrix,
    hmu, wardrobe, cameras, vehicles, requirements,
)

PROJECT_TITLE = "GQ India — Men of the Year 2026"
OUT = "/app/export_pack"

XLSX_REPORTS = [
    ("01_Master_Calendar.xlsx", calendar),
    ("02_Day_By_Day_Schedule.xlsx", main_schedule),
    ("03_Talent_Schedule_DOOD.xlsx", cast_dood),
    ("04_Segment_Matrix.xlsx", scenes_matrix),
    ("05_HMU_Schedule.xlsx", hmu),
    ("06_Wardrobe_Looks.xlsx", wardrobe),
    ("07_Camera_Video_Units.xlsx", cameras),
    ("08_Transport.xlsx", vehicles),
    ("09_Requirements.xlsx", requirements),
]


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:60]


async def build() -> None:
    os.makedirs(f"{OUT}/callsheets", exist_ok=True)

    async with AsyncSessionLocal() as session:
        proj = (await session.execute(
            sa.text("SELECT id, owner_id, live_scenario_id FROM projects WHERE title = :t"),
            {"t": PROJECT_TITLE},
        )).first()
        if not proj:
            raise SystemExit(f"Project not found: {PROJECT_TITLE} — run seed_gq_moty first")

        pg = await ProjectGraph.load(proj.id, proj.live_scenario_id, session)

        for filename, module in XLSX_REPORTS:
            path = f"{OUT}/{filename}"
            module.generate(pg, path)
            print(f"  ✓ {filename} ({os.path.getsize(path)/1024:.1f} KB)")

        day_rows = (await session.execute(
            sa.text("""
                SELECT d.id, d.date, d.kind, d.banner_text
                FROM days d
                WHERE d.project_id = :pid
                  AND d.kind IN ('shoot', 'prep')
                  AND EXISTS (SELECT 1 FROM day_scenes ds WHERE ds.day_id = d.id)
                ORDER BY d.date
            """),
            {"pid": proj.id},
        )).fetchall()

        for d in day_rows:
            sheet = await CallSheetGenerator.generate(proj.id, d.id, proj.owner_id, session)
            pdf = storage.get_bytes(sheet.pdf_s3_key)
            name = f"{d.date.isoformat()}_{_slug(d.banner_text or d.kind)}.pdf"
            with open(f"{OUT}/callsheets/{name}", "wb") as fh:
                fh.write(pdf)
            print(f"  ✓ callsheets/{name} ({len(pdf)/1024:.1f} KB)")

    print(f"\nPack written to {OUT}")


if __name__ == "__main__":
    asyncio.run(build())
