"""Softphone state machine on top of pyVoIP: one SIP line.

Ported from esap-voice `app/controller.py`, trimmed for this project:

* The transport is supplied by the caller (``make_transport``) instead of
  being chosen from a config dict — there is exactly one here, and the
  controller has no business knowing what a Kayan agent is.
* The desktop pieces are gone: sound-card ringer/ringback, mute, DTMF,
  and the device/loopback/Gemini transports.
* Agent persona / flow-graph config is gone; the brain lives behind the
  transport.

What is kept verbatim is everything that was learned from live calls
against a real PBX — the CANCEL handling pyVoIP lacks, the hand-built
BYE/REFER, the transfer fallback that bridges the legs itself when the PBX
refuses REFER, and the RTP timing patch.  ``tick()`` is polled by the
line manager; pyVoIP callbacks run on their own threads and only touch
state under the lock.
"""
import re
import socket
import sys
import threading
import time

from pyVoIP import SIP
from pyVoIP.SIP import SIPMessageType
from pyVoIP.VoIP import (
    CallState,
    InvalidStateError,
    PhoneStatus,
    VoIPPhone,
)

from . import diag
from . import sip_dialog
from .call_bridge import CallBridge
from .transport.rtp_patch import apply_rtp_timing_patch

apply_rtp_timing_patch()

# Default GIL switch interval is 5 ms; a busy thread (HTTP, numpy) can hold
# the RTP transmit thread off that long per switch, adding packet jitter.
# 2 ms keeps worst-case holds well inside a 20 ms frame.
sys.setswitchinterval(0.002)


class PatchedVoIPPhone(VoIPPhone):
    """VoIPPhone that also handles inbound CANCEL.

    Stock pyVoIP 1.6.8 ignores CANCEL, which leaves an incoming call stuck
    in RINGING forever when the remote side gives up before we answer.
    """

    def callback(self, request) -> None:
        if (
            request.type == SIPMessageType.MESSAGE
            and request.method == "INVITE"
        ):
            call = self.calls.get(request.headers.get("Call-ID"))
            if call is not None and call.state == CallState.RINGING:
                # Stock pyVoIP silently ignores a re-INVITE that arrives
                # before we answer; log it, it breaks media setup.
                diag.log("re-INVITE while RINGING — ignored by pyVoIP")
        if (
            request.type == SIPMessageType.MESSAGE
            and request.method == "CANCEL"
        ):
            call_id = request.headers.get("Call-ID")
            call = self.calls.get(call_id)
            if call is not None and call.state == CallState.RINGING:
                for client in call.RTPClients:
                    try:
                        client.stop()
                    except Exception:
                        pass
                call.state = CallState.ENDED
                self.calls.pop(call_id, None)
            return
        super().callback(request)


def caller_number(call) -> str:
    """The caller's number alone, for looking the beneficiary up.

    esap-voice returned ``"Name" <number>`` for display.  Here the value is
    fed to ``db.norm_phone`` and matched against a beneficiary file, so the
    display name has to be stripped or every call looks like a new caller.
    """
    try:
        frm = call.request.headers["From"]
        return (frm.get("number") or frm.get("caller")
                or frm.get("raw", "") or "unknown")
    except Exception:
        return "unknown"


def _caller_id(call) -> str:
    """Human-readable caller identity for the logs."""
    try:
        frm = call.request.headers["From"]
        name = frm.get("caller") or ""
        number = frm.get("number") or ""
        if name and number and name != number:
            return f"{name} <{number}>"
        return number or name or frm.get("raw", "unknown")
    except Exception:
        return "unknown"


def _local_ip(server: str, port: int) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((server, port))
        return s.getsockname()[0]
    finally:
        s.close()


