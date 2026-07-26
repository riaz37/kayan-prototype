"""
Use case 2 — CRM / ticketing + the two live channels (WhatsApp & SIP voice).
Models the admin panel in the client's screenshots: kanban board with
مفتوح / جاري العمل / بانتظار العميل / تم الرد columns, SLA countdown, department
routing, ticket stats, and the WhatsApp 24-hour session window.
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import timedelta

from backend import store as db

router = APIRouter()
T_CRM = "2 · نظام التذاكر CRM | Tickets & Kanban"
T_WA = "3 · قناة الواتساب | WhatsApp Channel"
T_SIP = "4 · قناة الاتصال الهاتفي | Voice / SIP Channel"


# ============================================================ tickets
@router.get("/crm/tickets", tags=[T_CRM],
            summary="List tickets with filters",
            description="Lists tickets (التذاكر والطلبات). Filter by status, department, channel or "
                        "beneficiary. Each row carries the SLA countdown like the admin panel.")
def list_tickets(status: Optional[str] = Query(None, examples=["open"]),
                 department_id: Optional[str] = Query(None, examples=["DEP-BEN"]),
                 channel: Optional[str] = Query(None, examples=["whatsapp"]),
                 beneficiary_id: Optional[str] = Query(None),
                 limit: int = Query(25, ge=1, le=100)):
    rows = db.tickets
    if status:
        rows = [t for t in rows if t["status"] == status]
    if department_id:
        rows = [t for t in rows if t["department_id"] == department_id]
    if channel:
        rows = [t for t in rows if t["channel"] == channel]
    if beneficiary_id:
        rows = [t for t in rows if t["beneficiary_id"] == beneficiary_id]
    rows = sorted(rows, key=lambda t: t["last_update"], reverse=True)[:limit]
    out = []
    for t in rows:
        out.append({**t, "status_ar": db.status_ar(t["status"]),
                    "department_ar": db.by_id["department"].get(t["department_id"], {}).get("name_ar"),
                    "sla": db.ticket_sla(t)})
    return {"count": len(out), "tickets": out}


@router.get("/crm/tickets/{ticket_id}", tags=[T_CRM],
            summary="Get a ticket with its full conversation",
            description="Full ticket detail including the message log (سجل المحادثة), SLA remaining, "
                        "and the beneficiary's other tickets — the same context the agent screen shows.")
def get_ticket(ticket_id: str):
    t = db.by_id["ticket"].get(ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    prev = [x["id"] for x in db.tickets_for(t["beneficiary_id"]) if x["id"] != ticket_id]
    return {**t, "status_ar": db.status_ar(t["status"]),
            "department_ar": db.by_id["department"].get(t["department_id"], {}).get("name_ar"),
            "sla": db.ticket_sla(t),
            "messages": db.messages_for(ticket_id),
            "previous_tickets": prev}


class CreateTicketIn(BaseModel):
    subject_ar: str = Field(..., examples=["سداد ايجار"])
    channel: str = Field("whatsapp", examples=["whatsapp", "call", "portal"])
    phone: Optional[str] = Field(None, examples=["0501234567"])
    beneficiary_id: Optional[str] = Field(None, examples=["BEN-1001"])
    department_id: str = Field("DEP-BEN", examples=["DEP-BEN"])
    priority: str = Field("medium", examples=["low", "medium", "high"])
    first_message_ar: Optional[str] = Field(None, examples=["احتاج مساعدة في سداد الايجار"])
    linked_request_id: Optional[str] = Field(None)


@router.post("/crm/tickets", tags=[T_CRM],
             summary="Open a ticket from any channel",
             description="Creates a ticket from a WhatsApp message or a phone call. If a phone is "
                         "given the beneficiary is auto-matched. This is what the bot calls when it "
                         "cannot resolve the query itself or when a human must act.")
def create_ticket(body: CreateTicketIn):
    b = db.get_beneficiary(body.beneficiary_id) if body.beneficiary_id else \
        (db.beneficiary_by_phone(body.phone) if body.phone else None)
    dep = db.by_id["department"].get(body.department_id)
    if not dep:
        raise HTTPException(404, "Unknown department")
    tid = db.next_id("tkt", "TK-2026-")
    t = {
        "id": tid, "beneficiary_id": (b or {}).get("id"),
        "customer_name_ar": (b or {}).get("sections", {}).get("SEC-BASIC", {}).get("full_name_ar")
                            or "غير مسجل",
        "whatsapp_number": db.norm_phone(body.phone) if body.phone else
                           (b or {}).get("sections", {}).get("SEC-CONTACT", {}).get("whatsapp"),
        "department_id": body.department_id, "subject_ar": body.subject_ar,
        "status": "open", "channel": body.channel, "priority": body.priority,
        "assigned_staff_id": None, "opened_at": db.now_iso(), "last_update": db.now_iso(),
        "closed_at": None, "messages_count": 1 if body.first_message_ar else 0,
        "linked_request_id": body.linked_request_id,
    }
    db.tickets.append(t)
    db.by_id["ticket"][tid] = t
    if body.first_message_ar:
        db.ticket_messages.append({
            "id": db.next_id("msg", "MSG-"), "ticket_id": tid, "direction": "inbound",
            "sender": "beneficiary", "body_ar": body.first_message_ar, "sent_at": db.now_iso()})
    return {"ticket_id": tid, "status": "open", "sla": db.ticket_sla(t),
            "department_ar": dep["name_ar"],
            "reply_ar": f"تم فتح تذكرة برقم {tid} وسيتم التواصل معكم خلال {dep['sla_hours']} ساعة."}


class MoveTicketIn(BaseModel):
    status: str = Field(..., examples=["in_progress"],
                        description="open | in_progress | waiting_customer | replied | closed | expired")
    note_ar: Optional[str] = None


@router.patch("/crm/tickets/{ticket_id}/status", tags=[T_CRM],
              summary="Move a ticket across the kanban board",
              description="Moves a ticket to another column (مفتوح / جاري العمل / بانتظار العميل / "
                          "تم الرد / مغلق).")
def move_ticket(ticket_id: str, body: MoveTicketIn):
    t = db.by_id["ticket"].get(ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    valid = {s["id"] for s in db.ticket_statuses}
    if body.status not in valid:
        raise HTTPException(422, f"Invalid status. Valid: {sorted(valid)}")
    t["status"] = body.status
    t["last_update"] = db.now_iso()
    if body.status == "closed":
        t["closed_at"] = db.now_iso()
    return {"ticket_id": ticket_id, "status": body.status,
            "status_ar": db.status_ar(body.status), "sla": db.ticket_sla(t)}


class AssignIn(BaseModel):
    staff_id: str = Field(..., examples=["STF-02"])


@router.patch("/crm/tickets/{ticket_id}/assign", tags=[T_CRM],
              summary="Assign a ticket to a staff member",
              description="Assigns the ticket to a member of فريق العمل.")
def assign_ticket(ticket_id: str, body: AssignIn):
    t = db.by_id["ticket"].get(ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    s = db.by_id["staff"].get(body.staff_id)
    if not s:
        raise HTTPException(404, "Staff member not found")
    t["assigned_staff_id"] = body.staff_id
    t["last_update"] = db.now_iso()
    return {"ticket_id": ticket_id, "assigned_to_ar": s["name_ar"], "role_ar": s["role_ar"]}


class ReplyIn(BaseModel):
    body_ar: str = Field(..., examples=["تم استلام طلبكم وجاري دراسته"])
    sender: str = Field("agent", examples=["agent", "bot"])


@router.post("/crm/tickets/{ticket_id}/reply", tags=[T_CRM],
             summary="Post a reply on a ticket",
             description="Adds an outbound message to the conversation and moves the ticket to "
                         "'replied'. If the WhatsApp 24h window has expired the response warns that "
                         "only a template message may be sent.")
def reply_ticket(ticket_id: str, body: ReplyIn):
    t = db.by_id["ticket"].get(ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    m = {"id": db.next_id("msg", "MSG-"), "ticket_id": ticket_id, "direction": "outbound",
         "sender": body.sender, "body_ar": body.body_ar, "sent_at": db.now_iso()}
    db.ticket_messages.append(m)
    t["messages_count"] = t.get("messages_count", 0) + 1
    t["status"] = "replied"
    t["last_update"] = db.now_iso()
    warn = None
    if t["channel"] == "whatsapp":
        sess = next((s for s in db.whatsapp_sessions
                     if db.norm_phone(s["wa_number"]) == db.norm_phone(t["whatsapp_number"])), None)
        if sess and not db.wa_window(sess)["open"]:
            warn = "نافذة الواتساب (24 ساعة) منتهية — يلزم استخدام رسالة قالب معتمدة."
    return {"message": m, "ticket_status": "replied", "warning_ar": warn}


@router.get("/crm/kanban", tags=[T_CRM],
            summary="Get the kanban board",
            description="Returns the board grouped into columns exactly as the admin panel renders it "
                        "(مفتوح، جاري العمل، بانتظار العميل، تم الرد) with per-column counts and cards.")
def kanban(department_id: Optional[str] = Query(None, examples=["DEP-BEN"])):
    cols = []
    rows = db.tickets if not department_id else [t for t in db.tickets if t["department_id"] == department_id]
    for st in sorted([s for s in db.ticket_statuses if s["kanban"]], key=lambda s: s["order"]):
        cards = [{"id": t["id"], "customer_name_ar": t["customer_name_ar"],
                  "subject_ar": t["subject_ar"],
                  "department_ar": db.by_id["department"].get(t["department_id"], {}).get("name_ar"),
                  "priority": t["priority"], "channel": t["channel"],
                  "sla_remaining_ar": db.ticket_sla(t)["remaining_ar"],
                  "last_update": t["last_update"]}
                 for t in rows if t["status"] == st["id"]]
        cols.append({"status": st["id"], "title_ar": st["name_ar"],
                     "count": len(cards), "cards": cards})
    summary = {s["name_ar"]: len([t for t in rows if t["status"] == s["id"]])
               for s in db.ticket_statuses}
    return {"columns": cols, "summary_ar": summary}


@router.get("/crm/stats", tags=[T_CRM],
            summary="Ticket statistics dashboard",
            description="Totals by status, today's tickets, closure rate, average response time and "
                        "the busiest department — the metric strip from the admin panel.")
def stats():
    total = len(db.tickets)
    by_status = {s["id"]: len([t for t in db.tickets if t["status"] == s["id"]])
                 for s in db.ticket_statuses}
    today = len([t for t in db.tickets
                 if db.parse(t["opened_at"]).date() == db.now().date()])
    closed = by_status.get("closed", 0)
    dep_counts = {}
    for t in db.tickets:
        dep_counts[t["department_id"]] = dep_counts.get(t["department_id"], 0) + 1
    top = max(dep_counts, key=dep_counts.get) if dep_counts else None
    durations = []
    for t in db.tickets:
        ms = db.messages_for(t["id"])
        first_in = next((m for m in ms if m["direction"] == "inbound"), None)
        first_out = next((m for m in ms if m["direction"] == "outbound"), None)
        if first_in and first_out:
            durations.append((db.parse(first_out["sent_at"]) - db.parse(first_in["sent_at"])).total_seconds())
    avg_h = round(sum(durations) / len(durations) / 3600, 1) if durations else 0.0
    breached = len([t for t in db.tickets if db.ticket_sla(t)["breached"]])
    return {
        "total": total,
        "by_status": by_status,
        "by_status_ar": {db.status_ar(k): v for k, v in by_status.items()},
        "today": today,
        "closure_rate_pct": round(closed / total * 100, 1) if total else 0.0,
        "avg_first_response_hours": avg_h,
        "sla_breached": breached,
        "top_department_ar": db.by_id["department"].get(top, {}).get("name_ar"),
        "by_channel": {c: len([t for t in db.tickets if t["channel"] == c])
                       for c in ("whatsapp", "call", "portal")},
    }


@router.get("/crm/departments", tags=[T_CRM],
            summary="List departments and their SLA",
            description="Routing targets (التصنيف) with each one's SLA in hours.")
def list_departments():
    return {"departments": db.departments}


@router.get("/crm/staff", tags=[T_CRM],
            summary="List staff (فريق العمل)",
            description="Staff available for assignment and escalation.")
def list_staff():
    return {"staff": db.staff}


# ============================================================ WhatsApp channel
class WaInboundIn(BaseModel):
    from_number: str = Field(..., examples=["966500287602"])
    text_ar: str = Field(..., examples=["السلام عليكم ابغى اسجل في الجمعية"])
    message_id: Optional[str] = Field(None, examples=["wamid.abc123"])


@router.post("/whatsapp/inbound", tags=[T_WA],
             summary="Handle an inbound WhatsApp message",
             description="Entry point for the WhatsApp bot. Identifies the sender against the "
                         "beneficiary database, opens or refreshes the 24-hour session window, and "
                         "returns the caller's context (file status, open tickets, pending requests) "
                         "so the agent can answer without asking who they are.")
def wa_inbound(body: WaInboundIn):
    p = db.norm_phone(body.from_number)
    b = db.beneficiary_by_phone(p)
    sess = next((s for s in db.whatsapp_sessions if db.norm_phone(s["wa_number"]) == p), None)
    if sess:
        sess["last_inbound_at"] = db.now_iso()
        sess["window_expires_at"] = (db.now() + timedelta(hours=24)).replace(microsecond=0).isoformat() + "Z"
        sess["status"] = "open"
        sess["messages"] = sess.get("messages", 0) + 1
    else:
        sess = {"id": db.next_id("wa", "WA-"), "wa_number": p,
                "beneficiary_id": (b or {}).get("id"), "opened_at": db.now_iso(),
                "window_expires_at": (db.now() + timedelta(hours=24)).replace(microsecond=0).isoformat() + "Z",
                "status": "open", "last_inbound_at": db.now_iso(), "messages": 1}
        db.whatsapp_sessions.append(sess)
    ctx = _context_for(b)
    return {"session_id": sess["id"], "window": db.wa_window(sess),
            "known_beneficiary": bool(b), "context": ctx,
            "suggested_greeting_ar": (
                f"اهلا {ctx['name_ar']}، حياكم الله في جمعية كيان للايتام. كيف اقدر اخدمكم؟"
                if b else
                "حياكم الله في جمعية كيان للايتام. بداية نشكركم على تواصلكم. "
                "هل انتم من فئة الايتام ذوي الظروف الخاصة (مجهولي الابوين)؟")}


@router.post("/whatsapp/send", tags=[T_WA],
             summary="Send a WhatsApp message",
             description="Sends a free-form message. Blocked with 409 if the 24-hour session window "
                         "has closed — use /whatsapp/send-template instead.")
def wa_send(to: str = Query(..., examples=["966500287602"]),
            body_ar: str = Query(..., examples=["تم استلام طلبكم"])):
    p = db.norm_phone(to)
    sess = next((s for s in db.whatsapp_sessions if db.norm_phone(s["wa_number"]) == p), None)
    if sess and not db.wa_window(sess)["open"]:
        raise HTTPException(409, "نافذة المحادثة (24 ساعة) منتهية — استخدم رسالة قالب معتمدة")
    n = db.send_notification("whatsapp", p, body_ar, kind="free_form")
    return {"sent": True, "notification": n}


class TemplateSendIn(BaseModel):
    to: str = Field(..., examples=["966500287602"])
    template_id: str = Field(..., examples=["TPL-DOCS"])
    params: dict = Field(default_factory=dict,
                         examples=[{"request_no": "SR-20001", "docs": "صورة الهوية، تعريف الراتب"}])


@router.post("/whatsapp/send-template", tags=[T_WA],
             summary="Send an approved WhatsApp template",
             description="Sends a pre-approved template message — the only thing permitted once the "
                         "24-hour window has closed.")
def wa_template(body: TemplateSendIn):
    tpl = next((t for t in db.templates if t["id"] == body.template_id), None)
    if not tpl:
        raise HTTPException(404, "Unknown template")
    text = db.render_template(body.template_id, **body.params)
    n = db.send_notification(tpl["channel"], body.to, text, kind="template")
    return {"sent": True, "template_ar": tpl["name_ar"], "body_ar": text, "notification": n}


@router.get("/whatsapp/templates", tags=[T_WA],
            summary="List approved message templates",
            description="Templates for OTP, registration confirmation, document requests, decisions, "
                        "visit scheduling and payment notices.")
def wa_templates():
    return {"templates": db.templates}


@router.get("/whatsapp/session/{phone}", tags=[T_WA],
            summary="Check a WhatsApp session window",
            description="Returns whether the 24-hour window is still open and how long remains "
                        "(الوقت المتبقي).")
def wa_session(phone: str):
    p = db.norm_phone(phone)
    sess = next((s for s in db.whatsapp_sessions if db.norm_phone(s["wa_number"]) == p), None)
    if not sess:
        raise HTTPException(404, "No session for this number")
    return {**sess, "window": db.wa_window(sess)}


# ============================================================ SIP / voice channel
class CallStartIn(BaseModel):
    from_number: str = Field(..., examples=["0501234567"])
    to_number: str = Field("966112925559", examples=["966112925559"])
    sip_call_id: Optional[str] = Field(None, examples=["sip-123456@kayan.pbx"])
    direction: str = Field("inbound", examples=["inbound", "outbound"])


@router.post("/voice/call-start", tags=[T_SIP],
             summary="Start a voice call session (SIP)",
             description="Called when a SIP call connects. Identifies the caller from the ANI, loads "
                         "their context, and returns a ready greeting. The agent should NOT disclose "
                         "file details until identity is confirmed for sensitive operations.")
def call_start(body: CallStartIn):
    p = db.norm_phone(body.from_number)
    b = db.beneficiary_by_phone(p)
    cid = db.next_id("call", "CALL-")
    sess = {"id": cid, "sip_call_id": body.sip_call_id or f"sip-{cid}@kayan.pbx",
            "direction": body.direction, "from_number": p, "to_number": body.to_number,
            "beneficiary_id": (b or {}).get("id"), "identified": bool(b),
            "language": "ar", "dialect": None, "started_at": db.now_iso(),
            "duration_sec": 0, "outcome": None, "intent": None, "transcript_available": True}
    db.call_sessions.append(sess)
    ctx = _context_for(b)
    return {"call_id": cid, "identified": bool(b), "context": ctx,
            "greeting_ar": (f"حياكم الله {ctx['name_ar']} في جمعية كيان للايتام. كيف اقدر اخدمكم؟"
                            if b else
                            "حياكم الله في جمعية كيان للايتام. كيف اقدر اخدمكم؟")}


class CallEndIn(BaseModel):
    outcome: str = Field(..., examples=["resolved_by_bot"],
                         description="resolved_by_bot | escalated_to_agent | ticket_created | voicemail")
    intent: Optional[str] = Field(None, examples=["استفسار عن حالة الطلب"])
    duration_sec: int = Field(0, examples=[145])
    transcript_ar: Optional[str] = None


@router.post("/voice/call-end/{call_id}", tags=[T_SIP],
             summary="End a voice call and log the outcome",
             description="Closes the call session with its outcome, detected intent and duration for "
                         "reporting.")
def call_end(call_id: str, body: CallEndIn):
    sess = next((c for c in db.call_sessions if c["id"] == call_id), None)
    if not sess:
        raise HTTPException(404, "Call session not found")
    sess.update({"outcome": body.outcome, "intent": body.intent,
                 "duration_sec": body.duration_sec, "ended_at": db.now_iso()})
    if body.transcript_ar:
        sess["transcript_ar"] = body.transcript_ar
    return {"call_id": call_id, "logged": True, "session": sess}


class TransferIn(BaseModel):
    reason_ar: str = Field(..., examples=["الحالة تحتاج تدخل موظف"])
    department_id: str = Field("DEP-BEN", examples=["DEP-BEN"])


@router.post("/voice/transfer/{call_id}", tags=[T_SIP],
             summary="Transfer a call to a human agent",
             description="Escalates a live call to a human, creating a ticket that carries the call "
                         "context so the agent does not start cold.")
def transfer_call(call_id: str, body: TransferIn):
    sess = next((c for c in db.call_sessions if c["id"] == call_id), None)
    if not sess:
        raise HTTPException(404, "Call session not found")
    dep = db.by_id["department"].get(body.department_id)
    if not dep:
        raise HTTPException(404, "Unknown department")
    tid = db.next_id("tkt", "TK-2026-")
    b = db.get_beneficiary(sess.get("beneficiary_id")) if sess.get("beneficiary_id") else None
    t = {"id": tid, "beneficiary_id": sess.get("beneficiary_id"),
         "customer_name_ar": (b or {}).get("sections", {}).get("SEC-BASIC", {}).get("full_name_ar") or "غير مسجل",
         "whatsapp_number": sess["from_number"], "department_id": body.department_id,
         "subject_ar": body.reason_ar, "status": "open", "channel": "call",
         "priority": "high", "assigned_staff_id": None, "opened_at": db.now_iso(),
         "last_update": db.now_iso(), "closed_at": None, "messages_count": 0,
         "linked_request_id": None, "source_call_id": call_id}
    db.tickets.append(t)
    db.by_id["ticket"][tid] = t
    sess["outcome"] = "escalated_to_agent"
    return {"ticket_id": tid, "queue_position": 2, "eta_minutes": 4,
            "reply_ar": "سأحولكم الان لاحد موظفي خدمات المستفيدين مع نقل تفاصيل مكالمتكم. "
                        "نرجو الانتظار لحظات."}


@router.get("/voice/calls", tags=[T_SIP],
            summary="List call sessions",
            description="Recent voice sessions with outcome and detected intent, for reporting.")
def list_calls(limit: int = Query(20, ge=1, le=100)):
    rows = sorted(db.call_sessions, key=lambda c: c["started_at"], reverse=True)[:limit]
    return {"count": len(rows), "calls": rows}


@router.get("/notifications", tags=[T_WA],
            summary="List sent notifications (WhatsApp / SMS log)",
            description="Everything the platform has sent in this session — useful to verify the bot "
                        "actually notified the beneficiary.")
def list_notifications(limit: int = Query(30, ge=1, le=200)):
    return {"count": len(db.notifications), "notifications": db.notifications[-limit:]}


# ============================================================ shared context
def _context_for(b):
    """The 360 snapshot both channels open with."""
    if not b:
        return {"known": False, "name_ar": None}
    bid = b["id"]
    reqs = db.requests_for(bid)
    open_tickets = [t["id"] for t in db.tickets_for(bid) if t["status"] not in ("closed",)]
    comp = db.file_completeness(bid)
    nxt = None
    for d in sorted(db.disbursements_for(bid), key=lambda x: x["due_date"]):
        if d["status"] != "paid":
            nxt = d
            break
    return {
        "known": True, "beneficiary_id": bid, "file_no": b["file_no"],
        "name_ar": b["sections"]["SEC-BASIC"]["full_name_ar"],
        "file_status": b["status"], "completion_pct": comp["completion_pct"],
        "missing_documents": [d["name_ar"] for d in comp["missing_documents"]],
        "open_requests": [{"id": r["id"], "title_ar": r["title_ar"], "stage": r["stage"]}
                          for r in reqs if r["stage"] != "decided"],
        "decided_requests": len([r for r in reqs if r["stage"] == "decided"]),
        "open_tickets": open_tickets,
        "next_disbursement": nxt,
    }
