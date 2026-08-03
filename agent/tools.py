"""
Tool definitions and handlers for the LLM agent.
Each tool maps to a backend API endpoint. Tool declarations follow the
OpenAI function calling schema (for vLLM/Qwen). Handlers make HTTP calls to the backend.
"""
from typing import Optional
import time
import httpx
from agent.config import settings

BACKEND = settings.backend_url

# Simple in-memory cache for FAQ responses
_faq_cache = {}
_FAQ_CACHE_TTL = 3600  # 1 hour


def _get(path: str, params: Optional[dict] = None) -> dict:
    resp = httpx.get(f"{BACKEND}{path}", params=params, timeout=30)
    return resp.json()


def _post(path: str, body: Optional[dict] = None) -> dict:
    resp = httpx.post(f"{BACKEND}{path}", json=body or {}, timeout=30)
    return resp.json()


def _patch(path: str, body: Optional[dict] = None) -> dict:
    resp = httpx.patch(f"{BACKEND}{path}", json=body or {}, timeout=30)
    return resp.json()


# ============================================================ Tool Handlers

def handle_check_phone(phone: str) -> dict:
    return _post("/registration/check-phone", {"phone": phone})


def handle_check_eligibility(orphan_category_id: str) -> dict:
    return _post("/registration/check-eligibility", {"orphan_category_id": orphan_category_id})


def handle_create_file(phone: str, case_type: str, orphan_category_id: str,
                       full_name_ar: str, city: str) -> dict:
    return _post("/beneficiary/create-file", {
        "phone": phone, "case_type": case_type,
        "orphan_category_id": orphan_category_id,
        "full_name_ar": full_name_ar, "city": city,
    })


def handle_get_file(beneficiary_id: str) -> dict:
    return _get(f"/beneficiary/{beneficiary_id}")


def handle_update_section(beneficiary_id: str, section_id: str, values: dict) -> dict:
    return _patch(f"/beneficiary/{beneficiary_id}/section/{section_id}", {"values": values})


def handle_get_completeness(beneficiary_id: str) -> dict:
    return _get(f"/beneficiary/{beneficiary_id}/completeness")


def handle_submit_file(beneficiary_id: str) -> dict:
    return _post(f"/beneficiary/{beneficiary_id}/submit")


def handle_add_dependent(beneficiary_id: str, name_ar: str, relationship_ar: str,
                         birth_date: str = "", education_stage: str = "",
                         has_special_needs: bool = False) -> dict:
    return _post(f"/beneficiary/{beneficiary_id}/dependents", {
        "name_ar": name_ar, "relationship_ar": relationship_ar,
        "birth_date": birth_date or None, "education_stage": education_stage or None,
        "has_special_needs": has_special_needs,
    })


def handle_list_dependents(beneficiary_id: str) -> dict:
    return _get(f"/beneficiary/{beneficiary_id}/dependents")


def handle_update_document(beneficiary_id: str, document_type_id: str, status: str) -> dict:
    return _patch(f"/beneficiary/{beneficiary_id}/documents/{document_type_id}", {"status": status})


def handle_get_financial_profile(beneficiary_id: str) -> dict:
    return _get(f"/beneficiary/{beneficiary_id}/financial-profile")


def handle_add_obligation(beneficiary_id: str, type_id: str,
                          monthly_sar: float, documented: bool = True) -> dict:
    return _post(f"/beneficiary/{beneficiary_id}/obligations", {
        "type_id": type_id,
        "monthly_sar": monthly_sar, "documented": documented,
    })


def handle_add_person_cost(beneficiary_id: str, type_id: str,
                           monthly_sar: float) -> dict:
    return _post(f"/beneficiary/{beneficiary_id}/person-costs", {
        "type_id": type_id,
        "monthly_sar": monthly_sar,
    })


def handle_search_request_types(q: str) -> dict:
    return _get("/request-types/search", {"q": q})


