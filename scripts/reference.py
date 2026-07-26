"""
Kayan prototype — reference data transcribed from the client's
"رحلة المستفيد في نظام جمعية كيان" guide and the ERP/CRM screenshots.
Imported by generate_seed.py. Arabic is undiacritized (standard for UI/ERP text).
"""

# ---------------------------------------------------------------- orphan categories
ORPHAN_CATEGORIES = [
    {"id": "OC-UNK", "name_ar": "يتيم مجهول الابوين", "name_en": "Orphan of unknown parentage",
     "eligible": True, "notes_ar": "الفئة الاساسية التي تخدمها جمعية كيان (الايتام ذوو الظروف الخاصة)"},
    {"id": "OC-SPEC", "name_ar": "يتيم ذو ظروف خاصة", "name_en": "Orphan with special circumstances",
     "eligible": True, "notes_ar": "يشمل حالات الرعاية البديلة والاحتضان"},
    {"id": "OC-FATHER", "name_ar": "يتيم الاب", "name_en": "Paternal orphan",
     "eligible": False, "notes_ar": "يحال الى الجمعيات المختصة بالايتام العاديين"},
    {"id": "OC-MOTHER", "name_ar": "يتيم الام", "name_en": "Maternal orphan",
     "eligible": False, "notes_ar": "يحال الى الجمعيات المختصة"},
    {"id": "OC-BOTH", "name_ar": "يتيم الابوين", "name_en": "Orphan of both parents",
     "eligible": False, "notes_ar": "يحال الى الجمعيات المختصة ما لم يكن مجهول الابوين"},
]

# ---------------------------------------------------------------- case / file types
CASE_TYPES = [
    {"id": "CT-IND", "name_ar": "تسجيل مستفيد جديد", "name_en": "New independent beneficiary",
     "description_ar": "يستخدم للمستفيد المستقل الذي تجاوز عمره 18 عاما"},
    {"id": "CT-FOSTER", "name_ar": "تسجيل اسرة بديلة", "name_en": "Foster / alternative family",
     "description_ar": "يستخدم للاسر الحاضنة او البديلة التي ترعى يتيم او يتيمة"},
]

# ---------------------------------------------------------------- the 10 form sections
FORM_SECTIONS = [
    {"order": 1, "id": "SEC-BASIC", "name_ar": "البيانات الاساسية", "name_en": "Basic data",
     "fields": ["full_name_ar", "national_id", "birth_date", "gender", "marital_status",
                "orphan_category_id", "nationality"]},
    {"order": 2, "id": "SEC-EXTRA", "name_ar": "البيانات الاضافية", "name_en": "Additional data",
     "fields": ["dependents_count", "income_sources", "has_social_security", "has_citizen_account"]},
    {"order": 3, "id": "SEC-JOIN", "name_ar": "بيانات الانضمام للجمعية", "name_en": "Association joining data",
     "fields": ["join_reason", "referral_source", "previous_support"]},
    {"order": 4, "id": "SEC-BANK", "name_ar": "البيانات البنكية", "name_en": "Bank data",
     "fields": ["bank_name", "iban", "account_holder_name"]},
    {"order": 5, "id": "SEC-CONTACT", "name_ar": "بيانات الاتصال", "name_en": "Contact data",
     "fields": ["mobile", "alt_mobile", "email", "whatsapp"]},
    {"order": 6, "id": "SEC-EDU", "name_ar": "المؤهل والوظيفة", "name_en": "Qualification and job",
     "fields": ["education_level", "employment_status", "employer", "monthly_salary"]},
    {"order": 7, "id": "SEC-HOUSING", "name_ar": "بيانات السكن", "name_en": "Housing data",
     "fields": ["city", "district", "housing_type", "ownership_proof_type", "rooms",
                "monthly_rent", "monthly_bills"]},
    {"order": 8, "id": "SEC-HEALTH", "name_ar": "البيانات الصحية", "name_en": "Health data",
     "fields": ["chronic_conditions", "disability", "has_health_insurance", "monthly_medication_cost"]},
    {"order": 9, "id": "SEC-DEP", "name_ar": "بيانات التابعين", "name_en": "Dependents data",
     "fields": ["dependents"]},
    {"order": 10, "id": "SEC-ATTACH", "name_ar": "المرفقات", "name_en": "Attachments",
     "fields": ["documents"]},
]

