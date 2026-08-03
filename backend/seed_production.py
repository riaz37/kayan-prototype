"""
Seed production database with realistic demo data for Kayan prototype.
Run: python backend/seed_production.py
"""
import json
import os
import random
import sqlite3
import uuid
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data")), "kayan.db")

FIRST_NAMES_M = ["محمد", "عبدالله", "فهد", "خالد", "سعد", "عبدالرحمن", "سلطان", "ياسر", "عمر", "احمد", "علي", "حسن", "يوسف", "ابراهيم", "مصطفى", "احمد", "امير", "هاني", "بلال", "راشد", "ماجد", "طارق", "كريم", "وليد", "ادهم", "نواف", "عاصف"]
FIRST_NAMES_F = ["فاطمة", "نورة", "سارة", "منى", "ريم", "هدى", "لينا", "دانا", "جنى", "رنا", "مريم", "حور", "عمر", "رigo", "ياسمين", "لمى", "ندى", "سمر", "هند", "عبير", "اماني", "نورة", "هبة", "مها", "ايمان", "سلمى", "منار"]
LAST_NAMES = ["العتيبي", "الشمري", "القحطاني", "الحربي", "المطيري", "الدوسري", "الغامدي", "الرشيدي", "الزهراني", "العمري", "البلوي", "الفيفي", "الخضيري", "السعدي", "الكردي", "الឋملي", "الهاجري", "النعيمي", "الشحي", "المري", "البواردي", "الكعبي", "الدهماني"]
CITIES = ["الرياض", "جدة", "مكة المكرمة", "المدينة المنورة", "الدمام", "الخبر", "الطائف", "بريدة", "الظهران", "الجبيل", "حائل", "أبها", "الجوف", "نجران", "الباحة", "عرعر", "سكاكا", "الحدود الشمالية"]
DISTRICTS = ["حي السلام", "حي النزهة", "حي الملقا", "حي الياسمين", "حي النرجس", "حي العارض", "حي الراكة", "حي الحمراء"]

def gen_id(prefix, seq):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

def gen_phone():
    return f"05{random.randint(10000000, 99999999)}"

def gen_datetime(max_days_ago=7):
    d = datetime.utcnow() - timedelta(days=random.randint(0, max_days_ago), hours=random.randint(0, 23), minutes=random.randint(0, 59))
    return d.isoformat()

def gen_date(max_days_ago=365):
    d = datetime.utcnow() - timedelta(days=random.randint(0, max_days_ago))
    return d.strftime("%Y-%m-%d")

def gen_birth_date():
    year = random.randint(1960, 2015)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"

