# Agent Design

Six agents, all sharing the same tool layer. Build them in your agent builder after importing `openapi/kayan_openapi.json`. Each section gives the **goal**, **intents**, **slots**, **flow**, **tools**, and a **sample Arabic dialogue**.

---

## Global rules (apply to every agent)

1. **Open with context.** First call is always `POST /whatsapp/inbound` or `POST /voice/call-start`. Both return the caller's file status, completion %, missing documents, open requests and next payment. Never ask "who are you?" when the number is known.
2. **Gate eligibility before collecting a file.** Kayan serves الأيتام ذوو الظروف الخاصة (مجهولو الأبوين). Ask once, early, exactly as the officer does in the guide. Non-eligible callers get a warm referral, not a form.
3. **Never predict a decision.** Say *"التسجيل في النظام لا يعني قبول الطلب، وجميع الطلبات تخضع لدراسة وتقييم."* The agent schedules, records and informs — it never approves.
4. **Use `reply_ar`.** Every conversational tool returns speech/print-ready Arabic. Don't compose from raw fields.
5. **Handle 409 by explaining, not retrying.** A 409 carries the reason and often `reply_ar`. Surface it and offer the fix.
6. **Confirm before writing.** Read numeric values back (amounts, dates, ID digits) before saving. On voice, digit-by-digit; never read a full IBAN aloud.
7. **Escalate on distress.** If a caller shows distress, hardship beyond the process, or anything involving a child's safety, stop the form and hand to a human researcher (`/voice/transfer` or `/crm/tickets` at high priority). This is not a form-filling failure — it's the correct outcome.
8. **Privacy.** Confirm identity before disclosing file details. Mirror the guide's assurance: *"جميع بياناتكم تحفظ بسرية تامة وتستخدم فقط لدراسة طلبكم."*
9. **Dialect.** Understand Najdi, Hijazi and Eastern; reply in clear, simple MSA-leaning Saudi Arabic.

---

## Agent 1 — Intake & Registration  (وكيل التسجيل)

**Goal:** take an unknown caller to a created, eligible beneficiary file.

**Intents:** `register`, `already_registered`, `check_eligibility`, `ask_how_to_register`

**Slots:** phone · orphan category · case type (independent vs foster family) · full name (رباعي) · national ID · city

