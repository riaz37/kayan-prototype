"""Shared fixtures. Every test module gets its own throwaway database."""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session", autouse=True)
def _isolated_database():
    """Point DATA_DIR at a temp dir BEFORE backend.store is imported.

    backend.store opens its connection and runs migrations at import time, so
    this has to happen before the first import of anything under backend/.
    """
    tmp = tempfile.mkdtemp(prefix="kayan-tests-")
    os.environ["DATA_DIR"] = tmp
    yield tmp


@pytest.fixture(scope="session")
def db(_isolated_database):
    from backend import store
    return store


@pytest.fixture(scope="session")
def client(_isolated_database):
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def beneficiary(client, db):
    """An approved file with a complete form, ready for support requests."""
    phone = f"05555{db.next_id('tkt', '')[-5:].zfill(5)}"
    created = client.post("/beneficiary/create-file", json={
        "phone": phone, "case_type": "CT-IND", "orphan_category_id": "OC-UNK",
        "full_name_ar": "مستفيد اختبار", "city": "الرياض"}).json()
    bid = created["beneficiary_id"]
    client.patch(f"/beneficiary/{bid}/section/SEC-EDU",
                 json={"values": {"monthly_salary": 3000, "education_level": "ثانوي",
                                  "employment_status": "يعمل", "employer": "جهة"}})
    client.patch(f"/beneficiary/{bid}/section/SEC-BANK",
                 json={"values": {"bank_name": "الراجحي", "iban": "SA0380000000608010167519",
                                  "account_holder_name": "مستفيد اختبار"}})
    db.update_beneficiary(bid, {"status": "approved"})
    return bid
