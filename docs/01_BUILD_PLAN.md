# Kayan AI Agent Platform — Build Plan

## 1. Objective

Stand up a complete, testable simulation of Kayan's beneficiary management platform so AI agents on **phone (SIP)** and **WhatsApp** can be built and validated end-to-end before touching any production system. The agents must be able to take a beneficiary from first contact to an approved, funded, tracked case — capturing information conversationally, writing it into the ERP/CRM, chasing what's missing, and keeping the full history synced.

## 2. Scope

**In scope**
- Mock backend simulating the whole domain: registration, the 10-section beneficiary file, dependents, documents, financial profile, 5 programs / 43 request types, casework, committee decisions, enrollment, monthly disbursements, payments, sponsorships, events.
- CRM: kanban ticket board, SLA countdown, department routing, WhatsApp session windows, ticket statistics.
- Channel entry points for SIP voice and WhatsApp with caller identification and context loading.
- Seed data with referential integrity, Arabic-first.
- OpenAPI contract importable directly into an agent builder.
- Agent design for each use case with Arabic dialogues.

**Out of scope (mocked)**
- Real telephony carriers, real WhatsApp Business API, real bank transfers, real national-ID/Absher/Najiz/SIMAH verification, production security, persistence. All represented deterministically so agent logic can be exercised without external dependencies.

## 3. Modules

| # | Module | Tag in API | Core tools |
|---|---|---|---|
| 1 | Registration & beneficiary file | `1 · التسجيل وملف المستفيد` | check-phone, OTP, eligibility, create-file, section updates, completeness, submit, dependents, documents, finances, FAQ |
| 2 | CRM tickets & kanban | `2 · نظام التذاكر CRM` | list/create/move/assign/reply, kanban, stats |
| 3 | WhatsApp channel | `3 · قناة الواتساب` | inbound, send, send-template, session window, templates |
| 4 | Voice / SIP channel | `4 · قناة الاتصال الهاتفي` | call-start, transfer, call-end, call log |
| 5 | Support requests | `5 · طلبات الدعم` | programs, request types, search, create, add-detail, status |
| 6 | Casework & committee | `6 · دراسة الحالة واللجنة` | open case, schedule step, findings, submit to committee, decision, queue |
| 7 | Enrollment & disbursement | `7 · الاعتماد والصرف` | enrol, disbursements, approve, pay, payment history, run |
| 8 | Sponsorships & events | `8 · الكفالات والفعاليات` | sponsorships, events, register |
| 9 | Beneficiary 360 | `9 · السجل الشامل` | history, search, overview report |

## 4. Phases

**Phase 0 — Foundations** *(done)*
Domain model from the client's guide + screenshots; deterministic seed generator; FastAPI skeleton with auto-OpenAPI.

**Phase 1 — Tool layer** *(done)*
72 endpoints with bot-facing descriptions and `reply_ar`; business rules enforced as 409/422; 83-assertion end-to-end test.

**Phase 2 — Agent build** *(your side)*
Import the OpenAPI spec. Build the agents in `docs/04_AGENT_DESIGN.md`. Wire Arabic STT/TTS for voice and the WhatsApp inbox for chat. Configure the shared escalation path.

**Phase 3 — Test & tune**
Run the sample dialogues as regression scripts. Validate slot-filling, tool selection, the 409 paths, and Arabic quality across Najdi/Hijazi/Eastern dialects. Measure task-completion, containment (resolved without a human), and data-capture accuracy.

**Phase 4 — Pilot integration**
Replace mock endpoints with the real stack one module at a time, keeping the contract (see `06_OPEN_SOURCE_STACK.md`). Recommended pilot order: (1) FAQ + status queries — read-only, low risk; (2) ticket creation + routing; (3) registration and file completion; (4) support requests; (5) disbursement queries. Casework and committee decisions stay human — the agent schedules and records, it does not decide.

**Phase 5 — Production hardening**
Auth, PDPL compliance review, audit logging, encryption at rest, role-based access, retention policy, human-in-the-loop checkpoints on anything financial.

## 5. Cross-cutting requirements

- **Arabic-first**, including Saudi dialects on voice. Every user-facing string is Arabic; English is available on the FAQ for staff.
- **Channel parity** — the same tools serve WhatsApp and voice; only the presentation differs.
- **Eligibility gate** — Kayan serves الأيتام ذوو الظروف الخاصة (مجهولو الأبوين). The bot confirms the category before collecting a full file, exactly as the officer does in the guide's WhatsApp sample.
- **Never promise an outcome** — "التسجيل في النظام لا يعني قبول الطلب" is baked into the submit response and must be echoed by agents.
- **Human escalation** available on every path.

## 6. Acceptance criteria

- [x] Full journey callable as tools, returning realistic data
- [x] Registration → file → submit runs end-to-end, blocked correctly when incomplete
- [x] Completeness tool returns exact missing fields and documents
- [x] Support request blocked until file approved
- [x] Casework → committee → decision → WhatsApp + SMS notification
- [x] Accepted request → enrollment → schedule → payment → history
- [x] Kanban board, SLA countdown and stats match the admin screenshots
- [x] WhatsApp 24-hour window enforced
- [x] OpenAPI spec importable into an agent builder

## 7. Risks

| Risk | Mitigation |
|---|---|
| Agent captures wrong financial data | Every write is echoed back for confirmation; casework verifies in the field visit |
| Dialect misrecognition on voice | Confirm critical values (IBAN, amounts, ID) digit-by-digit; prefer WhatsApp for numeric capture |
| Beneficiary expects approval from the bot | Fixed disclaimer on submit and request creation; agent never predicts a decision |
| Sensitive data on a consumer channel | Identity confirmed before disclosure; no full ID/IBAN read back on voice |
| Vulnerable callers in distress | Escalation to a human researcher on any distress signal — see the escalation rule in `04_AGENT_DESIGN.md` |
