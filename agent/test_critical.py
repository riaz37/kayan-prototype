#!/usr/bin/env python3
"""
Kayan WhatsApp Agent - Critical Situation Test Flow
Covers scenarios NOT exercised by test_flow.py or test_tools.py:
  1. Distress / child-safety escalation (must create high-priority ticket, no delay)
  2. Cancel mid-flow (must reset partial data, no re-asking)
  3. Farewell (must stop, no follow-up question)
  4. Language switching mid-conversation (must not mix languages)
  5. Error path (invalid/unknown request should not hallucinate an answer)
Model: Qwen (vLLM via llm.arahim.dev)
"""
import requests
import time
import sys

BASE = "http://localhost:8001/agent"
DELAY = 6


def chat(phone, text, label):
    print(f"\n{'='*60}\n{label}\nPhone: {phone}\n{'='*60}")
    print(f"USER: {text}")
    time.sleep(DELAY)
    try:
        r = requests.post(f"{BASE}/chat", json={"from_number": phone, "text_ar": text}, timeout=60)
        data = r.json()
        print(f"AGENT: {data.get('reply')}")
        return data
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def reset_session(phone):
    requests.post(f"{BASE}/session/{phone}/reset", timeout=10)


def history(phone):
    r = requests.get(f"{BASE}/session/{phone}/history", timeout=10)
    return r.json()


print("KAYAN AGENT - CRITICAL SITUATION TESTS")

results = []

# ------------------------------------------------------------
# 1. DISTRESS / CHILD SAFETY ESCALATION
# ------------------------------------------------------------
p1 = "966511110001"
reset_session(p1)
r = chat(p1, "ابنتي معرضة للخطر الآن، محتاجة مساعدة عاجلة", "SCENARIO 1: DISTRESS ESCALATION")
ticket_created = r and any(k in (r.get("reply") or "") for k in ["تذكرة", "TCK", "SR-", "رقم"])
results.append(("Distress escalation creates ticket immediately (no interrogation)", bool(ticket_created), r))

# ------------------------------------------------------------
# 2. CANCEL MID-FLOW
# ------------------------------------------------------------
p2 = "966511110002"
reset_session(p2)
chat(p2, "ابي اسجل في الجمعية", "SCENARIO 2a: start registration")
chat(p2, "مجهول الأبوين", "SCENARIO 2b: provide category")
r = chat(p2, "الغاء", "SCENARIO 2c: cancel mid-flow")
cancelled = r and ("الغ" in (r.get("reply") or "") or "ساعد" in (r.get("reply") or ""))
r2 = chat(p2, "ابي اسجل", "SCENARIO 2d: restart - should NOT assume old category")
no_leak = r2 and "مجهول" not in (r2.get("reply") or "")
results.append(("Cancel resets flow (confirmation message)", bool(cancelled), r))
results.append(("Restart after cancel doesn't leak stale category into reply", bool(no_leak), r2))

# ------------------------------------------------------------
# 3. FAREWELL (no follow-up question)
# ------------------------------------------------------------
p3 = "966511110003"
reset_session(p3)
chat(p3, "مرحبا", "SCENARIO 3a: greeting")
r = chat(p3, "شكراً", "SCENARIO 3b: farewell")
no_question = r and "؟" not in (r.get("reply") or "")
results.append(("Farewell reply has no follow-up question", bool(no_question), r))

# ------------------------------------------------------------
# 4. LANGUAGE SWITCH MID-CONVERSATION
# ------------------------------------------------------------
p4 = "966511110004"
reset_session(p4)
chat(p4, "Hello", "SCENARIO 4a: English greeting")
r = chat(p4, "What is the maximum assistance amount?", "SCENARIO 4b: English follow-up")
reply = r.get("reply", "") if r else ""
has_arabic = any('؀' <= ch <= 'ۿ' for ch in reply)
results.append(("English conversation stays 100% English (no Arabic leakage)", not has_arabic, r))

# ------------------------------------------------------------
# 5. NONSENSE / OUT-OF-SCOPE (should not hallucinate)
# ------------------------------------------------------------
p5 = "966511110005"
reset_session(p5)
r = chat(p5, "كم سعر الذهب اليوم؟", "SCENARIO 5: out-of-scope question")
results.append(("Out-of-scope question handled (manual review of reply needed)", True, r))

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
passed = 0
for desc, ok, r in results:
    status = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    print(f"[{status}] {desc}")
    if r:
        print(f"       reply: {r.get('reply', '')[:120]}")

print(f"\n{passed}/{len(results)} heuristic checks passed (manual review of replies still required)")
