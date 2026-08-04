"""
End-to-end journey check — walks one beneficiary from an inbound WhatsApp
message all the way to a paid disbursement, exercising every stage the guide
describes, and asserts the result was actually PERSISTED (not just returned).

Run:  DATA_DIR=/tmp/x PYTHONPATH=. python scripts/journey_check.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402
from backend import store as db  # noqa: E402

c = TestClient(app)
PASS = FAIL = 0
FAILURES = []

PHONE = "0555550" + os.environ.get("JOURNEY_SUFFIX", "123")


def check(title, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"[ OK ] {title}")
    else:
        FAIL += 1
        FAILURES.append(f"{title} — {detail}")
        print(f"[FAIL] {title}\n         {detail}")
    return ok


def call(method, path, expect=200, **kw):
    r = getattr(c, method)(path, **kw)
    body = None
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:200]}
    check(f"{method.upper()} {path} -> {expect}", r.status_code == expect,
          f"got {r.status_code}: {str(body)[:220]}")
    return body if isinstance(body, dict) else {}


print("=" * 78)
print("PART 1 — inbound WhatsApp, eligibility, file creation")
print("=" * 78)

call("post", "/whatsapp/inbound", json={"from_number": PHONE, "text_ar": "السلام عليكم"})
elig = call("post", "/registration/check-eligibility", json={"orphan_category_id": "OC-UNK"})
check("OC-UNK is eligible", elig.get("eligible") is True, str(elig))
no = call("post", "/registration/check-eligibility", json={"orphan_category_id": "OC-FATHER"})
check("OC-FATHER is refused", no.get("eligible") is False, str(no))

created = call("post", "/beneficiary/create-file", json={
    "phone": PHONE, "case_type": "CT-IND", "orphan_category_id": "OC-UNK",
    "full_name_ar": "سعد بن عبدالله القحطاني", "city": "الرياض"})
BID = created.get("beneficiary_id")
check("file created", bool(BID), str(created))

check("check-phone now finds the file",
      call("post", "/registration/check-phone", json={"phone": PHONE}).get("registered") is True)
call("post", "/beneficiary/create-file", expect=409, json={
    "phone": PHONE, "case_type": "CT-IND", "orphan_category_id": "OC-UNK",
    "full_name_ar": "مكرر", "city": "الرياض"})

print()
print("=" * 78)
print("PART 2 — the data form, dependents, documents, finances")
print("=" * 78)

SECTIONS = {
    "SEC-BASIC": {"national_id": "1012345678", "birth_date": "1985-01-01", "gender": "male",
                  "marital_status": "متزوج", "nationality": "سعودي"},
    "SEC-EXTRA": {"income_sources": [{"type": "راتب", "amount": 4000}],
                  "has_social_security": False, "has_citizen_account": True},
    "SEC-JOIN": {"join_reason": "احتياج مالي", "referral_source": "الموقع", "previous_support": "لا"},
    "SEC-BANK": {"bank_name": "الراجحي", "iban": "SA0380000000608010167519",
                 "account_holder_name": "سعد بن عبدالله القحطاني"},
    "SEC-CONTACT": {"alt_mobile": "0500000000", "email": "saad@example.com"},
    "SEC-EDU": {"education_level": "ثانوي", "employment_status": "يعمل",
                "employer": "شركة", "monthly_salary": 4000},
    "SEC-HOUSING": {"district": "النرجس", "housing_type": "ايجار",
                    "ownership_proof_type": "عقد ايجار", "rooms": 3,
                    "monthly_rent": 1500, "monthly_bills": 300},
    "SEC-HEALTH": {"chronic_conditions": "لا يوجد", "disability": "لا يوجد",
                   "has_health_insurance": False, "monthly_medication_cost": 0},
}
for sid, values in SECTIONS.items():
    call("patch", f"/beneficiary/{BID}/section/{sid}", json={"values": values})

call("patch", f"/beneficiary/{BID}/section/SEC-EDU", expect=422,
     json={"values": {"not_a_real_field": 1}})

stored = db.get_beneficiary(BID)
check("sections persisted to the database",
      stored["sections"]["SEC-BANK"]["iban"] == "SA0380000000608010167519",
      str(stored["sections"].get("SEC-BANK")))

call("post", f"/beneficiary/{BID}/dependents",
     json={"name_ar": "سارة", "relationship_ar": "ابنة", "birth_date": "2015-04-01"})
deps = call("post", f"/beneficiary/{BID}/dependents",
            json={"name_ar": "نورة", "relationship_ar": "الزوجة"})
check("dependents_count reported", deps.get("dependents_count") == 2, str(deps))
check("dependents persisted", len(db.deps_for(BID)) == 2)

docs = call("get", f"/beneficiary/{BID}/documents")
for d in docs.get("documents", []):
    dt = db.by_id["document_type"].get(d["document_type_id"], {})
    if dt.get("na_allowed"):
        status = "not_available"
    elif dt.get("ineligible_allowed"):
        status = "ineligible"
    else:
        status = "uploaded"
    call("patch", f"/beneficiary/{BID}/documents/{d['document_type_id']}",
         json={"status": status})

after = {d["document_type_id"]: d["status"] for d in db.docs_for(BID)}
check("document status persisted", "missing" not in after.values(), str(after))
call("patch", f"/beneficiary/{BID}/documents/DOC-ID", expect=409,
     json={"status": "not_available"})

call("post", f"/beneficiary/{BID}/obligations",
     json={"type_id": "OB-RENT", "monthly_sar": 1500, "documented": True})
fin = call("post", f"/beneficiary/{BID}/person-costs",
           json={"type_id": "PC-GROCERY", "monthly_sar": 900})
call("post", f"/beneficiary/{BID}/person-costs", expect=409,
     json={"type_id": "PC-LUXURY", "monthly_sar": 500})

stored_fin = db.finance_for(BID)
check("income persisted from SEC-EDU", stored_fin["monthly_income"] == 4000,
      f"monthly_income={stored_fin['monthly_income']}")
check("household_size persisted", stored_fin["household_size"] == 3,
      f"household_size={stored_fin['household_size']}")
check("obligations persisted", len(stored_fin["obligations"]) == 1, str(stored_fin["obligations"]))
check("need_score reflects real inputs", 0 < stored_fin["need_score"] <= 100,
      f"need_score={stored_fin['need_score']}")

comp = call("get", f"/beneficiary/{BID}/completeness")
check("file is complete", comp.get("ready_to_submit") is True,
      f"missing={comp.get('missing_fields')} docs={comp.get('missing_documents')}")
call("post", f"/beneficiary/{BID}/submit")
check("status persisted as submitted", db.get_beneficiary(BID)["status"] == "submitted")

print()
print("=" * 78)
print("PART 3 — support request, casework, committee")
print("=" * 78)

call("post", "/support-requests", expect=409, json={
    "beneficiary_id": BID, "request_type_id": "REQ-HSG-01",
    "case_description_ar": "طلب قبل الاعتماد يجب ان يرفض", "requested_amount_sar": 1000})

db.update_beneficiary(BID, {"status": "approved", "approved_at": db.now_iso()})
check("file approved for the next stage", db.get_beneficiary(BID)["status"] == "approved")

types = call("get", "/request-types/search", params={"q": "ايجار"})
check("request-type search finds rent", types.get("count", 0) > 0, str(types)[:200])
RT = types["results"][0]["id"]
ceiling = types["results"][0]["ceiling_sar"]

call("post", "/support-requests", expect=409, json={
    "beneficiary_id": BID, "request_type_id": RT,
    "case_description_ar": "مبلغ يتجاوز السقف المعتمد للطلب",
    "requested_amount_sar": (ceiling or 1000) + 50000})

sr = call("post", "/support-requests", json={
    "beneficiary_id": BID, "request_type_id": RT,
    "case_description_ar": "الاسرة متاخرة عن سداد الايجار لثلاثة اشهر وصدر انذار اخلاء",
    "requested_amount_sar": min(ceiling or 5000, 5000)})
SR = sr.get("support_request_id")
check("support request created", bool(SR), str(sr))

detail = call("patch", f"/support-requests/{SR}/add-detail",
              json={"additional_detail_ar": "صدر انذار اخلاء بتاريخ 1 يوليو"})
check("added detail PERSISTED",
      "انذار اخلاء بتاريخ" in (db.get_support_request(SR)["case_description_ar"] or ""),
      str(db.get_support_request(SR)["case_description_ar"])[:160])

case = call("post", f"/support-requests/{SR}/open-case")
CASE = case.get("case_id")
check("case study opened", bool(CASE), str(case))
check("stage moved to under_study PERSISTED",
      db.get_support_request(SR)["stage"] == "under_study",
      db.get_support_request(SR)["stage"])

call("post", f"/cases/{CASE}/submit-to-committee", expect=409,
     json={"recommendation_ar": "لا يجوز قبل اكمال خطوة"})

call("post", f"/cases/{CASE}/schedule-step",
     json={"step_id": "CS-FIELD", "scheduled_at": "2026-09-02T10:00:00Z"})
check("scheduled step PERSISTED", len(db.get_case(CASE)["steps"]) == 1,
      str(db.get_case(CASE)["steps"]))

call("post", f"/cases/{CASE}/record-findings",
     json={"step_id": "CS-FIELD", "findings_ar": "تم التحقق من السكن وعدد التابعين"})
check("findings PERSISTED",
      db.get_case(CASE)["steps"][0]["status"] == "completed",
      str(db.get_case(CASE)["steps"][0]))

call("post", f"/cases/{CASE}/submit-to-committee",
     json={"recommendation_ar": "التوصية بالقبول ضمن السقف المعتمد"})
check("stage moved to committee PERSISTED",
      db.get_support_request(SR)["stage"] == "committee",
      db.get_support_request(SR)["stage"])

queue = call("get", "/committee/queue")
check("request appears in the committee queue",
      any(r["support_request_id"] == SR for r in queue.get("queue", [])),
      str(queue)[:200])
mine = next((r for r in queue.get("queue", []) if r["support_request_id"] == SR), {})
check("queue shows the real household size", mine.get("household_size") == 3, str(mine))

APPROVED = 4500
dec = call("post", f"/support-requests/{SR}/decision", json={
    "decision": "accepted", "approved_amount_sar": APPROVED,
    "reason_ar": "استيفاء الشروط ووجود احتياج مؤكد"})
check("decision returned the approved amount",
      dec.get("decision", {}).get("approved_amount_sar") == APPROVED, str(dec)[:200])
stored_dec = db.decision_for(SR)
check("approved amount PERSISTED (was NULL)", stored_dec["amount"] == APPROVED,
      f"amount={stored_dec['amount']}")
check("decision links the beneficiary", stored_dec["beneficiary_id"] == BID)
check("stage moved to decided PERSISTED", db.get_support_request(SR)["stage"] == "decided")
call("post", f"/support-requests/{SR}/decision", expect=409, json={
    "decision": "declined", "reason_ar": "قرار مكرر"})

print()
print("=" * 78)
print("PART 4 — enrollment, disbursement schedule, payment")
print("=" * 78)

en = call("post", "/enrollments",
          json={"support_request_id": SR, "type": "monthly_recurring", "months": 3})
check("three instalments generated", en.get("disbursements_created") == 3, str(en)[:200])
check("instalment amount split correctly",
      en["schedule"][0]["amount"] == round(APPROVED / 3, 2), str(en.get("schedule"))[:200])
call("post", "/enrollments", expect=409,
     json={"support_request_id": SR, "type": "one_time", "months": 1})

disb = call("get", f"/beneficiary/{BID}/disbursements")
check("schedule persisted", disb.get("count") == 3, str(disb)[:200])
DIS = disb["disbursements"][0]["id"]

call("post", f"/disbursements/{DIS}/approve", json={"approved_by": "STF-06"})
check("approval PERSISTED", db.get_disbursement(DIS)["status"] == "approved",
      db.get_disbursement(DIS)["status"])

pay = call("post", f"/disbursements/{DIS}/pay")
check("payment recorded", bool(pay.get("payment", {}).get("reference")), str(pay)[:200])
check("disbursement marked paid PERSISTED", db.get_disbursement(DIS)["status"] == "paid")
call("post", f"/disbursements/{DIS}/pay", expect=409)

run = call("get", "/finance/disbursement-run", params={"days": 120})
check("payment run names the beneficiary",
      all(d.get("name_ar") is not None for d in run.get("disbursements", [])[:5]),
      str(run.get("disbursements", [])[:1]))

print()
print("=" * 78)
print("PART 5 — CRM, channels, reporting")
print("=" * 78)

tk = call("post", "/crm/tickets", json={
    "subject_ar": "استفسار عن الدفعة القادمة", "channel": "whatsapp", "phone": PHONE,
    "department_id": "DEP-FIN", "priority": "high",
    "first_message_ar": "متى تنزل الدفعة؟"})
TK = tk.get("ticket_id")
check("ticket opened and matched to the file", bool(TK), str(tk))

call("post", f"/crm/tickets/{TK}/reply",
     json={"body_ar": "ملاحظة داخلية للفريق", "sender": "agent", "send_to_whatsapp": False})
msgs = db.messages_for(TK)
internal = [m for m in msgs if m.get("is_internal")]
check("internal note PERSISTED as internal", len(internal) == 1, str(msgs))

call("patch", f"/crm/tickets/{TK}/assign", json={"staff_id": "STF-02"})
call("patch", f"/crm/tickets/{TK}/status", json={"status": "closed"})
closed = call("get", f"/crm/tickets/{TK}")
check("ticket closed and assigned PERSISTED",
      closed.get("status") == "closed" and closed.get("assigned_to") == "STF-02", str(closed)[:200])

call_start = call("post", "/voice/call-start", json={"from_number": PHONE})
CALL = call_start.get("call_id")
check("caller identified from the file", call_start.get("identified") is True, str(call_start)[:200])
call("post", f"/voice/call-end/{CALL}",
     json={"outcome": "resolved_by_bot", "intent": "استفسار", "duration_sec": 145})
calls = call("get", "/voice/calls", params={"limit": 5})
mine_call = next((x for x in calls.get("calls", []) if x["id"] == CALL), {})
check("call outcome PERSISTED", mine_call.get("outcome") == "resolved_by_bot", str(mine_call)[:200])
check("call exposes from_number/duration_sec for the console",
      mine_call.get("from_number") and mine_call.get("duration_sec") == 145, str(mine_call)[:200])

call("get", "/crm/kanban")
call("get", "/crm/stats")
call("get", "/reports/overview")
call("get", "/sponsorships")
call("get", "/events")
call("get", "/notifications")
hist = call("get", f"/beneficiary/{BID}/history")
check("360 history shows the payment",
      hist.get("payments", {}).get("total_sar", 0) > 0, str(hist.get("payments"))[:160])
check("360 history shows the decision",
      any(r.get("approved_amount_sar") == APPROVED for r in hist.get("support_requests", [])),
      str(hist.get("support_requests"))[:200])
check("360 history shows household of 3",
      hist.get("household", {}).get("size") == 3, str(hist.get("household", {}).get("size")))

search = call("get", "/beneficiaries/search", params={"q": PHONE})
check("phone search resolves the file",
      any(r["id"] == BID for r in search.get("results", [])), str(search)[:200])

print()
print("=" * 78)
print(f"RESULT: {PASS} passed, {FAIL} failed")
if FAILURES:
    print("-" * 78)
    for f in FAILURES:
        print("  •", f)
print("=" * 78)
sys.exit(1 if FAIL else 0)
