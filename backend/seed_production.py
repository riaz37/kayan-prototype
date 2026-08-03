"""
Seed script for Kayan production database.
Generates realistic demo data for client pitching.
"""
import json
import random
import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "kayan.db")

# ============================================= NAME POOLS =============================================

ARABIC_MALE_NAMES = [
    ("محمد", "بن عبدالله", "الراشد"),
    ("عبدالله", "بن احمد", "المطيري"),
    ("خالد", "بن سعد", "العمري"),
    ("فهد", "بن محمد", "الشمري"),
    ("سعد", "بن فيصل", "الدوسري"),
    ("عبدالرحمن", "بن عبدالله", "العتيبي"),
    ("ياسر", "بن علي", "الغامدي"),
    ("امير", "بن حسن", "القحطاني"),
    ("سلطان", "بن فهد", "الحربي"),
    ("ماجد", "بن عبدالله", "الرشيدي"),
    ("احمد", "بن محمد", "البلوي"),
    ("عمر", "بن سعد", "النعيمي"),
    ("حسن", "بن ابراهيم", "الجابري"),
    ("مصطفى", "بن حسين", "الkbti"),
    ("يوسف", "بن احمد", "الزهراني"),
    ("ابراهيم", "بن خالد", "السهيمي"),
    ("turki", "بن عبدالله", "الدلم"),
    ("فقيه", "بن سعيد", "المحمدي"),
    ("نواف", "بن فهد", "السبيعي"),
    ("تركي", "بن احمد", "الحداد"),
]

ARABIC_FEMALE_NAMES = [
    ("فاطمة", "بنت عبدالله", "الراشد"),
    ("نورة", "بنت احمد", "المطيري"),
    ("ريم", "بنت سعد", "العمري"),
    ("سارة", "بنت محمد", "الشمري"),
    ("هند", "بنت فيصل", "الدوسري"),
    ("اماني", "بنت عبدالله", "العتيبي"),
    ("رنا", "بنت علي", "الغامدي"),
    ("منال", "بنت حسن", "القحطاني"),
    ("عبير", "بنت فهد", "الحربي"),
    ("لينا", "بنت عبدالله", "الرشيدي"),
    ("دانا", "بنت محمد", "البلوي"),
    ("هيا", "بنت سعد", "النعيمي"),
]

ENGLISH_NAMES = [
    ("Riaz Muhammad", "Bin Islam", ""),
    ("Sarah Johnson", "", ""),
    ("Ahmed Khan", "", ""),
    ("Fatima Al-Rashid", "", ""),
    ("Omar Abdullah", "", ""),
    ("Layla Hassan", "", ""),
    ("Yusuf Ali", "", ""),
    ("Mariam Ibrahim", "", ""),
    ("Hassan Mahmood", "", ""),
    ("Aisha Patel", "", ""),
]

MIXED_NAMES = [
    ("احمد", "Ali Khan", ""),
    ("محمد", "David Wilson", ""),
    ("فاطمة", "Sarah Mitchell", ""),
    ("عمر", "James Omar", ""),
    ("نورة", "Lisa Noor", ""),
]

CITIES = ["الرياض", "جدة", "الدمام", "مكة المكرمة", "المدينة المنورة", "تبوك", "ابها", "بريدة"]
CITIES_EN = ["Riyadh", "Jeddah", "Dammam", "Mecca", "Medina", "Tabuk", "Abha", "Buraidah"]

BANKS = ["البنك الاهلي السعودي", "البنك السعودي الفرنسي", "بنك الراجحي", "البنك thươngي السعودي", "بنك الجزيرة"]

