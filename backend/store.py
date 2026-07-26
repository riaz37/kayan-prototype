"""
In-memory data store for the Kayan prototype.
Loads seed JSON once at import; mutations live in memory and reset on restart,
which keeps agent test runs repeatable.
"""
import json, os, random
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


# ---- reference
orphan_categories = _load("orphan_categories.json")
case_types = _load("case_types.json")
form_sections = _load("form_sections.json")
housing_proofs = _load("housing_proofs.json")
obligation_types = _load("obligation_types.json")
person_cost_types = _load("person_cost_types.json")
document_types = _load("document_types.json")
ticket_statuses = _load("ticket_statuses.json")
departments = _load("departments.json")
staff = _load("staff.json")
case_steps = _load("case_steps.json")
decision_types = _load("decisions.json")
templates = _load("templates.json")
programs = _load("programs.json")
request_types = _load("request_types.json")
faqs = _load("faqs.json")

# ---- transactional (start empty - data created by agent)
beneficiaries = []
dependents = []
documents = []
financial_profiles = []
support_requests = []
case_studies = []
committee_decisions = []
enrollments = []
disbursements = []
payments = []
sponsors = []
sponsorships = []
tickets = []
ticket_messages = []
call_sessions = []
whatsapp_sessions = []
events = []

# ---- runtime-only
otp_codes = {}          # phone -> {"code", "expires_at", "attempts"}
accounts = {}           # phone -> {"beneficiary_id", "password_set", "created_at"}
notifications = []      # sent whatsapp/sms log


def _index(rows):
    return {r["id"]: r for r in rows}


by_id = {
    "beneficiary": _index(beneficiaries), "program": _index(programs),
    "request_type": _index(request_types), "support_request": _index(support_requests),
    "ticket": _index(tickets), "department": _index(departments), "staff": _index(staff),
    "enrollment": _index(enrollments), "disbursement": _index(disbursements),
    "document_type": _index(document_types), "orphan_category": _index(orphan_categories),
    "form_section": _index(form_sections), "event": _index(events),
}


# ============================================================ helpers
def now():
    return datetime.utcnow()


def now_iso():
    return now().replace(microsecond=0).isoformat() + "Z"