**Flow**
1. `check-phone` → if registered, route to Agent 2 (don't re-register).
2. Ask the eligibility question → `check-eligibility`. Not served → referral, end warmly.
3. `send-otp` → `verify-otp`.
4. Determine case type: over-18 independent → `CT-IND`; family fostering an orphan → `CT-FOSTER`.
5. `create-file` → give them the file number.
6. Hand to Agent 2 to complete the file.

**Tools:** `/registration/check-phone` · `/registration/send-otp` · `/registration/verify-otp` · `/registration/check-eligibility` · `/reference/case-types` · `/beneficiary/create-file`

**Dialogue (WhatsApp)**
```
المستفيد: السلام عليكم، أرغب في التسجيل والاستفادة من خدماتكم. ما هي طريقة التسجيل؟

الوكيل: [whatsapp/inbound → غير معروف]
وعليكم السلام ورحمة الله وبركاته، حياكم الله وأسعد الله أوقاتكم.
بداية نشكركم على تواصلكم مع جمعية كيان للأيتام ذوي الظروف الخاصة.
لضمان توجيهكم للخدمة المناسبة، نود الاستفسار أولا:
هل أنتم من فئة الأيتام ذوي الظروف الخاصة (مجهولي الأبوين)؟

المستفيد: نعم، أنا يتيم مجهول الأبوين.

الوكيل: [check-eligibility OC-UNK → eligible]
شكرا لتأكيدكم. سأرسل لكم رمز تحقق على جوالكم للبدء.
[send-otp] ... [verify-otp] ... 
[create-file] تم إنشاء ملفكم برقم KY-4001. سنكمل معكم بقية البيانات خطوة بخطوة.
جميع بياناتكم تحفظ بسرية تامة وتستخدم فقط لدراسة طلبكم.
```

---

## Agent 2 — File Completion  (وكيل استكمال الملف)

**Goal:** drive the file from draft to submitted — the highest-value agent, because incomplete files are the association's main bottleneck.

**Intents:** `continue_file`, `update_section`, `add_dependent`, `upload_document`, `document_not_applicable`, `declare_income`, `declare_obligation`, `submit_file`

**Slots:** whichever fields `completeness` reports as missing (dynamic)

**Flow**
1. `completeness` → the tool tells you exactly what's missing. Work section by section, don't dump all 10 at once.
2. `PATCH /section/{id}` after each answer; confirm values back.
3. Dependents: explain *why* (household size drives the assessment), then `add_dependent` per person.
4. Documents: for each missing one, request it. If the caller says it doesn't apply → `ineligible` (عدم الأهلية). If unavailable → `not_available` (لا يوجد). If neither is allowed for that document, the 409 tells you it's mandatory.
5. Finances: obligations (`/obligations`) and living costs (`/person-costs`). Reject luxury spending gracefully — the 409 explains it.
6. `completeness` again → when `ready_to_submit`, call `submit`.
7. Close with the "registration ≠ approval" disclaimer.

**Tools:** `/beneficiary/{id}/completeness` · `/section/{sec}` · `/dependents` · `/documents/{type}` · `/obligations` · `/person-costs` · `/submit` · `/reference/*`

**Dialogue (WhatsApp)**
```
الوكيل: [completeness → 40%، ينقص: بيانات السكن، المرفقات]
ملفكم مكتمل بنسبة 40%. ننتقل لقسم بيانات السكن.
هل السكن ملك أم إيجار؟ وكم الإيجار الشهري؟

المستفيد: إيجار، ١٨٠٠ ريال بالشهر.

الوكيل: [PATCH SEC-HOUSING] سجلت: إيجار بقيمة 1800 ريال شهريا. 
ونحتاج إثبات ملكية السكن — يكفي عقد الإيجار.

المستفيد: عندي عقد إيجار، بس ما عندي تعريف راتب لأني ما أشتغل.

الوكيل: [documents/DOC-SALARY status=not_available]
لا مشكلة. سجلنا تعريف الراتب "لا يوجد". الرجاء إرفاق صورة مكتوب عليها "لا يوجد".
وبالنسبة لحساب المواطن، إذا كنتم غير مؤهلين أرفقوا صورة توضح "عدم الأهلية".

المستفيد: تمام. وعندي زوجة وولد يسكنون معي.

الوكيل: ممتاز، لازم نضيفهم في التابعين — عدد أفراد الأسرة يؤثر على دراسة الاحتياج.
[add_dependent ×2] تمت الإضافة. إجمالي التابعين 2.
[completeness → 100%] ملفكم مكتمل. هل نرفعه للدراسة الآن؟

المستفيد: نعم.

الوكيل: [submit] تم رفع ملفكم بنجاح. سيتم التواصل معكم لاستكمال إجراءات دراسة الحالة.
علما بأن التسجيل في النظام لا يعني قبول الطلب.
```

---

## Agent 3 — Support Requests  (وكيل طلبات الدعم)

**Goal:** turn "I need help with X" into a correctly classified request with a rich case description.

**Intents:** `request_support`, `which_program`, `add_detail`, `check_request_status`

**Slots:** request type · amount · **case description (the important one)**

**Flow**
1. `search_request_types` on what they said → confirm the right one. ("محتاج مساعدة بالإيجار" → طلب سداد إيجار / برنامج سكني.)
2. `create_request` — if the file isn't approved, the 409 says so; hand back to Agent 2.
3. **Probe for detail.** A one-line description weakens the case. Ask: since when? what triggered it? any notice or deadline? who else is affected? Then `add_detail`.
4. Respect the ceiling — the 409 returns it.
5. Set expectations: study, evaluation, priority. No promises.

**Tools:** `/request-types/search` · `/programs` · `/programs/{id}/request-types` · `/support-requests` · `/add-detail` · `/support-requests/{id}`

**Dialogue (voice)**
```
المستفيد: أبغى مساعدة، المالك يبغى يطلعنا من البيت.

الوكيل: [search_request_types "إيجار"] الله يعينكم. 
الطلب المناسب هو "طلب سداد إيجار" ضمن البرنامج السكني. أكمل معكم؟

المستفيد: إي نعم.

الوكيل: عشان اللجنة تفهم وضعكم بشكل كامل — من متى وأنتم متأخرين؟ وهل وصلكم إنذار رسمي؟

المستفيد: من ثلاثة أشهر، ووصلني إنذار إخلاء أول يوليو مدته شهر.

الوكيل: [create_request + add_detail]
تم تسجيل طلبكم رقم SR-25001 ضمن البرنامج السكني، وأضفت تفاصيل الإنذار.
سيخضع الطلب للدراسة والتقييم، وسيتم إشعاركم بالقرار عبر الواتساب ورسالة نصية.
```

---

## Agent 4 — Status & Enquiries  (وكيل الاستفسارات)

**Goal:** resolve the highest-volume queries without a human — status, payments, documents, how-to.

**Intents:** `check_status`, `when_is_payment`, `what_documents`, `how_to_x`, `contact_human`

**Flow**
1. Context from the channel entry call.
2. Status → `/support-requests/{id}` or `/beneficiary/{id}/support-requests`.
3. Money → `/disbursements` (next payment + totals) or `/payments`.
4. Procedure → `/faqs/search` **before improvising**. It covers the social security statement steps, the "already registered" message, dependents, housing proof, monthly bills, and more.
5. Can't resolve → ticket (`/crm/tickets`) or transfer.

**Dialogue (voice)**
```
المستفيد: متى ينزل مبلغ الإيجار؟

الوكيل: [call-start → معروف] حياكم الله أبو عبدالله.
[disbursements] إجمالي المصروف لكم 1500 ريال، 
والدفعة القادمة 1500 ريال بتاريخ 31 أغسطس.

المستفيد: طيب وش ناقص على ملفي؟

الوكيل: [completeness] ملفكم مكتمل 100% وما ينقصه شي. 
```

---

## Agent 5 — CRM & Triage  (وكيل الفرز)

**Goal:** everything the bot can't close becomes a well-formed, correctly routed ticket.

**Intents:** `create_ticket`, `route_department`, `escalate`, `check_ticket`

**Flow**
1. Classify → department (`/crm/departments`): beneficiary matters → DEP-BEN; login/technical → DEP-IT; sponsorship → DEP-KAF; events → DEP-EVT; payments → DEP-FIN.
2. `create_ticket` with the caller's own words as the first message.
3. Tell them the ticket number and the SLA.
4. On voice, `transfer` instead when it's urgent — it creates the ticket *and* hands over the call.
5. Watch the WhatsApp window: replying after 24h needs a template (`/whatsapp/send-template`).

**Staff-side tools:** `/crm/kanban` (board), `/crm/stats` (closure rate, avg response, top department), `/crm/tickets/{id}/assign`, `/status`, `/reply`.

---

## Agent 6 — Casework Assistant  (مساعد الباحث الاجتماعي) — *staff-facing*

**Goal:** support the social researcher. **Does not decide anything.**

**Flow:** `open-case` → `schedule-step` (field visit, office/online interview, psychological assessment — beneficiary is auto-notified) → `record-findings` → `submit-to-committee` with a recommendation → committee reviews `/committee/queue` (ordered by need score) → a **human** records the decision via `/decision`, which fires the WhatsApp + SMS notification → if accepted, `/enrollments` builds the disbursement schedule.

**Boundary:** the agent drafts recommendations and schedules; a human records the committee decision and authorizes every payment.

---

## Routing map

| Caller says | Agent | First tool |
|---|---|---|
| "أبغى أسجل" | 1 | check-phone |
| "رقم الجوال مسجل مسبقا" | 1 | check-phone → login guidance |
| "وش ناقص على ملفي" | 2 | completeness |
| "محتاج مساعدة في …" | 3 | request-types/search |
| "وش صار على طلبي" | 4 | support-requests |
| "متى ينزل المبلغ" | 4 | disbursements |
| "كيف أطلع مشهد الضمان" | 4 | faqs/search |
| "أبغى أكلم موظف" | 5 | transfer / create ticket |
| anything distressing | 5 | transfer, high priority |

## Test scripts

Run `scripts/smoke_test.py` — it walks this entire journey (83 assertions) and is the regression baseline for agent changes.
