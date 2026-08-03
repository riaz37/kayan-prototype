"""
Use cases 5 & 6 — what happens AFTER approval: enrollment into a program,
the monthly disbursement schedule, payments to the beneficiary's IBAN,
sponsorships (الكفالة), events, and the unified 360 history.
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import timedelta

from backend import store as db

router = APIRouter()
T_FIN = "7 · الاعتماد والصرف | Enrollment & Disbursement"
T_KAF = "8 · الكفالات والفعاليات | Sponsorships & Events"
T_360 = "9 · السجل الشامل | Beneficiary 360"


# ============================================================ enrollment
class EnrollIn(BaseModel):
    support_request_id: str = Field(..., examples=["SR-20001"])
    type: str = Field("one_time", examples=["one_time", "monthly_recurring"])
    months: int = Field(1, ge=1, le=36, examples=[12],
                        description="Number of monthly instalments for recurring support")
    start_date: Optional[str] = Field(None, examples=["2026-08-01"])


@router.post("/enrollments", tags=[T_FIN],
             summary="Enrol an approved beneficiary into a program",
             description="Creates the enrollment for an ACCEPTED request and generates the monthly "
                         "disbursement schedule. Returns 409 if the request was not accepted or is "
                         "already enrolled.")
def create_enrollment(body: EnrollIn):
    conn = db._get_conn()
    sr_row = conn.execute("SELECT * FROM support_requests WHERE id = ?",
                         (body.support_request_id,)).fetchone()
    if not sr_row:
        raise HTTPException(404, "Support request not found")
    sr = dict(sr_row)
    dec = db.decision_for(body.support_request_id)
    if not dec or dec["decision"] != "accepted":
        raise HTTPException(409, "Only accepted requests can be enrolled")
    existing = conn.execute("SELECT COUNT(*) as cnt FROM enrollments WHERE support_request_id = ?",
                           (body.support_request_id,)).fetchone()["cnt"]
    if existing > 0:
        raise HTTPException(409, "This request is already enrolled")
    approved_amount = dec.get("amount", 0)
    if approved_amount <= 0:
        raise HTTPException(409, "Approved amount is zero — nothing to disburse")

    months = body.months if body.type == "monthly_recurring" else 1
    monthly = round(approved_amount / months, 2)
    start = db.parse((body.start_date + "T00:00:00Z") if body.start_date else db.now_iso())
    eid = db.next_id("enr", "ENR-")
    en = {"id": eid, "beneficiary_id": sr["beneficiary_id"], "program_id": sr["program_id"],
          "support_request_id": sr["id"], "type": body.type,
          "monthly_amount": monthly if body.type == "monthly_recurring" else 0.0,
          "total_approved": approved_amount,
          "start_date": start.date().isoformat(),
          "end_date": (start + timedelta(days=30 * months)).date().isoformat(),
          "status": "active", "enrolled_at": db.now_iso()}
    conn.execute(
        """INSERT INTO enrollments (id, beneficiary_id, program_id, status, enrolled_at)
           VALUES (?,?,?,?,?)""",
        (eid, en["beneficiary_id"], en["program_id"], en["status"], en["enrolled_at"]))
    conn.commit()

    created = []
    for m in range(months):
        due = start + timedelta(days=30 * m)
        did = db.next_id("dis", "DIS-")
        d = {"id": did, "beneficiary_id": sr["beneficiary_id"],
             "program_id": sr["program_id"], "enrollment_id": eid,
             "amount": monthly, "due_date": due.date().isoformat(), "status": "scheduled"}
        conn.execute(
            """INSERT INTO disbursements (id, beneficiary_id, program_id, enrollment_id, amount, due_date, status, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (d["id"], d["beneficiary_id"], d["program_id"], d["enrollment_id"],
             d["amount"], d["due_date"], d["status"], db.now_iso()))
        conn.commit()
        created.append(d)
    return {"enrollment": en, "disbursements_created": len(created),
            "schedule": created,
            "reply_ar": f"تم اعتماد صرف {approved_amount} ريال "
                        f"{'على ' + str(months) + ' دفعات شهرية' if months > 1 else 'دفعة واحدة'} "
                        f"ضمن {db.program_name(sr['program_id'])}."}


