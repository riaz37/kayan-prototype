"""
Use cases 5 & 6 — what happens AFTER approval: enrollment into a program,
the monthly disbursement schedule, payments to the beneficiary's IBAN,
sponsorships (الكفالة), events, and the unified 360 history.
"""
from typing import Optional, List
import json
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
    sr = db.get_support_request(body.support_request_id)
    if not sr:
        raise HTTPException(404, "Support request not found")
    dec = db.decision_for(body.support_request_id)
    if not dec or dec["decision"] != "accepted":
        raise HTTPException(409, "Only accepted requests can be enrolled")
    existing = conn.execute("SELECT COUNT(*) as cnt FROM enrollments WHERE support_request_id = ?",
                           (body.support_request_id,)).fetchone()["cnt"]
    if existing > 0:
        raise HTTPException(409, "This request is already enrolled")
    approved_amount = float(dec.get("amount") or 0)
    if approved_amount <= 0:
        raise HTTPException(409, {
            "message": "Approved amount is zero — nothing to disburse",
            "reply_ar": "لا يوجد مبلغ معتمد للصرف على هذا الطلب.",
        })

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

    # The enrollment and its schedule are one unit of work: a half-written
    # schedule would leave money owed with no rows to pay it against.
    created = []
    with db.tx():
        db.insert_row("enrollments", en)
        for m in range(months):
            due = start + timedelta(days=30 * m)
            d = {"id": db.next_id("dis", "DIS-"), "beneficiary_id": sr["beneficiary_id"],
                 "program_id": sr["program_id"], "enrollment_id": eid,
                 "amount": monthly, "due_date": due.date().isoformat(),
                 "status": "scheduled", "created_at": db.now_iso()}
            db.insert_row("disbursements", d)
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
    d = db.get_disbursement(disbursement_id)
    if not d:
        raise HTTPException(404, "Disbursement not found")
    if d["status"] == "paid":
        raise HTTPException(409, "Already paid")
    db.update_disbursement(disbursement_id, {"status": "approved", "approved_by": body.approved_by})
    d["status"] = "approved"
    d["approved_by"] = body.approved_by
    return {"disbursement": d}


@router.post("/disbursements/{disbursement_id}/pay", tags=[T_FIN],
             summary="Execute payment to the beneficiary's IBAN",
             description="Records a bank transfer against the disbursement and sends an SMS notice. "
                         "Blocked (409) if the beneficiary has no IBAN on file.")
def pay_disbursement(disbursement_id: str):
    d = db.get_disbursement(disbursement_id)
    if not d:
        raise HTTPException(404, "Disbursement not found")
    if d["status"] == "paid":
        raise HTTPException(409, "Already paid")
    b = db.get_beneficiary(d["beneficiary_id"])
    if not b:
        raise HTTPException(404, "Beneficiary not found")
    bank = b.get("sections", {}).get("SEC-BANK", {})
    if not bank.get("iban"):
        raise HTTPException(409, "لا يوجد ايبان مسجل في ملف المستفيد — يجب تحديث البيانات البنكية اولا")
    import random as _r
    p = {"id": db.next_id("pay", "PAY-"), "disbursement_id": disbursement_id,
         "beneficiary_id": d["beneficiary_id"], "amount": d["amount"],
         "method": "bank_transfer", "reference": f"KYN{_r.randint(100000, 999999)}",
         "paid_at": db.now_iso()}
    paid_at = db.now_iso()
    with db.tx():
        db.insert_payment(p)
        db.update_disbursement(disbursement_id, {"status": "paid", "paid_at": paid_at})
    d["status"] = "paid"
    d["paid_at"] = paid_at
    msg = db.render_template("TPL-PAY", amount=d["amount"],
                             reason=db.program_name(d["program_id"]))
    contact = b.get("sections", {}).get("SEC-CONTACT", {})
    phone = contact.get("mobile") or contact.get("whatsapp") or b.get("phone")
    if phone:
        db.send_notification("sms", phone, msg, kind="payment")
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
    conn = db._get_conn()
    rows = [dict(r) for r in conn.execute(
        """SELECT * FROM disbursements
           WHERE status IN ('scheduled','approved','pending','pending_approval')
             AND due_date <= ?
           ORDER BY due_date""", (cutoff,))]
    by_prog = {}
    for d in rows:
        k = db.program_name(d["program_id"])
        by_prog[k] = round(by_prog.get(k, 0) + float(d["amount"] or 0), 2)
    # Attach the beneficiary name — the console's payment run listed bare IDs.
    names = {}
    for d in rows[:50]:
        bid = d["beneficiary_id"]
        if bid not in names:
            names[bid] = db.beneficiary_name(db.get_beneficiary(bid))
        d["name_ar"] = names[bid]
    return {"window_days": days, "count": len(rows),
            "total_sar": round(sum(float(d["amount"] or 0) for d in rows), 2),
            "by_program_ar": by_prog, "disbursements": rows[:50]}


