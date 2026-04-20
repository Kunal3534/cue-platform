# Task: Wire the Cue frontend to the v1 backend

You are picking up a codebase that already has two finished halves:

1. **`design/`** — a 22-screen clickable HTML prototype. This is the visual truth. Every page, every component, every color, every type choice, every micro-interaction is already decided here. Do not redesign; translate.
2. **`api/`** — a finished FastAPI v1 backend. 36 endpoints live, SSE running on Redis, chat streaming with tool-use, propagation preview/commit, scenario fork/diff/merge, call-sheet PDF, 14 xlsx exporters, worker queue. All endpoints are documented in **`SPEC_v1.md` §5**.

Your job is the third half: replace the current placeholder `web/` with a real Next.js 14 (App Router) app that (a) reproduces every screen in `design/` pixel-for-pixel, and (b) talks to the real backend on every route, button, and field. No mock data anywhere. No weeks, no phases — just do it end to end.

---

## Non-negotiables

- **Use the existing design as the target.** Open `design/<screen>.html` / `design/project/<screen>.html` side-by-side with the page you're building. If a spacing, color, or font differs, the design wins. The stylesheet at `design/styles.css` is your reference for tokens — port them to a Tailwind config or CSS variables file, don't re-invent them.
- **No mock data, no stubbed endpoints, no hardcoded sample JSON.** Every list, every grid, every chat reply must come from a real HTTP call to the FastAPI app running at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
- **Typed API client.** Generate types from the OpenAPI schema at `/openapi.json` (e.g. `openapi-typescript`) and wrap every endpoint in a typed fetcher under `web/src/lib/api/`. No raw `fetch` calls scattered in components.
- **Auth.** Magic-link flow per `SPEC_v1.md` §8. Session cookie is set by the backend; the frontend just needs to include credentials on fetches and handle 401 → redirect to `/login`.
- **SSE.** Project events stream from `GET /api/v1/projects/{id}/events` as documented in `SPEC_v1.md` §7. Use the native `EventSource` API, reconnect on drop, and dispatch each event type (`view_regenerated`, `edit_committed`, `call_sheet_regenerated`, `flag_raised`, etc.) into a project-scoped store (Zustand). Views in the UI should react to `view_regenerated` by refetching the affected view.
- **Chat streaming.** The chat endpoint streams SSE with tool-use deltas. Implement the full Anthropic-style render: assistant text streams token-by-token, tool calls render as cards with their inputs, tool results render inline, and when the assistant proposes an edit a **"Preview changes"** button appears that opens the propagation preview modal.

---

## Stack

- Next.js 14 App Router, React 18, TypeScript strict
- Tailwind CSS — **use `design/tokens.json` as the single source of truth**. Drive `tailwind.config.ts` (`theme.extend.colors`, `fontFamily`, `spacing`, `borderRadius`, `boxShadow`, `transitionTimingFunction`) from that file. Don't hand-copy hex values from `design/styles.css` — if a token is missing, add it to `tokens.json` first, then let Tailwind pick it up.
- Fonts: **IBM Plex Serif** (body/headings), **IBM Plex Mono** (meta/data), **Big Shoulders Display** (display numerals), **Erica One** (poster-weight accents). Load via `next/font/google`.
- State: Zustand for project-scoped state + SSE event dispatch. TanStack Query for server state (with SSE-triggered invalidation).
- Forms: react-hook-form + zod. Zod schemas should align with the Pydantic response types.
- Grid: **AG Grid Community** for the master grid on `/project/[id]/master` (editable cells → Edit DSL).
- Calendar: native HTML5 drag-and-drop, matching the Movie Magic–style stripboard in `design/project/calendar.html`. Do not pull in a calendar library; copy the behaviour from the prototype.
- Charts: Recharts if needed for budget/continuity views.
- Icons: Lucide.
- Logo: use `/cue-mark.svg` (already placed at `web/public/cue-mark.svg`). Every nav bar uses `<Image src="/cue-mark.svg" alt="Cue" width={32} height={32} />` inside a wordmark link — no legacy strip/dot spans.

