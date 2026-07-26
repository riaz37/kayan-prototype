# API / Tools Reference

Base URL (local): `http://localhost:8000` · interactive docs `/docs` · spec `openapi/kayan_openapi.json`.

**72 operations in 9 tool groups.** Conversational endpoints return `reply_ar` (speech/print-ready Arabic) alongside structured data.

Response conventions: **404** = unknown id · **409** = business-rule violation (surface it, don't retry) · **422** = invalid field or value.

## Quick start for agents

```bash
# 1. every conversation starts here
curl -X POST localhost:8000/whatsapp/inbound \
  -H 'Content-Type: application/json' \
  -d '{"from_number":"0501234567","text_ar":"السلام عليكم"}'

# ...or for a phone call
curl -X POST localhost:8000/voice/call-start \
  -H 'Content-Type: application/json' \
  -d '{"from_number":"0501234567"}'

# 2. what does this beneficiary still owe us?
curl localhost:8000/beneficiary/BEN-1001/completeness

# 3. everything about them, in one call
curl localhost:8000/beneficiary/BEN-1001/history
```

## The five tools that carry most of the work

| Tool | Why it matters |
|---|---|
| `POST /whatsapp/inbound` · `POST /voice/call-start` | Identify the caller and load full context in one call |
| `GET /beneficiary/{id}/completeness` | The exact missing fields + documents, with a ready Arabic sentence |
| `GET /request-types/search` | Maps free text ("محتاج مساعدة بالإيجار") to the right request type + program |
| `GET /beneficiary/{id}/history` | The 360 record — file, household, finances, requests, money, tickets |
| `GET /faqs/search` | 18 answers drawn from the association's own guide |

---

## Full endpoint list

### 1 · التسجيل وملف المستفيد | Registration & Beneficiary File

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/beneficiary/create-file` | Create a new beneficiary file |
| `GET` | `/beneficiary/{beneficiary_id}` | Get a beneficiary file |
| `GET` | `/beneficiary/{beneficiary_id}/completeness` | What is still missing from the file |
| `POST` | `/beneficiary/{beneficiary_id}/dependents` | Add a dependent (اضافة تابع) |
| `GET` | `/beneficiary/{beneficiary_id}/dependents` | List dependents / household |
| `GET` | `/beneficiary/{beneficiary_id}/documents` | Document checklist and status |
| `PATCH` | `/beneficiary/{beneficiary_id}/documents/{document_type_id}` | Record a document as uploaded / not available / ineligible |
| `GET` | `/beneficiary/{beneficiary_id}/financial-profile` | Get the financial profile & need score |
| `POST` | `/beneficiary/{beneficiary_id}/obligations` | Add a documented monthly obligation |
| `POST` | `/beneficiary/{beneficiary_id}/person-costs` | Add a per-person monthly living cost |
| `PATCH` | `/beneficiary/{beneficiary_id}/section/{section_id}` | Update one section of the data form |
| `POST` | `/beneficiary/{beneficiary_id}/submit` | Submit the file for review (اضافة سجل) |
| `GET` | `/faqs/search` | Search the beneficiary FAQ |
| `GET` | `/reference/case-types` | List file types (new beneficiary vs foster family) |
| `GET` | `/reference/form-sections` | List the 10 data form sections |
| `GET` | `/reference/housing-proofs` | List accepted housing ownership proofs |
| `GET` | `/reference/obligation-types` | List monthly obligation types |
| `GET` | `/reference/orphan-categories` | List orphan categories and which are served |
| `GET` | `/reference/person-cost-types` | List per-person monthly cost types |
| `POST` | `/registration/check-eligibility` | Check eligibility for Kayan's served category |
| `POST` | `/registration/check-phone` | Check if a phone number is already registered |
| `POST` | `/registration/send-otp` | Send an OTP verification code |
| `POST` | `/registration/verify-otp` | Verify the OTP code |

### 2 · نظام التذاكر CRM | Tickets & Kanban

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/crm/departments` | List departments and their SLA |
| `GET` | `/crm/kanban` | Get the kanban board |
| `GET` | `/crm/staff` | List staff (فريق العمل) |
| `GET` | `/crm/stats` | Ticket statistics dashboard |
| `GET` | `/crm/tickets` | List tickets with filters |
| `POST` | `/crm/tickets` | Open a ticket from any channel |
| `GET` | `/crm/tickets/{ticket_id}` | Get a ticket with its full conversation |
| `PATCH` | `/crm/tickets/{ticket_id}/assign` | Assign a ticket to a staff member |
| `POST` | `/crm/tickets/{ticket_id}/reply` | Post a reply on a ticket |
| `PATCH` | `/crm/tickets/{ticket_id}/status` | Move a ticket across the kanban board |

### 3 · قناة الواتساب | WhatsApp Channel

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/notifications` | List sent notifications (WhatsApp / SMS log) |
| `POST` | `/whatsapp/inbound` | Handle an inbound WhatsApp message |
| `POST` | `/whatsapp/send` | Send a WhatsApp message |
| `POST` | `/whatsapp/send-template` | Send an approved WhatsApp template |
| `GET` | `/whatsapp/session/{phone}` | Check a WhatsApp session window |
| `GET` | `/whatsapp/templates` | List approved message templates |

### 4 · قناة الاتصال الهاتفي | Voice / SIP Channel

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/voice/call-end/{call_id}` | End a voice call and log the outcome |
| `POST` | `/voice/call-start` | Start a voice call session (SIP) |
| `GET` | `/voice/calls` | List call sessions |
| `POST` | `/voice/transfer/{call_id}` | Transfer a call to a human agent |

### 5 · طلبات الدعم | Support Requests

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/beneficiary/{beneficiary_id}/support-requests` | List a beneficiary's support requests |
| `GET` | `/programs` | List the 5 association programs |
| `GET` | `/programs/{program_id}/request-types` | List request types under a program |
| `GET` | `/request-types/search` | Find the right request type from free text |
| `POST` | `/support-requests` | Submit a support request (طلب دعم) |
| `GET` | `/support-requests/{request_id}` | Get a support request with its casework and decision |
| `PATCH` | `/support-requests/{request_id}/add-detail` | Append more detail to a request |

### 6 · دراسة الحالة واللجنة | Casework & Committee

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/cases/{case_id}/record-findings` | Record findings for a completed step |
| `POST` | `/cases/{case_id}/schedule-step` | Schedule a case study step (visit / interview / assessment) |
| `POST` | `/cases/{case_id}/submit-to-committee` | Submit the case to the specialized committee |
| `GET` | `/committee/queue` | List cases awaiting committee review |
| `GET` | `/reference/case-steps` | List case study step types |
| `POST` | `/support-requests/{request_id}/decision` | Record the committee decision and notify the beneficiary |
| `POST` | `/support-requests/{request_id}/open-case` | Open a case study for a request |

### 7 · الاعتماد والصرف | Enrollment & Disbursement

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/beneficiary/{beneficiary_id}/disbursements` | List scheduled and paid disbursements |
| `GET` | `/beneficiary/{beneficiary_id}/enrollments` | List a beneficiary's program enrollments |
| `GET` | `/beneficiary/{beneficiary_id}/payments` | Payment history |
| `POST` | `/disbursements/{disbursement_id}/approve` | Approve a disbursement for payment (التعميد بالصرف) |
| `POST` | `/disbursements/{disbursement_id}/pay` | Execute payment to the beneficiary's IBAN |
| `POST` | `/enrollments` | Enrol an approved beneficiary into a program |
| `GET` | `/finance/disbursement-run` | Upcoming disbursement run |

### 8 · الكفالات والفعاليات | Sponsorships & Events

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/events` | List events and activities (الفعاليات والانشطة) |
| `POST` | `/events/{event_id}/register` | Register a beneficiary for an event |
| `GET` | `/sponsorships` | List sponsorships (الكفالات) |

### 9 · السجل الشامل | Beneficiary 360

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/beneficiaries/search` | Search beneficiaries by phone, name, file number or ID |
| `GET` | `/beneficiary/{beneficiary_id}/history` | Complete beneficiary history (السجل الشامل) |
| `GET` | `/reports/overview` | Association-wide overview report |

### system

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Platform info |
| `GET` | `/health` | Health check |
---

## Worked example — full journey in curl

```bash
BASE=localhost:8000
PHONE=0555550123

# registration
curl -sX POST $BASE/registration/check-phone -H 'Content-Type: application/json' -d "{\"phone\":\"$PHONE\"}"
CODE=$(curl -sX POST $BASE/registration/send-otp -H 'Content-Type: application/json' -d "{\"phone\":\"$PHONE\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["debug_code"])')
curl -sX POST $BASE/registration/verify-otp -H 'Content-Type: application/json' -d "{\"phone\":\"$PHONE\",\"code\":\"$CODE\"}"
curl -sX POST $BASE/registration/check-eligibility -H 'Content-Type: application/json' -d '{"orphan_category_id":"OC-UNK"}'

BID=$(curl -sX POST $BASE/beneficiary/create-file -H 'Content-Type: application/json' \
  -d "{\"phone\":\"$PHONE\",\"case_type\":\"CT-IND\",\"orphan_category_id\":\"OC-UNK\",\"full_name_ar\":\"سعد بن عبدالله الشمري\",\"city\":\"الرياض\"}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["beneficiary_id"])')

# file completion
curl -s $BASE/beneficiary/$BID/completeness
curl -sX PATCH $BASE/beneficiary/$BID/section/SEC-HOUSING -H 'Content-Type: application/json' \
  -d '{"values":{"district":"حي النرجس","housing_type":"شقة","ownership_proof_type":"HP-RENT","rooms":3,"monthly_rent":1800,"monthly_bills":900}}'
curl -sX POST $BASE/beneficiary/$BID/dependents -H 'Content-Type: application/json' \
  -d '{"name_ar":"نورة الشمري","relationship_ar":"الزوجة"}'
curl -sX PATCH $BASE/beneficiary/$BID/documents/DOC-SALARY -H 'Content-Type: application/json' -d '{"status":"not_available"}'
curl -sX POST $BASE/beneficiary/$BID/submit

# support request -> casework -> decision
curl -s "$BASE/request-types/search?q=ايجار"
SR=$(curl -sX POST $BASE/support-requests -H 'Content-Type: application/json' \
  -d "{\"beneficiary_id\":\"$BID\",\"request_type_id\":\"REQ-HSG-01\",\"case_description_ar\":\"متأخر عن الإيجار ثلاثة أشهر وصدر إنذار إخلاء\",\"requested_amount_sar\":18000}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["support_request_id"])')
CASE=$(curl -sX POST "$BASE/support-requests/$SR/open-case?researcher_id=STF-04" | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')
curl -sX POST $BASE/cases/$CASE/schedule-step -H 'Content-Type: application/json' \
  -d '{"step_id":"CS-FIELD","scheduled_at":"2026-08-02T10:00:00Z","assigned_staff_id":"STF-04"}'
curl -sX POST $BASE/cases/$CASE/record-findings -H 'Content-Type: application/json' \
  -d '{"step_id":"CS-FIELD","findings_ar":"تم التحقق من السكن والتابعين"}'
curl -sX POST $BASE/cases/$CASE/submit-to-committee -H 'Content-Type: application/json' \
  -d '{"recommendation_ar":"التوصية بالقبول ضمن السقف المعتمد"}'
curl -sX POST $BASE/support-requests/$SR/decision -H 'Content-Type: application/json' \
  -d '{"decision":"accepted","approved_amount_sar":18000,"reason_ar":"استيفاء الشروط"}'

# money
curl -sX POST $BASE/enrollments -H 'Content-Type: application/json' \
  -d "{\"support_request_id\":\"$SR\",\"type\":\"monthly_recurring\",\"months\":12}"
curl -s $BASE/beneficiary/$BID/disbursements
curl -s $BASE/beneficiary/$BID/history
```

## Useful seed ids for testing

- **Approved beneficiary:** any with `status:"approved"` in `data/beneficiaries.json`
- **Phone to test identification:** any `sections.SEC-CONTACT.mobile`
- **Request types:** `REQ-HSG-01` (سداد إيجار, recurring), `REQ-ILM-01` (منحة دراسية), `REQ-TRN-05` (خطاب شفاعة, no cash)
- **Departments:** `DEP-BEN` (24h SLA), `DEP-FIN`, `DEP-IT`
- **Staff:** `STF-02` (خدمات المستفيدين), `STF-04` (باحث اجتماعي), `STF-05` (أخصائية نفسية), `STF-06` (محاسب)
- **Templates:** `TPL-DOCS`, `TPL-ACCEPT`, `TPL-DECLINE`, `TPL-VISIT`, `TPL-PAY`
