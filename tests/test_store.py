"""
Store-level invariants: schema migration, connection safety, ID sequences,
and the endpoints that used to 500 on a column that did not exist.
"""
import sqlite3
import threading

import pytest


def test_migration_adds_missing_columns_to_an_old_database(tmp_path):
    """A database created by an older build must be upgraded, not 500'd against.
    CREATE TABLE IF NOT EXISTS never alters an existing table."""
    db_path = tmp_path / "kayan.db"
    old = sqlite3.connect(db_path)
    old.executescript("""
        CREATE TABLE documents (id TEXT PRIMARY KEY, beneficiary_id TEXT, status TEXT);
        CREATE TABLE enrollments (id TEXT PRIMARY KEY, beneficiary_id TEXT, program_id TEXT);
        CREATE TABLE support_requests (id TEXT PRIMARY KEY, beneficiary_id TEXT,
                                       amount REAL, description_ar TEXT);
        INSERT INTO support_requests VALUES ('SR-1', 'BEN-1', 1500.0, 'وصف قديم');
    """)
    old.commit()
    old.close()

    import importlib
    import os
    from backend import store
    previous = os.environ.get("DATA_DIR")
    os.environ["DATA_DIR"] = str(tmp_path)
    try:
        migrated = importlib.reload(store)
        assert "updated_at" in migrated._columns("documents")
        assert "support_request_id" in migrated._columns("enrollments")
        assert "case_description_ar" in migrated._columns("support_requests")
        # legacy amount/description are copied onto the canonical names
        row = migrated.get_support_request("SR-1")
        assert row["requested_amount_sar"] == 1500.0
        assert row["case_description_ar"] == "وصف قديم"
    finally:
        if previous:
            os.environ["DATA_DIR"] = previous
        importlib.reload(store)


def test_failed_write_does_not_wedge_later_writes(db, client):
    """A statement that raised used to leave the shared connection inside an
    open transaction, so every later write failed with 'database is locked'
    until the process restarted."""
    with pytest.raises(sqlite3.Error):
        db._get_conn().execute("UPDATE documents SET no_such_column = 1")

    r = client.post("/crm/tickets", json={
        "subject_ar": "بعد الخطأ", "channel": "whatsapp", "department_id": "DEP-BEN"})
    assert r.status_code == 200


