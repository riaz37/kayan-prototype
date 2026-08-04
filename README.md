# Kayan Orphan Care — AI Agent Platform (Prototype)

A **runnable mock** of جمعية كيان للأيتام's beneficiary management platform, built so AI agents on **phone (SIP)** and **WhatsApp** can execute the full journey in the association's guide *"رحلة المستفيد في نظام جمعية كيان"* — and so the CRM behind it behaves like the admin panel in the supplied screenshots.

**72 tool endpoints. 33 reference datasets. 115/115 end-to-end checks + 46 regression tests passing.**

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

Throughout, unresolved queries become **CRM tickets** on a kanban board with SLA countdowns and department routing.

## What's in the box

| Path | What it is |
|---|---|
| `backend/` | FastAPI service — 72 tool endpoints in 9 groups |
| `backend/store.py` | SQLite persistence: schema, migrations, read/write helpers |
| `backend/routers/beneficiary.py` | Registration, the 10 sections, dependents, documents, finances, FAQ |
| `backend/routers/crm.py` | Tickets, kanban, SLA, stats + WhatsApp & SIP channels |
| `backend/routers/programs.py` | 5 programs / 43 request types, casework, committee |
| `backend/routers/finance.py` | Enrollment, disbursements, payments, sponsorships, 360 history |
| `backend/seed_production.py` | Generates the demo database (deterministic) |
| `agent/` | WhatsApp LLM agent — webhook, tool-calling loop, session store |
| `reference-data/` | 33 reference datasets (JSON), Arabic-first, referentially intact |
| `openapi/kayan_openapi.json` | OpenAPI 3.1 spec — **import this into your agent builder** |
| `tests/` | pytest regression suite (46 tests) |
| `scripts/journey_check.py` | Walks the entire journey end-to-end (115 assertions) |
| `docs/` | Build plan, architecture, data model, agent design, tool reference, open-source stack, frontend |
| `frontend/` | Arabic RTL admin console (React + Tailwind, no CDN) |

## Run it

```bash
./run.sh                # venv, build, seed, then serve everything
./run.sh --no-agent     # skip the LLM agent
./run.sh --reseed       # wipe and regenerate the demo data
./run.sh --tunnel       # also expose the agent via ngrok for Meta webhooks
```

- **Console** — http://localhost:3000
- **Swagger UI** — http://localhost:8001/docs
- **Agent health** — http://localhost:8002/health

The console targets `localhost:8001` automatically. To point it at another
backend, append `?api=https://your-backend` once — the choice is remembered.

### Verify

```bash
.venv/bin/python -m pytest tests/ -q                       # 46 regression tests
DATA_DIR=/tmp/kayan-check PYTHONPATH=. \
  .venv/bin/python scripts/journey_check.py                # 115 end-to-end assertions
```

### Configuration

Copy `.env.example` to `.env`. The LLM defaults to a self-hosted vLLM
(`qwen3.6-27b-fp8`); any OpenAI-compatible endpoint works via `LLM_BASE_URL`
and `LLM_MODEL`. WhatsApp credentials are only needed for real delivery — the
console's agent tester works without them.

## Connecting your AI agents

1. Import `openapi/kayan_openapi.json` — each endpoint's summary/description is written to double as the tool's decision text.
2. Build one agent per group (see `docs/04_AGENT_DESIGN.md`), or one agent with the full toolset.
3. Conversational endpoints return **`reply_ar`** — speech/print-ready Arabic, so your TTS layer doesn't compose from raw fields.
4. Start every conversation with `POST /whatsapp/inbound` or `POST /voice/call-start` — both return the caller's full context (file status, what's missing, open requests, next payment).
5. `POST /agent/chat` streams Server-Sent Events (`delta` / `tool` / `reset` / `done`) so a multi-tool turn shows progress instead of stalling. Add `?stream=false` for a single JSON response.

## Three things built in deliberately

**It chases missing information.** `GET /beneficiary/{id}/completeness` returns the exact missing fields (with their section) and missing mandatory documents, plus a ready-to-send Arabic sentence. That's what lets the agent ask for *precisely* what's outstanding instead of "please complete your file."

**It enforces the real rules, so agents get tested against failure.** Support requests before file approval → 409. Amount over the program ceiling → 409. Committee before any completed case step → 409. Paying with no IBAN on file → 409. Marking a national ID as "لا يوجد" → 409. Luxury spending as a counted cost → 409.

**It models the WhatsApp 24-hour window.** Free-form sends outside the window are blocked; the response tells the agent to use an approved template instead — the same constraint the real Business API imposes.

## Assumptions (all changeable)

- **Stack:** Python/FastAPI, chosen because it auto-generates the OpenAPI spec your builder consumes. See `docs/06_OPEN_SOURCE_STACK.md` for the recommended production stack (ERPNext + Chatwoot + LiveKit).
- **State:** SQLite at `$DATA_DIR/kayan.db` (default `./data`). The database is generated, not committed — run `python backend/seed_production.py` to (re)create it. Schema changes are applied automatically on startup by the migration step in `backend/store.py`.
- **Auth:** none, open CORS, for sandbox use. Add a token before any shared deployment.
- **Language:** Arabic-first, undiacritized (standard for ERP/UI text). English available on FAQ.

> **All data is synthetic.** No real beneficiary, orphan, family, sponsor, or staff member is represented. This is a simulation for agent testing — not the production Kayan system, and not a security-hardened service. Real deployment handling orphan case data needs PDPL review, access control, audit logging, and encryption at rest.
