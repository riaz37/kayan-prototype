"""
Use case 1 — Registration & the beneficiary file (رحلة تسجيل المستفيد).
Mirrors the client's guide: account creation by phone + OTP, the 10-section
data form, dependents, documents (incl. "لا يوجد" / "عدم الاهلية"), and the
financial profile used for the needs assessment.
"""
import json
import random
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend import store as db

router = APIRouter()
T = "1 · التسجيل وملف المستفيد | Registration & Beneficiary File"


# ============================================================ account / OTP
class PhoneIn(BaseModel):
    phone: str = Field(..., examples=["0501234567"], description="Saudi mobile, any format")


@router.post("/registration/check-phone", tags=[T],
             summary="Check if a phone number is already registered",
             description="Mirrors the portal message 'رقم الجوال مسجل مسبقا'. Returns whether an "
                         "account exists so the agent can route the caller to login instead of "
                         "re-registering. Always call this before starting a new registration.")
def check_phone(body: PhoneIn):
    p = db.norm_phone(body.phone)
    acc = db.accounts.get(p)
    b = db.beneficiary_by_phone(p)
    if acc or b:
        return {
            "registered": True, "phone": p,
            "beneficiary_id": (b or {}).get("id"),
            "file_no": (b or {}).get("file_no"),
            "file_status": (b or {}).get("status"),
            "reply_ar": "رقم الجوال مسجل مسبقا لديكم حساب سابق. الرجاء تسجيل الدخول مباشرة. "
                        "وان نسيتم كلمة المرور تواصلوا مع خدمات المستفيدين على 0506094154.",
        }
    return {"registered": False, "phone": p,
            "reply_ar": "الرقم غير مسجل. يمكننا البدء بانشاء حساب جديد. سارسل لكم رمز التحقق."}


@router.post("/registration/send-otp", tags=[T],
             summary="Send an OTP verification code",
             description="Sends the رمز التحقق by SMS to start account creation or password reset. "
                         "Code is returned in the response for prototype testing only.")
def send_otp(body: PhoneIn):
    p = db.norm_phone(body.phone)
    code = f"{random.randint(1000, 9999)}"
    db.otp_codes[p] = {"code": code, "expires_at": db.now_iso(), "attempts": 0}
    msg = db.render_template("TPL-OTP", code=code)
    db.send_notification("sms", p, msg, kind="otp")
    return {"sent": True, "phone": p, "debug_code": code,
            "reply_ar": "تم ارسال رمز التحقق الى جوالكم. قد يتاخر وصول الرمز احيانا."}


class VerifyOtpIn(BaseModel):
    phone: str = Field(..., examples=["0501234567"])
    code: str = Field(..., examples=["1234"])


@router.post("/registration/verify-otp", tags=[T],
             summary="Verify the OTP code",
             description="Verifies the رمز التحقق. On success the caller may create the account.")
def verify_otp(body: VerifyOtpIn):
    p = db.norm_phone(body.phone)
    rec = db.otp_codes.get(p)
    if not rec:
        raise HTTPException(404, "No OTP was issued for this number")
    rec["attempts"] += 1
    if rec["attempts"] > 5:
        raise HTTPException(429, "Too many attempts, request a new code")
    if body.code != rec["code"]:
        return {"verified": False, "reply_ar": "رمز التحقق غير صحيح. حاولوا مرة اخرى."}
    return {"verified": True, "phone": p, "reply_ar": "تم التحقق بنجاح."}


# ============================================================ eligibility gate
class EligibilityIn(BaseModel):
    orphan_category_id: str = Field(..., examples=["OC-UNK"],
                                    description="From GET /reference/orphan-categories")


@router.post("/registration/check-eligibility", tags=[T],
             summary="Check eligibility for Kayan's served category",
             description="Kayan serves orphans with special circumstances (مجهولي الابوين). "
                         "The bot must confirm the category before collecting a full file, exactly "
                         "as the officer does in the guide's WhatsApp sample. Non-eligible callers "
                         "are politely referred elsewhere.")