# ---------------------------------------------------------------- housing ownership proofs
HOUSING_PROOFS = [
    {"id": "HP-RENT", "name_ar": "عقد ايجار"},
    {"id": "HP-DEED", "name_ar": "صك ملكية"},
    {"id": "HP-MORT", "name_ar": "عقد رهن"},
    {"id": "HP-INHERIT", "name_ar": "صك ورثة"},
    {"id": "HP-WAQF", "name_ar": "صك وقف"},
    {"id": "HP-CHARITY", "name_ar": "عقد انتفاع خيري"},
    {"id": "HP-OTHER", "name_ar": "اي مستند رسمي يثبت طبيعة السكن"},
]

# ---------------------------------------------------------------- monthly obligations
OBLIGATION_TYPES = [
    {"id": "OB-LOAN", "name_ar": "القروض والسلفات التمويلية من البنوك او الجهات التمويلية المعتمدة", "counted": True},
    {"id": "OB-CARD", "name_ar": "البطاقات الائتمانية (الفيزا ونحوها)", "counted": True},
    {"id": "OB-RENT", "name_ar": "سداد الايجار", "counted": True},
    {"id": "OB-UTIL", "name_ar": "فواتير الكهرباء والمياه", "counted": True},
    {"id": "OB-TELECOM", "name_ar": "فواتير الجوال والانترنت", "counted": True},
    {"id": "OB-BNPL", "name_ar": "الالتزامات المرتبطة بخدمات (تابي - تمارا)", "counted": True},
    {"id": "OB-NAJIZ", "name_ar": "اوامر التنفيذ في منصة ناجز", "counted": True},
    {"id": "OB-SIMAH", "name_ar": "اي التزام مالي موثق ضمن تقرير سمة الائتماني", "counted": True},
]

# ---------------------------------------------------------------- per-person monthly costs
PERSON_COST_TYPES = [
    {"id": "PC-FUEL", "name_ar": "البنزين", "counted": True},
    {"id": "PC-TRANSPORT", "name_ar": "تكاليف المواصلات (اوبر - كريم - جيني)", "counted": True},
    {"id": "PC-GROCERY", "name_ar": "المصروفات التموينية (المقاضي)", "counted": True},
    {"id": "PC-INFANT", "name_ar": "الحليب والاحتياجات الشهرية للرضيع (ان وجد)", "counted": True},
    {"id": "PC-PERSONAL", "name_ar": "السلفات الشخصية غير الموثقة والشهرية", "counted": True},
    {"id": "PC-LUXURY", "name_ar": "المصاريف الكمالية او الترفيهية", "counted": False,
     "note_ar": "لا يتم احتساب المصاريف الكمالية او الترفيهية ضمن الفواتير الشهرية المعتمدة"},
]

# ---------------------------------------------------------------- required documents
DOCUMENT_TYPES = [
    {"id": "DOC-ID", "name_ar": "صورة الهوية الوطنية", "required_for": ["CT-IND", "CT-FOSTER"], "mandatory": True},
    {"id": "DOC-ORPHAN", "name_ar": "وثيقة اثبات فئة اليتم", "required_for": ["CT-IND", "CT-FOSTER"], "mandatory": True},
    {"id": "DOC-FAMILY", "name_ar": "سجل الاسرة / كرت العائلة", "required_for": ["CT-IND", "CT-FOSTER"], "mandatory": True},
    {"id": "DOC-HOUSING", "name_ar": "اثبات ملكية السكن", "required_for": ["CT-IND", "CT-FOSTER"], "mandatory": True},
    {"id": "DOC-SALARY", "name_ar": "تعريف الراتب", "required_for": ["CT-IND", "CT-FOSTER"], "mandatory": True,
     "na_allowed": True, "na_note_ar": "في حال عدم التوفر يرفق صورة مكتوب عليها: لا يوجد"},
    {"id": "DOC-SOCIAL", "name_ar": "مشهد الضمان الاجتماعي", "required_for": ["CT-IND", "CT-FOSTER"], "mandatory": True,
     "ineligible_allowed": True, "na_note_ar": "في حال عدم الانطباق يرفق صورة توضح: عدم الاهلية"},
    {"id": "DOC-CITIZEN", "name_ar": "حساب المواطن", "required_for": ["CT-IND", "CT-FOSTER"], "mandatory": True,
     "ineligible_allowed": True, "na_note_ar": "في حال عدم الانطباق يرفق صورة توضح: عدم الاهلية"},
    {"id": "DOC-SIMAH", "name_ar": "تقرير سمة الائتماني", "required_for": ["CT-IND", "CT-FOSTER"], "mandatory": True},
    {"id": "DOC-MEDICAL", "name_ar": "تقارير طبية", "required_for": ["CT-IND", "CT-FOSTER"], "mandatory": False},
    {"id": "DOC-CUSTODY", "name_ar": "صك حضانة / وثيقة الاحتضان", "required_for": ["CT-FOSTER"], "mandatory": True},
]