@router.get("/beneficiary/{beneficiary_id}/enrollments", tags=[T_FIN],
            summary="List a beneficiary's program enrollments",
            description="Every program the beneficiary is enrolled in, with amounts and status.")
def list_enrollments(beneficiary_id: str):
    if not db.get_beneficiary(beneficiary_id):
        raise HTTPException(404, "Beneficiary not found")
    rows = db.enrollments_for(beneficiary_id)
    return {"beneficiary_id": beneficiary_id, "count": len(rows),
            "enrollments": [{**e, "program_ar": db.program_name(e["program_id"])} for e in rows]}


# ============================================================ disbursements
@router.get("/beneficiary/{beneficiary_id}/disbursements", tags=[T_FIN],
            summary="List scheduled and paid disbursements",
            description="The monthly transfer schedule with totals paid and upcoming — this answers "
                        "'كم اتحول لي وكم باقي'.")
def list_disbursements(beneficiary_id: str,
                       status: Optional[str] = Query(None, examples=["scheduled"])):
    if not db.get_beneficiary(beneficiary_id):
        raise HTTPException(404, "Beneficiary not found")
    rows = db.disbursements_for(beneficiary_id)
    if status:
        rows = [d for d in rows if d["status"] == status]
    rows = sorted(rows, key=lambda d: d["due_date"])
    paid = round(sum(d["amount"] for d in rows if d["status"] == "paid"), 2)
    upcoming = [d for d in rows if d["status"] != "paid"]
    nxt = upcoming[0] if upcoming else None
    return {"beneficiary_id": beneficiary_id, "count": len(rows),
            "total_paid_sar": paid,
            "total_upcoming_sar": round(sum(d["amount"] for d in upcoming), 2),
            "next_disbursement": nxt, "disbursements": rows,
            "reply_ar": (f"اجمالي المصروف لكم {paid} ريال." +
                         (f" الدفعة القادمة {nxt['amount']} ريال بتاريخ {nxt['due_date']}."
                          if nxt else " لا توجد دفعات قادمة حاليا."))}


class ApproveDisbIn(BaseModel):
    approved_by: str = Field("STF-06", examples=["STF-06"])


@router.post("/disbursements/{disbursement_id}/approve", tags=[T_FIN],
             summary="Approve a disbursement for payment (التعميد بالصرف)",
             description="Moves a scheduled disbursement to approved so finance can pay it.")
def approve_disbursement(disbursement_id: str, body: ApproveDisbIn):
    d = db.by_id["disbursement"].get(disbursement_id)
    if not d:
        raise HTTPException(404, "Disbursement not found")
    if d["status"] == "paid":
        raise HTTPException(409, "Already paid")
    d["status"] = "approved"
    d["approved_by"] = body.approved_by
    db.update_disbursement(disbursement_id, {"status": "approved", "approved_by": body.approved_by})
    return {"disbursement": d}


@router.post("/disbursements/{disbursement_id}/pay", tags=[T_FIN],
             summary="Execute payment to the beneficiary's IBAN",
             description="Records a bank transfer against the disbursement and sends an SMS notice. "
                         "Blocked (409) if the beneficiary has no IBAN on file.")
