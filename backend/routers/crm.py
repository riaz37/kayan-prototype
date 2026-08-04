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


def _agent_history(phone):
    """Pull the LLM conversation for a phone from the agent process.

    The agent keys sessions by whatever string the channel handed it, so try
    the normalised forms this deployment can produce. (The previous list also
    tried a hardcoded "88"+digits — a Bangladesh prefix left over from a
    developer's test number.)
    """
    if not phone:
        return []
    import httpx as _httpx, os as _os
    agent_url = _os.environ.get("AGENT_URL", "http://127.0.0.1:8002")
    digits = "".join(c for c in str(phone) if c.isdigit())
    candidates = []
    for cand in (str(phone), digits, db.norm_phone(phone)):
        if cand and cand not in candidates:
            candidates.append(cand)
    raw = []
    for candidate in candidates:
        try:
            resp = _httpx.get(f"{agent_url}/agent/session/{candidate}/history", timeout=5)
            raw = resp.json().get("history", [])
            if raw:
                break
        except Exception:
            continue
    out = []
    for h in raw:
        role = h.get("role", "")
        text = " ".join(p.get("text", "") for p in h.get("parts", []) if p.get("text"))
        if text:
            out.append({
                "id": f"WA-{len(out) + 1}",
                "direction": "inbound" if role == "user" else "outbound",
                "sender": "beneficiary" if role == "user" else "bot",
                "body_ar": text,
                "is_internal": 0,
                "sent_at": h.get("at"),
            })
    return out


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
    conn = db._get_conn()
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if department_id:
        query += " AND department_id = ?"
        params.append(department_id)
    if channel:
        query += " AND channel = ?"
        params.append(channel)
    if beneficiary_id:
        query += " AND beneficiary_id = ?"
        params.append(beneficiary_id)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    out = []
    for r in rows:
        t = dict(r)
        cust_name = None
        if t.get("beneficiary_id"):
            b = db.get_beneficiary(t["beneficiary_id"])
            if b:
                cust_name = b.get("sections", {}).get("SEC-BASIC", {}).get("full_name_ar")
        out.append({**t, "status_ar": db.status_ar(t["status"]),
                    "department_ar": db.by_id["department"].get(t["department_id"], {}).get("name_ar"),
                    "customer_name_ar": cust_name or "غير مسجل",
                    "sla": db.ticket_sla(t)})
    return {"count": len(out), "tickets": out}


@router.get("/crm/tickets/{ticket_id}", tags=[T_CRM],
            summary="Get a ticket with its full conversation",
            description="Full ticket detail including the message log (سجل المحادثة), SLA remaining, "
                        "and the beneficiary's other tickets — the same context the agent screen shows.")