CHRONIC_CONDITIONS = ["لا يوجد", "السكري", "ضغط الدم", "الربو", "امراض القلب"]
EDUCATION_LEVELS = ["ابتدائي", "متوسط", "ثانوي", "جامعي", "ماجستير"]
EMPLOYMENT_STATUS = ["باحث عن عمل", "موظف جزئي", " موظف كامل", "متقاعد", "عميل حر"]
HOUSING_TYPES = ["شقة استئجار", "دور في فيلا", "شقة ملكية", "سكن ايجار"]
RELATIONSHIPS = ["الزوجة", "الابن", "الابنة", "الاخ", "الأخت", "الام", "الاب"]

# ============================================= DATA GENERATORS =============================================

def gen_id(prefix, num):
    return f"{prefix}-{num}"

def gen_phone():
    return f"9665{random.randint(10000000, 99999999)}"

def gen_iban():
    return f"SA{random.randint(10, 99)}{random.randint(10000000000000000, 99999999999999999)}"

def gen_date(months_back=6):
    days = random.randint(0, months_back * 30)
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

def gen_datetime(months_back=6):
    days = random.randint(0, months_back * 30)
    hours = random.randint(8, 20)
    dt = datetime.now() - timedelta(days=days, hours=hours)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def gen_name():
    roll = random.random()
    if roll < 0.6:
        first, father, family = random.choice(ARABIC_MALE_NAMES + ARABIC_FEMALE_NAMES)
        return f"{first} {father} {family}".strip()
    elif roll < 0.9:
        first, last, _ = random.choice(ENGLISH_NAMES)
        return f"{first} {last}".strip()
    else:
        first, last, _ = random.choice(MIXED_NAMES)
        return f"{first} {last}".strip()

def gen_name_ar():
    first, father, family = random.choice(ARABIC_MALE_NAMES + ARABIC_FEMALE_NAMES)
    return f"{first} {father} {family}".strip()

def gen_bank_account(name):
    return {
        "bank_name": random.choice(BANKS),
        "iban": gen_iban(),
        "account_holder_name": name
    }

def gen_contact(phone):
    return {
        "mobile": phone,
        "alt_mobile": f"9665{random.randint(10000000, 99999999)}" if random.random() > 0.5 else None,
        "email": None,
        "whatsapp": phone
    }

def gen_basic(name):
    return {
        "full_name_ar": name,
        "national_id": str(random.randint(1000000000, 1999999999)),
        "birth_date": f"{random.randint(1970, 2005)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        "gender": random.choice(["male", "female"]),
        "marital_status": random.choice(["اعزب", "متزوج", "ارمل", "مطلق"]),
        "orphan_category_id": random.choice(["OC-UNK", "OC-SPEC"]),
        "nationality": "سعودي"
    }

def gen_extra():
    return {
        "dependents_count": random.randint(0, 8),
        "income_sources": [
            {"type": "الضمان الاجتماعي", "amount_sar": random.randint(1500, 5000)},
            {"type": "حساب المواطن", "amount_sar": random.randint(300, 1500)}
        ],
        "has_social_security": random.random() > 0.3,
        "has_citizen_account": random.random() > 0.4
    }

def gen_join():
    return {
        "join_reason": random.choice(["احتياج تعليمي", "احتياج صحي", "دعم معيشي", "مساعدة اجتماعية"]),
        "referral_source": random.choice(["الموقع الالكتروني", "واتساب", "الهاتف", "زيارة ميدانية", "اعزاء"]),
        "previous_support": random.random() > 0.7
    }

def gen_edu():
    return {
        "education_level": random.choice(EDUCATION_LEVELS),
        "employment_status": random.choice(EMPLOYMENT_STATUS),
        "employer": "-" if random.random() > 0.5 else f"شركة {random.choice(['ال振兴', 'ال Arciero', 'المتحدة', 'الخليج'])}",
        "monthly_salary": random.randint(0, 8000)
    }

def gen_housing(city):
    return {
        "city": city,
        "district": f"حي {random.choice(['النرجس', 'العليا', 'المروج', 'الзايدي', 'الورود'])}",
        "housing_type": random.choice(HOUSING_TYPES),
        "ownership_proof_type": random.choice(["HP-RENT", "HP-OWN"]),
        "rooms": random.randint(2, 7),
        "monthly_rent": random.randint(1000, 5000),
        "monthly_bills": random.randint(300, 2000)
    }

