"""
Regression tests for the read-modify-discard class of bug.

Every endpoint here used to return 200 (or 500) while writing nothing to the
database. Each test asserts against a FRESH read from the store, never against
the response body — that is the whole point.
"""


def test_section_update_is_written(client, db, beneficiary):
    r = client.patch(f"/beneficiary/{beneficiary}/section/SEC-HOUSING",
                     json={"values": {"city": "جدة", "district": "الحمراء"}})
    assert r.status_code == 200
    stored = db.get_beneficiary(beneficiary)
    assert stored["sections"]["SEC-HOUSING"]["city"] == "جدة"
    # top-level column mirrors the section so search/lookup agree
    assert stored["city"] == "جدة"


def test_unknown_section_field_is_rejected(client, beneficiary):
    r = client.patch(f"/beneficiary/{beneficiary}/section/SEC-HOUSING",
                     json={"values": {"nope": 1}})
    assert r.status_code == 422


def test_document_status_is_written(client, db, beneficiary):
    """Used to be a hard 500: UPDATE documents SET ... updated_at, no such column."""
    r = client.patch(f"/beneficiary/{beneficiary}/documents/DOC-ID",
                     json={"status": "uploaded"})
    assert r.status_code == 200
    stored = {d["document_type_id"]: d["status"] for d in db.docs_for(beneficiary)}
    assert stored["DOC-ID"] == "uploaded"


def test_document_rules_still_enforced(client, beneficiary):
    # DOC-ID does not allow "لا يوجد"
    assert client.patch(f"/beneficiary/{beneficiary}/documents/DOC-ID",
                        json={"status": "not_available"}).status_code == 409
    # DOC-SALARY does
    assert client.patch(f"/beneficiary/{beneficiary}/documents/DOC-SALARY",
                        json={"status": "not_available"}).status_code == 200


def test_obligations_and_costs_persist(client, db, beneficiary):
    """Both endpoints used to 500 — _recalc re-parsed an already-parsed list."""
    assert client.post(f"/beneficiary/{beneficiary}/obligations",
                       json={"type_id": "OB-RENT", "monthly_sar": 1200}).status_code == 200
    assert client.post(f"/beneficiary/{beneficiary}/person-costs",
                       json={"type_id": "PC-GROCERY", "monthly_sar": 800}).status_code == 200
    fin = db.finance_for(beneficiary)
    assert [o["type_id"] for o in fin["obligations"]] == ["OB-RENT"]
    assert [c["type_id"] for c in fin["person_costs"]] == ["PC-GROCERY"]


def test_luxury_cost_is_refused(client, beneficiary):
    r = client.post(f"/beneficiary/{beneficiary}/person-costs",
                    json={"type_id": "PC-LUXURY", "monthly_sar": 500})
    assert r.status_code == 409


def test_income_and_household_reach_the_need_score(client, db, beneficiary):
    """monthly_income and household_size were computed then thrown away, so
    every file scored as income 0 / household 1."""
    client.post(f"/beneficiary/{beneficiary}/dependents",
                json={"name_ar": "ابن", "relationship_ar": "ابن"})
    client.post(f"/beneficiary/{beneficiary}/dependents",
                json={"name_ar": "بنت", "relationship_ar": "ابنة"})
    client.post(f"/beneficiary/{beneficiary}/obligations",
                json={"type_id": "OB-RENT", "monthly_sar": 1000})

    fin = db.finance_for(beneficiary)
    assert fin["monthly_income"] == 3000, "SEC-EDU salary must reach the profile"
    assert fin["household_size"] == 3, "1 beneficiary + 2 dependents"

    body = client.get(f"/beneficiary/{beneficiary}/financial-profile").json()
    assert body["per_capita_monthly_sar"] == round((3000 - 1000) / 3, 2)


def test_add_detail_appends_to_the_stored_description(client, db, beneficiary):
    """Returned the appended text but never wrote it."""
    sr = client.post("/support-requests", json={
        "beneficiary_id": beneficiary, "request_type_id": "REQ-HSG-01",
        "case_description_ar": "الوصف الاصلي للحالة", "requested_amount_sar": 500}).json()
    srid = sr["support_request_id"]

    client.patch(f"/support-requests/{srid}/add-detail",
                 json={"additional_detail_ar": "تفصيل اضافي مهم"})
    stored = db.get_support_request(srid)["case_description_ar"]
    assert "الوصف الاصلي للحالة" in stored
    assert "تفصيل اضافي مهم" in stored


def test_ticket_internal_note_stays_internal(client, db):
    tk = client.post("/crm/tickets", json={
        "subject_ar": "اختبار", "channel": "whatsapp", "phone": "0555000111",
        "department_id": "DEP-BEN"}).json()
    tid = tk["ticket_id"]
    client.post(f"/crm/tickets/{tid}/reply",
                json={"body_ar": "ملاحظة داخلية", "send_to_whatsapp": False})
    client.post(f"/crm/tickets/{tid}/reply",
                json={"body_ar": "رد للمستفيد", "send_to_whatsapp": True})

    stored = {m["body_ar"]: m["is_internal"] for m in db.messages_for(tid)}
    assert stored["ملاحظة داخلية"] == 1
    assert stored["رد للمستفيد"] == 0


def test_ticket_status_and_assignment_persist(client, db):
    tk = client.post("/crm/tickets", json={
        "subject_ar": "اختبار الحالة", "channel": "call", "department_id": "DEP-FIN"}).json()
    tid = tk["ticket_id"]
    client.patch(f"/crm/tickets/{tid}/assign", json={"staff_id": "STF-02"})
    client.patch(f"/crm/tickets/{tid}/status", json={"status": "closed"})

    row = client.get(f"/crm/tickets/{tid}").json()
    assert row["status"] == "closed"
    assert row["assigned_to"] == "STF-02"
    assert row["closed_at"] is not None

    # reopening clears closed_at rather than leaving a stale timestamp
    client.patch(f"/crm/tickets/{tid}/status", json={"status": "open"})
    assert client.get(f"/crm/tickets/{tid}").json()["closed_at"] is None


def test_call_session_outcome_persists(client):
    started = client.post("/voice/call-start", json={"from_number": "0555000222"}).json()
    cid = started["call_id"]
    client.post(f"/voice/call-end/{cid}",
                json={"outcome": "resolved_by_bot", "intent": "استفسار", "duration_sec": 90})
    calls = client.get("/voice/calls", params={"limit": 50}).json()["calls"]
    row = next(c for c in calls if c["id"] == cid)
    assert row["outcome"] == "resolved_by_bot"
    # the console reads these two names
    assert row["from_number"]
    assert row["duration_sec"] == 90
