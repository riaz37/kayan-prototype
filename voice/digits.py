"""Turning spoken numbers into numbers you can actually dial.

A caller says "zero five nine four six four nine two six one". Whatever
transcribes it — our STT or Gemini's — hands back words, or Arabic-Indic
numerals, or a half-and-half mess ("05 nine four six"). The model is then
asked to record "the caller's phone number" and stores whatever it saw, so
the team gets a lead they cannot call.

Two jobs here:

* ``spoken_to_digits`` rewrites runs of number words into digits before the
  model ever sees the transcript. Three or more in a row, so "one moment"
  and "for one thing" are left alone.
* ``phone_digits`` / ``usable_phone`` are the gate: a value captured into a
  phone-ish variable is reduced to its digits and refused if there are too
  few of them, which makes the collect step ask again instead of saving
  something unusable.
"""
import re

# English, plus the Arabic words a bilingual caller mixes in. "oh" is how
# people say zero in a phone number; "double"/"triple" repeat the next one.
WORDS = {
    "zero": "0", "oh": "0", "o": "0", "nought": "0", "naught": "0",
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "صفر": "0", "واحد": "1", "اثنان": "2", "اثنين": "2", "ثلاثة": "3",
    "ثلاثه": "3", "أربعة": "4", "اربعة": "4", "اربعه": "4", "خمسة": "5",
    "خمسه": "5", "ستة": "6", "سته": "6", "سبعة": "7", "سبعه": "7",
    "ثمانية": "8", "ثمانيه": "8", "تسعة": "9", "تسعه": "9",
    # transliterated English digits, which Arabic-tuned STT loves to emit
    "زيرو": "0", "ون": "1", "تو": "2", "ثري": "3", "فور": "4", "فايف": "5",
    "سكس": "6", "سفن": "7", "ايت": "8", "ناين": "9",
}
REPEATERS = {"double": 2, "triple": 3, "دبل": 2}

