"""Seed the GQ India — Men of the Year editorial project.

Structure per GQ's brief (27 Oct): shoots on 5, 11 and 12 November 2026;
one talent per day, with one group day of three; each talent's photos and
film happen on their shoot day. Full November is seeded so the calendar
shows the whole month.

All names and contacts are fictional placeholders — swap in real details
when GQ confirms. Re-running the script replaces the project.

Run inside the api container:
    docker compose exec api python -m scripts.seed_gq_moty
"""
from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from datetime import date, time, timedelta

import sqlalchemy as sa

from app.db import AsyncSessionLocal

OWNER_EMAIL = "kunal.panjwani@pixis.ai"
PROJECT_TITLE = "GQ India — Men of the Year 2026"
WINDOW = "November 2026"


def _uid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Talent (fictional placeholders)
# ---------------------------------------------------------------------------

TALENT = {
    "aarav": ("Aarav Khanna", "Actor · Men of the Year (cover)", True,
              "Priya Nair", "+91 98200 11001", "team.aarav@talentdesk.in"),
    "zoya":  ("Zoya Merchant", "Musician · Artist of the Year", False,
              "Farhan Shaikh", "+91 98200 11002", "mgmt.zoya@soundline.in"),
    "dhruv": ("Dhruv Saldanha", "Athlete · Sportsperson of the Year", False,
              "Ankita Rao", "+91 98200 11003", "dhruv@apexsports.in"),
    "ira":   ("Ira Bakshi", "Entrepreneur · Innovator of the Year", False,
              "Rohit Menon", "+91 98200 11005", "ea@irabakshi.com"),
    "rehan": ("Rehan Qureshi", "Comedian · Breakthrough Performer", False,
              "Tanvi Joshi", "+91 98200 11006", "bookings.rehan@lol.in"),
}

LOCATIONS = {
    "studio":  ("Stage 2, Lightbox Studios", "Lower Parel, Mumbai", "studio"),
    "rooftop": ("The Terrace, Meridian House", "Worli, Mumbai", "ext"),
}

# ---------------------------------------------------------------------------
# Shoot days — 5, 11, 12 November 2026.
# segments: (ref, title, start "HH:MM", minutes, [talent keys])
# hmu:      (talent key, call "HH:MM", lead artist, apply minutes)
# crew:     photographer + video director for the day
# ---------------------------------------------------------------------------

SHOOT_DAYS = [
    dict(d=date(2026, 11, 5), no=1, loc="studio", shift=("07:30", "19:00"),
         banner="Cover shoot — Aarav Khanna",
         crew={"photographer": "Kabir Mistry", "video": "Sana Irani"},
         segments=[
             ("P1", "Photos — Aarav Khanna", "09:00", 240, ["aarav"]),
             ("F1", "Film — Aarav Khanna", "14:30", 150, ["aarav"]),
         ],
         hmu=[("aarav", "07:30", "Meher Contractor", 90)],
         notes="Closed set for the cover looks. Lunch 13:00."),
    dict(d=date(2026, 11, 11), no=2, loc="studio", shift=("08:00", "18:00"),
         banner="Shoot — Zoya Merchant",
         crew={"photographer": "Kabir Mistry", "video": "Sana Irani"},
         segments=[
             ("P2", "Photos — Zoya Merchant", "09:30", 210, ["zoya"]),
             ("F2", "Film — Zoya Merchant", "14:00", 120, ["zoya"]),
         ],
         hmu=[("zoya", "08:00", "Meher Contractor", 75)],
         notes=None),
    dict(d=date(2026, 11, 12), no=3, loc="rooftop", shift=("07:00", "19:30"),
         banner="Shoot — Dhruv · Ira · Rehan",
         crew={"photographer": "Nikhil Dhawan", "video": "Sana Irani"},
         segments=[
             ("P3", "Photos — Dhruv Saldanha", "08:30", 120, ["dhruv"]),
             ("P4", "Photos — Ira Bakshi", "11:00", 120, ["ira"]),
             ("P5", "Photos — Rehan Qureshi", "14:00", 120, ["rehan"]),
             ("F3", "Film — Dhruv · Ira · Rehan", "16:30", 120, ["dhruv", "ira", "rehan"]),
         ],
         hmu=[("dhruv", "07:00", "Jay Lobo", 45),
              ("ira", "09:30", "Meher Contractor", 60),
              ("rehan", "12:30", "Jay Lobo", 45)],
         notes="Golden-hour film block from 16:30 on the terrace."),
]


