"""
Seed the database with realistic demo data for the Kayan prototype.

Every identifier written here comes from reference-data/, so the seeded rows
join correctly against programs, request types, departments, document types,
orphan categories and staff. (The previous version invented its own IDs —
CT-NEW, DEPT-SERVICES, DOC-NAT-ID, OC-SPEC — none of which existed, so the
console showed blank department names, blank request titles, and /reports
reported a null busiest-department.)

Deterministic by default: pass --seed N or set SEED_RANDOM=1 to vary.

Run: python backend/seed_production.py
"""
import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import store as db  # noqa: E402  (import after sys.path setup)

FIRST_NAMES_M = ["محمد", "عبدالله", "فهد", "خالد", "سعد", "عبدالرحمن", "سلطان", "ياسر", "عمر",
                 "احمد", "علي", "حسن", "يوسف", "ابراهيم", "مصطفى", "هاني", "راشد", "ماجد",
                 "طارق", "وليد", "نواف"]
FIRST_NAMES_F = ["فاطمة", "نورة", "سارة", "منى", "ريم", "هدى", "لينا", "دانا", "جنى", "رنا",
                 "مريم", "ياسمين", "لمى", "ندى", "سمر", "هند", "عبير", "اماني", "مها", "سلمى"]
LAST_NAMES = ["العتيبي", "الشمري", "القحطاني", "الحربي", "المطيري", "الدوسري", "الغامدي",
              "الرشيدي", "الزهراني", "العمري", "البلوي", "الخضيري", "السعدي", "الهاجري",
              "النعيمي", "المري", "الكعبي"]
CITIES = ["الرياض", "جدة", "مكة المكرمة", "المدينة المنورة", "الدمام", "الخبر", "الطائف",
          "بريدة", "الظهران", "الجبيل", "حائل", "ابها", "نجران", "الباحة", "عرعر", "سكاكا"]
DISTRICTS = ["حي السلام", "حي النزهة", "حي الملقا", "حي الياسمين", "حي النرجس", "حي العارض",
             "حي الراكة", "حي الحمراء"]
BANKS = ["مصرف الراجحي", "البنك الاهلي", "بنك الرياض", "مصرف الانماء", "البنك السعودي الفرنسي"]

RELATIONSHIPS = ["ابن", "ابنة", "الزوجة", "اخ", "اخت", "الام الحاضنة"]
EDU_STAGES = ["ابتدائي", "متوسط", "ثانوي", "جامعي", None]
EDU_LEVELS = ["ابتدائي", "متوسط", "ثانوي", "بكالوريوس"]
EMPLOYMENT = ["يعمل", "لا يعمل", "عمل حر", "متقاعد"]
HOUSING = ["ايجار", "ملك", "سكن عائلي", "سكن حكومي"]
MARITAL = ["اعزب", "متزوج", "مطلق", "ارمل"]

TICKET_SUBJECTS = [
    "سداد ايجار", "استفسار عن برنامج علم", "طلب زيارة ميدانية", "رقم الجوال مسجل مسبقا",
    "تاخر صرف المبلغ", "تحديث البيانات البنكية", "استفسار عن حالة التسجيل", "شكوى في الخدمة",
    "طلب توضيح", "مشكلة في تسجيل الدخول", "استفسار عن الدفعة القادمة",
]
INBOUND_MESSAGES = [
    "السلام عليكم، عندي استفسار بخصوص طلب الدعم",
    "مرحبا، حبيت استفسر عن حالة ملفي",
    "متى تنزل الدفعة القادمة؟",
    "احتاج مساعدة في استكمال المستندات",
]
OUTBOUND_MESSAGES = [
    "شكرا لتواصلكم، تم استلام طلبكم وجاري دراسته",
    "يرجى ارسال المستندات المطلوبة لاستكمال الملف",
    "تم تحويل طلبكم للقسم المختص وسيتم الرد خلال المدة المحددة",
]
CASE_NOTES = [
    "تمت المعاينة الميدانية وتم توثيق حالة المستفيد",
    "المستفيد يعاني من صعوبات اقتصادية حادة",
    "الاسرة بحاجة الى دعم مستمر وفق تقييم الباحث",
]
RECOMMENDATIONS = [
    "التوصية بالقبول ضمن السقف المعتمد نظرا للحالة الاجتماعية",
    "يحتاج المستفيد للدعم العاجل بسبب انقطاع مصدر الدخل",
    "الحالة تستحق الدعم وفقا لمعايير اللجنة",
]
CASE_DESCRIPTIONS = [
    "احتياج معيشي شهري لتغطية المصاريف الاساسية للاسرة",
    "المستفيد باحث عن عمل ويحتاج تاهيل ودورة تدريبية معتمدة",
    "الاسرة تواجه صعوبة في سداد الالتزام الحالي وتحتاج دعم عاجل",
    "المستفيد ملتحق بالدراسة ويحتاج تغطية الرسوم للفصل القادم",
    "حالة اجتماعية حرجة تتطلب تدخل عاجل من الجمعية",
]

