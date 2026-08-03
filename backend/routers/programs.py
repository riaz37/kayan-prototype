"""
Use cases 3 & 4 — Support requests across the 5 programs, then the casework
pipeline: case study (field visit / interviews / psychological assessment) ->
specialized committee -> decision -> notification.
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import json

from backend import store as db

router = APIRouter()
T_REQ = "5 · طلبات الدعم | Support Requests"
T_CASE = "6 · دراسة الحالة واللجنة | Casework & Committee"


# ============================================================ catalogue
@router.get("/programs", tags=[T_REQ],
            summary="List the 5 association programs",
            description="برنامج علم، التاهيل والتدريب، جودة حياة، سكني، قيمي — each with its "
                        "description and request-type count.")
def list_programs():
    out = []
    for p in db.programs:
        rts = [r for r in db.request_types if r["program_id"] == p["id"]]
        out.append({**p, "request_types_count": len(rts)})
    return {"count": len(out), "programs": out}


@router.get("/programs/{program_id}/request-types", tags=[T_REQ],
            summary="List request types under a program",
            description="The projects/requests available under a program, with the approval ceiling "
                        "and whether the support is recurring monthly or one-off.")
def program_requests(program_id: str):
    p = db.by_id["program"].get(program_id)
    if not p:
        raise HTTPException(404, "Program not found")
    rts = [r for r in db.request_types if r["program_id"] == program_id]
    return {"program_id": program_id, "program_ar": p["name_ar"],
            "count": len(rts), "request_types": rts}


@router.get("/request-types/search", tags=[T_REQ],
            summary="Find the right request type from free text",
            description="Maps what the beneficiary said (e.g. 'محتاج مساعدة في الايجار') to the correct "
                        "request type and program. Use this before creating a request so the case lands "
                        "in the right program.")
def search_request_types(q: str = Query(..., examples=["ايجار"]), limit: int = Query(5, ge=1, le=20)):
    ql = q.strip()
    scored = []
    for r in db.request_types:
        hay = r["name_ar"] + " " + db.program_name(r["program_id"])
        score = sum(1 for tok in ql.split() if tok in hay)
        if ql in hay:
            score += 3
        if score:
            scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    hits = [r for _, r in scored[:limit]]
    return {"query": q, "count": len(hits),
            "results": [{**r, "program_ar": db.program_name(r["program_id"])} for r in hits]}


# ============================================================ support requests
class CreateRequestIn(BaseModel):
    beneficiary_id: str = Field(..., examples=["BEN-1001"])
    request_type_id: str = Field(..., examples=["REQ-HSG-01"])
    case_description_ar: str = Field(..., min_length=10,
                                     examples=["الاسرة متاخرة عن سداد الايجار لثلاثة اشهر وصدر انذار اخلاء"],
                                     description="وصف الحالة — the beneficiary's own explanation, in detail")
    requested_amount_sar: Optional[float] = Field(None, examples=[18000])
    internal_classification: str = Field("اعتيادي", examples=["عاجل", "اعتيادي", "متكرر", "موسمي"])
    channel: str = Field("whatsapp", examples=["whatsapp", "call", "portal"])


@router.post("/support-requests", tags=[T_REQ],
             summary="Submit a support request (طلب دعم)",
             description="Creates a support request under a program. Requires an APPROVED beneficiary "
                         "file — returns 409 otherwise, matching the guide ('after your file is "
                         "complete and approved'). Amounts above the request ceiling are rejected.")
def create_request(body: CreateRequestIn):
    b = db.get_beneficiary(body.beneficiary_id)
    if not b:
        raise HTTPException(404, "Beneficiary not found")
    if b["status"] != "approved":
        raise HTTPException(409, {
            "message": "Beneficiary file is not approved yet",
            "file_status": b["status"],
            "reply_ar": "لا يمكن تقديم طلب دعم قبل اكتمال ملفكم واعتماده من الجمعية. "
                        "سنساعدكم في استكمال الملف اولا.",
        })
    rt = db.by_id["request_type"].get(body.request_type_id)
    if not rt:
        raise HTTPException(404, "Unknown request type")
    amount = body.requested_amount_sar or 0.0
    if rt["ceiling_sar"] and amount > rt["ceiling_sar"]:
        raise HTTPException(409, {
            "message": "Requested amount exceeds the ceiling",
            "ceiling_sar": rt["ceiling_sar"],
            "reply_ar": f"الحد الاعلى لهذا الطلب هو {rt['ceiling_sar']} ريال.",
        })
    sid = db.next_id("sr", "SR-")
    sr = {"id": sid, "beneficiary_id": body.beneficiary_id, "program_id": rt["program_id"],
          "request_type_id": rt["id"], "title_ar": rt["name_ar"],
          "internal_classification": body.internal_classification,
          "case_description_ar": body.case_description_ar,
          "requested_amount_sar": amount, "stage": "submitted",
          "created_at": db.now_iso(), "channel": body.channel}
    db.support_requests.append(sr)
    db.by_id["support_request"][sid] = sr
    return {"support_request_id": sid, "stage": "submitted",
            "program_ar": db.program_name(rt["program_id"]), "title_ar": rt["name_ar"],
            "reply_ar": f"تم تسجيل طلبكم رقم {sid} ضمن {db.program_name(rt['program_id'])}. "
                        "سيخضع الطلب للدراسة والتقييم وسيتم اشعاركم بالقرار."}


@router.get("/support-requests", tags=[T_REQ],
            summary="List all support requests across all beneficiaries",
            description="Returns all support requests with program and beneficiary info.")
def list_all_requests():
    rows = db.requests_for_all()
    return {"count": len(rows), "requests": rows}


@router.get("/support-requests/{request_id}", tags=[T_REQ],
            summary="Get a support request with its casework and decision",
            description="Full request detail including the case study steps and the committee decision "
                        "if one has been issued.")
def get_request(request_id: str):
    sr = db.get_support_request(request_id)
    if not sr:
        raise HTTPException(404, "Support request not found")
    case = db.case_for(request_id)
    dec = db.decision_for(request_id)
    stage_ar = {"submitted": "تم التقديم — بانتظار الدراسة",
                "under_study": "قيد دراسة الحالة",
                "committee": "معروض على اللجنة المختصة",
                "decided": "تم اصدار القرار"}[sr["stage"]]
    return {**sr, "program_ar": db.program_name(sr["program_id"]),
            "stage_ar": stage_ar, "case_study": case, "decision": dec,
            "reply_ar": f"حالة طلبكم {sr['id']}: {stage_ar}." +
                        (f" القرار: {dec['decision_ar']}." if dec else "")}


@router.get("/beneficiary/{beneficiary_id}/support-requests", tags=[T_REQ],
            summary="List a beneficiary's support requests",
            description="All requests raised by a beneficiary with their stage and decision.")
def list_requests(beneficiary_id: str):
    if not db.get_beneficiary(beneficiary_id):
        raise HTTPException(404, "Beneficiary not found")
    rows = db.requests_for(beneficiary_id)
    out = []
    for r in rows:
        d = db.decision_for(r["id"])
        out.append({**r, "program_ar": db.program_name(r["program_id"]),
                    "decision": d["decision"] if d else None,
                    "decision_ar": d["decision_ar"] if d else None,
                    "approved_amount_sar": d["amount"] if d else None})
    return {"beneficiary_id": beneficiary_id, "count": len(out), "requests": out}


class AddDetailIn(BaseModel):
    additional_detail_ar: str = Field(..., min_length=5,
                                      examples=["صدر انذار اخلاء من المالك بتاريخ 1 يوليو"])


@router.patch("/support-requests/{request_id}/add-detail", tags=[T_REQ],
              summary="Append more detail to a request",
              description="Use when the case worker or bot asks the beneficiary to explain further. "
                          "Appends to وصف الحالة rather than overwriting it, preserving the history.")
def add_detail(request_id: str, body: AddDetailIn):
    sr = db.get_support_request(request_id)
    if not sr:
        raise HTTPException(404, "Support request not found")
    sr["case_description_ar"] += f"\n[{db.now_iso()}] {body.additional_detail_ar}"
    return {"support_request_id": request_id,
            "case_description_ar": sr["case_description_ar"],
            "reply_ar": "شكرا لتوضيحكم، تم اضافة التفاصيل الى الطلب."}


# ============================================================ casework
@router.get("/reference/case-steps", tags=[T_CASE],
            summary="List case study step types",
            description="المقابلة المكتبية، المقابلة الالكترونية، الزيارة الميدانية، تقييم الوضع النفسي.")
def list_case_steps():
    return {"steps": db.case_steps}


@router.post("/support-requests/{request_id}/open-case", tags=[T_CASE],
             summary="Open a case study for a request",
             description="Starts دراسة الحالة and moves the request to 'under_study'. Assigns a social "
                         "researcher.")
def open_case(request_id: str, researcher_id: str = Query("STF-04", examples=["STF-04"])):
    sr = db.get_support_request(request_id)
    if not sr:
        raise HTTPException(404, "Support request not found")
    if db.case_for(request_id):
        raise HTTPException(409, "A case study is already open for this request")
    cid = db.next_id("case", "CASE-")
    case = {"id": cid, "support_request_id": request_id,
            "beneficiary_id": sr["beneficiary_id"], "opened_at": db.now_iso(),
            "steps": [], "social_researcher_id": researcher_id,
            "recommendation_ar": None, "status": "open"}
    db.case_studies.append(case)
    sr["stage"] = "under_study"
    return {"case_id": cid, "stage": "under_study", "case_study": case}


class ScheduleStepIn(BaseModel):
    step_id: str = Field(..., examples=["CS-FIELD"],
                         description="CS-DESK | CS-ONLINE | CS-FIELD | CS-PSYCH")
    scheduled_at: str = Field(..., examples=["2026-08-02T10:00:00Z"])
    assigned_staff_id: str = Field("STF-04", examples=["STF-04"])


@router.post("/cases/{case_id}/schedule-step", tags=[T_CASE],
             summary="Schedule a case study step (visit / interview / assessment)",
             description="Schedules a field visit, office or online interview, or psychological "
                         "assessment, and notifies the beneficiary on WhatsApp.")
def schedule_step(case_id: str, body: ScheduleStepIn):
    case = next((c for c in db.case_studies if c["id"] == case_id), None)
    if not case:
        raise HTTPException(404, "Case study not found")
    st = next((s for s in db.case_steps if s["id"] == body.step_id), None)
    if not st:
        raise HTTPException(404, "Unknown case step")
    step = {"step_id": st["id"], "name_ar": st["name_ar"],
            "scheduled_at": body.scheduled_at, "status": "scheduled",
            "assigned_staff_id": body.assigned_staff_id, "findings_ar": None}
    case["steps"].append(step)
    b = db.get_beneficiary(case["beneficiary_id"])
    if b:
        msg = db.render_template("TPL-VISIT", date=body.scheduled_at[:10])
        db.send_notification("whatsapp", b["sections"]["SEC-CONTACT"]["whatsapp"], msg, kind="visit")
    return {"case_id": case_id, "step": step,
            "reply_ar": f"تم تحديد موعد {st['name_ar']} بتاريخ {body.scheduled_at[:10]}."}


class FindingsIn(BaseModel):
    step_id: str = Field(..., examples=["CS-FIELD"])
    findings_ar: str = Field(..., examples=["تم التحقق من السكن وعدد التابعين ومطابقة البيانات"])


@router.post("/cases/{case_id}/record-findings", tags=[T_CASE],
             summary="Record findings for a completed step",
             description="Marks a case step complete and stores the researcher's findings.")
def record_findings(case_id: str, body: FindingsIn):
    case = next((c for c in db.case_studies if c["id"] == case_id), None)
    if not case:
        raise HTTPException(404, "Case study not found")
    step = next((s for s in case["steps"] if s["step_id"] == body.step_id), None)
    if not step:
        raise HTTPException(404, "Step not scheduled on this case")
    step["status"] = "completed"
    step["findings_ar"] = body.findings_ar
    return {"case_id": case_id, "step": step}


class SubmitCommitteeIn(BaseModel):
    recommendation_ar: str = Field(..., examples=["التوصية بالقبول ضمن السقف المعتمد"])


@router.post("/cases/{case_id}/submit-to-committee", tags=[T_CASE],
             summary="Submit the case to the specialized committee",
             description="Presents the case to اللجنة المختصة with the researcher's recommendation. "
                         "Requires at least one completed step (409 otherwise).")
def submit_committee(case_id: str, body: SubmitCommitteeIn):
    case = next((c for c in db.case_studies if c["id"] == case_id), None)
    if not case:
        raise HTTPException(404, "Case study not found")
    done = [s for s in case["steps"] if s["status"] == "completed"]
    if not done:
        raise HTTPException(409, "لا يمكن العرض على اللجنة قبل اكمال خطوة واحدة على الاقل من دراسة الحالة")
    case["recommendation_ar"] = body.recommendation_ar
    sr = db.get_support_request(case["support_request_id"])
    if sr:
        sr["stage"] = "committee"
    return {"case_id": case_id, "stage": "committee",
            "completed_steps": len(done), "recommendation_ar": body.recommendation_ar}


class DecisionIn(BaseModel):
    decision: str = Field(..., examples=["accepted"],
                          description="accepted | docs_required | declined")
    approved_amount_sar: Optional[float] = Field(None, examples=[15000])
    reason_ar: str = Field(..., examples=["استيفاء الشروط ووجود احتياج مؤكد"])
    required_documents_ar: Optional[List[str]] = Field(None,
                                                       examples=[["تعريف الراتب", "عقد الايجار"]])


@router.post("/support-requests/{request_id}/decision", tags=[T_CASE],
             summary="Record the committee decision and notify the beneficiary",
             description="Records قبول الطلب / طلب استكمال مستندات / الاعتذار, then notifies the "
                         "beneficiary on BOTH WhatsApp and SMS as the guide specifies. Accepted "
                         "requests become eligible for enrollment and disbursement.")
def record_decision(request_id: str, body: DecisionIn):
    sr = db.get_support_request(request_id)
    if not sr:
        raise HTTPException(404, "Support request not found")
    if body.decision not in ("accepted", "docs_required", "declined"):
        raise HTTPException(422, "Invalid decision")
    if db.decision_for(request_id):
        raise HTTPException(409, "A decision already exists for this request")
    amt = body.approved_amount_sar or 0.0
    rt = db.by_id["request_type"].get(sr["request_type_id"], {})
    if body.decision == "accepted" and rt.get("ceiling_sar") and amt > rt["ceiling_sar"]:
        raise HTTPException(409, f"Approved amount exceeds the ceiling ({rt['ceiling_sar']} SAR)")
    did = db.next_id("dec", "DEC-")
    dec = {"id": did, "support_request_id": request_id, "beneficiary_id": sr["beneficiary_id"],
           "decision": body.decision,
           "decision_ar": next(d["name_ar"] for d in db.decision_types if d["id"] == body.decision),
           "approved_amount_sar": amt if body.decision == "accepted" else 0.0,
           "committee_date": db.now_iso(),
           "committee_members": [s["name_ar"] for s in db.staff[:3]],
           "reason_ar": body.reason_ar,
           "required_documents_ar": body.required_documents_ar,
           "notified_whatsapp": True, "notified_sms": True}
    db.committee_decisions.append(dec)
    conn.execute("UPDATE support_requests SET stage = ?, decision = ? WHERE id = ?",
                 ("decided", body.decision, request_id))
    conn.commit()
    sr["stage"] = "decided"
    sr["decision"] = body.decision
    case = db.case_for(request_id)
    if case:
        case["status"] = "closed"

    b = db.get_beneficiary(sr["beneficiary_id"])
    phone = b["sections"]["SEC-CONTACT"]["whatsapp"] if b else None
    if body.decision == "accepted":
        msg = db.render_template("TPL-ACCEPT", request_no=request_id,
                                 program=db.program_name(sr["program_id"]))
    elif body.decision == "docs_required":
        msg = db.render_template("TPL-DOCS", request_no=request_id,
                                 docs="، ".join(body.required_documents_ar or []))
    else:
        msg = db.render_template("TPL-DECLINE", request_no=request_id)
    if phone:
        db.send_notification("whatsapp", phone, msg, kind="decision")
        db.send_notification("sms", phone, msg, kind="decision")
    return {"decision": dec, "notified": {"whatsapp": bool(phone), "sms": bool(phone)},
            "message_sent_ar": msg}


@router.get("/committee/queue", tags=[T_CASE],
            summary="List cases awaiting committee review",
            description="The committee's queue, ordered by the beneficiary's need score so the "
                        "highest-need cases surface first (support is given وفق الاحتياج والاولوية).")
def committee_queue(limit: int = Query(20, ge=1, le=100)):
    rows = []
    for sr in db.support_requests:
        if sr["stage"] != "committee":
            continue
        f = db.finance_for(sr["beneficiary_id"]) or {}
        b = db.get_beneficiary(sr["beneficiary_id"])
        case = db.case_for(sr["id"])
        # Compute per_capita_monthly_sar from stored data
        obligations = json.loads(f.get("obligations", "[]")) if isinstance(f.get("obligations"), str) else (f.get("obligations") or [])
        person_costs = json.loads(f.get("person_costs", "[]")) if isinstance(f.get("person_costs"), str) else (f.get("person_costs") or [])
        total_obligations = round(sum(o.get("monthly_sar", 0) for o in obligations), 2)
        total_person_costs = round(sum(c.get("monthly_sar", 0) for c in person_costs), 2)
        net_monthly = round(f.get("monthly_income", 0) - total_obligations - total_person_costs, 2)
        hh = max(1, f.get("household_size", 1))
        per_capita = round(net_monthly / hh, 2)
        rows.append({
            "support_request_id": sr["id"],
            "beneficiary_id": sr["beneficiary_id"],
            "name_ar": b["sections"]["SEC-BASIC"]["full_name_ar"] if b else None,
            "program_ar": db.program_name(sr["program_id"]),
            "title_ar": sr["title_ar"],
            "requested_amount_sar": sr["requested_amount_sar"],
            "need_score": f.get("need_score"),
            "per_capita_monthly_sar": per_capita,
            "household_size": hh,
            "recommendation_ar": (case or {}).get("recommendation_ar"),
        })
    rows.sort(key=lambda r: r.get("need_score") or 0, reverse=True)
    return {"count": len(rows), "queue": rows[:limit]}
