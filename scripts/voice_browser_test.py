#!/usr/bin/env python
"""Drive the browser-microphone path without a browser.

The console's Voice Test page opens a WebSocket to the engine and streams
microphone PCM into it. This does exactly the same thing with synthesized
speech instead of a microphone, so the path can be tested from a terminal
and in CI — the browser half is then only the audio plumbing.

    PYTHONPATH=. .venv/bin/python scripts/voice_browser_test.py \\
        --phone 96655000000 "السلام عليكم" "وش ناقص في ملفي"
"""
import argparse
import asyncio
import audioop
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MIC_RATE = 16000
CHUNK_MS = 20


def synth_16k(text: str) -> bytes:
    """One utterance as 16 kHz mono PCM16 — what a microphone would send."""
    from voice import speech
    from voice.config import settings

    cfg = speech.tts_config_for(text, settings.tts_config())
    client = speech.make_client(cfg, timeout=90)
    pcm, rate = speech.synthesize(client, cfg, text)
    if rate != MIC_RATE:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, MIC_RATE, None)
    return pcm


async def run(base: str, phone: str, utterances, reply_wait: float) -> int:
    import httpx
    import websockets

    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post(f"{base}/voice/session", json={"phone": phone})
        r.raise_for_status()
        session_id = r.json()["session_id"]

    url = base.replace("http", "ws", 1) + f"/voice/ws/{session_id}"
    transcript = []
    tools = []

    async with websockets.connect(url, max_size=None) as ws:
        async def pump():
            """Print everything the engine sends, as it sends it."""
            async for message in ws:
                if isinstance(message, bytes):
                    continue          # reply audio; the browser would play it
                event = json.loads(message)
                kind = event.get("type")
                if kind == "text":
                    who = "caller" if event["role"] == "user" else "agent"
                    transcript.append(f"{who}: {event['text']}")
                    print(f"  {who}: {event['text']}")
                elif kind == "tool":
                    tools.append(event.get("name"))
                    print(f"  [tool] {event.get('name')}")
                elif kind == "state":
                    print(f"  ({event.get('value')})")
                elif kind == "error":
                    print(f"  [error] {event.get('text')}")

        reader = asyncio.create_task(pump())
        # Let the greeting arrive and play out before talking over it.
        await asyncio.sleep(8)

        for text in utterances:
            print(f"\n[speaking] {text}")
            pcm = await asyncio.to_thread(synth_16k, text)
            step = MIC_RATE // 1000 * CHUNK_MS * 2
            for i in range(0, len(pcm), step):
                await ws.send(pcm[i:i + step])
                await asyncio.sleep(CHUNK_MS / 1000)   # real time, as a mic does
            # Silence, so the VAD closes the utterance the normal way.
            silence = b"\x00" * step
            for _ in range(40):
                await ws.send(silence)
                await asyncio.sleep(CHUNK_MS / 1000)
            await asyncio.sleep(reply_wait)

        await ws.send(json.dumps({"type": "stop"}))
        await asyncio.sleep(1)
        reader.cancel()

    print("\n" + "=" * 60)
    print(f"turns: {len(transcript)}   tools: {tools or 'none'}")
    heard_caller = any(t.startswith("caller:") for t in transcript)
    answered = sum(1 for t in transcript if t.startswith("agent:")) >= 2
    ok = heard_caller and answered
    print("RESULT:", "browser voice works" if ok
          else "INCOMPLETE — the agent did not hear or did not answer")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("utterances", nargs="*", default=["السلام عليكم"])
    ap.add_argument("--phone", default="96655000000")
    ap.add_argument("--base", default="http://127.0.0.1:8004")
    ap.add_argument("--reply-wait", type=float, default=14.0)
    args = ap.parse_args()
    return asyncio.run(run(args.base, args.phone, args.utterances,
                           args.reply_wait))


if __name__ == "__main__":
    raise SystemExit(main())
