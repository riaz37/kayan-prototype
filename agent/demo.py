#!/usr/bin/env python3
"""
Kayan WhatsApp Agent - Live Demo
Sends messages one by one with visible output for presentation.
"""

import requests
import json
import time
import sys

WEBHOOK_URL = "http://localhost:8001/webhook"
AGENT_URL = "http://localhost:8001/agent"
DELAY = 8  # seconds between messages

def send_and_show(phone, name, text, step, description):
    """Send message and show response."""
    print(f"\n{'─'*60}")
    print(f"  Step {step}: {description}")
    print(f"{'─'*60}")
    print(f"\n  📱 User: {text}")
    print(f"\n  ⏳ Waiting for AI response...", end="", flush=True)
    
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15551543734",
                        "phone_number_id": "1202441799627748"
                    },
                    "contacts": [{"wa_id": phone, "profile": {"name": name}}],
                    "messages": [{"from": phone, "id": f"wamid.demo{step}", "timestamp": str(int(time.time())), "type": "text", "text": {"body": text}}]
                },
                "field": "messages"
            }]
        }]
    }
    
    start_time = time.time()
    
    try:
        r = requests.post(WEBHOOK_URL, json=payload, timeout=60)
        elapsed = time.time() - start_time
        
        # Get the reply from logs
        import subprocess
        result = subprocess.run(["tail", "-50", "/tmp/agent.log"], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        reply = ""
        for line in reversed(lines):
            if "Reply to" in phone and "Reply" in line:
                reply = line.split("Reply to " + phone + ": ")[-1]
                break
        
        if reply:
            print(f"\r  🤖 Agent: {reply}")
            print(f"\n  ⚡ Response time: {elapsed:.1f}s")
        else:
            print(f"\r  🤖 Agent: (processing...)")
        
        return True
    except Exception as e:
        print(f"\r  ❌ Error: {e}")
        return False

def main():
    # Clear screen
    print("\033[2J\033[H")
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        🤖 Kayan WhatsApp AI Agent - Live Demo                ║
║                                                              ║
║        Model: Qwen 3.6 27B (vLLM)                          ║
║        Language: Arabic (Saudi)                               ║
║        Tools: 25 backend API tools                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    input("  Press Enter to start the demo...")
    
    PHONE = "966533043483"
    NAME = "Rakan"
    
    # Reset session
    print("\n  🔄 Resetting session...")
    requests.post(f"{AGENT_URL}/session/{PHONE}/reset", timeout=10)
    time.sleep(1)
    
    print("\n" + "═"*60)
    print("  Starting demo...")
    print("═"*60)
    
    # Demo messages
    demo = [
        ("مرحبا", 1, "Greeting - Agent identifies beneficiary"),
        ("ابي اعرف حالة ملفي", 2, "File Status - Check completion"),
        ("وش ناقص على الملف", 3, "Missing Documents - Get details"),
        ("ابي مساعدة مالية", 4, "Support Request - Start process"),
        ("رسوم المدرسة لولدي", 5, "Specify Type - Search request types"),
        ("المبلغ 4500 ريال", 6, "Provide Amount - Confirm details"),
        ("نعم، اكد", 7, "Confirm - Create support request"),
        ("وش الطلبات المفتوحة", 8, "Open Requests - List all"),
        ("متى ينزل المبلغ", 9, "Disbursement - Check next payment"),
        ("ابي اكلم موظف", 10, "Ticket - Create support ticket"),
    ]
    
    for text, step, description in demo:
        send_and_show(PHONE, NAME, text, step, description)
        time.sleep(DELAY)
    
    print("\n" + "═"*60)
    print("  ✅ Demo Complete!")
    print("═"*60)
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║  Summary:                                                   ║
║  • 10 real-time AI conversations                            ║
║  • 25 backend tools available                               ║
║  • Arabic natural language processing                       ║
║  • Support requests created                                 ║
║  • Tickets generated                                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

if __name__ == "__main__":
    main()
