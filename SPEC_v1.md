# Cue — v1 Backend Specification

**Status:** ready to build · last updated 20 Apr 2026
**Owner:** Kunal Panjwani
**Intended consumer:** Claude Code (or any engineer) building out the full backend
**Design reference:** `cue-platform/design/` (22 clickable HTML screens)
**Predecessor:** `cue-platform/api/` (v0.1 — upload + parse + read-only main schedule; keep the parser and xlsx engine, replace the data model)

---

## 0. What this document is

A complete specification for Cue's v1 backend — the one that powers the clickable prototype in `cue-platform/design/`. Everything here is concrete: tables have columns, endpoints have shapes, services have interfaces. A new engineer (or agent) should be able to build it top-to-bottom without asking questions.

Where v0.1 stored the project as a single `parsed_json` JSONB blob, v1 breaks it apart. The reason: every v1 feature — drag-to-reschedule, propagation preview, scenario forks, multi-user edits, chat-driven mutations — needs transactional guarantees and per-entity history. A blob can't give you that.

---

## 1. Goals & non-goals

### In scope for v1

1. **Parse a master breakdown** (inherit from v0.1)
2. **Persist the whole project graph** as real relational tables — days, scenes, characters, 12 resource kinds, junction tables
3. **Reschedule operations** — move a scene between days, reorder scenes within a day, customize day banners, mark days off/travel/hold
4. **Propagation preview** — before committing any mutation, compute and return the downstream impact (which views change, which call sheets regenerate, which vendors need re-briefing)
5. **Commit or discard** — mutations are transactional; all-or-nothing
6. **Regenerate 14 views** on commit: main schedule, cast DOOD, picture vehicles, junior artists, cameras, props, animals, VFX, SFX+stunts, HMU+prosthetics, wardrobe, requirements breakdown, scene matrix, calendar
7. **Export** each view as xlsx; bundle-zip for all
8. **Generate call sheets** as paper-style PDFs (using the template from `design/project/callsheet-1.html`), versioned per day
9. **Scenarios** — fork the live board into what-if branches (Priya-cancel replan, director cut, rain contingency), diff against live, merge back
10. **Chat agent** — streaming conversational interface over the project graph with tool-use: ask questions, propose edits, commit with preview
11. **Real-time events** — SSE channel per project, broadcasts mutations to connected clients
12. **Magic-link auth** via Resend (replaces v0.1's dev-auto-login)
13. **Flags system** — surfaced conflicts (permit lead times, cast holds, weather, drone blocks)

### Out of scope for v1 (deferred to v2)

- Multi-user concurrent editing (CRDT / OT). v1 is single-owner per project, last-write-wins.
- Public share links with role-based read access.
- Mobile-specific API (v1's web frontend handles phone-sized layouts).
- Comments & collaboration threads per day/scene.
- Budget / cost tracking.
- Integrations (Google Calendar, Slack notifications, WhatsApp for call sheet distribution).

### Explicit non-goals (for all versions)

- We are not writing our own spreadsheet engine. `openpyxl` for reading/writing xlsx.
- We are not writing our own PDF engine. WeasyPrint renders HTML → PDF.
- We do not reimplement Movie Magic. The Cue mental model is scene-driven and chat-first, not a strip-rearrangement tool.

---

## 2. Architecture overview

```
┌─────────────────────────────────────────────────────────────┐
│  web/  (Next.js 14 — unchanged scope, rebuilt against v1)   │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTPS
                  ┌──────────┴──────────┐
                  │                     │
          ┌───────▼───────┐    ┌────────▼────────┐
          │   api/        │    │  worker/        │
          │  FastAPI      │    │  Arq (async)    │
          │  Uvicorn      │    │                 │
          └───┬───────────┘    └────┬────────────┘
              │                     │
    ┌─────────┼─────────────────────┼──────────┐
    │         │                     │          │
┌───▼───┐ ┌──▼──────┐  ┌────────────▼────┐  ┌──▼─────┐
│ DB    │ │ Redis   │  │  Object store    │  │ Anthropic│
│ PG15  │ │pub/sub  │  │  MinIO (S3)      │  │  API   │
│       │ │+ queues │  │                  │  │        │
└───────┘ └─────────┘  └──────────────────┘  └────────┘
```

### Services

| Service | Container | Purpose |
|---|---|---|
| `api`       | FastAPI + Uvicorn           | HTTP API, SSE streams |
| `worker`    | Arq (async Python worker)   | Heavy jobs: view regen, PDF gen, xlsx export, email send |
| `db`        | Postgres 15                 | Primary store |
| `redis`     | Redis 7                     | Job queue, pub/sub for SSE fan-out |
| `storage`   | MinIO (prod: S3/R2/Spaces)  | PDFs, exports, source xlsx blobs |
| `web`       | Next.js 14                  | Frontend (separate concern — not spec'd here) |

### Tech stack (extending v0.1)

- **Python 3.11**, FastAPI 0.115, SQLAlchemy 2.0, Alembic, Pydantic 2.9
- **Arq** for async jobs (lighter than Celery; native asyncio)
- **asyncpg + SQLAlchemy 2.0 async engine** (upgrade from v0.1's sync psycopg2)
- **WeasyPrint** for call-sheet PDFs
- **openpyxl** for xlsx (inherit from v0.1)
- **Anthropic SDK** (`anthropic` package) for the chat agent
- **itsdangerous** for signed session cookies
- **Resend** HTTP API for magic-link email
- **boto3** for S3-compatible storage

### Environment variables (extend `.env.example`)

```
DATABASE_URL=postgresql+asyncpg://cue:cue@db:5432/cue
REDIS_URL=redis://redis:6379/0
S3_ENDPOINT=http://storage:9000
S3_BUCKET=cue-v1
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_REGION=us-east-1
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5
RESEND_API_KEY=re_...
SECRET_KEY=change-me
FRONTEND_ORIGIN=http://localhost:3000
DEV_AUTO_LOGIN_EMAIL=you@studio.in      # dev only; unset in prod
MAGIC_LINK_TTL_SECONDS=900
```

---

## 3. Data model

Full DDL lives in Alembic migration `api/alembic/versions/002_v1_schema.py`. What follows is the authoritative reference.

Conventions:
- All tables have `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- All tables have `created_at TIMESTAMPTZ DEFAULT NOW()`, `updated_at TIMESTAMPTZ DEFAULT NOW()`
- Project-scoped tables include `project_id UUID REFERENCES projects(id) ON DELETE CASCADE`
- All enums are Postgres native enums (not Python-side)

### 3.1 Core

**`users`** (inherited from v0.1, no change)
```
id, email UNIQUE, name, created_at
```

**`projects`** (v0.1 `parsed_json` column dropped)
```
id
owner_id           → users(id)
title              VARCHAR(500)
window             VARCHAR(500)          -- human string "10th April to 10th May 2026"
start_date         DATE
end_date           DATE
status             ENUM('pre', 'shoot', 'wrap', 'archived')
settings           JSONB                 -- { week_off_days: [0, 6], timezone: 'Asia/Kolkata', ... }
source_file        BYTEA                 -- original uploaded xlsx
source_filename    VARCHAR(500)
live_scenario_id   UUID                  -- FK to scenarios(id), the live shoot plan
created_at, updated_at
```

**`locations`**
```
id, project_id
name               VARCHAR(500)          -- "Velneshwar Beach"
area               VARCHAR(500)          -- "Ratnagiri"
address            TEXT
lat, lng           NUMERIC(10,6) NULL
kind               ENUM('ext', 'int', 'studio', 'practical')
notes              TEXT
```

**`characters`**
```
id, project_id
canonical_name     VARCHAR(500)          -- UPPERCASE, from parser
display_name       VARCHAR(500)          -- "Aarav"
actor_name         VARCHAR(500) NULL
actor_contact      JSONB NULL            -- { phone, email, agent_name, agent_phone }
is_principal       BOOLEAN DEFAULT FALSE
notes              TEXT
UNIQUE (project_id, canonical_name)
```

**`days`**
```
id, project_id
shoot_day_number   INTEGER NULL          -- null for off/travel/hold
date               DATE
kind               ENUM('shoot','travel','off','hold','buffer','prep')
shift_start        TIME NULL
shift_end          TIME NULL
primary_location_id UUID NULL → locations(id)
banner_text        TEXT NULL             -- custom per-day note ("Shift 6-8, no lunch")
sunrise, sunset    TIME NULL             -- pre-computed from date+lat/lng
golden_hour_start, golden_hour_end TIME NULL
weather            JSONB NULL
notes              TEXT
UNIQUE (project_id, date)
INDEX (project_id, shoot_day_number)
```

**`scenes`**
```
id, project_id
scene_number       VARCHAR(32)           -- "14", "18A", "101A"
title              VARCHAR(500)          -- "Priya arrives"
description        TEXT
page_eighths       INTEGER               -- page count × 8 (so 18 = 2 2/8)
setups_est         INTEGER DEFAULT 0
dn                 ENUM('day','night','day_int','night_int','dusk')
location_id        UUID NULL → locations(id)
act                INTEGER NULL
sequence           INTEGER               -- sort in script
status             ENUM('planned','shot','omitted','pickup_needed') DEFAULT 'planned'
notes              TEXT
UNIQUE (project_id, scene_number)
```

**`scene_characters`**
```
id, scene_id, character_id
role               ENUM('speaking','non_speaking','featured','background')
UNIQUE (scene_id, character_id)
```

**`day_scenes`** — the schedule
```
id, day_id, scene_id
order_in_day       INTEGER
estimated_start    TIME NULL
estimated_duration_minutes INTEGER NULL
actual_status      ENUM('scheduled','in_progress','shot','omitted_today') DEFAULT 'scheduled'
UNIQUE (day_id, scene_id)
INDEX (scene_id)                         -- fast "what day is this scene on?"
```

### 3.2 Resources (12 kinds, separate tables)

The design exposed 12 resource departments. Each has unique fields, so each gets its own table rather than polymorphic inheritance. Shared pattern: `id, project_id, name, notes, status, created_at, updated_at` + kind-specific columns.

**`props`**
```
id, project_id
name               VARCHAR(500)
category           ENUM('hero_critical','hero','set_dress','background','food','paper_prop')
scenes_raw         TEXT                   -- denormalized SC list; junction `scene_props` is authoritative
source             ENUM('build_inhouse','build_studio','rental','owned','local_sourced','purchased')
source_vendor      VARCHAR(500) NULL
lead_days          INTEGER NULL
insurance_inr      INTEGER NULL
status             ENUM('planned','ordered','in_progress','ready','on_set','returned')
notes              TEXT
```

**`scene_props`** — junction
```
id, scene_id, prop_id
role               ENUM('hero','set_dress','action_prop','bg')
UNIQUE (scene_id, prop_id)
```

**`animals`**
```
id, project_id
species            VARCHAR(200)           -- "Horse (Marwari mare)"
count              INTEGER
handler_name       VARCHAR(500)
handler_contact    VARCHAR(500)
vet_on_set         ENUM('not_required','standby','required')
vet_name, vet_contact VARCHAR(500) NULL
awbi_status        ENUM('not_required','exempt','applied','pending','granted','denied')
awbi_number        VARCHAR(100) NULL
awbi_granted_at    DATE NULL
awbi_applied_at    DATE NULL
rest_window_hours  INTEGER NULL
insurance_inr      INTEGER NULL
welfare_notes      TEXT
```

**`day_animals`** — which animals on which day
```
id, day_id, animal_id, scene_id NULL
```

**`picture_vehicles`**
```
id, project_id
name               VARCHAR(500)           -- "Aarav's Motorcycle"
spec               TEXT                   -- "Royal Enfield Classic 350 · 2006 · faded red"
source             ENUM('rental','owned','local_hired','loan')
source_vendor      VARCHAR(500) NULL
driver_name        VARCHAR(500) NULL
driver_contact     VARCHAR(500) NULL
insurance_inr      INTEGER NULL
notes              TEXT
```

**`vehicle_day_uses`**
```
id, vehicle_id, day_id
count              INTEGER DEFAULT 1
UNIQUE (vehicle_id, day_id)
```

**`camera_units`**
```
id, project_id
unit_code          VARCHAR(16)            -- "C1", "L1", "SL", "DR", "JJ", "VFX", etc.
kind               ENUM('camera','lighting','grip','special','drone','steadi','jib')
description        TEXT
rental_vendor      VARCHAR(500) NULL
operator_name      VARCHAR(500) NULL
UNIQUE (project_id, unit_code)
```

**`camera_day_uses`**
```
id, camera_unit_id, day_id
count              INTEGER DEFAULT 1
UNIQUE (camera_unit_id, day_id)
```

**`junior_artist_calls`**
```
id, project_id, day_id
count              INTEGER
grade              ENUM('junior','sr','specialist','dancer','musician')
context            TEXT                   -- "Fishermen community · 60% local"
wardrobe_notes     TEXT
vendor_name        VARCHAR(500) NULL
vendor_contact     VARCHAR(500) NULL
meal_plan_required BOOLEAN DEFAULT FALSE
status             ENUM('planned','briefed','confirmed','on_set')
UNIQUE (day_id, grade)                    -- one row per day × grade
```

**`vfx_shots`**
```
id, project_id, scene_id
shot_number        VARCHAR(32)            -- "001", "004-006"
shot_type          ENUM('sky_grade','crowd_aug','greenscreen','cleanup','drone_replace','muzzle_flash','aging_blend','period_cleanup','rotoscope','other')
complexity         ENUM('low','medium','high','hero')
plates_required    INTEGER DEFAULT 1
description        TEXT
vendor_name        VARCHAR(500) NULL
budget_inr         INTEGER NULL
bid_status         ENUM('estimated','bidded','extended','cancelled')
status             ENUM('planned','plates_delivered','comp_started','review','delivered','final')
markers            JSONB NULL             -- tracking marker specs
notes              TEXT
UNIQUE (project_id, shot_number)
```

**`sfx_effects`** (SFX + stunts share this table; disambiguated by `kind`)
```
id, project_id
scene_id           UUID NULL → scenes(id)
day_id             UUID NULL → days(id)
effect_kind        ENUM('fire','pyro','squibs','rain','wind','breakaway','fog','water','explosion','stunt_fight','stunt_fall','stunt_vehicle','stunt_water','other')
description        TEXT
coordinator        VARCHAR(500)
coordinator_contact VARCHAR(500) NULL
safety_plan_url    TEXT NULL              -- S3 key
permits_required   JSONB                  -- array of permit kinds
insurance_rider    BOOLEAN DEFAULT FALSE
medic_required     BOOLEAN DEFAULT FALSE
stunt_doubles      JSONB NULL             -- [{name, for_character}]
rehearsal_date     DATE NULL
status             ENUM('planned','permit_pending','cleared','rehearsed','executed')
notes              TEXT
```

**`hmu_sessions`** (hair, makeup & prosthetics)
```
id, project_id
character_id       UUID → characters(id)
day_id             UUID → days(id)
look_id            VARCHAR(16)            -- "L01", "L05_aged"
category           ENUM('straight','prosthetic','wound_sfx','de_age','aged','aging','dental','hair_piece')
apply_minutes      INTEGER
remove_minutes     INTEGER
hmu_call_time      TIME NULL
artist_lead        VARCHAR(500) NULL
artist_vendor      VARCHAR(500) NULL
mold_sessions      JSONB                  -- [{date, location, notes}]
continuity_ref     TEXT
notes              TEXT
UNIQUE (character_id, day_id, look_id)
```

**`wardrobe_looks`**
```
id, project_id
character_id       UUID → characters(id)
look_id            VARCHAR(16)            -- "L01", "L02"
description        TEXT
era                ENUM('now','1994','2008','flashback','other')
era_label          VARCHAR(100) NULL      -- for 'other'
scenes_raw         TEXT
multiples_count    INTEGER DEFAULT 1
source             ENUM('in_house','tailored','rental','sourced_flea','govt_spec','purchased')
source_vendor      VARCHAR(500) NULL
return_by          DATE NULL
continuity_key     TEXT
notes              TEXT
UNIQUE (character_id, look_id)
```

**`art_builds`**
```
id, project_id
name               VARCHAR(500)
scenes_raw         TEXT
days_ref           UUID[] NULL            -- array of day ids touched
build_days_lead    INTEGER
art_dir            VARCHAR(500)
status             ENUM('planned','designing','building','ready','struck','returned')
notes              TEXT
```

**`permits`**
```
id, project_id
kind               ENUM('location','road_rto','fire','aerial_dgca','coastal','animal_awbi','closed_set','heritage_asi','police','panchayat','other')
issuing_body       VARCHAR(500)
reference_number   VARCHAR(100) NULL
applied_at         DATE NULL
granted_at         DATE NULL
expires_at         DATE NULL
status             ENUM('not_applied','applied','pending','granted','denied','expired')
fee_inr            INTEGER NULL
related_location_id UUID NULL
related_day_ids    UUID[] NULL
notes              TEXT
```

### 3.3 Cross-cutting

**`call_sheets`**
```
id, project_id, day_id
version            INTEGER                -- monotonic per day
status             ENUM('draft','ready','sent','distributed','stale')
pdf_s3_key         TEXT NULL
generated_at       TIMESTAMPTZ
generated_by       UUID → users(id)
sent_at            TIMESTAMPTZ NULL
sent_to            JSONB NULL             -- [{name, email, phone}]
notes              TEXT
UNIQUE (day_id, version)
INDEX (day_id, version DESC)              -- always want latest
```

**`flags`** — surfaced risks
```
id, project_id
kind               ENUM('cast_hold','permit_lead','weather','drone_block','insurance','continuity','vendor','capacity','missing_data','cost_overrun','safety','custom')
severity           ENUM('info','warning','blocker')
related_scene_id   UUID NULL → scenes(id)
related_day_id     UUID NULL → days(id)
related_character_id UUID NULL
related_resource_ref JSONB NULL           -- {table, id}
title              VARCHAR(500)
description        TEXT
raised_at          TIMESTAMPTZ DEFAULT NOW()
raised_by          ENUM('system','user')
resolved_at        TIMESTAMPTZ NULL
resolved_by        UUID NULL → users(id)
dismissed          BOOLEAN DEFAULT FALSE
INDEX (project_id, severity, resolved_at NULLS FIRST)
```

**`edits`** — append-only audit log
```
id, project_id, user_id, batch_id UUID
entity_table       VARCHAR(64)
entity_id          UUID
field              VARCHAR(64)
old_value          JSONB
new_value          JSONB
created_at         TIMESTAMPTZ DEFAULT NOW()
propagated         BOOLEAN DEFAULT FALSE
INDEX (batch_id)
INDEX (project_id, created_at DESC)
```

**`propagation_previews`**
```
id, project_id, batch_id UNIQUE
user_id            UUID → users(id)
created_at         TIMESTAMPTZ DEFAULT NOW()
diff               JSONB                  -- see §5.3 for shape
status             ENUM('pending','confirmed','discarded','expired')
confirmed_at       TIMESTAMPTZ NULL
expires_at         TIMESTAMPTZ            -- TTL 15 min
```

**`scenarios`** — branches of the shoot plan
```
id, project_id
name               VARCHAR(500)
parent_scenario_id UUID NULL → scenarios(id)
is_live            BOOLEAN DEFAULT FALSE  -- exactly one per project
created_by         UUID → users(id)
created_at         TIMESTAMPTZ
forked_at_batch    UUID NULL              -- edit batch_id at fork point
merged_at          TIMESTAMPTZ NULL
discarded_at       TIMESTAMPTZ NULL
snapshot           JSONB                  -- full graph state at fork time
notes              TEXT
```

Enforce `UNIQUE (project_id) WHERE is_live = TRUE` with a partial index.

**`chat_threads`**
```
id, project_id, user_id
title              VARCHAR(500)           -- auto-generated from first message
created_at, last_active_at
INDEX (project_id, last_active_at DESC)
```

**`chat_messages`**
```
id, thread_id
role               ENUM('user','assistant','tool')
content            TEXT                   -- for user/assistant
tool_calls         JSONB NULL             -- for assistant: [{name, arguments}]
tool_results       JSONB NULL             -- for tool
edits_batch_id     UUID NULL              -- links to edits/propagation_previews
created_at         TIMESTAMPTZ DEFAULT NOW()
INDEX (thread_id, created_at)
```

**`magic_links`**
```
id, email, token UNIQUE
created_at, expires_at
consumed_at        TIMESTAMPTZ NULL
```

---

## 4. Migration from v0.1

`api/alembic/versions/002_v1_schema.py` must do two things in one transaction:

1. Create every new table listed above.
2. Read every row from `projects.parsed_json` and split it into the new tables. Then drop `projects.parsed_json`.

### Migration algorithm (pseudocode)

```python
def upgrade():
    op.create_table(...)  # all new tables
    
    # data migration
    conn = op.get_bind()
    projects = conn.execute("SELECT id, parsed_json FROM projects")
    for proj in projects:
        pj = proj.parsed_json
        
        # 1. Extract locations from unique (location, film_location) pairs across days
        locations_map = {}  # (area, name) → location_id
        for d in pj["days"]:
            if d["is_shoot"]:
                key = (d["location"], d["film_location"])
                if key not in locations_map:
                    loc_id = insert(locations, project_id=proj.id, area=key[0], name=key[1], kind="ext" if "beach" in key[1].lower() else "int")
                    locations_map[key] = loc_id
        
        # 2. Create characters from cast_map
        chars_map = {}  # canonical → character_id
        for canonical, actor in pj["cast_map"].items():
            cid = insert(characters, project_id=proj.id, canonical_name=canonical, display_name=canonical.title(), actor_name=actor, is_principal=True)
            chars_map[canonical] = cid
        
        # 3. Create camera_units from unit_cols
        for code in pj["unit_cols"]:
            insert(camera_units, project_id=proj.id, unit_code=code, kind=_infer_kind(code))
        
        # 4. Create days
        for d in pj["days"]:
            day_id = insert(days, project_id=proj.id, shoot_day_number=d["shoot_day_no"], date=_parse_date(d["date_raw"], proj.start_date), kind="shoot" if d["is_shoot"] else "off", ...)
            
            # 5. For each shoot day, derive scenes from (film_location + notes)
            # v0.1 didn't capture scene-level; synthesize one placeholder scene per day
            # with scene_number = f"D{day_number}-1" so v1 edit flows work
            if d["is_shoot"]:
                scene_id = insert(scenes, project_id=proj.id, scene_number=f"D{d['shoot_day_no']}-1", title=d["film_location"], location_id=locations_map[(d["location"], d["film_location"])], dn="day", ...)
                insert(day_scenes, day_id=day_id, scene_id=scene_id, order_in_day=1)
                
                # link cast
                for char_name in d["cast"]:
                    insert(scene_characters, scene_id=scene_id, character_id=chars_map[char_name.upper()], role="speaking")
                
                # camera day uses
                for code, count in d["units"].items():
                    insert(camera_day_uses, camera_unit_id=_lookup_unit(code, proj.id), day_id=day_id, count=int(count))
                
                # junior artist call
                if d["units"].get("JR"):
                    insert(junior_artist_calls, day_id=day_id, count=int(d["units"]["JR"]), grade="junior")
                
                # picture vehicles
                for pv_name in d["picture_vehicles"]:
                    vid = _get_or_create_vehicle(proj.id, pv_name)
                    insert(vehicle_day_uses, vehicle_id=vid, day_id=day_id)
        
        # 6. Create a default live scenario
        live_id = insert(scenarios, project_id=proj.id, name="Live plan", is_live=True, created_by=proj.owner_id)
        conn.execute("UPDATE projects SET live_scenario_id=%s WHERE id=%s", (live_id, proj.id))
    
    # 7. drop parsed_json
    op.drop_column("projects", "parsed_json")
```

**Note to implementer:** scene-level data doesn't exist in v0.1 uploads (Katakirr xlsx only has day granularity). The migration synthesizes one placeholder scene per day so the v1 model validates. Real scene data arrives via two paths: (a) a scene breakdown sheet in the uploaded xlsx (parser already supports this — see `parser.py` scene_sheet handling), (b) manual scene edits in the UI post-upload.

---

## 5. API surface

All routes live under `api/app/routes/`. All responses are JSON unless otherwise noted. All mutations that touch the project graph go through the edit → preview → commit flow (§5.3).

### 5.1 Projects

| Method | Path | Notes |
|---|---|---|
| `GET`    | `/projects`                        | list |
| `POST`   | `/projects`                        | multipart upload of .xlsx; creates project + runs migration-style fill |
| `GET`    | `/projects/{id}`                   | full project header |
| `PATCH`  | `/projects/{id}`                   | update title, window, settings |
| `DELETE` | `/projects/{id}`                   | soft-delete (status=archived) |

### 5.2 Days

| Method | Path | Notes |
|---|---|---|
| `GET`    | `/projects/{id}/days`                            | list, ordered by date |
| `GET`    | `/projects/{id}/days/{day_id}`                   | full day detail (all scenes, resources) |
| `PATCH`  | `/projects/{id}/days/{day_id}`                   | goes through edit flow: kind, shift, banner_text, location |

### 5.3 Edit → preview → commit

The central pattern. No mutation is applied directly. All go through:

```
POST /projects/{id}/edits                  → creates edits[] with a batch_id, returns batch_id + preview_id
POST /projects/{id}/edits/{batch}/preview  → returns full diff (see below)
POST /projects/{id}/edits/{batch}/commit   → applies the batch transactionally, enqueues regenerations
POST /projects/{id}/edits/{batch}/discard  → rolls back (no effect — edits never committed)
```

**Edit request body shape:**
```json
{
  "edits": [
    { "op": "patch", "entity": "scenes",       "id": "...", "fields": { "dn": "night" } },
    { "op": "patch", "entity": "day_scenes",   "id": "...", "fields": { "day_id": "...", "order_in_day": 2 } },
    { "op": "create","entity": "junior_artist_calls", "fields": { "day_id": "...", "count": 48, "grade": "junior" } },
    { "op": "delete","entity": "scene_props",  "id": "..." }
  ]
}
```

**Propagation preview response shape:**
```json
{
  "batch_id": "uuid",
  "diff": {
    "views_affected": ["main_schedule","cast_dood","junior_artists","call_sheets"],
    "impacts": [
      {
        "view": "cast_dood",
        "rows_changed": 1,
        "detail": "Vasudev becomes W on Day 3 (was ·). W-count 9 → 10."
      },
      {
        "view": "call_sheets",
        "rows_changed": 2,
        "detail": "Day 3 v4 regenerated (v3 was already sent — re-send prompt will appear). Day 8 v2."
      }
    ],
    "side_effects": [
      { "kind": "re_email", "target": "Mumbai Crowd Co.", "reason": "JR count Day 3: 40 → 48" },
      { "kind": "flag_raised", "flag_id": "...", "title": "Day 10 drone permit deadline 4 days" }
    ],
    "breaks": []                      // hard blockers that prevent commit
  },
  "expires_at": "...+15min"
}
```

If `breaks[]` is non-empty, the commit endpoint returns 409.

### 5.4 Scenes

| Method | Path | Notes |
|---|---|---|
| `GET`    | `/projects/{id}/scenes`                          | all scenes |
| `GET`    | `/projects/{id}/scenes/{scene_id}`               | full scene detail |
| `POST`   | `/projects/{id}/scenes/{scene_id}/reschedule`    | shortcut that wraps edit-flow: `body: { to_day_id, order_in_day }`, returns preview |

### 5.5 Resources (one endpoint set per kind)

Template: for each kind in `[props, animals, vehicles, cameras, junior_artists, vfx, sfx, hmu, wardrobe, art, permits]`:

| Method | Path |
|---|---|
| `GET`    | `/projects/{id}/resources/{kind}`       |
| `GET`    | `/projects/{id}/resources/{kind}/{rid}` |
| `POST`   | `/projects/{id}/resources/{kind}`       (via edit-flow) |
| `PATCH`  | `/projects/{id}/resources/{kind}/{rid}` (via edit-flow) |
| `DELETE` | `/projects/{id}/resources/{kind}/{rid}` (via edit-flow) |

### 5.6 Views (read-only, computed)

Views are JSON payloads shaped for the frontend. They're cached on `view_cache` table (not modeled above — a simple `project_id, view_name, scenario_id, payload jsonb, computed_at`). Invalidated on any mutation that touches a dependency.

| Method | Path |
|---|---|
| `GET` | `/projects/{id}/views/main_schedule` |
| `GET` | `/projects/{id}/views/calendar?month=2026-04` |
| `GET` | `/projects/{id}/views/scenes_matrix` |
| `GET` | `/projects/{id}/views/cast_dood` |
| `GET` | `/projects/{id}/views/vehicles` |
| `GET` | `/projects/{id}/views/cameras` |
| `GET` | `/projects/{id}/views/junior_artists` |
| `GET` | `/projects/{id}/views/props` |
| `GET` | `/projects/{id}/views/animals` |
| `GET` | `/projects/{id}/views/vfx` |
| `GET` | `/projects/{id}/views/sfx_stunts` |
| `GET` | `/projects/{id}/views/hmu` |
| `GET` | `/projects/{id}/views/wardrobe` |
| `GET` | `/projects/{id}/views/requirements` |
| `GET` | `/projects/{id}/views/day/{day_id}` — the drill-in page |

All views accept `?scenario_id=...` to view a fork.

### 5.7 Exports

| Method | Path | Returns |
|---|---|---|
| `GET` | `/projects/{id}/export/{view}.xlsx`           | streaming xlsx |
| `POST`| `/projects/{id}/export/bundle`                | 202 + job_id; produces zip asynchronously |
| `GET` | `/projects/{id}/export/jobs/{job_id}`         | status + download URL when ready |

### 5.8 Call sheets

| Method | Path | Notes |
|---|---|---|
| `GET`  | `/projects/{id}/callsheets`                          | list, latest version per day |
| `POST` | `/projects/{id}/callsheets/{day_id}/regenerate`      | enqueues job, returns job_id + new version number |
| `GET`  | `/projects/{id}/callsheets/{day_id}/v{version}.pdf`  | redirect to S3 signed URL |
| `POST` | `/projects/{id}/callsheets/{day_id}/send`            | body: `{ to: [{email, name}], include_pdf: true }` |

### 5.9 Scenarios

| Method | Path | Notes |
|---|---|---|
| `GET`    | `/projects/{id}/scenarios`                     | list |
| `POST`   | `/projects/{id}/scenarios`                     | fork from live: `{ name, based_on_scenario_id? }` — defaults to live |
| `GET`    | `/projects/{id}/scenarios/{sid}/diff`          | diff vs live |
| `POST`   | `/projects/{id}/scenarios/{sid}/merge`         | merge into live (uses preview/commit on the way) |
| `DELETE` | `/projects/{id}/scenarios/{sid}`               | discard fork |

### 5.10 Chat

| Method | Path | Notes |
|---|---|---|
| `GET`  | `/projects/{id}/chat/threads`                                 | list |
| `POST` | `/projects/{id}/chat/threads`                                 | create empty thread |
| `GET`  | `/projects/{id}/chat/threads/{tid}/messages`                  | full history |
| `POST` | `/projects/{id}/chat/threads/{tid}/messages`                  | SSE stream; request: `{ content }` |

Chat message SSE events:
- `assistant_delta` — streaming text chunk
- `tool_call` — `{name, arguments}` (for UI to show "checking the graph...")
- `tool_result` — `{name, result}`
- `preview_ready` — `{batch_id}` (shown as an actionable card in the UI)
- `done` — stream end

### 5.11 Real-time events

| Method | Path | Notes |
|---|---|---|
| `GET` | `/projects/{id}/events` (SSE) | subscribes to `project:{id}:events` on Redis |

Event kinds: `scene_rescheduled`, `day_updated`, `flag_raised`, `flag_resolved`, `call_sheet_regenerated`, `call_sheet_sent`, `scenario_forked`, `scenario_merged`, `chat_message`.

### 5.12 Auth

| Method | Path | Notes |
|---|---|---|
| `POST` | `/auth/request_link` | body: `{ email }` — sends magic link |
| `GET`  | `/auth/verify?token=...` | consumes token, sets session cookie |
| `POST` | `/auth/signout` | clears cookie |
| `GET`  | `/auth/me` | current user |

Dev mode (`DEV_AUTO_LOGIN_EMAIL` set) bypasses this — `current_user` returns the auto-login user on every request.

---

## 6. Core services

New directory: `api/app/services/`. Each service is an importable class with a thin FastAPI-aware wrapper.

### 6.1 `ProjectGraph`

In-memory read model of the project. Built lazily per request (cached per project+scenario). Not persisted. Exposes:

```python
class ProjectGraph:
    def __init__(self, project_id: UUID, scenario_id: UUID | None = None): ...
    
    async def load(self, session: AsyncSession) -> None: ...
    
    # Queries
    def day_by_number(self, n: int) -> Day: ...
    def day_by_date(self, d: date) -> Day: ...
    def scenes_on_day(self, day_id: UUID) -> list[Scene]: ...
    def days_with_character(self, char_id: UUID) -> list[Day]: ...
    def days_with_resource(self, kind: str, rid: UUID) -> list[Day]: ...
    def character_statuses(self, char_id: UUID) -> dict[int, Literal["W","H","T","."]]: ...
    
    # Mutations (not persisted — used to compute propagation)
    def apply_virtual(self, edits: list[Edit]) -> ProjectGraph: ...   # returns a clone with edits layered on
```

### 6.2 `PropagationEngine`

```python
class PropagationEngine:
    def __init__(self, before: ProjectGraph, after: ProjectGraph): ...
    
    def compute_diff(self) -> PropagationDiff:
        """
        Compare before vs after. Return the diff shape documented in §5.3.
        Responsibilities:
          1. Identify which views are now stale (list of view names)
          2. For each affected entity, describe human-readable change
          3. Surface side_effects (re-emails, flag triggers, cost deltas)
          4. Identify hard breaks (cast double-booking across locations, permit not granted, etc.)
        """
```

Algorithm (high-level):
1. For each edit, mark dependent views as stale using a static DAG:
   - `scenes.dn` → [main_schedule, scenes_matrix, calendar, requirements, callsheet_day]
   - `day_scenes.day_id` → [main_schedule, calendar, scenes_matrix, call_sheet_source_day, call_sheet_target_day, cast_dood (if cast changes with day), requirements for both days]
   - `junior_artist_calls.count` → [junior_artists view, requirements, callsheet_day, vendor_re_email]
   - (see full table in `services/propagation_dag.py`)
2. For breaks: check cast availability (same character on two scenes that can't both happen), permit lead times (e.g., AWBI horse permit on Day 10 but applied < 14 days prior), weather (Day 3 scheduled outdoor festival but IMD alert).
3. For side effects: re-email vendors whose brief changes, raise flags on newly risky configurations.

### 6.3 `ViewRegenerator`

```python
class ViewRegenerator:
    @staticmethod
    async def render(view_name: str, project_id: UUID, scenario_id: UUID | None, session: AsyncSession) -> dict:
        """Returns the JSON payload for the given view. Called by worker after commit, cached in view_cache."""
```

14 view render methods, one per view name. Each is pure — takes graph, returns JSON.

### 6.4 `CallSheetGenerator`

```python
class CallSheetGenerator:
    @staticmethod
    async def render(day_id: UUID, project_id: UUID, session: AsyncSession) -> bytes:
        """
        Builds a call sheet PDF:
        1. Fetch day + all scenes + all resources for the day
        2. Render the HTML template (templates/callsheet.html — copied from design/project/callsheet-1.html and parameterized with Jinja2)
        3. Pipe through WeasyPrint → PDF bytes
        4. Returns bytes; caller persists to S3 and bumps call_sheets.version
        """
```

### 6.5 `XlsxExporter`

Reuse and extend `api/app/cue_engine/reports/` from v0.1. Add one file per view:
- `reports/main_schedule.py` (exists)
- `reports/cast_dood.py`
- `reports/vehicles.py`
- `reports/cameras.py`
- `reports/props.py`
- ... etc for all 14 views.

Each exports `generate(project: ProjectGraph, out_path: str)`. Worker job `export_bundle` runs all 14 + zips.

### 6.6 `ChatAgent`

```python
class ChatAgent:
    def __init__(self, project_id: UUID, user_id: UUID, anthropic_client: Anthropic): ...
    
    async def stream(self, thread_id: UUID, user_message: str) -> AsyncIterator[ChatEvent]:
        """
        Streams assistant response. Uses Anthropic messages API with tools.
        Tool definitions in tools.py.
        After each assistant turn, either:
          - Plain response (no edits) → just text
          - Edit proposal → creates edits + preview in DB, emits preview_ready event with batch_id
        """
```

**Tool schema** (`api/app/services/chat_tools.py`):

```python
TOOLS = [
    {
        "name": "get_project_overview",
        "description": "Summary of the project: title, window, shoot days, cast, open flags, what's tomorrow.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_day",
        "description": "Full detail of one shoot day — scenes, cast, resources, notes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Day number (e.g. '3') or ISO date (e.g. '2026-04-12')"},
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "find_scenes",
        "description": "Search scenes by cast, location, element, or text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "filters": {
                    "type": "object",
                    "properties": {
                        "character": {"type": "string"},
                        "location_name": {"type": "string"},
                        "has_vfx": {"type": "boolean"},
                        "dn": {"enum": ["day","night","day_int","night_int","dusk"]},
                    },
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_character_availability",
        "description": "For one character, return W/H/T/· status across all shoot days.",
        "input_schema": {"type": "object", "properties": {"character": {"type": "string"}}, "required": ["character"]},
    },
    {
        "name": "propose_reschedule",
        "description": "Simulate moving a scene from one day to another. Returns propagation preview. Does not commit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "scene_number": {"type": "string"},
                "to_day_identifier": {"type": "string"},
            },
            "required": ["scene_number", "to_day_identifier"],
        },
    },
    {
        "name": "propose_swap_days",
        "description": "Simulate swapping the entire content of two shoot days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "day_a": {"type": "string"},
                "day_b": {"type": "string"},
            },
            "required": ["day_a", "day_b"],
        },
    },
    {
        "name": "get_flags",
        "description": "List open flags, optionally filtered by severity.",
        "input_schema": {"type": "object", "properties": {"severity": {"enum": ["info","warning","blocker"]}}},
    },
    {
        "name": "commit_preview",
        "description": "Commit a previously-proposed preview batch. ONLY call this after the user has explicitly confirmed.",
        "input_schema": {"type": "object", "properties": {"batch_id": {"type": "string"}}, "required": ["batch_id"]},
    },
]
```

**System prompt** (lives in `services/chat_prompts.py`, loaded at thread init):

> You are Cue, the production office assistant for a Marathi feature currently in pre-production. You know the project graph intimately — every day, scene, cast member, resource, and flag.
>
> You never commit changes without the user's explicit confirmation. When they propose or ask about a change, use `propose_*` tools to compute the impact and return a preview. The user must say "confirm" or equivalent before you call `commit_preview`.
>
> Speak like a first AD: brief, calm, numbers-aware. Dates in Indian format (10 April, not April 10). Page counts in eighths ("4 2/8"). Never invent data — if you don't know, say so and suggest a tool call.
>
> The user is the producer. Treat them as the decision-maker; your job is to surface options and consequences, not to drive.

### 6.7 `FlagDetector`

Runs after every commit. A set of rules, each implemented as a function `detect_X(graph: ProjectGraph) -> list[Flag]`:

- `detect_cast_holds` — a contracted hold date overlaps a work day
- `detect_permit_leads` — permit not granted within its required lead time
- `detect_weather_conflicts` — weather forecast vs outdoor scheduling (requires weather integration — stub for v1)
- `detect_drone_nofly` — `dn=day` + drone unit + location within known no-fly zones (DGCA database — use a static JSON for v1)
- `detect_cost_overruns` — VFX bid_status=extended or call-sheet regenerations beyond a threshold
- `detect_missing_data` — shoot days without scenes, scenes without cast, etc.

---

## 7. Background jobs (Arq worker)

`api/app/worker.py` — Arq worker settings + task defs.

```python
@arq.task
async def regenerate_view(ctx, project_id, view_name, scenario_id=None):
    ...

@arq.task
async def regenerate_call_sheet(ctx, project_id, day_id):
    # produces PDF, uploads to S3, bumps call_sheets.version, marks previous version as stale
    ...

@arq.task
async def send_call_sheet(ctx, project_id, day_id, recipients, include_pdf):
    # uses Resend API
    ...

@arq.task
async def export_bundle(ctx, project_id, scenario_id=None):
    # generates all xlsx views, zips, uploads to S3, updates export_job row
    ...

@arq.task
async def propagation_compute(ctx, project_id, batch_id):
    # runs PropagationEngine for large batches off-thread; updates propagation_previews.diff
    ...

@arq.task
async def run_flag_detector(ctx, project_id, scenario_id):
    ...
```

After every successful commit, the API enqueues `regenerate_view` for each affected view + `regenerate_call_sheet` for each affected day + `run_flag_detector`.

---

## 8. Real-time (SSE)

`api/app/sse.py`:
- FastAPI SSE endpoint subscribes to Redis pub/sub channel `project:{id}:events`
- Any mutation (commit, call-sheet send, flag raise) `PUBLISH`es to the channel
- Connected clients receive `data: {...json...}\n\n` frames

Events schema in `api/app/events.py` — TypedDicts shared with frontend types.

---

## 9. Auth

`api/app/auth.py` (replace v0.1 implementation):

- `POST /auth/request_link` — generates signed token (itsdangerous) containing email+exp, stores in `magic_links`, POSTs to Resend with link `https://cue.app/auth/verify?token=...`
- `GET /auth/verify` — validates token, consumes `magic_links` row, issues signed cookie `cue_session=<signed(user_id)>`
- `current_user` dependency — reads cookie. If `DEV_AUTO_LOGIN_EMAIL` set, bypass and always return that user.
- No passwords, no OAuth, no 2FA in v1.

---

## 10. Storage

`api/app/storage.py` — thin boto3 wrapper.

Keys:
- `call_sheets/{project_id}/{day_id}/v{version}.pdf`
- `exports/{project_id}/{job_id}.zip`
- `exports/{project_id}/{view}-{ts}.xlsx`
- `uploads/{project_id}/master_{ts}.xlsx` (original)

All downloads via pre-signed URL (15 min TTL).

---

## 11. docker-compose.yml (extend v0.1)

Add:
```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  
  storage:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes: ["minio-data:/data"]
    ports: ["9000:9000", "9001:9001"]
  
  worker:
    build: ./api
    command: arq app.worker.WorkerSettings
    volumes: ["./api:/app"]
    depends_on: [db, redis]
    env_file: [.env]

volumes:
  minio-data:
```

---

## 12. Testing

- `api/tests/unit/` — service-level (PropagationEngine, ViewRegenerator) with fixtures
- `api/tests/integration/` — endpoint tests against testcontainers-postgres
- `api/tests/snapshot/` — view payload snapshots against the Ratnagiri sample
- Fixtures: load the Ratnagiri xlsx once per session

Run: `pytest` (async via `pytest-asyncio`).

Target coverage for v1: service layer >80%, routes >60%, overall >70%.

---

## 13. Build order (6 weeks)