def get_ticket(ticket_id: str):
    conn = db._get_conn()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Ticket not found")
    t = dict(row)
    prev = [r["id"] for r in conn.execute(
        "SELECT id FROM tickets WHERE beneficiary_id = ? AND id != ?",
        (t["beneficiary_id"], ticket_id)).fetchall()]
    msgs = [dict(r) for r in conn.execute(
        "SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY sent_at",
        (ticket_id,)).fetchall()]
    cust_name = None
    if t.get("beneficiary_id"):
        b = db.get_beneficiary(t["beneficiary_id"])
        if b:
            cust_name = b.get("sections", {}).get("SEC-BASIC", {}).get("full_name_ar")
    # Fetch WhatsApp conversation history from the agent's session store
    wa_history = _agent_history(t.get("phone"))
    # Merge: ticket_messages (explicit CRM messages) + wa_history (agent conversation).
    # Anything without a timestamp sorts to the end rather than jumping to the
    # top of the thread as an undated "—" bubble.
    all_msgs = msgs + wa_history
    all_msgs.sort(key=lambda m: m.get("sent_at") or "9999")
    return {**t, "status_ar": db.status_ar(t["status"]),
            "department_ar": db.by_id["department"].get(t["department_id"], {}).get("name_ar"),
            "customer_name_ar": cust_name or "غير مسجل",
            "whatsapp_number": t.get("phone") or "",
            "sla": db.ticket_sla(t),
            "messages": all_msgs,
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
        "subject_ar": body.subject_ar,
        "channel": body.channel,
        "phone": db.norm_phone(body.phone) if body.phone else
                 (b or {}).get("sections", {}).get("SEC-CONTACT", {}).get("whatsapp"),
        "department_id": body.department_id, "priority": body.priority,
        "status": "open", "assigned_to": None,
        "opened_at": db.now_iso(), "updated_at": db.now_iso(),
        "first_message": body.first_message_ar,
    }
    db.insert_ticket(t)
    if body.first_message_ar:
        msg_id = db.next_id("msg", "MSG-")
        db.insert_ticket_message({
            "id": msg_id, "ticket_id": tid, "direction": "inbound",
            "sender": "beneficiary", "body_ar": body.first_message_ar,
            "sent_at": db.now_iso()})
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
    conn = db._get_conn()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Ticket not found")
    valid = {s["id"] for s in db.ticket_statuses}
    if body.status not in valid:
        raise HTTPException(422, f"Invalid status. Valid: {sorted(valid)}")
    t = dict(row)
    t["status"] = body.status
    t["updated_at"] = db.now_iso()
    updates = {"status": body.status}
    # Only stamp closed_at on the transition; reopening clears it.
    if body.status == "closed":
        updates["closed_at"] = t["closed_at"] = db.now_iso()
    elif t.get("closed_at"):
        updates["closed_at"] = t["closed_at"] = None
    db.update_ticket(ticket_id, updates)
    if body.note_ar:
        db.insert_ticket_message({
            "id": db.next_id("msg", "MSG-"), "ticket_id": ticket_id, "direction": "outbound",
            "sender": "system", "body_ar": body.note_ar, "is_internal": 1,
            "sent_at": db.now_iso()})
    return {"ticket_id": ticket_id, "status": body.status,
            "status_ar": db.status_ar(body.status), "sla": db.ticket_sla(t)}


class AssignIn(BaseModel):
    staff_id: str = Field(..., examples=["STF-02"])


@router.patch("/crm/tickets/{ticket_id}/assign", tags=[T_CRM],
              summary="Assign a ticket to a staff member",
              description="Assigns the ticket to a member of فريق العمل.")
def assign_ticket(ticket_id: str, body: AssignIn):
    conn = db._get_conn()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Ticket not found")
    s = db.by_id["staff"].get(body.staff_id)
    if not s:
        raise HTTPException(404, "Staff member not found")
    db.update_ticket(ticket_id, {"assigned_to": body.staff_id})
    return {"ticket_id": ticket_id, "assigned_to": body.staff_id,
            "assigned_to_ar": s["name_ar"], "role_ar": s["role_ar"]}


class ReplyIn(BaseModel):
    body_ar: str = Field(..., examples=["تم استلام طلبكم وجاري دراسته"])
    sender: str = Field("agent", examples=["agent", "bot"])
    send_to_whatsapp: bool = Field(True, description="If false, stores as internal note only")


@router.post("/crm/tickets/{ticket_id}/reply", tags=[T_CRM],
             summary="Post a reply on a ticket and send via WhatsApp",
             description="Adds an outbound message to the conversation, sends it via WhatsApp, "
                         "and moves the ticket to 'replied'.")
