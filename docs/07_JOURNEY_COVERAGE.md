# Journey Coverage — guide → prototype

Traceability map: every step in *"رحلة المستفيد في نظام جمعية كيان"* against the endpoint that implements it. Use this to verify nothing from the client's document was dropped.

| # | Guide step | Implemented by | Notes |
|---|---|---|---|
| 1 | الدخول إلى موقع كيان، أيقونة المستخدم | *(portal UI — out of scope)* | Agents replace this with conversation |
| 2 | تسجيل الدخول / إنشاء حساب (جوال + رمز تحقق + كلمة مرور) | `POST /registration/send-otp`, `/verify-otp` | OTP code returned for testing |
| 3 | رسالة "رقم الجوال مسجل مسبقاً" | `POST /registration/check-phone` | Returns the exact guidance incl. the 0506094154 fallback |
| 4 | الخدمات الإلكترونية: تسجيل مستفيد جديد / تحديث بياناتي | `POST /beneficiary/create-file`, `PATCH /section/{id}` | |
| 5 | اختيار النموذج: مستفيد جديد vs أسرة بديلة | `GET /reference/case-types`, `case_type` on create | CT-IND (18+ independent) / CT-FOSTER |
| 6 | أقسام نموذج البيانات العشرة | `GET /reference/form-sections`, `PATCH /section/{id}` | All 10 sections modelled with their fields |
| 7 | إضافة التابعين + لماذا يجب إضافتهم | `POST /beneficiary/{id}/dependents`, `FAQ-05`, `FAQ-06` | Household size feeds the need score |
| 8 | إثبات ملكية السكن (7 أنواع) | `GET /reference/housing-proofs`, `SEC-HOUSING.ownership_proof_type` | عقد إيجار، صك ملكية، رهن، ورثة، وقف، انتفاع خيري، أي مستند رسمي |
| 9 | المصروفات الشهرية / الفواتير (8 أنواع) | `GET /reference/obligation-types`, `POST /obligations` | Incl. تابي/تمارا، ناجز، سمة |
| 10 | التكاليف الشهرية للفرد + استبعاد الكماليات | `GET /reference/person-cost-types`, `POST /person-costs` | Luxury costs rejected with 409 |
| 11 | المستند لا ينطبق → "عدم الأهلية" | `PATCH /documents/{type}` status=`ineligible` | Only where the doc type permits it |
| 12 | المستند غير متوفر → "لا يوجد" | `PATCH /documents/{type}` status=`not_available` | Blocked (409) on mandatory docs like ID |
| 13 | بعد الانتهاء اضغط "إضافة سجل" | `POST /beneficiary/{id}/submit` | 409 with exact gaps if incomplete |
| 14 | التواصل عبر الواتساب مع خدمات المستفيدين | `POST /whatsapp/inbound`, `/crm/tickets` | |
| 15 | دراسة الحالة، الزيارة الميدانية، المقابلة، التقييم النفسي | `POST /support-requests/{id}/open-case`, `/cases/{id}/schedule-step` | All 4 step types |
| 16 | طلب الدعم بعد اعتماد الملف | `POST /support-requests` | 409 until file `approved` |
| 17 | البرامج الخمسة | `GET /programs` | علم، التأهيل والتدريب، جودة حياة، سكني، قيمي |
| 18 | المشاريع والطلبات تحت كل برنامج | `GET /programs/{id}/request-types` | All 43 transcribed with ceilings |
| 19 | حقول الطلب: نموذج البيانات، عنوان الطلب، التصنيف الداخلي، وصف الحالة | `POST /support-requests` body | `case_description_ar` = وصف الحالة |
| 20 | تقييم الاحتياج بوسائل متعددة | `case_studies.steps[]` + `findings_ar` | |
| 21 | عرض الحالة على اللجنة المختصة | `POST /cases/{id}/submit-to-committee`, `GET /committee/queue` | Queue ordered by need score |
| 22 | إشعار القرار: قبول / استكمال مستندات / اعتذار | `POST /support-requests/{id}/decision` | |
| 23 | الرد عبر الواتساب **وأيضاً** رسالة نصية | Decision fires both `whatsapp` + `sms` notifications | Verify via `GET /notifications` |
| 24 | متابعة النتيجة وإغلاق الطلب من الحساب | `GET /support-requests/{id}`, `/beneficiary/{id}/support-requests` | |
| 25 | تنبيه: التسجيل لا يعني قبول الطلب | Baked into `submit` and `create-request` replies; `FAQ-15` | |
| 26 | تنبيه: جميع الطلبات تخضع لدراسة وتقييم | Same | |
| 27 | تنبيه: الدعم وفق الاحتياج والأولوية | `need_score` ordering on `/committee/queue` | |
| 28 | تنبيه: دقة البيانات تسرّع الدراسة | `completeness` tool | |
| 29 | تنبيه: نقص البيانات يؤثر على الدراسة | 409 on submit with the exact gaps | |
| 30 | النموذج الأول: سؤال فئة اليتم قبل أي شيء | `POST /registration/check-eligibility` | Same wording as the guide's officer |
| 31 | النموذج الأول: طلب الاسم الثلاثي، الجوال، المدينة، وصف مختصر | `create-file` params + `case_description_ar` | |
| 32 | النموذج الأول: التزام الخصوصية | Global rule 8 in `04_AGENT_DESIGN.md` | |
| 33 | النموذج الثاني: خطوات استخراج مشهد الضمان | `FAQ-17` (full HRSD steps) | Incl. the requirement that it list all dependents and the amount |
| 34 | بيانات التواصل (0506094154، الهواتف، البريد، العنوان) | `GET /` and `FAQ-16` | |

