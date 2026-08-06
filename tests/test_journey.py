"""
The casework → committee → enrollment → payment pipeline.

Everything from open-case onward used to be unreachable: open-case 500'd
(binding a Python list to a TEXT column), so no case existed for the next three
endpoints, and /enrollments 500'd on a column that was never in the schema.
"""
import pytest


@pytest.fixture
def request_id(client, beneficiary):
    sr = client.post("/support-requests", json={
        "beneficiary_id": beneficiary, "request_type_id": "REQ-HSG-01",
        "case_description_ar": "الاسرة متاخرة عن سداد الايجار لثلاثة اشهر",
        "requested_amount_sar": 800})
    assert sr.status_code == 200, sr.text
    return sr.json()["support_request_id"]


def test_request_blocked_before_file_approval(client, db):
    created = client.post("/beneficiary/create-file", json={
        "phone": "0555777001", "case_type": "CT-IND", "orphan_category_id": "OC-UNK",
        "full_name_ar": "غير معتمد", "city": "الرياض"}).json()
    r = client.post("/support-requests", json={
        "beneficiary_id": created["beneficiary_id"], "request_type_id": "REQ-HSG-01",
        "case_description_ar": "طلب قبل الاعتماد", "requested_amount_sar": 100})
    assert r.status_code == 409


def test_amount_over_ceiling_is_refused(client, beneficiary):
    r = client.post("/support-requests", json={
        "beneficiary_id": beneficiary, "request_type_id": "REQ-HSG-01",
        "case_description_ar": "مبلغ فوق السقف المعتمد", "requested_amount_sar": 10_000_000})
    assert r.status_code == 409


def test_full_casework_pipeline(client, db, request_id):
    case = client.post(f"/support-requests/{request_id}/open-case")
    assert case.status_code == 200, case.text
    cid = case.json()["case_id"]
    assert db.get_support_request(request_id)["stage"] == "under_study"

    # committee is blocked until at least one step is completed
    assert client.post(f"/cases/{cid}/submit-to-committee",
                       json={"recommendation_ar": "سابق لاوانه"}).status_code == 409

    assert client.post(f"/cases/{cid}/schedule-step", json={
        "step_id": "CS-FIELD", "scheduled_at": "2026-09-01T10:00:00Z"}).status_code == 200
    assert len(db.get_case(cid)["steps"]) == 1

    # the same step cannot be scheduled twice
    assert client.post(f"/cases/{cid}/schedule-step", json={
        "step_id": "CS-FIELD", "scheduled_at": "2026-09-02T10:00:00Z"}).status_code == 409

    assert client.post(f"/cases/{cid}/record-findings", json={
        "step_id": "CS-FIELD", "findings_ar": "تم التحقق"}).status_code == 200
    assert db.get_case(cid)["steps"][0]["status"] == "completed"

    assert client.post(f"/cases/{cid}/submit-to-committee",
                       json={"recommendation_ar": "التوصية بالقبول"}).status_code == 200
    assert db.get_support_request(request_id)["stage"] == "committee"
    assert db.get_case(cid)["recommendation_ar"] == "التوصية بالقبول"


def test_second_case_on_same_request_is_refused(client, request_id):
    assert client.post(f"/support-requests/{request_id}/open-case").status_code == 200
    assert client.post(f"/support-requests/{request_id}/open-case").status_code == 409


def test_decision_stores_the_approved_amount(client, db, request_id):
    """The router wrote `approved_amount_sar`; the column is `amount`. Every
    decision therefore stored NULL, and nothing could ever be enrolled."""
    db.update_support_request(request_id, {"stage": "committee"})
    r = client.post(f"/support-requests/{request_id}/decision", json={
        "decision": "accepted", "approved_amount_sar": 750, "reason_ar": "استيفاء الشروط"})
    assert r.status_code == 200

    stored = db.decision_for(request_id)
    assert stored["amount"] == 750
    assert stored["approved_amount_sar"] == 750
    assert stored["beneficiary_id"] is not None
    assert db.get_support_request(request_id)["stage"] == "decided"


def test_decision_requires_a_reason(client, db, request_id):
    """The console's accept modal omitted reason_ar and got a 422."""
    db.update_support_request(request_id, {"stage": "committee"})
    r = client.post(f"/support-requests/{request_id}/decision",
                    json={"decision": "accepted", "approved_amount_sar": 750})
    assert r.status_code == 422