class Softphone:
    """One SIP registration and the single call it may carry.

    ``make_transport(call, remote)`` is called when a call is answered and
    must return a started-on-``start()`` transport (see transport/base.py).
    """

    def __init__(self, make_transport, auto_answer: bool = True):
        self._lock = threading.RLock()
        self._make_transport = make_transport
        self._auto_answer_enabled = auto_answer
        self.phone = None
        self.call = None
        self.direction = None       # "in" | "out"
        self.remote = ""
        self.answered_at = None
        self.bridge = None
        self.last_error = ""
        self._registering = False
        self._ring_started = None
        self.relay = None        # CallBridge while a transferred call runs
        self.relay_call = None   # the target leg of that bridge
        self.label = ""

    # ---------- registration ----------

    def register(self, server: str, port: int, username: str, password: str,
                 local_sip_port: int) -> None:
        with self._lock:
            if self.phone is not None or self._registering:
                return
            self._registering = True
            self.last_error = ""
        threading.Thread(
            target=self._do_register,
            args=(server, port, username, password, local_sip_port),
            daemon=True, name="sip-register",
        ).start()

    def _do_register(self, server, port, username, password, local_sip_port):
        phone = None
        try:
            my_ip = _local_ip(server, port)
            phone = PatchedVoIPPhone(
                server, port, username, password,
                myIP=my_ip,
                sipPort=local_sip_port,
                callCallback=self._on_incoming,
            )
            phone.start()
            self._install_sip_debug(phone)
            with self._lock:
                self.phone = phone
            diag.log(f"sip: registered {username}@{server}:{port} "
                     f"(local {my_ip}:{local_sip_port})")
        except SIP.InvalidAccountInfoError:
            self._register_failed(
                phone, "Registration rejected: check username/password.")
        except OSError as e:
            self._register_failed(phone, f"Network error: {e}")
        except Exception as e:
            self._register_failed(phone, f"Registration failed: {e}")
        finally:
            with self._lock:
                self._registering = False

    def _install_sip_debug(self, phone) -> None:
        """Wrap the SIP client's message dispatch to (a) log every inbound
        in-dialog message to the call log, (b) track the PBX's response to
        our REFER, and (c) answer NOTIFY requests with 200 OK — pyVoIP
        ignores NOTIFY, and an unanswered transfer-progress NOTIFY makes
        some PBXs roll the transfer back."""
        sip = phone.sip
        orig = sip.parse_message

        def parse_logged(message):
            try:
                if self._sip_debug_hook(sip, message):
                    return  # handled (NOTIFY) — don't hand to pyVoIP
            except Exception as e:
                diag.log(f"sip debug hook failed: {e!r}")
            return orig(message)

        sip.parse_message = parse_logged

    def _sip_debug_hook(self, sip, message) -> bool:
        cseq = ""
        try:
            raw_cseq = message.headers.get("CSeq")
            if isinstance(raw_cseq, dict):
                cseq = raw_cseq.get("method", "")
        except Exception:
            pass
        if cseq in ("REGISTER", "OPTIONS"):
            return False
        if message.type == SIPMessageType.RESPONSE:
            try:
                code = int(message.status.value[0]) if isinstance(
                    message.status.value, tuple) else int(message.status.value)
            except Exception:
                code = 0
            diag.log(f"sip <- response {code} (cseq {cseq or '?'})")
            sip_dialog.note_response(message)
            if cseq in ("BYE", "REFER"):
                # Ours: pyVoIP would try to route it as an inbound call
                # event (its parse_message hands 200 OK to callCallback).
                return True
            return False
        method = getattr(message, "method", "?")
        if method == "NOTIFY":
            # Transfer progress: the body is a sipfrag status line like
            # "SIP/2.0 180 Ringing" / "SIP/2.0 200 OK".
            frag = ""
            try:
                raw = getattr(message, "raw", b"")
                if isinstance(raw, bytes):
                    tail = raw.decode("utf8", "replace").strip().splitlines()
                    frag = tail[-1].strip() if tail else ""
            except Exception:
                pass
            diag.log(f"sip <- NOTIFY (cseq {cseq or '?'}) body={frag!r}")
            m = re.search(r"SIP/2\.0\s+(\d{3})", frag)
            if m:
                sip_dialog.note_notify(
                    message.headers.get("Call-ID", ""), int(m.group(1)))
            try:
                ok = sip.gen_ok(message)
                sip.out.sendto(ok.encode("utf8"), (sip.server, sip.port))
            except Exception as e:
                diag.log(f"sip: NOTIFY 200 OK failed: {e!r}")
            return True
        diag.log(f"sip <- {method} (cseq {cseq or '?'})")
        return False

    def _register_failed(self, phone, message: str) -> None:
        with self._lock:
            self.last_error = message
        diag.log(f"sip: {message}")
        if phone is not None:
            try:
                phone.stop()
            except Exception:
                pass

    def unregister(self) -> None:
        with self._lock:
            phone, self.phone = self.phone, None
        self._end_call_cleanup()
        if phone is not None:
            threading.Thread(
                target=self._safe_stop, args=(phone,),
                daemon=True, name="sip-unregister",
            ).start()

    @staticmethod
    def _safe_stop(phone) -> None:
        try:
            phone.stop()
        except Exception:
            pass

    def status(self) -> PhoneStatus:
        with self._lock:
            if self._registering:
                return PhoneStatus.REGISTERING
            if self.phone is None:
                return PhoneStatus.INACTIVE
            try:
                return self.phone.get_status()
            except Exception:
                return PhoneStatus.INACTIVE

    # ---------- calls ----------

    def _on_incoming(self, call) -> None:
        """Runs on a pyVoIP thread.  Must stay alive for the whole call:
        pyVoIP garbage-collects calls whose callback thread has exited."""
        with self._lock:
            if self.call is not None:
                try:
                    call.deny()
                except Exception:
                    pass
                return
            self.call = call
            self.direction = "in"
            self.remote = caller_number(call)
            self._ring_started = time.time()
        diag.log(f"incoming call from {_caller_id(call)}")
        while call.state in (CallState.RINGING, CallState.ANSWERED):
            time.sleep(0.3)

    def dial(self, number: str) -> None:
        with self._lock:
            if self.phone is None or self.call is not None:
                return
            try:
                self.call = self.phone.call(number)
            except Exception as e:
                self.last_error = f"Call failed: {e}"
                return
            self.direction = "out"
            self.remote = number
        diag.log(f"outgoing call to {number}")

    def answer(self) -> None:
        with self._lock:
            call = self.call
        if call is None:
            return
        try:
            call.answer()
        except InvalidStateError:
            pass
        except Exception as e:
            with self._lock:
                self.last_error = f"Answer failed: {e}"

    def hangup(self) -> None:
        with self._lock:
            call = self.call
            phone = self.phone
        if call is None:
            return
        try:
            if call.state == CallState.ANSWERED:
                # pyVoIP's own BYE is malformed against strict PBXs (see
                # voice/sip_dialog.py) — build and send it ourselves, then do
                # the local teardown pyVoIP's hangup() would have done.
                for client in call.RTPClients:
                    try:
                        client.stop()
                    except Exception:
                        pass
                call.state = CallState.ENDED
                call_id = call.request.headers.get("Call-ID")
                if phone is not None:
                    phone.calls.pop(call_id, None)
                try:
                    sip_dialog.send_request(call.sip, call.request, "BYE")
                except Exception as e:
                    diag.log(f"sip: BYE failed ({e!r})")
                sip_dialog.forget(call_id)
                self._end_call_cleanup()
                return
            call.hangup()
        except InvalidStateError:
            # Outgoing call not answered yet: pyVoIP cannot send CANCEL,
            # so tear the call down locally.
            for client in call.RTPClients:
                try:
                    client.stop()
                except Exception:
                    pass
            call.state = CallState.ENDED
            if phone is not None:
                phone.calls.pop(call.request.headers.get("Call-ID"), None)
        except Exception:
            pass
        self._end_call_cleanup()

    @staticmethod
    def _log_call_media(call) -> None:
        try:
            body = call.request.body
            m_lines = [
                {"type": m.get("type"), "port": m.get("port"),
                 "methods": list(m.get("methods", []))}
                for m in body.get("m", [])
            ]
            c_lines = [c.get("address") for c in body.get("c", [])]
            clients = [
                {"codec": str(getattr(c, "preference", "?")),
                 "in": c.inPort, "out": f"{c.outIP}:{c.outPort}"}
                for c in call.RTPClients
            ]
            diag.log(f"call answered: sdp m={m_lines} c={c_lines}")
            diag.log(f"call answered: rtp clients={clients}")
        except Exception as e:
            diag.log(f"call answered: media introspection failed: {e}")

    def _end_call_cleanup(self) -> None:
        with self._lock:
            relay, self.relay = self.relay, None
            other, self.relay_call = self.relay_call, None
        if relay is not None:
            relay.stop()
        if other is not None:
            self._hangup_other(other)
        with self._lock:
            if self.bridge is not None:
                self.bridge.stop()
                self.bridge = None
            self.call = None
            self.direction = None
            self.remote = ""
            self.answered_at = None
            self._ring_started = None
            reason = self.last_error
        diag.end_call_log(reason)

    # ---------- polling ----------

    def tick(self) -> dict:
        """Advance the state machine; called from the line manager's loop."""
        with self._lock:
            call = self.call
            ring_started = self._ring_started
        if call is not None:
            state = call.state
            if (
                state == CallState.RINGING
                and self.direction == "in"
                and self._auto_answer_enabled
                and ring_started is not None
                # Short but non-zero: instant answers race some PBXs' media
                # setup, and callers expect to hear at least a partial ring.
                and time.time() - ring_started > 0.4
            ):
                self.answer()
            elif state == CallState.ANSWERED and self.bridge is None:
                diag.start_call_log(
                    f"{self.direction}-{self.remote}",
                    [f"line: {self.label}", f"remote: {self.remote}"],
                )
                try:
                    self._log_call_media(call)
                    bridge = self._make_transport(call, self.remote)
                    bridge.start()
                    with self._lock:
                        self.bridge = bridge
                        self.answered_at = time.time()
                except Exception as e:
                    with self._lock:
                        self.last_error = f"Transport error: {e}"
                    diag.log(f"transport start FAILED: {e!r}")
                    self.hangup()
            elif state == CallState.ENDED:
                self._end_call_cleanup()
        with self._lock:
            relay = self.relay
        if relay is not None:
            # A bridged (transferred) call: the AI is out of the loop, we
            # just watch for either side hanging up.
            if not relay.alive():
                diag.log("bridge: a leg ended — tearing down both")
                relay.stop()
                with self._lock:
                    other, self.relay, self.relay_call = (
                        self.relay_call, None, None)
                if other is not None:
                    self._hangup_other(other)
                self.hangup()
            return self.snapshot()
        with self._lock:
            bridge = self.bridge
        if bridge is not None and bridge.error:
            with self._lock:
                self.last_error = bridge.error
            diag.log(f"transport error mid-call: {bridge.error}")
            self.hangup()
        elif (bridge is not None
                and getattr(bridge, "wants_hangup", False)
                and not bridge._bot_speaking()
                and time.monotonic() >= getattr(
                    bridge, "_hangup_hold_until", 0.0)):
            # A tool (end_call / transfer) asked to end the call, the bot's
            # final words have finished playing out, and no barge-in hold
            # is pending.
            self._finish_tool_hangup(bridge, call)
        return self.snapshot()

    def _finish_tool_hangup(self, bridge, call) -> None:
        target = getattr(bridge, "transfer_target", None)
        if not target:
            diag.log("call ended by end_call tool")
            self.hangup()
            return
        if getattr(bridge, "_transfer_started", False):
            return  # the worker thread owns it now
        bridge._transfer_started = True
        bridge._transfer_cancelled = False
        threading.Thread(
            target=self._do_transfer, args=(bridge, call, target),
            daemon=True, name="sip-transfer",
        ).start()

    def _do_transfer(self, bridge, call, target: str) -> None:
        """Blind transfer (RFC 3515): REFER the caller to the target, watch
        the progress NOTIFYs, and only drop our leg once the PBX has taken
        the call.  Runs off the tick thread — REFER + NOTIFY can take
        seconds and other lines must keep ticking."""
        sip = call.sip
        call_id = call.request.headers.get("Call-ID", "")
        refer_to = f"<sip:{target}@{sip.server}>"
        try:
            code = sip_dialog.send_request(
                sip, call.request, "REFER",
                extra_headers=(
                    f"Refer-To: {refer_to}",
                    f"Referred-By: <sip:{sip.username}@{sip.myIP}:"
                    f"{sip.myPort}>",
                    "Supported: replaces, norefersub",
                ),
                timeout=3.0,
            )
        except Exception as e:
            diag.log(f"transfer: REFER failed to send ({e!r})")
            code = None
        if self._transfer_aborted(bridge):
            return
        if code is None or code >= 300:
            # Avaya IP Office answers 405 here: it does not accept a blind
            # REFER from a third-party SIP extension.  Transfer the call
            # ourselves instead — dial the target and bridge the audio.
            diag.log(f"transfer: REFER refused (code={code}) — falling "
                     "back to bridging the call ourselves")
            self._bridge_transfer(bridge, call, target)
            return
        diag.log(f"transfer: REFER accepted ({code}) — waiting for the "
                 "PBX to connect the caller")
        final = sip_dialog.wait_for_final_notify(call_id, timeout=20.0)
        if final is None:
            diag.log("transfer: no final NOTIFY (20s) — closing our leg "
                     "anyway; the PBX has the caller")
        elif final >= 300:
            diag.log(f"transfer: target refused ({final}) — staying on "
                     "the call")
            self._transfer_failed(bridge, spoken=True)
            return
        else:
            diag.log(f"transfer: connected ({final}) — closing our leg")
        self.hangup()

    RING_TIMEOUT = 35.0   # how long we let the target's phone ring

    @staticmethod
    def _transfer_aborted(bridge) -> bool:
        """The caller talked us out of it mid-dial ("لا لا، لحظة")."""
        if not getattr(bridge, "_transfer_cancelled", False):
            return False
        diag.log("transfer: cancelled by the caller — abandoning it")
        bridge._transfer_started = False
        return True

    def _bridge_transfer(self, bridge, call, target: str) -> None:
        """Dial the target ourselves and relay audio between the legs."""
        with self._lock:
            phone = self.phone
        if phone is None:
            self._transfer_failed(bridge, spoken=True)
            return
        try:
            consult = phone.call(target)
        except Exception as e:
            diag.log(f"transfer: dialling {target} failed ({e!r})")
            self._transfer_failed(bridge, spoken=True)
            return
        diag.log(f"transfer: calling {target} — waiting for an answer")
        deadline = time.monotonic() + self.RING_TIMEOUT
        while time.monotonic() < deadline:
            if self._transfer_aborted(bridge):
                # Never connect someone who just said not to.
                self._hangup_other(consult)
                return
            if consult.state == CallState.ANSWERED:
                break
            if consult.state == CallState.ENDED:
                diag.log(f"transfer: {target} rejected the call")
                self._transfer_failed(bridge, spoken=True)
                return
            if call.state != CallState.ANSWERED:
                diag.log("transfer: caller hung up while we were dialling")
                self._hangup_other(consult)
                return
            time.sleep(0.1)
        if self._transfer_aborted(bridge):
            self._hangup_other(consult)
            return
        if consult.state != CallState.ANSWERED:
            diag.log(f"transfer: {target} did not answer in "
                     f"{self.RING_TIMEOUT:.0f}s")
            self._hangup_other(consult)
            self._transfer_failed(bridge, spoken=True)
            return
        diag.log(f"transfer: {target} answered — bridging the two legs")
        # Hand the caller's audio over from the AI to the relay.
        bridge.wants_hangup = False
        bridge.transfer_target = None
        bridge.stop()
        relay = CallBridge(call, consult)
        relay.start()
        with self._lock:
            self.relay = relay
            self.relay_call = consult

    def _hangup_other(self, other) -> None:
        """End a leg that isn't self.call (the consult/target leg)."""
        with self._lock:
            phone = self.phone
        try:
            if other.state == CallState.ANSWERED:
                for client in other.RTPClients:
                    try:
                        client.stop()
                    except Exception:
                        pass
                other.state = CallState.ENDED
                call_id = other.request.headers.get("Call-ID")
                if phone is not None:
                    phone.calls.pop(call_id, None)
                sip_dialog.send_request(other.sip, other.request, "BYE")
                sip_dialog.forget(call_id)
            else:
                # Still ringing: CANCEL the INVITE transaction.
                sip_dialog.send_cancel(other.sip, other.request)
                for client in other.RTPClients:
                    try:
                        client.stop()
                    except Exception:
                        pass
                other.state = CallState.ENDED
                if phone is not None:
                    phone.calls.pop(
                        other.request.headers.get("Call-ID"), None)
        except Exception as e:
            diag.log(f"transfer: tearing down the target leg failed ({e!r})")

    # What the agent says when a transfer could not be completed.  It is
    # spoken, so it is undiacritized Arabic like the rest of the UI text.
    TRANSFER_FAILED_AR = ("عذرا، ما قدرت اوصلكم بالموظف الحين. "
                          "هل اقدر اساعدكم بشي ثاني؟")
    TRANSFER_FAILED_NOTE = (
        "The transfer did NOT happen. Do not tell the caller they have "
        "been transferred; offer to take their details instead so a "
        "member of staff can call them back."
    )

    def _transfer_failed(self, bridge, spoken: bool = False) -> None:
        """The transfer didn't happen: cancel the pending hangup and let
        the agent tell the caller, instead of dropping them."""
        bridge._transfer_started = False
        cancel = getattr(bridge, "_cancel_pending_hangup", None)
        if cancel is not None:
            cancel("transfer failed")
        else:
            bridge.wants_hangup = False
            bridge.transfer_target = None
        if not spoken:
            return
        say = getattr(bridge, "say", None)
        note = getattr(bridge, "note", None)
        try:
            if say is not None:
                say(self.TRANSFER_FAILED_AR)
            if note is not None:
                note(self.TRANSFER_FAILED_NOTE)
        except Exception as e:
            diag.log(f"transfer: apology failed ({e!r})")

    def snapshot(self) -> dict:
        with self._lock:
            call = self.call
            return {
                "status": self.status(),
                "error": self.last_error,
                "call_state": call.state if call else None,
                "direction": self.direction,
                "remote": self.remote,
                "auto_answer": self._auto_answer_enabled,
                "duration": (
                    int(time.time() - self.answered_at)
                    if self.answered_at else 0
                ),
            }

    def clear_error(self) -> None:
        with self._lock:
            self.last_error = ""

    def shutdown(self) -> None:
        self._end_call_cleanup()
        self.unregister()