def handle_create_support_request(beneficiary_id: str, request_type_id: str,
                                  case_description_ar: str,
                                  requested_amount_sar: float = 0) -> dict:
    return _post("/support-requests", {
        "beneficiary_id": beneficiary_id,
        "request_type_id": request_type_id,
        "case_description_ar": case_description_ar,
        "requested_amount_sar": requested_amount_sar,
    })


def handle_get_support_request(request_id: str) -> dict:
    return _get(f"/support-requests/{request_id}")


def handle_add_request_detail(request_id: str, additional_detail_ar: str) -> dict:
    return _patch(f"/support-requests/{request_id}/add-detail", {"additional_detail_ar": additional_detail_ar})


def handle_search_faqs(q: str) -> dict:
    """Search FAQs with in-memory caching."""
    cache_key = q.lower().strip()
    now = time.time()

    # Check cache
    if cache_key in _faq_cache:
        cached_time, cached_result = _faq_cache[cache_key]
        if now - cached_time < _FAQ_CACHE_TTL:
            return cached_result

    # Cache miss - fetch from backend
    result = _get("/faqs/search", {"q": q})

    # Store in cache
    _faq_cache[cache_key] = (now, result)
    return result


def handle_create_ticket(subject_ar: str, channel: str, phone: str = "",
                         beneficiary_id: str = "", department_id: str = "DEP-BEN",
                         priority: str = "medium", first_message_ar: str = "") -> dict:
    body = {
        "subject_ar": subject_ar, "channel": channel,
        "department_id": department_id, "priority": priority,
    }
    if phone:
        body["phone"] = phone
    if beneficiary_id:
        body["beneficiary_id"] = beneficiary_id
    if first_message_ar:
        body["first_message_ar"] = first_message_ar
    return _post("/crm/tickets", body)


def handle_get_beneficiary_history(beneficiary_id: str) -> dict:
    return _get(f"/beneficiary/{beneficiary_id}/history")


def handle_list_programs() -> dict:
    return _get("/programs")


def handle_cancel_flow() -> dict:
    """Reset the current conversation flow. Returns confirmation message."""
    return {"cancelled": True,
            "reply_ar": "تم الإلغاء. كيف أقدر أساعدك في شيء ثاني؟"}



# ============================================================ Tool Router

TOOL_HANDLERS = {
    "check_phone": lambda **kw: handle_check_phone(**kw),
    "check_eligibility": lambda **kw: handle_check_eligibility(**kw),
    "create_file": lambda **kw: handle_create_file(**kw),
    "get_file": lambda **kw: handle_get_file(**kw),
    "update_section": lambda **kw: handle_update_section(**kw),
    "get_completeness": lambda **kw: handle_get_completeness(**kw),
    "submit_file": lambda **kw: handle_submit_file(**kw),
    "add_dependent": lambda **kw: handle_add_dependent(**kw),
    "list_dependents": lambda **kw: handle_list_dependents(**kw),
    "update_document": lambda **kw: handle_update_document(**kw),
    "get_financial_profile": lambda **kw: handle_get_financial_profile(**kw),
    "add_obligation": lambda **kw: handle_add_obligation(**kw),
    "add_person_cost": lambda **kw: handle_add_person_cost(**kw),
    "search_request_types": lambda **kw: handle_search_request_types(**kw),
    "create_support_request": lambda **kw: handle_create_support_request(**kw),
    "get_support_request": lambda **kw: handle_get_support_request(**kw),
    "add_request_detail": lambda **kw: handle_add_request_detail(**kw),
    "search_faqs": lambda **kw: handle_search_faqs(**kw),
    "create_ticket": lambda **kw: handle_create_ticket(**kw),
    "get_beneficiary_history": lambda **kw: handle_get_beneficiary_history(**kw),
    "list_programs": lambda **kw: handle_list_programs(**kw),
    "cancel_flow": lambda **kw: handle_cancel_flow(**kw),
}