def check_eligibility(body: EligibilityIn):
    cat = db.by_id["orphan_category"].get(body.orphan_category_id)
    if not cat:
        raise HTTPException(404, "Unknown orphan category")
    if cat["eligible"]:
        return {"eligible": True, "category_ar": cat["name_ar"],
                "reply_ar": f"شكرا لتاكيدكم. فئة {cat['name_ar']} ضمن الفئات التي تخدمها جمعية كيان. "
                            "نكمل معكم اجراءات التسجيل."}
    return {"eligible": False, "category_ar": cat["name_ar"],
            "reply_ar": "نشكر تواصلكم مع جمعية كيان. خدماتنا مخصصة للايتام ذوي الظروف الخاصة "
                        "(مجهولي الابوين)، ويسعدنا ارشادكم للجهات المختصة بفئتكم.",
            "referral_note_ar": cat.get("notes_ar")}


# ============================================================ create file
class CreateFileIn(BaseModel):
    phone: str = Field(..., examples=["0555550001"])
    case_type: str = Field(..., examples=["CT-IND"], description="CT-IND or CT-FOSTER")
    orphan_category_id: str = Field(..., examples=["OC-UNK"])
    full_name_ar: str = Field(..., examples=["محمد بن عبدالله القحطاني"],
                              description="الاسم الرباعي كما في الهوية")
    national_id: Optional[str] = Field(None, examples=["1012345678"])
    city: Optional[str] = Field(None, examples=["الرياض"])


@router.post("/beneficiary/create-file", tags=[T],
             summary="Create a new beneficiary file",
             description="Creates the file (تسجيل مستفيد جديد or تسجيل اسرة بديلة) in draft state "
                         "with only what the caller gave so far. Remaining sections are filled "
                         "progressively — call /beneficiary/{id}/completeness to see what is still needed.")
def create_file(body: CreateFileIn):
    p = db.norm_phone(body.phone)
    if db.beneficiary_by_phone(p):
        raise HTTPException(409, "رقم الجوال مسجل مسبقا — this phone already has a file")
    ct = next((c for c in db.case_types if c["id"] == body.case_type), None)
    if not ct:
        raise HTTPException(404, "Unknown case type")
    cat = db.by_id["orphan_category"].get(body.orphan_category_id)
    if not cat:
        raise HTTPException(404, "Unknown orphan category")
    if not cat["eligible"]:
        raise HTTPException(409, "Category is not served by Kayan — refer the caller instead")

    bid = db.next_id("ben", "BEN-")
    file_no = db.next_id("file", "KY-")
    b = {
        "id": bid, "file_no": file_no, "case_type": body.case_type, "status": "draft",
        "orphan_category": body.orphan_category_id, "eligibility_verified": True,
        "created_at": db.now_iso(), "updated_at": db.now_iso(),
        "full_name_ar": body.full_name_ar, "phone": p, "city": body.city,
        "sections": {
            "SEC-BASIC": {"full_name_ar": body.full_name_ar, "national_id": body.national_id,
                          "birth_date": None, "gender": None, "marital_status": None,
                          "orphan_category_id": body.orphan_category_id, "nationality": None},
            "SEC-EXTRA": {"dependents_count": 0, "income_sources": [],
                          "has_social_security": None, "has_citizen_account": None},
            "SEC-JOIN": {"join_reason": None, "referral_source": None, "previous_support": None},
            "SEC-BANK": {"bank_name": None, "iban": None, "account_holder_name": None},
            "SEC-CONTACT": {"mobile": p, "alt_mobile": None, "email": None, "whatsapp": p},
            "SEC-EDU": {"education_level": None, "employment_status": None,
                        "employer": None, "monthly_salary": None},
            "SEC-HOUSING": {"city": body.city, "district": None, "housing_type": None,
                            "ownership_proof_type": None, "rooms": None,
                            "monthly_rent": None, "monthly_bills": None},
            "SEC-HEALTH": {"chronic_conditions": None, "disability": None,
                           "has_health_insurance": None, "monthly_medication_cost": None},
        },
    }
    db.insert_beneficiary(b)
    db.insert_account(p, bid)

    # seed the document checklist for this case type
    for dt in db.document_types:
        if body.case_type in dt["required_for"]:
            db.insert_document({
                "id": db.next_id("doc", "DOC-"), "beneficiary_id": bid,
                "document_type_id": dt["id"], "name_ar": dt["name_ar"],
                "mandatory": dt["mandatory"], "status": "missing",
                "created_at": db.now_iso(),
            })
    db.insert_financial_profile({
        "id": f"FP-{bid}", "beneficiary_id": bid,
        "monthly_income": 0.0, "monthly_expenses": 0.0,
        "obligations": [], "person_costs": [], "need_score": 0.0,
        "created_at": db.now_iso(),
    })
    msg = db.render_template("TPL-REG-OK", file_no=file_no)
    db.send_notification("whatsapp", p, msg, kind="registration")
    return {"beneficiary_id": bid, "file_no": file_no, "status": "draft",
            "case_type_ar": ct["name_ar"],
            "next_step_ar": "استكمال بقية اقسام النموذج والمرفقات",
            "reply_ar": f"تم انشاء ملفكم برقم {file_no}. سنكمل معكم بقية البيانات خطوة بخطوة."}