# ============================================================ sponsorships & events
@router.get("/sponsorships", tags=[T_KAF],
            summary="List sponsorships (الكفالات)",
            description="Sponsor-to-beneficiary kafala records, restricted or unrestricted.")
def list_sponsorships(beneficiary_id: Optional[str] = Query(None)):
    rows = list(db.sponsorships)
    if beneficiary_id:
        rows = [s for s in rows if s["beneficiary_id"] == beneficiary_id]
    sponsors = {s["id"]: s for s in db.sponsors}
    out = []
    for s in rows:
        sp = sponsors.get(s.get("sponsor_id"), {})
        amount = _sponsorship_amount(s)
        out.append({**s, "monthly_amount_sar": amount,
                    "sponsor_name_ar": sp.get("name_ar"), "sponsor_type": sp.get("type")})
    return {"count": len(out), "sponsorships": out,
            "monthly_total_sar": round(sum(_sponsorship_amount(s) for s in rows), 2)}


def _sponsorship_amount(s):
    """The column is monthly_amount; the API has always exposed monthly_amount_sar."""
    return float(s.get("monthly_amount", s.get("monthly_amount_sar", 0)) or 0)


def _entry_amount(entry):
    """Obligation / person-cost rows use monthly_sar (API) or amount (old seed)."""
    if not isinstance(entry, dict):
        return 0.0
    return float(entry.get("monthly_sar", entry.get("amount", 0)) or 0)


@router.get("/events", tags=[T_KAF],
            summary="List events and activities (الفعاليات والانشطة)",
            description="Association events with capacity and registration counts.")
def list_events(status: Optional[str] = Query(None, examples=["scheduled"])):
    rows = list(db.events)
    if status:
        rows = [e for e in rows if e.get("status") == status]
    return {"count": len(rows), "events": [_event_view(e) for e in rows]}


def _event_view(e):
    """Normalise an event row for the API/console (name_ar/date were added late)."""
    return {**e,
            "name_ar": e.get("name_ar") or e.get("title_ar"),
            "date": e.get("event_date"),
            "capacity": e.get("capacity") or 0,
            "registered": e.get("registered") or 0,
            "status": e.get("status") or "scheduled",
            "program_ar": db.program_name(e["program_id"]) if e.get("program_id") else None}


class RegisterEventIn(BaseModel):
    beneficiary_id: str = Field(..., examples=["BEN-1001"])


@router.post("/events/{event_id}/register", tags=[T_KAF],
             summary="Register a beneficiary for an event",
             description="Registers an approved beneficiary for an event; blocked when the event is "
                         "full, already completed, or the beneficiary is already registered.")