def parse(ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", ""))


def norm_phone(p):
    """Normalize Saudi numbers to 9665XXXXXXXX."""
    if not p:
        return ""
    p = "".join(ch for ch in str(p) if ch.isdigit() or ch == "+").lstrip("+")
    if p.startswith("00966"):
        p = p[2:]
    if p.startswith("05"):
        p = "966" + p[1:]
    elif p.startswith("5") and len(p) == 9:
        p = "966" + p
    return p


def get_beneficiary(bid):
    return by_id["beneficiary"].get(bid)


def beneficiary_by_phone(phone):
    p = norm_phone(phone)
    for b in beneficiaries:
        c = b["sections"]["SEC-CONTACT"]
        if norm_phone(c.get("mobile")) == p or norm_phone(c.get("whatsapp")) == p:
            return b
    return None


def deps_for(bid):
    return [d for d in dependents if d["beneficiary_id"] == bid]


def docs_for(bid):
    return [d for d in documents if d["beneficiary_id"] == bid]


def finance_for(bid):
    return next((f for f in financial_profiles if f["beneficiary_id"] == bid), None)


def requests_for(bid):
    return [r for r in support_requests if r["beneficiary_id"] == bid]


def decision_for(srid):
    return next((d for d in committee_decisions if d["support_request_id"] == srid), None)


def case_for(srid):
    return next((c for c in case_studies if c["support_request_id"] == srid), None)


def enrollments_for(bid):
    return [e for e in enrollments if e["beneficiary_id"] == bid]


def disbursements_for(bid):
    return [d for d in disbursements if d["beneficiary_id"] == bid]


def payments_for(bid):
    return [p for p in payments if p["beneficiary_id"] == bid]


def tickets_for(bid):
    return [t for t in tickets if t["beneficiary_id"] == bid]


def messages_for(tid):
    return sorted([m for m in ticket_messages if m["ticket_id"] == tid],
                  key=lambda m: m["sent_at"])


def program_name(pid):
    p = by_id["program"].get(pid)
    return p["name_ar"] if p else pid


def status_ar(sid):
    s = next((x for x in ticket_statuses if x["id"] == sid), None)
    return s["name_ar"] if s else sid


# ---- file completeness: which sections/fields/documents are still missing
def file_completeness(bid):
    b = get_beneficiary(bid)
    if not b:
        return None
    missing_fields, done = [], 0
    for sec in form_sections:
        sid = sec["id"]
        if sid == "SEC-DEP":
            if deps_for(bid) or b["sections"].get("SEC-EXTRA", {}).get("dependents_count") == 0:
                done += 1
            else:
                missing_fields.append({"section_id": sid, "section_ar": sec["name_ar"],
                                       "field": "dependents"})
            continue
        if sid == "SEC-ATTACH":
            continue
        data = b["sections"].get(sid, {})
        gaps = [f for f in sec["fields"]
                if data.get(f) in (None, "", []) and f != "dependents"]
        if gaps:
            for g in gaps:
                missing_fields.append({"section_id": sid, "section_ar": sec["name_ar"], "field": g})
        else:
            done += 1

    ds = docs_for(bid)
    missing_docs = [{"document_type_id": d["document_type_id"], "name_ar": d["name_ar"],
                     "status": d["status"]}
                    for d in ds if d["mandatory"] and d["status"] in ("missing", "rejected")]
    total_sections = len(form_sections) - 1
    pct = round((done / total_sections) * 100) if total_sections else 0
    if missing_docs:
        pct = min(pct, 90)
    return {
        "beneficiary_id": bid, "file_no": b["file_no"], "status": b["status"],
        "completion_pct": pct,
        "sections_complete": done, "sections_total": total_sections,
        "missing_fields": missing_fields, "missing_documents": missing_docs,
        "ready_to_submit": not missing_fields and not missing_docs,
    }


# ---- WhatsApp 24h session window
def wa_window(session):
    exp = parse(session["window_expires_at"])
    rem = (exp - now()).total_seconds()
    if rem <= 0:
        return {"open": False, "remaining_seconds": 0, "remaining_ar": "منتهية"}
    h, m = int(rem // 3600), int((rem % 3600) // 60)
    return {"open": True, "remaining_seconds": int(rem), "remaining_ar": f"{h}س {m}د"}


def ticket_sla(t):
    dep = by_id["department"].get(t["department_id"], {})
    hours = dep.get("sla_hours", 24)
    deadline = parse(t["opened_at"]) + timedelta(hours=hours)
    rem = (deadline - now()).total_seconds()
    if t["status"] == "closed":
        return {"breached": False, "remaining_ar": "-", "remaining_seconds": 0}
    if rem <= 0:
        return {"breached": True, "remaining_ar": "منتهية المدة", "remaining_seconds": 0}
    h, m = int(rem // 3600), int((rem % 3600) // 60)
    return {"breached": False, "remaining_ar": f"{h}س {m}د", "remaining_seconds": int(rem)}


# ---- id sequences
_seq = {"ben": 2000, "dep": 6000, "doc": 8000, "sr": 25000, "case": 35000,
        "dec": 45000, "enr": 55000, "dis": 65000, "pay": 75000, "tkt": 6000,
        "msg": 95000, "call": 15000, "wa": 16000, "file": 4000}


def next_id(kind, prefix):
    _seq[kind] += 1
    return f"{prefix}{_seq[kind]}"


def render_template(tid, **kw):
    t = next((x for x in templates if x["id"] == tid), None)
    if not t:
        return ""
    body = t["body_ar"]
    for k, v in kw.items():
        body = body.replace("{" + k + "}", str(v))
    return body


def send_notification(channel, to, body, kind="manual"):
    n = {"id": f"NTF-{len(notifications)+1:05d}", "channel": channel, "to": norm_phone(to),
         "body_ar": body, "kind": kind, "sent_at": now_iso(), "status": "sent"}
    notifications.append(n)
    return n