# ============================================================ sections
@router.get("/reference/form-sections", tags=[T],
            summary="List the 10 data form sections",
            description="Returns the sections of نموذج البيانات in order, with their field names — "
                        "use this to walk the caller through the form.")
def list_sections():
    return {"count": len(db.form_sections), "sections": db.form_sections}


@router.get("/reference/orphan-categories", tags=[T],
            summary="List orphan categories and which are served",
            description="Categories used for the eligibility gate.")
def list_categories():
    return {"categories": db.orphan_categories}


@router.get("/reference/case-types", tags=[T],
            summary="List file types (new beneficiary vs foster family)",
            description="تسجيل مستفيد جديد for an independent beneficiary over 18; "
                        "تسجيل اسرة بديلة for a host family caring for an orphan.")
def list_case_types():
    return {"case_types": db.case_types}


@router.get("/reference/housing-proofs", tags=[T],
            summary="List accepted housing ownership proofs",
            description="What counts as اثبات ملكية السكن.")
def list_housing_proofs():
    return {"proofs": db.housing_proofs}


@router.get("/beneficiary/{beneficiary_id}", tags=[T],
            summary="Get a beneficiary file",
            description="Full file with all sections. Use for context before answering questions.")
def get_file(beneficiary_id: str):
    b = db.get_beneficiary(beneficiary_id)
    if not b:
        raise HTTPException(404, "Beneficiary not found")
    return b


class UpdateSectionIn(BaseModel):
    values: Dict[str, Any] = Field(..., examples=[{"education_level": "بكالوريوس",
                                                   "employment_status": "لا يعمل"}])


@router.patch("/beneficiary/{beneficiary_id}/section/{section_id}", tags=[T],
              summary="Update one section of the data form",
              description="Writes the values the caller dictated into a section (e.g. SEC-HOUSING). "
                          "Only known fields for that section are accepted. Call completeness after "
                          "to see what is still missing.")
def update_section(beneficiary_id: str, section_id: str, body: UpdateSectionIn):
    b = db.get_beneficiary(beneficiary_id)
    if not b:
        raise HTTPException(404, "Beneficiary not found")
    sec = db.by_id["form_section"].get(section_id)
    if not sec:
        raise HTTPException(404, "Unknown section")
    allowed = set(sec["fields"])
    unknown = [k for k in body.values if k not in allowed]
    if unknown:
        raise HTTPException(422, f"Fields not in {section_id}: {unknown}. Allowed: {sorted(allowed)}")
    b["sections"].setdefault(section_id, {}).update(body.values)

    # keep the financial profile in sync when income-bearing fields change
    if section_id in ("SEC-EXTRA", "SEC-EDU"):
        f = db.finance_for(beneficiary_id)
        if f:
            srcs = b["sections"].get("SEC-EXTRA", {}).get("income_sources") or []
            salary = b["sections"].get("SEC-EDU", {}).get("monthly_salary") or 0
            other = sum(s.get("amount_sar", 0) for s in srcs
                        if s.get("type") != "راتب")
            f["income_breakdown"] = srcs
            f["monthly_income_sar"] = round(float(salary) + float(other), 2)
            _recalc(f)

    return {"beneficiary_id": beneficiary_id, "section_id": section_id,
            "section_ar": sec["name_ar"], "updated": body.values,
            "completeness": db.file_completeness(beneficiary_id)}


@router.get("/beneficiary/{beneficiary_id}/completeness", tags=[T],
            summary="What is still missing from the file",
            description="THE KEY TOOL for follow-up. Returns completion %, the exact missing fields "
                        "(with their section) and missing mandatory documents, plus whether the file "
                        "is ready to submit. Use it to ask the beneficiary for precisely what is "
                        "still needed instead of asking generically.")
