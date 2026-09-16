/**
 * Bilingual labels for the backend's reference data and enum codes.
 *
 * The API is Arabic-first: it returns codes (status, stage, program id…) and,
 * for many of them, only an Arabic label (`*_ar`). The UI never renders those
 * Arabic labels directly in English mode — it resolves the code (or the Arabic
 * label, via a normalised reverse index) against this catalog instead.
 */
import type { Locale } from "./config";

type Entry = { ar: string; en: string };
type Table = Record<string, Entry>;

export const catalog = {
  ticketStatus: {
    open: { ar: "مفتوح", en: "Open" },
    in_progress: { ar: "جاري العمل", en: "In progress" },
    waiting_customer: { ar: "بانتظار العميل", en: "Waiting on customer" },
    replied: { ar: "تم الرد", en: "Replied" },
    expired: { ar: "منتهية المدة", en: "Expired" },
    closed: { ar: "مغلق", en: "Closed" },
  },
  fileStatus: {
    draft: { ar: "مسودة", en: "Draft" },
    submitted: { ar: "مرفوع", en: "Submitted" },
    under_review: { ar: "قيد المراجعة", en: "Under review" },
    approved: { ar: "معتمد", en: "Approved" },
    rejected: { ar: "مرفوض", en: "Rejected" },
  },
  stage: {
    submitted: { ar: "تم التقديم", en: "Submitted" },
    under_study: { ar: "قيد الدراسة", en: "Under study" },
    committee: { ar: "لدى اللجنة", en: "With committee" },
    decided: { ar: "صدر القرار", en: "Decided" },
  },
  decision: {
    accepted: { ar: "قبول الطلب", en: "Accepted" },
    docs_required: { ar: "استكمال مستندات", en: "Documents required" },
    declined: { ar: "اعتذار", en: "Declined" },
  },
  disbursementStatus: {
    scheduled: { ar: "مجدول", en: "Scheduled" },
    pending: { ar: "معلّق", en: "Pending" },
    pending_approval: { ar: "بانتظار الاعتماد", en: "Pending approval" },
    approved: { ar: "معتمد", en: "Approved" },
    paid: { ar: "مصروف", en: "Paid" },
  },
  channel: {
    whatsapp: { ar: "واتساب", en: "WhatsApp" },
    call: { ar: "اتصال هاتفي", en: "Phone call" },
    portal: { ar: "الموقع", en: "Website" },
  },
  channelShort: {
    whatsapp: { ar: "واتساب", en: "WhatsApp" },
    call: { ar: "اتصال", en: "Call" },
    portal: { ar: "الموقع", en: "Website" },
  },
  priority: {
    high: { ar: "عاجل", en: "Urgent" },
    normal: { ar: "عادي", en: "Normal" },
    low: { ar: "منخفض", en: "Low" },
  },
  caseType: {
    "CT-FOSTER": { ar: "أسرة بديلة", en: "Foster family" },
    "CT-IND": { ar: "مستفيد مستقل", en: "Independent beneficiary" },
    "CT-NEW": { ar: "مستفيد مستقل", en: "Independent beneficiary" },
  },
  orphanCategory: {
    "OC-UNK": { ar: "يتيم مجهول الأبوين", en: "Orphan of unknown parentage" },
    "OC-SPEC": { ar: "يتيم ذو ظروف خاصة", en: "Orphan with special circumstances" },
    "OC-FATHER": { ar: "يتيم الأب", en: "Paternal orphan" },
    "OC-MOTHER": { ar: "يتيم الأم", en: "Maternal orphan" },
    "OC-BOTH": { ar: "يتيم الأبوين", en: "Orphan of both parents" },
  },
  department: {
    "DEP-BEN": { ar: "إدارة المستفيدين", en: "Beneficiary Services" },
    "DEP-IT": { ar: "تقنية المعلومات", en: "Information Technology" },
    "DEP-KAF": { ar: "كفالة يتيم مقيدة", en: "Restricted Orphan Sponsorship" },
    "DEP-EVT": { ar: "الفعاليات والأنشطة", en: "Events & Activities" },
    "DEP-PRG": { ar: "البرامج والمشاريع", en: "Programs & Projects" },
    "DEP-FIN": { ar: "الشؤون المالية", en: "Finance" },
    "DEPT-SERVICES": { ar: "خدمات المستفيدين", en: "Beneficiary Services" },
    "DEPT-PROGRAMS": { ar: "البرامج والمشاريع", en: "Programs & Projects" },
    "DEPT-FINANCE": { ar: "الشؤون المالية", en: "Finance" },
    "DEPT-COMPLAINTS": { ar: "الشكاوى", en: "Complaints" },
  },
  program: {
    "PRG-ILM": { ar: "برنامج علم", en: "Ilm (Education) Program" },
    "PRG-TRN": { ar: "برنامج التأهيل والتدريب", en: "Rehabilitation & Training Program" },
    "PRG-QOL": { ar: "برنامج جودة حياة", en: "Quality of Life Program" },
    "PRG-HSG": { ar: "برنامج سكني", en: "Housing Program" },
    "PRG-VAL": { ar: "برنامج قيمي", en: "Values Program" },
  },
  programDescription: {
    "PRG-ILM": {
      ar: "دعم التعليم العام والعالي والمستلزمات والأجهزة التعليمية",
      en: "Support for school and higher education, supplies and learning devices",
    },
    "PRG-TRN": {
      ar: "التدريب المهني والتمكين الوظيفي ودعم المشاريع الصغيرة",
      en: "Vocational training, job enablement and small-business support",
    },
    "PRG-QOL": {
      ar: "الإرشاد النفسي والاجتماعي والأسري والدعم العلاجي والمناسبات",
      en: "Psychological, social and family counselling, medical support and occasions",
    },
    "PRG-HSG": {
      ar: "دعم الإيجار والتملك والترميم والتأثيث والاحتياجات المعيشية",
      en: "Rent, home ownership, renovation, furnishing and living needs",
    },
    "PRG-VAL": {
      ar: "البرامج التربوية والتوعوية والدينية والفعاليات الوطنية والتطوع",
      en: "Educational, awareness and religious programs, national events and volunteering",
    },
  },
  requestType: {
    "REQ-ILM-01": { ar: "طلب منحة دراسية (التعليم العام - التعليم العالي)", en: "Scholarship (school / higher education)" },
    "REQ-ILM-02": { ar: "طلب سداد الرسوم الدراسية", en: "Tuition fee payment" },
    "REQ-ILM-03": { ar: "طلب مستلزمات تعليمية", en: "School supplies" },
    "REQ-ILM-04": { ar: "طلب أجهزة تعليمية", en: "Learning devices" },
    "REQ-ILM-05": { ar: "طلب كسوة مدرسية", en: "School uniform" },
    "REQ-ILM-06": { ar: "طلب سداد رسوم اختبارات مهنية أو أكاديمية", en: "Professional or academic exam fees" },
    "REQ-ILM-07": { ar: "طلب برنامج لتنمية القدرات والمهارات التعليمية والحسابية والذكاء", en: "Learning, numeracy and cognitive skills program" },
    "REQ-TRN-01": { ar: "طلب دورة تدريبية", en: "Training course" },
    "REQ-TRN-02": { ar: "طلب شهادة مهنية", en: "Professional certificate" },
    "REQ-TRN-03": { ar: "طلب سداد رسوم رخصة قيادة", en: "Driving licence fees" },
    "REQ-TRN-04": { ar: "طلب خطاب تدريب تعاوني لجهة خارجية", en: "Co-op training letter to an external party" },
    "REQ-TRN-05": { ar: "طلب خطاب شفاعة للتوظيف", en: "Employment recommendation letter" },
    "REQ-TRN-06": { ar: "طلب تأهيل لسوق العمل", en: "Job-market readiness" },
    "REQ-TRN-07": { ar: "طلب تمكين وظيفي", en: "Job enablement" },
    "REQ-TRN-08": { ar: "طلب استشارة مهنية", en: "Career consultation" },
    "REQ-TRN-09": { ar: "طلب دعم المشاريع الصغيرة والأسر المنتجة", en: "Small business & productive family support" },
    "REQ-QOL-01": { ar: "طلب خدمات الإرشاد (نفسي - اجتماعي - أسري - زواجي)", en: "Counselling (psychological / social / family / marital)" },
    "REQ-QOL-02": { ar: "طلب الانضمام إلى مجموعة دعم", en: "Join a support group" },
    "REQ-QOL-03": { ar: "طلب إحالة علاجية", en: "Medical referral" },
    "REQ-QOL-04": { ar: "طلب خطاب تعريف بالمستفيد", en: "Beneficiary introduction letter" },
    "REQ-QOL-05": { ar: "طلب زواج", en: "Marriage request" },
    "REQ-QOL-06": { ar: "طلب دعم زواج", en: "Marriage support" },
    "REQ-QOL-07": { ar: "طلب نشاط اجتماعي", en: "Social activity" },
    "REQ-QOL-08": { ar: "طلب رحلة ترفيهية", en: "Recreational trip" },
    "REQ-QOL-09": { ar: "طلب فعالية", en: "Event request" },
    "REQ-HSG-01": { ar: "طلب سداد إيجار", en: "Rent payment" },
    "REQ-HSG-02": { ar: "طلب تملك مسكن", en: "Home ownership" },
    "REQ-HSG-03": { ar: "طلب ترميم مسكن", en: "Home renovation" },
    "REQ-HSG-04": { ar: "طلب تأثيث مسكن", en: "Home furnishing" },
    "REQ-HSG-05": { ar: "طلب أجهزة منزلية", en: "Home appliances" },
    "REQ-HSG-06": { ar: "طلب سداد فواتير الكهرباء والمياه", en: "Electricity & water bills" },
    "REQ-HSG-07": { ar: "طلب سلة غذائية", en: "Food basket" },
    "REQ-HSG-08": { ar: "طلب بطاقات شرائية للغذاء", en: "Food purchase cards" },
    "REQ-HSG-09": { ar: "طلب كسوة عيد", en: "Eid clothing" },
    "REQ-HSG-10": { ar: "طلب احتياج سكني طارئ", en: "Emergency housing need" },
    "REQ-VAL-01": { ar: "طلب رحلة وطنية", en: "National trip" },
    "REQ-VAL-02": { ar: "طلب برنامج قيمي", en: "Values program" },
    "REQ-VAL-03": { ar: "طلب برنامج تربوي", en: "Educational program" },
    "REQ-VAL-04": { ar: "طلب برنامج توعوي", en: "Awareness program" },
    "REQ-VAL-05": { ar: "طلب برنامج ديني", en: "Religious program" },
    "REQ-VAL-06": { ar: "طلب فعالية وطنية", en: "National event" },
    "REQ-VAL-07": { ar: "طلب فعالية مجتمعية", en: "Community event" },
    "REQ-VAL-08": { ar: "طلب فرصة تطوعية", en: "Volunteering opportunity" },
  },
  documentType: {
    "DOC-ID": { ar: "صورة الهوية الوطنية", en: "National ID copy" },
    "DOC-ORPHAN": { ar: "وثيقة إثبات فئة اليتم", en: "Orphan category proof" },
    "DOC-FAMILY": { ar: "سجل الأسرة / كرت العائلة", en: "Family record / family card" },
    "DOC-HOUSING": { ar: "إثبات ملكية السكن", en: "Proof of housing" },
    "DOC-SALARY": { ar: "تعريف الراتب", en: "Salary certificate" },
    "DOC-SOCIAL": { ar: "مشهد الضمان الاجتماعي", en: "Social security statement" },
    "DOC-CITIZEN": { ar: "حساب المواطن", en: "Citizen Account statement" },
    "DOC-SIMAH": { ar: "تقرير سمة الائتماني", en: "SIMAH credit report" },
    "DOC-MEDICAL": { ar: "تقارير طبية", en: "Medical reports" },
    "DOC-CUSTODY": { ar: "صك حضانة / وثيقة الاحتضان", en: "Custody deed / foster document" },
  },
  formSection: {
    "SEC-BASIC": { ar: "البيانات الأساسية", en: "Basic information" },
    "SEC-EXTRA": { ar: "البيانات الإضافية", en: "Additional information" },
    "SEC-JOIN": { ar: "بيانات الانضمام للجمعية", en: "Membership details" },
    "SEC-BANK": { ar: "البيانات البنكية", en: "Bank details" },
    "SEC-CONTACT": { ar: "بيانات الاتصال", en: "Contact details" },
    "SEC-EDU": { ar: "المؤهل والوظيفة", en: "Qualification & employment" },
    "SEC-HOUSING": { ar: "بيانات السكن", en: "Housing details" },
    "SEC-HEALTH": { ar: "البيانات الصحية", en: "Health information" },
    "SEC-DEP": { ar: "بيانات التابعين", en: "Dependents" },
    "SEC-ATTACH": { ar: "المرفقات", en: "Attachments" },
  },
  city: {
    riyadh: { ar: "الرياض", en: "Riyadh" },
    jeddah: { ar: "جدة", en: "Jeddah" },
    makkah: { ar: "مكة المكرمة", en: "Makkah" },
    madinah: { ar: "المدينة المنورة", en: "Madinah" },
    dammam: { ar: "الدمام", en: "Dammam" },
    khobar: { ar: "الخبر", en: "Al Khobar" },
    dhahran: { ar: "الظهران", en: "Dhahran" },
    jubail: { ar: "الجبيل", en: "Jubail" },
    taif: { ar: "الطائف", en: "Taif" },
    buraydah: { ar: "بريدة", en: "Buraydah" },
    hail: { ar: "حائل", en: "Hail" },
    abha: { ar: "أبها", en: "Abha" },
    jouf: { ar: "الجوف", en: "Al Jouf" },
    najran: { ar: "نجران", en: "Najran" },
    baha: { ar: "الباحة", en: "Al Baha" },
    arar: { ar: "عرعر", en: "Arar" },
    sakaka: { ar: "سكاكا", en: "Sakaka" },
    tabuk: { ar: "تبوك", en: "Tabuk" },
    jazan: { ar: "جازان", en: "Jazan" },
    qassim: { ar: "القصيم", en: "Al Qassim" },
    khamis: { ar: "خميس مشيط", en: "Khamis Mushait" },
    yanbu: { ar: "ينبع", en: "Yanbu" },
    ahsa: { ar: "الأحساء", en: "Al Ahsa" },
    qatif: { ar: "القطيف", en: "Qatif" },
  },
  relationship: {
    spouse: { ar: "الزوج/الزوجة", en: "Spouse" },
    son: { ar: "ابن", en: "Son" },
    daughter: { ar: "ابنة", en: "Daughter" },
    brother: { ar: "أخ", en: "Brother" },
    sister: { ar: "أخت", en: "Sister" },
    father: { ar: "أب", en: "Father" },
    mother: { ar: "أم", en: "Mother" },
  },
  education: {
    primary: { ar: "ابتدائي", en: "Primary" },
    intermediate: { ar: "متوسط", en: "Intermediate" },
    secondary: { ar: "ثانوي", en: "Secondary" },
    university: { ar: "جامعي", en: "University" },
  },
  classification: {
    urgent: { ar: "عاجل", en: "Urgent" },
    normal: { ar: "عادي", en: "Normal" },
    routine: { ar: "اعتيادي", en: "Routine" },
    recurring: { ar: "متكرر", en: "Recurring" },
    seasonal: { ar: "موسمي", en: "Seasonal" },
  },
  gender: {
    M: { ar: "ذكر", en: "Male" },
    F: { ar: "أنثى", en: "Female" },
  },
  maritalStatus: {
    single: { ar: "أعزب/عزباء", en: "Single" },
    married: { ar: "متزوج/ة", en: "Married" },
    divorced: { ar: "مطلق/ة", en: "Divorced" },
    widowed: { ar: "أرمل/ة", en: "Widowed" },
  },
  employmentStatus: {
    employed: { ar: "موظف", en: "Employed" },
    self_employed: { ar: "عمل حر", en: "Self-employed" },
    unemployed: { ar: "بدون عمل", en: "Unemployed" },
    retired: { ar: "متقاعد", en: "Retired" },
    student: { ar: "طالب", en: "Student" },
  },
  housingType: {
    owned: { ar: "ملك", en: "Owned" },
    rented: { ar: "إيجار", en: "Rented" },
    family: { ar: "مع الأسرة", en: "With family" },
    government: { ar: "سكن حكومي", en: "Government housing" },
  },
  housingProof: {
    "HP-RENT": { ar: "عقد إيجار", en: "Rental contract" },
    "HP-DEED": { ar: "صك ملكية", en: "Title deed" },
    "HP-MORT": { ar: "عقد رهن", en: "Mortgage contract" },
    "HP-INHERIT": { ar: "صك ورثة", en: "Inheritance deed" },
    "HP-WAQF": { ar: "صك وقف", en: "Endowment deed" },
    "HP-CHARITY": { ar: "عقد انتفاع خيري", en: "Charitable use agreement" },
    "HP-OTHER": { ar: "مستند رسمي آخر", en: "Other official document" },
  },
  referralSource: {
    self: { ar: "بحث شخصي", en: "Found us directly" },
    social_media: { ar: "وسائل التواصل", en: "Social media" },
    charity: { ar: "جمعية أخرى", en: "Another charity" },
    government: { ar: "جهة حكومية", en: "Government entity" },
    other: { ar: "أخرى", en: "Other" },
  },
  caseStep: {
    "CS-DESK": { ar: "المقابلة المكتبية", en: "Office interview" },
    "CS-ONLINE": { ar: "المقابلة الإلكترونية / الأونلاين", en: "Online interview" },
    "CS-FIELD": { ar: "الزيارة الميدانية", en: "Field visit" },
    "CS-PSYCH": { ar: "تقييم الوضع النفسي / مقاييس نفسية", en: "Psychological assessment" },
  },
  caseStepStatus: {
    scheduled: { ar: "مجدولة", en: "Scheduled" },
    completed: { ar: "مكتملة", en: "Completed" },
  },
  enrollmentType: {
    one_time: { ar: "دفعة واحدة", en: "One-time payment" },
    monthly_recurring: { ar: "دفعات شهرية", en: "Monthly instalments" },
  },
  staffName: {
    "STF-01": { ar: "شادن الفصيلي", en: "Shaden Al-Fasaily" },
    "STF-02": { ar: "نورة إبراهيم", en: "Noura Ibrahim" },
    "STF-03": { ar: "هند العتيبي", en: "Hind Al-Otaibi" },
    "STF-04": { ar: "عمر الشمري", en: "Omar Al-Shammari" },
    "STF-05": { ar: "ليلى القحطاني", en: "Layla Al-Qahtani" },
    "STF-06": { ar: "خالد الدوسري", en: "Khalid Al-Dosari" },
  },
  role: {
    admin: { ar: "مدير النظام", en: "System admin" },
    services: { ar: "خدمات المستفيدين", en: "Beneficiary services" },
    caseworker: { ar: "باحث اجتماعي", en: "Case worker" },
    committee: { ar: "عضو اللجنة المختصة", en: "Committee member" },
    finance: { ar: "الشؤون المالية", en: "Finance" },
    agent: { ar: "الوكيل الذكي", en: "AI agent" },
  },
  staffRole: {
    admin: { ar: "مدير النظام", en: "System admin" },
    services: { ar: "مسؤولة خدمات المستفيدين", en: "Beneficiary services officer" },
    housing: { ar: "أخصائية برنامج سكني", en: "Housing program specialist" },
    researcher: { ar: "باحث اجتماعي", en: "Social researcher" },
    psychologist: { ar: "أخصائية نفسية", en: "Psychologist" },
    accountant: { ar: "محاسب", en: "Accountant" },
  },
  /** Placeholder names the backend uses instead of a real person's name. */
  personPlaceholder: {
    unregistered: { ar: "غير مسجل", en: "Unregistered" },
  },
} satisfies Record<string, Table>;

