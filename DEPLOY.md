# Cue v1 — Production Deployment Guide (Fly.io)

Fly.io is the chosen target: single `fly deploy` command, native Postgres and Redis add-ons, built-in secrets manager, and free S3-compatible object store via Tigris.

---

## Prerequisites

```bash
brew install flyctl
fly auth login
```

---

## 1. One-command deploy

```bash
# From the repo root — first time only
fly launch --name cue-api --region bom --dockerfile api/Dockerfile \
           --no-deploy

# Set all secrets (see §3 below), then:
fly deploy --config fly.toml
```

`fly.toml` (place at repo root):

```toml
app = "cue-api"
primary_region = "bom"           # Mumbai — closest to Ratnagiri production

[build]
  dockerfile = "api/Dockerfile"
  build-target = "production"

[env]
  ENV              = "production"
  FRONTEND_ORIGIN  = "https://cue.app"          # swap for your domain
  S3_REGION        = "auto"                      # Tigris uses "auto"
  ANTHROPIC_MODEL  = "claude-sonnet-4-6"

[[services]]
  internal_port = 8000
  protocol      = "tcp"

  [[services.ports]]
    port     = 80
    handlers = ["http"]

  [[services.ports]]
    port     = 443
    handlers = ["tls", "http"]

  [services.concurrency]
    type       = "requests"
    hard_limit = 100
    soft_limit = 80

[[services]]
  # Arq worker — same image, different command
  internal_port = 0
  protocol      = "tcp"
  [services.processes]
    worker = "python -m app.worker"

[processes]
  app    = "uvicorn app.main:app --host 0.0.0.0 --port 8000"
  worker = "python -m app.worker"
```

---

## 2. Environment variable list

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✓ | `postgresql+asyncpg://user:pass@host:5432/cue` |
| `SECRET_KEY` | ✓ | Random 32+ char string for itsdangerous cookie signing |
| `REDIS_URL` | ✓ | `redis://default:pass@host:6379` |
| `S3_ENDPOINT` | ✓ | Tigris: `https://fly.storage.tigris.dev` |
| `S3_BUCKET` | ✓ | Bucket name, e.g. `cue-v1-prod` |
| `S3_ACCESS_KEY` | ✓ | Tigris access key ID |
| `S3_SECRET_KEY` | ✓ | Tigris secret access key |
| `S3_REGION` | ✓ | `auto` for Tigris |
| `ANTHROPIC_API_KEY` | ✓ | From console.anthropic.com |
| `RESEND_API_KEY` | ✓ | From resend.com dashboard |
| `MAIL_FROM` | ✓ | Verified sender, e.g. `noreply@cue.app` |
| `FRONTEND_ORIGIN` | ✓ | Web app URL for CORS + redirect after verify |
| `ENV` | ✓ | `production` |
| `ANTHROPIC_MODEL` | — | Default `claude-sonnet-4-6` |
| `MAGIC_LINK_TTL_SECONDS` | — | Default `900` (15 min) |
| `DEV_AUTO_LOGIN_EMAIL` | ✗ | **Never set in production** |

---

## 3. Provisioning Postgres, Redis, and object store

### Postgres (Fly Postgres)
```bash
fly postgres create --name cue-db --region bom --initial-cluster-size 1
fly postgres attach cue-db --app cue-api
# Fly auto-sets DATABASE_URL; replace +psycopg2 driver with +asyncpg:
fly secrets set DATABASE_URL="postgresql+asyncpg://..."
```

Run migrations after first deploy:
```bash
fly ssh console -a cue-api --command "alembic upgrade head"
```

### Redis (Upstash via Fly)
```bash
fly redis create --name cue-redis --region bom --plan free-200m
fly redis attach cue-redis --app cue-api
# Fly sets REDIS_URL automatically
```

### Object store (Tigris)
```bash
fly storage create --name cue-storage
# Fly prints BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_ENDPOINT_URL_S3
fly secrets set \
  S3_BUCKET="cue-v1-prod" \
  S3_ENDPOINT="https://fly.storage.tigris.dev" \
  S3_ACCESS_KEY="<AWS_ACCESS_KEY_ID>" \
  S3_SECRET_KEY="<AWS_SECRET_ACCESS_KEY>"
```

---

## 4. Secrets management

All secrets are stored in Fly's encrypted secrets store (not in fly.toml or version control):

