"""
WhatsApp Bridge - Connects piwapp to Kayan AI Agent

This module bridges WhatsApp Web (via piwapp) to the existing Gemini agent.
"""

import asyncio
import httpx
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from piwapp.auth.creds import AuthenticationCreds
from piwapp.client import Client
from piwapp.config import ConnectionConfig
from piwapp.events import WAEventType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/whatsapp-bridge.log')
    ]
)
logger = logging.getLogger('whatsapp-bridge')

# Configuration
AGENT_URL = os.getenv('AGENT_URL', 'http://localhost:8000')
CREDS_PATH = Path(__file__).parent / 'session' / 'auth.json'


def load_creds(path: Path) -> AuthenticationCreds:
    """Load or create credentials."""
    if path.exists():
        return AuthenticationCreds.from_json(path.read_text())
    creds = AuthenticationCreds.initial()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json())
    return creds


async def send_to_agent(phone: str, message: str) -> str:
    """Send message to Gemini agent and get response."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            payload = {
                "object": "whatsapp_business_account",
                "entry": [{
                    "changes": [{
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "whatsapp",
                                "phone_number_id": "piwapp"
                            },
                            "contacts": [{
                                "wa_id": phone,
                                "profile": {"name": "WhatsApp User"}
                            }],
                            "messages": [{
                                "from": phone,
                                "id": f"wamid.bridge",
                                "timestamp": "1234567890",
                                "type": "text",
                                "text": {"body": message}
                            }]
                        },
                        "field": "messages"
                    }]
                }]
            }
            
            response = await http.post(
                f"{AGENT_URL}/webhook",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info(f"Message sent to agent for {phone}")
                return "Message processed"
            else:
                logger.error(f"Agent returned {response.status_code}")
                return "Error processing message"
                
    except Exception as e:
        logger.error(f"Error sending to agent: {e}")
        return "Error processing message"


async def main():
    """Main function to start the WhatsApp bridge."""
    logger.info("Starting WhatsApp Bridge...")
    logger.info(f"Agent URL: {AGENT_URL}")
    logger.info(f"Credentials: {CREDS_PATH}")
    
    # Load credentials
    creds = load_creds(CREDS_PATH)
    
    # Track connection state
    connected = asyncio.Event()
    
    def on_creds_update(updated: AuthenticationCreds):
        """Save credentials when updated."""
        CREDS_PATH.write_text(updated.to_json())
        logger.info("Credentials saved")
    
    # Create client
    config = ConnectionConfig()
    client = Client(
        creds=creds,
        config=config,
        on_creds_update=on_creds_update,
        keys_path=CREDS_PATH.with_suffix('.keys')
    )
    
    # Connection status handler
    async def on_connection_update(update: dict):
        if update.get("connection") == "open":
            logger.info("✓ Connected to WhatsApp!")
            connected.set()
        elif "qr" in update:
            logger.info("📱 Scan the QR code with your WhatsApp app")
        elif update.get("connection") == "close":
            logger.warning("Connection closed")
    
    client.on("connection.update", on_connection_update)
    
    # Message handler
    def on_messages(payload):
        for msg in payload.messages:
            # Extract phone number
            remote_jid = msg["key"]["remoteJid"]
            phone = remote_jid.user if hasattr(remote_jid, 'user') else str(remote_jid)
            
            # Skip group messages
            if '@g.us' in str(remote_jid):
                continue
            
            # Get message text
            text = None
            if hasattr(msg.get('message', {}), 'get'):
                message_content = msg.get('message', {})
                if 'conversation' in message_content:
                    text = message_content['conversation']
                elif 'extendedTextMessage' in message_content:
                    text = message_content['extendedTextMessage'].get('text')
            
            if text:
                logger.info(f"📱 Message from {phone}: {text[:50]}...")
                asyncio.create_task(send_to_agent(phone, text))
    
    client.events.on(WAEventType.MESSAGES_UPSERT, on_messages)
    
    # Start client
    logger.info("Connecting to WhatsApp Web...")
    try:
        await client.start()
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return
    
    # Wait for connection
    await connected.wait()
    logger.info("WhatsApp Bridge is ready!")
    logger.info("Waiting for messages...")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await client.stop()


if __name__ == '__main__':
    asyncio.run(main())
