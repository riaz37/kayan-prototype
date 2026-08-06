"""Transport interface: what a call's audio is connected to.

A transport owns the audio for one ANSWERED call — the sound card
(DeviceTransport), an AI agent (GeminiTransport), or a test echo
(LoopbackTransport).  The controller creates it when a call is answered and
stops it when the call ends.  A transport that fails mid-call sets
``self.error``; the controller polls it and hangs up.
"""


class CallTransport:
    def __init__(self, call):
        self.call = call
        self.error = None

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError
