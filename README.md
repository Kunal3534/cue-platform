# Cue — Film Production Scheduling Platform (v1)

Cue is a web-based production scheduling platform for Indian feature films. It ingests a Katakirr-style master breakdown spreadsheet and provides a real-time, collaborative schedule with AI-powered rescheduling, automated flag detection, PDF call sheets, and 14 exportable Excel views.

---

## Architecture

The platform is a three-tier system built entirely in Python and React:

**API** (FastAPI + PostgreSQL + Redis + MinIO) — async REST endpoints backed by SQLAlchemy 2.0 models, Alembic migrations, and an Arq background worker. The worker handles PDF generation (WeasyPrint), Excel exports (openpyxl), and flag detection. Server-sent events stream schedule changes and chat deltas to connected clients via Redis pub/sub.

**Chat agent** (Anthropic SDK) — a streaming tool-use loop that understands the schedule graph and can propose reschedules, surface flags, and commit previews — all within the same SSE stream as the edit flow.

**Frontend** (Next.js 14 + Tailwind) — built in Week 6+; the API is fully functional without it.

---

## Local dev

Prerequisites: Docker Desktop (or any Compose-compatible runtime).

```bash
cp .env.example .env          # edit DEV_AUTO_LOGIN_EMAIL, ANTHROPIC_API_KEY
docker compose up --build
```

Services after boot:

| Service | URL |
|---|---|
| API + Swagger docs | http://localhost:8000 / http://localhost:8000/docs |
| MinIO console | http://localhost:9001 (minioadmin / minioadmin) |
| Redis | localhost:6379 |

Upload the sample breakdown to seed the database:

```bash
curl -X POST http://localhost:8000/projects \
  -F "file=@api/tests/fixtures/ratnagiri_master.xlsx"
```

---

## Environment variables

| Variable | Dev default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://cue:cue@db:5432/cue` | Async Postgres URL |
| `SECRET_KEY` | `dev-change-me` | itsdangerous signing key |
| `REDIS_URL` | `redis://redis:6379/0` | Arq + SSE pub/sub |
| `S3_ENDPOINT` | `http://storage:9000` | MinIO (local) or Tigris (prod) |
| `S3_BUCKET` | `cue-v1` | Object store bucket |
| `S3_ACCESS_KEY` | `minioadmin` | |
| `S3_SECRET_KEY` | `minioadmin` | |
| `ANTHROPIC_API_KEY` | *(none)* | Required for chat agent |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Model used by chat agent |
| `RESEND_API_KEY` | *(none)* | Required for magic-link email in prod |
| `MAIL_FROM` | *(none)* | Verified sender address |
| `DEV_AUTO_LOGIN_EMAIL` | *(none)* | Set in dev to skip magic-link auth |
| `ENV` | `development` | Set to `production` in prod |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | CORS allow-origin + redirect |

---

## Running tests

Tests require a live Postgres instance. With `docker compose up db` running:

```bash
# From api/
pip install pytest pytest-asyncio httpx

# View snapshot tests
DATABASE_URL=postgresql+psycopg2://cue:cue@localhost:5432/cue \
  pytest tests/integration/test_view_snapshots.py -v

# Migration + ingest tests
DATABASE_URL=postgresql+psycopg2://cue:cue@localhost:5432/cue \
  pytest tests/integration/test_v1_migration.py -v

# Chat agent tool-call tests (mocked Anthropic)
DATABASE_URL=postgresql+psycopg2://cue:cue@localhost:5432/cue \
  pytest tests/integration/test_chat.py -v -s

# Week 6 comprehensive suite (all 6 scenarios)
DATABASE_URL=postgresql+psycopg2://cue:cue@localhost:5432/cue \
  pytest tests/integration/test_week6.py -v -s
```

Each test file wipes and re-migrates the database, so run files individually or point them at separate databases.

---

## Key files to read first

| File | What it does |
|---|---|
| [api/app/main.py](api/app/main.py) | FastAPI app, router wiring, startup warning |
| [api/app/services/project_graph.py](api/app/services/project_graph.py) | In-memory project snapshot used by all renderers, reports, and the flag detector |
| [api/app/services/propagation_engine.py](api/app/services/propagation_engine.py) | Preview → conflict-check → commit flow; called by edits route and chat agent |
| [api/app/services/chat_agent.py](api/app/services/chat_agent.py) | Anthropic streaming loop with tool-use; 8 tools in `chat_tools.py` |
| [api/app/services/flag_detector.py](api/app/services/flag_detector.py) | Orchestrates 7 flag-rule modules; upserts flags; publishes SSE |
| [api/app/worker.py](api/app/worker.py) | Arq worker: view regen, call sheet PDF, export bundle, flag detector |
| [api/app/routes/edits.py](api/app/routes/edits.py) | Edit DSL — preview + commit endpoints; enqueues worker tasks |
| [api/app/routes/scenarios.py](api/app/routes/scenarios.py) | Scenario fork / diff / merge / delete |
| [api/app/routes/auth.py](api/app/routes/auth.py) | Magic-link sign-in via Resend + itsdangerous cookies |
| [api/alembic/versions/](api/alembic/versions/) | Three migrations: 001 core schema, 002 v1 tables, 003 data fanout |

---

## 6-week build log

- **Week 1** — Core schema (Alembic migrations 001–002), async SQLAlchemy models, parser service, project CRUD, v0.1 main-schedule view
- **Week 2** — Edit DSL (preview/commit/propagation), 4 view renderers (main_schedule, calendar, scenes_matrix, cast_dood), snapshot tests
- **Week 3** — CallSheetGenerator (Jinja2 + WeasyPrint + S3), 14 xlsx report modules, Arq worker (4 tasks), MinIO storage, callsheets + exports routes, docker-compose additions
- **Week 4** — Chat agent (Anthropic SDK streaming, 8 tools), project-level SSE via Redis pub/sub, commit hook publishes events, integration tests with mocked Anthropic
- **Week 5** — Scenarios (fork/diff/merge/delete), FlagDetector (7 rules: cast_holds, permit_leads, weather, drone_nofly, cost_overruns, missing_data, continuity), magic-link auth (Resend + itsdangerous), startup ENV safety warning
- **Week 6** — Remaining 6 resource CRUD kinds (vfx_shots, sfx_effects, hmu_sessions, wardrobe_looks, art_builds, permits), parameterised resources router, comprehensive integration test suite (6 scenarios), production deploy guide (Fly.io), this README

---

## Further reading

- [SPEC_v1.md](SPEC_v1.md) — full feature specification with data model, API contract, and view schemas
- [design/](design/) — wireframes and design tokens
- [DEPLOY.md](DEPLOY.md) — Fly.io production deployment guide

---

## License

Proprietary. Kunal Panjwani · April 2026.