# ٠١٢٣٤٥٦٧٨٩ and ۰۱۲۳۴۵۶۷۸۹ are digits; models copy them through verbatim.
EASTERN = {ord(c): str(i % 10) for i, c in enumerate(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹")}

# Kept in step with backend.store, which is the authority: the floor is the
# shortest real mobile number, not E.164's shortest legal one. It does
# double duty here — it is also how many trailing digits still look like
# half of something the caller is still reading out.
MIN_PHONE_DIGITS = 9
MAX_PHONE_DIGITS = 15     # E.164's limit

_WORD_RE = "|".join(sorted((re.escape(w) for w in
                            list(WORDS) + list(REPEATERS)),
                           key=len, reverse=True))
# A run of spoken/written digits: "zero five nine", "05 nine four six",
# "059 464 9261", "double five one two". Bounded by non-word characters so
# "someone" never matches "one".
_RUN = re.compile(
    rf"(?<![^\W\d_])(?:{_WORD_RE}|\d+)"
    rf"(?:[\s,،\-‐-―.]+(?:{_WORD_RE}|\d+))*"
    rf"(?![^\W\d_])",
    re.IGNORECASE | re.UNICODE)
_SPLIT = re.compile(r"[\s,،\-‐-―.]+")
_PHONE_NAME = re.compile(
    r"phone|mobile|cell|whats\s*app|whatsapp|tel|number|contact|رقم|جوال|هاتف",
    re.IGNORECASE)


def spoken_to_digits(text: str, run: int = 3) -> str:
    """Rewrite runs of `run`+ spoken digits as digits, leaving prose alone.

    "my number is zero five nine four" -> "my number is 0594"
    "one moment please"                -> unchanged
    """
    if not text:
        return text
    def convert(match):
        """A long enough run becomes a number; anything shorter is prose
        and is returned exactly as the caller said it."""
        parts = [p for p in _SPLIT.split(match.group(0)) if p]
        out, repeat, spoken = [], 0, 0
        for part in parts:
            key = part.lower()
            if key in REPEATERS:
                repeat = REPEATERS[key]
                continue
            if key in WORDS:
                out.append(WORDS[key] * (repeat or 1))
                spoken += 1
            elif part.isdigit():
                out.append(part * (repeat or 1))
            else:
                return match.group(0)
            repeat = 0
        if len(out) < run or (run > 1 and not spoken and len(parts) < 2):
            return match.group(0)      # "I have 2 offices" is not a number
        # Trailing separator (a full stop that ended the sentence) is kept.
        tail = match.group(0)[len(match.group(0).rstrip(".,،")):]
        return "".join(out) + tail

    return _RUN.sub(convert, text.translate(EASTERN))


def phone_digits(value) -> str:
    """Every digit in a spoken or written number, in order."""
    if value in (None, ""):
        return ""
    text = spoken_to_digits(str(value), run=1).translate(EASTERN)
    return re.sub(r"\D", "", text)


def looks_like_phone(name: str = "", description: str = "") -> bool:
    return bool(_PHONE_NAME.search(f"{name} {description}"))


def usable_phone(value) -> bool:
    """Could someone actually ring this?"""
    return MIN_PHONE_DIGITS <= len(phone_digits(value)) <= MAX_PHONE_DIGITS


# Words a caller tacks on after a group of digits, and that speech
# recognition faithfully transcribes: "zero one seven one two, okay?".
# They sit between the digits and the end of the string, so a plain
# "does this end in digits?" test misses the fragment underneath them.
_TRAILING_FILLER = re.compile(
    r"(?:\b(?:ok|okay|yeah|yes|right|please|so|um|uh|and|then|thanks?|"
    r"sorry|hello|hmm)\b|يعني|تمام|طيب|زين|ايوه|ايوا|نعم|بس|و|ثم|"
    r"من\s*فضلك|لو\s*سمحت|شكرا)"
    r"[\s.,،!?؟…۔:;\-–—]*$", re.IGNORECASE | re.UNICODE)

_PUNCT = ".،,!?؟…۔:;-–— \t\n"

# Nouns that mean "a long number the caller has to read out", as opposed to
# the numbers an agent hands back (رقم الملف, رقم الطلب). Used to decide
# whether a short run of digits is half a dictated number or just an
# ordinary answer that happens to end in one.
_LONG_NUMBER_NOUN = re.compile(
    r"جوال|هاتف|موبايل|هوية|الهويه|ايبان|أيبان|حساب\s*بنكي|واتس|"
    r"phone|mobile|cell|whats\s*app|whatsapp|national\s*id|iban|"
    r"bank\s*account|contact\s*number", re.IGNORECASE | re.UNICODE)


def asks_for_a_long_number(agent_text: str) -> bool:
    """Did the agent just ask the caller to read a long number out?

    This is what tells the transport that a short run of digits is half of
    something, rather than a complete answer. Without it the hold fires on
    every numeric reply — "دخلي الشهري 4000", "I was born in 1985" — and
    each one costs the caller a 2.5 s pause, or worse gets spliced onto
    whatever they say next and re-transcribed as one utterance.

    Deliberately narrow: it matches the nouns for numbers a caller
    *dictates*, not the ones the agent reads back (رقم الملف, رقم الطلب).
    """
    return bool(_LONG_NUMBER_NOUN.search(agent_text or ""))


def _digit_share(text: str) -> float:
    """How much of this turn is digits, ignoring spaces and punctuation."""
    digits_n = sum(c.isdigit() for c in text)
    letters = sum(c.isalpha() for c in text)
    return digits_n / (digits_n + letters) if digits_n + letters else 0.0


def unfinished_number(text: str, expecting: bool = False) -> bool:
    """Did the caller stop in the MIDDLE of reading a number out?

    People read a number in groups, with a pause between them, and a
    600 ms silence closes the utterance — so "zero five nine … four six
    four … nine two six one" arrives as three separate turns, each
    transcribed on its own and each wrong. When a turn ends on a short
    run of digits, the transport waits a moment for the rest.

    `expecting` is the agent having just asked for a phone number or an ID
    (see `asks_for_a_long_number`). It is what separates the two things a
    turn ending in digits can be. Without it the caller pays 2.5 s for
    every ordinary numeric answer; with it alone the heuristic would miss a
    caller who volunteers their number unprompted — so a turn that is
    mostly digits still counts.
    """
    if not text:
        return False
    # Speech recognition punctuates what it hears, and callers tail off
    # into "okay" and "يعني", so a turn that ended mid-number comes back as
    # "The number is 9678." or "0171 2, yeah". Matching digits at the very
    # end of the string then never fires, the fragment is answered on its
    # own, and the caller lands in the loop this function exists to
    # prevent: agent asks for the number, caller reads part of it, agent
    # says that is not a complete number, repeat — four times, on a real
    # call. Strip the trailing punctuation and filler first.
    stripped = text.strip().rstrip(_PUNCT)
    while True:
        shorter = _TRAILING_FILLER.sub("", stripped).rstrip(_PUNCT)
        if shorter == stripped:
            break
        stripped = shorter
    tail = re.search(r"[\d\s]+$", stripped)
    if not tail:
        return False
    count = len(re.sub(r"\D", "", tail.group(0)))
    if not 1 <= count < MIN_PHONE_DIGITS:
        return False
    # A short run of digits at the end of a sentence is only half a number
    # if a number was what we were waiting for, or if the caller said
    # little else — "0171 2" is a fragment, "my income is 4000" is not.
    return expecting or _digit_share(stripped) >= 0.5


def tidy_phone(value) -> str:
    """The value to store: digits only, and a leading + kept if it was
    written that way."""
    digits = phone_digits(value)
    if not digits:
        return str(value or "")
    return ("+" + digits) if str(value).strip().startswith("+") else digits
