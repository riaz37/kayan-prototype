"""
Tool definitions and handlers for the Gemini agent.
Each tool maps to a backend API endpoint. Tool declarations follow the
Gemini function calling schema. Handlers make HTTP calls to the backend.
"""
from typing import Optional
import httpx
from google.genai import types
from agent.config import settings

BACKEND = settings.backend_url


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


def handle_send_otp(phone: str) -> dict:
    return _post("/registration/send-otp", {"phone": phone})


def handle_verify_otp(phone: str, code: str) -> dict:
    return _post("/registration/verify-otp", {"phone": phone, "code": code})


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
                         is_orphan: bool = False, has_special_needs: bool = False) -> dict:
    return _post(f"/beneficiary/{beneficiary_id}/dependents", {
        "name_ar": name_ar, "relationship_ar": relationship_ar,
        "is_orphan": is_orphan, "has_special_needs": has_special_needs,
    })


def handle_list_dependents(beneficiary_id: str) -> dict:
    return _get(f"/beneficiary/{beneficiary_id}/dependents")


def handle_update_document(beneficiary_id: str, document_type_id: str, status: str) -> dict:
    return _patch(f"/beneficiary/{beneficiary_id}/documents/{document_type_id}", {"status": status})


def handle_get_financial_profile(beneficiary_id: str) -> dict:
    return _get(f"/beneficiary/{beneficiary_id}/financial-profile")


def handle_add_obligation(beneficiary_id: str, obligation_type_id: str,
                          amount_sar: float, description_ar: str = "") -> dict:
    return _post(f"/beneficiary/{beneficiary_id}/obligations", {
        "obligation_type_id": obligation_type_id,
        "amount_sar": amount_sar, "description_ar": description_ar,
    })