def completeness(beneficiary_id: str):
    c = db.file_completeness(beneficiary_id)
    if not c:
        raise HTTPException(404, "Beneficiary not found")
    parts = []
    if c["missing_fields"]:
        names = sorted({m["section_ar"] for m in c["missing_fields"]})
        parts.append("اقسام ناقصة: " + "، ".join(names))
    if c["missing_documents"]:
        parts.append("مستندات مطلوبة: " + "، ".join(d["name_ar"] for d in c["missing_documents"]))
    c["reply_ar"] = (f"ملفكم مكتمل بنسبة {c['completion_pct']}%. " + ". ".join(parts)) if parts \
        else "ملفكم مكتمل ويمكن رفعه للدراسة."
    return c


@router.post("/beneficiary/{beneficiary_id}/submit", tags=[T],
             summary="Submit the file for review (اضافة سجل)",
             description="Submits the completed file to the association for review. Blocked with 409 "
                         "if mandatory fields or documents are still missing — surface the gaps to "
                         "the caller rather than retrying.")
def submit_file(beneficiary_id: str):
    b = db.get_beneficiary(beneficiary_id)
    if not b:
        raise HTTPException(404, "Beneficiary not found")
    c = db.file_completeness(beneficiary_id)
    if not c["ready_to_submit"]:
        raise HTTPException(409, {
            "message": "File is incomplete",
            "missing_fields": c["missing_fields"],
            "missing_documents": c["missing_documents"],
            "reply_ar": "لا يمكن رفع الملف قبل استكمال البيانات والمستندات المطلوبة.",
        })
    b["status"] = "submitted"
    return {"beneficiary_id": beneficiary_id, "status": "submitted",
            "reply_ar": "تم رفع ملفكم بنجاح. سيتم التواصل معكم لاستكمال اجراءات دراسة الحالة. "
                        "علما بان التسجيل في النظام لا يعني قبول الطلب."}


# ============================================================ dependents
class DependentIn(BaseModel):
    name_ar: str = Field(..., examples=["سارة القحطاني"])
    relationship_ar: str = Field(..., examples=["ابنة"],
                                 description="الزوج/الزوجة، ابن، ابنة، اخ، اخت، الام الحاضنة، اخ يتيم ذو ظروف خاصة")
    birth_date: Optional[str] = Field(None, examples=["2015-04-01"])
    gender: Optional[str] = Field(None, examples=["female"])
    education_stage: Optional[str] = Field(None, examples=["ابتدائي"])
    has_special_needs: bool = False


@router.post("/beneficiary/{beneficiary_id}/dependents", tags=[T],
             summary="Add a dependent (اضافة تابع)",
             description="Adds a household member. Everyone living permanently in the home must be "
                         "added — spouse, children, siblings, foster mother, orphan siblings — because "
                         "the household size drives the needs assessment.")
def add_dependent(beneficiary_id: str, body: DependentIn):
    b = db.get_beneficiary(beneficiary_id)
    if not b:
        raise HTTPException(404, "Beneficiary not found")
    d = {"id": db.next_id("dep", "DEP-"), "beneficiary_id": beneficiary_id,
         "name_ar": body.name_ar, "relationship": body.relationship_ar,
         "birth_date": body.birth_date, "gender": body.gender,
         "education": body.education_stage,
         "special_needs": 1 if body.has_special_needs else 0,
         "created_at": db.now_iso()}
    db.insert_dependent(d)
    n = len(db.deps_for(beneficiary_id))
    b["sections"]["SEC-EXTRA"]["dependents_count"] = n
    f = db.finance_for(beneficiary_id)
    if f:
        f["household_size"] = 1 + n
    return {"dependent": d, "dependents_count": n,
            "reply_ar": f"تمت اضافة {body.name_ar} ضمن التابعين. اجمالي التابعين {n}."}


@router.get("/beneficiary/{beneficiary_id}/dependents", tags=[T],
            summary="List dependents / household",
            description="All household members with household size.")
def list_dependents(beneficiary_id: str):
    if not db.get_beneficiary(beneficiary_id):
        raise HTTPException(404, "Beneficiary not found")
    ds = db.deps_for(beneficiary_id)
    return {"beneficiary_id": beneficiary_id, "count": len(ds),
            "household_size": len(ds) + 1, "dependents": ds}


