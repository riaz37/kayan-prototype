# Architecture

## 1. High level

```
   BENEFICIARY
   ┌──────────────┬──────────────┐
   │  Phone (PSTN)│   WhatsApp   │
   └──────┬───────┴──────┬───────┘
          │ SIP trunk    │ Business API webhook
          ▼              ▼
   ┌─────────────────────────────────┐
   │        AI AGENT LAYER           │  ← your agent builder
   │  STT(ar) → LLM → TTS(ar)        │
   │  intent · slots · tool calling  │
   └────────────┬────────────────────┘
                │ HTTP tool calls (OpenAPI)
                ▼
   ┌─────────────────────────────────┐
   │   KAYAN PLATFORM API (this)     │
   │  9 tool groups · 72 endpoints   │
   │  business rules · notifications │
   └────────────┬────────────────────┘
                │
   ┌────────────┴────────────────────┐
   │  Data layer (33 seed datasets)  │
   │  beneficiaries · requests ·     │
   │  casework · finance · CRM       │
   └─────────────────────────────────┘
                │
        ┌───────┴────────┐
        ▼                ▼
   HUMAN STAFF      REPORTING
   kanban board     dashboards
```

The agent layer owns conversation, language and speech. The platform API owns **data, rules and side effects**. They meet at the OpenAPI contract, which is what makes the mock swappable for the real stack later.

## 2. Channel model

| | WhatsApp | Voice / SIP |
|---|---|---|
| Entry | `POST /whatsapp/inbound` | `POST /voice/call-start` |
| Identity | sender number → beneficiary | ANI (caller ID) → beneficiary |
| Context returned | file status, completeness, open requests, tickets, next payment | same |
| Output | text (`reply_ar`), templates | TTS of `reply_ar` |
| Constraint | 24-hour session window; outside it, templates only | call duration; no visual confirmation |
| Escalation | `POST /crm/tickets` | `POST /voice/transfer/{call_id}` |
| Best for | document collection, IBANs, long forms, links | quick status, reminders, low-literacy callers |

**Design rule:** anything numeric or spelled (IBAN, national ID, amounts) is preferably captured or confirmed on WhatsApp. Voice confirms digit-by-digit and never reads a full IBAN back aloud.

## 3. Components

- **`backend/main.py`** — app assembly, CORS, root/health.
- **`backend/store.py`** — in-memory store, lookups (`beneficiary_by_phone` normalizes `05…`/`9665…`/`+9665…`), derived helpers: `file_completeness()`, `wa_window()`, `ticket_sla()`, notification log, id sequences.
- **`backend/routers/*.py`** — one file per domain area; OpenAPI tags group them into agent toolsets.

## 4. Key derived logic (why it lives server-side, not in the prompt)

**File completeness** walks all 10 sections plus the mandatory document checklist and returns the exact gaps. Keeping this server-side means every channel asks for the same thing and the agent can't hallucinate what's missing.

**Need score** = `100 − (per-capita monthly net ÷ 15)`, clamped 0–100, where per-capita net = (income − documented obligations − counted living costs) ÷ household size. It drives the committee queue ordering so that "support is provided according to need and priority" is mechanical rather than manual. *This formula is a placeholder — Kayan's real weighting should replace it.*

**SLA countdown** per department (24h for beneficiary services, 48h elsewhere), producing the `23س 57د` string seen in the ticket screenshots.

**WhatsApp window** — 24h from last inbound message; free-form sends outside it are rejected with 409 and the agent is told to use a template.

## 5. State & lifecycle

Reference data (programs, request types, sections, document types, FAQ) is read-only. Everything transactional is mutable in memory and **resets on restart**, which is what makes agent test runs repeatable. Re-run `scripts/generate_seed.py` to regenerate deterministically.

## 6. Business rules enforced

| Rule | Response |
|---|---|
| Phone already registered | `registered:true` + "log in instead" |
| Category not served by Kayan | 409 on file creation; polite referral reply |
| File incomplete on submit | 409 with the exact missing fields and documents |
| Support request before file approval | 409 + "complete your file first" |
| Amount over program ceiling | 409 + the ceiling |
| Mandatory doc marked "لا يوجد" when not permitted | 409 |
| Luxury spending as a counted cost | 409 (per the guide) |
| Committee before any completed case step | 409 |
| Second decision on one request | 409 |
| Enrolling a non-accepted request | 409 |
| Paying twice, or with no IBAN | 409 |
| Free-form WhatsApp outside the 24h window | 409 → use template |

## 7. Integration path to production

Each mock module maps to a real system without changing the contract:

| Mock module | Production target |
|---|---|
| Beneficiary file, dependents, documents | ERPNext / Frappe (or the existing نظام رافد) |
| Programs, requests, casework, committee | ERPNext custom doctypes |
| Enrollment, disbursement, payment | ERPNext Accounting + bank file/API |
| Tickets, kanban, WhatsApp inbox | Chatwoot or Frappe Helpdesk |
| Voice/SIP | LiveKit Agents + SIP trunk (or existing PBX) |
| Notifications | WhatsApp Business API + SMS gateway |

See `06_OPEN_SOURCE_STACK.md`.