def gen_health():
    return {
        "chronic_conditions": random.choice(CHRONIC_CONDITIONS),
        "disability": random.random() > 0.85,
        "has_health_insurance": random.random() > 0.6,
        "monthly_medication_cost": random.randint(0, 1500)
    }

# ============================================= MAIN SEED FUNCTION =============================================

def seed_database():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    print("Starting seed...")

    # Clear existing data
    tables = [
        "ticket_messages", "tickets", "payments", "disbursements",
        "enrollments", "committee_decisions", "case_studies",
        "support_requests", "financial_profiles", "documents",
        "dependents", "beneficiaries", "call_sessions", "whatsapp_sessions", "events"
    ]
    for table in tables:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    print("Cleared existing data")

    # Track created data
    beneficiaries = []
    tickets_list = []
    support_requests_list = []
    enrollments_list = []
    disbursements_list = []

    # ============================================= BENEFICIARIES =============================================
    print("Creating beneficiaries...")

    statuses = {
        "draft": (8, (11, 40)),
        "submitted": (7, (60, 90)),
        "approved": (6, (100, 100)),
        "rejected": (3, (50, 80)),
        "under_review": (3, (70, 95))
    }

    ben_id = 1001
    for status, (count, (pct_min, pct_max)) in statuses.items():
        for i in range(count):
            name = gen_name()
            name_ar = gen_name_ar()
            city = random.choice(CITIES)
            phone = gen_phone()
            pct = random.randint(pct_min, pct_max)

            sections = {
                "SEC-BASIC": gen_basic(name_ar),
                "SEC-EXTRA": gen_extra(),
                "SEC-JOIN": gen_join(),
                "SEC-BANK": gen_bank_account(name_ar),
                "SEC-CONTACT": gen_contact(phone),
                "SEC-EDU": gen_edu(),
                "SEC-HOUSING": gen_housing(city),
                "SEC-HEALTH": gen_health()
            }

            # Adjust completeness
            if pct < 50:
                sections.pop("SEC-HOUSING", None)
                sections.pop("SEC-HEALTH", None)
                if pct < 30:
                    sections.pop("SEC-BANK", None)
                    sections.pop("SEC-EDU", None)

            created = gen_datetime(6)
            updated = gen_datetime(3) if status != "draft" else created

            beneficiary = {
                "id": gen_id("BEN", ben_id),
                "file_no": f"KY-{random.randint(3001, 4000)}",
                "status": status,
                "case_type": random.choice(["CT-IND", "CT-FOSTER"]),
                "orphan_category": random.choice(["OC-UNK", "OC-SPEC"]),
                "city": city,
                "full_name_ar": name_ar,
                "phone": phone,
                "sections": json.dumps(sections, ensure_ascii=False),
                "created_at": created,
                "updated_at": updated
            }

            conn.execute("""
                INSERT INTO beneficiaries (id, file_no, status, case_type, orphan_category, city, full_name_ar, phone, sections, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (beneficiary["id"], beneficiary["file_no"], beneficiary["status"],
                  beneficiary["case_type"], beneficiary["orphan_category"], beneficiary["city"],
                  beneficiary["full_name_ar"], beneficiary["phone"], beneficiary["sections"],
                  beneficiary["created_at"], beneficiary["updated_at"]))

            beneficiaries.append(beneficiary)
            ben_id += 1

    conn.commit()
    print(f"Created {len(beneficiaries)} beneficiaries")

    # ============================================= DEPENDENTS =============================================
    print("Creating dependents...")
    dep_id = 3001
    for b in beneficiaries:
        num_deps = random.randint(0, 5)
        for _ in range(num_deps):
            dep = {
                "id": gen_id("DEP", dep_id),
                "beneficiary_id": b["id"],
                "name_ar": gen_name_ar(),
                "relationship": random.choice(RELATIONSHIPS),
                "birth_date": gen_date(12),
                "gender": random.choice(["male", "female"]),
                "education": random.choice(EDUCATION_LEVELS),
                "special_needs": random.random() > 0.9,
                "created_at": gen_datetime(6)
            }
            conn.execute("""
                INSERT INTO dependents (id, beneficiary_id, name_ar, relationship, birth_date, gender, education, special_needs, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (dep["id"], dep["beneficiary_id"], dep["name_ar"], dep["relationship"],
                  dep["birth_date"], dep["gender"], dep["education"], dep["special_needs"], dep["created_at"]))
            dep_id += 1

    conn.commit()
    print(f"Created {dep_id - 3001} dependents")

    # ============================================= DOCUMENTS =============================================
    print("Creating documents...")
    doc_types = ["DOC-NATID", "DOC-SALARY", "DOC-RENT", "DOC-BANK", "DOC-PHOTO"]
    doc_statuses = ["uploaded", "verified", "missing", "rejected", "not_available"]

    doc_id = 4001
    for b in beneficiaries:
        for dt in doc_types:
            status = random.choice(doc_statuses)
            if b["status"] == "approved":
                status = random.choice(["uploaded", "verified"])
            elif b["status"] == "draft":
                status = random.choice(["missing", "not_available"])

            doc = {
                "id": gen_id("DOC", doc_id),
                "beneficiary_id": b["id"],
                "document_type_id": dt,
                "name_ar": f"مستند {dt}",
                "mandatory": 1 if dt in ["DOC-NATID", "DOC-PHOTO"] else 0,
                "status": status,
                "file_path": f"/uploads/{b['id']}/{dt}.pdf" if status in ["uploaded", "verified"] else None,
                "created_at": gen_datetime(6)
            }
            conn.execute("""
                INSERT INTO documents (id, beneficiary_id, document_type_id, name_ar, mandatory, status, file_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (doc["id"], doc["beneficiary_id"], doc["document_type_id"], doc["name_ar"],
                  doc["mandatory"], doc["status"], doc["file_path"], doc["created_at"]))
            doc_id += 1

    conn.commit()
    print(f"Created {doc_id - 4001} documents")

    # ============================================= FINANCIAL PROFILES =============================================
    print("Creating financial profiles...")
    fin_id = 5001
    for b in beneficiaries:
        income = random.randint(2000, 15000)
        expenses = random.randint(1500, income)
        obligations = [
            {"type": "OB-RENT", "amount": random.randint(1000, 4000), "documented": True},
            {"type": "OB-LOAN", "amount": random.randint(200, 2000), "documented": random.random() > 0.3}
        ]
        person_costs = [
            {"type": "PC-FOOD", "amount": random.randint(500, 2000)},
            {"type": "PC-HEALTH", "amount": random.randint(100, 1000)},
            {"type": "PC-EDUCATION", "amount": random.randint(200, 1500)}
        ]

        fin = {
            "id": gen_id("FIN", fin_id),
            "beneficiary_id": b["id"],
            "monthly_income": income,
            "monthly_expenses": expenses,
            "obligations": json.dumps(obligations, ensure_ascii=False),
            "person_costs": json.dumps(person_costs, ensure_ascii=False),
            "need_score": round(random.uniform(20, 95), 2),
            "created_at": gen_datetime(6)
        }

        conn.execute("""
            INSERT INTO financial_profiles (id, beneficiary_id, monthly_income, monthly_expenses, obligations, person_costs, need_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (fin["id"], fin["beneficiary_id"], fin["monthly_income"], fin["monthly_expenses"],
              fin["obligations"], fin["person_costs"], fin["need_score"], fin["created_at"]))
        fin_id += 1

    conn.commit()
    print(f"Created {fin_id - 5001} financial profiles")

    # ============================================= SUPPORT REQUESTS =============================================
    print("Creating support requests...")
    programs = ["PRG-ILM", "PRG-TRN", "PRG-QOL", "PRG-HSG", "PRG-VAL"]
    stages = ["new", "under_study", "decided", "rejected"]
    channels = ["whatsapp", "call", "portal"]

    sr_id = 20001
    for i in range(20):
        b = random.choice(beneficiaries)
        program = random.choice(programs)
        stage = random.choice(stages)
        created = gen_datetime(6)

        sr = {
            "id": gen_id("SR", sr_id),
            "beneficiary_id": b["id"],
            "program_id": program,
            "request_type_id": f"REQ-{program.split('-')[1]}-{random.randint(1, 10):02d}",
            "description_ar": random.choice([
                "احتياج معيشي شهري لتغطية المصاريف الاساسية للاسرة",
                "المستفيد باحث عن عمل ويحتاج تاهيل ودورة تدريبية معتمدة",
                "الاسرة تواجه صعوبة في سداد الالتزام الحالي وتحتاج دعم عاجل",
                "المستفيد ملتحق بالدراسة ويحتاج تغطية الرسوم للفصل القادم",
                "حالة اجتماعية حرجة تتطلب تدخل عاجل من الجمعية"
            ]),
            "status": "submitted",
            "stage": stage,
            "amount": random.randint(500, 20000) if random.random() > 0.3 else None,
            "created_at": created,
            "updated_at": gen_datetime(3)
        }

        conn.execute("""
            INSERT INTO support_requests (id, beneficiary_id, program_id, request_type_id, description_ar, status, stage, amount, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sr["id"], sr["beneficiary_id"], sr["program_id"], sr["request_type_id"],
              sr["description_ar"], sr["status"], sr["stage"], sr["amount"],
              sr["created_at"], sr["updated_at"]))

        support_requests_list.append(sr)
        sr_id += 1

    conn.commit()
    print(f"Created {sr_id - 20001} support requests")

    # ============================================= CASE STUDIES =============================================
    print("Creating case studies...")
    cs_id = 6001
    for sr in support_requests_list[:12]:
        cs = {
            "id": gen_id("CS", cs_id),
            "support_request_id": sr["id"],
            "beneficiary_id": sr["beneficiary_id"],
            "caseworker": random.choice(["احمد المطيري", "نورة الشمري", "فهد العمري", "سارة الدوسري"]),
            "notes_ar": random.choice([
                "تمت المعاينة الميدانية وتحققنا من الحالة الاجتماعية",
                "اجرينا مقابلة مع المستفيد وتناولنا احتياجاته الاساسية",
                "التقييم النفسي الاجتماعي مكتمل - الحالة مستقرة",
                "need to follow up with the beneficiary next week",
                "Case approved after field visit - family needs documented"
            ]),
            "steps": json.dumps([
                {"step": "تم استلام الطلب", "date": gen_datetime(4)},
                {"step": "تمت المعاينة الميدانية", "date": gen_datetime(3)}
            ], ensure_ascii=False),
            "created_at": gen_datetime(4)
        }
        conn.execute("""
            INSERT INTO case_studies (id, support_request_id, beneficiary_id, caseworker, notes_ar, steps, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cs["id"], cs["support_request_id"], cs["beneficiary_id"],
              cs["caseworker"], cs["notes_ar"], cs["steps"], cs["created_at"]))
        cs_id += 1

    conn.commit()
    print(f"Created {cs_id - 6001} case studies")

    # ============================================= COMMITTEE DECISIONS =============================================
    print("Creating committee decisions...")
    cd_id = 7001
    for sr in support_requests_list:
        if sr["stage"] == "decided":
            cd = {
                "id": gen_id("CD", cd_id),
                "support_request_id": sr["id"],
                "decision": random.choice(["accepted", "accepted", "accepted", "rejected"]),
                "amount": random.randint(1000, 15000) if random.random() > 0.3 else 0,
                "notes_ar": random.choice([
                    "تمت الموافقة على الطلب بناء على التقييم الاجتماعي",
                    "يحتاج الطلب الى مراجعة اضافية",
                    "تم الرفضdue to incomplete documentation",
                    "Approved after review - amount adjusted per policy"
                ]),
                "decided_by": random.choice(["لجنة الدراسات", "الادارة العامة", "اللجنة الاجتماعية"]),
                "decided_at": gen_datetime(3)
            }
            conn.execute("""
                INSERT INTO committee_decisions (id, support_request_id, decision, amount, notes_ar, decided_by, decided_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (cd["id"], cd["support_request_id"], cd["decision"], cd["amount"],
                  cd["notes_ar"], cd["decided_by"], cd["decided_at"]))
            cd_id += 1

    conn.commit()
    print(f"Created {cd_id - 7001} committee decisions")

    # ============================================= TICKETS =============================================
    print("Creating tickets...")
    departments = ["DEP-BEN", "DEP-IT", "DEP-KAF", "DEP-EVT", "DEP-PRG", "DEP-FIN"]
    ticket_statuses = ["open", "in_progress", "waiting_customer", "resolved", "expired"]
    priorities = ["low", "medium", "high", "urgent"]
    ticket_channels = ["whatsapp", "call", "portal"]

    tk_id = 20265001
    for i in range(22):
        b = random.choice(beneficiaries)
        created = gen_datetime(6)
        status = random.choice(ticket_statuses)

        tk = {
            "id": f"TK-{tk_id}",
            "subject_ar": random.choice([
                "سداد ايجار", "استفسار عن برنامج علم", "طلب زيارة ميدانية",
                "رقم الجوال مسجل مسبقا", "تأخر صرف المبلغ", "need to update bank details",
                "استفسار عن حالة التسجيل", "شكوى في الخدمة", "طلب توضيح",
                " مشكلة في تسجيل الدخول", "استفسار عن الدفعة القادمة"
            ]),
            "channel": random.choice(ticket_channels),
            "phone": b["phone"],
            "beneficiary_id": b["id"],
            "department_id": random.choice(departments),
            "priority": random.choice(priorities),
            "status": status,
            "assigned_to": random.choice(["STF-01", "STF-02", "STF-03", None]),
            "opened_at": created,
            "updated_at": gen_datetime(2),
            "first_message": random.choice([
                "السلام عليكم، عندي استفسار بخصوص طلب الدعم",
                "مرحبا، حبيت اسفسر عن حالة ملفي",
                "Hello, I need help with my registration",
                "Hi, I want to check my support request status"
            ])
        }

        conn.execute("""
            INSERT INTO tickets (id, subject_ar, channel, phone, beneficiary_id, department_id, priority, status, assigned_to, opened_at, updated_at, first_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (tk["id"], tk["subject_ar"], tk["channel"], tk["phone"], tk["beneficiary_id"],
              tk["department_id"], tk["priority"], tk["status"], tk["assigned_to"],
              tk["opened_at"], tk["updated_at"], tk["first_message"]))

        tickets_list.append(tk)
        tk_id += 1

    conn.commit()
    print(f"Created {len(tickets_list)} tickets")

    # ============================================= TICKET MESSAGES =============================================
    print("Creating ticket messages...")
    msg_id = 8001
    for tk in tickets_list:
        num_msgs = random.randint(1, 5)
        for j in range(num_msgs):
            msg = {
                "id": gen_id("MSG", msg_id),
                "ticket_id": tk["id"],
                "direction": "inbound" if j % 2 == 0 else "outbound",
                "sender": tk["phone"] if j % 2 == 0 else "system",
                "body_ar": random.choice([
                    "مرحبا، عندي استفسار",
                    "تم مراجعة طلبكم وسيتم التواصل معكم قريبا",
                    "شكراً على تواصلكم",
                    "يرجى ارسال المستندات المطلوبة",
                    "Thank you for your patience",
                    "We are reviewing your request"
                ]),
                "sent_at": gen_datetime(2)
            }
            conn.execute("""
                INSERT INTO ticket_messages (id, ticket_id, direction, sender, body_ar, sent_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (msg["id"], msg["ticket_id"], msg["direction"], msg["sender"],
                  msg["body_ar"], msg["sent_at"]))
            msg_id += 1

    conn.commit()
    print(f"Created {msg_id - 8001} ticket messages")

    # ============================================= ENROLLMENTS =============================================
    print("Creating enrollments...")
    en_id = 9001
    approved_beneficiaries = [b for b in beneficiaries if b["status"] == "approved"]
    for b in approved_beneficiaries:
        num_programs = random.randint(1, 3)
        enrolled_programs = random.sample(programs, min(num_programs, len(programs)))
        for prog in enrolled_programs:
            en = {
                "id": gen_id("EN", en_id),
                "beneficiary_id": b["id"],
                "program_id": prog,
                "status": random.choice(["active", "active", "completed"]),
                "enrolled_at": gen_datetime(5)
            }
            conn.execute("""
                INSERT INTO enrollments (id, beneficiary_id, program_id, status, enrolled_at)
                VALUES (?, ?, ?, ?, ?)
            """, (en["id"], en["beneficiary_id"], en["program_id"], en["status"], en["enrolled_at"]))
            enrollments_list.append(en)
            en_id += 1

    conn.commit()
    print(f"Created {en_id - 9001} enrollments")

    # ============================================= DISBURSEMENTS =============================================
    print("Creating disbursements...")
    dis_id = 10001
    for en in enrollments_list:
        num_dis = random.randint(1, 4)
        for i in range(num_dis):
            paid = random.random() > 0.4
            dis = {
                "id": gen_id("DIS", dis_id),
                "beneficiary_id": en["beneficiary_id"],
                "program_id": en["program_id"],
                "amount": random.randint(1000, 8000),
                "status": "paid" if paid else ("scheduled" if random.random() > 0.5 else "pending"),
                "due_date": gen_date(3),
                "paid_at": gen_datetime(2) if paid else None,
                "created_at": gen_datetime(4)
            }
            conn.execute("""
                INSERT INTO disbursements (id, beneficiary_id, program_id, amount, status, due_date, paid_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (dis["id"], dis["beneficiary_id"], dis["program_id"],
                  dis["amount"], dis["status"], dis["due_date"], dis["paid_at"], dis["created_at"]))
            disbursements_list.append(dis)
            dis_id += 1

    conn.commit()
    print(f"Created {dis_id - 10001} disbursements")

    # ============================================= PAYMENTS =============================================
    print("Creating payments...")
    pay_id = 11001
    paid_disbursements = [d for d in disbursements_list if d["status"] == "paid"]
    for d in paid_disbursements[:15]:
        pay = {
            "id": gen_id("PAY", pay_id),
            "beneficiary_id": d["beneficiary_id"],
            "disbursement_id": d["id"],
            "amount": d["amount"],
            "method": random.choice(["bank_transfer", "bank_transfer", "wallet"]),
            "reference": f"REF-{random.randint(100000, 999999)}",
            "paid_at": d["paid_at"]
        }
        conn.execute("""
            INSERT INTO payments (id, beneficiary_id, disbursement_id, amount, method, reference, paid_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pay["id"], pay["beneficiary_id"], pay["disbursement_id"], pay["amount"],
              pay["method"], pay["reference"], pay["paid_at"]))
        pay_id += 1

    conn.commit()
    print(f"Created {pay_id - 11001} payments")

    # ============================================= CALL SESSIONS =============================================
    print("Creating call sessions...")
    cs_id = 12001
    for i in range(12):
        b = random.choice(beneficiaries)
        call = {
            "id": gen_id("CALL", cs_id),
            "phone": b["phone"],
            "beneficiary_id": b["id"],
            "direction": random.choice(["inbound", "outbound"]),
            "outcome": random.choice(["resolved", "follow_up", "no_answer", "voicemail"]),
            "intent": random.choice(["استفسار", "طلب دعم", "شكوى", "تسجيل", "تحديث بيانات"]),
            "duration_seconds": random.randint(30, 600),
            "notes_ar": random.choice([
                "المستفيد يتقدم بطلب دعم تعليمي",
                "تم حل المشكلة بنجاح",
                "Need to follow up next week",
                "Call completed - beneficiary satisfied"
            ]),
            "started_at": gen_datetime(3),
            "ended_at": gen_datetime(2)
        }
        conn.execute("""
            INSERT INTO call_sessions (id, phone, beneficiary_id, direction, outcome, intent, duration_seconds, notes_ar, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (call["id"], call["phone"], call["beneficiary_id"], call["direction"],
              call["outcome"], call["intent"], call["duration_seconds"], call["notes_ar"],
              call["started_at"], call["ended_at"]))
        cs_id += 1

    conn.commit()
    print(f"Created {cs_id - 12001} call sessions")

    # ============================================= EVENTS =============================================
    print("Creating events...")
    events = [
        ("ورشة عمل المهارات الحياتية", "ورشة عمل لتأهيل المستفيدينسوق العمل"),
        ("حملة التبرع بالدم", "حملة تبرع بالدم بالتعاون مع الهلال الاحمر"),
        ("اليوم المفتوح", "يوم مفتوح لتعريف الجمهور بخدمات الجمعية"),
        ("دورة التدقيق المالي", "دورة تدريبية على ادارةالميزانية الشخصية"),
        ("ملتقى التوظيف", "ملتقى توظيف لخريجي برامج التاهيل"),
        ("احتفال يوم الطفل", "احتفال بمناسبة اليوم العالمي للطفل"),
    ]
    ev_id = 13001
    for title, desc in events:
        ev = {
            "id": gen_id("EV", ev_id),
            "title_ar": title,
            "description_ar": desc,
            "event_date": gen_date(2),
            "location": random.choice(["مقر الجمعية", "قاعة المؤتمرات", "صالة الاحتفالات"]),
            "created_at": gen_datetime(4)
        }
        conn.execute("""
            INSERT INTO events (id, title_ar, description_ar, event_date, location, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ev["id"], ev["title_ar"], ev["description_ar"], ev["event_date"],
              ev["location"], ev["created_at"]))
        ev_id += 1

    conn.commit()
    print(f"Created {ev_id - 13001} events")

    # ============================================= SUMMARY =============================================
    print("\n" + "="*50)
    print("SEED COMPLETE!")
    print("="*50)

    cursor = conn.execute("SELECT COUNT(*) FROM beneficiaries")
    print(f"Beneficiaries: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM dependents")
    print(f"Dependents: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM documents")
    print(f"Documents: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM financial_profiles")
    print(f"Financial Profiles: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM support_requests")
    print(f"Support Requests: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM case_studies")
    print(f"Case Studies: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM committee_decisions")
    print(f"Committee Decisions: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM tickets")
    print(f"Tickets: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM ticket_messages")
    print(f"Ticket Messages: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM enrollments")
    print(f"Enrollments: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM disbursements")
    print(f"Disbursements: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM payments")
    print(f"Payments: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM call_sessions")
    print(f"Call Sessions: {cursor.fetchone()[0]}")
    cursor = conn.execute("SELECT COUNT(*) FROM events")
    print(f"Events: {cursor.fetchone()[0]}")

    conn.close()
    print("\nDatabase seeded successfully!")


if __name__ == "__main__":
    seed_database()
