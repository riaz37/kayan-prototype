"""Is this thing a phone number?

`backend/store.py` is the authority — it is what refuses to write a file
under a number nobody can ring, and its answer is the one that counts. This
is the same rule stated locally so the agent can decide what to put in the
prompt without a round trip: whether the number a turn arrived from is worth
telling the model it already has.

The distinction that matters here is the one the test rig makes obvious.
A SIP extension (`1000`, `1001`) arrives in the ANI exactly where a real
caller's number would, and it is not a number. Telling the agent "the
caller is on 1000, use it" would file a family under an extension.
"""
import re

# Mirrors backend.store.MIN_PHONE_DIGITS / MAX_PHONE_DIGITS — see there
# for why the floor is the shortest real mobile, not the shortest legal one.
MIN_PHONE_DIGITS = 9
MAX_PHONE_DIGITS = 15

_EASTERN = {ord(c): str(i % 10) for i, c in enumerate(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹")}


def digits(value) -> str:
    """Every digit in a number, in order, Arabic-Indic ones included."""
    return re.sub(r"\D", "", str(value or "").translate(_EASTERN))


def usable(value) -> bool:
    """Could someone actually ring this?"""
    return MIN_PHONE_DIGITS <= len(digits(value)) <= MAX_PHONE_DIGITS


def spaced(value) -> str:
    """Digits separated for speech: "0501234567" -> "0 5 0 1 2 3 4 5 6 7".

    TTS reads a run of digits as a quantity ("five hundred and one
    million…"). Separating them is what makes a number read back digit by
    digit, which is how the voice prompt says to confirm one.
    """
    return " ".join(digits(value))