def pay_disbursement(disbursement_id: str):
    d = db.by_id["disbursement"].get(disbursement_id)
    if not d:
        raise HTTPException(404, "Disbursement not found")
    if d["status"] == "paid":
        raise HTTPException(409, "Already paid")
    b = db.get_beneficiary(d["beneficiary_id"])
    bank = b["sections"]["SEC-BANK"] if b else {}
    if not bank.get("iban"):
        raise HTTPException(409, "لا يوجد ايبان مسجل في ملف المستفيد — يجب تحديث البيانات البنكية اولا")
    import random as _r
    p = {"id": db.next_id("pay", "PAY-"), "disbursement_id": disbursement_id,
         "beneficiary_id": d["beneficiary_id"], "amount": d["amount"],
         "method": "bank_transfer", "reference": f"KYN{_r.randint(100000, 999999)}",
         "paid_at": db.now_iso()}
    db.insert_payment(p)
    db.payments.append(p)
    db.update_disbursement(disbursement_id, {"status": "paid"})
    d["status"] = "paid"
    msg = db.render_template("TPL-PAY", amount=d["amount"],
                             reason=db.program_name(d["program_id"]))
    db.send_notification("sms", b["sections"]["SEC-CONTACT"]["mobile"], msg, kind="payment")
    return {"payment": p, "disbursement": d,
            "reply_ar": f"تم صرف مبلغ {d['amount']} ريال الى حسابكم البنكي برقم مرجعي {p['reference']}."}


@router.get("/beneficiary/{beneficiary_id}/payments", tags=[T_FIN],
            summary="Payment history",
            description="All settled payments with bank reference numbers.")
def list_payments(beneficiary_id: str):
    if not db.get_beneficiary(beneficiary_id):
        raise HTTPException(404, "Beneficiary not found")
    rows = sorted(db.payments_for(beneficiary_id), key=lambda p: p["paid_at"], reverse=True)
    return {"beneficiary_id": beneficiary_id, "count": len(rows),
            "total_sar": round(sum(p["amount"] for p in rows), 2), "payments": rows}


@router.get("/finance/disbursement-run", tags=[T_FIN],
            summary="Upcoming disbursement run",
            description="Everything due in the next N days across all beneficiaries — the monthly "
                        "payment run the finance team executes.")
def disbursement_run(days: int = Query(30, ge=1, le=120)):
    cutoff = (db.now() + timedelta(days=days)).date().isoformat()
    rows = [d for d in db.disbursements
            if d["status"] in ("scheduled", "approved", "pending_approval") and d["due_date"] <= cutoff]
    rows.sort(key=lambda d: d["due_date"])
    by_prog = {}
    for d in rows:
        k = db.program_name(d["program_id"])
        by_prog[k] = round(by_prog.get(k, 0) + d["amount"], 2)
    return {"window_days": days, "count": len(rows),
            "total_sar": round(sum(d["amount"] for d in rows), 2),
            "by_program_ar": by_prog, "disbursements": rows[:50]}


# ============================================================ sponsorships & events
@router.get("/sponsorships", tags=[T_KAF],
            summary="List sponsorships (الكفالات)",
            description="Sponsor-to-beneficiary kafala records, restricted or unrestricted.")
def list_sponsorships(beneficiary_id: Optional[str] = Query(None)):
    rows = db.sponsorships
    if beneficiary_id:
        rows = [s for s in rows if s["beneficiary_id"] == beneficiary_id]
    out = []
    for s in rows:
        sp = next((x for x in db.sponsors if x["id"] == s["sponsor_id"]), {})
        out.append({**s, "sponsor_name_ar": sp.get("name_ar"), "sponsor_type": sp.get("type")})
    return {"count": len(out), "sponsorships": out,
            "monthly_total_sar": round(sum(s["monthly_amount_sar"] for s in rows), 2)}


@router.get("/events", tags=[T_KAF],
            summary="List events and activities (الفعاليات والانشطة)",
            description="Association events with capacity and registration counts.")
def list_events(status: Optional[str] = Query(None, examples=["scheduled"])):
    rows = db.events
    if status:
        rows = [e for e in rows if e["status"] == status]
    return {"count": len(rows),
            "events": [{**e, "program_ar": db.program_name(e["program_id"])} for e in rows]}


class RegisterEventIn(BaseModel):
    beneficiary_id: str = Field(..., examples=["BEN-1001"])


@router.post("/events/{event_id}/register", tags=[T_KAF],
             summary="Register a beneficiary for an event",
             description="Registers an approved beneficiary for an event; blocked when the event is "
                         "full or already completed.")