TABLES_TO_CLEAR = [
    "ticket_messages", "tickets", "event_registrations", "events", "call_sessions",
    "whatsapp_sessions", "notifications", "payments", "disbursements", "enrollments",
    "committee_decisions", "case_studies", "support_requests", "documents",
    "financial_profiles", "dependents", "accounts", "sponsorships", "sponsors",
    "beneficiaries",
]


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(days_ago=0, jitter_hours=True):
    d = _utcnow() - timedelta(days=days_ago)
    if jitter_hours:
        d -= timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))
    return d.replace(microsecond=0).isoformat() + "Z"


def date_only(days_ago=0):
    return (_utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def birth_date(min_year=1960, max_year=2015):
    return f"{random.randint(min_year, max_year)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"


def phone_number(i):
    """Distinct, valid-looking Saudi mobile numbers — no collisions."""
    return f"05{5000000 + i * 137:07d}"


def seed_database(count=28):
    conn = db._get_conn()
    print(f"Seeding {db.DB_PATH}")

    for table in TABLES_TO_CLEAR:
        try:
            conn.execute(f"DELETE FROM {table}")
        except Exception:
            pass
    print(f"Cleared {len(TABLES_TO_CLEAR)} tables")

    eligible_categories = [c["id"] for c in db.orphan_categories if c["eligible"]]
    all_categories = [c["id"] for c in db.orphan_categories]
    case_type_ids = [c["id"] for c in db.case_types]
    department_ids = [d["id"] for d in db.departments]
    staff_ids = [s["id"] for s in db.staff]
    program_ids = [p["id"] for p in db.programs]

    # ---------------------------------------------------------------- files
    beneficiaries = []
    for i in range(count):
        bid = f"BEN-{1001 + i}"
        gender_m = random.random() < 0.5
        first = random.choice(FIRST_NAMES_M if gender_m else FIRST_NAMES_F)
        full_name = f"{first} {random.choice(LAST_NAMES)}"
        phone = db.norm_phone(phone_number(i))
        city = random.choice(CITIES)
        case_type = random.choice(case_type_ids)
        # Kayan only serves the eligible categories; a few ineligible files
        # exist because they were registered before the gate was enforced.
        category = random.choice(eligible_categories) if i < count - 3 else random.choice(all_categories)

        complete = i < 10
        status = "approved" if complete else random.choice(
            ["draft", "submitted", "under_review", "approved"])
        salary = random.randint(0, 6000)

        sections = {
            "SEC-BASIC": {"full_name_ar": full_name, "national_id": str(random.randint(1000000000, 1099999999)),
                          "birth_date": birth_date(1965, 2000), "gender": "male" if gender_m else "female",
                          "marital_status": random.choice(MARITAL),
                          "orphan_category_id": category, "nationality": "سعودي"},
            "SEC-EXTRA": {"dependents_count": 0,
                          "income_sources": [{"type": "راتب", "amount": salary}] if salary else [],
                          "has_social_security": random.choice([True, False]),
                          "has_citizen_account": random.choice([True, False])},
            "SEC-JOIN": {"join_reason": random.choice(["احتياج مالي", "فقدان العائل", "ظروف صحية"]),
                         "referral_source": random.choice(["الموقع", "احد المعارف", "جهة حكومية"]),
                         "previous_support": random.choice(["لا يوجد", "دعم سابق من جمعية اخرى"])},
            "SEC-BANK": {"bank_name": random.choice(BANKS),
                         "iban": f"SA{random.randint(10, 99)}{random.randint(10**19, 10**20 - 1)}"[:24],
                         "account_holder_name": full_name},
            "SEC-CONTACT": {"mobile": phone, "alt_mobile": db.norm_phone(phone_number(i + 500)),
                            "email": f"user{1001 + i}@example.com", "whatsapp": phone},
            "SEC-EDU": {"education_level": random.choice(EDU_LEVELS),
                        "employment_status": "يعمل" if salary else random.choice(EMPLOYMENT),
                        "employer": "جهة خاصة" if salary else "لا يوجد",
                        "monthly_salary": salary},
            "SEC-HOUSING": {"city": city, "district": random.choice(DISTRICTS),
                            "housing_type": random.choice(HOUSING),
                            "ownership_proof_type": random.choice([h["id"] for h in db.housing_proofs]),
                            "rooms": random.randint(1, 6),
                            "monthly_rent": random.randint(500, 4000),
                            "monthly_bills": random.randint(100, 600)},
            "SEC-HEALTH": {"chronic_conditions": random.choice(["لا يوجد", "سكري", "ضغط"]),
                           "disability": random.choice(["لا يوجد", "اعاقة حركية"]),
                           "has_health_insurance": random.choice([True, False]),
                           "monthly_medication_cost": random.randint(0, 800)},
        }
        if not complete:
            # Leave real gaps so the completeness endpoint has something to report.
            for sid, field in [("SEC-BANK", "iban"), ("SEC-HEALTH", "chronic_conditions")]:
                if random.random() < 0.5:
                    sections[sid][field] = None

        created = iso(random.randint(30, 120))
        b = {"id": bid, "file_no": f"KY-{4001 + i}", "status": status, "case_type": case_type,
             "orphan_category": category, "city": city, "full_name_ar": full_name,
             "phone": phone, "sections": sections, "eligibility_verified": 1,
             "approved_at": iso(random.randint(1, 20)) if status == "approved" else None,
             "created_at": created, "updated_at": iso(random.randint(0, 5))}
        db.insert_beneficiary(b)
        db.insert_account(phone, bid)
        beneficiaries.append({**b, "complete": complete, "salary": salary})
    print(f"Created {len(beneficiaries)} beneficiaries")

    # ---------------------------------------------------------- dependents
    dep_n = 0
    for b in beneficiaries:
        for _ in range(random.randint(1, 5) if b["complete"] else random.randint(0, 4)):
            dep_n += 1
            female = random.random() < 0.5
            db.insert_dependent({
                "id": f"DEP-{6000 + dep_n}", "beneficiary_id": b["id"],
                "name_ar": f"{random.choice(FIRST_NAMES_F if female else FIRST_NAMES_M)} "
                           f"{b['full_name_ar'].split()[-1]}",
                "relationship": random.choice(RELATIONSHIPS),
                "birth_date": birth_date(2000, 2020),
                "gender": "female" if female else "male",
                "education": random.choice(EDU_STAGES),
                "special_needs": 1 if random.random() < 0.15 else 0,
                "created_at": b["created_at"]})
        n = len(db.deps_for(b["id"]))
        b["household_size"] = 1 + n
        b["sections"]["SEC-EXTRA"]["dependents_count"] = n
        db.update_beneficiary(b["id"], {"sections": b["sections"]})
    print(f"Created {dep_n} dependents")

    # ----------------------------------------------------------- documents
    doc_n = 0
    for b in beneficiaries:
        for dt in db.document_types:
            if b["case_type"] not in dt["required_for"]:
                continue
            doc_n += 1
            if b["complete"]:
                status = "verified"
            elif dt["mandatory"]:
                status = random.choice(["uploaded", "verified", "missing", "missing"])
            else:
                status = random.choice(["uploaded", "missing"])
            db.insert_document({
                "id": f"DOC-{8000 + doc_n}", "beneficiary_id": b["id"],
                "document_type_id": dt["id"], "name_ar": dt["name_ar"],
                "mandatory": 1 if dt["mandatory"] else 0, "status": status,
                "file_path": f"/docs/{b['id']}/{dt['id']}.pdf" if status != "missing" else None,
                "created_at": b["created_at"],
                "updated_at": iso(random.randint(0, 30)) if status != "missing" else None})
    print(f"Created {doc_n} documents")

    # -------------------------------------------------- financial profiles
    for b in beneficiaries:
        obligations, person_costs = [], []
        for ot in random.sample(db.obligation_types, k=min(2, len(db.obligation_types))):
            obligations.append({"type_id": ot["id"], "name_ar": ot["name_ar"],
                                "monthly_sar": random.randint(300, 2500), "documented": True})
        countable = [c for c in db.person_cost_types if c["counted"]]
        for ct in random.sample(countable, k=min(2, len(countable))):
            person_costs.append({"type_id": ct["id"], "name_ar": ct["name_ar"],
                                 "monthly_sar": random.randint(200, 1500)})

        income = float(b["salary"])
        household = b.get("household_size", 1)
        total_ob = sum(o["monthly_sar"] for o in obligations)
        total_pc = sum(c["monthly_sar"] for c in person_costs)
        per_capita = (income - total_ob - total_pc) / max(1, household)
        need_score = max(0, min(100, round(100 - (per_capita / 15), 1)))

        db.insert_financial_profile({
            "id": f"FP-{b['id']}", "beneficiary_id": b["id"],
            "monthly_income": income, "monthly_expenses": float(total_ob + total_pc),
            "obligations": obligations, "person_costs": person_costs,
            "income_breakdown": b["sections"]["SEC-EXTRA"]["income_sources"],
            "household_size": household, "need_score": need_score,
            "created_at": b["created_at"]})
    print(f"Created {len(beneficiaries)} financial profiles")

    # ----------------------------------------------------- support requests
    approved = [b for b in beneficiaries if b["status"] == "approved"]
    stages = ["submitted", "under_study", "committee", "committee", "decided", "decided"]
    requests = []
    for i in range(22):
        b = random.choice(approved)
        rt = random.choice(db.request_types)          # a REAL request type
        stage = stages[i % len(stages)]
        ceiling = rt["ceiling_sar"] or 5000
        amount = float(random.randint(int(ceiling * 0.3), ceiling))
        description = random.choice(CASE_DESCRIPTIONS)
        sr = {"id": f"SR-{25001 + i}", "beneficiary_id": b["id"], "program_id": rt["program_id"],
              "request_type_id": rt["id"], "title_ar": rt["name_ar"],
              "case_description_ar": description, "description_ar": description,
              "internal_classification": random.choice(["عاجل", "اعتيادي", "اعتيادي", "متكرر"]),
              "channel": random.choice(["whatsapp", "call", "portal"]),
              "requested_amount_sar": amount, "amount": amount,
              "status": "submitted", "stage": stage,
              "created_at": iso(random.randint(10, 60)), "updated_at": iso(random.randint(0, 5))}
        db.insert_row("support_requests", sr)
        requests.append({**sr, "ceiling": ceiling})
    print(f"Created {len(requests)} support requests")

    # ------------------------------------------------- case studies & decisions
    case_n = dec_n = 0
    for sr in requests:
        if sr["stage"] in ("submitted",):
            continue
        case_n += 1
        steps = []
        for st in random.sample(db.case_steps, k=random.randint(1, 3)):
            steps.append({"step_id": st["id"], "name_ar": st["name_ar"],
                          "scheduled_at": iso(random.randint(5, 25), jitter_hours=False),
                          "status": "completed", "assigned_staff_id": random.choice(staff_ids),
                          "findings_ar": random.choice(CASE_NOTES),
                          "completed_at": iso(random.randint(1, 5))})
        recommendation = random.choice(RECOMMENDATIONS)
        db.insert_row("case_studies", {
            "id": f"CASE-{35000 + case_n}", "support_request_id": sr["id"],
            "beneficiary_id": sr["beneficiary_id"],
            "caseworker": random.choice(staff_ids),
            "social_researcher_id": random.choice(staff_ids),
            "notes_ar": random.choice(CASE_NOTES), "recommendation_ar": recommendation,
            "steps": steps,
            "status": "closed" if sr["stage"] == "decided" else "submitted_to_committee",
            "opened_at": iso(random.randint(20, 40)), "created_at": iso(random.randint(20, 40))})

        if sr["stage"] != "decided":
            continue
        dec_n += 1
        decision = random.choice(["accepted", "accepted", "docs_required", "declined"])
        amount = float(random.randint(int(sr["ceiling"] * 0.4), sr["ceiling"])) \
            if decision == "accepted" else 0.0
        reason = {"accepted": "استيفاء الشروط ووجود احتياج مؤكد",
                  "docs_required": "يلزم استكمال المستندات المطلوبة",
                  "declined": "لا يوجد احتياج مؤكد حسب التقييم"}[decision]
        db.insert_row("committee_decisions", {
            "id": f"DEC-{45000 + dec_n}", "support_request_id": sr["id"],
            "beneficiary_id": sr["beneficiary_id"], "decision": decision,
            "amount": amount, "notes_ar": reason, "reason_ar": reason,
            "required_documents_ar": ["تعريف الراتب", "عقد الايجار"] if decision == "docs_required" else [],
            "committee_members": [s["name_ar"] for s in db.staff[:3]],
            "notified_whatsapp": 1, "notified_sms": 1,
            "decided_by": random.choice(staff_ids), "decided_at": iso(random.randint(1, 15))})
        db.update_support_request(sr["id"], {"decision": decision, "status": decision})
        sr["decision"] = decision
        sr["approved_amount"] = amount
    print(f"Created {case_n} case studies and {dec_n} committee decisions")

    # ------------------------------------- enrollments, disbursements, payments
    enr_n = dis_n = pay_n = 0
    for sr in requests:
        if sr.get("decision") != "accepted" or not sr.get("approved_amount"):
            continue
        enr_n += 1
        eid = f"ENR-{55000 + enr_n}"
        months = random.choice([1, 3, 6])
        monthly = round(sr["approved_amount"] / months, 2)
        start = _utcnow() - timedelta(days=random.randint(30, 90))
        db.insert_row("enrollments", {
            "id": eid, "beneficiary_id": sr["beneficiary_id"], "program_id": sr["program_id"],
            "support_request_id": sr["id"],
            "type": "monthly_recurring" if months > 1 else "one_time",
            "monthly_amount": monthly if months > 1 else 0.0,
            "total_approved": sr["approved_amount"],
            "start_date": start.date().isoformat(),
            "end_date": (start + timedelta(days=30 * months)).date().isoformat(),
            "status": "active", "enrolled_at": iso(random.randint(20, 40))})

        for m in range(months):
            dis_n += 1
            due = start + timedelta(days=30 * m)
            paid = due < _utcnow() - timedelta(days=2)
            did = f"DIS-{65000 + dis_n}"
            paid_at = iso(random.randint(1, 10)) if paid else None
            db.insert_row("disbursements", {
                "id": did, "beneficiary_id": sr["beneficiary_id"], "program_id": sr["program_id"],
                "enrollment_id": eid, "amount": monthly,
                "status": "paid" if paid else random.choice(["scheduled", "approved"]),
                "approved_by": random.choice(staff_ids) if paid else None,
                "due_date": due.date().isoformat(), "paid_at": paid_at,
                "created_at": iso(random.randint(20, 40))})
            if paid:
                pay_n += 1
                # Every payment points at a real disbursement, so the 360 view
                # and the finance totals reconcile.
                db.insert_payment({
                    "id": f"PAY-{75000 + pay_n}", "beneficiary_id": sr["beneficiary_id"],
                    "disbursement_id": did, "amount": monthly, "method": "bank_transfer",
                    "reference": f"KYN{random.randint(100000, 999999)}", "paid_at": paid_at})
    print(f"Created {enr_n} enrollments, {dis_n} disbursements, {pay_n} payments")

    # --------------------------------------------------------------- tickets
    msg_n = 0
    for i in range(24):
        b = random.choice(beneficiaries)
        tid = f"TK-2026-{6001 + i}"
        status = random.choice(["open", "open", "in_progress", "waiting_customer", "replied", "closed"])
        opened = _utcnow() - timedelta(hours=random.randint(1, 96))
        first_message = random.choice(INBOUND_MESSAGES)
        db.insert_ticket({
            "id": tid, "subject_ar": random.choice(TICKET_SUBJECTS),
            "channel": random.choice(["whatsapp", "whatsapp", "call", "portal"]),
            "phone": b["phone"], "beneficiary_id": b["id"],
            "department_id": random.choice(department_ids),   # REAL department
            "priority": random.choice(["low", "medium", "medium", "high"]),
            "status": status,
            "assigned_to": random.choice(staff_ids + [None]),
            "opened_at": opened.replace(microsecond=0).isoformat() + "Z",
            "updated_at": iso(random.randint(0, 2)),
            "closed_at": iso(0) if status == "closed" else None,
            "first_message": first_message})

        # A believable thread: the beneficiary opens, staff answers later.
        cursor = opened
        msg_n += 1
        db.insert_ticket_message({
            "id": f"MSG-{95000 + msg_n}", "ticket_id": tid, "direction": "inbound",
            "sender": "beneficiary", "body_ar": first_message, "is_internal": 0,
            "sent_at": cursor.replace(microsecond=0).isoformat() + "Z"})
        for turn in range(random.randint(1, 4)):
            cursor += timedelta(minutes=random.randint(20, 240))
            if cursor > _utcnow():
                break
            inbound = turn % 2 == 1
            msg_n += 1
            db.insert_ticket_message({
                "id": f"MSG-{95000 + msg_n}", "ticket_id": tid,
                "direction": "inbound" if inbound else "outbound",
                "sender": "beneficiary" if inbound else random.choice(["agent", "bot"]),
                "body_ar": random.choice(INBOUND_MESSAGES if inbound else OUTBOUND_MESSAGES),
                "is_internal": 0,
                "sent_at": cursor.replace(microsecond=0).isoformat() + "Z"})
    print(f"Created 24 tickets and {msg_n} ticket messages")

    # ------------------------------------------------------- channel sessions
    for i in range(14):
        b = random.choice(beneficiaries)
        started = _utcnow() - timedelta(hours=random.randint(1, 240))
        duration = random.randint(45, 600)
        db.insert_call_session({
            "id": f"CALL-{15001 + i}", "phone": b["phone"], "beneficiary_id": b["id"],
            "sip_call_id": f"sip-{15001 + i}@kayan.pbx", "to_number": "966112925559",
            "identified": 1, "language": "ar",
            "dialect": random.choice(["نجدي", "حجازي", "شرقاوي", None]),
            "direction": random.choice(["inbound", "inbound", "outbound"]),
            "outcome": random.choice(["resolved_by_bot", "resolved_by_bot",
                                      "escalated_to_agent", "ticket_created", "voicemail"]),
            "intent": random.choice(["استفسار عن حالة الطلب", "طلب تسجيل جديد",
                                     "استفسار عن الدفعة", "شكوى"]),
            "duration_seconds": duration,
            "notes_ar": random.choice(["تم الرد على الاستفسار", "تم فتح تذكرة",
                                       "المستفيد يرغب في تسجيل جديد"]),
            "started_at": started.replace(microsecond=0).isoformat() + "Z",
            "ended_at": (started + timedelta(seconds=duration)).replace(microsecond=0).isoformat() + "Z"})

    for i in range(10):
        b = random.choice(beneficiaries)
        last = _utcnow() - timedelta(hours=random.randint(0, 40))
        db.insert_whatsapp_session({
            "id": f"WA-{16001 + i}", "phone": b["phone"], "beneficiary_id": b["id"],
            "window_expires_at": (last + timedelta(hours=24)).replace(microsecond=0).isoformat() + "Z",
            "last_message_at": last.replace(microsecond=0).isoformat() + "Z",
            "direction": "inbound"})
    print("Created 14 call sessions and 10 WhatsApp sessions")

    # ------------------------------------------------- sponsors & sponsorships
    for i in range(8):
        db.insert_row("sponsors", {
            "id": f"SPO-{19001 + i}",
            "name_ar": f"{random.choice(FIRST_NAMES_M)} {random.choice(LAST_NAMES)}"
                       if i % 3 else f"شركة {random.choice(LAST_NAMES)} للتجارة",
            "type": "individual" if i % 3 else "corporate",
            "phone": db.norm_phone(phone_number(i + 900)),
            "email": f"sponsor{i}@example.com",
            "total_pledged": float(random.randint(5000, 80000)),
            "created_at": iso(random.randint(60, 200))})
    for i in range(12):
        b = random.choice(approved)
        db.insert_row("sponsorships", {
            "id": f"KAF-{20001 + i}", "sponsor_id": f"SPO-{19001 + (i % 8)}",
            "beneficiary_id": b["id"],
            "monthly_amount": float(random.choice([500, 750, 1000, 1500])),
            "kind": random.choice(["restricted", "unrestricted"]),
            "status": "active" if i < 10 else "ended",
            "started_at": iso(random.randint(30, 180))})
    print("Created 8 sponsors and 12 sponsorships")

    # ---------------------------------------------------------------- events
    for i in range(6):
        capacity = random.choice([30, 50, 80])
        in_past = i < 2
        db.insert_row("events", {
            "id": f"EVT-{17001 + i}",
            "name_ar": random.choice(["يوم التاهيل المهني", "ورشة المهارات الحياتية",
                                      "اللقاء الدوري لاسر المستفيدين", "فعالية توعوية",
                                      "اليوم المفتوح", "برنامج تدريبي صيفي"]),
            "description_ar": random.choice(["ورشة تاهيل للمستفيدين", "لقاء مع المختصين",
                                             "برنامج تدريبي معتمد"]),
            "program_id": random.choice(program_ids),        # REAL program
            "event_date": date_only(-random.randint(5, 60)) if not in_past else date_only(random.randint(5, 40)),
            "location": random.choice(["مقر الجمعية", "قاعة المؤتمرات", "صالة المعهد"]),
            "capacity": capacity,
            "registered": random.randint(0, capacity),
            "status": "completed" if in_past else "scheduled",
            "created_at": iso(random.randint(40, 90))})
    print("Created 6 events")

    print("\n" + "=" * 52)
    print("SEED COMPLETE")
    print("=" * 52)
    for table in ("beneficiaries", "dependents", "documents", "support_requests",
                  "case_studies", "committee_decisions", "enrollments", "disbursements",
                  "payments", "tickets", "ticket_messages", "sponsorships", "events"):
        print(f"  {table:22} {db.count_table(table)}")


def main():
    parser = argparse.ArgumentParser(description="Seed the Kayan prototype database")
    parser.add_argument("--seed", type=int, default=None,
                        help="RNG seed (default: 20260101 for reproducible data)")
    parser.add_argument("--count", type=int, default=28, help="number of beneficiary files")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
    elif os.environ.get("SEED_RANDOM"):
        random.seed()
    else:
        random.seed(20260101)  # deterministic so demos and tests are repeatable

    seed_database(count=args.count)


if __name__ == "__main__":
    main()