DOC_STATUSES = ["missing", "uploaded", "verified", "rejected", "not_available", "ineligible"]

# ---------------------------------------------------------------- the 5 programs + 43 request types
PROGRAMS = [
    {
        "id": "PRG-ILM", "name_ar": "برنامج علم", "name_en": "Ilm (Education) Program",
        "description_ar": "دعم التعليم العام والعالي والمستلزمات والاجهزة التعليمية",
        "requests": [
            ("REQ-ILM-01", "طلب منحة دراسية (التعليم العام - التعليم العالي)", 5000),
            ("REQ-ILM-02", "طلب سداد الرسوم الدراسية", 8000),
            ("REQ-ILM-03", "طلب مستلزمات تعليمية", 800),
            ("REQ-ILM-04", "طلب اجهزة تعليمية", 3000),
            ("REQ-ILM-05", "طلب كسوة مدرسية", 700),
            ("REQ-ILM-06", "طلب سداد رسوم اختبارات مهنية او اكاديمية", 1200),
            ("REQ-ILM-07", "طلب برنامج لتنمية القدرات والمهارات التعليمية والحسابية والذكاء", 2500),
        ],
    },
    {
        "id": "PRG-TRN", "name_ar": "برنامج التاهيل والتدريب", "name_en": "Rehabilitation and Training Program",
        "description_ar": "التدريب المهني والتمكين الوظيفي ودعم المشاريع الصغيرة",
        "requests": [
            ("REQ-TRN-01", "طلب دورة تدريبية", 3500),
            ("REQ-TRN-02", "طلب شهادة مهنية", 2500),
            ("REQ-TRN-03", "طلب سداد رسوم رخصة قيادة", 2000),
            ("REQ-TRN-04", "طلب خطاب تدريب تعاوني لجهة خارجية", 0),
            ("REQ-TRN-05", "طلب خطاب شفاعة للتوظيف", 0),
            ("REQ-TRN-06", "طلب تاهيل لسوق العمل", 4000),
            ("REQ-TRN-07", "طلب تمكين وظيفي", 4000),
            ("REQ-TRN-08", "طلب استشارة مهنية", 0),
            ("REQ-TRN-09", "طلب دعم المشاريع الصغيرة والاسر المنتجة", 15000),
        ],
    },
    {
        "id": "PRG-QOL", "name_ar": "برنامج جودة حياة", "name_en": "Quality of Life Program",
        "description_ar": "الارشاد النفسي والاجتماعي والاسري والدعم العلاجي والمناسبات",
        "requests": [
            ("REQ-QOL-01", "طلب خدمات الارشاد (نفسي - اجتماعي - اسري - زواجي)", 0),
            ("REQ-QOL-02", "طلب الانضمام الى مجموعة دعم", 0),
            ("REQ-QOL-03", "طلب احالة علاجية", 6000),
            ("REQ-QOL-04", "طلب خطاب تعريف بالمستفيد", 0),
            ("REQ-QOL-05", "طلب زواج", 20000),
            ("REQ-QOL-06", "طلب دعم زواج", 15000),
            ("REQ-QOL-07", "طلب نشاط اجتماعي", 1000),
            ("REQ-QOL-08", "طلب رحلة ترفيهية", 1500),
            ("REQ-QOL-09", "طلب فعالية", 1000),
        ],
    },
    {
        "id": "PRG-HSG", "name_ar": "برنامج سكني", "name_en": "Housing Program",
        "description_ar": "دعم الايجار والتملك والترميم والتاثيث والاحتياجات المعيشية",
        "requests": [
            ("REQ-HSG-01", "طلب سداد ايجار", 24000),
            ("REQ-HSG-02", "طلب تملك مسكن", 300000),
            ("REQ-HSG-03", "طلب ترميم مسكن", 25000),
            ("REQ-HSG-04", "طلب تاثيث مسكن", 15000),
            ("REQ-HSG-05", "طلب اجهزة منزلية", 6000),
            ("REQ-HSG-06", "طلب سداد فواتير الكهرباء والمياه", 2500),
            ("REQ-HSG-07", "طلب سلة غذائية", 600),
            ("REQ-HSG-08", "طلب بطاقات شرائية للغذاء", 1000),
            ("REQ-HSG-09", "طلب كسوة عيد", 800),
            ("REQ-HSG-10", "طلب احتياج سكني طارئ", 5000),
        ],
    },
    {
        "id": "PRG-VAL", "name_ar": "برنامج قيمي", "name_en": "Values Program",
        "description_ar": "البرامج التربوية والتوعوية والدينية والفعاليات الوطنية والتطوع",
        "requests": [
            ("REQ-VAL-01", "طلب رحلة وطنية", 2000),
            ("REQ-VAL-02", "طلب برنامج قيمي", 1000),
            ("REQ-VAL-03", "طلب برنامج تربوي", 1000),
            ("REQ-VAL-04", "طلب برنامج توعوي", 800),
            ("REQ-VAL-05", "طلب برنامج ديني", 800),
            ("REQ-VAL-06", "طلب فعالية وطنية", 1200),
            ("REQ-VAL-07", "طلب فعالية مجتمعية", 1200),
            ("REQ-VAL-08", "طلب فرصة تطوعية", 0),
        ],
    },
]

# ---------------------------------------------------------------- CRM (from screenshots)
TICKET_STATUSES = [
    {"id": "open", "name_ar": "مفتوح", "kanban": True, "order": 1},
    {"id": "in_progress", "name_ar": "جاري العمل", "kanban": True, "order": 2},
    {"id": "waiting_customer", "name_ar": "بانتظار العميل", "kanban": True, "order": 3},
    {"id": "replied", "name_ar": "تم الرد", "kanban": True, "order": 4},
    {"id": "expired", "name_ar": "منتهية المدة", "kanban": False, "order": 5},
    {"id": "closed", "name_ar": "مغلق", "kanban": False, "order": 6},
]

DEPARTMENTS = [
    {"id": "DEP-BEN", "name_ar": "ادارة المستفيدون", "sla_hours": 24},
    {"id": "DEP-IT", "name_ar": "تقنية المعلومات", "sla_hours": 24},
    {"id": "DEP-KAF", "name_ar": "كفالة يتيم مقيدة", "sla_hours": 48},
    {"id": "DEP-EVT", "name_ar": "الفعاليات والانشطة", "sla_hours": 48},
    {"id": "DEP-PRG", "name_ar": "البرامج والمشاريع", "sla_hours": 48},
    {"id": "DEP-FIN", "name_ar": "الشؤون المالية", "sla_hours": 48},
]

STAFF = [
    {"id": "STF-01", "name_ar": "شادن الفصيلي", "role_ar": "مدير النظام", "department_id": "DEP-BEN"},
    {"id": "STF-02", "name_ar": "نورة ابراهيم", "role_ar": "مسؤولة خدمات المستفيدين", "department_id": "DEP-BEN"},
    {"id": "STF-03", "name_ar": "هند العتيبي", "role_ar": "اخصائية برنامج سكني", "department_id": "DEP-PRG"},
    {"id": "STF-04", "name_ar": "عمر الشمري", "role_ar": "باحث اجتماعي", "department_id": "DEP-BEN"},
    {"id": "STF-05", "name_ar": "ليلى القحطاني", "role_ar": "اخصائية نفسية", "department_id": "DEP-PRG"},
    {"id": "STF-06", "name_ar": "خالد الدوسري", "role_ar": "محاسب", "department_id": "DEP-FIN"},
]

# ---------------------------------------------------------------- casework
CASE_STEPS = [
    {"id": "CS-DESK", "name_ar": "المقابلة المكتبية", "name_en": "Office interview"},
    {"id": "CS-ONLINE", "name_ar": "المقابلة الالكترونية / الاونلاين", "name_en": "Online interview"},
    {"id": "CS-FIELD", "name_ar": "الزيارة الميدانية", "name_en": "Field visit"},
    {"id": "CS-PSYCH", "name_ar": "تقييم الوضع النفسي / مقاييس نفسية", "name_en": "Psychological assessment"},
]

