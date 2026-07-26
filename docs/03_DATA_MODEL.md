# Data Model

33 JSON datasets in `data/`, UTF-8, Arabic-first, cross-referenced by id. Reference "today" is **2026-07-23**. All data is synthetic.

## Entity relationships

```
orphan_category ──┐
case_type ────────┤
                  ▼
            beneficiary ──┬──< dependent
            (10 sections) ├──< document ──> document_type
                          ├──1 financial_profile ──< obligation / person_cost
                          ├──< support_request ──> request_type ──> program
                          │        │
                          │        ├──1 case_study ──< step ──> case_step
                          │        └──1 committee_decision
                          │                 │
                          │                 ▼ (if accepted)
                          ├──< enrollment ──< disbursement ──1 payment
                          ├──< sponsorship ──> sponsor
                          ├──< ticket ──< ticket_message
                          ├──< call_session
                          └──< whatsapp_session

ticket ──> department ──> staff        event ──> program
```

## Core entities

### `beneficiaries.json` (40)
The central record. `id` (BEN-####), `file_no` (KY-####), `case_type` (CT-IND / CT-FOSTER), `status` (**draft → submitted → under_review → approved / rejected**), `orphan_category_id`, `eligibility_verified`, timestamps, and **`sections`** — a nested object keyed by the 10 form section ids:

| Section | Key fields |
|---|---|
| `SEC-BASIC` البيانات الأساسية | full_name_ar, national_id, birth_date, gender, marital_status, orphan_category_id, nationality |
| `SEC-EXTRA` البيانات الإضافية | dependents_count, income_sources[], has_social_security, has_citizen_account |
| `SEC-JOIN` بيانات الانضمام | join_reason, referral_source, previous_support |
| `SEC-BANK` البيانات البنكية | bank_name, iban, account_holder_name |
| `SEC-CONTACT` بيانات الاتصال | mobile, alt_mobile, email, whatsapp |
| `SEC-EDU` المؤهل والوظيفة | education_level, employment_status, employer, monthly_salary |
| `SEC-HOUSING` بيانات السكن | city, district, housing_type, ownership_proof_type, rooms, monthly_rent, monthly_bills |
| `SEC-HEALTH` البيانات الصحية | chronic_conditions, disability, has_health_insurance, monthly_medication_cost |
| `SEC-DEP` بيانات التابعين | → `dependents.json` |
| `SEC-ATTACH` المرفقات | → `documents.json` |

### `dependents.json` (104)
`beneficiary_id`, `name_ar`, `relationship_ar` (الزوج/الزوجة، ابن، ابنة، أخ، أخت، الأم الحاضنة، أخ يتيم ذو ظروف خاصة), birth_date, gender, `is_orphan`, education_stage, has_special_needs. **Household size = dependents + 1**, and it divides the per-capita calculation.

### `documents.json` (369)
One row per required document per file. `document_type_id`, `mandatory`, `status` ∈ **missing / uploaded / verified / rejected / not_available / ineligible**, `note_ar`. The last two encode the guide's rules: *لا يوجد* when a document is unavailable (salary certificate), *عدم الأهلية* when it doesn't apply (social security, citizen account).

### `financial_profiles.json` (40)
`monthly_income_sar` + breakdown; `obligations[]` (الفواتير الشهرية — loans, credit cards, rent, utilities, telecom, Tabby/Tamara, Najiz enforcement, SIMAH); `person_costs[]` (التكاليف الشهرية للفرد — fuel, transport, groceries, infant needs, personal loans); `household_size`; `net_monthly_sar`; `per_capita_monthly_sar`; `need_score` (0–100, higher = greater need). Luxury spending is defined but flagged `counted:false`.

## Programs & requests

### `programs.json` (5) + `request_types.json` (43)
The five programs and every request type beneath them, transcribed from the guide:

| Program | Requests |
|---|---|
| برنامج علم | 7 — منحة دراسية، سداد رسوم، مستلزمات، أجهزة، كسوة مدرسية، رسوم اختبارات، تنمية قدرات |
| برنامج التأهيل والتدريب | 9 — دورة، شهادة مهنية، رخصة قيادة، تدريب تعاوني، شفاعة توظيف، تأهيل، تمكين، استشارة، مشاريع صغيرة |
| برنامج جودة حياة | 9 — إرشاد، مجموعة دعم، إحالة علاجية، خطاب تعريف، زواج، دعم زواج، نشاط، رحلة، فعالية |
| برنامج سكني | 10 — سداد إيجار، تملك، ترميم، تأثيث، أجهزة، فواتير، سلة غذائية، بطاقات شرائية، كسوة عيد، طارئ |
| برنامج قيمي | 8 — رحلة وطنية، قيمي، تربوي، توعوي، ديني، فعالية وطنية، مجتمعية، تطوع |

Each request type carries `ceiling_sar` (approval ceiling), `kind` (cash/in-kind vs service/letter) and `recurring`.

### `support_requests.json` (45)
`beneficiary_id`, `request_type_id`, `title_ar`, `internal_classification` (عاجل/اعتيادي/متكرر/موسمي), **`case_description_ar`** (وصف الحالة — the beneficiary's own explanation; appended to, never overwritten), `requested_amount_sar`, `stage` ∈ submitted → under_study → committee → decided, `channel`.

## Casework

### `case_studies.json` (42)
`support_request_id`, `steps[]` — each a `case_step` (المقابلة المكتبية / الإلكترونية / الزيارة الميدانية / تقييم الوضع النفسي) with scheduled_at, status, assigned staff, `findings_ar`; plus `social_researcher_id` and `recommendation_ar`.

### `committee_decisions.json` (30)
`decision` ∈ **accepted / docs_required / declined** (قبول الطلب / طلب استكمال مستندات / الاعتذار), `approved_amount_sar`, committee date and members, `reason_ar`, `required_documents_ar`, and `notified_whatsapp` / `notified_sms` flags.

## Money

- **`enrollments.json`** (14) — links an accepted request to a program; `type` one_time or monthly_recurring, monthly amount, total approved, start/end.
- **`disbursements.json`** (14) — the schedule; `due_date`, `amount_sar`, `status` ∈ scheduled → approved → paid.
- **`payments.json`** (11) — settled transfers with `iban`, `bank_name`, `reference`.
- **`sponsors.json`** (15) / **`sponsorships.json`** (7) — الكفالة, restricted or unrestricted, monthly pledge.

## CRM & channels

- **`tickets.json`** (40) — `status` ∈ open / in_progress / waiting_customer / replied / expired / closed (مفتوح / جاري العمل / بانتظار العميل / تم الرد / منتهية المدة / مغلق), `department_id`, `channel`, `priority`, `assigned_staff_id`, `linked_request_id`. **`ticket_messages.json`** (78) is the conversation log.
- **`departments.json`** (6) — إدارة المستفيدون، تقنية المعلومات، كفالة يتيم مقيدة، الفعاليات والأنشطة، البرامج والمشاريع، الشؤون المالية — each with `sla_hours`.
- **`whatsapp_sessions.json`** (25) — `window_expires_at` drives the 24-hour rule.
- **`call_sessions.json`** (20) — SIP id, ANI, identified flag, dialect, duration, outcome, intent.

## Reference

`orphan_categories` (5, with `eligible` flag), `case_types` (2), `form_sections` (10), `housing_proofs` (7), `obligation_types` (8), `person_cost_types` (6), `document_types` (10), `ticket_statuses` (6), `case_steps` (4), `decisions` (3), `staff` (6), `templates` (7 WhatsApp/SMS), `faqs` (18 bilingual), `events` (6).

## Conventions

- **Money:** `*_sar` floats, SAR.
- **Phones:** stored `9665XXXXXXXX`; `store.norm_phone()` accepts `05…`, `+9665…`, `00966…`.
- **Timestamps:** ISO-8601 UTC with trailing `Z`; dates `YYYY-MM-DD`.
- **Arabic:** undiacritized, standard for ERP/UI text.