def handle_add_person_cost(beneficiary_id: str, person_cost_type_id: str,
                           amount_sar: float, description_ar: str = "") -> dict:
    return _post(f"/beneficiary/{beneficiary_id}/person-costs", {
        "person_cost_type_id": person_cost_type_id,
        "amount_sar": amount_sar, "description_ar": description_ar,
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


def handle_add_request_detail(request_id: str, detail_ar: str) -> dict:
    return _patch(f"/support-requests/{request_id}/add-detail", {"detail_ar": detail_ar})


def handle_search_faqs(q: str) -> dict:
    return _get("/faqs/search", {"q": q})


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


def handle_send_whatsapp(to: str, body_ar: str) -> dict:
    return _post("/whatsapp/send", None)
    # Note: /whatsapp/send uses query params in the mock, but we'll
    # handle this via the whatsapp.py sender directly


def handle_send_template(to: str, template_id: str, params: dict) -> dict:
    return _post("/whatsapp/send-template", {
        "to": to, "template_id": template_id, "params": params,
    })


# ============================================================ Tool Declarations (Gemini schema)

TOOL_DECLARATIONS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="check_phone",
            description="Check if a phone number is already registered in the system. Use this first when a new user contacts us.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "phone": types.Schema(type=types.Type.STRING, description="Phone number (e.g. 0501234567)"),
                },
                required=["phone"],
            ),
        ),
        types.FunctionDeclaration(
            name="send_otp",
            description="Send an OTP verification code to a phone number. Use after confirming the user wants to register.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "phone": types.Schema(type=types.Type.STRING, description="Phone number"),
                },
                required=["phone"],
            ),
        ),
        types.FunctionDeclaration(
            name="verify_otp",
            description="Verify the OTP code the user received. Use after they provide the code.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "phone": types.Schema(type=types.Type.STRING, description="Phone number"),
                    "code": types.Schema(type=types.Type.STRING, description="The OTP code received"),
                },
                required=["phone", "code"],
            ),
        ),
        types.FunctionDeclaration(
            name="check_eligibility",
            description="Check if a user is eligible for Kayan's services. Kayan serves الأيتام ذوو الظروف الخاصة (مجهولو الأبوين). Always ask this before creating a file.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "orphan_category_id": types.Schema(
                        type=types.Type.STRING,
                        description="Orphan category: OC-UNK (مجهول الأبوين), OC-MARTYR (شهيد), OC-DISABLED (معاق), OC-PRISONER (سجين), OC-DIVERGENT (مفقود)",
                    ),
                },
                required=["orphan_category_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="create_file",
            description="Create a new beneficiary file. Use after verifying identity and eligibility.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "phone": types.Schema(type=types.Type.STRING, description="Phone number"),
                    "case_type": types.Schema(type=types.Type.STRING, description="CT-IND for independent, CT-FOSTER for foster family"),
                    "orphan_category_id": types.Schema(type=types.Type.STRING, description="Orphan category ID"),
                    "full_name_ar": types.Schema(type=types.Type.STRING, description="Full Arabic name (رباعي)"),
                    "city": types.Schema(type=types.Type.STRING, description="City name"),
                },
                required=["phone", "case_type", "orphan_category_id", "full_name_ar", "city"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_file",
            description="Get a beneficiary's full file including all sections.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID (e.g. BEN-1001)"),
                },
                required=["beneficiary_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="update_section",
            description="Update one section of the beneficiary's data form. Each section has specific fields. Use get_completeness first to know which sections are missing.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID"),
                    "section_id": types.Schema(
                        type=types.Type.STRING,
                        description="Section ID: SEC-BASIC, SEC-EXTRA, SEC-JOIN, SEC-BANK, SEC-CONTACT, SEC-EDU, SEC-HOUSING, SEC-HEALTH",
                    ),
                    "values": types.Schema(type=types.Type.OBJECT, description="Key-value pairs of fields to update"),
                },
                required=["beneficiary_id", "section_id", "values"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_completeness",
            description="Check what is still missing from a beneficiary's file. Returns missing fields, missing documents, and completion percentage. Use this to know what to ask for next.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID"),
                },
                required=["beneficiary_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="submit_file",
            description="Submit the beneficiary file for review. Only works when file is 100% complete. Use after get_completeness shows ready_to_submit=true.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID"),
                },
                required=["beneficiary_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="add_dependent",
            description="Add a household member (تابع) to the beneficiary's file. Household size affects the need assessment.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID"),
                    "name_ar": types.Schema(type=types.Type.STRING, description="Dependent's Arabic name"),
                    "relationship_ar": types.Schema(type=types.Type.STRING, description="Relationship (الزوجة، الابن، الابنة، الأخ، الأخت)"),
                    "is_orphan": types.Schema(type=types.Type.BOOLEAN, description="Whether the dependent is an orphan"),
                    "has_special_needs": types.Schema(type=types.Type.BOOLEAN, description="Whether the dependent has special needs"),
                },
                required=["beneficiary_id", "name_ar", "relationship_ar"],
            ),
        ),
        types.FunctionDeclaration(
            name="list_dependents",
            description="List all dependents/household members for a beneficiary.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID"),
                },
                required=["beneficiary_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="update_document",
            description="Update the status of a document in the checklist. Use 'uploaded' if user uploaded it, 'not_available' if they don't have it, 'ineligible' if it doesn't apply.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID"),
                    "document_type_id": types.Schema(
                        type=types.Type.STRING,
                        description="Document type ID (e.g. DOC-NATID, DOC-SALARY, DOC-RENT, DOC-BANK, DOC-PHOTO)",
                    ),
                    "status": types.Schema(
                        type=types.Type.STRING,
                        description="Status: uploaded, not_available, ineligible, missing, rejected, verified",
                    ),
                },
                required=["beneficiary_id", "document_type_id", "status"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_financial_profile",
            description="Get the beneficiary's financial profile including income, obligations, and need score.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID"),
                },
                required=["beneficiary_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="add_obligation",
            description="Add a monthly financial obligation (إيجار، قرض، صرف عائلي). These are deducted when calculating the need score.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID"),
                    "obligation_type_id": types.Schema(
                        type=types.Type.STRING,
                        description="Type: OBL-RENT (إيجار), OBL-LOAN (قرض), OBL-MAINTENANCE (صيانة), OBL-EDUCATION (تعليم)",
                    ),
                    "amount_sar": types.Schema(type=types.Type.NUMBER, description="Monthly amount in SAR"),
                    "description_ar": types.Schema(type=types.Type.STRING, description="Optional description"),
                },
                required=["beneficiary_id", "obligation_type_id", "amount_sar"],
            ),
        ),
        types.FunctionDeclaration(
            name="add_person_cost",
            description="Add a per-person monthly living cost (مصاريف شخصية). These affect the need score calculation.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID"),
                    "person_cost_type_id": types.Schema(
                        type=types.Type.STRING,
                        description="Type: PC-FOOD (طعام), PC-HEALTH (صحة), PC-EDUCATION (تعليم), PC-TRANSPORT (مواصلات)",
                    ),
                    "amount_sar": types.Schema(type=types.Type.NUMBER, description="Monthly amount in SAR"),
                    "description_ar": types.Schema(type=types.Type.STRING, description="Optional description"),
                },
                required=["beneficiary_id", "person_cost_type_id", "amount_sar"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_request_types",
            description="Search for the right support request type using free text. Maps natural language like 'محتاج مساعدة بالإيجار' to the correct program and request type.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "q": types.Schema(type=types.Type.STRING, description="Free text search (Arabic or English)"),
                },
                required=["q"],
            ),
        ),
        types.FunctionDeclaration(
            name="create_support_request",
            description="Submit a support request (طلب دعم). Only works if the beneficiary file is approved. Ask for a detailed case description.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID"),
                    "request_type_id": types.Schema(type=types.Type.STRING, description="Request type ID from search_request_types"),
                    "case_description_ar": types.Schema(type=types.Type.STRING, description="Detailed Arabic description of the case"),
                    "requested_amount_sar": types.Schema(type=types.Type.NUMBER, description="Requested amount in SAR if applicable"),
                },
                required=["beneficiary_id", "request_type_id", "case_description_ar"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_support_request",
            description="Get details of a support request including casework status and committee decision.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "request_id": types.Schema(type=types.Type.STRING, description="Support request ID (e.g. SR-25001)"),
                },
                required=["request_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="add_request_detail",
            description="Append more detail to an existing support request. Never overwrites existing detail.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "request_id": types.Schema(type=types.Type.STRING, description="Support request ID"),
                    "detail_ar": types.Schema(type=types.Type.STRING, description="Additional detail in Arabic"),
                },
                required=["request_id", "detail_ar"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_faqs",
            description="Search the beneficiary FAQ. Use this BEFORE improvising an answer about procedures, documents, or how-to questions.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "q": types.Schema(type=types.Type.STRING, description="Search query in Arabic or English"),
                },
                required=["q"],
            ),
        ),
        types.FunctionDeclaration(
            name="create_ticket",
            description="Open a CRM ticket when you cannot resolve the query yourself or when a human must act. Use for escalations and complex issues.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "subject_ar": types.Schema(type=types.Type.STRING, description="Ticket subject in Arabic"),
                    "channel": types.Schema(type=types.Type.STRING, description="Channel: whatsapp, call, portal"),
                    "phone": types.Schema(type=types.Type.STRING, description="Phone number"),
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID if known"),
                    "department_id": types.Schema(
                        type=types.Type.STRING,
                        description="Department: DEP-BEN (خدمات المستفيدين), DEP-FIN (المالية), DEP-IT (تقنية), DEP-KAF (الكفالات), DEP-EVT (الفعاليات), DEP-RES (البحث الاجتماعي)",
                    ),
                    "priority": types.Schema(type=types.Type.STRING, description="Priority: low, medium, high"),
                    "first_message_ar": types.Schema(type=types.Type.STRING, description="First message from the user"),
                },
                required=["subject_ar", "channel"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_beneficiary_history",
            description="Get the complete 360-degree record of a beneficiary: file, household, finances, requests, disbursements, tickets.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "beneficiary_id": types.Schema(type=types.Type.STRING, description="Beneficiary ID"),
                },
                required=["beneficiary_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="list_programs",
            description="List all association programs available for support requests.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={}),
        ),
        types.FunctionDeclaration(
            name="send_template_message",
            description="Send an approved WhatsApp template message. Use this when the 24-hour session window has expired.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "to": types.Schema(type=types.Type.STRING, description="Recipient phone number"),
                    "template_id": types.Schema(
                        type=types.Type.STRING,
                        description="Template: TPL-OTP, TPL-REG-OK, TPL-DOCS, TPL-ACCEPT, TPL-DECLINE, TPL-VISIT, TPL-PAY",
                    ),
                    "params": types.Schema(type=types.Type.OBJECT, description="Template parameters as key-value pairs"),
                },
                required=["to", "template_id"],
            ),
        ),
    ]),
]


# ============================================================ Tool Router

TOOL_HANDLERS = {
    "check_phone": lambda **kw: handle_check_phone(**kw),
    "send_otp": lambda **kw: handle_send_otp(**kw),
    "verify_otp": lambda **kw: handle_verify_otp(**kw),
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
    "send_template_message": lambda **kw: handle_send_template(**kw),
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