## From the ERP/CRM screenshots

| Screenshot element | Implemented by |
|---|---|
| لوحة التذاكر kanban (مفتوح / جاري العمل / بانتظار العميل / تم الرد) | `GET /crm/kanban` |
| ملخص الحالات incl. منتهية المدة، مغلق | `GET /crm/kanban` → `summary_ar` |
| رقم التذكرة TK-2026-XXXX | Ticket id format |
| الوقت المتبقي 23س 57د | `wa_window()` and `ticket_sla()` |
| التصنيف: إدارة المستفيدون، تقنية المعلومات، كفالة يتيم مقيدة، الفعاليات | `GET /crm/departments` |
| نسبة الإغلاق، متوسط وقت الرد، أكثر الأقسام طلباً، طلبات اليوم | `GET /crm/stats` |
| سجل المحادثة / نافذة الرسائل | `GET /crm/tickets/{id}` → `messages` |
| تذاكر سابقة | Same → `previous_tickets` |
| فريق العمل | `GET /crm/staff` |
| إدارة الفعاليات | `GET /events`, `POST /events/{id}/register` |
| البرودكاست | `POST /whatsapp/send-template` (per-recipient) |
| رقم الواتساب على التذكرة | `whatsapp_number` on every ticket |
| إدارة ملفات المستفيدين / التابعين (نظام رافد) | Beneficiary + dependents endpoints |
| إدارة التعميد بالصرف | `POST /disbursements/{id}/approve` |
| لجنة المساعدات | `GET /committee/queue`, `/decision` |

## Deliberately not built

| Item | Why |
|---|---|
| Portal UI screens | Agents replace the portal; the client asked for the agent-callable system |
| Real OTP/SMS delivery | Mocked; `debug_code` returned for testing |
| Real bank transfers | Payment records only |
| National ID / Absher / Najiz / SIMAH verification | Requires government integration; documents are recorded, not verified |
| إدارة الأوصياء (guardians) | Visible in the ERP screenshot but not described in the guide — add if in scope |
| المكتب الإداري / الأعضاء المشاركون | Internal admin modules, unrelated to the beneficiary journey |
| Broadcast campaign manager | Single-send templates only; campaign scheduling not modelled |
