"""Correctly-formed in-dialog SIP requests (BYE, REFER).

pyVoIP 1.6.8 builds in-dialog requests in ways Avaya IP Office drops on
the floor without a reply:

  * the Request-URI is ``Contact.strip("<").strip(">")``.  ``strip`` only
    removes those characters from the *ends* of the string, so a remote
    Contact of ``"Usman Nazir" <sip:1210@pbx:5060;transport=udp>`` becomes
    ``"Usman Nazir" <sip:1210@pbx:5060;transport=udp`` — display name kept,
    closing bracket eaten.  The request line is malformed and the PBX
    discards the message (that is why BYE never actually cleared the call
    and REFER got no response at all).
  * the Via header is copied from the inbound INVITE.  That is right for a
    *response* but wrong for a *request*: a request carries the sender's
    own Via with a fresh branch.  Echoing the PBX's Via makes the PBX see
    a request that appears to come from itself.
  * a 401/407 challenge on an in-dialog request is never answered.

REFER isn't implemented by pyVoIP at all.  This module builds both
methods per RFC 3261 §12.2 and RFC 3515, waits for the response, and
retries once with digest auth when challenged.
"""
import hashlib
import random
import re
import threading
import time

from . import diag

# call_id -> next CSeq number we will use for our own requests
_cseq = {}
# (call_id, cseq_number) -> {"event": Event, "message": SIPMessage|None}
_pending = {}
# call_id -> {"event": Event, "codes": [int]}  (REFER progress NOTIFYs)
_notifies = {}
_lock = threading.Lock()

_URI_RE = re.compile(r"<([^>]+)>")


def uri_from_contact(raw: str) -> str:
    """The bare SIP URI from a Contact/To/From header value.

    ``"Usman Nazir" <sip:1210@pbx:5060;transport=udp>`` -> the part inside
    the angle brackets; a bare ``sip:1210@pbx`` is returned as-is.
    """
    raw = (raw or "").strip()
    m = _URI_RE.search(raw)
    if m:
        return m.group(1).strip()
    # No angle brackets: drop any trailing header parameters (";tag=...").
    return raw.split(";tag=")[0].strip()


def _new_branch() -> str:
    return "z9hG4bK" + hashlib.md5(
        str(random.randint(1, 2**32)).encode()
    ).hexdigest()[:24]


def _next_cseq(call_id: str, request) -> int:
    with _lock:
        n = _cseq.get(call_id)
        if n is None:
            # Start above anything the remote side has used, so PBXs that
            # (incorrectly) track one CSeq space per dialog stay happy.
            try:
                n = int(request.headers["CSeq"]["check"]) + 1
            except Exception:
                n = 1
        _cseq[call_id] = n + 1
        return n


def dialog_parties(sip, request):
    """(local_header, remote_header, remote_target_uri) for this dialog."""
    call_id = request.headers["Call-ID"]
    our_tag = sip.tagLibrary[call_id]
    from_h = request.headers["From"]
    to_h = request.headers["To"]
    if from_h["tag"] == our_tag:
        # We placed the call: From is us.
        local = f'{from_h["raw"]};tag={our_tag}'
        remote = to_h["raw"]
        if to_h["tag"]:
            remote += f';tag={to_h["tag"]}'
    else:
        local = f'{to_h["raw"]};tag={our_tag}'
        remote = f'{from_h["raw"]};tag={from_h["tag"]}'
    target = uri_from_contact(request.headers.get("Contact", ""))
    if not target:
        target = uri_from_contact(remote)
    return local, remote, target


def build_request(sip, request, method: str, cseq: int,
                  extra_headers=(), auth: str = "") -> str:
    local, remote, target = dialog_parties(sip, request)
    call_id = request.headers["Call-ID"]
    msg = f"{method} {target} SIP/2.0\r\n"
    # OUR Via, with a fresh branch — this is a request, not a response.
    msg += (f"Via: SIP/2.0/UDP {sip.myIP}:{sip.myPort};"
            f"branch={_new_branch()};rport\r\n")
    msg += "Max-Forwards: 70\r\n"
    msg += f"From: {local}\r\n"
    msg += f"To: {remote}\r\n"
    msg += f"Call-ID: {call_id}\r\n"
    msg += f"CSeq: {cseq} {method}\r\n"
    msg += f"Contact: <sip:{sip.username}@{sip.myIP}:{sip.myPort}>\r\n"
    for h in extra_headers:
        msg += f"{h}\r\n"
    if auth:
        msg += f"{auth}\r\n"
    msg += "User-Agent: Kayan Voice\r\n"
    msg += "Content-Length: 0\r\n\r\n"
    return msg