---

## Screen-to-endpoint map

For each route below, build the page so it matches the named HTML prototype and calls the listed endpoints. Unless noted, all endpoints are prefixed `/api/v1`.

| Route | Design file | Key endpoints |
|---|---|---|
| `/login` | (new — magic-link entry + `/auth/callback`) | `POST /auth/magic-link`, `GET /auth/callback`, `GET /auth/me` |
| `/` | `design/index.html` | `GET /projects` |
| `/projects/new` | `design/upload.html` | `POST /projects` (multipart upload), poll `GET /projects/{id}` until `status=ready` |
| `/project/[id]` | `design/project/chat.html` | `GET /projects/{id}`, `POST /projects/{id}/chat` (SSE), `GET /projects/{id}/chat/history`, SSE `GET /projects/{id}/events` |
| `/project/[id]/schedule` | `design/project/schedule.html` | `GET /projects/{id}/views/schedule` |
| `/project/[id]/calendar` | `design/project/calendar.html` | `GET /projects/{id}/views/calendar`, drag-drop → `POST /projects/{id}/edits/preview` then `POST /projects/{id}/edits/commit` |
| `/project/[id]/day/[date]` | `design/project/day.html` | `GET /projects/{id}/views/day?date=...` |
| `/project/[id]/scenes` | `design/project/scenes.html` | `GET /projects/{id}/views/scenes` |
| `/project/[id]/master` | `design/project/master.html` | `GET /projects/{id}/views/master`, AG Grid cell edits → preview/commit |
| `/project/[id]/resources` | `design/project/resources.html` | `GET /projects/{id}/views/resources` (dept summary) |
| `/project/[id]/resources/cast` | `design/project/cast.html` | `GET /projects/{id}/views/cast` |
| `/project/[id]/resources/juniors` | `design/project/juniors.html` | `GET /projects/{id}/views/juniors` |
| `/project/[id]/resources/vehicles` | `design/project/vehicles.html` | `GET /projects/{id}/views/vehicles` |
| `/project/[id]/resources/cameras` | `design/project/cameras.html` | `GET /projects/{id}/views/cameras` |
| `/project/[id]/resources/props` | `design/project/props.html` | `GET /projects/{id}/views/props` |
| `/project/[id]/resources/animals` | `design/project/animals.html` | `GET /projects/{id}/views/animals` |
| `/project/[id]/resources/vfx` | `design/project/vfx.html` | `GET /projects/{id}/views/vfx` |
| `/project/[id]/resources/effects` | `design/project/effects.html` | `GET /projects/{id}/views/effects` (SFX + stunts) |
| `/project/[id]/resources/hmu` | `design/project/hmu.html` | `GET /projects/{id}/views/hmu` |
| `/project/[id]/resources/wardrobe` | `design/project/wardrobe.html` | `GET /projects/{id}/views/wardrobe` |
| `/project/[id]/requirements` | `design/project/requirements.html` | `GET /projects/{id}/views/requirements` |
| `/project/[id]/callsheets` | `design/project/callsheets.html` | `GET /projects/{id}/callsheets` |
| `/project/[id]/callsheets/[date]` | `design/project/callsheet-1.html` | `GET /projects/{id}/callsheets/{date}`, `POST /projects/{id}/callsheets/{date}/send`, `GET /projects/{id}/callsheets/{date}/pdf` |
| `/project/[id]/scenarios` | (use existing scenarios panel in chat.html, promote to a page) | `GET /projects/{id}/scenarios`, `POST /projects/{id}/scenarios/fork`, `GET /projects/{id}/scenarios/diff`, `POST /projects/{id}/scenarios/merge` |
| `/project/[id]/exports` | (small export drawer, reachable from every view) | `POST /projects/{id}/exports` → returns job id → poll `GET /exports/{id}` → download signed URL |

Any endpoint listed in `SPEC_v1.md` §5 that isn't surfaced in a page above still needs a typed client method — the chat agent calls several of them via tool-use and the UI needs to render the results.

