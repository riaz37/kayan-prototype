"""
SQLite-backed data store for the Kayan prototype.
Reference data loaded from JSON (static). Transactional data persisted in SQLite.

Connection policy
-----------------
One connection PER THREAD, in autocommit mode (isolation_level=None).

FastAPI runs sync endpoints in a threadpool, so a single shared connection was
both a thread-safety hazard and a availability hazard: a statement that raised
mid-transaction left the write lock held, and every later write in the process
failed with "database is locked" until restart. Autocommit means there is no
open transaction to leak. Use tx() where several statements must land together.
"""
import json, os, sqlite3, threading, unicodedata
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

REF_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "reference-data")
DATA_DIR = os.path.join(os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data")))
DB_PATH = os.path.join(DATA_DIR, "kayan.db")

_local = threading.local()


def _get_conn():
    """The calling thread's connection. Autocommit; WAL; 10s busy timeout."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, isolation_level=None, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        _local.conn = conn
    return conn


@contextmanager
def tx():
    """Group several writes into one transaction; rolls back on any exception."""
    conn = _get_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


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
            eligibility_verified INTEGER DEFAULT 0,
            approved_at TEXT,
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
            note_ar TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS financial_profiles (
            id TEXT PRIMARY KEY,
            beneficiary_id TEXT,
            monthly_income REAL DEFAULT 0,
            monthly_expenses REAL DEFAULT 0,
            obligations TEXT DEFAULT '[]',
            person_costs TEXT DEFAULT '[]',
            income_breakdown TEXT DEFAULT '[]',
            household_size INTEGER DEFAULT 1,
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
            social_researcher_id TEXT,
            notes_ar TEXT,
            recommendation_ar TEXT,
            steps TEXT DEFAULT '[]',
            status TEXT DEFAULT 'open',
            opened_at TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS committee_decisions (
            id TEXT PRIMARY KEY,
            support_request_id TEXT,
            beneficiary_id TEXT,
            decision TEXT,
            amount REAL,
            notes_ar TEXT,
            reason_ar TEXT,
            required_documents_ar TEXT DEFAULT '[]',
            committee_members TEXT DEFAULT '[]',
            notified_whatsapp INTEGER DEFAULT 0,
            notified_sms INTEGER DEFAULT 0,
            decided_by TEXT,
            decided_at TEXT
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            id TEXT PRIMARY KEY,
            beneficiary_id TEXT,
            program_id TEXT,
            support_request_id TEXT,
            type TEXT DEFAULT 'one_time',
            monthly_amount REAL DEFAULT 0,
            total_approved REAL DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
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
            approved_by TEXT,
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
            type TEXT,
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
            kind TEXT DEFAULT 'restricted',
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
            is_internal INTEGER DEFAULT 0,
            sent_at TEXT
        );

        CREATE TABLE IF NOT EXISTS call_sessions (
            id TEXT PRIMARY KEY,
            phone TEXT,
            beneficiary_id TEXT,
            sip_call_id TEXT,
            to_number TEXT,
            identified INTEGER DEFAULT 0,
            language TEXT DEFAULT 'ar',
            dialect TEXT,
            direction TEXT DEFAULT 'inbound',
            outcome TEXT,
            intent TEXT,
            duration_seconds INTEGER DEFAULT 0,
            notes_ar TEXT,
            transcript_ar TEXT,
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
            name_ar TEXT,
            description_ar TEXT,
            program_id TEXT,
            event_date TEXT,
            location TEXT,
            capacity INTEGER DEFAULT 0,
            registered INTEGER DEFAULT 0,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS event_registrations (
            id TEXT PRIMARY KEY,
            event_id TEXT,
            beneficiary_id TEXT,
            registered_at TEXT,
            UNIQUE (event_id, beneficiary_id)
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


# CREATE TABLE IF NOT EXISTS never alters an existing table, so a database
# created by an older build keeps its old columns and the new code 500s against
# it ("no such column: ..."). Every column added after a table first shipped
# must therefore also be listed here.
_MIGRATIONS = {
    "beneficiaries":       [("eligibility_verified", "INTEGER DEFAULT 0"), ("approved_at", "TEXT")],
    "documents":           [("note_ar", "TEXT"), ("updated_at", "TEXT")],
    "financial_profiles":  [("income_breakdown", "TEXT DEFAULT '[]'"),
                            ("household_size", "INTEGER DEFAULT 1")],
    "support_requests":    [("decision", "TEXT"), ("case_description_ar", "TEXT"),
                            ("internal_classification", "TEXT"), ("channel", "TEXT"),
                            ("requested_amount_sar", "REAL"), ("title_ar", "TEXT"),
                            ("updated_at", "TEXT")],
    "case_studies":        [("social_researcher_id", "TEXT"), ("status", "TEXT DEFAULT 'open'"),
                            ("opened_at", "TEXT")],
    "committee_decisions": [("beneficiary_id", "TEXT"), ("reason_ar", "TEXT"),
                            ("required_documents_ar", "TEXT DEFAULT '[]'"),
                            ("committee_members", "TEXT DEFAULT '[]'"),
                            ("notified_whatsapp", "INTEGER DEFAULT 0"),
                            ("notified_sms", "INTEGER DEFAULT 0")],
    "enrollments":         [("support_request_id", "TEXT"), ("type", "TEXT DEFAULT 'one_time'"),
                            ("monthly_amount", "REAL DEFAULT 0"), ("total_approved", "REAL DEFAULT 0"),
                            ("start_date", "TEXT"), ("end_date", "TEXT")],
    "disbursements":       [("approved_by", "TEXT")],
    "ticket_messages":     [("is_internal", "INTEGER DEFAULT 0")],
    "call_sessions":       [("sip_call_id", "TEXT"), ("to_number", "TEXT"),
                            ("identified", "INTEGER DEFAULT 0"), ("language", "TEXT DEFAULT 'ar'"),
                            ("dialect", "TEXT"), ("transcript_ar", "TEXT")],
    "sponsors":            [("type", "TEXT")],
    "sponsorships":        [("kind", "TEXT DEFAULT 'restricted'")],
    "events":              [("name_ar", "TEXT"), ("program_id", "TEXT"),
                            ("capacity", "INTEGER DEFAULT 0"), ("registered", "INTEGER DEFAULT 0"),
                            ("status", "TEXT DEFAULT 'scheduled'")],
}


def _migrate():
    """Add any column the current code expects but an older database lacks."""
    conn = _get_conn()
    for table, columns in _MIGRATIONS.items():
        try:
            have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        except sqlite3.Error:
            continue
        if not have:
            continue  # table does not exist; _init_db created the current shape
        for name, decl in columns:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def _columns(table):
    conn = _get_conn()
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _backfill():
    """Reconcile rows written before the column names were unified."""
    conn = _get_conn()

    # Older seeds wrote support_requests.amount / .description_ar; the API has
    # always written requested_amount_sar / case_description_ar. Same field —
    # which is why the console showed blank amounts for every seeded request.
    sr = _columns("support_requests")
    if {"amount", "requested_amount_sar"} <= sr:
        conn.execute("""UPDATE support_requests SET requested_amount_sar = amount
                        WHERE requested_amount_sar IS NULL AND amount IS NOT NULL""")
    if {"description_ar", "case_description_ar"} <= sr:
        conn.execute("""UPDATE support_requests SET case_description_ar = description_ar
                        WHERE case_description_ar IS NULL AND description_ar IS NOT NULL""")

    ev = _columns("events")
    if {"title_ar", "name_ar"} <= ev:
        conn.execute("UPDATE events SET name_ar = title_ar WHERE name_ar IS NULL")

    # committee_decisions.beneficiary_id was added late; recover it via the request.
    if "beneficiary_id" in _columns("committee_decisions"):
        conn.execute("""UPDATE committee_decisions SET beneficiary_id = (
                            SELECT sr.beneficiary_id FROM support_requests sr
                            WHERE sr.id = committee_decisions.support_request_id)
                        WHERE beneficiary_id IS NULL""")


_init_db()
_migrate()
_backfill()


# ---- helpers
def now():
    """Naive UTC. Timestamps are stored as '...Z' strings and compared against
    each other, so the whole codebase stays on naive-UTC rather than mixing
    aware and naive datetimes (which raises on subtraction)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def now_iso():
    return now().replace(microsecond=0).isoformat() + "Z"


def parse(ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", ""))


def phone_digits(p) -> str:
    """Every digit in a phone number, in order, as ASCII.

    Arabic-Indic numerals count: ``"٠٥٩"``.isdigit() is True in Python but
    ``int()`` of the joined string is not what anyone wants, and a caller
    who dictates their number over the phone can easily produce them.
    """
    out = []
    for ch in str(p or ""):
        if ch.isascii():
            if ch.isdigit():
                out.append(ch)
        elif ch.isdigit():                    # ٠١٢٣ / ۰۱۲۳
            out.append(str(unicodedata.digit(ch)))
    return "".join(out)


# Every number in this system is a mobile — it is what the file is reached
# on and what WhatsApp is keyed by. Saudi mobiles are 10 digits local
# (05XXXXXXXX) and 12 with the country code; every number in the seeded and
# live data is 11 or more. A floor of 7 (E.164's shortest legal number)
# would accept "0501234" — two thirds of a dictated Saudi mobile — as
# whole, which is the failure this exists to catch, so the floor is the
# shortest real mobile rather than the shortest legal number.
MIN_PHONE_DIGITS = 9
MAX_PHONE_DIGITS = 15


def usable_phone(p) -> bool:
    """Could someone actually ring this?

    Voice made this worth enforcing. A caller reads their number out in
    groups, the pause closes the utterance, and the agent is handed
    ``"0171"`` — which the API used to accept as a phone number, answer
    "not registered", and then store on a real file. See the phone-number
    section of SIP_INTEGRATION.md.
    """
    return MIN_PHONE_DIGITS <= len(phone_digits(p)) <= MAX_PHONE_DIGITS


def norm_phone(p):
    if not p:
        return ""
    p = phone_digits(p) if not str(p).lstrip("+").isascii() else \
        "".join(ch for ch in str(p) if ch.isdigit() or ch == "+").lstrip("+")
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


# ---- JSON-valued columns, decoded on read and encoded on write in one place
JSON_COLUMNS = {
    "sections": dict,
    "obligations": list,
    "person_costs": list,
    "income_breakdown": list,
    "steps": list,
    "required_documents_ar": list,
    "committee_members": list,
}


def _decode(row):
    """sqlite3.Row -> dict with JSON columns parsed into real Python values."""
    if row is None:
        return None
    d = dict(row)
    for key, kind in JSON_COLUMNS.items():
        if key in d:
            v = d[key]
            if isinstance(v, str):
                try:
                    d[key] = json.loads(v)
                except (ValueError, TypeError):
                    d[key] = kind()
            elif v is None:
                d[key] = kind()
    return d


def _encode(key, value):
    """Python value -> the form SQLite can bind (JSON columns become text)."""
    if key in JSON_COLUMNS or isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return int(value)
    return value


def update_row(table, row_id, updates, id_column="id"):
    """Persist a partial update. The missing half of every read-modify-write
    in the routers: they used to mutate the dict returned by a SELECT and
    return 200 without ever writing it back."""
    if not updates:
        return 0
    valid = _columns(table)
    cols = [k for k in updates if k in valid]
    if not cols:
        return 0
    conn = _get_conn()
    sets = ", ".join(f'"{c}" = ?' for c in cols)
    values = [_encode(c, updates[c]) for c in cols] + [row_id]
    cur = conn.execute(f"UPDATE {table} SET {sets} WHERE {id_column} = ?", values)
    return cur.rowcount


# ---- beneficiary lookups
def get_beneficiary(bid):
    conn = _get_conn()
    return _decode(conn.execute("SELECT * FROM beneficiaries WHERE id = ?", (bid,)).fetchone())


def beneficiary_by_phone(phone):
    """Resolve a caller to their file.

    Runs on every inbound WhatsApp message and every call, so try the indexed
    top-level phone column first and only fall back to scanning SEC-CONTACT
    (older rows recorded the number solely inside the sections blob).
    """
    p = norm_phone(phone)
    if not p:
        return None
    conn = _get_conn()
    for row in conn.execute("SELECT * FROM beneficiaries WHERE phone IS NOT NULL"):
        if norm_phone(row["phone"]) == p:
            return _decode(row)
    for row in conn.execute("SELECT * FROM beneficiaries"):
        contact = (json.loads(row["sections"] or "{}")).get("SEC-CONTACT", {})
        if norm_phone(contact.get("mobile")) == p or norm_phone(contact.get("whatsapp")) == p:
            return _decode(row)
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
    return _decode(conn.execute(
        "SELECT * FROM financial_profiles WHERE beneficiary_id = ?", (bid,)).fetchone())


def get_support_request(request_id):
    conn = _get_conn()
    sr = _decode(conn.execute(
        "SELECT * FROM support_requests WHERE id = ?", (request_id,)).fetchone())
    return _normalize_request(sr)


def _normalize_request(sr):
    """Fill the canonical field from its legacy twin for rows seeded long ago,
    and derive title_ar from the request type when the seed omitted it."""
    if not sr:
        return None
    if sr.get("requested_amount_sar") is None and sr.get("amount") is not None:
        sr["requested_amount_sar"] = sr["amount"]
    if not sr.get("case_description_ar") and sr.get("description_ar"):
        sr["case_description_ar"] = sr["description_ar"]
    if not sr.get("title_ar"):
        rt = by_id["request_type"].get(sr.get("request_type_id")) or {}
        sr["title_ar"] = rt.get("name_ar")
    if not sr.get("internal_classification"):
        sr["internal_classification"] = "اعتيادي"
    return sr


def get_disbursement(did):
    conn = _get_conn()
    return _decode(conn.execute("SELECT * FROM disbursements WHERE id = ?", (did,)).fetchone())


def get_event(eid):
    conn = _get_conn()
    return _decode(conn.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone())


def get_enrollment(eid):
    conn = _get_conn()
    return _decode(conn.execute("SELECT * FROM enrollments WHERE id = ?", (eid,)).fetchone())


def get_case(case_id):
    conn = _get_conn()
    return _decode(conn.execute("SELECT * FROM case_studies WHERE id = ?", (case_id,)).fetchone())


def requests_for(bid):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM support_requests WHERE beneficiary_id = ?", (bid,)).fetchall()
    return [_normalize_request(_decode(r)) for r in rows]


def requests_for_all():
    """List all support requests with beneficiary name and program info."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM support_requests ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        sr = _normalize_request(_decode(r))
        b = get_beneficiary(sr["beneficiary_id"])
        sr["name_ar"] = beneficiary_name(b)
        sr["program_ar"] = program_name(sr["program_id"])
        dec = decision_for(sr["id"])
        # decision_ar must be the human label; the raw code goes in `decision`.
        sr["decision"] = dec["decision"] if dec else sr.get("decision")
        sr["decision_ar"] = dec["decision_ar"] if dec else None
        sr["approved_amount_sar"] = dec["amount"] if dec else None
        out.append(sr)
    return out


def decision_for(srid):
    conn = _get_conn()
    d = _decode(conn.execute(
        "SELECT * FROM committee_decisions WHERE support_request_id = ?", (srid,)).fetchone())
    if not d:
        return None
    d["decision_ar"] = next((dt["name_ar"] for dt in decision_types if dt["id"] == d["decision"]),
                            d["decision"])
    # The API surface has always called this approved_amount_sar; the column is `amount`.
    d["approved_amount_sar"] = d.get("amount")
    return d


def case_for(srid):
    conn = _get_conn()
    return _decode(conn.execute(
        "SELECT * FROM case_studies WHERE support_request_id = ?", (srid,)).fetchone())


def enrollments_for(bid):
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM enrollments WHERE beneficiary_id = ?", (bid,)).fetchall()
    return [_decode(r) for r in rows]


def beneficiary_name(b):
    """Display name, wherever it happens to live on this row."""
    if not b:
        return None
    return (b.get("sections", {}).get("SEC-BASIC", {}).get("full_name_ar")
            or b.get("full_name_ar"))


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


# Thin named wrappers over update_row, kept because the routers read better
# with them and they document which tables are meant to be mutated.
def update_beneficiary(bid, updates):
    return update_row("beneficiaries", bid, {**updates, "updated_at": now_iso()})


def update_support_request(srid, updates):
    return update_row("support_requests", srid, {**updates, "updated_at": now_iso()})


def update_case(case_id, updates):
    return update_row("case_studies", case_id, updates)


def update_finance(fp_id, updates):
    return update_row("financial_profiles", fp_id, updates)


def update_document(doc_id, updates):
    return update_row("documents", doc_id, {**updates, "updated_at": now_iso()})


def update_disbursement(disbursement_id, updates):
    return update_row("disbursements", disbursement_id, updates)


def update_payment(payment_id, updates):
    return update_row("payments", payment_id, updates)


def update_ticket(ticket_id, updates):
    return update_row("tickets", ticket_id, {**updates, "updated_at": now_iso()})


def update_event(event_id, updates):
    return update_row("events", event_id, updates)


def insert_payment(p):
    """Insert a payment record into the database."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO payments (id, disbursement_id, beneficiary_id, amount, method, reference, paid_at)
           VALUES (?,?,?,?,?,?,?)""",
        (p["id"], p.get("disbursement_id"), p.get("beneficiary_id"), p.get("amount"),
         p.get("method"), p.get("reference"), p.get("paid_at")))


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
    exp = parse(session.get("window_expires_at"))
    if exp is None:
        return {"open": False, "remaining_seconds": 0, "remaining_ar": "منتهية"}
    rem = (exp - now()).total_seconds()
    if rem <= 0:
        return {"open": False, "remaining_seconds": 0, "remaining_ar": "منتهية"}
    h, m = int(rem // 3600), int((rem % 3600) // 60)
    return {"open": True, "remaining_seconds": int(rem), "remaining_ar": f"{h}س {m}د"}


def ticket_sla(t):
    if t.get("status") == "closed":
        return {"breached": False, "remaining_ar": "-", "remaining_seconds": 0}
    dep = by_id["department"].get(t.get("department_id")) or {}
    hours = dep.get("sla_hours", 24)
    opened = parse(t.get("opened_at"))
    if opened is None:
        return {"breached": False, "remaining_ar": "-", "remaining_seconds": 0}
    rem = (opened + timedelta(hours=hours) - now()).total_seconds()
    if rem <= 0:
        return {"breached": True, "remaining_ar": "منتهية المدة", "remaining_seconds": 0}
    h, m = int(rem // 3600), int((rem % 3600) // 60)
    return {"breached": False, "remaining_ar": f"{h}س {m}د", "remaining_seconds": int(rem)}


# ---- id sequences
# Counters start from the highest existing numeric suffix so a restart never
# reissues an ID. Non-numeric suffixes (older seeds used UUID hex, which CAST
# turned into nonsense like 18131096) are ignored rather than trusted.
_seq = {}
_seq_lock = threading.Lock()
_seq_initialized = False

_SEQ_SOURCES = {
    "ben":  ("beneficiaries", "id", 2000),
    "dep":  ("dependents", "id", 6000),
    "doc":  ("documents", "id", 8000),
    "sr":   ("support_requests", "id", 25000),
    "case": ("case_studies", "id", 35000),
    "dec":  ("committee_decisions", "id", 45000),
    "enr":  ("enrollments", "id", 55000),
    "dis":  ("disbursements", "id", 65000),
    "pay":  ("payments", "id", 75000),
    "tkt":  ("tickets", "id", 6000),
    "msg":  ("ticket_messages", "id", 95000),
    "call": ("call_sessions", "id", 15000),
    "wa":   ("whatsapp_sessions", "id", 16000),
    "evt":  ("events", "id", 17000),
    "reg":  ("event_registrations", "id", 18000),
    "spo":  ("sponsors", "id", 19000),
    "kaf":  ("sponsorships", "id", 20000),
    "file": ("beneficiaries", "file_no", 4000),
}


def _init_seq():
    global _seq_initialized
    if _seq_initialized:
        return
    conn = _get_conn()
    for kind, (table, column, default) in _SEQ_SOURCES.items():
        best = default
        try:
            for (value,) in conn.execute(f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL"):
                suffix = str(value).rsplit("-", 1)[-1]
                if suffix.isdigit():
                    best = max(best, int(suffix))
        except sqlite3.Error:
            pass
        _seq[kind] = best
    _seq_initialized = True


def next_id(kind, prefix):
    with _seq_lock:
        _init_seq()
        _seq[kind] = _seq.get(kind, 0) + 1
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
    sent_at = now_iso()
    conn.execute(
        'INSERT INTO notifications (id, channel, "to", body_ar, kind, sent_at, status) VALUES (?,?,?,?,?,?,?)',
        (nid, channel, norm_phone(to), body, kind, sent_at, "sent")
    )
    return {"id": nid, "channel": channel, "to": norm_phone(to), "body_ar": body,
            "kind": kind, "sent_at": sent_at, "status": "sent"}


def notifications_recent(limit=30):
    conn = _get_conn()
    rows = conn.execute(
        'SELECT * FROM notifications ORDER BY sent_at DESC LIMIT ?', (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---- inserts
# One generic writer instead of a hand-written INSERT per table. The old
# per-table statements listed their columns explicitly, so every column added
# later was silently dropped on write (that is how case-study `steps`,
# `is_internal` and the whole call-session payload went missing).
_ALIASES = {
    "dependents": {"relationship_ar": "relationship", "education_stage": "education",
                   "has_special_needs": "special_needs"},
    "call_sessions": {"from_number": "phone", "duration_sec": "duration_seconds"},
    "support_requests": {},
    "committee_decisions": {"approved_amount_sar": "amount"},
    "sponsorships": {"monthly_amount_sar": "monthly_amount"},
    "events": {"title_ar": "name_ar", "date": "event_date"},
}


def insert_row(table, item):
    """Insert (or replace) a row, keeping only columns the table really has."""
    valid = _columns(table)
    aliases = _ALIASES.get(table, {})
    row = {}
    for key, value in item.items():
        col = aliases.get(key, key)
        if col in valid and (col not in row or row[col] in (None, "")):
            row[col] = _encode(col, value)
    if not row:
        return None
    cols = list(row)
    conn = _get_conn()
    conn.execute(
        f'INSERT OR REPLACE INTO {table} ({",".join(chr(34)+c+chr(34) for c in cols)}) '
        f'VALUES ({",".join("?" * len(cols))})',
        [row[c] for c in cols])
    return item.get("id")


def insert_beneficiary(b):
    return insert_row("beneficiaries", b)


def insert_ticket(t):
    return insert_row("tickets", {"priority": "medium", "status": "open", **t})


def insert_ticket_message(m):
    return insert_row("ticket_messages", m)


def insert_whatsapp_session(ws):
    return insert_row("whatsapp_sessions", {"direction": "inbound", **ws})


def insert_call_session(cs):
    return insert_row("call_sessions", {"direction": "inbound", **cs})


def insert_dependent(d):
    return insert_row("dependents", d)


def insert_document(doc):
    return insert_row("documents", {"mandatory": 1, "status": "missing", **doc})


def insert_financial_profile(fp):
    return insert_row("financial_profiles", {"monthly_income": 0, "monthly_expenses": 0,
                                             "obligations": [], "person_costs": [],
                                             "household_size": 1, "need_score": 0, **fp})


def insert_account(phone, beneficiary_id):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO accounts (phone, beneficiary_id, password_set, created_at) VALUES (?,?,0,?)",
        (norm_phone(phone), beneficiary_id, now_iso()))


# ---- bulk load (for API listing)
def load_table(table, limit=200):
    conn = _get_conn()
    rows = conn.execute(f"SELECT * FROM {table} LIMIT ?", (limit,)).fetchall()
    return [_decode(r) for r in rows]


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
        insert_row(self._table, item)

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
notifications = _TableProxy("notifications")


class _AccountsView:
    """`accounts` used to be a dict that was never populated, so check-phone
    only ever matched via beneficiary lookup. Back it with the real table."""

    def get(self, phone, default=None):
        conn = _get_conn()
        row = conn.execute("SELECT * FROM accounts WHERE phone = ?", (norm_phone(phone),)).fetchone()
        return dict(row) if row else default

    def __contains__(self, phone):
        return self.get(phone) is not None


accounts = _AccountsView()
