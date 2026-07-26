"""
Simple WhatsApp Bridge - Quick setup for demo
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory
sys.path.insert(0, str(Path(__file__).parent))

from piwapp.client import Client
from piwapp.events import Events

SESSION_DIR = Path(__file__).parent / 'session'


async def on_message(message, client):
    """Handle incoming messages."""
    try:
        phone = message.key.remoteJid.user
        if '@g.us' in str(message.key.remoteJid):
            return
            
        if hasattr(message.message, 'conversation'):
            text = message.message.conversation
        elif hasattr(message.message, 'extendedTextMessage'):
            text = message.message.extendedTextMessage.text
        else:
            return
            
        print(f"\n📱 Message from {phone}: {text}")
        
        # Forward to agent
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as http:
            payload = {
                "object": "whatsapp_business_account",
                "entry": [{"changes": [{"value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "whatsapp", "phone_number_id": "piwapp"},
                    "contacts": [{"wa_id": phone, "profile": {"name": "User"}}],
                    "messages": [{"from": phone, "id": "wamid.123", "timestamp": "1234567890", "type": "text", "text": {"body": text}}]
                }, "field": "messages"}]}]
            }
            resp = await http.post("http://localhost:8000/webhook", json=payload)
            print(f"   ✅ Agent notified (status: {resp.status_code})")
            
    except Exception as e:
        print(f"Error: {e}")


async def main():
    print("🚀 WhatsApp Bridge Starting...")
    print("📱 Scan the QR code with your WhatsApp app\n")
    
    SESSION_DIR.mkdir(exist_ok=True)
    
    client = Client(auth_dir=str(SESSION_DIR))
    client.on(Events.MESSAGE_UPSERT, on_message)
    
    await client.start()
    
    print("\n✅ Connected! Waiting for messages...")
    print("   Send a message to yourself from another device to test\n")
    
    while True:
        await asyncio.sleep(1)


if __name__ == '__main__':
    asyncio.run(main())