DECISIONS = [
    {"id": "accepted", "name_ar": "قبول الطلب"},
    {"id": "docs_required", "name_ar": "طلب استكمال مستندات"},
    {"id": "declined", "name_ar": "الاعتذار"},
]

# ---------------------------------------------------------------- notification templates
TEMPLATES = [
    {"id": "TPL-OTP", "channel": "sms", "name_ar": "رمز التحقق",
     "body_ar": "رمز التحقق الخاص بك في جمعية كيان للايتام هو {code}. لا تشاركه مع احد."},
    {"id": "TPL-REG-OK", "channel": "whatsapp", "name_ar": "تاكيد انشاء الملف",
     "body_ar": "تم انشاء ملفك في نظام جمعية كيان برقم {file_no}. الرجاء استكمال بقية الاقسام والمرفقات."},
    {"id": "TPL-DOCS", "channel": "whatsapp", "name_ar": "استكمال مستندات",
     "body_ar": "طلبك رقم {request_no} يحتاج استكمال المستندات التالية: {docs}. نامل رفعها عبر حسابك في النظام."},
    {"id": "TPL-ACCEPT", "channel": "whatsapp", "name_ar": "قبول الطلب",
     "body_ar": "نبشركم بقبول طلبكم رقم {request_no} ضمن {program}. سيتم التواصل معكم بخصوص اجراءات الصرف."},
    {"id": "TPL-DECLINE", "channel": "whatsapp", "name_ar": "الاعتذار",
     "body_ar": "نعتذر عن عدم التمكن من قبول طلبكم رقم {request_no} في الوقت الحالي. نشكر تواصلكم مع جمعية كيان."},
    {"id": "TPL-VISIT", "channel": "whatsapp", "name_ar": "موعد زيارة ميدانية",
     "body_ar": "تم تحديد موعد زيارة ميدانية لدراسة حالتكم بتاريخ {date}. الرجاء التاكيد."},
    {"id": "TPL-PAY", "channel": "sms", "name_ar": "اشعار صرف",
     "body_ar": "تم صرف مبلغ {amount} ريال لحسابكم المسجل لدى جمعية كيان عن {reason}."},
]