def test_decision_cannot_exceed_ceiling(client, db, request_id):
    db.update_support_request(request_id, {"stage": "committee"})
    r = client.post(f"/support-requests/{request_id}/decision", json={
        "decision": "accepted", "approved_amount_sar": 10_000_000, "reason_ar": "سبب"})
    assert r.status_code == 409


def test_enrollment_schedule_and_payment(client, db, request_id, beneficiary):
    db.update_support_request(request_id, {"stage": "committee"})
    client.post(f"/support-requests/{request_id}/decision", json={
        "decision": "accepted", "approved_amount_sar": 900, "reason_ar": "استيفاء الشروط"})

    en = client.post("/enrollments", json={
        "support_request_id": request_id, "type": "monthly_recurring", "months": 3})
    assert en.status_code == 200, en.text
    assert en.json()["disbursements_created"] == 3
    assert en.json()["schedule"][0]["amount"] == 300

    # already enrolled
    assert client.post("/enrollments", json={
        "support_request_id": request_id, "type": "one_time", "months": 1}).status_code == 409

    disb = client.get(f"/beneficiary/{beneficiary}/disbursements").json()
    assert disb["count"] == 3
    did = disb["disbursements"][0]["id"]

    client.post(f"/disbursements/{did}/approve", json={"approved_by": "STF-06"})
    assert db.get_disbursement(did)["status"] == "approved"

    pay = client.post(f"/disbursements/{did}/pay")
    assert pay.status_code == 200
    assert db.get_disbursement(did)["status"] == "paid"
    assert client.post(f"/disbursements/{did}/pay").status_code == 409


def test_payment_blocked_without_iban(client, db):
    created = client.post("/beneficiary/create-file", json={
        "phone": "0555777002", "case_type": "CT-IND", "orphan_category_id": "OC-UNK",
        "full_name_ar": "بدون ايبان", "city": "الرياض"}).json()
    bid = created["beneficiary_id"]
    db.update_beneficiary(bid, {"status": "approved"})
    sr = client.post("/support-requests", json={
        "beneficiary_id": bid, "request_type_id": "REQ-HSG-01",
        "case_description_ar": "طلب بدون بيانات بنكية", "requested_amount_sar": 600}).json()
    db.update_support_request(sr["support_request_id"], {"stage": "committee"})
    client.post(f"/support-requests/{sr['support_request_id']}/decision", json={
        "decision": "accepted", "approved_amount_sar": 600, "reason_ar": "سبب"})
    en = client.post("/enrollments", json={
        "support_request_id": sr["support_request_id"], "type": "one_time", "months": 1}).json()
    did = en["schedule"][0]["id"]

    r = client.post(f"/disbursements/{did}/pay")
    assert r.status_code == 409
    assert "ايبان" in r.json()["detail"]


def test_zero_amount_decision_cannot_be_enrolled(client, db, request_id):
    db.update_support_request(request_id, {"stage": "committee"})
    client.post(f"/support-requests/{request_id}/decision", json={
        "decision": "declined", "reason_ar": "لا يوجد احتياج"})
    r = client.post("/enrollments", json={
        "support_request_id": request_id, "type": "one_time", "months": 1})
    assert r.status_code == 409


# ------------------------------------------- numbers dictated over the phone
def test_check_phone_says_how_much_of_the_number_it_heard(client):
    """Answering "not registered" to half a dictated number sent the agent
    straight on to create-file with a four-digit phone.

    Reporting how many digits arrived is what lets it ask for the REST of
    the number instead of starting the whole exchange again — which on a
    real call ran four times before the caller gave up.
    """
    r = client.post("/registration/check-phone", json={"phone": "0171"})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert body["registered"] is False
    assert body["digits_heard"] == 4
    assert "0 1 7 1" in body["reply_ar"], "read back digit by digit, for TTS"

    ok = client.post("/registration/check-phone",
                     json={"phone": "0501234567"}).json()
    assert ok["valid"] is True


def test_a_file_cannot_be_created_under_half_a_number(client, db):
    """The file's phone is how the association reaches the family, and the
    key check-phone matches on later. Half a number is a beneficiary nobody
    can call and a duplicate waiting to happen."""
    before = len(db.load_table("beneficiaries"))
    r = client.post("/beneficiary/create-file", json={
        "phone": "0171", "case_type": "CT-IND",
        "orphan_category_id": "OC-UNK",
        "full_name_ar": "اختبار الرقم الناقص", "city": "الرياض"})
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_phone"
    assert detail["reply_ar"]
    # …and nothing was written — the point of the whole exercise.
    assert len(db.load_table("beneficiaries")) == before