### Week 1 — data model + migration
- Write Alembic migration 002 (all new tables)
- Write data-move migration 003 (read parsed_json, fan out)
- New SQLAlchemy 2.0 async models + repositories
- Drop parsed_json
- Integration test: migrate v0.1 Ratnagiri project, verify all v0.1 routes still return identical payloads

### Week 2 — edit/preview/commit + propagation + 4 core views
- Edit DSL (`edits[]` request parsing)
- `PropagationEngine` with static DAG for the most common edits
- `ViewRegenerator` for main_schedule, calendar, scenes_matrix, cast_dood
- `view_cache` table + invalidation
- Reschedule shortcut endpoint
- Snapshot tests for the 4 views

### Week 3 — call sheets + exports + worker
- Arq worker set up
- CallSheetGenerator (HTML template + WeasyPrint)
- XlsxExporter for all 14 views
- Export bundle job
- Storage (MinIO + boto3)

### Week 4 — chat agent + SSE
- Anthropic SDK integration
- Tool definitions (get_project_overview, get_day, find_scenes, propose_reschedule, propose_swap_days, get_character_availability, get_flags, commit_preview)
- Chat threads + messages tables + endpoints
- SSE stream for both chat and project events
- Redis pub/sub wiring

### Week 5 — scenarios + flags + auth
- Scenarios (fork, diff, merge)
- FlagDetector with the seven rules
- Magic-link auth via Resend (plus dev-auto-login preserved)