def register_event(event_id: str, body: RegisterEventIn):
    e = db.get_event(event_id)
    if not e:
        raise HTTPException(404, "Event not found")
    view = _event_view(e)
    if view["status"] == "completed":
        raise HTTPException(409, "الفعالية منتهية")
    if view["capacity"] and view["registered"] >= view["capacity"]:
        raise HTTPException(409, "اكتمل العدد لهذه الفعالية")
    if not db.get_beneficiary(body.beneficiary_id):
        raise HTTPException(404, "Beneficiary not found")
    conn = db._get_conn()
    already = conn.execute(
        "SELECT 1 FROM event_registrations WHERE event_id = ? AND beneficiary_id = ?",
        (event_id, body.beneficiary_id)).fetchone()
    if already:
        raise HTTPException(409, "المستفيد مسجل مسبقا في هذه الفعالية")
    count = view["registered"] + 1
    with db.tx():
        db.insert_row("event_registrations", {
            "id": db.next_id("reg", "REG-"), "event_id": event_id,
            "beneficiary_id": body.beneficiary_id, "registered_at": db.now_iso()})
        db.update_event(event_id, {"registered": count})
    return {"event_id": event_id, "registered": count, "capacity": view["capacity"],
            "reply_ar": f"تم تسجيلكم في {view['name_ar']} بتاريخ {view['date']}."}


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
                     "title_ar": r.get("title_ar"), "stage": r.get("stage"),
                     "requested_amount_sar": r.get("requested_amount_sar"),
                     "decision_ar": d["decision_ar"] if d else None,
                     "approved_amount_sar": d["amount"] if d else None,
                     "created_at": r.get("created_at")})
    pays = db.payments_for(beneficiary_id)
    disb = db.disbursements_for(beneficiary_id)
    tks = db.tickets_for(beneficiary_id)
    fin = db.finance_for(beneficiary_id) or {}
    obligations = fin.get("obligations") or []
    person_costs = fin.get("person_costs") or []
    # Entries have carried both `monthly_sar` (API) and `amount` (older seed).
    total_obligations = round(sum(_entry_amount(o) for o in obligations), 2)
    total_person_costs = round(sum(_entry_amount(p) for p in person_costs), 2)
    monthly_income = float(fin.get("monthly_income") or 0)
    deps_count = 1 + len(db.deps_for(beneficiary_id))
    per_capita = round((monthly_income - total_obligations - total_person_costs) / deps_count, 2)
    return {
        "beneficiary": {"id": b["id"], "file_no": b["file_no"], "status": b["status"],
                        "case_type": b["case_type"],
                        "name_ar": db.beneficiary_name(b),
                        "category_ar": (db.by_id["orphan_category"].get(
                            b.get("orphan_category") or "") or {}).get("name_ar"),
                        "city": b.get("sections", {}).get("SEC-HOUSING", {}).get("city") or b.get("city"),
                        "created_at": b["created_at"], "approved_at": b.get("approved_at")},
        "completeness": {"pct": comp["completion_pct"],
                         "missing_fields": comp["missing_fields"],
                         "missing_documents": comp["missing_documents"]},
        "household": {"size": deps_count,
                      "dependents": db.deps_for(beneficiary_id)},
        "financial": {"monthly_income_sar": monthly_income,
                      "total_obligations_sar": total_obligations,
                      "total_person_costs_sar": total_person_costs,
                      "per_capita_monthly_sar": per_capita,
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
    matched = []
    for b in db.beneficiaries:
        c = b["sections"].get("SEC-CONTACT", {})
        basic = b["sections"].get("SEC-BASIC", {})
        name = basic.get("full_name_ar") or b.get("full_name_ar") or ""
        # If query is empty, return all; otherwise filter
        if not ql or \
                (phone and (db.norm_phone(c.get("mobile")) == phone
                            or db.norm_phone(c.get("whatsapp")) == phone
                            or db.norm_phone(b.get("phone")) == phone)) \
                or ql == b["id"] or ql == b.get("file_no") \
                or ql == (basic.get("national_id") or "") \
                or (len(ql) > 2 and ql in name):
            matched.append(b)

    # completeness is 3 queries per file, so only pay for the page being returned
    results = []
    for b in matched[:limit]:
        comp = db.file_completeness(b["id"])
        sections = b["sections"]
        results.append({"id": b["id"], "file_no": b.get("file_no"),
                        "name_ar": db.beneficiary_name(b) or "",
                        "status": b.get("status"), "case_type": b.get("case_type"),
                        "city": sections.get("SEC-HOUSING", {}).get("city") or b.get("city"),
                        "mobile": sections.get("SEC-CONTACT", {}).get("mobile") or b.get("phone"),
                        "completion_pct": comp["completion_pct"] if comp else 0,
                        "dependents": len(db.deps_for(b["id"]))})
    return {"query": q, "count": len(matched), "results": results}


@router.get("/reports/overview", tags=[T_360],
            summary="Association-wide overview report",
            description="Headline numbers across files, requests, programs, disbursements and "
                        "channels — the management dashboard.")
def overview():
    conn = db._get_conn()

    def counts(sql):
        return {row[0]: row[1] for row in conn.execute(sql) if row[0] is not None}

    by_status = counts("SELECT status, COUNT(*) FROM beneficiaries GROUP BY status")
    dec_counts = counts("SELECT decision, COUNT(*) FROM committee_decisions GROUP BY decision")
    by_stage_all = counts("SELECT stage, COUNT(*) FROM support_requests GROUP BY stage")
    by_program = counts("SELECT program_id, COUNT(*) FROM support_requests GROUP BY program_id")

    prog_totals = {}
    for row in conn.execute("""SELECT program_id, status, SUM(amount) FROM disbursements
                               GROUP BY program_id, status"""):
        k = db.program_name(row[0])
        bucket = prog_totals.setdefault(k, {"scheduled_sar": 0.0, "paid_sar": 0.0})
        key = "paid_sar" if row[1] == "paid" else "scheduled_sar"
        bucket[key] = round(bucket[key] + float(row[2] or 0), 2)

    sponsor_total = round(sum(_sponsorship_amount(s) for s in db.sponsorships), 2)
    return {
        "beneficiaries": {"total": db.count_table("beneficiaries"), "by_status": by_status,
                          "dependents": db.count_table("dependents")},
        "support_requests": {"total": db.count_table("support_requests"),
                             "by_stage": {s: by_stage_all.get(s, 0)
                                          for s in ("submitted", "under_study", "committee", "decided")},
                             "decisions": dec_counts},
        "programs": {p["name_ar"]: by_program.get(p["id"], 0) for p in db.programs},
        "disbursements_by_program_ar": prog_totals,
        "payments_total_sar": round(
            conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments").fetchone()[0], 2),
        "sponsorships": {"count": db.count_table("sponsorships"), "monthly_sar": sponsor_total},
        "channels": {"tickets": db.count_table("tickets"), "calls": db.count_table("call_sessions"),
                     "whatsapp_sessions": db.count_table("whatsapp_sessions")},
    }
