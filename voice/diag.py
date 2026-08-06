"""Diagnostic logging for call/media debugging.

Two sinks:

- ``voice.log`` — append-only, everything from every session.
- ``calls/call-<timestamp>-<remote>.log`` — one file per call, opened when
  the call is answered and closed when it ends.  While a call log is open,
  every ``log()`` line is written to both sinks, so each call file is a
  complete self-contained record: caller, negotiated SDP/codec, transport
  events, per-turn stage timings, 5 s buffer stats, errors, and duration.

Ported from esap-voice `app/diag.py`.  Both sinks moved under ``$DATA_DIR``
(default ``./data``), which is already gitignored and regenerable — call
logs carry beneficiary phone numbers and full Arabic transcripts, so they
must not land in the working tree where they could be committed.
"""
import os
import re
import threading
import time
from pathlib import Path

_DATA_DIR = Path(os.environ.get("DATA_DIR", "./data")).resolve()
LOG_PATH = _DATA_DIR / "voice.log"
CALL_LOG_DIR = _DATA_DIR / "calls"

try:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

_lock = threading.Lock()
_call_file = None          # open file handle while a call is active
_call_path = None
_call_started = None


def _stamp() -> str:
    now = time.time()
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)) + (
        ".%03d" % int(now % 1 * 1000)
    )


def log(msg: str) -> None:
    line = f"[{_stamp()}] {msg}\n"
    try:
        with _lock:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line)
            if _call_file is not None:
                _call_file.write(line)
                _call_file.flush()
    except OSError:
        pass


def start_call_log(label: str, header_lines=()) -> None:
    """Open a per-call log file; subsequent log() lines also land there."""
    global _call_file, _call_path, _call_started
    safe = re.sub(r"[^\w.+-]+", "_", label).strip("_") or "call"
    name = f"call-{time.strftime('%Y%m%d-%H%M%S')}-{safe[:40]}.log"
    try:
        with _lock:
            if _call_file is not None:      # shouldn't happen; be safe
                _call_file.close()
            CALL_LOG_DIR.mkdir(parents=True, exist_ok=True)
            _call_path = CALL_LOG_DIR / name
            _call_file = open(_call_path, "a", encoding="utf-8")
            _call_started = time.monotonic()
    except OSError:
        _call_file = None
        _call_path = None
        return
    log(f"=== call log opened: {label} ===")
    for line in header_lines:
        log(f"    {line}")


def end_call_log(reason: str = "") -> None:
    """Close the per-call log (no-op when none is open)."""
    global _call_file, _call_path, _call_started
    with _lock:
        open_now = _call_file is not None
    if not open_now:
        return
    dur = time.monotonic() - _call_started if _call_started else 0
    log(f"=== call ended after {int(dur // 60):02d}:{int(dur % 60):02d}"
        f"{' — ' + reason if reason else ''} ===")
    try:
        with _lock:
            if _call_file is not None:
                _call_file.close()
    except OSError:
        pass
    finally:
        _call_file = None
        _call_path = None
        _call_started = None


def current_call_log():
    """Path of the active per-call log, or None."""
    with _lock:
        return _call_path
