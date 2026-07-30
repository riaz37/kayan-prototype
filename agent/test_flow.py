#!/usr/bin/env python3
"""
Kayan WhatsApp Agent - Full Testing Flow
Tests all 6 agent roles with proper RPM delays (6s between requests)
Model: Qwen 3.6 27B (vLLM)
"""

import requests
import json
import time
import sys

BASE = "http://localhost:8001/agent"
DELAY = 6  # seconds between requests (under 15 RPM)

def chat(phone, text, step, delay=DELAY):
    """Send a message and print the response."""
    print(f"\n{'='*60}")
    print(f"STEP {step} | Phone: {phone}")
    print(f"{'='*60}")
    print(f"📤 USER: {text}")
    
    time.sleep(delay)
    
    try:
        r = requests.post(
            f"{BASE}/chat",
            json={"from_number": phone, "text_ar": text},
            timeout=60
        )
        data = r.json()
        print(f"📥 AGENT: {data['reply']}")
        
        if data.get("context"):
            ctx = data["context"]
            print(f"\n[CONTEXT: {ctx.get('name_ar')} | File: {ctx.get('file_no')} | Status: {ctx.get('file_status')}]")
        
        return data
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None

def reset_session(phone):
    """Reset session for a phone number."""
    print(f"\n🔄 Resetting session for {phone}...")
    requests.post(f"{BASE}/session/{phone}/reset", timeout=10)
    print("✅ Session reset")

def check_requests(phone):
    """Check open support requests."""
    print(f"\n📋 Checking open requests for {phone}...")
    r = requests.get(f"{BASE}/session/{phone}/history", timeout=10)
    data = r.json()
    if data.get("history"):
        for h in data["history"][-3:]:
            print(f"  - {h.get('name_ar', 'N/A')}: {h.get('reply', '')[:80]}...")
    return data

# ============================================================
# TEST SCENARIOS
# ============================================================

print("=" * 60)
print("🧪 KAYAN WHATSAPP AGENT - FULL TEST FLOW")
print("=" * 60)
print(f"Model: Qwen 3.6 27B (vLLM)")
print(f"RPM Limit: 15 requests/minute")
print(f"Delay between requests: {DELAY}s")
print("=" * 60)

# Phone numbers to test
KNOWN_PHONE = "966533043483"  # راكان الدوسري (existing beneficiary)
NEW_PHONE = "966500287602"    # New user

# ============================================================
# SCENARIO 1: GREETING & CONTEXT RETRIEVAL
# ============================================================
print("\n" + "🔹" * 30)
print("SCENARIO 1: GREETING & CONTEXT RETRIEVAL")
print("🔹" * 30)

reset_session(KNOWN_PHONE)
chat(KNOWN_PHONE, "مرحبا", 1)

# ============================================================
# SCENARIO 2: FILE STATUS INQUIRY
# ============================================================
print("\n" + "🔹" * 30)
print("SCENARIO 2: FILE STATUS INQUIRY")
print("🔹" * 30)

chat(KNOWN_PHONE, "ابي اعرف حالة ملفي", 2)
chat(KNOWN_PHONE, "وش ناقص على الملف", 3)

# ============================================================
# SCENARIO 3: SUPPORT REQUEST CREATION
# ============================================================
print("\n" + "🔹" * 30)
print("SCENARIO 3: SUPPORT REQUEST CREATION")
print("🔹" * 30)

chat(KNOWN_PHONE, "ابي مساعدة مالية", 4)
chat(KNOWN_PHONE, "رسوم المدرسة لولدي", 5)
chat(KNOWN_PHONE, "المبلغ 4500 ريال", 6)
chat(KNOWN_PHONE, "نعم، اكد", 7)

# ============================================================
# SCENARIO 4: CHECK OPEN REQUESTS
# ============================================================
print("\n" + "🔹" * 30)
print("SCENARIO 4: CHECK OPEN REQUESTS")
print("🔹" * 30)

chat(KNOWN_PHONE, "وش الطلبات المفتوحة", 8)
chat(KNOWN_PHONE, "متى ينزل المبلغ", 9)

# ============================================================
# SCENARIO 5: FAQ LOOKUP
# ============================================================
print("\n" + "🔹" * 30)
print("SCENARIO 5: FAQ LOOKUP")
print("🔹" * 30)

chat(KNOWN_PHONE, "كم الحد الأقصى للمساعدة", 10)
chat(KNOWN_PHONE, "وش شروط التسجيل", 11)

# ============================================================
# SCENARIO 6: CREATE SUPPORT TICKET
# ============================================================
print("\n" + "🔹" * 30)
print("SCENARIO 6: CREATE SUPPORT TICKET")
print("🔹" * 30)

chat(KNOWN_PHONE, "ابي اكلم موظف", 12)
chat(KNOWN_PHONE, "عندي مشكلة في الملف", 13)

# ============================================================
# SCENARIO 7: NEW USER (UNKNOWN)
# ============================================================
print("\n" + "🔹" * 30)
print("SCENARIO 7: NEW USER (UNKNOWN)")
print("🔹" * 30)

reset_session(NEW_PHONE)
chat(NEW_PHONE, "السلام عليكم", 14)
chat(NEW_PHONE, "ابي اسجل في الجمعية", 15)
chat(NEW_PHONE, "مجهول الأبوين", 16)

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("✅ TEST FLOW COMPLETED")
print("=" * 60)
print(f"Total requests: ~16")
print(f"Estimated time: ~{16 * DELAY // 60} minutes")
print(f"RPM used: ~{60 // DELAY} requests/minute")
print("=" * 60)

# Check final state
print("\n📊 Final State:")
check_requests(KNOWN_PHONE)
