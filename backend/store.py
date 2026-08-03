"""
SQLite-backed data store for the Kayan prototype.
Reference data loaded from JSON (static). Transactional data persisted in SQLite.
"""
import json, os, sqlite3
from datetime import datetime, timedelta

REF_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "reference-data")
DATA_DIR = os.path.join(os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data")))
DB_PATH = os.path.join(DATA_DIR, "kayan.db")

_conn = None


def _get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def _load(name):
    with open(os.path.join(REF_DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def _index(rows):
    return {r["id"]: r for r in rows}


# ---- reference data (static, loaded from JSON)
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


# ---- SQLite schema
def _init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS beneficiaries (
            id TEXT PRIMARY KEY,
            file_no TEXT,
            status TEXT DEFAULT 'draft',
            case_type TEXT,
            orphan_category TEXT,
            city TEXT,
            full_name_ar TEXT,
            phone TEXT,
            sections TEXT DEFAULT '{}',
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS dependents (
            id TEXT PRIMARY KEY,
            beneficiary_id TEXT,
            name_ar TEXT,
            relationship TEXT,
            birth_date TEXT,
            gender TEXT,
            education TEXT,
            special_needs INTEGER DEFAULT 0,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            beneficiary_id TEXT,
            document_type_id TEXT,
            name_ar TEXT,
            mandatory INTEGER DEFAULT 1,
            status TEXT DEFAULT 'missing',
            file_path TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS financial_profiles (
            id TEXT PRIMARY KEY,
            beneficiary_id TEXT,
            monthly_income REAL DEFAULT 0,
            monthly_expenses REAL DEFAULT 0,
            obligations TEXT DEFAULT '[]',
            person_costs TEXT DEFAULT '[]',
            need_score REAL DEFAULT 0,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS support_requests (
            id TEXT PRIMARY KEY,
            beneficiary_id TEXT,
            program_id TEXT,
            request_type_id TEXT,
            title_ar TEXT,
            description_ar TEXT,
            case_description_ar TEXT,
            internal_classification TEXT,
            channel TEXT,
            requested_amount_sar REAL,
            amount REAL,
            status TEXT DEFAULT 'submitted',
            stage TEXT DEFAULT 'new',
            decision TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS case_studies (
            id TEXT PRIMARY KEY,
            support_request_id TEXT,
            beneficiary_id TEXT,
            caseworker TEXT,
            notes_ar TEXT,
            recommendation_ar TEXT,
            steps TEXT DEFAULT '[]',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS committee_decisions (
            id TEXT PRIMARY KEY,
            support_request_id TEXT,
            beneficiary_id TEXT,
            decision TEXT,
            amount REAL,
            notes_ar TEXT,
            decided_by TEXT,
            decided_at TEXT
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            id TEXT PRIMARY KEY,
            beneficiary_id TEXT,
            program_id TEXT,
            status TEXT DEFAULT 'active',
            enrolled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS disbursements (
            id TEXT PRIMARY KEY,
            beneficiary_id TEXT,
            program_id TEXT,
            enrollment_id TEXT,
            amount REAL,
            status TEXT DEFAULT 'scheduled',
            due_date TEXT,
            paid_at TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY,
            beneficiary_id TEXT,
            disbursement_id TEXT,
            amount REAL,
            method TEXT,
            reference TEXT,
            paid_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sponsors (
            id TEXT PRIMARY KEY,
            name_ar TEXT,
            phone TEXT,
            email TEXT,
            total_pledged REAL DEFAULT 0,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sponsorships (
            id TEXT PRIMARY KEY,
            sponsor_id TEXT,
            beneficiary_id TEXT,
            monthly_amount REAL,
            status TEXT DEFAULT 'active',
            started_at TEXT
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            subject_ar TEXT,
            channel TEXT,
            phone TEXT,
            beneficiary_id TEXT,
            department_id TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            assigned_to TEXT,
            opened_at TEXT,
            updated_at TEXT,
            closed_at TEXT,
            first_message TEXT
        );

        CREATE TABLE IF NOT EXISTS ticket_messages (
            id TEXT PRIMARY KEY,
            ticket_id TEXT,
            direction TEXT,
            sender TEXT,
            body_ar TEXT,
            sent_at TEXT
        );

        CREATE TABLE IF NOT EXISTS call_sessions (
            id TEXT PRIMARY KEY,
            phone TEXT,
            beneficiary_id TEXT,
            direction TEXT DEFAULT 'inbound',
            outcome TEXT,
            intent TEXT,
            duration_seconds INTEGER,
            notes_ar TEXT,
            started_at TEXT,
            ended_at TEXT
        );

        CREATE TABLE IF NOT EXISTS whatsapp_sessions (
            id TEXT PRIMARY KEY,
            phone TEXT,
            beneficiary_id TEXT,
            window_expires_at TEXT,
            last_message_at TEXT,
            direction TEXT DEFAULT 'inbound'
        );

        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            title_ar TEXT,
            description_ar TEXT,
            event_date TEXT,
            location TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            channel TEXT,
            "to" TEXT,
            body_ar TEXT,
            kind TEXT,
            sent_at TEXT,
            status TEXT DEFAULT 'sent'
        );

        CREATE TABLE IF NOT EXISTS accounts (
            phone TEXT PRIMARY KEY,
            beneficiary_id TEXT,
            password_set INTEGER DEFAULT 0,
            created_at TEXT
        );
    """)
    conn.commit()


_init_db()


def _init_dynamic_indexes():
    """Populate in-memory indexes for dynamic data from the database."""
    conn = _get_conn()
    for table, key in [("support_requests", "support_request"),
                       ("disbursements", "disbursement"),
                       ("events", "event"),
                       ("tickets", "ticket")]:
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            for row in rows:
                d = dict(row)
                # Parse JSON fields if present
                if "sections" in d and isinstance(d["sections"], str):
                    d["sections"] = json.loads(d["sections"])
                if "obligations" in d and isinstance(d["obligations"], str):
                    d["obligations"] = json.loads(d["obligations"])
                if "person_costs" in d and isinstance(d["person_costs"], str):
                    d["person_costs"] = json.loads(d["person_costs"])
                by_id[key][d["id"]] = d
        except Exception:
            pass  # Table may not exist yet


_init_dynamic_indexes()


# ---- helpers
def now():
    return datetime.utcnow()


def now_iso():
    return now().replace(microsecond=0).isoformat() + "Z"


def parse(ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", ""))


def norm_phone(p):
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


# ---- reference index lookups
by_id = {
    "program": _index(programs),
    "request_type": _index(request_types),
    "department": _index(departments),
    "staff": _index(staff),
    "document_type": _index(document_types),
    "orphan_category": _index(orphan_categories),
    "form_section": _index(form_sections),
    "support_request": {},
    "disbursement": {},
    "event": {},
    "ticket": {},
}


def _warm_indices():
    """Populate mutable indices from the database (for seed records)."""
    conn = _get_conn()
    for table in ("support_request", "disbursement", "event", "ticket"):
        rows = conn.execute(f"SELECT * FROM {table}s").fetchall()
        by_id[table] = _index(rows)


_warm_indices()


# ---- beneficiary lookups
def get_beneficiary(bid):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM beneficiaries WHERE id = ?", (bid,)).fetchone()
    if not row:
        return None
    b = dict(row)
    b["sections"] = json.loads(b.get("sections", "{}"))
    return b


def beneficiary_by_phone(phone):
    p = norm_phone(phone)
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM beneficiaries").fetchall()
    for r in rows:
        sections = json.loads(r["sections"] or "{}")
        contact = sections.get("SEC-CONTACT", {})
        if norm_phone(contact.get("mobile")) == p or norm_phone(contact.get("whatsapp")) == p:
            b = dict(r)
            b["sections"] = sections
            return b
    return None


def deps_for(bid):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM dependents WHERE beneficiary_id = ?", (bid,)).fetchall()
    return [dict(r) for r in rows]


def docs_for(bid):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM documents WHERE beneficiary_id = ?", (bid,)).fetchall()
    return [dict(r) for r in rows]


def finance_for(bid):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM financial_profiles WHERE beneficiary_id = ?", (bid,)).fetchone()
    return dict(row) if row else None


def get_support_request(request_id):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM support_requests WHERE id = ?", (request_id,)).fetchone()
    return dict(row) if row else None


def requests_for(bid):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM support_requests WHERE beneficiary_id = ?", (bid,)).fetchall()
    return [dict(r) for r in rows]


def requests_for_all():
    """List all support requests with beneficiary name and program info."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM support_requests ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        sr = dict(r)
        # Get beneficiary name
        b = get_beneficiary(sr["beneficiary_id"])
        sr["name_ar"] = b["sections"]["SEC-BASIC"]["full_name_ar"] if b else None
        sr["program_ar"] = program_name(sr["program_id"])
        # Get decision info
        dec = decision_for(sr["id"])
        sr["decision_ar"] = dec["decision"] if dec else None
        sr["approved_amount_sar"] = dec["amount"] if dec else None
        out.append(sr)
    return out


def decision_for(srid):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM committee_decisions WHERE support_request_id = ?", (srid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["decision_ar"] = next((dt["name_ar"] for dt in decision_types if dt["id"] == d["decision"]), d["decision"])
    return d


def case_for(srid):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM case_studies WHERE support_request_id = ?", (srid,)).fetchone()
    return dict(row) if row else None


def enrollments_for(bid):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM enrollments WHERE beneficiary_id = ?", (bid,)).fetchall()
    return [dict(r) for r in rows]


def disbursements_for(bid):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM disbursements WHERE beneficiary_id = ?", (bid,)).fetchall()
    return [dict(r) for r in rows]


def payments_for(bid):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM payments WHERE beneficiary_id = ?", (bid,)).fetchall()
    return [dict(r) for r in rows]


def tickets_for(bid):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM tickets WHERE beneficiary_id = ?", (bid,)).fetchall()
    return [dict(r) for r in rows]


def messages_for(tid):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY sent_at", (tid,)).fetchall()
    return [dict(r) for r in rows]


def update_disbursement(disbursement_id, updates):
    """Update disbursement fields in the database and in-memory index."""
    conn = _get_conn()
    set_clauses = []
    values = []
    for k, v in updates.items():
        set_clauses.append(f"{k} = ?")
        values.append(v)
    if set_clauses:
        values.append(disbursement_id)
        conn.execute(f"UPDATE disbursements SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
    # Update in-memory index
    d = by_id["disbursement"].get(disbursement_id)
    if d:
        d.update(updates)


def update_payment(payment_id, updates):
    """Update payment fields in the database."""
    conn = _get_conn()
    set_clauses = []
    values = []
    for k, v in updates.items():
        set_clauses.append(f"{k} = ?")
        values.append(v)
    if set_clauses:
        values.append(payment_id)
        conn.execute(f"UPDATE payments SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()


def insert_payment(p):
    """Insert a payment record into the database."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO payments (id, disbursement_id, beneficiary_id, amount, method, reference, paid_at)
           VALUES (?,?,?,?,?,?,?)""",
        (p["id"], p.get("disbursement_id"), p.get("beneficiary_id"), p.get("amount"),
         p.get("method"), p.get("reference"), p.get("paid_at")))
    conn.commit()


def program_name(pid):
    p = by_id["program"].get(pid)
    return p["name_ar"] if p else pid


def status_ar(sid):
    s = next((x for x in ticket_statuses if x["id"] == sid), None)
    return s["name_ar"] if s else sid


# ---- file completeness
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


# ---- id sequences (initialized from DB on first call)
_seq = {}
_seq_initialized = False

def _init_seq():
    global _seq_initialized
    if _seq_initialized:
        return
    conn = _get_conn()
    # Get max IDs from each table to avoid duplicates
    queries = {
        "ben": "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM beneficiaries",
        "dep": "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM dependents",
        "doc": "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM documents",
        "sr": "SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) FROM support_requests",
        "case": "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM case_studies",
        "dec": "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM committee_decisions",
        "enr": "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM enrollments",
        "dis": "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM disbursements",
        "pay": "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM payments",
        "tkt": "SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) FROM tickets",
        "msg": "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM ticket_messages",
        "call": "SELECT MAX(CAST(SUBSTR(id, 6) AS INTEGER)) FROM call_sessions",
        "wa": "SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) FROM whatsapp_sessions",
        "file": "SELECT MAX(CAST(SUBSTR(file_no, 4) AS INTEGER)) FROM beneficiaries WHERE file_no LIKE 'KY-%'",
    }
    defaults = {"ben": 2000, "dep": 6000, "doc": 8000, "sr": 25000, "case": 35000,
                "dec": 45000, "enr": 55000, "dis": 65000, "pay": 75000, "tkt": 6000,
                "msg": 95000, "call": 15000, "wa": 16000, "file": 4000}
    for kind, query in queries.items():
        try:
            row = conn.execute(query).fetchone()
            max_val = row[0] if row and row[0] else defaults[kind]
            _seq[kind] = max_val
        except Exception:
            _seq[kind] = defaults[kind]
    _seq_initialized = True


def next_id(kind, prefix):
    _init_seq()
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
    import uuid
    conn = _get_conn()
    nid = f"NTF-{uuid.uuid4().hex[:8].upper()}"
    conn.execute(
        'INSERT INTO notifications (id, channel, "to", body_ar, kind, sent_at, status) VALUES (?,?,?,?,?,?,?)',
        (nid, channel, norm_phone(to), body, kind, now_iso(), "sent")
    )
    conn.commit()
    return {"id": nid, "channel": channel, "to": norm_phone(to), "body_ar": body,
            "kind": kind, "sent_at": now_iso(), "status": "sent"}


# ---- convenience inserts
def insert_beneficiary(b):
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO beneficiaries
           (id, file_no, status, case_type, orphan_category, city, full_name_ar, phone, sections, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (b["id"], b.get("file_no"), b.get("status", "draft"), b.get("case_type"),
         b.get("orphan_category"), b.get("city"), b.get("full_name_ar"), b.get("phone"),
         json.dumps(b.get("sections", {}), ensure_ascii=False), b.get("created_at"), b.get("updated_at"))
    )
    conn.commit()


def insert_ticket(t):
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO tickets
           (id, subject_ar, channel, phone, beneficiary_id, department_id, priority, status, assigned_to, opened_at, updated_at, first_message)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (t["id"], t.get("subject_ar"), t.get("channel"), t.get("phone"),
         t.get("beneficiary_id"), t.get("department_id"), t.get("priority", "normal"),
         t.get("status", "open"), t.get("assigned_to"), t.get("opened_at"),
         t.get("updated_at"), t.get("first_message"))
    )
    conn.commit()


def insert_ticket_message(m):
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO ticket_messages (id, ticket_id, direction, sender, body_ar, sent_at)
           VALUES (?,?,?,?,?,?)""",
        (m["id"], m["ticket_id"], m["direction"], m["sender"], m["body_ar"], m["sent_at"])
    )
    conn.commit()


def insert_whatsapp_session(ws):
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO whatsapp_sessions
           (id, phone, beneficiary_id, window_expires_at, last_message_at, direction)
           VALUES (?,?,?,?,?,?)""",
        (ws["id"], ws["phone"], ws.get("beneficiary_id"),
         ws["window_expires_at"], ws.get("last_message_at"), ws.get("direction", "inbound"))
    )
    conn.commit()


def insert_call_session(cs):
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO call_sessions
           (id, phone, beneficiary_id, direction, outcome, intent, duration_seconds, notes_ar, started_at, ended_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (cs["id"], cs["phone"], cs.get("beneficiary_id"), cs.get("direction", "inbound"),
         cs.get("outcome"), cs.get("intent"), cs.get("duration_seconds"),
         cs.get("notes_ar"), cs.get("started_at"), cs.get("ended_at"))
    )
    conn.commit()


def insert_dependent(d):
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO dependents
           (id, beneficiary_id, name_ar, relationship, birth_date, gender, education, special_needs, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (d["id"], d["beneficiary_id"], d.get("name_ar"),
         d.get("relationship") or d.get("relationship_ar"),
         d.get("birth_date"), d.get("gender"),
         d.get("education") or d.get("education_stage"),
         d.get("special_needs") if d.get("special_needs") is not None else d.get("has_special_needs", False),
         d.get("created_at"))
    )
    conn.commit()


def insert_document(doc):
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO documents
           (id, beneficiary_id, document_type_id, name_ar, mandatory, status, file_path, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc["id"], doc["beneficiary_id"], doc.get("document_type_id"), doc.get("name_ar"),
         doc.get("mandatory", 1), doc.get("status", "missing"), doc.get("file_path"), doc.get("created_at"))
    )
    conn.commit()


def insert_financial_profile(fp):
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO financial_profiles
           (id, beneficiary_id, monthly_income, monthly_expenses, obligations, person_costs, need_score, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (fp["id"], fp["beneficiary_id"], fp.get("monthly_income", 0), fp.get("monthly_expenses", 0),
         json.dumps(fp.get("obligations", []), ensure_ascii=False),
         json.dumps(fp.get("person_costs", []), ensure_ascii=False),
         fp.get("need_score", 0), fp.get("created_at"))
    )
    conn.commit()


def insert_account(phone, beneficiary_id):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO accounts (phone, beneficiary_id, password_set, created_at) VALUES (?,?,0,?)",
        (norm_phone(phone), beneficiary_id, now_iso())
    )
    conn.commit()


# ---- bulk load (for API listing)
def load_table(table, limit=200):
    conn = _get_conn()
    rows = conn.execute(f"SELECT * FROM {table} LIMIT ?", (limit,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        for k in ("sections", "obligations", "person_costs"):
            if k in d and isinstance(d[k], str):
                try:
                    d[k] = json.loads(d[k])
                except:
                    pass
        result.append(d)
    return result


def count_table(table):
    conn = _get_conn()
    row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
    return row["cnt"] if row else 0


# ---- compatibility properties (return lists from DB for router compatibility)
class _TableProxy:
    """Proxy that returns DB rows as a list, supports append() for compatibility."""
    def __init__(self, table_name):
        self._table = table_name

    def __iter__(self):
        return iter(load_table(self._table, limit=10000))

    def __len__(self):
        return count_table(self._table)

    def __getitem__(self, key):
        if isinstance(key, slice):
            return load_table(self._table, limit=10000)[key]
        raise TypeError("Index must be a slice")

    def append(self, item):
        """Insert item into the appropriate table."""
        conn = _get_conn()
        if self._table == "beneficiaries":
            insert_beneficiary(item)
        elif self._table == "tickets":
            insert_ticket(item)
        elif self._table == "ticket_messages":
            insert_ticket_message(item)
        elif self._table == "whatsapp_sessions":
            insert_whatsapp_session(item)
        elif self._table == "call_sessions":
            insert_call_session(item)
        elif self._table == "dependents":
            insert_dependent(item)
        elif self._table == "documents":
            insert_document(item)
        elif self._table == "financial_profiles":
            insert_financial_profile(item)
        else:
            # Generic insert — only use columns that exist in the table
            cursor = conn.execute(f"PRAGMA table_info({self._table})")
            valid_cols = {row[1] for row in cursor.fetchall()}
            cols = [k for k in item.keys() if k in valid_cols]
            if not cols:
                return
            placeholders = ",".join(["?"] * len(cols))
            col_names = ",".join([f'"{c}"' for c in cols])
            conn.execute(f"INSERT OR REPLACE INTO {self._table} ({col_names}) VALUES ({placeholders})",
                        [item[c] for c in cols])
            conn.commit()

    def extend(self, items):
        for item in items:
            self.append(item)


# Expose tables as proxies for router compatibility
beneficiaries = _TableProxy("beneficiaries")
dependents = _TableProxy("dependents")
documents = _TableProxy("documents")
financial_profiles = _TableProxy("financial_profiles")
support_requests = _TableProxy("support_requests")
case_studies = _TableProxy("case_studies")
committee_decisions = _TableProxy("committee_decisions")
enrollments = _TableProxy("enrollments")
disbursements = _TableProxy("disbursements")
payments = _TableProxy("payments")
sponsors = _TableProxy("sponsors")
sponsorships = _TableProxy("sponsorships")
tickets = _TableProxy("tickets")
ticket_messages = _TableProxy("ticket_messages")
call_sessions = _TableProxy("call_sessions")
whatsapp_sessions = _TableProxy("whatsapp_sessions")
events = _TableProxy("events")

# Runtime-only (kept in memory, not critical)
accounts = {}
notifications = []