def reply_ticket(ticket_id: str, body: ReplyIn):
    conn = db._get_conn()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Ticket not found")
    t = dict(row)
    msg_id = db.next_id("msg", "MSG-")
    m = {"id": msg_id, "ticket_id": ticket_id, "direction": "outbound",
         "sender": body.sender, "body_ar": body.body_ar, "sent_at": db.now_iso(),
         # Persisted now: without the column, an internal note came back from
         # the database indistinguishable from a message sent to the beneficiary.
         "is_internal": 1 if not body.send_to_whatsapp else 0}
    db.insert_ticket_message(m)
    # Auto-transition: open/in_progress → waiting_customer
    new_status = "waiting_customer" if t["status"] in ("open", "in_progress") else t["status"]
    db.update_ticket(ticket_id, {"status": new_status})
    warn = None
    wa_sent = False
    # Resolve phone: ticket field → beneficiary sections → whatsapp_sessions
    phone = t.get("phone")
    if not phone and t.get("beneficiary_id"):
        b = db.get_beneficiary(t["beneficiary_id"])
        if b:
            phone = b.get("sections", {}).get("SEC-CONTACT", {}).get("whatsapp")
    if not phone:
        sess_row = conn.execute(
            "SELECT phone FROM whatsapp_sessions WHERE beneficiary_id = ? ORDER BY last_message_at DESC LIMIT 1",
            (t.get("beneficiary_id"),)).fetchone()
        if sess_row:
            phone = sess_row["phone"]
    if body.send_to_whatsapp and t["channel"] == "whatsapp" and phone:
        import httpx as _httpx, os as _os
        agent_url = _os.environ.get("AGENT_URL", "http://127.0.0.1:8002")
        try:
            resp = _httpx.post(f"{agent_url}/agent/send-text",
                               json={"to": phone, "text": body.body_ar}, timeout=30)
            wa_sent = resp.json().get("ok", False)
        except Exception as e:
            warn = f"WhatsApp send failed: {e}"
        sess_row = conn.execute(
            "SELECT * FROM whatsapp_sessions WHERE phone = ? ORDER BY last_message_at DESC LIMIT 1",
            (phone,)).fetchone()
        if sess_row:
            sess = dict(sess_row)
            if not db.wa_window(sess)["open"]:
                warn = "نافذة الواتساب (24 ساعة) منتهية — يلزم استخدام رسالة قالب معتمدة."
    elif not body.send_to_whatsapp:
        warn = "ملاحظة داخلية — لم تُرسل للمستفيد"
    elif body.send_to_whatsapp and not phone:
        warn = "لم يتم العثور على رقم واتساب مرتبط بالتذكرة"
    return {"message": m, "ticket_status": new_status, "whatsapp_sent": wa_sent, "warning_ar": warn}


@router.get("/crm/kanban", tags=[T_CRM],
            summary="Get the kanban board",
            description="Returns the board grouped into columns exactly as the admin panel renders it "
                        "(مفتوح، جاري العمل، بانتظار العميل، تم الرد) with per-column counts and cards.")
def kanban(department_id: Optional[str] = Query(None, examples=["DEP-BEN"])):
    conn = db._get_conn()
    query = "SELECT * FROM tickets"
    params = []
    if department_id:
        query += " WHERE department_id = ?"
        params.append(department_id)
    rows = conn.execute(query, params).fetchall()
    tickets_list = [dict(r) for r in rows]
    # Pre-load beneficiary names for all tickets
    ben_names = {}
    for t in tickets_list:
        bid = t.get("beneficiary_id")
        if bid and bid not in ben_names:
            b = db.get_beneficiary(bid)
            ben_names[bid] = b.get("sections", {}).get("SEC-BASIC", {}).get("full_name_ar") if b else None
    cols = []
    for st in sorted([s for s in db.ticket_statuses if s["kanban"]], key=lambda s: s["order"]):
        cards = [{"id": t["id"], "customer_name_ar": ben_names.get(t.get("beneficiary_id")) or "غير مسجل",
                  "subject_ar": t["subject_ar"],
                  "department_ar": db.by_id["department"].get(t["department_id"], {}).get("name_ar"),
                  "priority": t["priority"], "channel": t["channel"],
                  "sla_remaining_ar": db.ticket_sla(t)["remaining_ar"],
                  "last_update": t["updated_at"]}
                 for t in tickets_list if t["status"] == st["id"]]
        cols.append({"status": st["id"], "title_ar": st["name_ar"],
                     "count": len(cards), "cards": cards})
    summary = {s["name_ar"]: len([t for t in tickets_list if t["status"] == s["id"]])
               for s in db.ticket_statuses}
    return {"columns": cols, "summary_ar": summary}


@router.get("/crm/stats", tags=[T_CRM],
            summary="Ticket statistics dashboard",
            description="Totals by status, today's tickets, closure rate, average response time and "
                        "the busiest department — the metric strip from the admin panel.")
