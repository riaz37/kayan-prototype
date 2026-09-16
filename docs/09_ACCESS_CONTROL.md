# Sign-in, roles and permissions

Every console screen and every API endpoint now requires a signed-in staff account. The WhatsApp agent authenticates with a service key instead.

## How sign-in works

- **Email + password.** Passwords are hashed with scrypt (Python standard library) and a per-user salt.
- **Session cookie.** Sign-in sets an httpOnly, SameSite=Lax cookie (`kayan_session`, 14 days). Only the SHA-256 hash of the token is stored, so database access alone cannot be replayed as a session. The cookie is marked Secure automatically when the console is served over HTTPS.
- **First-party only.** The console calls its own `/api/...` route, which proxies to the backend server-side (`frontend/src/app/api/[...path]/route.ts`). The backend URL is never exposed to the browser and there is no cross-site cookie.
- **First admin.** On startup, if no account exists and `ADMIN_EMAIL` / `ADMIN_PASSWORD` are set, that admin is created once.
- **Temporary passwords.** Accounts an admin creates can be flagged "must change password"; the console then forces a change before anything else.
- **Deactivation** removes every active session for that user immediately.

## Roles

A role grants a default set of permissions. **An admin can grant extra permissions or take some away per person**, on top of the role (shown on the Staff page as green `+` and red `−` chips).

| Role | Can do (beyond viewing) |
|---|---|
| **Admin** (مدير النظام) | Everything, including staff accounts and `/admin/*` |
| **Beneficiary services** (خدمات المستفيدين) | Tickets, create and edit beneficiary files, approve/reject files, create requests, agent test |
| **Case worker** (باحث اجتماعي) | Case studies (visits, findings, send to committee), tickets, create requests |
| **Committee member** (عضو اللجنة) | Record committee decisions |
| **Finance** (الشؤون المالية) | Enrollment, approve and pay disbursements |

Every signed-in role can **read** tickets, beneficiaries, requests and disbursements — the agreed model is "all staff see the data; the role decides what they can change".

## Permissions

| Key | Covers |
|---|---|
| `tickets:view` / `tickets:manage` | See tickets / reply, move, assign, close |
| `beneficiaries:view` / `beneficiaries:manage` / `beneficiaries:review` | See files / create and edit them / approve and reject them |
| `requests:view` / `requests:create` | See requests / raise them and add details |
| `casework:manage` | Open a case study, schedule steps, record findings, send to committee |
| `committee:decide` | Accept, request documents, decline |
| `finance:view` / `finance:manage` | See disbursements / enroll, approve, pay |
| `agent:test` | The Agent Test page and `/agent/*` |
| `staff:manage` | Staff accounts, roles and permissions |
| `admin:all` | Everything (implies all of the above) |

Enforcement lives in two places, both in `backend/auth.py`:
- `PUBLIC_PATHS` — the only endpoints reachable without signing in (`/health`, `/auth/login`, `/webhook` for Meta, and the API docs).
- `_RULES` — a table mapping method + path to the permission required. It is applied by one middleware in `backend/main.py`, so a new endpoint is protected by default (any signed-in user) and write endpoints are matched by their area's rule.

In the console, `useSession().can("…")` hides actions and whole pages (`RequirePermission`), and the sidebar only lists what the user may open. The UI hiding is convenience — the backend enforces the same rules.

## The WhatsApp agent

The agent runs unattended, so it sends `X-Agent-Key: $AGENT_API_KEY` on every backend call. That key grants exactly what the agent needs: read data, register beneficiaries and fill their file, create tickets and requests, reply to tickets. It cannot manage staff, decide committee outcomes, approve files or pay money.

Set `AGENT_API_KEY` to a long random string and give the backend and the agent the same value. `./start.sh` uses a development key locally when the variable is unset.

## Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | backend | First admin, created only while no account exists |
| `ADMIN_NAME`, `ADMIN_NAME_EN` | backend | Optional display name for that admin |
| `AGENT_API_KEY` | backend + agent | Service key for the WhatsApp agent |
| `ALLOWED_ORIGINS` | backend | Comma-separated origins for direct browser calls; default `*` disables credentialed CORS |
| `BACKEND_URL` | console (server-side) | Where the console's `/api` proxy forwards to |

## Operating notes

- Change the first admin's password after the first sign-in; the account is created from environment variables.
- Removing a person: deactivate rather than delete, so their ticket replies and decisions keep their author.
- A future audit log (who approved, decided, paid) is not built yet — worth adding before real beneficiary data.

## Conversations and tickets

One conversation per phone number: while a caller has a ticket that is not closed, everything they send joins it (`db.active_ticket_for`). A new ticket is opened only after the previous one is closed. Every WhatsApp message in both directions is stored in `ticket_messages` through `POST /crm/conversation/log`, which the agent calls on each turn, so the console shows the full exchange without querying the agent process.

`scripts/merge_duplicate_tickets.py` merges tickets created before this rule (dry run by default, `--apply` to write).