def seed_database():
    print("Starting seed...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Clear existing data
    for table in ["ticket_messages", "tickets", "events", "call_sessions",
                   "whatsapp_sessions", "notifications", "payments", "disbursements",
                   "enrollments", "committee_decisions", "case_studies", "support_requests",
                   "documents", "financial_profiles", "dependents", "accounts", "sponsors",
                   "sponsorships", "beneficiaries"]:
        try:
            conn.execute(f"DELETE FROM {table}")
        except:
            pass
    conn.commit()
    print("Cleared existing data")

    # Create beneficiaries
    beneficiaries = []
    for i in range(27):
        bid = gen_id("ben", i)
        file_no = f"KY-{1000 + i}"
        first = random.choice(FIRST_NAMES_M + FIRST_NAMES_F)
        last = random.choice(LAST_NAMES)
        full_name = f"{first} {last}"
        phone = gen_phone()
        city = random.choice(CITIES)
        district = random.choice(DISTRICTS)
        status = random.choice(["draft", "submitted", "under_review", "approved", "approved", "approved"])
        case_type = random.choice(["CT-NEW", "CT-NEW", "CT-FOSTER"])
        orphan_cat = random.choice(["OC-UNKNOWN-PARENTS", "OC-DECEASED", "OC-DISABLED"])

        sections = {
            "SEC-BASIC": {
                "full_name_ar": full_name,
                "national_id": f"{random.randint(1000000000, 9999999999)}",
                "birth_date": gen_birth_date(),
                "gender": random.choice(["M", "F"]),
                "marital_status": random.choice(["single", "married", "divorced", "widowed"]),
                "orphan_category_id": orphan_cat,
                "nationality": "SA"
            },
            "SEC-CONTACT": {
                "mobile": phone,
                "alt_mobile": f"05{random.randint(10000000, 99999999)}" if random.random() > 0.5 else None,
                "email": f"{first.lower()}.{last.lower()}@email.com" if random.random() > 0.6 else None,
                "whatsapp": phone
            },
            "SEC-HOUSING": {
                "city": city,
                "district": district,
                "housing_type": random.choice(["rented", "owned", "family", "government"]),
                "ownership_proof_type": random.choice(["title_deed", "rental_contract", "gov_letter"]),
                "rooms": random.randint(1, 6),
                "monthly_rent": random.randint(500, 5000) if random.random() > 0.3 else 0,
                "monthly_bills": random.randint(100, 500)
            },
            "SEC-EDU": {
                "education_level": random.choice(["primary", "intermediate", "secondary", "university", None]),
                "employment_status": random.choice(["employed", "unemployed", "self_employed", "retired"]),
                "employer": None,
                "monthly_salary": random.randint(2000, 12000) if random.random() > 0.4 else 0
            },
            "SEC-HEALTH": {
                "chronic_conditions": random.choice([None, None, "diabetes", "hypertension"]),
                "disability": random.choice([None, None, None, "physical"]),
                "has_health_insurance": random.choice([True, False]),
                "monthly_medication_cost": random.randint(0, 1000) if random.random() > 0.5 else 0
            },
            "SEC-EXTRA": {
                "dependents_count": random.randint(0, 8),
                "income_sources": random.choice([[], ["salary"], ["salary", "rental"], ["business"]]),
                "has_social_security": random.choice([True, False]),
                "has_citizen_account": random.choice([True, False])
            },
            "SEC-JOIN": {
                "join_reason": random.choice(["loss_of_breadwinner", "disability", "poverty", "natural_disaster"]),
                "referral_source": random.choice(["government", "self", "charity", "social_media"]),
                "previous_support": random.choice([None, "some_charity", "government_aid"])
            },
            "SEC-BANK": {
                "bank_name": random.choice(["alinma", "alrajhi", "snb", " Riyad Bank"]),
                "iban": f"SA{random.randint(10, 99)}{random.randint(1000, 9999)}{random.randint(1000, 9999)}{random.randint(1000, 9999)}{random.randint(1000, 9999)}{random.randint(1000, 9999)}" if random.random() > 0.2 else None,
                "account_holder_name": full_name
            },
            "SEC-ORPHAN": {
                "father_deceased_date": gen_date(3650) if random.random() > 0.3 else None,
                "father_death_cause": random.choice(["natural", "accident", "illness", None]),
                "mother_status": random.choice(["alive", "deceased", "remarried", "absent"]),
                "has_guardian": random.choice([True, False])
            }
        }

        created = gen_datetime(90)
        b = {
            "id": bid, "file_no": file_no, "status": status,
            "case_type": case_type, "orphan_category": orphan_cat,
            "city": city, "full_name_ar": full_name, "phone": phone,
            "sections": sections, "created_at": created, "updated_at": gen_datetime(3)
        }
        beneficiaries.append(b)

        conn.execute("""
            INSERT INTO beneficiaries (id, file_no, status, case_type, orphan_category, city, full_name_ar, phone, sections, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (b["id"], b["file_no"], b["status"], b["case_type"], b["orphan_category"],
              b["city"], b["full_name_ar"], b["phone"],
              json.dumps(b["sections"], ensure_ascii=False), b["created_at"], b["updated_at"]))

    print(f"Created {len(beneficiaries)} beneficiaries")

    # Create accounts
    for b in beneficiaries:
        conn.execute("INSERT INTO accounts (phone, beneficiary_id, password_set, created_at) VALUES (?, ?, ?, ?)",
                     (b["phone"], b["id"], 1, b["created_at"]))
    print(f"Created {len(beneficiaries)} accounts")

    # Create dependents
    dep_count = 0
    for b in beneficiaries:
        num_deps = random.randint(0, 6)
        for j in range(num_deps):
            dep_id = gen_id("dep", dep_count)
            dep_count += 1
            dep_name = random.choice(FIRST_NAMES_M + FIRST_NAMES_F) + " " + random.choice(LAST_NAMES)
            conn.execute("""
                INSERT INTO dependents (id, beneficiary_id, name_ar, relationship, birth_date, gender, education, special_needs, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (dep_id, b["id"], dep_name,
                  random.choice(["son", "daughter", "brother", "sister", "father", "mother", "spouse"]),
                  gen_birth_date(), random.choice(["M", "F"]),
                  random.choice(["primary", "intermediate", "secondary", "university", None]),
                  random.choice([0, 0, 0, 1]), gen_datetime(60)))
    print(f"Created {dep_count} dependents")

    # Create documents
    doc_count = 0
    doc_types = ["DOC-NAT-ID", "DOC-PASSPORT", "DOC-BIRTH-CERT", "DOC-DEATH-CERT", "DOC-HOUSING",
                 "DOC-INCOME", "DOC-MEDICAL", "DOC-EDU-CERT", "DOC-BANK-STMT", "DOC-PHOTO"]
    for b in beneficiaries:
        num_docs = random.randint(3, 8)
        for j in range(num_docs):
            doc_id = gen_id("doc", doc_count)
            doc_count += 1
            doc_type = random.choice(doc_types)
            conn.execute("""
                INSERT INTO documents (id, beneficiary_id, document_type_id, name_ar, mandatory, status, file_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (doc_id, b["id"], doc_type,
                  random.choice(["صورة الهوية", "شهادة الميلاد", "شهادة الوفاة", "عقد إيجار", "كشف حساب بنكي", "شهادة مدرسية", "تقرير طبي"]),
                  random.choice([1, 1, 1, 0]),
                  random.choice(["missing", "uploaded", "verified"]),
                  f"/docs/{doc_id}.pdf" if random.random() > 0.4 else None,
                  gen_datetime(60)))
    print(f"Created {doc_count} documents")

    # Create financial profiles
    for b in beneficiaries:
        conn.execute("""
            INSERT INTO financial_profiles (id, beneficiary_id, monthly_income, monthly_expenses, obligations, person_costs, need_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (f"FP-{b['id']}", b["id"],
              random.randint(0, 8000), random.randint(1000, 10000),
              json.dumps([{"type": "rent", "amount": random.randint(500, 3000)}], ensure_ascii=False),
              json.dumps([{"type": "food", "amount": random.randint(500, 2000)}], ensure_ascii=False),
              random.randint(20, 95),
              gen_datetime(60)))
    print(f"Created {len(beneficiaries)} financial profiles")

    # Create support requests
    programs = ["PROG-EDU", "PROG-HEALTH", "PROG-HOUSING", "PROG-LIVELIHOOD", "PROG-COMPASSION"]
    stages = ["submitted", "under_study", "committee", "decided", "decided"]
    sr_count = 0
    for i in range(20):
        b = random.choice(beneficiaries)
        sr_id = gen_id("SR", sr_count)
        sr_count += 1
        prog = random.choice(programs)
        stage = random.choice(stages)
        created = gen_datetime(60)

        conn.execute("""
            INSERT INTO support_requests (id, beneficiary_id, program_id, request_type_id, description_ar, status, stage, amount, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sr_id, b["id"], prog,
              f"REQ-{prog.split('-')[1]}-{random.randint(1, 10):02d}",
              random.choice([
                  "احتياج معيشي شهري لتغطية المصاريف الاساسية للاسرة",
                  "المستفيد باحث عن عمل ويحتاج تاهيل ودورة تدريبية معتمدة",
                  "الاسرة تواجه صعوبة في سداد الالتزام الحالي وتحتاج دعم عاجل",
                  "المستفيد ملتحق بالدراسة ويحتاج تغطية الرسوم للفصل القادم",
                  "حالة اجتماعية حرجة تتطلب تدخل عاجل من الجمعية"
              ]),
              "submitted", stage,
              random.randint(500, 20000) if random.random() > 0.3 else None,
              created, gen_datetime(3)))
    print(f"Created {sr_count} support requests")

    # Create case studies
    cs_count = 0
    for i in range(12):
        b = random.choice(beneficiaries)
        cs_id = gen_id("CS", cs_count)
        cs_count += 1
        conn.execute("""
            INSERT INTO case_studies (id, support_request_id, beneficiary_id, caseworker, notes_ar, steps, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cs_id, f"SR-{random.randint(1000, 9999)}", b["id"],
              random.choice(["STF-01", "STF-02", "STF-03"]),
              random.choice([
                  "تمت المعاينة الميدانية وتم توثيق حالة المستفيد",
                  "المستفيد يعاني من صعوبات اقتصادية حادة",
                  "الاسرة في حالة جيدة وتحتاج دعم مستمر",
                  "تم التعرف على احتياجات خاصة"
              ]),
              json.dumps(["visit", "interview", "assessment"], ensure_ascii=False),
              gen_datetime(30)))
    print(f"Created {cs_count} case studies")

    # Create committee decisions
    cd_count = 0
    for i in range(6):
        cd_id = gen_id("CD", cd_count)
        cd_count += 1
        conn.execute("""
            INSERT INTO committee_decisions (id, support_request_id, decision, amount, notes_ar, decided_by, decided_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cd_id, f"SR-{random.randint(1000, 9999)}",
              random.choice(["accepted", "declined", "docs_required"]),
              random.randint(1000, 15000) if random.random() > 0.3 else 0,
              random.choice(["تم قبول الطلب", "يرجى استكمال المستندات", "تم رفض الطلب"]),
              random.choice(["STF-01", "STF-02", "STF-03"]),
              gen_datetime(20)))
    print(f"Created {cd_count} committee decisions")

    # Create tickets
    ticket_channels = ["whatsapp", "call", "portal"]
    departments = ["DEPT-SERVICES", "DEPT-FINANCE", "DEPT-PROGRAMS", "DEPT-COMPLAINTS"]
    priorities = ["low", "normal", "normal", "high"]
    statuses = ["open", "open", "in_progress", "waiting_customer", "replied", "closed"]
    tk_count = 0
    for i in range(22):
        b = random.choice(beneficiaries)
        tk_id = f"TK-{1000 + i}"
        tk_count += 1
        created = gen_datetime(14)
        status = random.choice(statuses)

        conn.execute("""
            INSERT INTO tickets (id, subject_ar, channel, phone, beneficiary_id, department_id, priority, status, assigned_to, opened_at, updated_at, first_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (tk_id,
              random.choice([
                  "سداد ايجار", "استفسار عن برنامج علم", "طلب زيارة ميدانية",
                  "رقم الجوال مسجل مسبقا", "تأخر صرف المبلغ", "need to update bank details",
                  "استفسار عن حالة التسجيل", "شكوى في الخدمة", "طلب توضيح",
                  " مشكلة في تسجيل الدخول", "استفسار عن الدفعة القادمة"
              ]),
              random.choice(ticket_channels), b["phone"], b["id"],
              random.choice(departments), random.choice(priorities), status,
              random.choice(["STF-01", "STF-02", "STF-03", None]),
              created, gen_datetime(2),
              random.choice([
                  "السلام عليكم، عندي استفسار بخصوص طلب الدعم",
                  "مرحبا، حبيت اسفسر عن حالة ملفي",
                  "Hello, I need help with my registration",
                  "Hi, I want to check my support request status"
              ])))
    print(f"Created {tk_count} tickets")

    # Create ticket messages
    msg_count = 0
    for i in range(1, tk_count + 1):
        tk_id = f"TK-{1000 + i}"
        num_msgs = random.randint(2, 8)
        for j in range(num_msgs):
            msg_id = gen_id("MSG", msg_count)
            msg_count += 1
            is_inbound = random.random() > 0.4
            direction = "inbound" if is_inbound else "outbound"
            sender = "beneficiary" if is_inbound else random.choice(["bot", "agent"])
            conn.execute("""
                INSERT INTO ticket_messages (id, ticket_id, direction, sender, body_ar, sent_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (msg_id, tk_id, direction, sender,
                  random.choice([
                      "السلام عليكم، عندي استفسار بخصوص طلب الدعم",
                      "مرحبا، كيف حالك؟ حبيت اسفسر عن حالة ملفي",
                      "شكراً لتواصلكم، تم الرد على طلبكم",
                      "يرجى ارسال المستندات المطلوبة",
                      "Hello, I need help with my registration",
                      "Thank you for contacting us. Your request is being processed."
                  ]),
                  gen_datetime(7)))
    print(f"Created {msg_count} ticket messages")

    # Create enrollments
    en_count = 0
    enrollments = []
    for i in range(10):
        b = random.choice(beneficiaries)
        en_id = gen_id("EN", en_count)
        en_count += 1
        prog = random.choice(programs)
        created = gen_datetime(60)
        en = {"id": en_id, "beneficiary_id": b["id"], "program_id": prog}
        enrollments.append(en)

        conn.execute("""
            INSERT INTO enrollments (id, beneficiary_id, program_id, status, enrolled_at)
            VALUES (?, ?, ?, ?, ?)
        """, (en_id, b["id"], prog, random.choice(["active", "completed"]), created))
    print(f"Created {en_count} enrollments")

    # Create disbursements
    dis_count = 0
    for en in enrollments:
        num_dis = random.randint(1, 4)
        for j in range(num_dis):
            dis_id = gen_id("DIS", dis_count)
            dis_count += 1
            paid = random.random() > 0.4
            conn.execute("""
                INSERT INTO disbursements (id, beneficiary_id, program_id, amount, status, due_date, paid_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (dis_id, en["beneficiary_id"], en["program_id"],
                  random.randint(1000, 8000),
                  "paid" if paid else ("scheduled" if random.random() > 0.5 else "pending"),
                  gen_date(3),
                  gen_datetime(2) if paid else None,
                  gen_datetime(4)))
    print(f"Created {dis_count} disbursements")

    # Create payments
    pay_count = 0
    for i in range(15):
        pay_id = gen_id("PAY", pay_count)
        pay_count += 1
        b = random.choice(beneficiaries)
        conn.execute("""
            INSERT INTO payments (id, beneficiary_id, disbursement_id, amount, method, reference, paid_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pay_id, b["id"], f"DIS-{random.randint(1000, 9999)}",
              random.randint(1000, 10000),
              random.choice(["bank_transfer", "cash", "sadad"]),
              f"REF-{random.randint(100000, 999999)}",
              gen_datetime(30)))
    print(f"Created {pay_count} payments")

    # Create call sessions
    cs_count = 0
    for i in range(12):
        cs_id = gen_id("CS", cs_count)
        cs_count += 1
        b = random.choice(beneficiaries)
        conn.execute("""
            INSERT INTO call_sessions (id, phone, beneficiary_id, direction, outcome, intent, duration_seconds, notes_ar, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cs_id, b["phone"], b["id"],
              random.choice(["inbound", "outbound"]),
              random.choice(["resolved_by_bot", "escalated_to_agent", "ticket_created", "voicemail"]),
              random.choice(["registration", "support_request", "complaint", "inquiry"]),
              random.randint(30, 600),
              random.choice(["المستفيد يرغب في تسجيل جديد", "تم الرد على الاستفسار", "تم فتح تذكرة"]),
              gen_datetime(14),
              gen_datetime(14)))
    print(f"Created {cs_count} call sessions")

    # Create events
    ev_count = 0
    for i in range(6):
        ev_id = gen_id("EV", ev_count)
        ev_count += 1
        conn.execute("""
            INSERT INTO events (id, title_ar, description_ar, event_date, location, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ev_id,
              random.choice(["يوم التأهيل", "ورشة العمل", "اللقاء الدوري", "فعالية توعوية", "يوم مفتوح"]),
              random.choice(["ورشة تأهيل للمستفيدين", "لقاء مع المختصين", "برنامج تدريبي"]),
              gen_date(30),
              random.choice(["مقر الجمعية", "قاعة المؤتمرات", "صالة المعهد"]),
              gen_datetime(60)))
    print(f"Created {ev_count} events")

    conn.commit()
    conn.close()

    print("\n" + "="*50)
    print("SEED COMPLETE!")
    print("="*50)
    print(f"Beneficiaries: {len(beneficiaries)}")
    print(f"Accounts: {len(beneficiaries)}")
    print(f"Dependents: {dep_count}")
    print(f"Documents: {doc_count}")
    print(f"Support Requests: {sr_count}")
    print(f"Case Studies: {cs_count}")
    print(f"Committee Decisions: {cd_count}")
    print(f"Tickets: {tk_count}")
    print(f"Ticket Messages: {msg_count}")
    print(f"Enrollments: {en_count}")
    print(f"Disbursements: {dis_count}")
    print(f"Payments: {pay_count}")
    print(f"Call Sessions: {cs_count}")
    print(f"Events: {ev_count}")
    print("\nDatabase seeded successfully!")


if __name__ == "__main__":
    seed_database()
