# Kayan Orphan Care — AI Agent Platform (Prototype)

A **runnable mock** of جمعية كيان للأيتام's beneficiary management platform, built so AI agents on **phone (SIP)** and **WhatsApp** can execute the full journey in the association's guide *"رحلة المستفيد في نظام جمعية كيان"* — and so the CRM behind it behaves like the admin panel in the supplied screenshots.

**72 tool endpoints. 33 seed datasets. 83/83 end-to-end checks passing.**

## The journey this simulates

```
WhatsApp / Phone call
      │
      ▼
identify caller ──► eligibility gate (مجهولو الأبوين)
      │
      ▼
create file ──► 10 form sections ──► dependents ──► documents ──► financial profile
      │                                    (لا يوجد / عدم الأهلية)
      ▼
submit ──► staff approval ──► support request (5 programs / 43 request types)
      │
      ▼
case study (زيارة ميدانية · مقابلة · تقييم نفسي) ──► اللجنة المختصة
      │
      ▼
decision (قبول / استكمال مستندات / اعتذار) ──► WhatsApp + SMS notification
      │
      ▼
enrollment ──► monthly disbursement schedule ──► payment to IBAN ──► 360 history
```

Throughout, unresolved queries become **CRM tickets** on a kanban board with SLA countdowns and department routing. Each phone number has **one open conversation**: new WhatsApp messages join the caller's open ticket instead of opening duplicates, and the whole exchange (beneficiary, AI agent, staff) is stored on that ticket.

## What's in the box

| Path | What it is |
|---|---|
| `backend/` | FastAPI mock — 72 tool endpoints in 9 groups |
| `backend/routers/beneficiary.py` | Registration, OTP, the 10 sections, dependents, documents, finances, FAQ |
| `backend/routers/crm.py` | Tickets, kanban, SLA, stats + WhatsApp & SIP channels |
| `backend/routers/programs.py` | 5 programs / 43 request types, casework, committee |
| `backend/routers/finance.py` | Enrollment, disbursements, payments, sponsorships, 360 history |
| `data/` | 33 seed datasets (JSON), Arabic-first, referentially intact |
| `openapi/kayan_openapi.json` | OpenAPI 3.1 spec — **import this into your agent builder** |
| `scripts/generate_seed.py` | Regenerates all seed data (deterministic) |
| `scripts/smoke_test.py` | Walks the entire journey end-to-end (83 assertions) |
| `docs/09_ACCESS_CONTROL.md` | Sign-in, roles, permissions and the agent service key |
| `docs/` | Build plan, architecture, data model, agent design, tool reference, open-source stack, frontend |
| `frontend/` | Admin console — Next.js + shadcn/ui, Arabic (RTL) and English (LTR). See `docs/08_FRONTEND.md` |

## Run it

**One command (backend + agent + console):** `./start.sh` — Ctrl+C stops everything. It prints the local sign-in details; copy `.env.example` to `.env.local` to set your own. Add `--ngrok` to expose the WhatsApp webhook.

Or manually:

```bash
pip install -r requirements.txt
python scripts/generate_seed.py          # already generated; re-run to reset
PYTHONPATH=. uvicorn backend.main:app --reload --port 8000
```

or `./run.sh`. Then:

- **Console UI** — `cd frontend && npm install && npm run dev` → http://localhost:3000
- **Swagger UI** — http://localhost:8000/docs
- **Verify everything** — `PYTHONPATH=. python scripts/smoke_test.py`

## Connecting your AI agents

1. Import `openapi/kayan_openapi.json` — each endpoint's summary/description is written to double as the tool's decision text.
2. Build one agent per group (see `docs/04_AGENT_DESIGN.md`), or one agent with the full toolset.
3. Conversational endpoints return **`reply_ar`** — speech/print-ready Arabic, so your TTS layer doesn't compose from raw fields.
4. Start every conversation with `POST /whatsapp/inbound` or `POST /voice/call-start` — both return the caller's full context (file status, what's missing, open requests, next payment).

## Three things built in deliberately

**It chases missing information.** `GET /beneficiary/{id}/completeness` returns the exact missing fields (with their section) and missing mandatory documents, plus a ready-to-send Arabic sentence. That's what lets the agent ask for *precisely* what's outstanding instead of "please complete your file."

**It enforces the real rules, so agents get tested against failure.** Support requests before file approval → 409. Amount over the program ceiling → 409. Committee before any completed case step → 409. Paying with no IBAN on file → 409. Marking a national ID as "لا يوجد" → 409. Luxury spending as a counted cost → 409.

**It models the WhatsApp 24-hour window.** Free-form sends outside the window are blocked; the response tells the agent to use an approved template instead — the same constraint the real Business API imposes.

## Assumptions (all changeable)

- **Stack:** Python/FastAPI, chosen because it auto-generates the OpenAPI spec your builder consumes. See `docs/06_OPEN_SOURCE_STACK.md` for the recommended production stack (ERPNext + Chatwoot + LiveKit).
- **State:** in-memory; resets on restart — repeatable agent tests. No DB, no real money, no real SIP/WhatsApp.
- **Auth:** email + password with roles and per-user permissions (`docs/09_ACCESS_CONTROL.md`). Every endpoint requires a session; the WhatsApp agent uses a service key.
- **Language:** Arabic-first, undiacritized (standard for ERP/UI text). English available on FAQ.

> **All data is synthetic.** No real beneficiary, orphan, family, sponsor, or staff member is represented. This is a simulation for agent testing — not the production Kayan system, and not a security-hardened service. Real deployment handling orphan case data needs PDPL review, access control, audit logging, and encryption at rest.