# ============================================================ documents
@router.get("/beneficiary/{beneficiary_id}/documents", tags=[T],
            summary="Document checklist and status",
            description="The المرفقات checklist for this file with each document's status "
                        "(missing / uploaded / verified / rejected / not_available / ineligible).")
def list_documents(beneficiary_id: str):
    if not db.get_beneficiary(beneficiary_id):
        raise HTTPException(404, "Beneficiary not found")
    ds = db.docs_for(beneficiary_id)
    return {"beneficiary_id": beneficiary_id, "count": len(ds), "documents": ds,
            "missing_mandatory": [d["name_ar"] for d in ds
                                  if d["mandatory"] and d["status"] in ("missing", "rejected")]}


class DocStatusIn(BaseModel):
    status: str = Field(..., examples=["uploaded"],
                        description="uploaded | verified | rejected | not_available | ineligible")
    note_ar: Optional[str] = Field(None, examples=["لا يوجد"])


@router.patch("/beneficiary/{beneficiary_id}/documents/{document_type_id}", tags=[T],
              summary="Record a document as uploaded / not available / ineligible",
              description="Sets a document's status. Per the guide: if the document does not apply "
                          "(social security, citizen account) mark it 'ineligible' (عدم الاهلية); if it "
                          "is unavailable (salary certificate) mark it 'not_available' (لا يوجد).")
def set_document(beneficiary_id: str, document_type_id: str, body: DocStatusIn):
    if body.status not in ("uploaded", "verified", "rejected", "not_available", "ineligible", "missing"):
        raise HTTPException(422, "Invalid status")
    conn = db._get_conn()
    d_row = conn.execute(
        "SELECT * FROM documents WHERE beneficiary_id = ? AND document_type_id = ?",
        (beneficiary_id, document_type_id)).fetchone()
    if not d_row:
        raise HTTPException(404, "Document not on this file's checklist")
    d = dict(d_row)
    dt = db.by_id["document_type"].get(document_type_id, {})
    if body.status == "not_available" and not dt.get("na_allowed"):
        raise HTTPException(409, f"{dt.get('name_ar')} لا يقبل حالة لا يوجد — يجب رفع المستند")
    if body.status == "ineligible" and not dt.get("ineligible_allowed"):
        raise HTTPException(409, f"{dt.get('name_ar')} لا يقبل حالة عدم الاهلية — يجب رفع المستند")
    conn.execute("UPDATE documents SET status=?, updated_at=? WHERE id=?",
                (body.status, db.now_iso(), d["id"]))
    conn.commit()
    d["status"] = body.status
    return {"document": d, "completeness": db.file_completeness(beneficiary_id)}


# ============================================================ financial profile
@router.get("/beneficiary/{beneficiary_id}/financial-profile", tags=[T],
            summary="Get the financial profile & need score",
            description="Income, documented monthly obligations (الفواتير الشهرية), per-person living "
                        "costs (التكاليف الشهرية للفرد), net income, per-capita income and the derived "
                        "need score used for prioritization.")
def get_finance(beneficiary_id: str):
    f = db.finance_for(beneficiary_id)
    if not f:
        raise HTTPException(404, "Beneficiary not found")
    return f


class ObligationIn(BaseModel):
    type_id: str = Field(..., examples=["OB-RENT"], description="From /reference/obligation-types")
    monthly_sar: float = Field(..., examples=[1500.0])
    documented: bool = Field(True, description="Documented in SIMAH / Najiz / a contract")


@router.post("/beneficiary/{beneficiary_id}/obligations", tags=[T],
             summary="Add a documented monthly obligation",
             description="Adds to الفواتير الشهرية and recalculates net income, per-capita income and "
                         "the need score.")
def add_obligation(beneficiary_id: str, body: ObligationIn):
    f = db.finance_for(beneficiary_id)
    if not f:
        raise HTTPException(404, "Beneficiary not found")
    ot = next((o for o in db.obligation_types if o["id"] == body.type_id), None)
    if not ot:
        raise HTTPException(404, "Unknown obligation type")
    obligations = json.loads(f.get("obligations", "[]"))
    obligations.append({"type_id": ot["id"], "name_ar": ot["name_ar"],
                       "monthly_sar": body.monthly_sar, "documented": body.documented})
    conn = db._get_conn()
    conn.execute("UPDATE financial_profiles SET obligations=? WHERE id=?",
                (json.dumps(obligations, ensure_ascii=False), f["id"]))
    conn.commit()
    f["obligations"] = obligations
    return _recalc(f)