export type CatalogKind = keyof typeof catalog;

/**
 * Arabic spellings the backend uses that differ from our canonical label
 * (older seed data, undiacritised forms). Mapped to the catalog key.
 */
const aliases: Partial<Record<CatalogKind, Record<string, string>>> = {
  decision: { "الاعتذار": "declined", "طلب استكمال مستندات": "docs_required", "قبول": "accepted" },
  department: { "ادارة المستفيدون": "DEP-BEN" },
  relationship: { "زوج": "spouse", "زوجة": "spouse", "بنت": "daughter" },
};

/** Normalise Arabic for matching: drop diacritics/tatweel, unify alef, yaa and taa marbuta. */
export function normalizeArabic(s: string): string {
  return s
    .replace(/[ً-ْٰـ]/g, "")
    .replace(/[أإآٱ]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/ة/g, "ه")
    .replace(/\s+/g, " ")
    .trim();
}

const reverseIndex = new Map<CatalogKind, Map<string, string>>();

function reverseFor(kind: CatalogKind): Map<string, string> {
  let idx = reverseIndex.get(kind);
  if (!idx) {
    idx = new Map();
    const table = catalog[kind] as Table;
    for (const [key, entry] of Object.entries(table)) idx.set(normalizeArabic(entry.ar), key);
    for (const [ar, key] of Object.entries(aliases[kind] ?? {})) idx.set(normalizeArabic(ar), key);
    reverseIndex.set(kind, idx);
  }
  return idx;
}