def register_event(event_id: str, body: RegisterEventIn):
    e = db.by_id["event"].get(event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    if e["status"] == "completed":
        raise HTTPException(409, "الفعالية منتهية")
    if e["registered"] >= e["capacity"]:
        raise HTTPException(409, "اكتمل العدد لهذه الفعالية")
    if not db.get_beneficiary(body.beneficiary_id):
        raise HTTPException(404, "Beneficiary not found")
    e["registered"] += 1
    return {"event_id": event_id, "registered": e["registered"], "capacity": e["capacity"],
            "reply_ar": f"تم تسجيلكم في {e['name_ar']} بتاريخ {e['date']}."}


# ============================================================ 360 history
@router.get("/beneficiary/{beneficiary_id}/history", tags=[T_360],
            summary="Complete beneficiary history (السجل الشامل)",
            description="THE ONE CALL that returns everything about a beneficiary in one place: file "
                        "status and completeness, household, documents, finances, every support "
                        "request with its decision, enrollments, disbursements, payments, "
                        "sponsorships, tickets and channel sessions. Use it to open any conversation "
                        "with full context.")
def history(beneficiary_id: str):
    b = db.get_beneficiary(beneficiary_id)
    if not b:
        raise HTTPException(404, "Beneficiary not found")
    comp = db.file_completeness(beneficiary_id)
    reqs = []
    for r in db.requests_for(beneficiary_id):
        d = db.decision_for(r["id"])
        reqs.append({"id": r["id"], "program_ar": db.program_name(r["program_id"]),
                     "title_ar": r["title_ar"], "stage": r["stage"],
                     "requested_amount_sar": r["requested_amount_sar"],
                     "decision_ar": d["decision_ar"] if d else None,
                     "approved_amount_sar": d["amount"] if d else None,
                     "created_at": r["created_at"]})
    pays = db.payments_for(beneficiary_id)
    disb = db.disbursements_for(beneficiary_id)
    tks = db.tickets_for(beneficiary_id)
    fin = db.finance_for(beneficiary_id) or {}
    return {
        "beneficiary": {"id": b["id"], "file_no": b["file_no"], "status": b["status"],
                        "case_type": b["case_type"],
                        "name_ar": b["sections"]["SEC-BASIC"]["full_name_ar"],
                         "category_ar": db.by_id.get("orphan_category", {}).get(
                             b.get("orphan_category", ""), {}).get("name_ar"),
                        "city": b["sections"]["SEC-HOUSING"].get("city"),
                        "created_at": b["created_at"], "approved_at": b.get("approved_at")},
        "completeness": {"pct": comp["completion_pct"],
                         "missing_fields": comp["missing_fields"],
                         "missing_documents": comp["missing_documents"]},
        "household": {"size": 1 + len(db.deps_for(beneficiary_id)),
                      "dependents": db.deps_for(beneficiary_id)},
        "financial": {"monthly_income_sar": fin.get("monthly_income_sar"),
                      "total_obligations_sar": fin.get("total_obligations_sar"),
                      "total_person_costs_sar": fin.get("total_person_costs_sar"),
                      "per_capita_monthly_sar": fin.get("per_capita_monthly_sar"),
                      "need_score": fin.get("need_score")},
        "support_requests": reqs,
        "enrollments": [{**e, "program_ar": db.program_name(e["program_id"])}
                        for e in db.enrollments_for(beneficiary_id)],
        "disbursements": {"count": len(disb),
                          "paid_sar": round(sum(d["amount"] for d in disb if d["status"] == "paid"), 2),
                          "upcoming_sar": round(sum(d["amount"] for d in disb if d["status"] != "paid"), 2),
                          "rows": sorted(disb, key=lambda d: d["due_date"])},
        "payments": {"count": len(pays),
                     "total_sar": round(sum(p["amount"] for p in pays), 2),
                     "rows": sorted(pays, key=lambda p: p["paid_at"], reverse=True)[:10]},
        "sponsorships": [s for s in db.sponsorships if s["beneficiary_id"] == beneficiary_id],
        "tickets": [{"id": t["id"], "subject_ar": t["subject_ar"], "status_ar": db.status_ar(t["status"]),
                     "channel": t["channel"], "opened_at": t["opened_at"]} for t in tks],
        "channel_sessions": {
            "calls": len([c for c in db.call_sessions if c.get("beneficiary_id") == beneficiary_id]),
            "whatsapp": len([w for w in db.whatsapp_sessions if w.get("beneficiary_id") == beneficiary_id]),
        },
    }


@router.get("/beneficiaries/search", tags=[T_360],
            summary="Search beneficiaries by phone, name, file number or ID",
            description="Primary lookup for both channels — resolves a caller to their file. Phone "
                        "matching accepts 05…, 9665…, +9665… formats. Empty q returns all.")
def search_beneficiary(q: str = Query("", examples=["0501234567"]),
                       limit: int = Query(200, ge=1, le=1000)):
    ql = q.strip()
    phone = db.norm_phone(ql) if ql else None
    hits = []
    for b in db.beneficiaries:
        c = b["sections"].get("SEC-CONTACT", {})
        basic = b["sections"].get("SEC-BASIC", {})
        housing = b["sections"].get("SEC-HOUSING", {})
        # If query is empty, return all; otherwise filter
        match = not ql or \
                (phone and (db.norm_phone(c.get("mobile")) == phone or db.norm_phone(c.get("whatsapp")) == phone)) \
                or ql == b["id"] or ql == b.get("file_no") \
                or ql == (basic.get("national_id") or "") \
                or (len(ql) > 2 and ql in (basic.get("full_name_ar") or ""))
        if match:
            comp = db.file_completeness(b["id"])
            hits.append({"id": b["id"], "file_no": b.get("file_no"),
                         "name_ar": basic.get("full_name_ar", ""), "status": b.get("status"),
                         "case_type": b.get("case_type"),
                         "city": housing.get("city"),
                         "mobile": c.get("mobile"),
                         "completion_pct": comp["completion_pct"] if comp else 0,
                         "dependents": len(db.deps_for(b["id"]))})
    return {"query": q, "count": len(hits), "results": hits[:limit]}


@router.get("/reports/overview", tags=[T_360],
            summary="Association-wide overview report",
            description="Headline numbers across files, requests, programs, disbursements and "
                        "channels — the management dashboard.")
def overview():
    by_status = {}
    for b in db.beneficiaries:
        by_status[b["status"]] = by_status.get(b["status"], 0) + 1
    prog_totals = {}
    for d in db.disbursements:
        k = db.program_name(d["program_id"])
        prog_totals.setdefault(k, {"scheduled_sar": 0.0, "paid_sar": 0.0})
        key = "paid_sar" if d["status"] == "paid" else "scheduled_sar"
        prog_totals[k][key] = round(prog_totals[k][key] + d.get("amount", d.get("amount", 0)), 2)
    dec_counts = {}
    for d in db.committee_decisions:
        dec_counts[d["decision"]] = dec_counts.get(d["decision"], 0) + 1
    return {
        "beneficiaries": {"total": len(db.beneficiaries), "by_status": by_status,
                          "dependents": len(db.dependents)},
        "support_requests": {"total": len(db.support_requests),
                             "by_stage": {s: len([r for r in db.support_requests if r["stage"] == s])
                                          for s in ("submitted", "under_study", "committee", "decided")},
                             "decisions": dec_counts},
        "programs": {p["name_ar"]: len([r for r in db.support_requests if r["program_id"] == p["id"]])
                     for p in db.programs},
        "disbursements_by_program_ar": prog_totals,
        "payments_total_sar": round(sum(p["amount"] for p in db.payments), 2),
        "sponsorships": {"count": len(db.sponsorships),
                         "monthly_sar": round(sum(s["monthly_amount_sar"] for s in db.sponsorships), 2)},
        "channels": {"tickets": len(db.tickets), "calls": len(db.call_sessions),
                     "whatsapp_sessions": len(db.whatsapp_sessions)},
    }