### Week 6 — polish + prod deploy docs
- Remaining 10 resource view endpoints + CRUD edit operations
- Comprehensive integration tests
- Production deployment guide (Fly.io or Railway — one target)
- README updates

---

## 14. Directory layout after v1

```
cue-platform/api/
  Dockerfile
  requirements.txt
  alembic.ini
  alembic/
    versions/
      001_initial.py               (v0.1, inherited)
      002_v1_schema.py             (new tables)
      003_v1_data_migration.py     (parsed_json → rows)
  app/
    main.py                        (FastAPI app)
    config.py                      (settings)
    db.py                          (async engine + session)
    models/                        (NEW — broken from one models.py into package)
      __init__.py
      core.py                      (users, projects, locations)
      characters.py
      schedule.py                  (days, scenes, day_scenes, scene_characters)
      resources/                   (one file per kind)
        props.py
        animals.py
        vehicles.py
        cameras.py
        juniors.py
        vfx.py
        sfx.py
        hmu.py
        wardrobe.py
        art.py
        permits.py
      cross_cutting.py             (flags, edits, propagation_previews, scenarios)
      chat.py                      (threads, messages)
      auth.py                      (magic_links)
    schemas/                       (Pydantic response models — one per view)
    services/
      project_graph.py
      propagation_engine.py
      propagation_dag.py
      view_regenerator.py
      views/                       (one render() per view)
      call_sheet_generator.py
      xlsx_exporter.py
      flag_detector.py
      flag_rules/                  (one file per rule)
      chat_agent.py
      chat_tools.py
      chat_prompts.py
      storage.py
      auth.py
      sse.py
      events.py
    routes/
      projects.py                  (replace v0.1 — thinner, delegates to services)
      days.py
      scenes.py
      resources.py                 (parameterized router for all 12 kinds)
      views.py
      edits.py
      exports.py
      callsheets.py
      scenarios.py
      chat.py
      auth.py
      events.py
    templates/
      callsheet.html               (jinja — from design/project/callsheet-1.html)
    cue_engine/                    (v0.1 parser — keep as-is)
      parser.py
      styles.py
      reports/
    worker.py                      (arq task defs + settings)
  tests/
    conftest.py                    (fixtures: db, client, sample project)
    unit/
    integration/
    snapshot/
    fixtures/
      ratnagiri_master.xlsx        (copy of cue-v2/sample_master_breakdown.xlsx)
```

