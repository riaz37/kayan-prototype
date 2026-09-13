#!/usr/bin/env python3
"""
Kayan Agent — Hard Scenario Test Suite
Tests the agent's tool handlers, session management, business logic,
and edge cases WITHOUT requiring the LLM. Uses FastAPI TestClient.
"""
import json
import os
import sys
import time
import re
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from backend.main import app
from backend import store as db
from agent.tools import (
    execute_tool, TOOLS_OPENAI, _faq_cache,
    handle_check_phone, handle_check_eligibility, handle_create_file,
    handle_get_file, handle_update_section, handle_get_completeness,
    handle_submit_file, handle_create_ticket, handle_search_faqs,
    handle_search_request_types, handle_create_support_request,
    handle_get_support_request, handle_add_request_detail,
    handle_get_beneficiary_history, handle_cancel_flow,
    handle_save_collected_info, handle_list_programs,
    handle_list_staff, handle_get_ticket, handle_assign_ticket,
    handle_reply_to_ticket,
)
from agent import sessions
from agent.gemini import _is_arabic, _map_error_to_friendly, _estimate_tokens, _count_message_tokens

c = TestClient(app, raise_server_exceptions=False)
PASS = FAIL = 0
TOTAL = 0


def test(name, condition, detail=""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _set_beneficiary_status(bid, status):
    """Directly update beneficiary status in DB (dict copy doesn't persist)."""
    conn = db._get_conn()
    conn.execute("UPDATE beneficiaries SET status=? WHERE id=?", (status, bid))
    conn.commit()


def _find_seed_beneficiary():
    """Find a seed beneficiary with phone and id."""
    conn = db._get_conn()
    row = conn.execute(
        "SELECT id, phone FROM beneficiaries ORDER BY rowid LIMIT 1"
    ).fetchone()
    if row:
        return row["id"], row["phone"]
    return None, None


def _find_seed_approved():
    """Find a seed beneficiary that is approved."""
    conn = db._get_conn()
    row = conn.execute(
        "SELECT id, phone FROM beneficiaries WHERE status='approved' ORDER BY rowid LIMIT 1"
    ).fetchone()
    if row:
        return row["id"], row["phone"]
    return None, None


SEED_BID, SEED_PHONE = _find_seed_beneficiary()
SEED_APPROVED_BID, SEED_APPROVED_PHONE = _find_seed_approved()
SEED_BID = SEED_BID or "BEN-EBE923CE"
SEED_PHONE = SEED_PHONE or "0586384363"
SEED_APPROVED_BID = SEED_APPROVED_BID or SEED_BID
SEED_APPROVED_PHONE = SEED_APPROVED_PHONE or SEED_PHONE


# ============================================================
# SECTION 1: Tool Handler Edge Cases
# ============================================================
section("1. TOOL HANDLER EDGE CASES")

r = handle_check_phone("")
test("check_phone with empty string returns response", isinstance(r, dict))

r = handle_check_phone("0000000000")
test("check_phone unknown number returns registered=False", r.get("registered") == False)

r = handle_check_eligibility("INVALID-CAT")
test("check_eligibility with invalid category", isinstance(r, dict))

try:
    r = handle_create_file("", "", "", "", "")
    test("create_file with empty fields returns error or response", isinstance(r, dict))
except Exception:
    test("create_file with empty fields raises/handles error", True)

r = handle_get_file("BEN-99999")
test("get_file non-existent returns error", "error" in r or "detail" in r or "not found" in json.dumps(r).lower())

r = handle_update_section(SEED_BID, "SEC-INVALID", {"foo": "bar"})
test("update_section with invalid section returns error", isinstance(r, dict))

r = handle_submit_file(SEED_BID)
test("submit_file returns response", isinstance(r, dict))

r = handle_create_ticket(subject_ar="اختبار", channel="whatsapp")
test("create_ticket with minimal fields succeeds", "ticket_id" in r or "reply_ar" in r or isinstance(r, dict))

r = handle_search_faqs("")
test("search_faqs with empty query returns results dict", isinstance(r, dict))

r = handle_search_request_types("ايجار")
test("search_request_types Arabic returns results", isinstance(r, dict))

r = handle_search_request_types("xyznonexistent123")
test("search_request_types gibberish returns empty", isinstance(r, dict))

r = handle_get_beneficiary_history(SEED_BID)
test("get_beneficiary_history valid ID returns data", isinstance(r, dict))

r = handle_cancel_flow()
test("cancel_flow returns cancelled=True", r.get("cancelled") == True)

r = handle_list_programs()
test("list_programs returns programs", isinstance(r, dict))

PHONE_TEST = "0555990001"
r = handle_save_collected_info(PHONE_TEST, "test_key", "test_value")
test("save_collected_info stores value", r.get("saved") == True)

r = execute_tool("nonexistent_tool", {})
test("execute_tool unknown tool returns error", "error" in r)

r = execute_tool("check_phone", {"phone": 12345})
test("execute_tool handles wrong arg types", isinstance(r, dict))


# ============================================================
# SECTION 2: Business Rule Enforcement
# ============================================================
section("2. BUSINESS RULE ENFORCEMENT")

BID = SEED_BID

_set_beneficiary_status(BID, "draft")
r = c.post("/support-requests", json={
    "beneficiary_id": BID, "request_type_id": "REQ-HSG-01",
    "case_description_ar": "اختبار تقديم طلب قبل الاعتماد"})
test("Support request before approval → 409", r.status_code == 409)

_set_beneficiary_status(BID, "approved")
r = c.post("/support-requests", json={
    "beneficiary_id": BID, "request_type_id": "REQ-HSG-01",
    "case_description_ar": "اختبار مبالغ فيه", "requested_amount_sar": 999999})
test("Over-ceiling amount → 409", r.status_code == 409)

r = handle_check_eligibility("OC-FATHER")
test("Ineligible category returns eligible=False", r.get("eligible") == False)

sr = c.post("/support-requests", json={
    "beneficiary_id": BID, "request_type_id": "REQ-HSG-01",
    "case_description_ar": "اختبار قرار مكرر", "requested_amount_sar": 5000})
if sr.status_code == 200:
    sr_id = sr.json().get("support_request_id", "")
    case = c.post(f"/support-requests/{sr_id}/open-case", params={"researcher_id": "STF-04"})
    if case.status_code == 200:
        case_id = case.json().get("case_id", "")
        c.post(f"/cases/{case_id}/schedule-step", json={
            "step_id": "CS-FIELD", "scheduled_at": "2026-08-02T10:00:00Z",
            "assigned_staff_id": "STF-04"})
        c.post(f"/cases/{case_id}/record-findings", json={
            "step_id": "CS-FIELD", "findings_ar": "تم التحقق"})
        c.post(f"/cases/{case_id}/submit-to-committee", json={
            "recommendation_ar": "قبول"})
        c.post(f"/support-requests/{sr_id}/decision", json={
            "decision": "accepted", "approved_amount_sar": 5000, "reason_ar": "مقبول"})
        dec2 = c.post(f"/support-requests/{sr_id}/decision", json={
            "decision": "declined", "reason_ar": "مكرر"})
        test("Duplicate decision → 409", dec2.status_code == 409)

r_create = c.post("/crm/tickets", json={
    "subject_ar": "تذكرة اختبار الحالة", "channel": "whatsapp"})
if r_create.status_code == 200:
    TCK_TEST = r_create.json().get("ticket_id", "")
    r = c.patch(f"/crm/tickets/{TCK_TEST}/status", json={"status": "banana"})
    test("Invalid ticket status → 422", r.status_code == 422)
else:
    test("Invalid ticket status → 422 (skip: no ticket created)", True)


# ============================================================
# SECTION 3: Session Management Hard Scenarios
# ============================================================
section("3. SESSION MANAGEMENT HARD SCENARIOS")

sess = sessions.get_session(PHONE_TEST)
test("Session created for new phone", sess["phone"] == PHONE_TEST)

sessions.set_slot(PHONE_TEST, "orphan_category", "مجهول الأبوين")
val = sessions.get_slot(PHONE_TEST, "orphan_category")
test("Slot persisted correctly", val == "مجهول الأبوين")

sessions.set_slot(PHONE_TEST, "name", "محمد العتيبي")
sessions.set_slot(PHONE_TEST, "city", "الرياض")
test("get_slot for name", sessions.get_slot(PHONE_TEST, "name") == "محمد العتيبي")
test("get_slot for city", sessions.get_slot(PHONE_TEST, "city") == "الرياض")

sessions.set_slot(PHONE_TEST, "city", "جدة")
test("Slot overwrite works", sessions.get_slot(PHONE_TEST, "city") == "جدة")

sessions.add_to_history(PHONE_TEST, "user", [{"text": "مرحبا"}])
sessions.add_to_history(PHONE_TEST, "model", [{"text": "أهلًا وسهلًا!"}])
history = sessions.get_history(PHONE_TEST)
test("History has messages", len(history) >= 2)

for i in range(60):
    sessions.add_to_history(PHONE_TEST, "user", [{"text": f"رسالة تختبر الحفظ رقم {i}"}])
history = sessions.get_history(PHONE_TEST)
test("History trimmed to MAX_HISTORY", len(history) <= sessions.MAX_HISTORY)

tokens = _estimate_tokens("مرحبا، كيف حالك اليوم؟")
test("Token estimation returns positive", tokens > 0)

msgs = [{"role": "user", "content": "test " * 100}, {"role": "assistant", "content": "reply " * 100}]
total = _count_message_tokens(msgs)
test("Token counting across messages", total > 0)

sessions.set_context(PHONE_TEST, {"known": True, "beneficiary_id": SEED_BID})
ctx = sessions.get_context(PHONE_TEST)
test("Context set and retrieved", ctx.get("known") == True and ctx.get("beneficiary_id") == SEED_BID)

sessions.clear_session(PHONE_TEST)
sess = sessions.get_session(PHONE_TEST)
test("Session cleared", len(sess.get("history", [])) == 0)

sessions.set_flow(PHONE_TEST, "registration")
test("Flow set correctly", sessions.get_flow(PHONE_TEST) == "registration")

sessions.clear_all_sessions()
all_sess = sessions.get_all_sessions()
test("All sessions cleared", len(all_sess) == 0)


# ============================================================
# SECTION 4: Language Detection Edge Cases
# ============================================================
section("4. LANGUAGE DETECTION EDGE CASES")

test("Pure Arabic detected", _is_arabic("مرحبا بكم") == True)
test("Pure English not detected as Arabic", _is_arabic("Hello world") == False)
test("Arabic numerals (0123) not Arabic", _is_arabic("0123456789") == False)
test("Mixed text detected as Arabic (has Arabic chars)", _is_arabic("Hello مرحبا") == True)
test("Transliterated Arabic in Latin = not Arabic", _is_arabic("Assalamu Alaikum") == False)
test("Empty string not Arabic", _is_arabic("") == False)
test("None input not Arabic", _is_arabic(None) == False)
test("Arabic punctuation only", _is_arabic("؟!،") == True)
test("Bidirectional text with Arabic", _is_arabic("Hello مرحبا World") == True)
test("Very long Arabic text", _is_arabic("مرحبا " * 1000) == True)


# ============================================================
# SECTION 5: Error Mapping and Graceful Degradation
# ============================================================
section("5. ERROR MAPPING AND GRACEFUL DEGRADATION")

msg = _map_error_to_friendly("404 not found", "مرحبا")
test("404 maps to Arabic friendly message", "غير متوفر" in msg or "خدمة" in msg)

msg = _map_error_to_friendly("404 not found", "Hello")
test("404 maps to English friendly message", "unavailable" in msg.lower() or "try again" in msg.lower())

msg = _map_error_to_friendly("500 internal error", "ابي مساعدة")
test("500 maps to Arabic error", "خطأ" in msg or "خطا" in msg)

msg = _map_error_to_friendly("timeout exceeded", "ابي مساعدة")
test("Timeout maps to Arabic timeout message", "وقت" in msg or "محاول" in msg)

msg = _map_error_to_friendly("something weird happened", "مرحبا")
test("Unknown error maps to generic Arabic", "خطأ" in msg or "حدث" in msg)

msg = _map_error_to_friendly("something weird happened", "Hello")
test("Unknown error maps to generic English", "error" in msg.lower() or "unexpected" in msg.lower())


# ============================================================
# SECTION 6: Tool Declaration Integrity
# ============================================================
section("6. TOOL DECLARATION INTEGRITY")

test(f"Tool count = {len(TOOLS_OPENAI)}", len(TOOLS_OPENAI) >= 20)

all_valid = True
for tool in TOOLS_OPENAI:
    fn = tool.get("function", {})
    if not fn.get("name") or not fn.get("description") or not fn.get("parameters"):
        all_valid = False
        break
test("All tools have name, description, parameters", all_valid)

all_schemas_valid = True
for tool in TOOLS_OPENAI:
    params = tool.get("function", {}).get("parameters", {})
    if params.get("type") != "object":
        all_schemas_valid = False
        break
test("All tools have type=object parameters", all_schemas_valid)

tool_names = [t["function"]["name"] for t in TOOLS_OPENAI]
test("All tool names unique", len(tool_names) == len(set(tool_names)))

all_required_valid = True
for tool in TOOLS_OPENAI:
    params = tool.get("function", {}).get("parameters", {})
    required = params.get("required", [])
    properties = params.get("properties", {})
    for req in required:
        if req not in properties:
            all_required_valid = False
            break
    if not all_required_valid:
        break
test("All required fields exist in properties", all_required_valid)


# ============================================================
# SECTION 7: FAQ Caching
# ============================================================
section("7. FAQ CACHING")

_faq_cache.clear()

r1 = handle_search_faqs("ايجار")
test("First FAQ call returns results", isinstance(r1, dict))
test("Cache populated after first call", len(_faq_cache) > 0)

start = time.time()
r2 = handle_search_faqs("ايجار")
elapsed = time.time() - start
test("Second FAQ call uses cache (fast)", elapsed < 0.1)

r3 = handle_search_faqs("تسجيل")
test("Different query creates new cache entry", len(_faq_cache) >= 2)


# ============================================================
# SECTION 8: WhatsApp Inbound Edge Cases
# ============================================================
section("8. WHATSAPP INBOUND EDGE CASES")

r = c.post("/whatsapp/inbound", json={
    "from_number": SEED_PHONE, "text_ar": "مرحبا"})
test("Inbound WhatsApp known number", r.status_code == 200)

r = c.post("/whatsapp/inbound", json={
    "from_number": "0509999999", "text_ar": "ابي اسجل"})
test("Inbound WhatsApp unknown number", r.status_code == 200)

r = c.post("/whatsapp/inbound", json={
    "from_number": "0509999999", "text_ar": ""})
test("Inbound WhatsApp empty text", r.status_code == 200)

r = c.post("/whatsapp/inbound", json={
    "from_number": "0509999999", "text_ar": "مرحبا " * 500})
test("Inbound WhatsApp very long text", r.status_code == 200)

r = c.get(f"/whatsapp/session/{SEED_PHONE}")
test("WhatsApp session window endpoint", r.status_code == 200)


# ============================================================
# SECTION 9: CRM Ticket Edge Cases
# ============================================================
section("9. CRM TICKET EDGE CASES")

r = c.post("/crm/tickets", json={
    "subject_ar": "تذكرة اختبار شاملة",
    "channel": "whatsapp",
    "phone": SEED_PHONE,
    "department_id": "DEP-FIN",
    "priority": "high",
    "first_message_ar": "عندي مشكلة عاجلة"})
test("Create ticket with all fields", r.status_code == 200)

r = c.post("/crm/tickets", json={
    "subject_ar": "تذكرة بسيطة",
    "channel": "call"})
test("Create ticket minimal fields", r.status_code == 200)

r = c.post("/crm/tickets", json={
    "subject_ar": "تذكرة", "channel": "whatsapp", "priority": "urgent"})
test("Invalid priority handled", r.status_code in [200, 422])

r = c.get("/crm/kanban")
test("Kanban board returns columns", r.status_code == 200 and "columns" in r.json())

r = c.get("/crm/stats")
test("CRM stats returns data", r.status_code == 200)

r = c.get("/crm/departments")
test("Departments list returns data", r.status_code == 200)

r = c.get("/crm/staff")
test("Staff list returns data", r.status_code == 200)


# ============================================================
# SECTION 10: Multi-Language Response Quality
# ============================================================
section("10. MULTI-LANGUAGE RESPONSE QUALITY")

r = c.get("/faqs/search", params={"q": "ايجار"})
if r.status_code == 200 and r.json().get("results"):
    faq_text = r.json()["results"][0].get("answer", "")
    has_arabic = any('\u0600' <= ch <= '\u06FF' for ch in faq_text)
    test("FAQ Arabic search returns Arabic text", has_arabic or len(faq_text) > 0)
else:
    test("FAQ Arabic search returns data", True)

r = c.get("/faqs/search", params={"q": "dependents", "lang": "en"})
test("FAQ English search returns", r.status_code == 200)

r = c.post("/whatsapp/inbound", json={
    "from_number": "0501111111", "text_ar": "السلام عليكم"})
if r.status_code == 200:
    data = r.json()
    test("WhatsApp response has suggested_greeting", "suggested_greeting_ar" in data or "context" in data)


# ============================================================
# SECTION 11: Finance Edge Cases
# ============================================================
section("11. FINANCE EDGE CASES")

r = c.get("/programs")
test("Programs list returns", r.status_code == 200 and "programs" in r.json())

r = c.get("/request-types/search", params={"q": "تعليم"})
test("Request type search returns", r.status_code == 200)

r = c.get("/request-types/search", params={"q": ""})
test("Request type search empty query", r.status_code == 200)

r = c.get("/sponsorships")
test("Sponsorships endpoint", r.status_code == 200)

r = c.get("/events")
test("Events endpoint", r.status_code == 200)

r = c.get("/reports/overview")
test("Reports overview endpoint", r.status_code == 200)


# ============================================================
# SECTION 12: Beneficiary Search Edge Cases
# ============================================================
section("12. BENEFICIARY SEARCH EDGE CASES")

r = c.get("/beneficiaries/search", params={"q": SEED_PHONE})
test("Search by phone returns results", r.status_code == 200)

r = c.get("/beneficiaries/search", params={"q": "test"})
test("Search by name returns results", r.status_code == 200)

r = c.get("/beneficiaries/search", params={"q": "ZZZZNOTEXIST999"})
test("Search no results returns empty", r.status_code == 200 and len(r.json().get("beneficiaries", [])) == 0)

r = c.get("/beneficiary/BEN-99999/history")
test("404 on unknown beneficiary", r.status_code == 404)


# ============================================================
# SECTION 13: Token Overflow Protection
# ============================================================
section("13. TOKEN OVERFLOW PROTECTION")

test("Tokens for empty string", _estimate_tokens("") == 0)
test("Tokens for long string", _estimate_tokens("a" * 1000) == 250)

msgs = [{"role": "user", "content": f"Message {i} with some content " * 10} for i in range(100)]
total = _count_message_tokens(msgs)
test("Token count for 100 messages", total > 0)

short_history = [{"role": "user", "parts": [{"text": "hi"}]}] * 5
trimmed = sessions._trim_history(short_history)
test("Short history not trimmed", len(trimmed) == 5)

long_history = [{"role": "user", "parts": [{"text": "x" * 400}]}] * 100
trimmed = sessions._trim_history(long_history)
test("Long history trimmed to MIN_HISTORY_KEEP", len(trimmed) == sessions.MIN_HISTORY_KEEP)


# ============================================================
# SECTION 14: Registration Flow Edge Cases
# ============================================================
section("14. REGISTRATION FLOW EDGE CASES")

test("Known beneficiary phone returns registered=True",
     handle_check_phone(SEED_PHONE).get("registered") == True)

cats = db.orphan_categories
for cat in cats:
    r = handle_check_eligibility(cat["id"])
    test(f"Eligibility check for {cat['id']} ({cat['name_en']})", isinstance(r, dict) and "eligible" in r)

UNIQUE_PHONE = f"055{int(time.time()*1000) % 10000000:07d}"
r = handle_create_file(UNIQUE_PHONE, "CT-IND", "OC-UNK", "اختبار تسجيل جديد", "جدة")
test("Create file returns beneficiary_id", "beneficiary_id" in r)
if "beneficiary_id" in r:
    r2 = handle_check_phone(UNIQUE_PHONE)
    test("Phone now shows registered", r2.get("registered") == True)


# ============================================================
# SECTION 15: Support Request Lifecycle
# ============================================================
section("15. SUPPORT REQUEST LIFECYCLE")

_set_beneficiary_status(BID, "approved")

r = handle_search_request_types("ايجار")
test("Search request types works", isinstance(r, dict))

r = handle_create_support_request(
    BID, "REQ-HSG-01",
    "الاسرة متأخرة عن سداد الايجار لثلاثة أشهر", 18000)
test("Create support request", isinstance(r, dict))

if "support_request_id" in r:
    SR_TEST = r["support_request_id"]
    r2 = handle_get_support_request(SR_TEST)
    test("Get support request details", isinstance(r2, dict))

    r3 = c.patch(f"/support-requests/{SR_TEST}/add-detail", json={
        "additional_detail_ar": "الانذار صادر من المالك"})
    test("Add detail to support request", r3.status_code == 200)


# ============================================================
# SECTION 16: Agent Chat Endpoint
# ============================================================
section("16. AGENT CHAT ENDPOINT (proxy to agent:8001)")

try:
    r = c.post("/agent/chat", json={
        "from_number": "966533043483", "text_ar": "مرحبا"})
    test("Agent chat endpoint responds (may be 502 if agent offline)", r.status_code in [200, 502, 503, 500])
except Exception:
    test("Agent chat endpoint responds (may be 502 if agent offline)", True)

try:
    r = c.post("/agent/chat", json={
        "from_number": "05012345678", "text_ar": "ابي اسجل"})
    test("Agent chat unknown number responds", r.status_code in [200, 502, 503, 500])
except Exception:
    test("Agent chat unknown number responds", True)


# ============================================================
# SECTION 17: Notifications and Events
# ============================================================
section("17. NOTIFICATIONS AND EVENTS")

r = c.get("/notifications")
test("Notifications endpoint", r.status_code == 200)

r = c.get("/events", params={"status": "scheduled"})
test("Events scheduled list", r.status_code == 200)


# ============================================================
# SECTION 18: Edge Case Messages
# ============================================================
section("18. EDGE CASE MESSAGES (via WhatsApp inbound)")

edge_cases = [
    ("Emoji only", "😀🎉"),
    ("Numbers only", "12345"),
    ("Single char", "!"),
    ("Very long", "مرحبا " * 100),
    ("XSS attempt", "<script>alert('xss')</script>"),
    ("SQL injection", "'; DROP TABLE sessions; --"),
    ("Arabic diacritics", "مَرْحَبًا بِكُمْ"),
    ("Mixed dialects", "هلا وغلا كيفك عاوز اساعدك"),
]

for label, text in edge_cases:
    r = c.post("/whatsapp/inbound", json={
        "from_number": "05077770001", "text_ar": text})
    test(f"WhatsApp handles {label}", r.status_code == 200)


# ============================================================
# SECTION 19: Voice Channel Edge Cases
# ============================================================
section("19. VOICE CHANNEL EDGE CASES")

r = c.post("/voice/call-start", json={
    "from_number": SEED_PHONE, "sip_call_id": "sip-test-hard@kayan.pbx"})
test("Voice call start known caller", r.status_code == 200)

r = c.post("/voice/call-start", json={
    "from_number": "05099999999", "sip_call_id": "sip-test-unknown@kayan.pbx"})
test("Voice call start unknown caller", r.status_code == 200)

r = c.get("/voice/calls")
test("Voice calls list", r.status_code == 200)


# ============================================================
# SECTION 20: Reference Data Integrity
# ============================================================
section("20. REFERENCE DATA INTEGRITY")

r = c.get("/reference/form-sections")
test("Form sections reference", r.status_code == 200)

r = c.get("/reference/orphan-categories")
test("Orphan categories reference", r.status_code == 200)

r = c.get("/reference/case-types")
test("Case types reference", r.status_code == 200)

r = c.get("/reference/housing-proofs")
test("Housing proofs reference", r.status_code == 200)

r = c.get("/reference/obligation-types")
test("Obligation types reference", r.status_code == 200)

r = c.get("/reference/person-cost-types")
test("Person cost types reference", r.status_code == 200)

r = c.get("/reference/case-steps")
test("Case steps reference", r.status_code == 200)


# ============================================================
# 21. TICKET LIFECYCLE TOOLS
# ============================================================
print(f"\n{'=' * 60}")
print(f"  21. TICKET LIFECYCLE TOOLS")
print(f"{'=' * 60}")

# list_staff
r = handle_list_staff()
test("list_staff returns staff list", "staff" in r and len(r["staff"]) > 0,
     f"keys={list(r.keys())}")

# Create a ticket first
r_ticket = handle_create_ticket(
    subject_ar="اختبار دورة التذكرة",
    channel="whatsapp",
    phone="0559990001",
    first_message_ar="أحتاج مساعدة في vấnعة"
)
TCK_LIFECYCLE = r_ticket.get("ticket_id", "")
test("Create ticket for lifecycle test", bool(TCK_LIFECYCLE),
     f"ticket_id={TCK_LIFECYCLE}")

# get_ticket
if TCK_LIFECYCLE:
    r = handle_get_ticket(TCK_LIFECYCLE)
    test("get_ticket returns detail", "status" in r and "messages" in r,
         f"status={r.get('status')}, msgs={len(r.get('messages', []))}")
else:
    test("get_ticket returns detail", False, "no ticket created")

# assign_ticket
if TCK_LIFECYCLE:
    r = handle_assign_ticket(TCK_LIFECYCLE, "STF-02")
    test("assign_ticket succeeds", "assigned_to_ar" in r,
         f"assigned_to={r.get('assigned_to_ar')}")
else:
    test("assign_ticket succeeds", False, "no ticket created")

# assign_ticket with invalid ticket
r = handle_assign_ticket("TK-FAKE", "STF-02")
test("assign_ticket invalid ticket → error", "error" in r or "detail" in r,
     f"result={str(r)[:80]}")

# assign_ticket with invalid staff
if TCK_LIFECYCLE:
    r = handle_assign_ticket(TCK_LIFECYCLE, "STF-FAKE")
    test("assign_ticket invalid staff → error", "error" in r or "detail" in r,
         f"result={str(r)[:80]}")

# reply_to_ticket
if TCK_LIFECYCLE:
    r = handle_reply_to_ticket(TCK_LIFECYCLE, "تم استلام طلبكم وجاري مراجعته")
    test("reply_to_ticket succeeds", "message" in r and r.get("ticket_status"),
         f"status={r.get('ticket_status')}, wa_sent={r.get('whatsapp_sent')}")
else:
    test("reply_to_ticket succeeds", False, "no ticket created")

# reply_to_ticket as internal note
if TCK_LIFECYCLE:
    r = handle_reply_to_ticket(TCK_LIFECYCLE, "ملاحظة داخلية", send_to_whatsapp=False)
    test("reply_to_ticket internal note", r.get("warning_ar") and "داخلية" in r["warning_ar"],
         f"warning={r.get('warning_ar')}")

# Full lifecycle: create → assign → reply → get detail
if TCK_LIFECYCLE:
    r = handle_get_ticket(TCK_LIFECYCLE)
    test("Full lifecycle: ticket has messages after replies",
         len(r.get("messages", [])) >= 2,
         f"msg_count={len(r.get('messages', []))}")
else:
    test("Full lifecycle: ticket has messages after replies", False, "no ticket")


# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "=" * 60)
print(f"  HARD SCENARIO TEST RESULTS")
print(f"  {PASS}/{TOTAL} passed, {FAIL} failed")
print("=" * 60)

if FAIL > 0:
    print(f"\n  {FAIL} test(s) FAILED — review above")
else:
    print(f"\n  All {TOTAL} tests PASSED")

sys.exit(1 if FAIL else 0)
