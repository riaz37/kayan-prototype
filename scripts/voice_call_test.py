#!/usr/bin/env python
"""Place a real phone call to the voice agent and speak Arabic into it.

You cannot test a voice agent by reading its code, and testing it by hand
means holding a softphone and talking to it, which nobody does more than
twice. This drives a whole call through the real stack — FreeSWITCH, SIP,
RTP, G.711, the VAD, nemotron STT, the Kayan agent with its tools, and
OmniVoice TTS — and prints what actually happened.

    ./scripts/voice_call_test.py --phone 96655000000 \\
        "السلام عليكم" "ابي اعرف وش ناقص في ملفي"

What it does:
  1. synthesizes each utterance (the same TTS the agent speaks with)
  2. originates a call from FreeSWITCH to the agent's extension, with the
     caller ID set to --phone, so the agent identifies the beneficiary
     exactly as a real caller would be identified
  3. plays the utterances into the call with gaps for the agent to reply
  4. records the whole call to a WAV so you can listen to it
  5. prints the engine's per-call log and the call_sessions row it wrote

The last step is the point: it asserts against a fresh read of the
database, not against anything the engine told us — same discipline as
scripts/journey_check.py.
"""
import argparse
import json
import os
import subprocess
import sqlite3
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

WORK = Path("/tmp/kayan-voice-test")
DEFAULT_EXTENSION = "1001"


def fs_cli(command: str) -> str:
    out = subprocess.run(["fs_cli", "-x", command], capture_output=True,
                         text=True, timeout=60)
    return (out.stdout or out.stderr or "").strip()


def synthesize_wav(text: str, path: Path) -> float:
    """TTS one utterance to an 8 kHz mono WAV FreeSWITCH can play."""
    import audioop
    from voice import speech
    from voice.config import settings

    cfg = speech.tts_config_for(text, settings.tts_config())
    client = speech.make_client(cfg, timeout=90)
    pcm, rate = speech.synthesize(client, cfg, text)
    if rate != 8000:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 8000, None)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(pcm)
    return len(pcm) / 2 / 8000


def gaps_for(utterances, gap: str):
    """One pause per utterance, from `--gap`.

    A single value is the old behaviour: the same wait after everything.
    A comma-separated list is per utterance, and that is what makes the
    number-dictation bug reproducible from here. A caller reading a long
    number does not pause for the agent between the groups — they pause
    for about a second, which is longer than the VAD's endpointing and
    shorter than `NUMBER_PAUSE`. Reproducing that needs one long gap (the
    agent answers) followed by short ones (the caller keeps reading):

        --gap 16,1.2,1.2
    """
    values = [float(g) for g in str(gap).split(",") if g.strip()]
    if not values:
        values = [16.0]
    # Shorter list: the last value repeats, so `--gap 16` behaves as before.
    return [values[min(i, len(values) - 1)] for i in range(len(utterances))]


def build_playlist(utterances, lead_in: float, gaps, tail: float):
    """A FreeSWITCH file_string: silence, utterance, silence, utterance…"""
    WORK.mkdir(parents=True, exist_ok=True)
    parts = [f"silence_stream://{int(lead_in * 1000)}"]
    for i, text in enumerate(utterances):
        path = WORK / f"utt{i}.wav"
        secs = synthesize_wav(text, path)
        print(f"  [tts] {secs:4.1f}s  (then {gaps[i]:.1f}s pause)  {text}")
        parts.append(str(path))
        parts.append(f"silence_stream://{int(gaps[i] * 1000)}")
    parts[-1] = f"silence_stream://{int(tail * 1000)}"
    return "file_string://" + "!".join(parts)