---

## 15. Things to watch out for

1. **Async everywhere.** v0.1 uses sync psycopg2. v1 uses asyncpg + async SQLAlchemy + async FastAPI. Don't mix — if you import a sync session anywhere, it'll block the event loop.

2. **The propagation DAG is the hard part.** Take extra care with it. Missing an edge means a stale view. Getting it wrong means over-invalidating (which is slow but correct). Better to over-invalidate in v1 than risk staleness.

3. **`scenarios.is_live` uniqueness.** Enforce at DB level with `CREATE UNIQUE INDEX ... WHERE is_live = TRUE`. A project with two live scenarios would be chaos.

4. **Preview TTL.** 15 minutes. If the user sits on a preview too long and the underlying state changes (real-time event from another client), the commit endpoint must re-check diff and either pass-through or raise 409.

5. **Chat tool-use loop.** Use Anthropic's tool-use with streaming. Assistant calls a tool, we execute it server-side, pass result back, assistant continues. When assistant calls `propose_*`, we create a propagation_preview row and emit `preview_ready` event. We do NOT auto-commit; only `commit_preview` (invoked by a user confirmation in the UI) persists.

6. **v0.1 routes stay alive during migration.** Week 1 must keep v0.1's endpoints working unchanged. Frontend isn't switched to v1 routes until Week 2 views land.

