# Cue — clickable prototype (v2)

Twenty screens covering the whole pre-pro workflow, from "good morning" to
"ship the call sheet". Real content from the Ratnagiri sample xlsx. One shared
stylesheet, no framework, no build step.

## To open

```bash
open /Users/kunalpanjwani/Downloads/cue-platform/design/index.html
```

Or serve locally (recommended — relative paths always work):

```bash
cd /Users/kunalpanjwani/Downloads/cue-platform/design
python3 -m http.server 5500
# then open http://localhost:5500
```

## The flow

1. **index.html** — projects list. Click Ratnagiri.
2. **project/chat.html** — you land here, not the schedule. Ask Cue anything — it already knows the project graph. The demo conversation replans Day 1 because Priya's flight got cancelled.
3. From chat, navigate with the top tabs: **Schedule · Calendar · Scenes · Resources · Call sheets · Edit master**.

## The 20 screens

### Entry points
| # | File | What |
|---|---|---|
| 1 | `index.html` | Projects list — 4 sample projects, empty state |
| 2 | `upload.html` | Upload flow, file-selected state |

### Project navigation (top-level tabs)
| # | File | What |
|---|---|---|
| 3 | `project/chat.html` | **Home. The novelty.** Conversational UI that knows the project |
| 4 | `project/schedule.html` | Stripboard with scene counts, scene IDs, element chips per day |
| 5 | `project/calendar.html` | Month view — every day colour-coded, break / hold / travel called out |
| 6 | `project/scenes.html` | Scene × day matrix (94 scenes) |
| 7 | `project/resources.html` | Hub — tiles grouped into People / On-camera / FX / Set / Cross-cutting |
| 8 | `project/callsheets.html` | List of 22 call sheets, draft & ready states |
| 9 | `project/master.html` | Editable grid + propagation preview modal |

### Day detail (click any day from schedule or calendar)
| # | File | What |
|---|---|---|
| 10 | `project/day.html` | Scenes-in-order left, all 18 resource blocks right — on one page |
| 11 | `project/callsheet-1.html` | Full paper-style call sheet for one shoot day |

### Resource views (from the Resources hub)
| # | File | What |
|---|---|---|
| 12 | `project/cast.html` | Cast DOOD (day out of days) — W/H/T matrix |
| 13 | `project/juniors.html` | Junior-artist bar chart + vendor brief |
| 14 | `project/vehicles.html` | Picture-vehicle grid with continuity notes |
| 15 | `project/animals.html` | Animals · AWBI permits · vet · handler · welfare windows |
| 16 | `project/props.html` | 47 props · hero + set-dress · lead times · cross-references |
| 17 | `project/vfx.html` | 34 shots · 142 plates · vendor brief · on-set protocol |
| 18 | `project/effects.html` | SFX + stunts — 6 days, safety plans, insurance riders |
| 19 | `project/hmu.html` | Hair, makeup, prosthetics — mold sessions + continuity |
| 20 | `project/wardrobe.html` | Costume lookbook + continuity grid (3 time periods) |
| 21 | `project/cameras.html` | Camera + lighting units per day |
| 22 | `project/requirements.html` | Per-day one-pager — everything, on one sheet |

## What changed from v1

**The front door is the chat, not the schedule.** When you click a project, you arrive at a conversation with Cue that already knows tomorrow's call, the open flags, and the downstream consequences of any change you propose. The stripboard is a view; the conversation is the app.

**The schedule now speaks in scenes, not just days.** Every day row shows SC numbers, page counts, setup estimates, and element chips (cast, props, VFX, SFX, stunts, animals). Click any day to drill into a full page of scene-by-scene detail + every resource that walks onto that set.

**The calendar view exists.** Month grid with colour-coded shoot-day strips. Break days, travel days, weather holds, and weekly-offs are rendered as honestly as shoot days.

**12 resource departments, not 4.** Props, animals, VFX, SFX, stunts, prosthetics, wardrobe, art — each tracked with the specifics that matter (AWBI permits, mold lead times, fire-dept approvals, continuity keys, vendor briefs, insurance riders).

**The Resources hub groups departments by purpose.** Cast & people · Things on camera · Effects & spectacle · Set & dress · Cross-cutting. Every tile shows counts + open flags.

**Every open flag surfaces everywhere.** Amruta's Day 14 hold shows in Cast DOOD, in the Day calendar strip, and in the chat sidebar. Drone blocked on Day 10 surfaces in Cameras, Calendar, and the VFX budget extend. Nothing hides.

## Design principles still in force

Warm chalk background, not white. Type says what colour can't. IBM Plex Serif for names, Plex Mono for data, Big Shoulders Display for strip labels and buttons, Erica One for the wordmark only. The tilted stripboard motif appears once per screen. Signal colours (Day · Night · Day-Int · Night-Int · Dusk) mean something. Hairlines, no shadows. No gradients (except 3 wardrobe lookbook chips). No rounded corners > 4px.

## What this prototype is not

Still not interactive. Clicks go to pages, but cells don't edit. The chat is scripted, not live. The propagation modal is always open. No empty/error states for every path.

## Next

Review. If the direction is right, we rebuild `/web` against these screens:
CSS tokens port straight to Tailwind config, component shapes port to React,
and `/api` already speaks JSON for every view except the new ones (chat,
calendar, scenes, day-detail, and the 6 new resource views — we'll add those
endpoints in parallel with the UI rebuild).