def stats():
    conn = db._get_conn()
    total = conn.execute("SELECT COUNT(*) as cnt FROM tickets").fetchone()["cnt"]
    by_status = {}
    for s in db.ticket_statuses:
        cnt = conn.execute("SELECT COUNT(*) as cnt FROM tickets WHERE status = ?",
                          (s["id"],)).fetchone()["cnt"]
        by_status[s["id"]] = cnt
    today = conn.execute("SELECT COUNT(*) as cnt FROM tickets WHERE date(opened_at) = date('now')",
                        ).fetchone()["cnt"]
    closed = by_status.get("closed", 0)
    dep_rows = conn.execute("SELECT department_id, COUNT(*) as cnt FROM tickets GROUP BY department_id",
                           ).fetchall()
    dep_counts = {r["department_id"]: r["cnt"] for r in dep_rows}
    top = max(dep_counts, key=dep_counts.get) if dep_counts else None
    durations = []
    ticket_ids = [r["id"] for r in conn.execute("SELECT id FROM tickets").fetchall()]
    for tid in ticket_ids:
        ms = db.messages_for(tid)
        first_in = next((m for m in ms if m["direction"] == "inbound"), None)
        first_out = next((m for m in ms if m["direction"] == "outbound"), None)
        if first_in and first_out:
            durations.append((db.parse(first_out["sent_at"]) - db.parse(first_in["sent_at"])).total_seconds())
    avg_h = round(sum(durations) / len(durations) / 3600, 1) if durations else 0.0
    breached = 0
    for r in conn.execute("SELECT * FROM tickets").fetchall():
        if db.ticket_sla(dict(r))["breached"]:
            breached += 1
    return {
        "total": total,
        "by_status": by_status,
        "by_status_ar": {db.status_ar(k): v for k, v in by_status.items()},
        "today": today,
        "closure_rate_pct": round(closed / total * 100, 1) if total else 0.0,
        "avg_first_response_hours": avg_h,
        "sla_breached": breached,
        "top_department_ar": db.by_id["department"].get(top, {}).get("name_ar"),
        "by_channel": {c: conn.execute("SELECT COUNT(*) as cnt FROM tickets WHERE channel = ?",
                                       (c,)).fetchone()["cnt"]
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
    conn = db._get_conn()
    # Auto-transition: waiting_customer → in_progress when customer responds
    open_ticket = conn.execute(
        "SELECT id FROM tickets WHERE phone = ? AND status = 'waiting_customer' ORDER BY updated_at DESC LIMIT 1",
        (p,)).fetchone()
    if open_ticket:
        conn.execute("UPDATE tickets SET status='in_progress', updated_at=? WHERE id=?",
                    (db.now_iso(), open_ticket["id"]))
        conn.commit()
    sess_row = conn.execute(
        "SELECT * FROM whatsapp_sessions WHERE phone = ? ORDER BY last_message_at DESC LIMIT 1",
        (p,)).fetchone()
    if sess_row:
        sess = dict(sess_row)
        new_expiry = (db.now() + timedelta(hours=24)).replace(microsecond=0).isoformat() + "Z"
        conn.execute("UPDATE whatsapp_sessions SET last_message_at=?, window_expires_at=? WHERE id=?",
                    (db.now_iso(), new_expiry, sess["id"]))
        conn.commit()
        sess["window_expires_at"] = new_expiry
        sess["last_message_at"] = db.now_iso()
    else:
        sess = {"id": db.next_id("wa", "WA-"), "phone": p,
                "beneficiary_id": (b or {}).get("id"),
                "window_expires_at": (db.now() + timedelta(hours=24)).replace(microsecond=0).isoformat() + "Z",
                "last_message_at": db.now_iso(), "direction": "inbound"}
        db.insert_whatsapp_session(sess)
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
    conn = db._get_conn()
    sess_row = conn.execute(
        "SELECT * FROM whatsapp_sessions WHERE phone = ? ORDER BY last_message_at DESC LIMIT 1",
        (p,)).fetchone()
    if sess_row:
        sess = dict(sess_row)
        if not db.wa_window(sess)["open"]:
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
    conn = db._get_conn()
    row = conn.execute(
        "SELECT * FROM whatsapp_sessions WHERE phone = ? ORDER BY last_message_at DESC LIMIT 1",
        (p,)).fetchone()
    if not row:
        # Fall back to a scan for rows stored in a different phone format.
        row = next((r for r in conn.execute("SELECT * FROM whatsapp_sessions")
                    if db.norm_phone(r["phone"]) == p), None)
    if not row:
        raise HTTPException(404, "No session for this number")
    sess = dict(row)
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
            "direction": body.direction, "phone": p, "from_number": p,
            "to_number": body.to_number,
            "beneficiary_id": (b or {}).get("id"), "identified": 1 if b else 0,
            "language": "ar", "dialect": None, "started_at": db.now_iso(),
            "duration_seconds": 0, "outcome": None, "intent": None}
    db.insert_call_session(sess)
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
    sess = _call_session(call_id)
    if not sess:
        raise HTTPException(404, "Call session not found")
    updates = {"outcome": body.outcome, "intent": body.intent,
               "duration_seconds": body.duration_sec, "ended_at": db.now_iso()}
    if body.transcript_ar:
        updates["transcript_ar"] = body.transcript_ar
    db.update_row("call_sessions", call_id, updates)
    sess.update(updates)
    return {"call_id": call_id, "logged": True, "session": _call_view(sess)}


def _call_session(call_id):
    conn = db._get_conn()
    row = conn.execute("SELECT * FROM call_sessions WHERE id = ?", (call_id,)).fetchone()
    return dict(row) if row else None


def _call_view(c):
    """Expose both the stored and the historical field names — the console
    reads from_number/duration_sec, the table stores phone/duration_seconds."""
    return {**c,
            "from_number": c.get("from_number") or c.get("phone"),
            "duration_sec": c.get("duration_sec") or c.get("duration_seconds") or 0,
            "identified": bool(c.get("identified") or c.get("beneficiary_id"))}


class TransferIn(BaseModel):
    reason_ar: str = Field(..., examples=["الحالة تحتاج تدخل موظف"])
    department_id: str = Field("DEP-BEN", examples=["DEP-BEN"])


@router.post("/voice/transfer/{call_id}", tags=[T_SIP],
             summary="Transfer a call to a human agent",
             description="Escalates a live call to a human, creating a ticket that carries the call "
                         "context so the agent does not start cold.")
def transfer_call(call_id: str, body: TransferIn):
    sess = _call_session(call_id)
    if not sess:
        raise HTTPException(404, "Call session not found")
    dep = db.by_id["department"].get(body.department_id)
    if not dep:
        raise HTTPException(404, "Unknown department")
    tid = db.next_id("tkt", "TK-2026-")
    t = {"id": tid, "beneficiary_id": sess.get("beneficiary_id"),
         "phone": sess.get("from_number") or sess.get("phone"),
         "department_id": body.department_id,
         "subject_ar": body.reason_ar, "status": "open", "channel": "call",
         "priority": "high", "assigned_to": None, "opened_at": db.now_iso(),
         "updated_at": db.now_iso(), "closed_at": None}
    with db.tx():
        db.insert_ticket(t)
        db.update_row("call_sessions", call_id, {"outcome": "escalated_to_agent"})
    db.by_id["ticket"][tid] = t
    return {"ticket_id": tid, "queue_position": 2, "eta_minutes": 4,
            "reply_ar": "سأحولكم الان لاحد موظفي خدمات المستفيدين مع نقل تفاصيل مكالمتكم. "
                        "نرجو الانتظار لحظات."}


@router.get("/voice/calls", tags=[T_SIP],
            summary="List call sessions",
            description="Recent voice sessions with outcome and detected intent, for reporting.")
def list_calls(limit: int = Query(20, ge=1, le=100)):
    conn = db._get_conn()
    rows = conn.execute(
        "SELECT * FROM call_sessions ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
    return {"count": len(rows), "calls": [_call_view(dict(r)) for r in rows]}


@router.get("/notifications", tags=[T_WA],
            summary="List sent notifications (WhatsApp / SMS log)",
            description="Everything the platform has sent in this session — useful to verify the bot "
                        "actually notified the beneficiary.")
def list_notifications(limit: int = Query(30, ge=1, le=200)):
    rows = db.notifications_recent(limit)
    return {"count": len(rows), "notifications": rows}


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
