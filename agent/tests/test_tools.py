"""
Local test script for the Kayan WhatsApp Agent.
Tests tool handlers against the live backend without requiring Gemini API keys.
Run: python3 -m agent.tests.test_tools
"""
import json
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def test_tools():
    """Test all tool handlers against the live backend."""
    from agent.tools import (
        handle_check_phone, handle_send_otp, handle_verify_otp,
        handle_check_eligibility, handle_create_file, handle_get_file,
        handle_update_section, handle_get_completeness, handle_submit_file,
        handle_add_dependent, handle_list_dependents, handle_update_document,
        handle_get_financial_profile, handle_add_obligation, handle_add_person_cost,
        handle_search_request_types, handle_create_support_request,
        handle_get_support_request, handle_add_request_detail,
        handle_search_faqs, handle_create_ticket, handle_get_beneficiary_history,
        handle_list_programs, handle_send_template,
    )

    results = []

    def run(name, fn, *args, **kwargs):
        try:
            r = fn(*args, **kwargs)
            ok = not r.get("error")
            results.append((name, ok, r))
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] {name}")
            if not ok:
                print(f"         Error: {r.get('error')}")
        except Exception as e:
            results.append((name, False, {"error": str(e)}))
            print(f"  [FAIL] {name}: {e}")

    print("\n=== Registration Tools ===")
    run("check_phone (new)", handle_check_phone, "0551234567")
    run("check_phone (known)", handle_check_phone, "0500087602")

    print("\n=== File Tools ===")
    run("get_completeness", handle_get_completeness, "BEN-1001")
    run("get_file", handle_get_file, "BEN-1001")

    print("\n=== Reference Tools ===")
    run("list_programs", handle_list_programs)
    run("search_faqs (تسجيل)", handle_search_faqs, "التسجيل")
    run("search_faqs (ايجار)", handle_search_faqs, "ايجار")

    print("\n=== Support Request Tools ===")
    run("search_request_types (ايجار)", handle_search_request_types, "ايجار")
    run("search_request_types (تعليم)", handle_search_request_types, "تعليم")

    print("\n=== History Tools ===")
    run("get_beneficiary_history", handle_get_beneficiary_history, "BEN-1001")

    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'='*40}")
    print(f"Results: {passed}/{total} passed")
    if passed < total:
        print("Some tests failed — check backend is running on port 8000")
    return passed == total


def test_sessions():
    """Test the session management."""
    from agent.sessions import (
        get_session, set_context, get_context, add_to_history,
        get_history, set_flow, get_flow, set_slot, get_slot,
    )

    print("\n=== Session Tests ===")
    phone = "966500999001"

    sess = get_session(phone)
    assert sess["phone"] == phone, "Session phone mismatch"
    print("  [PASS] create session")

    set_context(phone, {"known": True, "beneficiary_id": "BEN-1001"})
    ctx = get_context(phone)
    assert ctx["known"] == True, "Context not set"
    print("  [PASS] set/get context")

    add_to_history(phone, "user", [{"text": "مرحبا"}])
    add_to_history(phone, "model", [{"text": "اهلا بكم"}])
    h = get_history(phone)
    assert len(h) == 2, f"History length wrong: {len(h)}"
    print("  [PASS] add/get history")

    set_flow(phone, "intake")
    assert get_flow(phone) == "intake", "Flow not set"
    print("  [PASS] set/get flow")

    set_slot(phone, "phone", "0551234567")
    assert get_slot(phone, "phone") == "0551234567", "Slot not set"
    print("  [PASS] set/get slot")

    print("  All session tests passed!")


def test_whatsapp_parsing():
    """Test WhatsApp webhook payload parsing."""
    from agent.whatsapp import extract_message, verify_webhook

    print("\n=== WhatsApp Parsing Tests ===")

    # Verify webhook
    result = verify_webhook("subscribe", "kayan-verify-token", "challenge123")
    assert result == "challenge123", "Webhook verify failed"
    print("  [PASS] webhook verification")

    result = verify_webhook("subscribe", "wrong-token", "challenge123")
    assert result is None, "Webhook should reject wrong token"
    print("  [PASS] webhook rejection")

    # Parse text message
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "96650012345",
                        "id": "wamid.abc",
                        "type": "text",
                        "text": {"body": "مرحبا"},
                        "timestamp": "1234567890"
                    }],
                    "contacts": [{
                        "profile": {"name": "أحمد"},
                        "wa_id": "96650012345"
                    }]
                }
            }]
        }]
    }
    msg = extract_message(payload)
    assert msg is not None, "Failed to parse message"
    assert msg["from"] == "96650012345", "Wrong sender"
    assert msg["text"] == "مرحبا", "Wrong text"
    assert msg["contact_name"] == "أحمد", "Wrong name"
    print("  [PASS] parse text message")

    # Parse status update (no message)
    status_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{"id": "wamid.abc", "status": "sent"}]
                }
            }]
        }]
    }
    msg = extract_message(status_payload)
    assert msg is None, "Should ignore status updates"
    print("  [PASS] ignore status updates")

    print("  All WhatsApp tests passed!")


if __name__ == "__main__":
    print("Kayan WhatsApp Agent — Test Suite\n")

    all_pass = True
    all_pass &= test_tools()
    test_sessions()
    test_whatsapp_parsing()

    if all_pass:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed")
        sys.exit(1)
