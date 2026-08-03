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

FIRST_NAMES_M = ["محمد", "عبدالله", "فهد", "خالد", "سعد", "عبدالرحمن", "سلطان", "ياسر", "عمر", "احمد", "علي", "حسن", "يوسف", "ابراهيم", "مصطفى", "امير", "هاني", "بلال", "راشد", "ماجد", "طارق", "كريم", "وليد", "ادهم", "نواف", "عاصف"]
FIRST_NAMES_F = ["فاطمة", "نورة", "سارة", "منى", "ريم", "هدى", "لينا", "دانا", "جنى", "رنا", "مريم", "حور", "ياسمين", "لمى", "ندى", "سمر", "هند", "عبير", "اماني", "مها", "ايمان", "سلمى", "منار"]
LAST_NAMES = ["العتيبي", "الشمري", "القحطاني", "الحربي", "المطيري", "الدوسري", "الغامدي", "الرشيدي", "الزهراني", "العمري", "البلوي", "الفيفي", "الخضيري", "السعدي", "الكردي", "الهاجري", "النعيمي", "الشحي", "المري", "البواردي", "الكعبي"]
CITIES = ["الرياض", "جدة", "مكة المكرمة", "المدينة المنورة", "الدمام", "الخبر", "الطائف", "بريدة", "الظهران", "الجبيل", "حائل", "أبها", "الجوف", "نجران", "الباحة", "عرعر", "سكاكا"]
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
    print(f"DB_PATH: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

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
        fully_complete = i < 6
        status = "approved" if fully_complete else random.choice(["draft", "submitted", "under_review", "approved", "approved"])
        case_type = random.choice(["CT-NEW", "CT-NEW", "CT-FOSTER"])
        orphan_cat = random.choice(["OC-UNK", "OC-SPEC", "OC-FATHER", "OC-MOTHER", "OC-BOTH"])

        sections = {
            "SEC-BASIC": {"full_name_ar": full_name, "national_id": f"{random.randint(1000000000, 9999999999)}",
                          "birth_date": gen_birth_date(), "gender": random.choice(["M", "F"]),
                          "marital_status": random.choice(["single", "married", "divorced", "widowed"]),
                          "orphan_category_id": orphan_cat, "nationality": "SA"},
            "SEC-CONTACT": {"mobile": phone, "alt_mobile": f"05{random.randint(10000000, 99999999)}",
                            "email": f"{first.lower()}.{last.lower()}@email.com",
                            "whatsapp": phone},
            "SEC-HOUSING": {"city": city, "district": district,
                            "housing_type": random.choice(["rented", "owned", "family", "government"]),
                            "ownership_proof_type": random.choice(["title_deed", "rental_contract", "gov_letter"]),
                            "rooms": random.randint(1, 6), "monthly_rent": random.randint(500, 5000),
                            "monthly_bills": random.randint(100, 500)},
            "SEC-EDU": {"education_level": random.choice(["primary", "intermediate", "secondary", "university"]),
                        "employment_status": random.choice(["employed", "unemployed", "self_employed", "retired"]),
                        "employer": "شركة أرامكو" if fully_complete else None,
                        "monthly_salary": random.randint(2000, 12000)},
            "SEC-HEALTH": {"chronic_conditions": random.choice(["diabetes", "hypertension", "none"]),
                           "disability": random.choice(["none", "physical"]),
                           "has_health_insurance": True,
                           "monthly_medication_cost": random.randint(0, 1000)},
            "SEC-EXTRA": {"dependents_count": random.randint(1, 6),
                          "income_sources": random.choice([["salary"], ["salary", "rental"], ["business"]]),
                          "has_social_security": True,
                          "has_citizen_account": True},
            "SEC-JOIN": {"join_reason": random.choice(["loss_of_breadwinner", "disability", "poverty", "natural_disaster"]),
                         "referral_source": random.choice(["government", "self", "charity", "social_media"]),
                         "previous_support": "some_charity"},
            "SEC-BANK": {"bank_name": random.choice(["alinma", "alrajhi", "snb", "Riyad Bank"]),
                         "iban": f"SA{random.randint(10, 99)}{random.randint(1000000000, 9999999999)}{random.randint(1000, 9999)}",
                         "account_holder_name": full_name},
            "SEC-ORPHAN": {"father_deceased_date": gen_date(3650),
                           "father_death_cause": random.choice(["natural", "accident", "illness"]),
                           "mother_status": random.choice(["alive", "deceased", "remarried", "absent"]),
                           "has_guardian": True}
        }

        created = gen_datetime(90)
        b = {"id": bid, "file_no": file_no, "status": status, "case_type": case_type,
             "orphan_category": orphan_cat, "city": city, "full_name_ar": full_name,
             "phone": phone, "sections": sections, "created_at": created, "updated_at": gen_datetime(3),
             "fully_complete": fully_complete}
        beneficiaries.append(b)

        conn.execute("""INSERT INTO beneficiaries (id, file_no, status, case_type, orphan_category, city, full_name_ar, phone, sections, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (b["id"], b["file_no"], b["status"], b["case_type"], b["orphan_category"],
                      b["city"], b["full_name_ar"], b["phone"],
                      json.dumps(b["sections"], ensure_ascii=False), b["created_at"], b["updated_at"]))
    print(f"Created {len(beneficiaries)} beneficiaries")

    for b in beneficiaries:
        conn.execute("INSERT INTO accounts (phone, beneficiary_id, password_set, created_at) VALUES (?, ?, ?, ?)",
                     (b["phone"], b["id"], 1, b["created_at"]))

    dep_count = 0
    for b in beneficiaries:
        dep_range = random.randint(1, 6) if b["fully_complete"] else random.randint(0, 6)
        for j in range(dep_range):
            dep_count += 1
            conn.execute("""INSERT INTO dependents (id, beneficiary_id, name_ar, relationship, birth_date, gender, education, special_needs, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                         (gen_id("dep", dep_count), b["id"],
                          random.choice(FIRST_NAMES_M + FIRST_NAMES_F) + " " + random.choice(LAST_NAMES),
                          random.choice(["son", "daughter", "brother", "sister", "father", "mother", "spouse"]),
                          gen_birth_date(), random.choice(["M", "F"]),
                          random.choice(["primary", "intermediate", "secondary", "university", None]),
                          random.choice([0, 0, 0, 1]), gen_datetime(60)))
    print(f"Created {dep_count} dependents")

    doc_count = 0
    doc_types = ["DOC-NAT-ID", "DOC-PASSPORT", "DOC-BIRTH-CERT", "DOC-DEATH-CERT", "DOC-HOUSING", "DOC-INCOME", "DOC-MEDICAL", "DOC-EDU-CERT", "DOC-BANK-STMT", "DOC-PHOTO"]
    doc_names = ["صورة الهوية", "جواز السفر", "شهادة الميلاد", "شهادة الوفاة", "عقد إيجار", "كشف حساب بنكي", "تقرير طبي", "شهادة مدرسية", "صورة شخصية"]
    for b in beneficiaries:
        for j in range(random.randint(5, 8)):
            doc_count += 1
            mandatory = 1 if j < 5 else 0
            status = "verified" if (b["fully_complete"] or random.random() > 0.3) else random.choice(["uploaded", "missing"])
            conn.execute("""INSERT INTO documents (id, beneficiary_id, document_type_id, name_ar, mandatory, status, file_path, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                         (gen_id("doc", doc_count), b["id"], doc_types[j % len(doc_types)],
                          doc_names[j % len(doc_names)], mandatory, status,
                          f"/docs/{gen_id('doc', doc_count)}.pdf", gen_datetime(60)))
    print(f"Created {doc_count} documents")

    for b in beneficiaries:
        conn.execute("""INSERT INTO financial_profiles (id, beneficiary_id, monthly_income, monthly_expenses, obligations, person_costs, need_score, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                     (f"FP-{b['id']}", b["id"], random.randint(0, 8000), random.randint(1000, 10000),
                      json.dumps([{"type": "rent", "amount": random.randint(500, 3000)}], ensure_ascii=False),
                      json.dumps([{"type": "food", "amount": random.randint(500, 2000)}], ensure_ascii=False),
                      random.randint(20, 95), gen_datetime(60)))
    print(f"Created {len(beneficiaries)} financial profiles")

    programs = ["PROG-EDU", "PROG-HEALTH", "PROG-HOUSING", "PROG-LIVELIHOOD", "PROG-COMPASSION"]
    sr_count = 0
    sr_ids = []
    stages_cycle = ["submitted", "under_study", "committee", "committee", "committee", "decided", "decided", "decided"]
    for i in range(20):
        b = random.choice(beneficiaries)
        sr_count += 1
        prog = random.choice(programs)
        stage = stages_cycle[i % len(stages_cycle)]
        sr_id = gen_id("SR", sr_count)
        sr_ids.append((sr_id, stage))
        conn.execute("""INSERT INTO support_requests (id, beneficiary_id, program_id, request_type_id, description_ar, status, stage, amount, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (sr_id, b["id"], prog,
                      f"REQ-{prog.split('-')[1]}-{random.randint(1, 10):02d}",
                      random.choice(["احتياج معيشي شهري لتغطية المصاريف الاساسية للاسرة",
                                      "المستفيد باحث عن عمل ويحتاج تاهيل ودورة تدريبية معتمدة",
                                      "الاسرة تواجه صعوبة في سداد الالتزام الحالي وتحتاج دعم عاجل",
                                      "المستفيد ملتحق بالدراسة ويحتاج تغطية الرسوم للفصل القادم",
                                      "حالة اجتماعية حرجة تتطلب تدخل عاجل من الجمعية"]),
                      "submitted", stage,
                      random.randint(500, 20000) if random.random() > 0.3 else None,
                      gen_datetime(60), gen_datetime(3)))
    print(f"Created {sr_count} support requests")

    cs_count = 0
    committee_srs = [sr_id for sr_id, stage in sr_ids if stage == "committee"]
    for sr_id in committee_srs:
        cs_count += 1
        sr = conn.execute("SELECT * FROM support_requests WHERE id = ?", (sr_id,)).fetchone()
        ben_id = sr["beneficiary_id"] if sr else random.choice(beneficiaries)["id"]
        conn.execute("""INSERT INTO case_studies (id, support_request_id, beneficiary_id, caseworker, notes_ar, recommendation_ar, steps, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                     (gen_id("CS", cs_count), sr_id, ben_id,
                      random.choice(["STF-01", "STF-02", "STF-03"]),
                      random.choice(["تمت المعاينة الميدانية وتم توثيق حالة المستفيد",
                                      "المستفيد يعاني من صعوبات اقتصادية حادة",
                                      "الاسرة في حالة جيدة وتحتاج دعم مستمر"]),
                      random.choice(["يُنصح بالموافقة على طلب الدعم نظرا للحالة الاجتماعية الحرجة",
                                      "يحتاج المستفيد للدعم العاجلdue to loss of income",
                                      "الحالة تستحق الدعم وفقا لمعايير اللجنة"]),
                      json.dumps(["visit", "interview", "assessment"], ensure_ascii=False), gen_datetime(30)))
    print(f"Created {cs_count} case studies")

    cd_count = 0
    decided_srs = [sr_id for sr_id, stage in sr_ids if stage == "decided"]
    for sr_id in decided_srs[:6]:
        cd_count += 1
        conn.execute("""INSERT INTO committee_decisions (id, support_request_id, decision, amount, notes_ar, decided_by, decided_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                     (gen_id("CD", cd_count), sr_id,
                      random.choice(["accepted", "declined", "docs_required"]),
                      random.randint(1000, 15000) if random.random() > 0.3 else 0,
                      random.choice(["تم قبول الطلب", "يرجى استكمال المستندات", "تم رفض الطلب"]),
                      random.choice(["STF-01", "STF-02", "STF-03"]), gen_datetime(20)))
    print(f"Created {cd_count} committee decisions")

    tk_count = 0
    for i in range(22):
        b = random.choice(beneficiaries)
        tk_count += 1
        created = gen_datetime(14)
        status = random.choice(["open", "open", "in_progress", "waiting_customer", "replied", "closed"])
        conn.execute("""INSERT INTO tickets (id, subject_ar, channel, phone, beneficiary_id, department_id, priority, status, assigned_to, opened_at, updated_at, first_message)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (f"TK-{1000 + i}",
                      random.choice(["سداد ايجار", "استفسار عن برنامج علم", "طلب زيارة ميدانية",
                                      "رقم الجوال مسجل مسبقا", "تأخر صرف المبلغ", "need to update bank details",
                                      "استفسار عن حالة التسجيل", "شكوى في الخدمة", "طلب توضيح",
                                      " مشكلة في تسجيل الدخول", "استفسار عن الدفعة القادمة"]),
                      random.choice(["whatsapp", "call", "portal"]), b["phone"], b["id"],
                      random.choice(["DEPT-SERVICES", "DEPT-FINANCE", "DEPT-PROGRAMS", "DEPT-COMPLAINTS"]),
                      random.choice(["low", "normal", "normal", "high"]), status,
                      random.choice(["STF-01", "STF-02", "STF-03", None]),
                      created, gen_datetime(2),
                      random.choice(["السلام عليكم، عندي استفسار بخصوص طلب الدعم",
                                      "مرحبا، حبيت اسفسر عن حالة ملفي",
                                      "Hello, I need help with my registration",
                                      "Hi, I want to check my support request status"])))
    print(f"Created {tk_count} tickets")

    msg_count = 0
    for i in range(1, tk_count + 1):
        for j in range(random.randint(2, 8)):
            msg_count += 1
            is_inbound = random.random() > 0.4
            conn.execute("""INSERT INTO ticket_messages (id, ticket_id, direction, sender, body_ar, sent_at)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (gen_id("MSG", msg_count), f"TK-{1000 + i}",
                          "inbound" if is_inbound else "outbound",
                          "beneficiary" if is_inbound else random.choice(["bot", "agent"]),
                          random.choice(["السلام عليكم، عندي استفسار بخصوص طلب الدعم",
                                          "مرحبا، كيف حالك؟ حبيت اسفسر عن حالة ملفي",
                                          "شكراً لتواصلكم، تم الرد على طلبكم",
                                          "يرجى ارسال المستندات المطلوبة",
                                          "Hello, I need help with my registration",
                                          "Thank you for contacting us. Your request is being processed."]),
                          gen_datetime(7)))
    print(f"Created {msg_count} ticket messages")

    en_count = 0
    enrollments = []
    for i in range(10):
        b = random.choice(beneficiaries)
        en_count += 1
        prog = random.choice(programs)
        en_id = gen_id("EN", en_count)
        enrollments.append({"id": en_id, "beneficiary_id": b["id"], "program_id": prog})
        conn.execute("""INSERT INTO enrollments (id, beneficiary_id, program_id, status, enrolled_at)
                        VALUES (?, ?, ?, ?, ?)""",
                     (en_id, b["id"], prog, random.choice(["active", "completed"]), gen_datetime(60)))
    print(f"Created {en_count} enrollments")

    dis_count = 0
    for en in enrollments:
        for j in range(random.randint(1, 4)):
            dis_count += 1
            paid = random.random() > 0.4
            conn.execute("""INSERT INTO disbursements (id, beneficiary_id, program_id, amount, status, due_date, paid_at, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                         (gen_id("DIS", dis_count), en["beneficiary_id"], en["program_id"],
                          random.randint(1000, 8000),
                          "paid" if paid else ("scheduled" if random.random() > 0.5 else "pending"),
                          gen_date(3), gen_datetime(2) if paid else None, gen_datetime(4)))
    print(f"Created {dis_count} disbursements")

    pay_count = 0
    for i in range(15):
        pay_count += 1
        b = random.choice(beneficiaries)
        conn.execute("""INSERT INTO payments (id, beneficiary_id, disbursement_id, amount, method, reference, paid_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                     (gen_id("PAY", pay_count), b["id"], f"DIS-{random.randint(1000, 9999)}",
                      random.randint(1000, 10000), random.choice(["bank_transfer", "cash", "sadad"]),
                      f"REF-{random.randint(100000, 999999)}", gen_datetime(30)))
    print(f"Created {pay_count} payments")

    cs2_count = 0
    for i in range(12):
        cs2_count += 1
        b = random.choice(beneficiaries)
        conn.execute("""INSERT INTO call_sessions (id, phone, beneficiary_id, direction, outcome, intent, duration_seconds, notes_ar, started_at, ended_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (gen_id("CS", cs2_count), b["phone"], b["id"],
                      random.choice(["inbound", "outbound"]),
                      random.choice(["resolved_by_bot", "escalated_to_agent", "ticket_created", "voicemail"]),
                      random.choice(["registration", "support_request", "complaint", "inquiry"]),
                      random.randint(30, 600),
                      random.choice(["المستفيد يرغب في تسجيل جديد", "تم الرد على الاستفسار", "تم فتح تذكرة"]),
                      gen_datetime(14), gen_datetime(14)))
    print(f"Created {cs2_count} call sessions")

    ev_count = 0
    for i in range(6):
        ev_count += 1
        conn.execute("""INSERT INTO events (id, title_ar, description_ar, event_date, location, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     (gen_id("EV", ev_count),
                      random.choice(["يوم التأهيل", "ورشة العمل", "اللقاء الدوري", "فعالية توعوية", "يوم مفتوح"]),
                      random.choice(["ورشة تأهيل للمستفيدين", "لقاء مع المختصين", "برنامج تدريبي"]),
                      gen_date(30), random.choice(["مقر الجمعية", "قاعة المؤتمرات", "صالة المعهد"]), gen_datetime(60)))
    print(f"Created {ev_count} events")

    conn.commit()
    conn.close()

    print(f"\n{'='*50}\nSEED COMPLETE!\n{'='*50}")
    print(f"Beneficiaries: {len(beneficiaries)}\nDependents: {dep_count}\nDocuments: {doc_count}")
    print(f"Support Requests: {sr_count}\nTickets: {tk_count}\nTicket Messages: {msg_count}")
    print(f"Enrollments: {en_count}\nDisbursements: {dis_count}\nPayments: {pay_count}")
    print("\nDatabase seeded successfully!")


if __name__ == "__main__":
    seed_database()
