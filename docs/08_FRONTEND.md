# Console UI (Frontend)

An Arabic-first, RTL admin console for the Kayan platform — the staff-facing counterpart to the AI agents. Built to match the light, premium shadcn aesthetic.

## Run

The console is served by the API itself, so there's no CORS setup and no second server:

```bash
./run.sh              # then open http://localhost:8000/app/
```

To rebuild after editing the UI:

```bash
cd frontend && ./build.sh
```

## Screens

| Screen | What it shows |
|---|---|
| **لوحة المعلومات** | Greeting hero, ticket/file/disbursement stats, kanban preview, requests by program, channel activity, committee decisions |
| **لوحة التذاكر** | Four-column kanban (مفتوح · جاري العمل · بانتظار العميل · تم الرد) with SLA countdown per card, department filter |
| **التذاكر والطلبات** | Filterable ticket table with status, channel, SLA and search |
| **ملفات المستفيدين** | Beneficiary table with completion bars, dependants, file status, search |
| **طلبات الدعم** | Requests across the 5 programs, clickable program filter cards |
| **اللجنة المختصة** | Need-ranked committee queue with per-case decision actions |
| **الصرف والكفالات** | Upcoming disbursement run, totals by program, sponsorship summary |
| **البرامج** | The five programs with their request-type counts |
| **قنوات الوكلاء** | AI agent activity: SIP call log with dialect, intent, outcome, containment rate |

Two detail panels slide over any screen:

- **Ticket sheet** — conversation log styled as a chat, SLA card, previous tickets, reply box
- **Beneficiary 360** — completion ring, need score, missing-items alert, and tabs for الأسرة / الطلبات / الصرف / النشاط

## Design system

Hand-built shadcn-style primitives in `js/ui.jsx` — `Card`, `Button`, `Badge`, `Input`, `Select`, `Table`, `Tabs`, `Sheet`, `Progress`, `Ring`, `Avatar`, `Stat`, `Empty`, `Skeleton`, `Field`.

| Token | Value |
|---|---|
| Canvas | `#FAFAFB` |
| Surface | `#FFFFFF` with `1px #EAECF0` border |
| Brand | teal ramp, primary `#0F8478` (matches Kayan's identity) |
| Text | `#0F172A` / muted `#64748B` / soft `#94A3B8` |
| Radius | `0.875rem` cards, `0.5rem` controls |
| Shadow | `card` (barely-there) and `pop` (hover/overlay) |
| Type | IBM Plex Sans Arabic, 300–700, **bundled locally** |

Status colours are consistent everywhere: green = open/paid/accepted, sky = in progress, amber = waiting/docs required, violet = replied, rose = expired/declined, slate = closed.

## Architecture

```
frontend/
├── index.html          shell, loads local assets only
├── js/ui.jsx           design system + API client
├── js/pages.jsx        all screens
├── js/app.jsx          sidebar, topbar, routing
├── dist/               built output (JS + CSS) — generated
├── vendor/             React 18 UMD — vendored, no CDN
├── fonts/              IBM Plex Sans Arabic woff2 — bundled
├── snapshot.json       offline data so the UI renders without the API
└── build.sh            JSX → JS, Tailwind → CSS
```

**No CDN, no runtime build step.** React and the font are vendored; JSX is precompiled by Babel; Tailwind is compiled to a static stylesheet. The whole console works offline.

**Live-with-fallback data.** Every screen calls the real API first. If it's unreachable, it falls back to `snapshot.json` so the UI still demos. The topbar pill shows which mode you're in — *متصل بالنظام* (green) or *وضع العرض* (amber).

## What is presentational

This is a demo console, not the production admin app. Read paths are wired to the live API; **write actions are not** — the reply box, the committee accept/decline buttons, and the topbar search render but don't post. Wire them to the existing endpoints (`POST /crm/tickets/{id}/reply`, `POST /support-requests/{id}/decision`, `GET /beneficiaries/search`) when you take it further.

## Notes

- Fully RTL; the layout mirrors correctly and numerals are tabular-aligned for scanning.
- Responsive: sidebar collapses under 1024px, tables scroll horizontally, stat grids reflow.
- Accessibility gaps to close before production: focus-visible rings exist but keyboard traps in the sheet aren't handled, and colour-only status cues need text equivalents in a few spots.