/** Find the catalog key for an Arabic label coming from the API. */
export function keyFromArabic(kind: CatalogKind, arabic: string | null | undefined): string | undefined {
  if (!arabic) return undefined;
  return reverseFor(kind).get(normalizeArabic(arabic));
}

const ARABIC_RE = /[؀-ۿ]/;

/**
 * Resolve a label for `code` (or, when no code is available, for the API's
 * Arabic label) in the requested locale.
 *
 * Arabic mode prefers the catalog, then whatever Arabic the API sent.
 * English mode never falls back to Arabic when the value is a known term; for
 * unknown free text it returns the original string (it is user data).
 */
export function resolveLabel(
  locale: Locale,
  kind: CatalogKind,
  code?: string | null,
  arabic?: string | null,
): string | undefined {
  const table = catalog[kind] as Table;
  const key =
    (code && Object.hasOwn(table, code) ? code : undefined) ??
    keyFromArabic(kind, arabic) ??
    (code && ARABIC_RE.test(code) ? keyFromArabic(kind, code) : undefined);
  if (key) return table[key][locale];
  if (locale === "ar") return arabic ?? code ?? undefined;
  return code && !ARABIC_RE.test(code) ? humanize(code) : (arabic ?? code ?? undefined);
}

/** `under_review` → `Under review`; used only as a last resort for unknown codes. */
function humanize(code: string): string {
  const s = code.replace(/[_-]+/g, " ").trim().toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}
