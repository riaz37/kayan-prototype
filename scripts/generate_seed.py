"""
Kayan prototype — seed data generator (deterministic, seed=7).
Builds a fully cross-referenced synthetic dataset covering the whole
beneficiary journey: registration -> file sections -> dependents -> documents
-> financial profile -> support requests -> casework -> committee decision
-> enrollment -> monthly disbursements -> payments, plus CRM tickets and
WhatsApp/call sessions.

ALL DATA IS SYNTHETIC. No real beneficiary, orphan, or family is represented.

Run:  python scripts/generate_seed.py
"""
import json, os, random, sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
import reference as R

random.seed(7)
BASE = os.path.join(os.path.dirname(__file__), "..", "reference-data")
os.makedirs(BASE, exist_ok=True)
NOW = datetime(2026, 7, 23, 10, 0, 0)


def dump(name, obj):
    with open(os.path.join(BASE, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    n = len(obj) if isinstance(obj, list) else 1
    print(f"  {name:32} {n:>4} records")


def iso(dt):
    return dt.replace(microsecond=0).isoformat() + "Z"


M_FIRST = ["محمد", "عبدالله", "احمد", "خالد", "سعود", "تركي", "نواف", "سلطان", "بندر", "ماجد", "فهد", "راكان", "صالح", "عبدالرحمن"]
F_FIRST = ["سارة", "نورة", "ريم", "لينا", "هالة", "مها", "جواهر", "لطيفة", "الجوهرة", "دانة", "شادن", "منال", "امل", "رغد"]
FAMILY = ["القحطاني", "الغامدي", "الحربي", "الشهري", "العتيبي", "الدوسري", "المطيري", "الزهراني", "العنزي", "عسيري", "الشمري", "البقمي"]
MID = ["بن عبدالله", "بن محمد", "بن سعد", "بن ناصر", "بن فهد"]

BANKS = ["مصرف الراجحي", "البنك الاهلي السعودي", "بنك الرياض", "بنك البلاد", "مصرف الانماء", "البنك السعودي الفرنسي"]
EDU = ["ابتدائي", "متوسط", "ثانوي", "دبلوم", "بكالوريوس", "لم يكمل التعليم"]
EMPLOY = ["لا يعمل", "يعمل بدوام كامل", "يعمل بدوام جزئي", "طالب", "باحث عن عمل", "عمل حر"]
MARITAL = ["اعزب", "متزوج", "مطلق", "ارمل"]
HOUSING_TYPE = ["شقة", "دور في فيلا", "بيت شعبي", "غرفة", "استوديو"]
CHRONIC = ["لا يوجد", "لا يوجد", "لا يوجد", "سكري", "ربو", "ضغط", "فقر دم"]
REL = ["الزوج", "الزوجة", "ابن", "ابنة", "اخ", "اخت", "الام الحاضنة", "اخ يتيم ذو ظروف خاصة"]


def phone():
    return "9665" + "".join(str(random.randint(0, 9)) for _ in range(8))


def nid():
    return "1" + "".join(str(random.randint(0, 9)) for _ in range(9))


def iban():
    return "SA" + "".join(str(random.randint(0, 9)) for _ in range(22))


# ============================================================ reference dumps
dump("orphan_categories.json", R.ORPHAN_CATEGORIES)
dump("case_types.json", R.CASE_TYPES)
dump("form_sections.json", R.FORM_SECTIONS)
dump("housing_proofs.json", R.HOUSING_PROOFS)
dump("obligation_types.json", R.OBLIGATION_TYPES)
dump("person_cost_types.json", R.PERSON_COST_TYPES)
dump("document_types.json", R.DOCUMENT_TYPES)
dump("ticket_statuses.json", R.TICKET_STATUSES)
dump("departments.json", R.DEPARTMENTS)
dump("staff.json", R.STAFF)
dump("case_steps.json", R.CASE_STEPS)
dump("decisions.json", R.DECISIONS)
dump("templates.json", R.TEMPLATES)

# programs + flattened request-type catalogue
programs, request_types = [], []
for p in R.PROGRAMS:
    programs.append({k: v for k, v in p.items() if k != "requests"})
    for rid, name_ar, ceiling in p["requests"]:
        request_types.append({
            "id": rid, "program_id": p["id"], "name_ar": name_ar,
            "ceiling_sar": ceiling,
            "kind": "in_kind_or_cash" if ceiling > 0 else "service_or_letter",
            "recurring": rid in ("REQ-HSG-01", "REQ-ILM-02"),
        })
dump("programs.json", programs)
dump("request_types.json", request_types)

faqs = [{"id": i, "category": c, "q_ar": qa, "a_ar": aa, "q_en": qe, "a_en": ae}
        for (i, c, qa, aa, qe, ae) in R.FAQS]
dump("faqs.json", faqs)

# ============================================================ beneficiaries
beneficiaries, dependents, documents, financials = [], [], [], []
FILE_SEQ = 3000

for i in range(1, 41):
    FILE_SEQ += 1
    male = random.random() < 0.55
    first = random.choice(M_FIRST if male else F_FIRST)
    fam = random.choice(FAMILY)
    full = f"{first} {random.choice(MID)} {fam}"
    city_ar, city_en, districts = random.choice(R.CITIES)
    case_type = random.choices(["CT-IND", "CT-FOSTER"], weights=[7, 3])[0]
    cat = random.choices(["OC-UNK", "OC-SPEC"], weights=[8, 2])[0]
    created = NOW - timedelta(days=random.randint(3, 700))

    # file lifecycle state
    status = random.choices(
        ["draft", "submitted", "under_review", "approved", "approved", "approved", "rejected"],
        weights=[3, 3, 3, 6, 6, 6, 1])[0]

    salary = 0
    employment = random.choice(EMPLOY)
    if employment in ("يعمل بدوام كامل", "يعمل بدوام جزئي", "عمل حر"):
        salary = round(random.uniform(2500, 9000), 2)
    social_sec = random.random() < 0.5
    citizen_acc = random.random() < 0.6
    ss_amount = round(random.uniform(800, 3200), 2) if social_sec else 0.0
    ca_amount = round(random.uniform(300, 1100), 2) if citizen_acc else 0.0

    bid = f"BEN-{1000+i}"
    rent = round(random.choice([0, 12000, 18000, 24000, 30000]) / 12, 2)
    b = {
        "id": bid,
        "file_no": f"KY-{FILE_SEQ}",
        "case_type": case_type,
        "status": status,
        "orphan_category_id": cat,
        "eligibility_verified": True,
        "created_at": iso(created),
        "approved_at": iso(created + timedelta(days=random.randint(10, 45))) if status == "approved" else None,
        "sections": {
            "SEC-BASIC": {
                "full_name_ar": full, "national_id": nid(),
                "birth_date": iso(NOW - timedelta(days=random.randint(19, 48) * 365))[:10],
                "gender": "male" if male else "female",
                "marital_status": random.choice(MARITAL),
                "orphan_category_id": cat, "nationality": "سعودي" if male else "سعودية",
            },
            "SEC-EXTRA": {
                "dependents_count": 0,  # filled below
                "income_sources": ([{"type": "راتب", "amount_sar": salary}] if salary else []) +
                                  ([{"type": "الضمان الاجتماعي", "amount_sar": ss_amount}] if social_sec else []) +
                                  ([{"type": "حساب المواطن", "amount_sar": ca_amount}] if citizen_acc else []),
                "has_social_security": social_sec, "has_citizen_account": citizen_acc,
            },
            "SEC-JOIN": {
                "join_reason": random.choice(["احتياج سكني", "احتياج تعليمي", "احتياج معيشي", "تاهيل وتوظيف"]),
                "referral_source": random.choice(["الموقع الالكتروني", "الواتساب", "توصية مستفيد", "جهة حكومية"]),
                "previous_support": random.random() < 0.4,
            },
            "SEC-BANK": {"bank_name": random.choice(BANKS), "iban": iban(), "account_holder_name": full},
            "SEC-CONTACT": {"mobile": phone(), "alt_mobile": None,
                            "email": None, "whatsapp": None},
            "SEC-EDU": {"education_level": random.choice(EDU), "employment_status": employment,
                        "employer": random.choice(["-", "شركة خاصة", "جهة حكومية", "عمل حر"]) if salary else "-",
                        "monthly_salary": salary},
            "SEC-HOUSING": {
                "city": city_ar, "district": random.choice(districts),
                "housing_type": random.choice(HOUSING_TYPE),
                "ownership_proof_type": random.choice([h["id"] for h in R.HOUSING_PROOFS]),
                "rooms": random.randint(1, 5), "monthly_rent": rent, "monthly_bills": 0.0,
            },
            "SEC-HEALTH": {
                "chronic_conditions": random.choice(CHRONIC),
                "disability": random.random() < 0.12,
                "has_health_insurance": random.random() < 0.25,
                "monthly_medication_cost": round(random.uniform(0, 600), 2),
            },
        },
    }
    b["sections"]["SEC-CONTACT"]["whatsapp"] = b["sections"]["SEC-CONTACT"]["mobile"]
    beneficiaries.append(b)

    # ---- dependents
    n_dep = random.randint(0, 5) if case_type == "CT-IND" else random.randint(1, 6)
    for d in range(n_dep):
        dmale = random.random() < 0.5
        rel = random.choice(REL)
        dependents.append({
            "id": f"DEP-{5000 + len(dependents) + 1}",
            "beneficiary_id": bid,
            "name_ar": f"{random.choice(M_FIRST if dmale else F_FIRST)} {fam}",
            "relationship_ar": rel,
            "birth_date": iso(NOW - timedelta(days=random.randint(1, 40) * 365))[:10],
            "gender": "male" if dmale else "female",
            "is_orphan": rel == "اخ يتيم ذو ظروف خاصة",
            "education_stage": random.choice(["روضة", "ابتدائي", "متوسط", "ثانوي", "جامعي", "غير ملتحق"]),
            "has_special_needs": random.random() < 0.1,
        })
    b["sections"]["SEC-EXTRA"]["dependents_count"] = n_dep

    # ---- documents
    for dt in R.DOCUMENT_TYPES:
        if case_type not in dt["required_for"]:
            continue
        if status == "draft":
            st = random.choices(["missing", "uploaded"], weights=[7, 3])[0]
        elif status in ("submitted", "under_review"):
            st = random.choices(["uploaded", "missing", "verified"], weights=[5, 3, 2])[0]
        elif status == "approved":
            st = random.choices(["verified", "not_available", "ineligible"], weights=[8, 1, 1])[0]
        else:
            st = random.choice(["rejected", "missing"])
        if st == "not_available" and not dt.get("na_allowed"):
            st = "verified"
        if st == "ineligible" and not dt.get("ineligible_allowed"):
            st = "verified"
        documents.append({
            "id": f"DOC-{7000 + len(documents) + 1}",
            "beneficiary_id": bid, "document_type_id": dt["id"],
            "name_ar": dt["name_ar"], "mandatory": dt["mandatory"], "status": st,
            "note_ar": {"not_available": "لا يوجد", "ineligible": "عدم الاهلية"}.get(st),
            "uploaded_at": iso(created + timedelta(days=random.randint(0, 20))) if st != "missing" else None,
        })

    # ---- financial profile
    obligations = []
    for ot in R.OBLIGATION_TYPES:
        if random.random() < 0.45:
            amt = {"OB-LOAN": (500, 3000), "OB-CARD": (200, 1200), "OB-RENT": (800, 2500),
                   "OB-UTIL": (150, 600), "OB-TELECOM": (80, 350), "OB-BNPL": (100, 800),
                   "OB-NAJIZ": (300, 2000), "OB-SIMAH": (200, 1500)}[ot["id"]]
            obligations.append({"type_id": ot["id"], "name_ar": ot["name_ar"],
                                "monthly_sar": round(random.uniform(*amt), 2),
                                "documented": True})
    costs = []
    for ct in R.PERSON_COST_TYPES:
        if ct["counted"] and random.random() < 0.7:
            amt = {"PC-FUEL": (150, 600), "PC-TRANSPORT": (100, 700), "PC-GROCERY": (600, 2500),
                   "PC-INFANT": (150, 500), "PC-PERSONAL": (100, 900)}[ct["id"]]
            costs.append({"type_id": ct["id"], "name_ar": ct["name_ar"],
                          "monthly_sar": round(random.uniform(*amt), 2)})

    income = salary + ss_amount + ca_amount
    total_ob = round(sum(o["monthly_sar"] for o in obligations), 2)
    total_cost = round(sum(c["monthly_sar"] for c in costs), 2)
    household = 1 + n_dep
    net = round(income - total_ob - total_cost, 2)
    per_capita = round(net / household, 2)
    financials.append({
        "beneficiary_id": bid,
        "monthly_income_sar": round(income, 2),
        "income_breakdown": b["sections"]["SEC-EXTRA"]["income_sources"],
        "obligations": obligations, "total_obligations_sar": total_ob,
        "person_costs": costs, "total_person_costs_sar": total_cost,
        "household_size": household,
        "net_monthly_sar": net, "per_capita_monthly_sar": per_capita,
        # need score 0-100, higher = greater need (drives prioritization)
        "need_score": max(0, min(100, round(100 - (per_capita / 15), 1))),
    })
    b["sections"]["SEC-HOUSING"]["monthly_bills"] = total_ob

dump("beneficiaries.json", beneficiaries)
dump("dependents.json", dependents)
dump("documents.json", documents)
dump("financial_profiles.json", financials)

approved = [b for b in beneficiaries if b["status"] == "approved"]

# ============================================================ support requests
support_requests, case_studies, decisions_log = [], [], []
by_prog = {}
for rt in request_types:
    by_prog.setdefault(rt["program_id"], []).append(rt)

for i in range(1, 46):
    b = random.choice(approved)
    rt = random.choice(request_types)
    created = NOW - timedelta(days=random.randint(0, 180))
    stage = random.choices(
        ["submitted", "under_study", "committee", "decided", "decided", "decided"],
        weights=[2, 3, 2, 5, 5, 5])[0]
    sr_id = f"SR-{20000+i}"
    amount = 0.0
    if rt["ceiling_sar"]:
        amount = round(random.uniform(rt["ceiling_sar"] * 0.3, rt["ceiling_sar"]), 2)
    sr = {
        "id": sr_id, "beneficiary_id": b["id"], "program_id": rt["program_id"],
        "request_type_id": rt["id"], "title_ar": rt["name_ar"],
        "internal_classification": random.choice(["عاجل", "اعتيادي", "متكرر", "موسمي"]),
        "case_description_ar": random.choice([
            "الاسرة تواجه صعوبة في سداد الالتزام الحالي وتحتاج دعم عاجل",
            "المستفيد ملتحق بالدراسة ويحتاج تغطية الرسوم للفصل القادم",
            "السكن الحالي بحاجة الى ترميم بسبب تسربات في السقف",
            "المستفيد باحث عن عمل ويحتاج تاهيل ودورة تدريبية معتمدة",
            "احتياج معيشي شهري لتغطية المصاريف الاساسية للاسرة",
        ]),
        "requested_amount_sar": amount,
        "stage": stage,
        "created_at": iso(created),
        "channel": random.choice(["portal", "whatsapp", "call", "portal"]),
    }
    support_requests.append(sr)

    # ---- casework for anything past submitted
    if stage in ("under_study", "committee", "decided"):
        steps = []
        for cs in R.CASE_STEPS:
            if random.random() < 0.6:
                steps.append({
                    "step_id": cs["id"], "name_ar": cs["name_ar"],
                    "scheduled_at": iso(created + timedelta(days=random.randint(2, 20))),
                    "status": random.choice(["completed", "completed", "scheduled"]),
                    "assigned_staff_id": random.choice([s["id"] for s in R.STAFF if s["department_id"] in ("DEP-BEN", "DEP-PRG")]),
                    "findings_ar": random.choice([
                        "الحالة مطابقة للبيانات المقدمة", "يوجد احتياج فعلي مؤكد",
                        "تم التحقق من السكن والتابعين", "يحتاج متابعة اضافية",
                    ]),
                })
        case_studies.append({
            "id": f"CASE-{30000+i}", "support_request_id": sr_id,
            "beneficiary_id": b["id"],
            "opened_at": iso(created + timedelta(days=1)),
            "steps": steps,
            "social_researcher_id": random.choice(["STF-04", "STF-02"]),
            "recommendation_ar": random.choice([
                "التوصية بالقبول ضمن السقف المعتمد", "التوصية بالقبول جزئيا",
                "التوصية باستكمال المستندات", "التوصية بالاعتذار لعدم انطباق الشروط",
            ]),
            "status": "closed" if stage == "decided" else "open",
        })

    # ---- committee decision
    if stage == "decided":
        dec = random.choices(["accepted", "docs_required", "declined"], weights=[6, 2, 2])[0]
        approved_amt = 0.0
        if dec == "accepted" and amount:
            approved_amt = round(amount * random.choice([1.0, 1.0, 0.75, 0.5]), 2)
        decisions_log.append({
            "id": f"DEC-{40000+i}", "support_request_id": sr_id,
            "beneficiary_id": b["id"], "decision": dec,
            "decision_ar": next(d["name_ar"] for d in R.DECISIONS if d["id"] == dec),
            "approved_amount_sar": approved_amt,
            "committee_date": iso(created + timedelta(days=random.randint(20, 40))),
            "committee_members": random.sample([s["name_ar"] for s in R.STAFF], 3),
            "reason_ar": {
                "accepted": "استيفاء الشروط ووجود احتياج مؤكد",
                "docs_required": "نقص في المستندات المطلوبة",
                "declined": "عدم انطباق شروط الاستحقاق حاليا",
            }[dec],
            "notified_whatsapp": True, "notified_sms": True,
        })
        sr["decision"] = dec

dump("support_requests.json", support_requests)
dump("case_studies.json", case_studies)
dump("committee_decisions.json", decisions_log)

# ============================================================ enrollments + disbursements + payments
enrollments, disbursements, payments = [], [], []
accepted = [d for d in decisions_log if d["decision"] == "accepted" and d["approved_amount_sar"] > 0]

for i, d in enumerate(accepted, start=1):
    sr = next(s for s in support_requests if s["id"] == d["support_request_id"])
    rt = next(r for r in request_types if r["id"] == sr["request_type_id"])
    start = datetime.fromisoformat(d["committee_date"].replace("Z", "")) + timedelta(days=5)
    recurring = rt["recurring"]
    months = 12 if recurring else 1
    monthly = round(d["approved_amount_sar"] / months, 2)
    en_id = f"ENR-{50000+i}"
    enrollments.append({
        "id": en_id, "beneficiary_id": d["beneficiary_id"],
        "program_id": sr["program_id"], "request_type_id": rt["id"],
        "support_request_id": sr["id"], "decision_id": d["id"],
        "type": "monthly_recurring" if recurring else "one_time",
        "monthly_amount_sar": monthly if recurring else 0.0,
        "total_approved_sar": d["approved_amount_sar"],
        "start_date": iso(start)[:10],
        "end_date": iso(start + timedelta(days=365))[:10] if recurring else iso(start)[:10],
        "status": random.choice(["active", "active", "completed"]),
    })
    for m in range(months):
        due = start + timedelta(days=30 * m)
        if due > NOW + timedelta(days=60):
            break
        st = "paid" if due < NOW - timedelta(days=2) else random.choice(["scheduled", "pending_approval"])
        dis_id = f"DIS-{60000 + len(disbursements) + 1}"
        disbursements.append({
            "id": dis_id, "enrollment_id": en_id, "beneficiary_id": d["beneficiary_id"],
            "program_id": sr["program_id"],
            "amount_sar": monthly, "due_date": iso(due)[:10], "status": st,
            "approved_by": "STF-06" if st == "paid" else None,
        })
        if st == "paid":
            ben = next(b for b in beneficiaries if b["id"] == d["beneficiary_id"])
            payments.append({
                "id": f"PAY-{70000 + len(payments) + 1}",
                "disbursement_id": dis_id, "beneficiary_id": d["beneficiary_id"],
                "amount_sar": monthly, "method": "bank_transfer",
                "iban": ben["sections"]["SEC-BANK"]["iban"],
                "bank_name": ben["sections"]["SEC-BANK"]["bank_name"],
                "paid_at": iso(due + timedelta(days=random.randint(0, 3))),
                "reference": f"KYN{random.randint(100000, 999999)}",
                "status": "settled",
            })

dump("enrollments.json", enrollments)
dump("disbursements.json", disbursements)
dump("payments.json", payments)

# ============================================================ sponsors + sponsorships (كفالة)
sponsors, sponsorships = [], []
for i in range(1, 16):
    male = random.random() < 0.6
    sponsors.append({
        "id": f"SPO-{8000+i}",
        "name_ar": f"{random.choice(M_FIRST if male else F_FIRST)} {random.choice(FAMILY)}",
        "type": random.choice(["individual", "individual", "corporate"]),
        "phone": phone(),
        "city": random.choice(R.CITIES)[0],
        "monthly_pledge_sar": round(random.choice([500, 800, 1000, 1500, 2000]), 2),
        "status": random.choice(["active", "active", "paused"]),
        "since": iso(NOW - timedelta(days=random.randint(60, 900)))[:10],
    })
for i, s in enumerate(sponsors, start=1):
    if s["status"] != "active":
        continue
    b = random.choice(approved)
    sponsorships.append({
        "id": f"KAF-{9000+i}", "sponsor_id": s["id"], "beneficiary_id": b["id"],
        "type": random.choice(["restricted", "unrestricted"]),
        "type_ar": "كفالة مقيدة" if random.random() < 0.5 else "كفالة غير مقيدة",
        "monthly_amount_sar": s["monthly_pledge_sar"],
        "start_date": s["since"], "status": "active",
    })
dump("sponsors.json", sponsors)
dump("sponsorships.json", sponsorships)

# ============================================================ CRM tickets + messages
TICKET_SUBJECTS = [
    ("سداد ايجار", "DEP-BEN"), ("استفسار عن حالة الطلب", "DEP-BEN"),
    ("تعذر تسجيل الدخول", "DEP-IT"), ("رقم الجوال مسجل مسبقا", "DEP-IT"),
    ("كفالة يتيم مقيدة", "DEP-KAF"), ("استفسار عن فعالية", "DEP-EVT"),
    ("طلب مشهد الضمان", "DEP-BEN"), ("تاخر صرف المساعدة", "DEP-FIN"),
    ("استكمال مستندات", "DEP-BEN"), ("استفسار عن برنامج علم", "DEP-PRG"),
    ("تحديث البيانات البنكية", "DEP-FIN"), ("طلب زيارة ميدانية", "DEP-BEN"),
]
tickets, ticket_messages = [], []
for i in range(1, 41):
    b = random.choice(beneficiaries)
    subj, dep = random.choice(TICKET_SUBJECTS)
    opened = NOW - timedelta(hours=random.randint(1, 480))
    st = random.choices(
        ["open", "in_progress", "waiting_customer", "replied", "closed", "expired"],
        weights=[4, 2, 2, 3, 8, 2])[0]
    tid = f"TK-2026-{5000+i*37 % 9000}"
    last = opened + timedelta(hours=random.randint(0, 20))
    tickets.append({
        "id": tid,
        "beneficiary_id": b["id"],
        "customer_name_ar": b["sections"]["SEC-BASIC"]["full_name_ar"],
        "whatsapp_number": b["sections"]["SEC-CONTACT"]["whatsapp"],
        "department_id": dep,
        "subject_ar": subj,
        "status": st,
        "channel": random.choices(["whatsapp", "call", "portal"], weights=[6, 3, 1])[0],
        "priority": random.choice(["low", "medium", "medium", "high"]),
        "assigned_staff_id": random.choice([None, "STF-01", "STF-02", "STF-03"]),
        "opened_at": iso(opened), "last_update": iso(last),
        "closed_at": iso(last + timedelta(hours=2)) if st == "closed" else None,
        "messages_count": random.randint(1, 5),
        "linked_request_id": random.choice([None] + [s["id"] for s in support_requests[:10]]),
    })
    for m in range(random.randint(1, 3)):
        ticket_messages.append({
            "id": f"MSG-{90000 + len(ticket_messages) + 1}",
            "ticket_id": tid,
            "direction": "inbound" if m % 2 == 0 else "outbound",
            "sender": "beneficiary" if m % 2 == 0 else "agent",
            "body_ar": subj if m == 0 else random.choice([
                "شكرا لتواصلكم، جاري دراسة طلبكم وسنوافيكم بالتحديث",
                "نامل تزويدنا بصورة الهوية الوطنية لاستكمال الطلب",
                "تم استلام المستندات وسيتم رفعها للجنة المختصة",
                "متى يتم الرد على الطلب؟",
            ]),
            "sent_at": iso(opened + timedelta(minutes=8 * (m + 1))),
        })
dump("tickets.json", tickets)
dump("ticket_messages.json", ticket_messages)

# ============================================================ channel sessions
call_sessions, wa_sessions = [], []
for i in range(1, 21):
    b = random.choice(beneficiaries)
    started = NOW - timedelta(hours=random.randint(1, 300))
    dur = random.randint(45, 420)
    call_sessions.append({
        "id": f"CALL-{11000+i}",
        "sip_call_id": f"sip-{random.randint(100000,999999)}@kayan.pbx",
        "direction": random.choice(["inbound", "inbound", "outbound"]),
        "from_number": b["sections"]["SEC-CONTACT"]["mobile"],
        "to_number": "966112925559",
        "beneficiary_id": b["id"],
        "identified": random.random() < 0.8,
        "language": "ar", "dialect": random.choice(["نجدي", "حجازي", "شرقاوي", "فصحى"]),
        "started_at": iso(started), "duration_sec": dur,
        "outcome": random.choice(["resolved_by_bot", "escalated_to_agent", "ticket_created", "voicemail"]),
        "intent": random.choice(["استفسار عن حالة الطلب", "تسجيل جديد", "استكمال مستندات",
                                 "استفسار عن صرف", "طلب دعم سكني"]),
        "transcript_available": True,
    })
for i in range(1, 26):
    b = random.choice(beneficiaries)
    started = NOW - timedelta(hours=random.randint(0, 200))
    wa_sessions.append({
        "id": f"WA-{12000+i}",
        "wa_number": b["sections"]["SEC-CONTACT"]["whatsapp"],
        "beneficiary_id": b["id"],
        "opened_at": iso(started),
        "window_expires_at": iso(started + timedelta(hours=24)),
        "status": "open" if (NOW - started).total_seconds() < 86400 else "expired",
        "last_inbound_at": iso(started + timedelta(minutes=random.randint(0, 300))),
        "messages": random.randint(1, 12),
    })
dump("call_sessions.json", call_sessions)
dump("whatsapp_sessions.json", wa_sessions)

# ============================================================ events (from ERP screenshot)
events = []
EV = [("ملتقى ابناء كيان السنوي", "الرياض"), ("رحلة ترفيهية لابناء الجمعية", "جدة"),
      ("ورشة تاهيل لسوق العمل", "الرياض"), ("برنامج توعوي للاسر الحاضنة", "الدمام"),
      ("حفل تكريم المتفوقين", "الرياض"), ("فعالية اليوم الوطني", "الرياض")]
for i, (n, c) in enumerate(EV, start=1):
    d = NOW + timedelta(days=random.randint(-60, 90))
    events.append({
        "id": f"EVT-{13000+i}", "name_ar": n, "city": c,
        "date": iso(d)[:10],
        "status": "completed" if d < NOW else "scheduled",
        "capacity": random.choice([50, 80, 120, 200]),
        "registered": random.randint(20, 120),
        "program_id": random.choice([p["id"] for p in programs]),
    })
dump("events.json", events)

print("\nSeed generation complete.")