```bash
fly secrets set \
  SECRET_KEY="$(openssl rand -hex 32)" \
  ANTHROPIC_API_KEY="sk-ant-..." \
  RESEND_API_KEY="re_..." \
  MAIL_FROM="noreply@cue.app" \
  FRONTEND_ORIGIN="https://cue.app" \
  ENV="production"
```

Verify (values are masked):
```bash
fly secrets list -a cue-api
```

Rotate a single secret:
```bash
fly secrets set SECRET_KEY="$(openssl rand -hex 32)" -a cue-api
```

---

## 5. Post-deploy smoke test

After `fly deploy` completes, run the smoke test against the live instance:

```bash
API="https://cue-api.fly.dev"

# Health
curl -sf "$API/health" | jq .
# → {"ok": true}

# Upload Ratnagiri
PROJECT=$(curl -sf -X POST "$API/projects" \
  -F "file=@api/tests/fixtures/ratnagiri_master.xlsx" \
  -H "Cookie: cue_session=<dev-token>" | jq -r '.id')
echo "project_id: $PROJECT"

# Views
curl -sf "$API/projects/$PROJECT/views/main_schedule" | jq '.rows | length'
# → 21 (shoot days)

# Flag detector (run via worker; check flags table)
curl -sf "$API/projects/$PROJECT/flags" | jq 'length'
# → ≥1

# Chat round-trip
THREAD=$(curl -sf -X POST "$API/projects/$PROJECT/chat/threads" \
  -H "Content-Type: application/json" \
  -H "Cookie: cue_session=<dev-token>" \
  -d '{"title":"smoke"}' | jq -r '.id')

curl -sf -X POST "$API/projects/$PROJECT/chat/threads/$THREAD/messages" \
  -H "Content-Type: application/json" \
  -H "Cookie: cue_session=<dev-token>" \
  -d '{"content":"What is this project?"}' \
  --no-buffer | head -5
# → data: {"type":"assistant_delta","text":"This is..."}
```

### Expected output (annotated transcript)

```
$ bash smoke_test.sh

[1/5] GET /health
  ✓ {"ok":true}

[2/5] POST /projects — Ratnagiri upload
  ✓ project_id: a1b2c3d4-e5f6-...
  ✓ 42 scenes, 21 shoot days, 14 characters ingested

[3/5] GET /views/main_schedule
  ✓ 21 rows returned, total 148⅛ pages

[4/5] FlagDetector (via worker — check flags table)
  ✓ 7 open flags: 3×missing_data, 2×permit_lead, 1×drone_block, 1×continuity

[5/5] Chat: "What is this project?"
  data: {"type":"tool_call","name":"get_project_overview"}
  data: {"type":"tool_result","name":"get_project_overview",
         "result":{"title":"Ratnagiri","shoot_days_total":21,...}}
  data: {"type":"assistant_delta","text":"This is "}
  data: {"type":"assistant_delta","text":"the Ratnagiri production — a 21-day shoot..."}
  data: {"type":"done"}
  ✓ Chat responded successfully

Smoke test complete — all 5 checks passed.
```

---

## 6. Wipe and re-seed for demo

```bash
# SSH into the running container
fly ssh console -a cue-api

# Wipe schema
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
import os
async def wipe():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with engine.begin() as conn:
        await conn.execute(__import__('sqlalchemy').text('DROP SCHEMA public CASCADE'))
        await conn.execute(__import__('sqlalchemy').text('CREATE SCHEMA public'))
    await engine.dispose()
asyncio.run(wipe())
"

# Re-migrate
alembic upgrade head

# Re-seed via API upload (from your local machine)
curl -X POST "https://cue-api.fly.dev/projects" \
  -F "file=@ratnagiri_master.xlsx" \
  -H "Cookie: cue_session=<token>"
```

---

## Dockerfile refinement (production target)

Add a `production` build stage to `api/Dockerfile` so `fly.toml`'s `build-target = "production"` strips dev tooling:

```dockerfile
# --- base stage (existing content stays) ---
FROM python:3.11-slim AS base
# ... (existing WeasyPrint deps + pip install) ...

# --- production stage ---
FROM base AS production
# Drop build tools not needed at runtime
RUN pip uninstall -y pip setuptools wheel 2>/dev/null || true
WORKDIR /app
COPY --from=base /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=base /usr/local/bin /usr/local/bin
COPY api/ /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