class CostIn(BaseModel):
    type_id: str = Field(..., examples=["PC-GROCERY"], description="From /reference/person-cost-types")
    monthly_sar: float = Field(..., examples=[1200.0])


@router.post("/beneficiary/{beneficiary_id}/person-costs", tags=[T],
             summary="Add a per-person monthly living cost",
             description="Adds to التكاليف الشهرية للفرد. Luxury/entertainment costs (PC-LUXURY) are "
                         "rejected with 409 — they are not counted per the guide.")
def add_cost(beneficiary_id: str, body: CostIn):
    f = db.finance_for(beneficiary_id)
    if not f:
        raise HTTPException(404, "Beneficiary not found")
    ct = next((c for c in db.person_cost_types if c["id"] == body.type_id), None)
    if not ct:
        raise HTTPException(404, "Unknown cost type")
    if not ct["counted"]:
        raise HTTPException(409, "لا يتم احتساب المصاريف الكمالية او الترفيهية ضمن الفواتير المعتمدة")
    person_costs = json.loads(f.get("person_costs", "[]"))
    person_costs.append({"type_id": ct["id"], "name_ar": ct["name_ar"],
                        "monthly_sar": body.monthly_sar})
    conn = db._get_conn()
    conn.execute("UPDATE financial_profiles SET person_costs=? WHERE id=?",
                (json.dumps(person_costs, ensure_ascii=False), f["id"]))
    conn.commit()
    f["person_costs"] = person_costs
    return _recalc(f)


def _recalc(f):
    obligations = json.loads(f.get("obligations", "[]"))
    person_costs = json.loads(f.get("person_costs", "[]"))
    total_obligations = round(sum(o["monthly_sar"] for o in obligations), 2)
    total_person_costs = round(sum(c["monthly_sar"] for c in person_costs), 2)
    net_monthly = round(f.get("monthly_income", 0) - total_obligations - total_person_costs, 2)
    hh = max(1, f.get("household_size", 1))
    per_capita = round(net_monthly / hh, 2)
    need_score = max(0, min(100, round(100 - (per_capita / 15), 1)))
    conn = db._get_conn()
    conn.execute("""UPDATE financial_profiles SET
        obligations=?, person_costs=?, need_score=? WHERE id=?""",
        (json.dumps(obligations, ensure_ascii=False),
         json.dumps(person_costs, ensure_ascii=False),
         need_score, f["id"]))
    conn.commit()
    f["obligations"] = obligations
    f["person_costs"] = person_costs
    f["need_score"] = need_score
    return f


@router.get("/reference/obligation-types", tags=[T],
            summary="List monthly obligation types",
            description="What counts as الفواتير الشهرية.")
def list_obligations():
    return {"types": db.obligation_types}


@router.get("/reference/person-cost-types", tags=[T],
            summary="List per-person monthly cost types",
            description="What counts (and what does not) as التكاليف الشهرية للفرد.")
def list_costs():
    return {"types": db.person_cost_types}


# ============================================================ FAQ
@router.get("/faqs/search", tags=[T],
            summary="Search the beneficiary FAQ",
            description="Keyword search over the FAQ built from the association's guide (registration, "
                        "eligibility, dependents, housing, finances, documents, requests, decisions). "
                        "Use this before improvising an answer.")
def search_faqs(q: str = Query(..., examples=["مشهد الضمان"]),
                lang: str = Query("ar", examples=["ar", "en"]),
                limit: int = Query(3, ge=1, le=10)):
    ql = q.lower().strip()
    scored = []
    for f in db.faqs:
        hay = " ".join([f["q_ar"], f["a_ar"], f["q_en"], f["a_en"], f["category"]]).lower()
        score = sum(1 for tok in ql.split() if tok in hay)
        if ql in hay:
            score += 3
        if score:
            scored.append((score, f))
    scored.sort(key=lambda x: -x[0])
    hits = [f for _, f in scored[:limit]] or db.faqs[:limit]
    return {"query": q, "count": len(hits),
            "results": [{"id": f["id"], "category": f["category"],
                         "question": f["q_ar"] if lang == "ar" else f["q_en"],
                         "answer": f["a_ar"] if lang == "ar" else f["a_en"]} for f in hits]}