# ---------------------------------------------------------------- FAQs (from the guide)
FAQS = [
    ("FAQ-01", "registration", "كيف اسجل في نظام جمعية كيان؟",
     "ادخل الى موقع kayan.org.sa واضغط على ايقونة المستخدم ثم اختر تسجيل حساب جديد وادخل رقم الجوال ورمز التحقق وكلمة المرور.",
     "How do I register?", "Go to kayan.org.sa, click the user icon, choose create new account, then enter your mobile, the verification code, and a password."),
    ("FAQ-02", "registration", "تظهر لي رسالة رقم الجوال مسجل مسبقا فماذا افعل؟",
     "هذا يعني ان لديك حساب سابق. قم بتسجيل الدخول مباشرة، وان نسيت كلمة المرور تواصل مع خدمات المستفيدين على 0506094154 لان الكود قد يصل متاخرا.",
     "It says my number is already registered.", "You already have an account. Log in directly, or contact beneficiary services on 0506094154 if you forgot the password, as the code may arrive late."),
    ("FAQ-03", "eligibility", "من هي الفئة التي تخدمها جمعية كيان؟",
     "جمعية كيان للايتام تخدم الايتام ذوي الظروف الخاصة (مجهولي الابوين). يتم التحقق من الفئة قبل استكمال الطلب.",
     "Who is eligible?", "Kayan serves orphans with special circumstances (of unknown parentage). Category is verified before the request proceeds."),
    ("FAQ-04", "forms", "ما الفرق بين تسجيل مستفيد جديد وتسجيل اسرة بديلة؟",
     "تسجيل مستفيد جديد يستخدم للمستفيد المستقل الذي تجاوز عمره 18 عاما، اما تسجيل اسرة بديلة فيستخدم للاسر الحاضنة او البديلة التي ترعى يتيم او يتيمة.",
     "Difference between the two forms?", "New beneficiary is for an independent beneficiary over 18; foster family is for a host/alternative family caring for an orphan."),
    ("FAQ-05", "dependents", "من يجب اضافته في بيانات التابعين؟",
     "كل فرد يسكن معك في نفس المنزل: الزوج او الزوجة، الابناء او البنات، الاخ او الاخت، الام الحاضنة، احد الاخوة الايتام ذوي الظروف الخاصة، او اي شخص اخر يسكن معك بشكل دائم.",
     "Who must be added as a dependent?", "Everyone living in the same home: spouse, children, siblings, foster mother, orphan siblings with special circumstances, or anyone permanently residing with you."),
    ("FAQ-06", "dependents", "لماذا يجب اضافة جميع التابعين؟",
     "لان ذلك يساعد الجمعية على تكوين صورة واضحة عن الحالة الاسرية والمعيشية، ودراسة الاحتياج بشكل ادق، واحتساب عدد افراد الاسرة المقيمين في نفس السكن، وربط الخدمات المناسبة لجميع افراد الاسرة، وتقييم الحالة السكنية والاجتماعية بصورة صحيحة.",
     "Why add all dependents?", "It gives a clear picture of the household, sharpens the needs assessment, counts residents in the home, links suitable services to each member, and assesses the housing and social situation correctly."),
    ("FAQ-07", "housing", "ما المقصود باثبات ملكية السكن؟",
     "اي مستند او عقد يوضح نوع السكن الحالي المرتبط بالمستفيد او الاسرة، مثل عقد ايجار او صك ملكية او عقد رهن او صك ورثة او صك وقف او عقد انتفاع خيري او اي مستند رسمي يثبت طبيعة السكن.",
     "What counts as housing proof?", "Any document or contract showing the current housing type: rental contract, title deed, mortgage, inheritance deed, endowment deed, charitable usufruct, or any official document proving the housing arrangement."),
    ("FAQ-08", "finance", "ما المقصود بالفواتير الشهرية؟",
     "اجمالي الالتزامات والمبالغ المالية الشهرية الموثقة على المستفيد او الاسرة، مثل القروض والبطاقات الائتمانية وسداد الايجار وفواتير الكهرباء والمياه والجوال والانترنت والتزامات تابي وتمارا واوامر التنفيذ في ناجز واي التزام موثق في تقرير سمة.",
     "What are monthly bills?", "Total documented monthly obligations: loans, credit cards, rent, utilities, telecom, Tabby/Tamara, Najiz enforcement orders, and anything documented in the SIMAH credit report."),
    ("FAQ-09", "finance", "ما هي التكاليف الشهرية للفرد؟",
     "المصاريف الاساسية الشهرية اللازمة للمعيشة وليست المصروفات الكمالية، مثل البنزين والمواصلات والمقاضي وحليب الرضيع والسلفات الشخصية. لا يتم احتساب المصاريف الكمالية او الترفيهية.",
     "What are per-person monthly costs?", "Essential living costs, not luxuries: fuel, transport, groceries, infant milk, undocumented personal loans. Luxury or entertainment spending is not counted."),
    ("FAQ-10", "documents", "ماذا افعل اذا كان المستند لا ينطبق علي؟",
     "اذا كان المستند لا ينطبق عليك مثل الضمان الاجتماعي او حساب المواطن، يرجى ارفاق صورة توضح عدم الاهلية. واذا كان المستند غير متوفر مثل تعريف الراتب، يرجى ارفاق صورة مكتوب عليها لا يوجد.",
     "What if a document does not apply to me?", "If it does not apply (e.g. social security, citizen account) attach an image showing ineligibility. If unavailable (e.g. salary certificate) attach an image marked 'not available'."),
    ("FAQ-11", "requests", "كيف اقدم طلب دعم؟",
     "بعد اكتمال بيانات حسابك كمستفيد واعتماده من قبل المسؤولة بالجمعية، اختر طلب الدعم من قائمة الخدمات الالكترونية، ثم اختر البرنامج والطلب المناسب وعبئ الاستبيان.",
     "How do I submit a support request?", "Once your beneficiary file is complete and approved by the association officer, choose Support Request from the e-services menu, pick the program and request type, and fill the questionnaire."),
    ("FAQ-12", "requests", "ما هي برامج الجمعية؟",
     "خمسة برامج: برنامج علم، برنامج التاهيل والتدريب، برنامج جودة حياة، برنامج سكني، وبرنامج قيمي. ويندرج تحت كل برنامج مشاريع وطلبات متعددة.",
     "What are the programs?", "Five: Ilm (education), Rehabilitation and Training, Quality of Life, Housing, and Values. Each contains multiple projects and request types."),
    ("FAQ-13", "casework", "كيف تتم دراسة الاحتياج؟",
     "يتم تقييم الاحتياج من خلال وسائل متعددة على سبيل المثال لا الحصر: المقابلات المكتبية والالكترونية والزيارات الميدانية والمقاييس النفسية، ثم تعرض الحالة على اللجنة المختصة.",
     "How is the need assessed?", "Through several means including office and online interviews, field visits, and psychological scales; the case is then presented to the specialized committee."),
    ("FAQ-14", "casework", "كيف اعرف نتيجة طلبي؟",
     "سيتم اشعارك بالقرار سواء كان قبول الطلب او طلب استكمال مستندات او الاعتذار، وذلك عبر الرد في الواتساب وايضا رسالة نصية. ويمكنك متابعة طلباتك من خلال حسابك في النظام.",
     "How do I learn the outcome?", "You are notified of the decision (accepted, documents required, or declined) via WhatsApp reply and SMS. You can also track requests in your account."),
    ("FAQ-15", "general", "هل التسجيل في النظام يعني قبول الطلب؟",
     "لا. التسجيل في النظام لا يعني قبول الطلب. جميع الطلبات تخضع لدراسة وتقييم، ويتم تقديم الدعم وفق الاحتياج والاولوية.",
     "Does registering mean approval?", "No. Registration does not mean approval. All requests are studied and evaluated, and support is provided according to need and priority."),
    ("FAQ-16", "general", "كيف اتواصل مع الجمعية؟",
     "قسم خدمات المستفيدين على الواتساب 0506094154، او هاتف 0533155582 و 0112925559، او البريد info@kayan.org.sa، والموقع kayan.org.sa. العنوان الرياض حي الفلاح.",
     "How do I contact Kayan?", "Beneficiary services on WhatsApp 0506094154, phones 0533155582 and 0112925559, email info@kayan.org.sa, site kayan.org.sa. Address: Riyadh, Al Falah district."),
    ("FAQ-17", "documents", "كيف استخرج مشهد الضمان الاجتماعي؟",
     "ادخل الى موقع نظام الضمان الاجتماعي المطور في وزارة الموارد البشرية، سجل الدخول، ومن القائمة الرئيسية اختر الخدمات الالكترونية ثم طلب مشهد اعانة او اعاشة، ثم اضغط اصدار المشهد ثم عرض او تحميل ليصلك بصيغة PDF. ويشترط ان يتضمن المشهد اسماء جميع التابعين وقيمة مبلغ الاعانة.",
     "How do I get the social security statement?", "Log in to the developed Social Security system on the HRSD site, choose E-Services then request a support/subsistence statement, click issue then view/download for a PDF. It must include all dependents' names and the support amount."),
    ("FAQ-18", "general", "متى يتم تقديم الدعم؟",
     "يتم تقديم الدعم وفق الاحتياج والاولوية. ودقة البيانات تساعد في سرعة دراسة الطلب، بينما عدم اكتمال البيانات والمستندات قد يؤثر على دراسة الحالة.",
     "When is support provided?", "According to need and priority. Accurate data speeds up the review, while incomplete data or documents may affect the case study."),
]

CITIES = [
    ("الرياض", "Riyadh", ["حي الفلاح", "حي النرجس", "حي العزيزية", "حي الشفا", "حي الملز"]),
    ("جدة", "Jeddah", ["حي السلامة", "حي الروضة", "حي النزهة", "حي الصفا"]),
    ("الدمام", "Dammam", ["حي الفيصلية", "حي الشاطئ", "حي المزروعية"]),
    ("مكة المكرمة", "Mecca", ["حي العزيزية", "حي الششة", "حي الزاهر"]),
    ("المدينة المنورة", "Medina", ["حي قباء", "حي العوالي", "حي الحرة الشرقية"]),
    ("بريدة", "Buraidah", ["حي الصفراء", "حي الاسكان", "حي الروضة"]),
]