def _t(hhmm: str | None) -> time | None:
    if not hhmm:
        return None
    h, m = hhmm.split(":")
    return time(int(h), int(m))


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # Owner
        row = (await session.execute(
            sa.text("SELECT id FROM users WHERE email = :e"), {"e": OWNER_EMAIL}
        )).first()
        if row:
            owner_id = row.id
        else:
            owner_id = _uid()
            await session.execute(
                sa.text("INSERT INTO users (id, email, name, created_at) "
                        "VALUES (:id, :e, :n, NOW())"),
                {"id": owner_id, "e": OWNER_EMAIL, "n": "Kunal Panjwani"},
            )

        # Replace any previous seed of this project
        await session.execute(
            sa.text("DELETE FROM projects WHERE title = :t AND owner_id = :o"),
            {"t": PROJECT_TITLE, "o": owner_id},
        )

        project_id = _uid()
        share_token = secrets.token_urlsafe(16)
        settings = {"mode": "editorial", "share_token": share_token}
        await session.execute(
            sa.text(
                "INSERT INTO projects (id, owner_id, title, \"window\", start_date, end_date, "
                "status, settings, source_file, source_filename, created_at, updated_at) "
                "VALUES (:id, :o, :t, :w, :sd, :ed, 'pre', CAST(:s AS jsonb), :src, :fn, NOW(), NOW())"
            ),
            {"id": project_id, "o": owner_id, "t": PROJECT_TITLE, "w": WINDOW,
             "sd": date(2026, 11, 1), "ed": date(2026, 11, 30),
             "s": json.dumps(settings), "src": b"", "fn": "seed_gq_moty"},
        )

        loc_ids: dict[str, str] = {}
        for key, (name, area, kind) in LOCATIONS.items():
            lid = _uid()
            await session.execute(
                sa.text("INSERT INTO locations (id, project_id, name, area, kind, created_at, updated_at) "
                        "VALUES (:id, :pid, :n, :a, :k, NOW(), NOW())"),
                {"id": lid, "pid": project_id, "n": name, "a": area, "k": kind},
            )
            loc_ids[key] = lid

        char_ids: dict[str, str] = {}
        for key, (name, role, principal, mgr, phone, email) in TALENT.items():
            cid = _uid()
            await session.execute(
                sa.text(
                    "INSERT INTO characters (id, project_id, canonical_name, display_name, "
                    "actor_name, actor_contact, is_principal, notes, created_at, updated_at) "
                    "VALUES (:id, :pid, :cn, :dn, NULL, CAST(:ct AS jsonb), :pr, :nt, NOW(), NOW())"
                ),
                {"id": cid, "pid": project_id, "cn": name.upper(), "dn": name,
                 "ct": json.dumps({"manager": mgr, "phone": phone, "email": email}),
                 "pr": principal, "nt": role},
            )
            char_ids[key] = cid

        shoot_by_date = {s["d"]: s for s in SHOOT_DAYS}

        # Full month of November, so the calendar shows every date
        for offset in range(30):
            day_date = date(2026, 11, 1) + timedelta(days=offset)
            spec = shoot_by_date.get(day_date)
            day_id = _uid()
            shift = spec.get("shift") if spec else None
            await session.execute(
                sa.text(
                    "INSERT INTO days (id, project_id, shoot_day_number, date, kind, "
                    "shift_start, shift_end, primary_location_id, banner_text, crew, notes, "
                    "created_at, updated_at) "
                    "VALUES (:id, :pid, :no, :dt, :k, :ss, :se, :loc, :bn, CAST(:cr AS jsonb), :nt, NOW(), NOW())"
                ),
                {"id": day_id, "pid": project_id,
                 "no": spec.get("no") if spec else None,
                 "dt": day_date, "k": "shoot" if spec else "off",
                 "ss": _t(shift[0]) if shift else None,
                 "se": _t(shift[1]) if shift else None,
                 "loc": loc_ids.get(spec.get("loc")) if spec else None,
                 "bn": spec.get("banner") if spec else None,
                 "cr": json.dumps(spec["crew"]) if spec and spec.get("crew") else None,
                 "nt": spec.get("notes") if spec else None},
            )

            if not spec:
                continue

            for order, (ref, title, start, minutes, who) in enumerate(spec["segments"], 1):
                scene_id = _uid()
                await session.execute(
                    sa.text(
                        "INSERT INTO scenes (id, project_id, scene_number, title, dn, "
                        "location_id, sequence, status, created_at, updated_at) "
                        "VALUES (:id, :pid, :sn, :t, 'day_int', :loc, :seq, 'planned', NOW(), NOW())"
                    ),
                    {"id": scene_id, "pid": project_id, "sn": ref, "t": title,
                     "loc": loc_ids.get(spec["loc"]), "seq": order},
                )
                await session.execute(
                    sa.text(
                        "INSERT INTO day_scenes (id, day_id, scene_id, order_in_day, "
                        "estimated_start, estimated_duration_minutes, actual_status, "
                        "created_at, updated_at) "
                        "VALUES (:id, :did, :sid, :o, :st, :dur, 'scheduled', NOW(), NOW())"
                    ),
                    {"id": _uid(), "did": day_id, "sid": scene_id, "o": order,
                     "st": _t(start), "dur": minutes},
                )
                for key in who:
                    await session.execute(
                        sa.text(
                            "INSERT INTO scene_characters (id, scene_id, character_id, role, created_at) "
                            "VALUES (:id, :sid, :cid, 'featured', NOW())"
                        ),
                        {"id": _uid(), "sid": scene_id, "cid": char_ids[key]},
                    )

            for key, call, lead, apply_min in spec.get("hmu", []):
                await session.execute(
                    sa.text(
                        "INSERT INTO hmu_sessions (id, project_id, character_id, day_id, "
                        "look_id, category, apply_minutes, hmu_call_time, artist_lead, "
                        "mold_sessions, created_at, updated_at) "
                        "VALUES (:id, :pid, :cid, :did, 'L1', 'straight', :ap, :ct, :ld, "
                        "CAST('[]' AS jsonb), NOW(), NOW())"
                    ),
                    {"id": _uid(), "pid": project_id, "cid": char_ids[key],
                     "did": day_id, "ap": apply_min, "ct": _t(call), "ld": lead},
                )

        scenario_id = _uid()
        await session.execute(
            sa.text(
                "INSERT INTO scenarios (id, project_id, name, is_live, created_by, "
                "created_at, updated_at) VALUES (:id, :pid, 'Live plan', TRUE, :o, NOW(), NOW())"
            ),
            {"id": scenario_id, "pid": project_id, "o": owner_id},
        )
        await session.execute(
            sa.text("UPDATE projects SET live_scenario_id = :sid WHERE id = :pid"),
            {"sid": scenario_id, "pid": project_id},
        )

        await session.commit()

        print(f"Seeded: {PROJECT_TITLE}")
        print(f"  project_id : {project_id}")
        print(f"  share token: {share_token}")
        print(f"  app URL    : http://localhost:3000/project/{project_id}/calendar")
        print(f"  share URL  : http://localhost:3000/share/{share_token}")


if __name__ == "__main__":
    asyncio.run(seed())