def test_ids_are_unique_under_concurrency(db):
    """next_id is called from FastAPI's threadpool; it must not hand out
    duplicates."""
    seen, lock = [], threading.Lock()

    def grab():
        local = [db.next_id("tkt", "TK-") for _ in range(25)]
        with lock:
            seen.extend(local)

    threads = [threading.Thread(target=grab) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(seen) == len(set(seen))


def test_id_sequence_ignores_non_numeric_suffixes(db):
    """An older seed used UUID hex IDs; CAST turned them into values like
    18131096 and the counter jumped there."""
    conn = db._get_conn()
    conn.execute("INSERT OR REPLACE INTO events (id) VALUES ('EVT-DEADBEEF')")
    db._seq_initialized = False
    db._seq.clear()
    new_id = db.next_id("evt", "EVT-")
    assert int(new_id.rsplit("-", 1)[1]) < 100000


def test_json_columns_round_trip(db):
    db.insert_row("case_studies", {"id": "CASE-RT", "support_request_id": "SR-RT",
                                   "steps": [{"step_id": "CS-FIELD", "status": "scheduled"}]})
    stored = db.get_case("CASE-RT")
    assert isinstance(stored["steps"], list)
    assert stored["steps"][0]["step_id"] == "CS-FIELD"


def test_insert_row_keeps_columns_the_old_writer_dropped(db):
    """The hand-written INSERTs listed columns explicitly, so anything added
    later was silently discarded on write."""
    db.insert_call_session({"id": "CALL-KEEP", "phone": "966500000000",
                            "dialect": "نجدي", "identified": 1, "sip_call_id": "sip-x"})
    row = dict(db._get_conn().execute(
        "SELECT * FROM call_sessions WHERE id = 'CALL-KEEP'").fetchone())
    assert row["dialect"] == "نجدي"
    assert row["sip_call_id"] == "sip-x"


def test_events_endpoint_reads_real_columns(client, db):
    """/events read program_id, status, capacity — none of which existed."""
    db.insert_row("events", {"id": "EVT-T1", "name_ar": "فعالية", "program_id": "PRG-QOL",
                             "event_date": "2026-09-01", "capacity": 2, "registered": 0,
                             "status": "scheduled"})
    r = client.get("/events")
    assert r.status_code == 200
    row = next(e for e in r.json()["events"] if e["id"] == "EVT-T1")
    assert row["program_ar"] == "برنامج جودة حياة"


def test_event_registration_is_capped_and_deduplicated(client, db, beneficiary):
    db.insert_row("events", {"id": "EVT-T2", "name_ar": "ورشة", "program_id": "PRG-QOL",
                             "event_date": "2026-09-01", "capacity": 1, "registered": 0,
                             "status": "scheduled"})
    assert client.post("/events/EVT-T2/register",
                       json={"beneficiary_id": beneficiary}).status_code == 200
    # same person again
    assert client.post("/events/EVT-T2/register",
                       json={"beneficiary_id": beneficiary}).status_code == 409
    assert db.get_event("EVT-T2")["registered"] == 1


def test_sponsorships_totals_use_the_real_column(client, db):
    """/sponsorships and /reports/overview read monthly_amount_sar; the column
    is monthly_amount, so both raised KeyError once any row existed."""
    db.insert_row("sponsors", {"id": "SPO-T1", "name_ar": "كافل", "type": "individual"})
    db.insert_row("sponsorships", {"id": "KAF-T1", "sponsor_id": "SPO-T1",
                                   "beneficiary_id": "BEN-X", "monthly_amount": 500,
                                   "status": "active"})
    body = client.get("/sponsorships").json()
    assert body["monthly_total_sar"] >= 500
    assert client.get("/reports/overview").status_code == 200


def test_phone_normalisation(db):
    assert db.norm_phone("0501234567") == "966501234567"
    assert db.norm_phone("+966501234567") == "966501234567"
    assert db.norm_phone("00966501234567") == "966501234567"
    assert db.norm_phone("501234567") == "966501234567"
    assert db.norm_phone("") == ""
    assert db.norm_phone(None) == ""


def test_sla_handles_missing_timestamps(db):
    assert db.ticket_sla({"status": "open", "department_id": "DEP-BEN",
                          "opened_at": None})["remaining_ar"] == "-"
    assert db.ticket_sla({"status": "closed", "department_id": "DEP-BEN",
                          "opened_at": None})["breached"] is False


# --------------------------------------------- a phone number you can ring
def test_half_a_dictated_number_is_not_a_phone_number(db):
    """Voice made this worth enforcing.

    A caller reads their number in groups, the pause closes the utterance,
    and what reaches the API is "0171". Every digit-count in the system was
    implicit, so that was accepted as a phone number.
    """
    for fragment in ("0171", "05", "", None, "1000", "1" * 16,
                     # Two thirds of a Saudi mobile. E.164's floor of 7
                     # would call this whole; every real number in this
                     # system is 11 digits or more.
                     "0501234", "01712345"):
        assert not db.usable_phone(fragment), f"{fragment!r} is not dialable"
    for real in ("0501234567", "966501234567", "+966 50 123 4567",
                 "01712345678"):
        assert db.usable_phone(real), f"{real!r} is dialable"


def test_arabic_indic_numerals_normalise_to_a_saudi_number(db):
    """`"٠٥٩".isdigit()` is True in Python, so the old filter kept the
    Arabic characters and the 05 -> 966 rewrite never fired — a caller who
    dictated their number in Arabic numerals got a different key from the
    same number typed in Latin ones."""
    assert db.phone_digits("٠٥٩٤٦٤٩٢٦١") == "0594649261"
    assert db.norm_phone("٠٥٩٤٦٤٩٢٦١") == db.norm_phone("0594649261")
