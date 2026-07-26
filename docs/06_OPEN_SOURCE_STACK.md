# Recommended Open-Source Stack

You asked which open-source solution fits the CRM + kanban + WhatsApp design in your screenshots. Short answer: **no single project does all of it well.** The screenshots show two different products fused — a WhatsApp-first ticket desk *and* an NGO ERP. Trying to force one tool to do both is where these projects usually go wrong.

The stack below splits it three ways, along the seams that actually exist.

## Recommendation at a glance

| Layer | Pick | Licence | Why |
|---|---|---|---|
| ERP / system of record | **ERPNext + Frappe Framework** | GPLv3 | Full ERP with a non-profit domain module; accounting for disbursements; low-code custom doctypes for the beneficiary file, programs and casework; Arabic/RTL support; widely deployed in Gulf charities |
| WhatsApp desk / CRM | **Chatwoot** (or **Frappe Helpdesk + Frappe CRM**) | MIT core | Chatwoot is the closest match to your screenshots: omnichannel inbox, WhatsApp Business API, labels, canned responses, private notes, auto-assignment, self-hostable |
| Voice / SIP AI | **LiveKit + LiveKit Agents** | Apache 2.0 | Native SIP since 2025 (no Twilio bridge needed), bring-your-own STT/LLM/TTS, bridges to existing Asterisk/FreeSWITCH, MCP tool support |
| Orchestration | **this prototype's API layer** | — | Keeps the agent contract stable while the systems behind it change |

### The one decision that matters

**Chatwoot vs. Frappe Helpdesk.** If you want the *fewest moving parts*, go all-Frappe: Frappe CRM ships a drag-and-drop kanban and WhatsApp integration, and Frappe Helpdesk gives you ticketing — all sharing ERPNext's database, so a beneficiary record is genuinely one object with no sync layer. If you want the *best WhatsApp experience*, Chatwoot wins clearly: it's the most-starred open-source support tool (~33k GitHub stars, MIT core), purpose-built for omnichannel messaging, and its inbox looks and behaves like the ticket screens you sent.

**My recommendation: ERPNext + Chatwoot**, with this API layer between them. You lose single-database simplicity but gain a materially better beneficiary-facing channel, and beneficiary experience is the point of the project. Reassess if the integration burden gets heavy.

---

## Layer 1 — ERPNext (system of record)

ERPNext ships a non-profit domain and, critically, the **Frappe Framework** low-code layer, so the Kayan-specific objects are configuration rather than a codebase.

**Map to Kayan:**

| Kayan concept | ERPNext / Frappe |
|---|---|
| ملف المستفيد (10 sections) | Custom doctype `Beneficiary` with 10 field tabs |
| التابعون | Child table `Dependent` |
| المرفقات | Attachments + a `Document Checklist` child table with the `لا يوجد` / `عدم الأهلية` states |
| البرامج الخمسة والطلبات | `Program` + `Request Type` doctypes (seed from `data/programs.json`, `request_types.json`) |
| طلب الدعم | `Support Request` doctype with workflow states |
| دراسة الحالة | `Case Study` + child `Case Step`; assignments to social researchers |
| اللجنة المختصة | Workflow state + approval role; committee decision doctype |
| الصرف الشهري | Journal Entries / Payment Entries against a program cost centre |
| الكفالات | `Sponsor` + `Sponsorship`, linked to Donor |
| الفعاليات | Event doctype |
| الموظفون | HR module |

**Why not Odoo?** Also viable, and its community NGO modules (OCA) are decent. ERPNext edges it for a charity because it's fully open-source (Odoo's best pieces are Enterprise), the non-profit module is first-party, and Frappe's low-code layer suits an org without a large dev team.

**Note on نظام رافد:** your screenshot shows Kayan already using Rafed for beneficiary files. Decide early whether ERPNext *replaces* Rafed or *integrates* with it. Running both as systems of record will hurt. If Rafed stays, this API layer becomes the integration surface and ERPNext handles only what Rafed doesn't (programs, casework, disbursement).

## Layer 2 — Chatwoot (WhatsApp desk)

Maps directly onto your screenshots: conversation = ticket, inbox = queue, labels = التصنيف, teams = الأقسام, auto-assignment = routing, private notes = internal comments.