def execute_tool(name: str, args: dict) -> dict:
    """Execute a tool by name with the given arguments."""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    try:
        return handler(**args)
    except Exception as e:
        return {"error": str(e)}


# ============================================================ Tool Declarations (OpenAI schema)

TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "check_phone",
            "description": "Check if a phone number is already registered in the system. Use this first when a new user contacts us.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Phone number (e.g. 0501234567)"},
                },
                "required": ["phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_eligibility",
            "description": "Check if a user is eligible for Kayan's services. Kayan serves الأيتام ذوو الظروف الخاصة (مجهولو الأبوين). Always ask this before creating a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "orphan_category_id": {
                        "type": "string",
                        "description": "Orphan category: OC-UNK (مجهول الأبوين), OC-MARTYR (شهيد), OC-DISABLED (معاق), OC-PRISONER (سجين), OC-DIVERGENT (مفقود)",
                    },
                },
                "required": ["orphan_category_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new beneficiary file. Use after verifying identity and eligibility.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Phone number"},
                    "case_type": {"type": "string", "description": "CT-IND for independent, CT-FOSTER for foster family"},
                    "orphan_category_id": {"type": "string", "description": "Orphan category ID"},
                    "full_name_ar": {"type": "string", "description": "Full Arabic name (رباعي)"},
                    "city": {"type": "string", "description": "City name"},
                },
                "required": ["phone", "case_type", "orphan_category_id", "full_name_ar", "city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file",
            "description": "Get a beneficiary's full file including all sections.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID (e.g. BEN-1001)"},
                },
                "required": ["beneficiary_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_section",
            "description": "Update one section of the beneficiary's data form. Each section has specific fields. Use get_completeness first to know which sections are missing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID"},
                    "section_id": {
                        "type": "string",
                        "description": "Section ID: SEC-BASIC, SEC-EXTRA, SEC-JOIN, SEC-BANK, SEC-CONTACT, SEC-EDU, SEC-HOUSING, SEC-HEALTH",
                    },
                    "values": {"type": "object", "description": "Key-value pairs of fields to update"},
                },
                "required": ["beneficiary_id", "section_id", "values"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_completeness",
            "description": "Check what is still missing from a beneficiary's file. Returns missing fields, missing documents, and completion percentage. Use this to know what to ask for next.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID"},
                },
                "required": ["beneficiary_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_file",
            "description": "Submit the beneficiary file for review. Only works when file is 100% complete. Use after get_completeness shows ready_to_submit=true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID"},
                },
                "required": ["beneficiary_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_dependent",
            "description": "Add a household member (تابع) to the beneficiary's file. Household size affects the need assessment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID"},
                    "name_ar": {"type": "string", "description": "Dependent's Arabic name"},
                    "relationship_ar": {"type": "string", "description": "Relationship (الزوجة، الابن، الابنة، الأخ، الأخت)"},
                    "birth_date": {"type": "string", "description": "Birth date (YYYY-MM-DD), optional"},
                    "education_stage": {"type": "string", "description": "Education stage (ابتدائي، متوسط، ثانوي، جامعي), optional"},
                    "has_special_needs": {"type": "boolean", "description": "Whether the dependent has special needs"},
                },
                "required": ["beneficiary_id", "name_ar", "relationship_ar"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dependents",
            "description": "List all dependents/household members for a beneficiary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID"},
                },
                "required": ["beneficiary_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_document",
            "description": "Update the status of a document in the checklist. Use 'uploaded' if user uploaded it, 'not_available' if they don't have it, 'ineligible' if it doesn't apply.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID"},
                    "document_type_id": {
                        "type": "string",
                        "description": "Document type ID (e.g. DOC-NATID, DOC-SALARY, DOC-RENT, DOC-BANK, DOC-PHOTO)",
                    },
                    "status": {
                        "type": "string",
                        "description": "Status: uploaded, not_available, ineligible, missing, rejected, verified",
                    },
                },
                "required": ["beneficiary_id", "document_type_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_profile",
            "description": "Get the beneficiary's financial profile including income, obligations, and need score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID"},
                },
                "required": ["beneficiary_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_obligation",
            "description": "Add a monthly financial obligation (إيجار، قرض، صرف عائلي). These are deducted when calculating the need score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID"},
                    "type_id": {
                        "type": "string",
                        "description": "Type: OB-RENT (إيجار), OB-LOAN (قرض), OB-MAINTENANCE (صيانة), OB-EDUCATION (تعليم)",
                    },
                    "monthly_sar": {"type": "number", "description": "Monthly amount in SAR"},
                    "documented": {"type": "boolean", "description": "Whether the obligation is documented (default true)"},
                },
                "required": ["beneficiary_id", "type_id", "monthly_sar"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_person_cost",
            "description": "Add a per-person monthly living cost (مصاريف شخصية). These affect the need score calculation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID"},
                    "type_id": {
                        "type": "string",
                        "description": "Type: PC-FOOD (طعام), PC-HEALTH (صحة), PC-EDUCATION (تعليم), PC-TRANSPORT (مواصلات)",
                    },
                    "monthly_sar": {"type": "number", "description": "Monthly amount in SAR"},
                },
                "required": ["beneficiary_id", "type_id", "monthly_sar"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_request_types",
            "description": "Search for the right support request type using free text. Maps natural language like 'محتاج مساعدة بالإيجار' to the correct program and request type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Free text search (Arabic or English)"},
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_support_request",
            "description": "Submit a support request (طلب دعم). Only works if the beneficiary file is approved. Ask for a detailed case description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID"},
                    "request_type_id": {"type": "string", "description": "Request type ID from search_request_types"},
                    "case_description_ar": {"type": "string", "description": "Detailed Arabic description of the case"},
                    "requested_amount_sar": {"type": "number", "description": "Requested amount in SAR if applicable"},
                },
                "required": ["beneficiary_id", "request_type_id", "case_description_ar"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_support_request",
            "description": "Get details of a support request including casework status and committee decision.",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "Support request ID (e.g. SR-25001)"},
                },
                "required": ["request_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_request_detail",
            "description": "Append more detail to an existing support request. Never overwrites existing detail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {"type": "string", "description": "Support request ID"},
                    "additional_detail_ar": {"type": "string", "description": "Additional detail in Arabic"},
                },
                "required": ["request_id", "additional_detail_ar"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_faqs",
            "description": "Search the beneficiary FAQ. Use this BEFORE improvising an answer about procedures, documents, or how-to questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Search query in Arabic or English"},
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_ticket",
            "description": "Open a CRM ticket when you cannot resolve the query yourself or when a human must act. Use for escalations and complex issues.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject_ar": {"type": "string", "description": "Ticket subject in Arabic"},
                    "channel": {"type": "string", "description": "Channel: whatsapp, call, portal"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID if known"},
                    "department_id": {
                        "type": "string",
                        "description": "Department: DEP-BEN (خدمات المستفيدين), DEP-FIN (المالية), DEP-IT (تقنية), DEP-KAF (الكفالات), DEP-EVT (الفعاليات), DEP-RES (البحث الاجتماعي)",
                    },
                    "priority": {"type": "string", "description": "Priority: low, medium, high"},
                    "first_message_ar": {"type": "string", "description": "First message from the user"},
                },
                "required": ["subject_ar", "channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_beneficiary_history",
            "description": "Get the complete 360-degree record of a beneficiary: file, household, finances, requests, disbursements, tickets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "beneficiary_id": {"type": "string", "description": "Beneficiary ID"},
                },
                "required": ["beneficiary_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_programs",
            "description": "List all association programs available for support requests.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_flow",
            "description": "Cancel the current conversation flow and reset. Use when user says cancel/stop/nevermind or when they want to start over.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]