7. **Dev-auto-login bypass.** Easy to forget to disable in prod. Add a startup check that logs a big warning if `ENV=production` and `DEV_AUTO_LOGIN_EMAIL` is set.

8. **Call sheet versions are immutable.** Once generated, never overwrite. New version number. Old PDFs stay in S3 for audit — the UI may show a "v3 was sent to Rohit 18:20" next to v4's regen notice.

---

## 16. Success criteria for v1 shipping

- A user uploads the Ratnagiri xlsx and sees the chat home populated with real data
- They ask "what's tomorrow?" and get a structured answer with mini-cards
- They drag SC 14 from Day 1 to Day 2 in the calendar → see the propagation preview → confirm → watch the main schedule, cast DOOD, and 2 call sheets update via SSE
- They fork into "Priya cancel replan", swap Day 1 ⇄ Day 6, diff against live, merge
- They click Download bundle → get a zip with all 14 xlsx views + 22 call sheet PDFs
- They sign out, request a magic link, sign back in on a different device, and pick up where they left off

If all six work end-to-end, v1 is done.

---

## 17. Anything not covered here

If Claude Code (or any implementer) hits something not specified, decisions default to these principles:

1. **Prefer explicit over magical.** Don't invent implicit relationships.
2. **Prefer re-rendering a whole view over incremental patches.** Correctness > speed for v1.
3. **Append-only audit.** `edits` is the source of truth for history. Never delete.
4. **Return useful errors.** 422s must explain which field and why.
5. **Dates in IST (`Asia/Kolkata`) by default.** Store as `TIMESTAMPTZ`. Serialize with the project's configured timezone.

---

*End of spec. Build in order. Ask the spec first. When in doubt, match the design in `cue-platform/design/`.*
