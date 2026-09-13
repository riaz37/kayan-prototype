"""
Deterministic intent router — runs BEFORE the LLM.

Classifies user messages into intents using keyword matching.
Forces the right flow so the LLM doesn't have to figure out routing.

Intents:
  - registration: wants to register / join / benefit
  - file_completion: wants to complete their file
  - support: needs help / wants to submit a request
  - status: asks about payment / request status
  - escalate: wants to talk to an employee
  - cancel: wants to stop / cancel
  - faq: general question about services
  - greeting: just saying hello
  - unknown: doesn't match anything
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Intent:
    name: str          # registration, support, status, escalate, cancel, faq, greeting, unknown
    confidence: float  # 0.0 - 1.0
    forced_context: str  # injected into LLM context to force the right flow


# ── Arabic patterns ──────────────────────────────────────────────
_AR_REGISTRATION = [
    r"ابي\s*اسجل", r"ابي\s*أسجل", r"اريد\s*التسجيل", r"أريد\s*التسجيل",
    r"ابي\s*افتح\s*ملف", r"ابي\s*أفتح\s*ملف", r"اريد\s*افتح\s*ملف",
    r"ابي\s*انضم", r"اريد\s*انضم", r"ابي\s*استفيع", r"اريد\s*استفادة",
    r"ابي\s*خدمة", r"اريد\s*خدمة", r"ابي\s*تسجيل", r"اريد\s*تسجيل",
    r"كيف\s*اسجل", r"كيف\s*أسجل", r"وش\s*خطوات\s*التسجيل",
    r"ابي\s*سجل", r"ابي\s*أسجل", r"اريد\s*سجل",
    r"ابي\s*assist", r"ابي\s*assistance",
]

_AR_FILE_COMPLETION = [
    r"ابي\s*اكمل\s*ملفي", r"ابي\s*أكمل\s*ملفي", r"اريد\s*اكمل\s*ملفي",
    r"اكمل\s*ملفي", r"أكمل\s*ملفي", r"ناقص\s*في\s*ملفي",
    r"وش\s*ناقص", r"وش\s*نقص", r"ابي\s*ابدأ\s*اكمل",
    r"تكملة\s*الملف", r"استكمال\s*الملف",
]

_AR_SUPPORT = [
    r"ابي\s*مساعدة", r"اريد\s*مساعدة", r"ابي\s*طلب", r"اريد\s*طلب",
    r"ابي\s*اشكوا", r"اريد\s*اشكوا", r"شكوى", r"مشكلة",
    r"ابي\s*ارسل\s*طلب", r"اريد\s*ارسل\s*طلب", r"ابي\s*أرسل\s*طلب",
    r"ابي\s*تقديم\s*طلب", r"اريد\s*تقديم\s*طلب",
]

_AR_STATUS = [
    r"وين\s*طلب", r"وين\s* طلبي", r"ش\s*حالة\s*طلبي",
    r"متى\s*يوصل", r"متى\s*يجهز", r"متى\s*الدفعة",
    r"ش\s*حالة\s*الملف", r"وين\s*وصل\s*طلب", r"تتبع\s*طلب",
    r"حالة\s*الطلب", r"حالة\s*الملف", r"看完\s*تتتابع",
    r"ابي\s*اعرف\s*حالة", r"اريد\s*اعرف\s*حالة",
    r"ش\s*حالة", r"وين\s*وصل",
]

_AR_ESCALATE = [
    r"ابي\s*اتكلم", r"اريد\s*اتكلم", r"ابي\s*اتصل", r"اريد\s*اتصل",
    r"LOYEE", r"موظف", r".KEYAN", r"تواصل\s*مع",
    r"ابي\s*حد\s*يكلمني", r"ابي\s*حد\s*يتصل", r"اريد\s*حد\s*يتكلم",
]

_AR_CANCEL = [
    r"^الغاء$", r"^غّير$", r"^لا$", r"^بس$", r"^كفاية$",
    r"^الغ\s*و$", r"^غ ي ر$", r"^الغاء\s*التسجيل$",
    r"^cancel$", r"^stop$", r"^nevermind$", r"^never\s*mind$",
]

_AR_GREETING = [
    r"^مرحبا$", r"^مرحبا\s*!*$", r"^اهلا$", r"^اهلا\s*!*$",
    r"^السلام\s*عليكم$", r"^السلام\s*عليكم\s*!*",
    r"^هاي$", r"^هلا$", r"^صباح\s*(الخير|النور)$",
    r"^مساء\s*(الخير|النور)$", r"^اخبارك$", r"^كيفك$",
    r"^ا\s*هلا$", r"^ا\s*هلا\s*وغل",
]

_AR_FAQ = [
    r"وش\s*خدماتكم", r"وش\s*تسوون", r"كيف\s*تساعدون",
    r"وش\s*الشروط", r"كيف\s*اساعد", r"ش\s*عدد\s*الاوراق",
    r"وش\s*يحتاج", r"وش\s*المطلوب", r"تقبلون",
    r"ما\s*هي\s*الخدمات", r"ابي\s*اعرف\s*خدمات",
]


# ── English patterns ─────────────────────────────────────────────
_EN_REGISTRATION = [
    r"i\s*want\s*to\s*register", r"register\s*me", r"sign\s*me\s*up",
    r"how\s*to\s*register", r"how\s*do\s*i\s*register",
    r"i\s*want\s*to\s*join", r"i\s*want\s*to\s*benefit",
    r"open\s*a\s*file", r"create\s*my\s*file", r"start\s*registration",
    r"apply\s*for\s*benefits", r"i\s*need\s*to\s*register",
    r"i'd\s*like\s*to\s*register", r"want\s*to\s*sign\s*up",
]

_EN_FILE_COMPLETION = [
    r"complete\s*my\s*file", r"what.*missing", r"file\s*completion",
    r"finish\s*my\s*file", r"update\s*my\s*file",
    r"what.*need.*complete", r"still\s*missing",
]

_EN_SUPPORT = [
    r"i\s*need\s*help", r"can\s*you\s*help", r"submit\s*a\s*request",
    r"file\s*a\s*complaint", r"i\s*have\s*a\s*problem",
    r"i\s*have\s*an\s*issue", r"support\s*request",
    r"i\s*want\s*to\s*request", r"i\s*need\s*assistance",
]

_EN_STATUS = [
    r"where.*my\s*(request|file|payment)", r"status\s*of",
    r"what.*happened\s*to", r"when\s*will",
    r"check\s*status", r"track\s*my", r"follow\s*up",
    r"when\s*is\s*the\s*next\s*payment",
]

_EN_ESCALATE = [
    r"talk\s*to\s*(a\s*)?(human|person|agent|employee|someone)",
    r"speak\s*to\s*(a\s*)?(human|person|agent|employee)",
    r"transfer\s*me", r"connect\s*me", r"real\s*(person|agent)",
    r"i\s*want\s*to\s*speak", r"can\s*i\s*talk",
]

_EN_CANCEL = [
    r"^cancel$", r"^stop$", r"^never\s*mind$", r"^nevermind$",
    r"^no\s*thanks$", r"^nah$", r"^nvm$",
]

_EN_GREETING = [
    r"^hi$", r"^hello$", r"^hey$", r"^howdy$",
    r"^good\s*(morning|afternoon|evening)$",
    r"^assalamu\s*alaikum$", r"^salam$",
]

_EN_FAQ = [
    r"what\s*(do|does)\s*(you|your)\s*(service|organization|association)",
    r"what\s*services", r"how\s*does\s*this\s*work",
    r"what\s*are\s*the\s*requirements", r"who\s*are\s*you",
    r"what\s*do\s*you\s*do", r"tell\s*me\s*about",
]


def _match(text: str, patterns: list[str]) -> bool:
    """Check if text matches any pattern (case-insensitive)."""
    lower = text.strip().lower()
    for p in patterns:
        if re.search(p, lower, re.IGNORECASE):
            return True
    return False


def classify(text: str) -> Intent:
    """
    Classify user message into an intent.
    Returns Intent with name, confidence, and forced_context for the LLM.
    """
    text = text.strip()
    if not text:
        return Intent("greeting", 1.0, "")

    # Cancel — highest priority, short circuit
    if _match(text, _AR_CANCEL + _EN_CANCEL):
        return Intent("cancel", 1.0, "المستخدم يريد الإلغاء. استخدم cancel_flow.")

    # Registration
    if _match(text, _AR_REGISTRATION + _EN_REGISTRATION):
        return Intent("registration", 1.0,
            "الغير مسجل في النظام. رقم الجوال معك في السياق — لا تسأل عنه.\n"
            "ابدأ مباشرة: سلّم الفئة أولاً (مجهول الأبوين / شهيد / معاق / سجين / مفقود).\n"
            "لا تُظهر أكواد OC-xxx للمستخدم — استخدم الأسماء العربية فقط.\n"
            "لا تقل 'مرحبا' أو ترحيب — انتقل مباشرة لجمع البيانات."
        )

    # File completion
    if _match(text, _AR_FILE_COMPLETION + _EN_FILE_COMPLETION):
        return Intent("file_completion", 1.0,
            "المستخدم يريد استكمال ملفه. ابدأ بـ get_completeness لтаobao ما ناقص."
        )

    # Support request
    if _match(text, _AR_SUPPORT + _EN_SUPPORT):
        return Intent("support", 1.0,
            "المستخدم يريد تقديم طلب دعم. ابدأ بـ search_request_types."
        )

    # Status enquiry
    if _match(text, _AR_STATUS + _EN_STATUS):
        return Intent("status", 1.0,
            "المستخدم يسأل عن حالة طلب أو ملف. ابحث في التاريخ أو الطلبات المفتوحة."
        )

    # Escalate
    if _match(text, _AR_ESCALATE + _EN_ESCALATE):
        return Intent("escalate", 1.0,
            "المستخدم يريد التحدث مع موظف. أنشئ تذكرة فوراً via create_ticket."
        )

    # FAQ
    if _match(text, _AR_FAQ + _EN_FAQ):
        return Intent("faq", 0.8,
            "المستخدم يسأل عن الخدمات. ابحث في search_faqs أو أجب من المعرفة."
        )

    # Greeting — lowest priority, only if nothing else matched
    if _match(text, _AR_GREETING + _EN_GREETING):
        return Intent("greeting", 1.0, "")

    # Unknown — let the LLM handle it
    return Intent("unknown", 0.0, "")
