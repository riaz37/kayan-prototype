"""Kayan voice engine — FastAPI control server (:8004).

Runs the SIP line(s) and the browser-microphone endpoint in one process.
Kayan is single-tenant, so the line is configured from `.env` and
registered at startup; the line-manager shape is kept from esap-voice
because a second line (a second extension, or an outbound line) costs
nothing but a config block.

    GET  /health          is the engine up, is the line registered
    GET  /lines           every line's status and current call
    GET  /lines/{id}      one line
    POST /lines/{id}/reregister   re-read config and re-register

    POST /voice/session   mint a browser-microphone session
    WS   /voice/ws/{id}   speak to the agent from a browser

Run:
    PYTHONPATH=. .venv/bin/python -m uvicorn voice.main:app --port 8004
"""
import threading
import time

import pyVoIP.VoIP  # noqa: F401 — must import before controller (pyVoIP
#                       has a circular import when SIP loads first)
from pyVoIP.VoIP import PhoneStatus

from . import diag
from . import webvoice
from .brain import CallBrain
from .config import settings
from .controller import Softphone
from .transport.kayan import KayanVoiceTransport

STATUS_NAMES = {
    PhoneStatus.REGISTERED: "registered",
    PhoneStatus.REGISTERING: "registering",
    PhoneStatus.DEREGISTERING: "registering",
    PhoneStatus.FAILED: "failed",
    PhoneStatus.INACTIVE: "stopped",
}


class LineRuntime:
    """One registered SIP line, and the call it is currently carrying."""

    def __init__(self, line_id: str, cfg: dict):
        self.id = line_id
        self.cfg = cfg
        self.last_status = None
        # Per-call state. The transport is destroyed on cleanup before we
        # can read it, so everything needed for the call record is stashed
        # while the call is still live.
        self._bridge = None
        self._brain = None
        self._call_remote = ""
        self._call_direction = ""
        self._call_started = None
        self.phone = Softphone(self._make_transport,
                               auto_answer=cfg.get("auto_answer", True))
        self.phone.label = cfg.get("label", line_id)
        self.phone.register(
            cfg["server"], int(cfg.get("port") or 5060),
            cfg.get("username", ""), cfg.get("password", ""),
            int(cfg.get("local_port") or 15060),
        )

    def _make_transport(self, call, remote: str):
        """Called by the controller when a call is answered."""
        sip_call_id = None
        try:
            sip_call_id = call.request.headers.get("Call-ID")
        except Exception:
            pass
        brain = CallBrain(
            phone=remote,
            direction="inbound" if self.phone.direction == "in" else "outbound",
            sip_call_id=sip_call_id,
        )
        self._brain = brain
        return KayanVoiceTransport(call, brain)

    def stop(self) -> None:
        try:
            self.phone.shutdown()
        except Exception:
            pass

    # ---------- polling ----------

    def tick(self) -> None:
        snap = self.phone.tick()
        status = STATUS_NAMES.get(snap["status"], "stopped")
        if snap.get("error") and status != "registered":
            status = "failed"
        if status != self.last_status:
            self.last_status = status
            diag.log(f"engine: line {self.id} status -> {status}"
                     + (f" ({snap['error']})" if snap.get("error") else ""))

        bridge = self.phone.bridge
        if bridge is not None and self._bridge is None:
            self._bridge = bridge
            self._call_remote = snap.get("remote", "")
            self._call_direction = snap.get("direction") or "in"
            self._call_started = time.time()
        elif bridge is None and self._bridge is not None:
            self._finish_call()

    def _finish_call(self) -> None:
        """The call ended: close the session on the backend.

        This is the write that makes a call show up in the console's call
        log, so it must happen even when the call fell over — a call that
        crashed mid-way is exactly the one worth seeing.
        """
        bridge, self._bridge = self._bridge, None
        brain, self._brain = self._brain, None
        started = self._call_started or time.time()
        duration = int(time.time() - started)
        if brain is None:
            return
        try:
            brain.end(outcome=brain.outcome(), duration_sec=duration,
                      transcript_ar=bridge.transcript() if bridge else None)
        except Exception as e:
            diag.log(f"engine: logging the call failed: {e!r}")
        finally:
            brain.close()
        diag.log(f"engine: line {self.id} call ended "
                 f"({duration}s, {self._call_remote})")

    def snapshot(self) -> dict:
        snap = self.phone.snapshot()
        call = None
        if snap.get("call_state") is not None:
            state = snap["call_state"]
            call = {
                "remote": snap.get("remote", ""),
                "state": str(getattr(state, "value", state)),
                "duration": snap.get("duration", 0),
                "call_id": getattr(self._brain, "call_id", None),
                "identified": getattr(self._brain, "identified", False),
            }
        return {
            "id": self.id,
            "label": self.cfg.get("label", ""),
            "extension": self.cfg.get("username", ""),
            "server": self.cfg.get("server", ""),
            "status": self.last_status or "registering",
            "error": snap.get("error", ""),
            "auto_answer": snap.get("auto_answer", True),
            "call": call,
        }


class LineManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._lines: dict = {}
        self._running = True
        self._thread = threading.Thread(target=self._tick_loop, daemon=True,
                                        name="voice-tick")
        self._thread.start()

    def put(self, line_id: str, cfg: dict) -> dict:
        with self._lock:
            old = self._lines.pop(line_id, None)
        if old is not None:
            old.stop()
            time.sleep(0.5)  # let the old registration wind down
        runtime = LineRuntime(line_id, cfg)
        with self._lock:
            self._lines[line_id] = runtime
        diag.log(f"engine: line {line_id} configured "
                 f"({cfg.get('username')}@{cfg.get('server')}, "
                 f"local port {cfg.get('local_port')})")
        return runtime.snapshot()

    def delete(self, line_id: str) -> bool:
        with self._lock:
            runtime = self._lines.pop(line_id, None)
        if runtime is None:
            return False
        runtime.stop()
        return True

    def get(self, line_id: str):
        with self._lock:
            return self._lines.get(line_id)

    def all(self) -> list:
        with self._lock:
            lines = list(self._lines.values())
        return [line.snapshot() for line in lines]

    def stop(self) -> None:
        self._running = False
        for line_id in list(self._lines):
            self.delete(line_id)

    def _tick_loop(self) -> None:
        while self._running:
            with self._lock:
                lines = list(self._lines.values())
            for line in lines:
                try:
                    line.tick()
                except Exception as e:
                    diag.log(f"engine: tick error on {line.id}: {e!r}")
            time.sleep(0.1)


def configured_line() -> dict:
    """The SIP line from .env, or None when none is configured."""
    if not settings.sip_server or not settings.sip_username:
        return None
    return {
        "label": settings.sip_line_label,
        "server": settings.sip_server,
        "port": settings.sip_port,
        "username": settings.sip_username,
        "password": settings.sip_password,
        "local_port": settings.sip_local_port,
        "auto_answer": settings.sip_auto_answer,
    }


def create_app(manager: LineManager = None):
    from fastapi import FastAPI, HTTPException, WebSocket
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="Kayan Voice Engine", version="1.0.0")
    # Same posture as the backend and the agent: open. There is no auth
    # anywhere in this prototype yet (CLAUDE.md, "Known-unfixed"), and the
    # console has to reach the browser-voice endpoint from :3000.
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])
    mgr = manager or LineManager()
    app.state.manager = mgr
    app.state.voice_sessions = webvoice.SessionStore()

    @app.on_event("startup")
    def _register_configured_line():
        cfg = configured_line()
        if cfg is None:
            diag.log("engine: no SIP_SERVER configured — running without a "
                     "phone line (browser microphone still works)")
            return
        mgr.put("default", cfg)

    @app.on_event("shutdown")
    def _shutdown():
        mgr.stop()

    @app.get("/health", tags=["system"])
    def health():
        lines = mgr.all()
        return {
            "status": "ok",
            "service": "kayan-voice-engine",
            "lines": len(lines),
            "registered": sum(1 for l in lines if l["status"] == "registered"),
        }

    @app.get("/", tags=["system"])
    def root():
        return {
            "service": "Kayan Voice Engine",
            "backend": settings.backend_url,
            "agent": settings.agent_url,
            # language is shown because it is pinned, not detected, and
            # flipping it is a routine part of demoing this.
            "stt": f"{settings.stt_base_url} ({settings.stt_model}, "
                   f"language={settings.stt_language})",
            "tts": f"{settings.tts_base_url} ({settings.tts_model}"
                   f"/{settings.tts_voice})",
            "sip": (f"{settings.sip_username}@{settings.sip_server}"
                    f":{settings.sip_port}" if settings.sip_server
                    else "not configured"),
            "transfer_target": settings.sip_transfer_target,
        }

    @app.get("/lines", tags=["sip"])
    def list_lines():
        return {"lines": mgr.all()}

    @app.get("/lines/{line_id}", tags=["sip"])
    def get_line(line_id: str):
        runtime = mgr.get(line_id)
        if runtime is None:
            raise HTTPException(404, "no such line")
        return runtime.snapshot()

    @app.post("/lines/{line_id}/reregister", tags=["sip"])
    def reregister(line_id: str):
        """Re-read .env and register again — the cheapest way to recover a
        line whose PBX went away without restarting the process."""
        cfg = configured_line()
        if cfg is None:
            raise HTTPException(400, "no SIP line configured")
        return mgr.put(line_id, cfg)

    @app.post("/lines/{line_id}/hangup", tags=["sip"])
    def hangup(line_id: str):
        runtime = mgr.get(line_id)
        if runtime is None:
            raise HTTPException(404, "no such line")
        runtime.phone.hangup()
        return {"ok": True}

    # ---- browser microphone: same agent, no telephony involved ----------

    @app.post("/voice/session", tags=["browser"])
    async def voice_session(payload: dict = None):
        """Mint a single-use session for the console's microphone button."""
        session_id = app.state.voice_sessions.create(payload or {})
        return {"session_id": session_id,
                "ws": f"/voice/ws/{session_id}"}

    @app.websocket("/voice/ws/{session_id}")
    async def voice_ws(websocket: WebSocket, session_id: str):
        # The unguessable session id IS the credential here: browsers
        # cannot set headers on a WebSocket handshake, and the id was
        # handed out over a call to this same service moments earlier.
        session = app.state.voice_sessions.take(session_id)
        if session is None:
            await websocket.close(code=4404)
            return
        await websocket.accept()
        diag.log(f"webvoice: session {session_id[:8]} opened")
        try:
            await webvoice.run_socket(websocket, session)
        except Exception as e:
            diag.log(f"webvoice: session ended: {e!r}")
        finally:
            try:
                await websocket.close()
            except Exception:
                pass
            diag.log(f"webvoice: session {session_id[:8]} closed")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    diag.log(f"engine: starting on :{settings.voice_port} "
             f"(backend {settings.backend_url}, agent {settings.agent_url})")
    uvicorn.run(app, host="0.0.0.0", port=settings.voice_port,
                log_level="info")


if __name__ == "__main__":
    main()
