"""
End-to-end smoke test — walks a brand-new beneficiary through the entire
journey exactly as an AI agent would, then exercises the CRM and channels.
Run:  PYTHONPATH=. python scripts/smoke_test.py
"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient
from backend.main import app
from backend import store as db

c = TestClient(app)
PASS = FAIL = 0


def step(title, r, expect=200, show=None):
    global PASS, FAIL
    ok = r.status_code == expect
    mark = "OK " if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{mark}] {title:52} HTTP {r.status_code}")
    if not ok:
        print("        ->", str(r.json())[:300])
    elif show:
        d = r.json()
        for k in show:
            v = d
            for part in k.split("."):
                v = (v or {}).get(part) if isinstance(v, dict) else None
            print(f"        {k}: {str(v)[:150]}")
    return r.json() if r.status_code < 500 else {}


print("=" * 78)
print("PART 1 — WhatsApp intake, eligibility, and file creation")
print("=" * 78)

step("root", c.get("/"), show=["counts.beneficiaries", "counts.request_types"])

PHONE = "0555550123"
step("check-phone (new number)", c.post("/registration/check-phone", json={"phone": PHONE}),
     show=["registered"])
otp = step("send-otp", c.post("/registration/send-otp", json={"phone": PHONE}), show=["debug_code"])
step("verify-otp (wrong code)", c.post("/registration/verify-otp",
     json={"phone": PHONE, "code": "0000"}), show=["verified"])
step("verify-otp (correct)", c.post("/registration/verify-otp",
     json={"phone": PHONE, "code": otp["debug_code"]}), show=["verified"])

step("eligibility — NOT served category", c.post("/registration/check-eligibility",
     json={"orphan_category_id": "OC-FATHER"}), show=["eligible", "reply_ar"])
step("eligibility — served category", c.post("/registration/check-eligibility",
     json={"orphan_category_id": "OC-UNK"}), show=["eligible"])

nb = step("create-file", c.post("/beneficiary/create-file", json={
    "phone": PHONE, "case_type": "CT-IND", "orphan_category_id": "OC-UNK",
    "full_name_ar": "سعد بن عبدالله الشمري", "national_id": "1099887766", "city": "الرياض"}),
    show=["beneficiary_id", "file_no", "reply_ar"])
BID = nb["beneficiary_id"]

step("check-phone (now registered)", c.post("/registration/check-phone", json={"phone": PHONE}),
     show=["registered", "file_no"])

print()
print("=" * 78)
print("PART 2 — Progressive file completion (what the agent chases)")
print("=" * 78)

comp = step("completeness (fresh file)", c.get(f"/beneficiary/{BID}/completeness"),
            show=["completion_pct", "ready_to_submit"])
print(f"        missing fields: {len(comp['missing_fields'])}, "
      f"missing docs: {len(comp['missing_documents'])}")

step("submit too early (expect 409)", c.post(f"/beneficiary/{BID}/submit"), expect=409)

step("update SEC-BASIC", c.patch(f"/beneficiary/{BID}/section/SEC-BASIC", json={"values": {
    "birth_date": "1998-03-11", "gender": "male", "marital_status": "متزوج",
    "nationality": "سعودي"}}))
step("reject unknown field (expect 422)", c.patch(f"/beneficiary/{BID}/section/SEC-BASIC",
     json={"values": {"favourite_colour": "blue"}}), expect=422)
step("update SEC-CONTACT", c.patch(f"/beneficiary/{BID}/section/SEC-CONTACT", json={"values": {
    "alt_mobile": "0555550999", "email": "saad@example.com"}}))
step("update SEC-BANK", c.patch(f"/beneficiary/{BID}/section/SEC-BANK", json={"values": {
    "bank_name": "مصرف الراجحي", "iban": "SA0380000000608010167519",
    "account_holder_name": "سعد بن عبدالله الشمري"}}))
step("update SEC-EDU", c.patch(f"/beneficiary/{BID}/section/SEC-EDU", json={"values": {
    "education_level": "ثانوي", "employment_status": "لا يعمل",
    "employer": "-", "monthly_salary": 0}}))
step("update SEC-HOUSING", c.patch(f"/beneficiary/{BID}/section/SEC-HOUSING", json={"values": {
    "district": "حي النرجس", "housing_type": "شقة", "ownership_proof_type": "HP-RENT",
    "rooms": 3, "monthly_rent": 1800, "monthly_bills": 900}}))
step("update SEC-HEALTH", c.patch(f"/beneficiary/{BID}/section/SEC-HEALTH", json={"values": {
    "chronic_conditions": "لا يوجد", "disability": False,
    "has_health_insurance": False, "monthly_medication_cost": 0}}))
step("update SEC-EXTRA", c.patch(f"/beneficiary/{BID}/section/SEC-EXTRA", json={"values": {
    "income_sources": [{"type": "الضمان الاجتماعي", "amount_sar": 2100}],
    "has_social_security": True, "has_citizen_account": False}}))
step("update SEC-JOIN", c.patch(f"/beneficiary/{BID}/section/SEC-JOIN", json={"values": {
    "join_reason": "احتياج سكني", "referral_source": "الواتساب", "previous_support": False}}))

step("add dependent (spouse)", c.post(f"/beneficiary/{BID}/dependents", json={
    "name_ar": "نورة الشمري", "relationship_ar": "الزوجة", "birth_date": "2000-01-05",
    "gender": "female"}), show=["dependents_count"])
step("add dependent (child)", c.post(f"/beneficiary/{BID}/dependents", json={
    "name_ar": "عبدالله الشمري", "relationship_ar": "ابن", "birth_date": "2021-06-01",
    "gender": "male", "education_stage": "روضة"}), show=["dependents_count"])

print("  -- documents --")
for dt in ["DOC-ID", "DOC-ORPHAN", "DOC-FAMILY", "DOC-HOUSING", "DOC-SIMAH"]:
    c.patch(f"/beneficiary/{BID}/documents/{dt}", json={"status": "verified"})
print("        5 mandatory docs marked verified")
step("salary cert -> not_available (لا يوجد)",
     c.patch(f"/beneficiary/{BID}/documents/DOC-SALARY", json={"status": "not_available"}),
     show=["document.note_ar"])
step("citizen account -> ineligible (عدم الاهلية)",
     c.patch(f"/beneficiary/{BID}/documents/DOC-CITIZEN", json={"status": "ineligible"}),
     show=["document.note_ar"])
step("ID cannot be 'not_available' (expect 409)",
     c.patch(f"/beneficiary/{BID}/documents/DOC-ID", json={"status": "not_available"}), expect=409)
c.patch(f"/beneficiary/{BID}/documents/DOC-SOCIAL", json={"status": "verified"})

print("  -- financial profile --")
step("add obligation (rent)", c.post(f"/beneficiary/{BID}/obligations",
     json={"type_id": "OB-RENT", "monthly_sar": 1800}))
step("add obligation (BNPL tabby)", c.post(f"/beneficiary/{BID}/obligations",
     json={"type_id": "OB-BNPL", "monthly_sar": 350}))
step("add cost (groceries)", c.post(f"/beneficiary/{BID}/person-costs",
     json={"type_id": "PC-GROCERY", "monthly_sar": 1400}),
     show=["per_capita_monthly_sar", "need_score"])
step("luxury cost rejected (expect 409)", c.post(f"/beneficiary/{BID}/person-costs",
     json={"type_id": "PC-LUXURY", "monthly_sar": 500}), expect=409)

comp = step("completeness (after filling)", c.get(f"/beneficiary/{BID}/completeness"),
            show=["completion_pct", "ready_to_submit", "reply_ar"])
step("submit file", c.post(f"/beneficiary/{BID}/submit"), show=["status", "reply_ar"])

print()
print("=" * 78)
print("PART 3 — Support request, casework, committee decision")
print("=" * 78)

step("request too early: file not approved (409)", c.post("/support-requests", json={
    "beneficiary_id": BID, "request_type_id": "REQ-HSG-01",
    "case_description_ar": "احتاج مساعدة في سداد الايجار المتاخر"}), expect=409)

# approve the file the way a staff member would
db.get_beneficiary(BID)["status"] = "approved"
print("        [staff action] file approved")

step("programs list", c.get("/programs"), show=["count"])
step("request-type search 'ايجار'", c.get("/request-types/search", params={"q": "ايجار"}),
     show=["results"])
step("over-ceiling amount rejected (409)", c.post("/support-requests", json={
    "beneficiary_id": BID, "request_type_id": "REQ-HSG-01",
    "case_description_ar": "طلب مبالغ فيه لاختبار السقف", "requested_amount_sar": 999999}),
     expect=409)

sr = step("create support request", c.post("/support-requests", json={
    "beneficiary_id": BID, "request_type_id": "REQ-HSG-01",
    "case_description_ar": "الاسرة متاخرة عن سداد الايجار لثلاثة اشهر وصدر انذار اخلاء من المالك",
    "requested_amount_sar": 18000, "internal_classification": "عاجل", "channel": "whatsapp"}),
    show=["support_request_id", "reply_ar"])
SR = sr["support_request_id"]

step("agent asks for more detail", c.patch(f"/support-requests/{SR}/add-detail", json={
    "additional_detail_ar": "الانذار صادر بتاريخ 1 يوليو ومدته 30 يوم"}), show=["reply_ar"])

case = step("open case study", c.post(f"/support-requests/{SR}/open-case",
            params={"researcher_id": "STF-04"}), show=["case_id", "stage"])
CASE = case["case_id"]
step("committee too early (expect 409)", c.post(f"/cases/{CASE}/submit-to-committee",
     json={"recommendation_ar": "قبول"}), expect=409)
step("schedule field visit", c.post(f"/cases/{CASE}/schedule-step", json={
    "step_id": "CS-FIELD", "scheduled_at": "2026-08-02T10:00:00Z",
    "assigned_staff_id": "STF-04"}), show=["reply_ar"])
step("schedule psychological assessment", c.post(f"/cases/{CASE}/schedule-step", json={
    "step_id": "CS-PSYCH", "scheduled_at": "2026-08-04T12:00:00Z",
    "assigned_staff_id": "STF-05"}))
step("record findings", c.post(f"/cases/{CASE}/record-findings", json={
    "step_id": "CS-FIELD",
    "findings_ar": "تم التحقق من السكن وعدد التابعين ومطابقة البيانات للواقع"}))
step("submit to committee", c.post(f"/cases/{CASE}/submit-to-committee", json={
    "recommendation_ar": "التوصية بالقبول ضمن السقف المعتمد"}), show=["stage"])
step("committee queue (need-ranked)", c.get("/committee/queue"), show=["count"])
dec = step("record decision: accepted", c.post(f"/support-requests/{SR}/decision", json={
    "decision": "accepted", "approved_amount_sar": 18000,
    "reason_ar": "استيفاء الشروط ووجود احتياج مؤكد ومستندات مكتملة"}),
    show=["decision.decision_ar", "message_sent_ar"])
step("duplicate decision blocked (409)", c.post(f"/support-requests/{SR}/decision", json={
    "decision": "declined", "reason_ar": "تكرار"}), expect=409)
step("get request with case + decision", c.get(f"/support-requests/{SR}"), show=["reply_ar"])

print()
print("=" * 78)
print("PART 4 — Enrollment, disbursement schedule, payment")
print("=" * 78)

en = step("enrol (12 monthly instalments)", c.post("/enrollments", json={
    "support_request_id": SR, "type": "monthly_recurring", "months": 12,
    "start_date": "2026-08-01"}), show=["enrollment.monthly_amount_sar", "reply_ar"])
step("duplicate enrollment blocked (409)", c.post("/enrollments", json={
    "support_request_id": SR, "type": "one_time", "months": 1}), expect=409)
disb = step("list disbursements", c.get(f"/beneficiary/{BID}/disbursements"),
            show=["count", "reply_ar"])
DIS = disb["disbursements"][0]["id"]
step("approve disbursement", c.post(f"/disbursements/{DIS}/approve", json={"approved_by": "STF-06"}))
step("pay disbursement", c.post(f"/disbursements/{DIS}/pay"), show=["reply_ar"])
step("double payment blocked (409)", c.post(f"/disbursements/{DIS}/pay"), expect=409)
step("payment history", c.get(f"/beneficiary/{BID}/payments"), show=["total_sar"])
step("finance disbursement run", c.get("/finance/disbursement-run", params={"days": 60}),
     show=["count", "total_sar"])

print()
print("=" * 78)
print("PART 5 — CRM: tickets, kanban, SLA, stats")
print("=" * 78)

tk = step("open ticket from WhatsApp", c.post("/crm/tickets", json={
    "subject_ar": "استفسار عن موعد الصرف", "channel": "whatsapp", "phone": PHONE,
    "department_id": "DEP-FIN", "priority": "medium",
    "first_message_ar": "متى ينزل مبلغ الايجار؟"}), show=["ticket_id", "sla.remaining_ar"])
TK = tk["ticket_id"]
step("assign ticket", c.patch(f"/crm/tickets/{TK}/assign", json={"staff_id": "STF-02"}),
     show=["assigned_to_ar"])
step("move to in_progress", c.patch(f"/crm/tickets/{TK}/status", json={"status": "in_progress"}),
     show=["status_ar"])
step("reply on ticket", c.post(f"/crm/tickets/{TK}/reply", json={
    "body_ar": "تم اعتماد الصرف وسينزل المبلغ خلال يومين عمل", "sender": "bot"}))
step("invalid status (expect 422)", c.patch(f"/crm/tickets/{TK}/status",
     json={"status": "banana"}), expect=422)
step("get ticket w/ conversation", c.get(f"/crm/tickets/{TK}"), show=["messages"])
kb = step("kanban board", c.get("/crm/kanban"))
print("        columns:", [f"{col['title_ar']}={col['count']}" for col in kb["columns"]])
step("ticket stats", c.get("/crm/stats"),
     show=["total", "closure_rate_pct", "avg_first_response_hours", "top_department_ar"])
step("close ticket", c.patch(f"/crm/tickets/{TK}/status", json={"status": "closed"}))

print()
print("=" * 78)
print("PART 6 — Channels: WhatsApp session + SIP voice call")
print("=" * 78)

wa = step("inbound WhatsApp (known beneficiary)", c.post("/whatsapp/inbound", json={
    "from_number": PHONE, "text_ar": "السلام عليكم متى ينزل المبلغ؟"}),
    show=["known_beneficiary", "window.remaining_ar", "suggested_greeting_ar"])
step("whatsapp session window", c.get(f"/whatsapp/session/{PHONE}"), show=["window.open"])
step("send free-form whatsapp", c.post("/whatsapp/send",
     params={"to": PHONE, "body_ar": "تم اعتماد طلبكم"}))
step("send template", c.post("/whatsapp/send-template", json={
    "to": PHONE, "template_id": "TPL-DOCS",
    "params": {"request_no": SR, "docs": "تعريف الراتب"}}), show=["body_ar"])
step("inbound WhatsApp (unknown number)", c.post("/whatsapp/inbound", json={
    "from_number": "0500000001", "text_ar": "ابغى اسجل"}),
    show=["known_beneficiary", "suggested_greeting_ar"])

call = step("SIP call start (known caller)", c.post("/voice/call-start", json={
    "from_number": PHONE, "sip_call_id": "sip-test-1@kayan.pbx"}),
    show=["identified", "greeting_ar", "context.next_disbursement.due_date"])
CALL = call["call_id"]
step("transfer to human", c.post(f"/voice/transfer/{CALL}", json={
    "reason_ar": "المستفيد يطلب التحدث مع موظف", "department_id": "DEP-BEN"}),
    show=["ticket_id", "reply_ar"])
step("end call", c.post(f"/voice/call-end/{CALL}", json={
    "outcome": "escalated_to_agent", "intent": "استفسار عن صرف", "duration_sec": 132}))
step("notifications log", c.get("/notifications"), show=["count"])

print()
print("=" * 78)
print("PART 7 — 360 history, search, FAQ, reports")
print("=" * 78)

step("FAQ search 'مشهد الضمان'", c.get("/faqs/search", params={"q": "مشهد الضمان"}),
     show=["results"])
step("FAQ search English", c.get("/faqs/search", params={"q": "dependents", "lang": "en"}))
step("search by phone", c.get("/beneficiaries/search", params={"q": PHONE}), show=["count"])
step("search by file no", c.get("/beneficiaries/search", params={"q": nb["file_no"]}), show=["count"])
h = step("360 history", c.get(f"/beneficiary/{BID}/history"),
         show=["beneficiary.name_ar", "completeness.pct", "household.size",
               "payments.total_sar", "financial.need_score"])
print(f"        requests={len(h['support_requests'])} enrollments={len(h['enrollments'])} "
      f"tickets={len(h['tickets'])} disbursements={h['disbursements']['count']}")
step("association overview report", c.get("/reports/overview"), show=["payments_total_sar"])
step("sponsorships", c.get("/sponsorships"), show=["count", "monthly_total_sar"])
ev = step("events", c.get("/events", params={"status": "scheduled"}), show=["count"])
step("register for event", c.post(f"/events/{ev['events'][0]['id']}/register",
     json={"beneficiary_id": BID}), show=["reply_ar"])
step("404 on unknown beneficiary", c.get("/beneficiary/BEN-9999/history"), expect=404)

print()
print("=" * 78)
print(f"RESULT: {PASS} passed, {FAIL} failed")
print("=" * 78)
sys.exit(1 if FAIL else 0)