def latest_call(db: Path, phone: str):
    """The most recent call session for this number, read fresh."""
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM call_sessions WHERE phone LIKE ? "
            "ORDER BY started_at DESC LIMIT 1", (f"%{phone[-9:]}",)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("utterances", nargs="*",
                    default=["السلام عليكم", "ابي اعرف وش ناقص في ملفي"],
                    help="what the caller says, in order")
    ap.add_argument("--phone", default="96655000000",
                    help="caller ID; use a seeded beneficiary to be identified")
    ap.add_argument("--extension", default=DEFAULT_EXTENSION,
                    help="the agent's SIP extension")
    ap.add_argument("--domain", default=None,
                    help="SIP domain (default: ask FreeSWITCH)")
    ap.add_argument("--lead-in", type=float, default=9.0,
                    help="seconds of silence before speaking (the greeting)")
    ap.add_argument("--gap", default="16",
                    help="seconds between utterances (the agent's reply). "
                         "A comma-separated list sets them per utterance: "
                         "'16,1.2,1.2' is a caller reading a number in "
                         "groups without waiting for an answer.")
    ap.add_argument("--tail", type=float, default=16.0,
                    help="seconds of silence at the end")
    ap.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "./data"))
    args = ap.parse_args()

    data_dir = Path(args.data_dir).resolve()
    db = data_dir / "kayan.db"
    calls_dir = data_dir / "calls"
    before = {p.name for p in calls_dir.glob("call-*.log")} if calls_dir.exists() else set()

    print(f"Synthesizing {len(args.utterances)} utterance(s)…")
    gaps = gaps_for(args.utterances, args.gap)
    playlist = build_playlist(args.utterances, args.lead_in, gaps, args.tail)

    WORK.mkdir(parents=True, exist_ok=True)
    recording = WORK / f"call-{time.strftime('%H%M%S')}.wav"
    total = args.lead_in + args.tail + sum(gaps[:-1])
    print(f"\nCalling extension {args.extension} as {args.phone} "
          f"(~{total:.0f}s)…")

    # record_session captures both legs, so the WAV has the caller and the
    # agent on it — the artifact to listen to when something sounds wrong.
    variables = (f"origination_caller_id_number={args.phone},"
                 f"origination_caller_id_name={args.phone},"
                 f"ignore_early_media=true,"
                 f"execute_on_answer='record_session {recording}'")
    # `user%domain` makes sofia look the extension up in the registration
    # table. Without the domain it tries to dial it as a raw host and
    # answers USER_NOT_REGISTERED even when the phone is registered.
    domain = args.domain or fs_cli("eval $${domain}").strip() or "127.0.0.1"
    result = fs_cli(f"originate {{{variables}}}"
                    f"sofia/internal/{args.extension}%{domain} "
                    f"&playback({playlist})")
    if not result.startswith("+OK"):
        print(f"\nThe call did not connect: {result}")
        print("Is FreeSWITCH up (./scripts/freeswitch_dev.sh status) and the "
              "engine registered (curl :8004/lines)?")
        return 1
    print(f"  {result}")

    # `originate` returns as soon as the call is ANSWERED and the playback
    # application starts — not when the call ends. Reading the database
    # here would read a call that is still in progress (no outcome, no
    # transcript). Wait for the channel to go away.
    uuid = result.split()[-1]
    deadline = time.monotonic() + total + 45
    print("  on the call", end="", flush=True)
    while time.monotonic() < deadline:
        if "true" not in fs_cli(f"uuid_exists {uuid}").lower():
            break
        time.sleep(2)
        print(".", end="", flush=True)
    else:
        print(" (timed out — hanging up)", end="")
        fs_cli(f"uuid_kill {uuid}")
    print(" done")
    # Wait for the engine to write the call record. A transferred call
    # outlives the channel we were watching — the engine holds its leg open
    # for up to 20s waiting for the PBX to report the transfer connected —
    # so poll for the row rather than sleeping a fixed amount.
    for _ in range(20):
        row = latest_call(db, args.phone)
        if row and row.get("ended_at"):
            break
        time.sleep(2)

    print("\n" + "=" * 70)
    print("ENGINE CALL LOG")
    print("=" * 70)
    new = sorted(p for p in calls_dir.glob("call-*.log") if p.name not in before)
    if not new:
        print("no new call log — did the engine answer?")
    for path in new:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if any(k in line for k in ("caller said", "agent said", "TOOL",
                                       "brain:", "REPLY LATENCY", "tts ",
                                       "empty transcript", "barge-in",
                                       "transfer", "hangup", "call ended",
                                       "FAILED", "error")):
                print("  " + line)

    print("\n" + "=" * 70)
    print("WHAT THE DATABASE SAYS (fresh read)")
    print("=" * 70)
    row = latest_call(db, args.phone)
    if not row:
        print(f"  no call_sessions row for {args.phone} — the call was never "
              f"logged")
        return 1
    for key in ("id", "phone", "beneficiary_id", "identified", "direction",
                "outcome", "duration_seconds", "started_at", "ended_at"):
        print(f"  {key:18s} {row.get(key)}")
    print("  transcript:")
    for line in (row.get("transcript_ar") or "").splitlines():
        print(f"      {line}")

    ok = bool(row.get("ended_at")) and bool(row.get("transcript_ar"))
    print(f"\n  recording: {recording}")
    print(f"\nRESULT: {'call completed and persisted' if ok else 'INCOMPLETE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