def _auth_header(sip, response, method: str) -> str:
    """Digest response to a 401/407 challenge on our own request."""
    realm = response.authentication["realm"]
    nonce = response.authentication["nonce"]
    uri = f"sip:{sip.server};transport=UDP"
    ha1 = hashlib.md5(
        f"{sip.username}:{realm}:{sip.password}".encode("utf8")
    ).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode("utf8")).hexdigest()
    resp = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode("utf8")).hexdigest()
    name = ("Proxy-Authorization"
            if _status_code(response) == 407 else "Authorization")
    return (f'{name}: Digest username="{sip.username}",realm="{realm}",'
            f'nonce="{nonce}",uri="{uri}",response="{resp}",algorithm=MD5')


def _status_code(message) -> int:
    try:
        value = message.status.value
        return int(value[0] if isinstance(value, tuple) else value)
    except Exception:
        return 0


# ---------- response plumbing (fed by the controller's SIP hook) ----------

def note_response(message) -> None:
    """Hand an inbound SIP response to whoever is waiting for it."""
    try:
        call_id = message.headers["Call-ID"]
        cseq = int(message.headers["CSeq"]["check"])
    except Exception:
        return
    with _lock:
        slot = _pending.get((call_id, cseq))
    if slot is not None:
        slot["message"] = message
        slot["event"].set()


def note_notify(call_id: str, code: int) -> None:
    """Record a REFER-progress NOTIFY (sipfrag status code)."""
    with _lock:
        slot = _notifies.setdefault(
            call_id, {"event": threading.Event(), "codes": []})
    slot["codes"].append(code)
    slot["event"].set()


def wait_for_final_notify(call_id: str, timeout: float):
    """Wait for a NOTIFY carrying a final (>=200) status; returns it."""
    deadline = time.monotonic() + timeout
    with _lock:
        slot = _notifies.setdefault(
            call_id, {"event": threading.Event(), "codes": []})
    seen = 0
    while time.monotonic() < deadline:
        codes = slot["codes"]
        while seen < len(codes):
            code = codes[seen]
            seen += 1
            if code >= 200:
                return code
        slot["event"].clear()
        slot["event"].wait(min(0.5, max(0.05, deadline - time.monotonic())))
    return None


def forget(call_id: str) -> None:
    with _lock:
        _cseq.pop(call_id, None)
        _notifies.pop(call_id, None)
        for key in [k for k in _pending if k[0] == call_id]:
            _pending.pop(key, None)


def send_cancel(sip, invite) -> None:
    """CANCEL an INVITE we sent that hasn't been answered yet.  Unlike an
    in-dialog request this must reuse the INVITE's own branch and CSeq
    number (same transaction), and carry no To-tag."""
    headers = invite.headers
    target = uri_from_contact(headers["To"]["raw"])
    branch = ""
    try:
        branch = headers["Via"][0].get("branch", "")
    except Exception:
        pass
    msg = f"CANCEL {target} SIP/2.0\r\n"
    msg += (f"Via: SIP/2.0/UDP {sip.myIP}:{sip.myPort}"
            f"{';branch=' + branch if branch else ''};rport\r\n")
    msg += "Max-Forwards: 70\r\n"
    msg += f'From: {headers["From"]["raw"]};tag={headers["From"]["tag"]}\r\n'
    msg += f'To: {headers["To"]["raw"]}\r\n'
    msg += f'Call-ID: {headers["Call-ID"]}\r\n'
    msg += f'CSeq: {headers["CSeq"]["check"]} CANCEL\r\n'
    msg += "Content-Length: 0\r\n\r\n"
    for line in msg.strip().splitlines():
        diag.log(f"sip -> {line}")
    sip.out.sendto(msg.encode("utf8"), (sip.server, sip.port))


# ---------- the one public entry point ----------

def send_request(sip, request, method: str, extra_headers=(),
                 timeout: float = 1.5):
    """Send an in-dialog request, wait for the response, retry once with
    digest auth if challenged.  Returns the final status code, or None if
    the PBX never answered."""
    call_id = request.headers["Call-ID"]
    challenge = None
    for attempt in (1, 2):
        cseq = _next_cseq(call_id, request)
        auth = _auth_header(sip, challenge, method) if challenge else ""
        msg = build_request(sip, request, method, cseq, extra_headers, auth)
        slot = {"event": threading.Event(), "message": None}
        with _lock:
            _pending[(call_id, cseq)] = slot
        try:
            for line in msg.strip().splitlines():
                diag.log(f"sip -> {line}")
            sip.out.sendto(msg.encode("utf8"), (sip.server, sip.port))
            slot["event"].wait(timeout)
            response = slot["message"]
        finally:
            with _lock:
                _pending.pop((call_id, cseq), None)
        if response is None:
            diag.log(f"sip: no response to {method} after {timeout:.1f}s")
            return None
        code = _status_code(response)
        diag.log(f"sip <- {code} for our {method}")
        if code in (401, 407) and attempt == 1:
            challenge = response
            diag.log(f"sip: {method} challenged ({code}) — retrying with auth")
            continue
        return code
    return None