---

## Cross-cutting behaviour

**Edit DSL → Preview → Commit.** Any UI action that mutates project state (drag a scene to a new day, edit a cell in the master grid, change a call time, reassign a resource) must:
1. Build an Edit DSL payload (shape in `SPEC_v1.md` §5.4).
2. POST to `/edits/preview` — receive a `propagation_preview` id + a diff of every affected view.
3. Show a modal that renders the diff (added/removed/changed rows per view, flags raised, cost delta if present). Per `design/project/calendar.html` the preview modal is slate-on-chalk with the Edit DSL pretty-printed on the left and a view-by-view impact list on the right.
4. On confirm, POST to `/edits/commit` with the preview id. On success, the SSE `edit_committed` event will fire and refresh affected views.
5. On cancel, discard the preview (it TTLs after 15 min anyway).

**Flags.** The backend raises flags (cast holds, permit leads, weather conflicts, drone no-fly, cost overruns, missing data, continuity). Render these as a persistent **Flags** drawer reachable from the nav — count badge in the wordmark bar. Each flag has severity, affected entity, and an "ask chat about this" button that opens the chat pane pre-filled.

**Scenarios.** The active scenario is shown next to the project name in the nav. Clicking opens the scenario switcher; forking creates a branch; merging is gated behind a diff view.

**Offline / error states.** If the API is down, show the chalk empty-state from the prototype. If SSE drops, reconnect silently with exponential backoff. If a preview 409s (stale), refetch and re-preview.

---

## Directory layout

```
web/
  app/
    layout.tsx                  # fonts, global providers
    page.tsx                    # → design/index.html
    login/page.tsx
    projects/new/page.tsx       # → design/upload.html
    project/[id]/
      layout.tsx                # project nav + SSE provider + flags drawer
      page.tsx                  # chat home → design/project/chat.html
      schedule/page.tsx
      calendar/page.tsx
      day/[date]/page.tsx
      scenes/page.tsx
      master/page.tsx
      resources/
        page.tsx
        cast/page.tsx
        juniors/page.tsx
        vehicles/page.tsx
        cameras/page.tsx
        props/page.tsx
        animals/page.tsx
        vfx/page.tsx
        effects/page.tsx
        hmu/page.tsx
        wardrobe/page.tsx
      requirements/page.tsx
      callsheets/
        page.tsx
        [date]/page.tsx
      scenarios/page.tsx
  src/
    components/
      nav/                      # wordmark + project nav
      chat/                     # streaming chat, tool-card renderer, preview button
      calendar/                 # stripboard + DnD
      grid/                     # AG Grid wrapper
      preview-modal/            # Edit DSL + diff renderer
      flags/                    # flags drawer + badge
      scenarios/                # switcher, diff, merge
    lib/
      api/                      # typed clients, generated from /openapi.json
      sse/                      # EventSource wrapper + project event store
      auth/                     # session helpers
      edit-dsl/                 # builders, preview/commit flow
    stores/                     # zustand: project, flags, scenario, chat
    styles/
      tokens.css                # ported from design/styles.css
      globals.css
  public/
    cue-mark.svg                # already in place — use this in the wordmark
```

---

## Definition of done

- All 25 routes render against real backend data with no mocks.
- Log in from scratch → create project → upload breakdown → wait for parse → chat "schedule Ratnagiri in 18 days starting June 3" → watch SSE events land → see calendar populate → drag a scene → preview modal shows downstream impact → commit → views refresh → generate call sheet → download PDF — all without touching the network tab to fake anything.
- Every screen is visually within rounding error of its `design/` counterpart at 1440×900 and at 375×812.
- `pnpm typecheck` and `pnpm lint` pass clean.
- No `any`, no `@ts-ignore`, no `TODO: wire this up`.

Start by reading `SPEC_v1.md` end-to-end, opening a handful of `design/` pages, and sketching the API client + SSE provider. Then build top-down: layout → chat home → calendar → the rest.