**Gaps to close yourself:**
- **Kanban board** — Chatwoot is inbox-first, not board-first. Either build the board as a view over the API (as this prototype's `/crm/kanban` does) or use Frappe Helpdesk, which has one natively.
- **24-hour window** — Chatwoot surfaces it, but your agent logic must enforce template-only sends outside it. This prototype models it.
- **SLA countdown** — the `23س 57د` display is custom; drive it from ticket age + department SLA.

**WhatsApp connection:** use the **official Meta WhatsApp Business Cloud API**. For a charity handling orphan case data, do not use an unofficial bridge (Baileys-based gateways such as WAHA or Evolution API) in production — the ban risk and the data-handling exposure aren't worth it. Unofficial is fine for the prototype only.

## Layer 3 — LiveKit Agents (voice / SIP)

LiveKit shipped native SIP and phone numbers, so inbound and outbound calling no longer needs a Twilio bridge in the middle, and it bridges to an existing Asterisk or FreeSWITCH PBX if Kayan already has one. Agents run a streaming STT → LLM → TTS pipeline with tool calling.

**Arabic components — the real constraint.** Saudi dialect handling is the weakest link in the whole stack, so budget testing time here:

| Component | Options | Note |
|---|---|---|
| STT | Whisper large-v3 (self-host), Deepgram, ElevenLabs Scribe | Test explicitly on Najdi/Hijazi/Eastern; MSA-trained models degrade on dialect |
| TTS | ElevenLabs, Azure Neural (ar-SA), Google | Azure's Saudi voices are solid; open-source Arabic TTS is still noticeably behind |
| LLM | Claude, GPT, Gemini, or an open model | Arabic instruction-following varies more than English; evaluate on your own dialogues |

Self-hosted STT/TTS on a GPU costs roughly $0.50–0.90/hour whether or not calls come in; pay-per-minute APIs cost nothing idle. Below roughly 15,000 minutes/month the APIs almost always win — which is where Kayan will start.

**Alternative:** Pipecat is simpler to learn and fine for lower concurrency. Reach for LiveKit when concurrency crosses a few hundred simultaneous calls or you want native telephony without a bridge.

---

## How the pieces connect

```
Phone ──SIP──► LiveKit Agents ─┐
                               ├──► THIS API LAYER ──► ERPNext (records, money)
WhatsApp ──Cloud API──► Chatwoot ┘                └──► Chatwoot (tickets)
```

Keep the agent talking to **one** API surface. Don't let agents call ERPNext and Chatwoot directly — you'd rewrite prompts every time either changes.

## Deployment sketch

Docker Compose or K8s: ERPNext (MariaDB + Redis), Chatwoot (Postgres + Redis + Sidekiq), LiveKit server + agent workers, this API, nginx/Caddy. **Host in-Kingdom** — beneficiary data on orphans is sensitive personal data under Saudi PDPL; a KSA region (or on-prem) keeps residency simple and avoids a cross-border transfer assessment.

## Rough effort

| Phase | Effort |
|---|---|
| ERPNext install + doctype modelling + seed import | 3–4 weeks |
| Chatwoot + WhatsApp Business API verification | 1–2 weeks (Meta approval is the long pole) |
| API integration layer (replace mocks) | 3–4 weeks |
| LiveKit + SIP + Arabic STT/TTS tuning | 3–5 weeks |
| Agent build + dialect testing | 4–6 weeks |
| Security, PDPL, audit, UAT | 3–4 weeks |

Roughly **4–5 months** to a supervised production pilot with a small team. Start with WhatsApp only and read-only queries — voice and write operations are where both the risk and the effort concentrate.

## Compliance checklist (do not skip)

- [ ] PDPL assessment; lawful basis and retention policy for orphan case data
- [ ] Data residency in KSA
- [ ] Role-based access; researchers see only their assigned cases
- [ ] Audit log on every read and write of a beneficiary record
- [ ] Encryption at rest and in transit
- [ ] Consent language for AI handling, with a human-agent opt-out on every channel
- [ ] Human-in-the-loop mandatory on committee decisions and all payment authorisation
- [ ] Escalation path for callers in distress or any child-safety concern

*Project maturity and licences change — re-verify before committing. This assessment reflects sources reviewed in July 2026.*
