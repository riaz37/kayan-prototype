# Console UI (Frontend)

The staff-facing admin console for the Kayan platform — the counterpart to the AI agents. Arabic-first (RTL) with a full English (LTR) mode.

**Stack:** Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS 4 · shadcn/ui (Radix, RTL-enabled) · SWR · Sonner · lucide-react.

## Run

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000  (expects the API on http://localhost:8000)
```

Production build: `npm run build && npm start`. The Docker image (`frontend/Dockerfile.frontend`) runs the Next.js standalone server on port 3000.

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Where the console's server-side `/api` proxy forwards to. The browser only ever calls `/api`, so the session cookie stays first-party and there is no CORS |

## Sign-in

Every page except `/login` requires a session. `src/proxy.ts` redirects signed-out visitors (keeping a `next` path), `AuthGate` blocks rendering until `/auth/me` answers, and `useSession().can("…")` hides actions and pages the role does not allow. See `docs/09_ACCESS_CONTROL.md`.

## Languages and direction

- Every URL carries its locale: `/ar/...` and `/en/...`. The server renders `lang`/`dir` for that locale, so there is no flash of the wrong direction.
- `src/proxy.ts` redirects bare paths (`/`, `/kanban`) to the visitor's last-used locale (`NEXT_LOCALE` cookie), defaulting to Arabic.
- The topbar switch keeps the current page and query (`/ar/tickets?ticket=TK-1` ⇄ `/en/tickets?ticket=TK-1`).
- Layout uses logical properties only (`ms-*`, `pe-*`, `start-*`, `text-start`, `border-e`), so every screen mirrors correctly.

### Where strings live

| File | What |
|---|---|
| `src/lib/i18n/dictionaries/ar.ts` | All UI strings — the source of truth for the dictionary shape |
| `src/lib/i18n/dictionaries/en.ts` | English strings, typed against `ar.ts`: **a missing key is a compile error**, so English can't silently fall back to Arabic |
| `src/lib/i18n/catalog.ts` | Bilingual labels for API codes and reference data (ticket/file/stage/decision statuses, departments, programs, 43 request types, documents, form sections, cities, relationships, education, case-study steps, staff, enrollment types) |
| `src/lib/i18n/format.ts` | Locale-aware numbers, money (`92,655 ر.س` / `SAR 92,655`), dates, relative time, plurals, SLA countdown |

The backend is Arabic-first and often sends only an Arabic label (`status_ar`, `department_ar`, `program_ar`…). Components never render those directly — they call `label(kind, code, arabic)`, which resolves the code (or the Arabic label, via a normalised reverse index) against the catalog. **To add a new term:** add it to `catalog.ts` with both `ar` and `en`.

User-entered content (names, ticket subjects, chat messages, case-worker notes) is data, not UI — it stays as entered and is rendered with `dir="auto"` so it lays out correctly inside either direction.

## Screens

| Route | What it shows |
|---|---|
| `/` Dashboard | Greeting hero, ticket/file/disbursement stats, kanban preview, requests by program, channel activity, committee decisions |
| `/kanban` | Four-column board with drag-and-drop status changes (optimistic), SLA per card, department filter |
| `/tickets` | Filterable ticket table (status, search) |
| `/beneficiaries` | Beneficiary table with completion bars and status filter; honours `?q=` from the topbar search. Staff with `beneficiaries:manage` can create a file (**New file**) and edit any file's sections from the panel; submitted files are approved/rejected there too |
| `/requests` | Requests across the programs; click a row for the full request workflow (case study → committee → decision → enrollment) |
| `/committee` | Need-ranked committee queue; accept / request documents / decline |
| `/finance` | Upcoming disbursements with approve/pay, totals by program, sponsorships |
| `/programs` | Programs; click one to see its request types, ceilings, recurrence |
| `/agent-test` | Chat with the WhatsApp agent through the API, with live conversation context |
| `/staff` | Staff accounts: add, set role and department, grant/revoke individual permissions, reset password, deactivate (admins only) |
| `/login` | Email + password sign-in (the only page reachable signed out) |

Detail panels are addressed by the URL (`?ticket=TK-1005`, `?ben=ben-…`, `?request=SR-…`), so they survive refresh, can be shared, and close with the back button:

- **Ticket** (`?ticket=`) — the conversation: WhatsApp-style thread (day separators, grouped bubbles, delivery state, jump-to-latest), a details drawer (department, SLA, previous tickets, close ticket) and a composer that sends via WhatsApp or saves an internal note
- **Beneficiary 360** (`?ben=`) — file review (approve / reject), completion ring, need score, missing items, tabs for household / requests / disbursements / activity
- **Support request** (`?request=`) — progress stepper and the whole casework flow: open case study, schedule visits/interviews, record findings, send to committee, decide, enroll and generate the payment schedule

## Structure

```
frontend/src/
├── app/[locale]/            layout (html lang/dir, providers), one folder per route, 404, error
├── proxy.ts                 locale redirect + cookie
├── components/ui/           shadcn/ui primitives, restyled to the Kayan tokens
├── components/kayan/        Stat, PageHead, StatusBadge, NameAvatar, Ring, Field, Empty, LoadError…
├── components/shell/        sidebar, topbar (search, language, health, notifications), nav config
├── components/details/      ticket sheet, beneficiary 360 sheet, decision dialog
├── components/views/        one client view per screen
└── lib/                     api client + SWR hooks + types, i18n
```

## Design tokens

Defined once in `src/app/globals.css` and exposed both as shadcn semantic tokens and as `brand-*`, `ink`, `line`, `canvas` utilities.

| Token | Value |
|---|---|
| Canvas | `#FAFAFB` |
| Surface | `#FFFFFF` with `1px #EAECF0` border |
| Brand | teal ramp, primary `#0F8478` |
| Text | `#0F172A` / muted `#64748B` / soft `#94A3B8` |
| Radius | `0.875rem` cards, `0.5rem` controls |
| Shadow | `card` (barely-there) and `pop` (hover/overlay) |
| Type | IBM Plex Sans Arabic 300–700, self-hosted in `public/fonts` |

Status colours are consistent everywhere: green = open/paid/accepted, sky = in progress, amber = waiting/docs required, violet = replied, rose = expired/declined, slate = closed.
