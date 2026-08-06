/* ============================================================
   Kayan console — pages
   ============================================================ */
const { useState, useEffect, useMemo, useRef } = React;
const U = window.UI, A = window.API;
const { cx, money, num, dateAr, timeAgo, Icon, I, Card, CardHead, Button, Badge, STATUS_TONE,
        FILE_STATUS_AR, STAGE_AR, Input, Select, Progress, Ring, Avatar, Stat, Table, Td,
        Tabs, Sheet, Empty, Skeleton, Field } = U;

/* ============================================================ Dashboard */
function Dashboard({ go }) {
  const stats = A.useApi("/crm/stats", "stats");
  const kb = A.useApi("/crm/kanban", "kanban");
  const ov = A.useApi("/reports/overview", "overview");
  const hour = new Date().getHours();
  const greet = hour < 12 ? "صباح الخير" : hour < 17 ? "مساء الخير" : "مساء الخير";
  const s = stats.data || {}, o = ov.data || {};

  return (
    <div className="space-y-5">
      {/* hero */}
      <Card className="relative overflow-hidden border-brand-100/70 bg-gradient-to-l from-brand-50/70 via-white to-white animate-in">
        <div className="absolute -left-16 -top-20 w-72 h-72 rounded-full bg-brand-100/30 blur-3xl" />
        <div className="relative px-6 py-6 flex flex-wrap items-center justify-between gap-5">
          <div>
            <div className="flex items-center gap-2 text-[12px] text-brand-700 font-medium mb-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              النظام يعمل — {new Date().toLocaleDateString("ar-SA-u-nu-latn", { weekday:"long", day:"numeric", month:"long", year:"numeric" })}
            </div>
            <h1 className="text-[26px] font-semibold text-ink tracking-tight">{greet}، شادن 👋</h1>
            <p className="text-[13px] text-ink-muted mt-1">
              وصل اليوم <b className="text-ink font-semibold">{s.today ?? 0}</b> طلب جديد ·
              متوسط وقت الرد <b className="text-ink font-semibold tabular">{s.avg_first_response_hours ?? 0}س</b>
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="lg" onClick={() => go("kanban")}>
              <Icon d={I.board} className="w-4 h-4" /> لوحة التذاكر
            </Button>
            <Button size="lg" onClick={() => go("beneficiaries")}>
              <Icon d={I.users} className="w-4 h-4" /> ملفات المستفيدين
            </Button>
          </div>
        </div>
      </Card>

      {/* stat row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="إجمالي التذاكر" value={num(s.total ?? 0)} icon={I.ticket} tone="brand"
              hint={`مفتوح ${s.by_status?.open ?? 0} · مغلق ${s.by_status?.closed ?? 0}`}
              onClick={() => go("tickets")} />
        <Stat label="نسبة الإغلاق" value={`${s.closure_rate_pct ?? 0}%`} icon={I.check} tone="green"
              hint={`متأخرة عن المدة ${s.sla_breached ?? 0}`} />
        <Stat label="ملفات المستفيدين" value={num(o.beneficiaries?.total ?? 0)} icon={I.users} tone="violet"
              hint={`معتمد ${o.beneficiaries?.by_status?.approved ?? 0} · تابعين ${o.beneficiaries?.dependents ?? 0}`}
              onClick={() => go("beneficiaries")} />
        <Stat label="إجمالي المصروف" value={money(o.payments_total_sar)} icon={I.wallet} tone="amber"
              hint={`كفالات شهرية ${money(o.sponsorships?.monthly_sar)}`} onClick={() => go("finance")} />
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        {/* kanban preview */}
        <Card className="lg:col-span-2">
          <CardHead title="لوحة التذاكر" sub="نظرة سريعة على حالة الطلبات الواردة"
            action={<Button variant="ghost" size="sm" onClick={() => go("kanban")}>
              عرض الكل <Icon d={I.chevron} className="w-3.5 h-3.5" /></Button>} />
          <div className="px-5 pb-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {(kb.data?.columns || []).map(col => (
              <button key={col.status} onClick={() => go("kanban")}
                className="text-right rounded-xl border border-line bg-line-soft/40 p-3 hover:bg-white hover:shadow-card transition-all">
                <div className="flex items-center justify-between mb-2">
                  <Badge tone={STATUS_TONE[col.status] || "slate"} dot>{col.title_ar}</Badge>
                  <span className="text-[19px] font-semibold tabular text-ink">{col.count}</span>
                </div>
                <div className="space-y-1">
                  {col.cards.slice(0, 2).map(c => (
                    <p key={c.id} className="text-[11.5px] text-ink-muted truncate">{c.subject_ar}</p>
                  ))}
                  {!col.cards.length && <p className="text-[11.5px] text-ink-soft">لا توجد تذاكر</p>}
                </div>
              </button>
            ))}
          </div>
        </Card>

        {/* programs */}
        <Card>
          <CardHead title="الطلبات حسب البرنامج" sub="توزيع طلبات الدعم" />
          <div className="px-5 pb-5 space-y-3">
            {Object.entries(o.programs || {}).map(([name, count]) => {
              const max = Math.max(...Object.values(o.programs || { a: 1 }));
              return (
                <div key={name}>
                  <div className="flex items-center justify-between text-[12.5px] mb-1.5">
                    <span className="text-ink">{name}</span>
                    <span className="tabular text-ink-muted">{count}</span>
                  </div>
                  <Progress value={(count / max) * 100} />
                </div>
              );
            })}
            {!Object.keys(o.programs || {}).length && <Skeleton className="h-24" />}
          </div>
        </Card>
      </div>

      {/* channels + decisions */}
      <div className="grid lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHead title="نشاط القنوات" sub="مصدر الطلبات الواردة عبر وكلاء الذكاء الاصطناعي" />
          <div className="px-5 pb-5 grid sm:grid-cols-3 gap-3">
            {[
              { k: "whatsapp", label: "واتساب", icon: I.chat, tone: "green", v: s.by_channel?.whatsapp },
              { k: "call", label: "اتصال هاتفي", icon: I.phone, tone: "sky", v: s.by_channel?.call },
              { k: "portal", label: "الموقع", icon: I.home, tone: "violet", v: s.by_channel?.portal },
            ].map(c => (
              <div key={c.k} className="rounded-xl border border-line p-4">
                <span className={cx("inline-flex rounded-lg p-2 ring-1 ring-inset mb-2.5", U.TONE[c.tone])}>
                  <Icon d={c.icon} className="w-4 h-4" /></span>
                <p className="text-[22px] font-semibold tabular text-ink">{c.v ?? 0}</p>
                <p className="text-[12px] text-ink-muted">{c.label}</p>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHead title="قرارات اللجنة" sub="إجمالي القرارات الصادرة" />
          <div className="px-5 pb-5 space-y-2.5">
            {[["accepted","قبول الطلب","green"],["docs_required","استكمال مستندات","amber"],["declined","اعتذار","rose"]].map(([k,l,t]) => (
              <div key={k} className="flex items-center justify-between rounded-lg border border-line px-3 py-2.5">
                <Badge tone={t} dot>{l}</Badge>
                <span className="text-[15px] font-semibold tabular text-ink">{o.support_requests?.decisions?.[k] ?? 0}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ============================================================ Kanban */
function KanbanPage({ openTicket }) {
  const [dept, setDept] = useState("");
  const kb = A.useApi(`/crm/kanban${dept ? `?department_id=${dept}` : ""}`, "kanban", [dept]);
  const deps = A.useApi("/crm/departments", "departments");
  const cols = kb.data?.columns || [];
  const [dragId, setDragId] = useState(null);

  const handleDragStart = (e, ticketId) => {
    setDragId(ticketId);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDrop = async (e, targetStatus) => {
    e.preventDefault();
    if (!dragId) return;
    try {
      await A.patch(`/crm/tickets/${dragId}/status`, { status: targetStatus });
      setDragId(null);
      kb.refresh?.();
    } catch (err) {
      console.error("Status update failed:", err);
    }
  };

  return (
    <div className="space-y-4">
      <PageHead title="لوحة التذاكر" sub="متابعة طلبات المستفيدين الواردة عبر الواتساب والاتصال"
        right={
          <Select value={dept} onChange={e => setDept(e.target.value)}>
            <option value="">كل الأقسام</option>
            {(deps.data?.departments || []).map(d => <option key={d.id} value={d.id}>{d.name_ar}</option>)}
          </Select>
        } />
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {cols.map((col, ci) => (
          <div key={col.status} className="animate-in" style={{ animationDelay: `${ci * 50}ms` }}>
            <div className="flex items-center justify-between mb-2.5 px-1">
              <div className="flex items-center gap-2">
                <span className={cx("w-2 h-2 rounded-full",
                  { green:"bg-emerald-500", sky:"bg-sky-500", amber:"bg-amber-500", violet:"bg-violet-500" }[STATUS_TONE[col.status]] || "bg-slate-400")} />
                <h3 className="text-[13px] font-semibold text-ink">{col.title_ar}</h3>
              </div>
              <span className="text-[11.5px] tabular text-ink-muted bg-line-soft rounded-md px-1.5 py-0.5">{col.count}</span>
            </div>
            <div className="space-y-2.5 min-h-[120px] rounded-xl p-1 transition-colors"
                 onDragOver={handleDragOver}
                 onDrop={(e) => handleDrop(e, col.status)}
                 style={{ background: dragId ? "rgba(99,102,241,0.04)" : "transparent" }}>
              {col.cards.map(c => (
                <button key={c.id}
                  draggable
                  onDragStart={(e) => handleDragStart(e, c.id)}
                  onClick={() => openTicket(c.id)}
                  className={cx("w-full text-right bg-white border rounded-xl p-3.5 shadow-card transition-all group text-left",
                    dragId === c.id ? "opacity-50 border-brand-300" : "border-line hover:shadow-pop hover:border-brand-200")}>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="text-[11px] tabular text-ink-soft">{c.id}</span>
                    {c.priority === "high" && <Badge tone="rose">عاجل</Badge>}
                  </div>
                  <p className="text-[13px] font-medium text-ink leading-snug mb-2 group-hover:text-brand-700 transition-colors">
                    {c.subject_ar}</p>
                  <div className="flex items-center gap-2 mb-2.5">
                    <Avatar name={c.customer_name_ar} size={22} />
                    <span className="text-[12px] text-ink-muted truncate">{c.customer_name_ar}</span>
                  </div>
                  <div className="flex items-center justify-between pt-2 border-t border-line-soft">
                    <span className="text-[11px] text-ink-soft">{c.department_ar}</span>
                    <span className={cx("inline-flex items-center gap-1 text-[11px] tabular",
                      c.sla_remaining_ar === "منتهية المدة" ? "text-rose-600" : "text-ink-soft")}>
                      <Icon d={I.clock} className="w-3 h-3" />{c.sla_remaining_ar}
                    </span>
                  </div>
                </button>
              ))}
              {!col.cards.length && (
                <div className="rounded-xl border border-dashed border-line py-8 text-center text-[12px] text-ink-soft">
                  لا توجد تذاكر
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ============================================================ Tickets list */
function TicketsPage({ openTicket }) {
  const [q, setQ] = useState(""); const [status, setStatus] = useState("");
  const tk = A.useApi("/crm/tickets?limit=60", "tickets");
  const st = A.useApi("/crm/stats", "stats");
  const s = st.data || {};
  const rows = (tk.data?.tickets || []).filter(t =>
    (!status || t.status === status) &&
    (!q || (t.subject_ar + t.customer_name_ar + t.id).includes(q)));

  return (
    <div className="space-y-4">
      <PageHead title="التذاكر والطلبات" sub="متابعة طلبات المستفيدين الواردة عبر القنوات" />
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {[["الإجمالي", s.total, "brand"], ["مفتوح", s.by_status?.open, "green"],
          ["جاري العمل", s.by_status?.in_progress, "sky"], ["تم الرد", s.by_status?.replied, "violet"],
          ["مغلق", s.by_status?.closed, "slate"]].map(([l, v, t]) => (
          <Card key={l} className="px-4 py-3">
            <p className="text-[11.5px] text-ink-muted">{l}</p>
            <p className={cx("text-[21px] font-semibold tabular mt-0.5",
              t === "brand" ? "text-brand-700" : "text-ink")}>{v ?? 0}</p>
          </Card>
        ))}
      </div>
      <Card>
        <div className="p-4 flex flex-wrap gap-2.5 border-b border-line">
          <div className="flex-1 min-w-[200px]">
            <Input icon={I.search} placeholder="ابحث برقم التذكرة أو الاسم أو الموضوع…"
              value={q} onChange={e => setQ(e.target.value)} />
          </div>
          <Select value={status} onChange={e => setStatus(e.target.value)}>
            <option value="">كل الحالات</option>
            <option value="open">مفتوح</option><option value="in_progress">جاري العمل</option>
            <option value="waiting_customer">بانتظار العميل</option><option value="replied">تم الرد</option>
            <option value="closed">مغلق</option>
          </Select>
        </div>
        <Table head={["رقم التذكرة", "المستفيد", "التصنيف", "الحالة", "القناة", "المتبقي", "آخر تحديث", ""]}
               empty={!rows.length && "لا توجد تذاكر مطابقة"}>
          {rows.map(t => (
            <tr key={t.id} className="hover:bg-line-soft/50 transition-colors cursor-pointer"
                onClick={() => openTicket(t.id)}>
              <Td><span className="tabular text-[12px] text-ink-muted">{t.id}</span></Td>
              <Td>
                <div className="flex items-center gap-2.5">
                  <Avatar name={t.customer_name_ar} size={28} />
                  <div className="min-w-0">
                    <p className="font-medium text-ink truncate">{t.customer_name_ar}</p>
                    <p className="text-[11.5px] text-ink-soft truncate">{t.subject_ar}</p>
                  </div>
                </div>
              </Td>
              <Td><span className="text-[12.5px] text-ink-muted">{t.department_ar}</span></Td>
              <Td><Badge tone={STATUS_TONE[t.status]} dot>{t.status_ar}</Badge></Td>
              <Td>
                <span className="inline-flex items-center gap-1.5 text-[12px] text-ink-muted">
                  <Icon d={t.channel === "call" ? I.phone : t.channel === "whatsapp" ? I.chat : I.home}
                        className="w-3.5 h-3.5" />
                  {{ whatsapp:"واتساب", call:"اتصال", portal:"الموقع" }[t.channel]}
                </span>
              </Td>
              <Td><span className={cx("text-[12px] tabular",
                t.sla?.breached ? "text-rose-600 font-medium" : "text-ink-muted")}>{t.sla?.remaining_ar}</span></Td>
              <Td><span className="text-[12px] text-ink-soft">{timeAgo(t.last_update)}</span></Td>
              <Td><Icon d={I.chevron} className="w-4 h-4 text-ink-soft" /></Td>
            </tr>
          ))}
        </Table>
      </Card>
    </div>
  );
}

/* ============================================================ Ticket detail */
function TicketSheet({ id, onClose }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const t = A.useApi(id ? `/crm/tickets/${id}` : "", s => s.ticket_details?.[id], [id, refreshKey]);
  const d = t.data;
  const [replyText, setReplyText] = useState("");
  const [sendToWhatsApp, setSendToWhatsApp] = useState(true);
  const [sending, setSending] = useState(false);
  const [showCount, setShowCount] = useState(15);
  const chatRef = useRef(null);

  const sendReply = async () => {
    if (!replyText.trim() || !id) return;
    setSending(true);
    try {
      await A.post(`/crm/tickets/${id}/reply`, { body_ar: replyText.trim(), sender: "agent", send_to_whatsapp: sendToWhatsApp });
      setReplyText("");
      setRefreshKey(k => k + 1);
    } catch (e) {
      console.error("Reply failed:", e);
    }
    setSending(false);
  };

  const closeTicket = async () => {
    if (!id) return;
    try {
      await A.patch(`/crm/tickets/${id}/status`, { status: "closed" });
      setRefreshKey(k => k + 1);
    } catch (e) {
      console.error("Close failed:", e);
    }
  };

  const allMsgs = d?.messages || [];
  const visibleMsgs = allMsgs.slice(-showCount);
  const hasMore = allMsgs.length > showCount;

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [visibleMsgs.length]);

  if (!id) return null;
  return (
    <Sheet open={!!id} onClose={onClose} title={d ? d.subject_ar : "…"}
           sub={d ? `${d.id} · ${d.customer_name_ar}` : ""}>
      {!d ? <Skeleton className="h-64" /> : (
        <div className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <Card className="p-4">
              <p className="text-[12px] text-ink-muted mb-3">معلومات التذكرة</p>
              <dl className="space-y-2.5">
                <Field label="الحالة" value={<Badge tone={STATUS_TONE[d.status]} dot>{d.status_ar}</Badge>} />
                <Field label="التصنيف" value={d.department_ar} />
                <Field label="القناة" value={{ whatsapp:"واتساب", call:"اتصال هاتفي", portal:"الموقع" }[d.channel]} />
                <Field label="رقم الواتساب" value={d.whatsapp_number} mono />
                <Field label="تاريخ الفتح" value={dateAr(d.opened_at)} />
              </dl>
              {d.status !== "closed" && (
                <button onClick={closeTicket}
                  className="mt-3 w-full py-2 text-[12px] font-medium text-rose-600 bg-rose-50 hover:bg-rose-100 rounded-lg transition-colors">
                  إغلاق التذكرة
                </button>
              )}
            </Card>
            <div className="space-y-4">
              <Card className={cx("p-4", d.sla?.breached && "border-rose-200 bg-rose-50/40")}>
                <div className="flex items-center gap-2 text-[12px] text-ink-muted mb-1.5">
                  <Icon d={I.clock} className="w-3.5 h-3.5" /> الوقت المتبقي للرد
                </div>
                <p className={cx("text-[24px] font-semibold tabular",
                  d.sla?.breached ? "text-rose-600" : "text-ink")}>{d.sla?.remaining_ar}</p>
                <p className="text-[11.5px] text-ink-soft mt-1">
                  نافذة الواتساب 24 ساعة — بعدها تُستخدم رسالة قالب معتمدة
                </p>
              </Card>
              {d.previous_tickets?.length > 0 && (
                <Card className="p-4">
                  <p className="text-[12px] text-ink-muted mb-2">تذاكر سابقة ({d.previous_tickets.length})</p>
                  <div className="flex flex-wrap gap-1.5">
                    {d.previous_tickets.slice(0, 6).map(p =>
                      <span key={p} className="text-[11px] tabular rounded-md bg-line-soft px-1.5 py-0.5 text-ink-muted">{p}</span>)}
                  </div>
                </Card>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-line bg-white overflow-hidden">
            {/* Chat Header */}
            <div className="px-4 py-3 border-b border-line bg-gradient-to-l from-brand-50 to-white">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center">
                    <Icon d={I.bot} className="w-4 h-4 text-white" />
                  </div>
                  <div>
                    <p className="text-[13px] font-semibold text-ink">المحادثة</p>
                    <p className="text-[11px] text-ink-muted">{allMsgs.length} رسالة</p>
                  </div>
                </div>
                {hasMore && (
                  <button onClick={() => setShowCount(c => c + 30)}
                    className="text-[11px] text-brand-600 hover:text-brand-700 font-medium px-2 py-1 rounded-lg hover:bg-brand-50 transition-colors">
                    تحميل سابقات
                  </button>
                )}
              </div>
            </div>

            {/* Chat Messages */}
            <div ref={chatRef} className="px-4 py-3 space-y-3 overflow-y-auto bg-[#F8F9FB]" style={{ maxHeight: "420px" }}>
              {visibleMsgs.map((m, i) => {
                const inbound = m.direction === "inbound";
                const prev = visibleMsgs[i - 1];
                const showSender = !prev || prev.direction !== m.direction;
                const showDate = !prev || new Date(m.sent_at).toDateString() !== new Date(prev.sent_at).toDateString();
                return (
                  <React.Fragment key={i}>
                    {showDate && (
                      <div className="flex items-center gap-3 my-1">
                        <div className="flex-1 h-px bg-line" />
                        <span className="text-[10px] text-ink-soft font-medium px-2">{dateAr(m.sent_at)}</span>
                        <div className="flex-1 h-px bg-line" />
                      </div>
                    )}
                    <div className={cx("flex", inbound ? "justify-start" : "justify-end")}>
                      {inbound ? (
                        <div className="flex items-end gap-2 max-w-[80%]">
                          <div className="w-6 h-6 rounded-full bg-line-soft flex items-center justify-center flex-shrink-0 mb-0.5">
                            <span className="text-[10px] font-semibold text-ink-muted">
                              {m.sender_name?.charAt(0) || "م"}
                            </span>
                          </div>
                          <div>
                            {showSender && <p className="text-[10px] text-ink-soft mb-1 mr-1">المستفيد</p>}
                            <div className="bg-white border border-line rounded-2xl rounded-br-md px-3.5 py-2.5 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
                              <p className="text-[13px] text-ink leading-[1.7] whitespace-pre-wrap">{m.body_ar}</p>
                              <p className="text-[10px] text-ink-soft mt-1.5 text-left">
                                {new Date(m.sent_at).toLocaleTimeString("ar-SA", { hour: "2-digit", minute: "2-digit" })}
                              </p>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-end gap-2 max-w-[80%] flex-row-reverse">
                          <div className="w-6 h-6 rounded-full bg-brand-600 flex items-center justify-center flex-shrink-0 mb-0.5">
                            <Icon d={m.sender === "bot" ? I.bot : I.user} className="w-3 h-3 text-white" />
                          </div>
                          <div>
                            {showSender && (
                              <p className={cx("text-[10px] mb-1 ml-1 text-left",
                                m.is_internal ? "text-amber-500" : "text-ink-soft")}>
                                {m.is_internal ? "ملاحظة داخلية" : m.sender === "bot" ? "الوكيل الذكي" : "الموظف"}
                              </p>
                            )}
                            <div className={cx("rounded-2xl rounded-bl-md px-3.5 py-2.5 shadow-[0_1px_2px_rgba(0,0,0,0.06)]",
                              m.is_internal ? "bg-amber-50 border border-amber-200" : "bg-brand-600 text-white")}>
                              <p className={cx("text-[13px] leading-[1.7] whitespace-pre-wrap",
                                m.is_internal ? "text-amber-900" : "text-white")}>{m.body_ar}</p>
                              <p className={cx("text-[10px] mt-1.5 text-left",
                                m.is_internal ? "text-amber-400" : "text-brand-200")}>
                                {new Date(m.sent_at).toLocaleTimeString("ar-SA", { hour: "2-digit", minute: "2-digit" })}
                              </p>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </React.Fragment>
                );
              })}
              {!allMsgs.length && (
                <div className="py-12 text-center">
                  <div className="w-12 h-12 rounded-full bg-brand-50 flex items-center justify-center mx-auto mb-3">
                    <Icon d={I.chat} className="w-5 h-5 text-brand-500" />
                  </div>
                  <p className="text-[13px] text-ink font-medium">ابدأ المحادثة</p>
                  <p className="text-[11px] text-ink-soft mt-0.5">اكتب رسالة للمستفيد</p>
                </div>
              )}
            </div>

            {/* Input Area */}
            <div className="border-t border-line bg-white p-3">
              <div className="flex items-center gap-2 mb-2.5">
                <button onClick={() => setSendToWhatsApp(!sendToWhatsApp)}
                  className={cx("relative w-9 h-5 rounded-full transition-colors flex-shrink-0", sendToWhatsApp ? "bg-brand-600" : "bg-line-soft")}>
                  <span className={cx("absolute top-[3px] left-[3px] w-4 h-4 rounded-full bg-white shadow-sm transition-transform", sendToWhatsApp && "translate-x-4")} />
                </button>
                <span className="text-[11px] text-ink-muted">
                  {sendToWhatsApp ? "إرسال عبر واتساب" : "ملاحظة داخلية"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  className="flex-1 h-10 rounded-xl border border-line bg-line-soft/30 px-4 text-[13px] text-ink placeholder:text-ink-soft focus:outline-none focus:ring-2 focus:ring-brand-200 focus:border-brand-300 transition-all"
                  placeholder={sendToWhatsApp ? "اكتب ردًا للمستفيد…" : "اكتب ملاحظة داخلية…"}
                  value={replyText}
                  onChange={e => setReplyText(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendReply();
                    }
                  }}
                />
                <button onClick={sendReply} disabled={sending || !replyText.trim()}
                  className={cx("flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-all",
                    sending || !replyText.trim()
                      ? "bg-line-soft text-ink-soft cursor-not-allowed"
                      : "bg-brand-600 text-white hover:bg-brand-700 active:scale-95 shadow-sm")}>
                  {sending ? (
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : (
                    <Icon d={I.arrow} className="w-4 h-4 flip" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Sheet>
  );
}

/* ============================================================ Beneficiaries */
function BeneficiariesPage({ openBen }) {
  const [q, setQ] = useState(""); const [status, setStatus] = useState("");
  const b = A.useApi("/beneficiaries/search?q=&limit=100", "beneficiaries");
  const all = b.data?.results || [];
  const rows = all.filter(x => (!status || x.status === status) &&
    (!q || (x.name_ar + x.file_no + (x.mobile || "")).includes(q)));

  return (
    <div className="space-y-4">
      <PageHead title="ملفات المستفيدين" sub="قاعدة بيانات المستفيدين والتابعين" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[["إجمالي الملفات", all.length, "brand"],
          ["معتمد", all.filter(x=>x.status==="approved").length, "green"],
          ["قيد المراجعة", all.filter(x=>["submitted","under_review"].includes(x.status)).length, "amber"],
          ["مسودة", all.filter(x=>x.status==="draft").length, "slate"]].map(([l,v,t]) => (
          <Card key={l} className="px-4 py-3">
            <p className="text-[11.5px] text-ink-muted">{l}</p>
            <p className={cx("text-[21px] font-semibold tabular mt-0.5", t==="brand"?"text-brand-700":"text-ink")}>{v}</p>
          </Card>
        ))}
      </div>
      <Card>
        <div className="p-4 flex flex-wrap gap-2.5 border-b border-line">
          <div className="flex-1 min-w-[200px]">
            <Input icon={I.search} placeholder="ابحث بالاسم أو رقم الملف أو الجوال…"
                   value={q} onChange={e => setQ(e.target.value)} />
          </div>
          <Select value={status} onChange={e => setStatus(e.target.value)}>
            <option value="">كل الحالات</option>
            {Object.entries(FILE_STATUS_AR).map(([k,v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </div>
        <Table head={["رقم الملف", "المستفيد", "المدينة", "النوع", "اكتمال الملف", "التابعون", "الحالة", ""]}
               empty={!rows.length && "لا توجد ملفات مطابقة"}>
          {rows.map(x => (
            <tr key={x.id} className="hover:bg-line-soft/50 cursor-pointer transition-colors"
                onClick={() => openBen(x.id)}>
              <Td><span className="tabular text-[12px] text-ink-muted">{x.file_no}</span></Td>
              <Td>
                <div className="flex items-center gap-2.5">
                  <Avatar name={x.name_ar} size={30} />
                  <div className="min-w-0">
                    <p className="font-medium text-ink truncate">{x.name_ar}</p>
                    <p className="text-[11.5px] text-ink-soft tabular">{x.mobile}</p>
                  </div>
                </div>
              </Td>
              <Td><span className="text-[12.5px] text-ink-muted">{x.city}</span></Td>
              <Td><Badge tone={x.case_type === "CT-FOSTER" ? "violet" : "slate"}>
                {x.case_type === "CT-FOSTER" ? "أسرة بديلة" : "مستفيد مستقل"}</Badge></Td>
              <Td>
                <div className="flex items-center gap-2 w-32">
                  <Progress value={x.completion_pct} tone={x.completion_pct >= 90 ? "green" : "amber"} />
                  <span className="text-[11.5px] tabular text-ink-muted shrink-0">{x.completion_pct}%</span>
                </div>
              </Td>
              <Td><span className="tabular text-[12.5px] text-ink-muted">{x.dependents}</span></Td>
              <Td><Badge tone={STATUS_TONE[x.status]} dot>{FILE_STATUS_AR[x.status]}</Badge></Td>
              <Td><Icon d={I.chevron} className="w-4 h-4 text-ink-soft" /></Td>
            </tr>
          ))}
        </Table>
      </Card>
    </div>
  );
}

/* ============================================================ Beneficiary 360 */
function BeneficiarySheet({ id, onClose }) {
  const [tab, setTab] = useState("overview");
  const r = A.useApi(id ? `/beneficiary/${id}/history` : "", s => s.histories?.[id], [id]);
  const d = r.data;
  useEffect(() => setTab("overview"), [id]);
  if (!id) return null;

  const b = d?.beneficiary || {}, c = d?.completeness || {}, f = d?.financial || {};
  const tabs = [
    { id: "overview", label: "نظرة عامة" },
    { id: "household", label: "الأسرة", count: d?.household?.size },
    { id: "requests", label: "الطلبات", count: d?.support_requests?.length },
    { id: "money", label: "الصرف", count: d?.disbursements?.count },
    { id: "activity", label: "النشاط" },
  ];

  const missingDocNames = c.missing_documents?.map(x => x.name_ar) || [];
  const missingSectionNames = [...new Set((c.missing_fields || []).map(x => x.section_ar))];

  return (
    <Sheet open={!!id} onClose={onClose} width="max-w-3xl">
      {!d ? <Skeleton className="h-64" /> : (
        <div className="space-y-5">
          {/* Beneficiary header */}
          <div className="flex items-start gap-4 pb-1">
            <Avatar name={b.name_ar} size={48} />
            <div className="min-w-0 flex-1">
              <h2 className="text-[17px] font-bold text-ink leading-snug">{b.name_ar || "—"}</h2>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                {b.file_no && <span className="text-[12.5px] font-mono text-ink-muted">{b.file_no}</span>}
                {b.category_ar && <span className="text-[12.5px] text-ink-soft">· {b.category_ar}</span>}
              </div>
              <div className="flex items-center gap-2 mt-1.5">
                <Badge tone={STATUS_TONE[b.status]} dot>{FILE_STATUS_AR[b.status]}</Badge>
                {b.city && <span className="text-[11.5px] text-ink-soft">{b.city}</span>}
              </div>
            </div>
          </div>

          {/* Stats cards */}
          <div className="grid grid-cols-3 gap-3">
            <Card className="p-4">
              <p className="text-[11.5px] text-ink-muted font-medium">إجمالي المصروف</p>
              <p className="text-[22px] font-bold tabular text-ink mt-1">{money(d.payments?.total_sar)}</p>
              <p className="text-[11px] text-ink-soft mt-1">قادم: {money(d.disbursements?.upcoming_sar)}</p>
            </Card>
            <Card className="p-4">
              <p className="text-[11.5px] text-ink-muted font-medium">درجة الاحتياج</p>
              <p className="text-[22px] font-bold tabular text-ink mt-1">{f.need_score ?? "—"}</p>
              <Progress value={f.need_score || 0} tone={f.need_score > 70 ? "rose" : "amber"} className="mt-2" />
            </Card>
            <Card className="p-4 flex items-center justify-between">
              <div>
                <p className="text-[11.5px] text-ink-muted font-medium">اكتمال الملف</p>
                <p className="text-[13px] text-ink-soft mt-1">{Math.round(c.pct ?? 0)}%</p>
              </div>
              <Ring value={c.pct ?? 0} size={56} stroke={5} />
            </Card>
          </div>

          {/* Missing documents / sections alert */}
          {(missingDocNames.length > 0 || missingSectionNames.length > 0) && (
            <Card className="border border-amber-200 bg-amber-50/60 p-4">
              <div className="flex gap-3">
                <div className="shrink-0 mt-0.5">
                  <Icon d={I.alert} className="w-4 h-4 text-amber-600" />
                </div>
                <div className="min-w-0 space-y-2.5">
                  <p className="text-[13px] font-semibold text-amber-900">الملف يحتاج استكمال</p>
                  {missingDocNames.length > 0 && (
                    <div>
                      <p className="text-[11.5px] text-amber-700 font-medium mb-1.5">مستندات ناقصة</p>
                      <div className="flex flex-wrap gap-1.5">
                        {missingDocNames.map((name, i) => (
                          <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-100 text-amber-800 text-[11px] font-medium">
                            <Icon d={I.alert} className="w-3 h-3 opacity-60" />
                            {name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {missingSectionNames.length > 0 && (
                    <div>
                      <p className="text-[11.5px] text-amber-700 font-medium mb-1.5">أقسام ناقصة</p>
                      <div className="flex flex-wrap gap-1.5">
                        {missingSectionNames.map((name, i) => (
                          <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-md bg-amber-100 text-amber-800 text-[11px] font-medium">
                            {name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          )}

          {/* Tabs */}
          <Tabs tabs={tabs} value={tab} onChange={setTab} />

          {/* Tab content */}
          {tab === "overview" && (
            <div className="grid sm:grid-cols-2 gap-4">
              <Card className="p-5">
                <p className="text-[13px] font-semibold text-ink mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-500"></span>
                  البيانات الأساسية
                </p>
                <dl className="space-y-3">
                  <Field label="رقم الملف" value={b.file_no} mono />
                  <Field label="نوع الملف" value={b.case_type === "CT-FOSTER" ? "أسرة بديلة" : "مستفيد مستقل"} />
                  <Field label="الفئة" value={b.category_ar} />
                  <Field label="المدينة" value={b.city} />
                  <Field label="تاريخ التسجيل" value={dateAr(b.created_at)} />
                  <Field label="تاريخ الاعتماد" value={b.approved_at ? dateAr(b.approved_at) : "—"} />
                </dl>
              </Card>
              <Card className="p-5">
                <p className="text-[13px] font-semibold text-ink mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  الوضع المالي
                </p>
                <dl className="space-y-3">
                  <Field label="الدخل الشهري" value={money(f.monthly_income_sar)} mono />
                  <Field label="الالتزامات" value={money(f.total_obligations_sar)} mono />
                  <Field label="تكاليف المعيشة" value={money(f.total_person_costs_sar)} mono />
                  <Field label="نصيب الفرد" value={money(f.per_capita_monthly_sar)} mono />
                </dl>
              </Card>
            </div>
          )}

          {tab === "household" && (
            <Card>
              <CardHead title="أفراد الأسرة" sub={`عدد أفراد الأسرة ${d.household?.size}`} />
              <Table head={["الاسم", "صلة القرابة", "تاريخ الميلاد", "المرحلة التعليمية", ""]}
                     empty={!d.household?.dependents?.length && "لا يوجد تابعون مسجلون"}>
                {(d.household?.dependents || []).map(x => (
                  <tr key={x.id}>
                    <Td><div className="flex items-center gap-2.5">
                      <Avatar name={x.name_ar} size={28} />
                      <span className="font-medium text-ink">{x.name_ar}</span></div></Td>
                    <Td><span className="text-[12.5px] text-ink-muted">{x.relationship}</span></Td>
                    <Td><span className="tabular text-[12.5px] text-ink-muted">{x.birth_date}</span></Td>
                    <Td><span className="text-[12.5px] text-ink-muted">{x.education}</span></Td>
                    <Td>{x.special_needs ? <Badge tone="violet">احتياج خاص</Badge> : null}</Td>
                  </tr>
                ))}
              </Table>
            </Card>
          )}

          {tab === "requests" && (
            <Card>
              <CardHead title="طلبات الدعم" sub={`${d.support_requests?.length || 0} طلب`} />
              <Table head={["البرنامج", "الطلب", "المرحلة", "المبلغ المطلوب", "القرار", "المعتمد"]}
                     empty={!d.support_requests?.length && "لا توجد طلبات"}>
                {(d.support_requests || []).map(x => (
                  <tr key={x.id}>
                    <Td><Badge tone="brand">{x.program_ar}</Badge></Td>
                    <Td><span className="text-[12.5px] text-ink">{x.title_ar}</span></Td>
                    <Td><Badge tone={STATUS_TONE[x.stage]} dot>{STAGE_AR[x.stage]}</Badge></Td>
                    <Td><span className="tabular text-[12.5px]">{money(x.requested_amount_sar)}</span></Td>
                    <Td>{x.decision_ar
                      ? <Badge tone={x.decision_ar.includes("قبول") ? "green" : x.decision_ar.includes("اعتذار") ? "rose" : "amber"}>{x.decision_ar}</Badge>
                      : <span className="text-ink-soft text-[12px]">—</span>}</Td>
                    <Td><span className="tabular text-[12.5px] font-medium">{x.approved_amount_sar ? money(x.approved_amount_sar) : "—"}</span></Td>
                  </tr>
                ))}
              </Table>
            </Card>
          )}

          {tab === "money" && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <Card className="p-4">
                  <p className="text-[11.5px] text-ink-muted font-medium">مصروف</p>
                  <p className="text-[19px] font-bold tabular text-emerald-600 mt-1">{money(d.disbursements?.paid_sar)}</p>
                </Card>
                <Card className="p-4">
                  <p className="text-[11.5px] text-ink-muted font-medium">قادم</p>
                  <p className="text-[19px] font-bold tabular text-ink mt-1">{money(d.disbursements?.upcoming_sar)}</p>
                </Card>
                <Card className="p-4">
                  <p className="text-[11.5px] text-ink-muted font-medium">عدد الدفعات</p>
                  <p className="text-[19px] font-bold tabular text-ink mt-1">{d.disbursements?.count ?? 0}</p>
                </Card>
              </div>
              <Card>
                <CardHead title="جدول الصرف" />
                <Table head={["تاريخ الاستحقاق", "البرنامج", "المبلغ", "الحالة"]}
                       empty={!d.disbursements?.rows?.length && "لا توجد دفعات"}>
                  {(d.disbursements?.rows || []).map(x => (
                    <tr key={x.id}>
                      <Td><span className="tabular text-[12.5px]">{x.due_date}</span></Td>
                      <Td><span className="text-[12.5px] text-ink-muted">
                        {(d.enrollments || []).find(e => e.id === x.enrollment_id)?.program_ar || "—"}</span></Td>
                      <Td><span className="tabular text-[12.5px] font-medium">{money(x.amount)}</span></Td>
                      <Td><Badge tone={STATUS_TONE[x.status]} dot>
                        {{ paid:"مصروف", scheduled:"مجدول", approved:"معتمد", pending_approval:"بانتظار الاعتماد" }[x.status] || x.status}
                      </Badge></Td>
                    </tr>
                  ))}
                </Table>
              </Card>
            </div>
          )}

          {tab === "activity" && (
            <Card>
              <CardHead title="سجل التواصل" sub={`${d.tickets?.length || 0} تذكرة · ${d.channel_sessions?.calls || 0} مكالمة · ${d.channel_sessions?.whatsapp || 0} جلسة واتساب`} />
              <div className="px-5 pb-5">
                <ol className="relative border-r-2 border-line-soft mr-2">
                  {(d.tickets || []).map(t => (
                    <li key={t.id} className="mr-5 pb-4 relative">
                      <span className="absolute -right-[26px] top-1 w-2.5 h-2.5 rounded-full bg-brand-400 ring-4 ring-white" />
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-[13px] font-medium text-ink">{t.subject_ar}</p>
                        <Badge tone={STATUS_TONE[t.status] || "slate"}>{t.status_ar}</Badge>
                      </div>
                      <p className="text-[11.5px] text-ink-soft mt-0.5">
                        {{ whatsapp:"واتساب", call:"اتصال هاتفي", portal:"الموقع" }[t.channel]} · {dateAr(t.opened_at)}
                      </p>
                    </li>
                  ))}
                </ol>
                {!d.tickets?.length && <Empty icon={I.chat} title="لا يوجد نشاط" />}
              </div>
            </Card>
          )}
        </div>
      )}
    </Sheet>
  );
}

/* ============================================================ Requests */
const DEFAULT_DOCS = "تعريف الراتب، عقد الإيجار";
const DEFAULT_REASON = {
  accepted: "استيفاء الشروط ووجود احتياج مؤكد",
  docs_required: "يلزم استكمال المستندات المطلوبة",
  declined: "لا يوجد احتياج مؤكد حسب التقييم",
};

const DECISION_META = {
  accepted:      { title: "اعتماد الطلب", verb: "قبول" },
  docs_required: { title: "طلب استكمال مستندات", verb: "مستندات" },
  declined:      { title: "الاعتذار عن الطلب", verb: "اعتذار" },
};

/* One decision flow shared by the Requests table and the Committee board, so
   the two cannot drift apart. Returns { open, node } — render node once. */
function useDecisionModal(onDone) {
  const [state, setState] = useState({ open: false, type: null, request: null });
  const [amount, setAmount] = useState("");
  const [docs, setDocs] = useState(DEFAULT_DOCS);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const open = (request, type) => {
    setState({ open: true, type, request });
    setError(null);
    setAmount(String(request?.requested_amount_sar ?? ""));
    setDocs(DEFAULT_DOCS);
    setReason(DEFAULT_REASON[type] || "");
  };
  const close = () => { if (!submitting) setState({ open: false, type: null, request: null }); };

  const submit = async () => {
    const { type, request } = state;
    const id = request?.id || request?.support_request_id;
    if (!id) return;
    setSubmitting(true);
    setError(null);
    try {
      // reason_ar is required by the API for EVERY decision type. Sending it
      // only for "declined" made accept and docs_required fail with a 422.
      const body = { decision: type, reason_ar: reason || DEFAULT_REASON[type] };
      if (type === "accepted") {
        const value = parseFloat(amount);
        if (!Number.isFinite(value) || value <= 0) {
          setError("أدخل مبلغًا صحيحًا أكبر من صفر");
          setSubmitting(false);
          return;
        }
        body.approved_amount_sar = value;
      } else if (type === "docs_required") {
        body.required_documents_ar = docs.split(/[،,]/).map(s => s.trim()).filter(Boolean);
      }
      await A.post(`/support-requests/${id}/decision`, body);
      setState({ open: false, type: null, request: null });
      onDone?.();
    } catch (e) {
      // Surface the API's reason (ceiling exceeded, already decided…) instead
      // of a bare "خطأ في تسجيل القرار".
      setError(e?.message || "تعذّر تسجيل القرار");
    }
    setSubmitting(false);
  };

  const node = state.open && state.type ? (
    <U.Modal open onClose={close}
      title={DECISION_META[state.type].title}
      sub={state.request
        ? `${state.request.id || state.request.support_request_id} — ${state.request.name_ar || ""}`
        : ""}
      footer={
        <>
          <Button variant="outline" onClick={close} disabled={submitting}>إلغاء</Button>
          <Button variant={state.type === "declined" ? "danger" : "default"}
            onClick={submit} disabled={submitting}>
            {submitting ? "جاري التسجيل…" : "تأكيد"}
          </Button>
        </>
      }>
      <div className="space-y-3">
        {state.type === "accepted" && (
          <>
            <p className="text-[13px] text-ink-muted">المبلغ المعتمد للصرف:</p>
            <Input type="number" value={amount} onChange={e => setAmount(e.target.value)} placeholder="0" />
            <div className="flex items-center justify-between text-[12px] text-ink-muted">
              <span>المبلغ المطلوب:</span>
              <span className="tabular font-medium">{money(state.request?.requested_amount_sar)}</span>
            </div>
          </>
        )}
        {state.type === "docs_required" && (
          <>
            <p className="text-[13px] text-ink-muted">المستندات المطلوبة (مفصولة بفاصلة):</p>
            <textarea rows={2} value={docs} onChange={e => setDocs(e.target.value)}
              className="w-full rounded-lg border border-line px-3 py-2 text-[13px] text-ink focus:outline-none focus:ring-2 focus:ring-brand-200" />
          </>
        )}
        <p className="text-[13px] text-ink-muted">
          {state.type === "declined" ? "سبب الاعتذار:" : "سبب القرار:"}
        </p>
        <textarea rows={3} value={reason} onChange={e => setReason(e.target.value)}
          className="w-full rounded-lg border border-line px-3 py-2 text-[13px] text-ink focus:outline-none focus:ring-2 focus:ring-brand-200" />
        {error && (
          <p className="text-[12.5px] text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
            {error}
          </p>
        )}
      </div>
    </U.Modal>
  ) : null;

  return { open, node, busy: submitting };
}

function RequestsPage() {
  const [prog, setProg] = useState(""); const [q, setQ] = useState("");
  const rq = A.useApi("/support-requests", "support-requests");
  const pr = A.useApi("/programs", "programs");
  const rows = (rq.data?.requests || []).filter(r => (!prog || r.program_id === prog) &&
    (!q || (r.title_ar + r.name_ar).includes(q)));
  const decision = useDecisionModal(() => rq.refresh());

  return (
    <div className="space-y-4">
      <PageHead title="طلبات الدعم" sub="طلبات المستفيدين ضمن برامج الجمعية الخمسة" />
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {(pr.data?.programs || []).map(p => {
          const n = (rq.data?.requests || []).filter(r => r.program_id === p.id).length;
          return (
            <button key={p.id} onClick={() => setProg(prog === p.id ? "" : p.id)}
              className={cx("text-right rounded-xl border p-4 transition-all bg-white",
                prog === p.id ? "border-brand-300 ring-2 ring-brand-100 shadow-card" : "border-line hover:shadow-card")}>
              <p className="text-[13px] font-medium text-ink">{p.name_ar}</p>
              <p className="text-[22px] font-semibold tabular text-brand-700 mt-1">{n}</p>
              <p className="text-[11px] text-ink-soft">{p.request_types_count} نوع طلب</p>
            </button>
          );
        })}
      </div>
      <Card>
        <div className="p-4 border-b border-line">
          <Input icon={I.search} placeholder="ابحث في الطلبات…" value={q} onChange={e => setQ(e.target.value)} />
        </div>
        <Table head={["رقم الطلب", "المستفيد", "البرنامج", "نوع الطلب", "التصنيف", "المرحلة", "المطلوب", "المعتمد", "إجراء"]}
               empty={!rows.length && "لا توجد طلبات"}>
          {rows.slice(0, 60).map(r => (
            <tr key={r.id} className="hover:bg-line-soft/50 transition-colors">
              <Td><span className="tabular text-[12px] text-ink-muted">{r.id}</span></Td>
              <Td><span className="text-[12.5px] font-medium text-ink">{r.name_ar}</span></Td>
              <Td><Badge tone="brand">{r.program_ar}</Badge></Td>
              <Td><span className="text-[12.5px] text-ink">{r.title_ar}</span></Td>
              <Td><Badge tone={r.internal_classification === "عاجل" ? "rose" : "slate"}>{r.internal_classification}</Badge></Td>
              <Td><Badge tone={STATUS_TONE[r.stage]} dot>{STAGE_AR[r.stage]}</Badge></Td>
              <Td><span className="tabular text-[12.5px]">{money(r.requested_amount_sar)}</span></Td>
              <Td><span className="tabular text-[12.5px] font-medium text-emerald-700">
                {r.approved_amount_sar ? money(r.approved_amount_sar) : "—"}</span></Td>
              <Td>
                {r.stage === "committee" && (
                  <div className="flex gap-1">
                    <Button size="sm" variant="outline" onClick={() => decision.open(r, "accepted")}>
                      قبول
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => decision.open(r, "docs_required")}>
                      مستندات
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => decision.open(r, "declined")}>
                      اعتذار
                    </Button>
                  </div>
                )}
                {r.stage === "decided" && r.approved_amount_sar && <span className="text-[12px] text-emerald-600 font-medium">✓ معتمد</span>}
              </Td>
            </tr>
          ))}
        </Table>
      </Card>

      {decision.node}
    </div>
  );
}

/* ============================================================ Committee */
function CommitteePage() {
  const cq = A.useApi("/committee/queue", "committee");
  const rows = cq.data?.queue || [];
  // Was three chained window.prompt() calls, which cannot show the case being
  // decided and gave no way to report why the API refused.
  const decision = useDecisionModal(() => cq.refresh());

  return (
    <div className="space-y-4">
      <PageHead title="اللجنة المختصة" sub="الحالات المعروضة للدراسة — مرتبة حسب درجة الاحتياج والأولوية" />
      <Card className="border-brand-100 bg-brand-50/40 p-4">
        <div className="flex gap-3">
          <Icon d={I.scale} className="w-4 h-4 text-brand-700 shrink-0 mt-0.5" />
          <p className="text-[12.5px] text-brand-900 leading-relaxed">
            يتم ترتيب الحالات تلقائيًا حسب <b>درجة الاحتياج</b> المحتسبة من نصيب الفرد الشهري بعد الالتزامات،
            بما يضمن تقديم الدعم وفق الاحتياج والأولوية. القرار النهائي يصدر من اللجنة وليس من النظام.
          </p>
        </div>
      </Card>
      <div className="grid md:grid-cols-2 gap-4">
        {rows.map((r, i) => (
          <Card key={r.support_request_id} className="p-5 animate-in" style={{ animationDelay: `${i * 40}ms` }}>
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex items-center gap-3 min-w-0">
                <Avatar name={r.name_ar} size={38} />
                <div className="min-w-0">
                  <p className="text-[14px] font-medium text-ink truncate">{r.name_ar}</p>
                  <p className="text-[11.5px] text-ink-soft tabular">{r.support_request_id}</p>
                </div>
              </div>
              <div className="text-left shrink-0">
                <p className="text-[10.5px] text-ink-muted">درجة الاحتياج</p>
                <p className={cx("text-[19px] font-semibold tabular",
                  r.need_score > 80 ? "text-rose-600" : r.need_score > 60 ? "text-amber-600" : "text-ink")}>
                  {r.need_score}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5 mb-3">
              <Badge tone="brand">{r.program_ar}</Badge>
              <Badge tone="slate">{r.title_ar}</Badge>
            </div>
            <dl className="grid grid-cols-3 gap-2 mb-3 pb-3 border-b border-line-soft">
              <Field label="المطلوب" value={money(r.requested_amount_sar)} mono />
              <Field label="نصيب الفرد" value={money(r.per_capita_monthly_sar)} mono />
              <Field label="أفراد الأسرة" value={r.household_size} mono />
            </dl>
            {r.recommendation_ar && (
              <p className="text-[12px] text-ink-muted leading-relaxed mb-3">
                <span className="text-ink font-medium">توصية الباحث: </span>{r.recommendation_ar}
              </p>
            )}
            <div className="flex gap-2">
              <Button size="sm" className="flex-1" onClick={() => decision.open(r, "accepted")}>
                <Icon d={I.check} className="w-3.5 h-3.5" /> قبول
              </Button>
              <Button size="sm" variant="outline" className="flex-1"
                onClick={() => decision.open(r, "docs_required")}>استكمال مستندات</Button>
              <Button size="sm" variant="ghost"
                onClick={() => decision.open(r, "declined")}>اعتذار</Button>
            </div>
          </Card>
        ))}
      </div>
      {!rows.length && <Card><Empty icon={I.scale} title="لا توجد حالات معروضة على اللجنة" /></Card>}
      {decision.node}
    </div>
  );
}

/* ============================================================ Finance */
function FinancePage() {
  const run = A.useApi("/finance/disbursement-run?days=60", "run");
  const ov = A.useApi("/reports/overview", "overview");
  const sp = A.useApi("/sponsorships", "sponsorships");
  const d = run.data || {}, o = ov.data || {};
  const [acting, setActing] = useState(null);
  const [notice, setNotice] = useState(null);

  const handleApprove = async (id) => {
    setActing(id); setNotice(null);
    try {
      await A.post(`/disbursements/${id}/approve`, { approved_by: "STF-06" });
      run.refresh();
    } catch (e) {
      // e.message carries the API's Arabic explanation (e.g. "لا يوجد ايبان…").
      setNotice({ tone: "error", text: e?.message || "تعذّر اعتماد الدفعة" });
    }
    setActing(null);
  };

  const handlePay = async (id) => {
    setActing(id); setNotice(null);
    try {
      const res = await A.post(`/disbursements/${id}/pay`);
      run.refresh(); ov.refresh();
      setNotice({ tone: "ok", text: res?.reply_ar || "تم الصرف بنجاح" });
    } catch (e) {
      setNotice({ tone: "error", text: e?.message || "تعذّر صرف الدفعة" });
    }
    setActing(null);
  };

  return (
    <div className="space-y-4">
      <PageHead title="الصرف والكفالات" sub="جدول الصرف الشهري والتحويلات للمستفيدين" />
      {notice && (
        <Card className={cx("px-4 py-3 flex items-start justify-between gap-3",
          notice.tone === "error" ? "border-rose-200 bg-rose-50/60" : "border-emerald-200 bg-emerald-50/60")}>
          <p className={cx("text-[12.5px]", notice.tone === "error" ? "text-rose-700" : "text-emerald-700")}>
            {notice.text}
          </p>
          <button onClick={() => setNotice(null)} className="text-ink-soft hover:text-ink shrink-0">
            <Icon d={I.x} className="w-3.5 h-3.5" />
          </button>
        </Card>
      )}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="إجمالي المصروف" value={money(o.payments_total_sar)} icon={I.wallet} tone="green" />
        <Stat label="مستحق خلال 60 يوم" value={money(d.total_sar)} icon={I.clock} tone="amber"
              hint={`${d.count ?? 0} دفعة`} />
        <Stat label="الكفالات النشطة" value={num(sp.data?.count ?? 0)} icon={I.gift} tone="violet"
              hint={`شهريًا ${money(sp.data?.monthly_total_sar)}`} />
        <Stat label="الملفات المعتمدة" value={num(o.beneficiaries?.by_status?.approved ?? 0)} icon={I.users} tone="brand" />
      </div>
      <div className="grid lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHead title="دفعات مستحقة" sub="خلال الستين يومًا القادمة" />
          <Table head={["تاريخ الاستحقاق", "المستفيد", "المبلغ", "الحالة", "إجراء"]}
                 empty={!d.disbursements?.length && "لا توجد دفعات مستحقة"}>
            {(d.disbursements || []).slice(0, 14).map(x => (
              <tr key={x.id}>
                <Td><span className="tabular text-[12.5px]">{x.due_date}</span></Td>
                <Td>
                  <span className="text-[12.5px] text-ink">{x.name_ar || "—"}</span>
                  <span className="block tabular text-[11px] text-ink-soft">{x.beneficiary_id}</span>
                </Td>
                <Td><span className="tabular text-[12.5px] font-medium">{money(x.amount)}</span></Td>
                <Td><Badge tone={STATUS_TONE[x.status]} dot>
                  {{ scheduled:"مجدول", approved:"معتمد", pending_approval:"بانتظار الاعتماد" }[x.status] || x.status}</Badge></Td>
                <Td>
                  {x.status === "scheduled" && (
                    <Button size="sm" variant="outline" disabled={acting === x.id}
                      onClick={() => handleApprove(x.id)}>
                      {acting === x.id ? "..." : "اعتماد"}
                    </Button>
                  )}
                  {x.status === "approved" && (
                    <Button size="sm" disabled={acting === x.id}
                      onClick={() => handlePay(x.id)}>
                      {acting === x.id ? "..." : "صرف"}
                    </Button>
                  )}
                  {x.status === "paid" && <span className="text-[12px] text-emerald-600 font-medium">✓ مصروف</span>}
                </Td>
              </tr>
            ))}
          </Table>
        </Card>
        <Card>
          <CardHead title="الصرف حسب البرنامج" />
          <div className="px-5 pb-5 space-y-3">
            {Object.entries(d.by_program_ar || {}).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between rounded-lg border border-line px-3 py-2.5">
                <span className="text-[12.5px] text-ink">{k}</span>
                <span className="text-[13px] font-medium tabular text-ink">{money(v)}</span>
              </div>
            ))}
            {!Object.keys(d.by_program_ar || {}).length && <Skeleton className="h-20" />}
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ============================================================ Channels (AI agents) */
function ChannelsPage() {
  const calls = A.useApi("/voice/calls?limit=20", "calls");
  const st = A.useApi("/crm/stats", "stats");
  const s = st.data || {};
  const rows = calls.data?.calls || [];
  const OUT = { resolved_by_bot:["مكتمل بالوكيل","green"], escalated_to_agent:["تحويل لموظف","amber"],
                ticket_created:["فتح تذكرة","sky"], voicemail:["بريد صوتي","slate"] };
  return (
    <div className="space-y-4">
      <PageHead title="قنوات الوكلاء الأذكياء" sub="نشاط وكلاء الذكاء الاصطناعي عبر الاتصال الهاتفي والواتساب" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="مكالمات هاتفية" value={num(rows.length)} icon={I.phone} tone="sky" />
        <Stat label="تذاكر الواتساب" value={num(s.by_channel?.whatsapp ?? 0)} icon={I.chat} tone="green" />
        <Stat label="مكتمل بالوكيل" value={num(rows.filter(r => r.outcome === "resolved_by_bot").length)}
              icon={I.spark} tone="brand" hint="دون تدخل موظف" />
        <Stat label="محوّل لموظف" value={num(rows.filter(r => r.outcome === "escalated_to_agent").length)}
              icon={I.users} tone="amber" />
      </div>
      <Card>
        <CardHead title="سجل المكالمات" sub="المكالمات الواردة عبر SIP ونتيجة كل مكالمة" />
        <Table head={["المتصل", "الاتجاه", "اللهجة", "الغرض", "المدة", "النتيجة", "الوقت"]}
               empty={!rows.length && "لا توجد مكالمات"}>
          {rows.map(r => {
            const [lbl, tone] = OUT[r.outcome] || ["—", "slate"];
            return (
              <tr key={r.id} className="hover:bg-line-soft/50 transition-colors">
                <Td>
                  <div className="flex items-center gap-2">
                    <span className={cx("w-1.5 h-1.5 rounded-full", r.identified ? "bg-emerald-500" : "bg-slate-300")} />
                    <span className="tabular text-[12.5px] text-ink">{r.from_number}</span>
                  </div>
                </Td>
                <Td><span className="text-[12px] text-ink-muted">{r.direction === "inbound" ? "وارد" : "صادر"}</span></Td>
                <Td><span className="text-[12px] text-ink-muted">{r.dialect || "—"}</span></Td>
                <Td><span className="text-[12.5px] text-ink">{r.intent || "—"}</span></Td>
                <Td><span className="tabular text-[12px] text-ink-muted">
                  {Math.floor((r.duration_sec || 0) / 60)}:{String((r.duration_sec || 0) % 60).padStart(2, "0")}</span></Td>
                <Td><Badge tone={tone} dot>{lbl}</Badge></Td>
                <Td><span className="text-[12px] text-ink-soft">{timeAgo(r.started_at)}</span></Td>
              </tr>
            );
          })}
        </Table>
      </Card>
    </div>
  );
}

/* ============================================================ Programs */
function ProgramsPage() {
  const pr = A.useApi("/programs", "programs");
  const [open, setOpen] = useState(null);
  const rt = A.useApi(open ? `/programs/${open}/request-types` : "",
    s => null, [open]);
  return (
    <div className="space-y-4">
      <PageHead title="برامج الجمعية" sub="خمسة برامج تندرج تحتها 43 نوع طلب" />
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {(pr.data?.programs || []).map((p, i) => (
          <Card key={p.id} hover className="p-5 animate-in" style={{ animationDelay: `${i * 50}ms` }}>
            <div className="flex items-start justify-between mb-3">
              <span className="inline-flex rounded-xl p-2.5 ring-1 ring-inset bg-brand-50 text-brand-700 ring-brand-100">
                <Icon d={[I.doc, I.spark, I.gift, I.home2, I.scale][i % 5]} className="w-5 h-5" />
              </span>
              <Badge tone="slate">{p.request_types_count} طلب</Badge>
            </div>
            <h3 className="text-[15px] font-semibold text-ink">{p.name_ar}</h3>
            <p className="text-[12.5px] text-ink-muted mt-1 leading-relaxed">{p.description_ar}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ============================================================ shared */
function PageHead({ title, sub, right }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[22px] font-semibold text-ink tracking-tight">{title}</h1>
        {sub && <p className="text-[13px] text-ink-muted mt-0.5">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

/* ============================================================ Agent Test Console */
// Shown while a tool runs, so a multi-round turn reads as progress rather than
// a stall. Falls back to the raw tool name for anything not listed.
const TOOL_LABEL_AR = {
  check_phone: "التحقق من رقم الجوال…",
  check_eligibility: "التحقق من الأهلية…",
  create_file: "إنشاء الملف…",
  get_file: "قراءة الملف…",
  update_section: "تحديث بيانات الملف…",
  get_completeness: "فحص اكتمال الملف…",
  submit_file: "رفع الملف للدراسة…",
  add_dependent: "إضافة تابع…",
  list_dependents: "قراءة التابعين…",
  update_document: "تحديث حالة المستند…",
  get_financial_profile: "قراءة الملف المالي…",
  add_obligation: "إضافة التزام شهري…",
  add_person_cost: "إضافة تكلفة معيشية…",
  search_request_types: "البحث عن نوع الطلب…",
  create_support_request: "تسجيل طلب الدعم…",
  get_support_request: "قراءة حالة الطلب…",
  add_request_detail: "إضافة تفاصيل للطلب…",
  search_faqs: "البحث في الأسئلة الشائعة…",
  create_ticket: "فتح تذكرة…",
  get_beneficiary_history: "قراءة السجل الشامل…",
  list_programs: "قراءة البرامج…",
  cancel_flow: "إلغاء العملية…",
};

function AgentTestPage() {
  const [phone, setPhone] = useState("966500287602");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeTool, setActiveTool] = useState(null);
  const [context, setContext] = useState(null);
  const chatEndRef = useRef(null);
  const { t } = U;

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", text, time: new Date() }]);
    setLoading(true);
    setActiveTool(null);

    // Placeholder the stream writes into, so the reply appears word by word
    // instead of after several seconds of silence.
    const slot = Date.now();
    setMessages(prev => [...prev, { role: "agent", text: "", time: new Date(), key: slot, streaming: true }]);
    const patchSlot = (fn) => setMessages(prev =>
      prev.map(m => (m.key === slot ? { ...m, ...fn(m) } : m)));

    try {
      await A.postStream("/agent/chat", { from_number: phone, text_ar: text }, (ev) => {
        if (ev.type === "delta") {
          patchSlot(m => ({ text: m.text + ev.text }));
        } else if (ev.type === "tool") {
          setActiveTool(ev.name);
        } else if (ev.type === "reset") {
          // what was streamed was the model's preamble before a tool call
          patchSlot(() => ({ text: "" }));
        } else if (ev.type === "error") {
          patchSlot(() => ({ role: "error", text: ev.message, streaming: false }));
        } else if (ev.type === "done") {
          patchSlot(() => ({ text: ev.reply, streaming: false }));
          if (ev.context) setContext(ev.context);
        }
      });
    } catch (e) {
      patchSlot(() => ({ role: "error", text: e?.message || t("connectionError"), streaming: false }));
    }
    patchSlot(() => ({ streaming: false }));
    setActiveTool(null);
    setLoading(false);
  };

  const resetSession = async () => {
    try {
      await A.post(`/agent/session/${phone}/reset`, {});
      setMessages([]);
      setContext(null);
    } catch (e) {}
  };

  const clearAllSessions = async () => {
    if (!confirm("Clear all sessions?")) return;
    try {
      await A.post("/agent/sessions/clear-all", {});
      setMessages([]);
      setContext(null);
    } catch (e) {}
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="space-y-4 animate-in">
      <PageHead
        title={t("agentTestTitle")}
        sub={t("agentTestSub")}
        right={
          <div className="flex gap-2">
            <Button variant="outline" onClick={resetSession}>
              <Icon d={I.x} className="w-4 h-4" /> {t("reset")}
            </Button>
            <Button variant="outline" onClick={clearAllSessions} className="text-red-600 border-red-200 hover:bg-red-50">
              <Icon d={I.x} className="w-4 h-4" /> Clear All Sessions
            </Button>
          </div>
        }
      />

      {/* Phone selector */}
      <Card className="p-4">
        <div className="flex items-center gap-3">
          <label className="text-[13px] font-medium text-ink whitespace-nowrap">{t("phoneNumber")}</label>
          <Input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="966500287602"
            className="flex-1 max-w-xs"
          />
          <Badge tone={context?.known ? "green" : "slate"} dot>
            {context?.known ? t("registeredBeneficiary") : t("newUser")}
          </Badge>
        </div>
      </Card>

      <div className="grid lg:grid-cols-3 gap-4">
        {/* Chat area */}
        <Card className="lg:col-span-2 flex flex-col" style={{ height: "500px" }}>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="p-3 rounded-xl bg-line-soft text-ink-soft mb-3">
                  <Icon d={I.chat} className="w-5 h-5" />
                </div>
                <p className="text-[14px] font-medium text-ink">{t("startChat")}</p>
                <p className="text-[12.5px] text-ink-muted mt-1">{t("startChatSub")}</p>
              </div>
            )}
            {messages.map((msg, i) => {
              // an agent bubble that has arrived empty is still waiting on the
              // first token — render the typing dots inside it, not after it
              const awaiting = msg.streaming && !msg.text;
              return (
                <div key={msg.key ?? i} className={cx("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                  <div className={cx(
                    "max-w-[80%] rounded-2xl px-4 py-2.5",
                    msg.role === "user" && "bg-brand-600 text-white rounded-br-md",
                    msg.role === "agent" && "bg-white border border-line text-ink rounded-bl-md shadow-card",
                    msg.role === "error" && "bg-rose-50 border border-rose-200 text-rose-700 rounded-bl-md"
                  )}>
                    {awaiting ? (
                      <div className="flex gap-1.5 py-1">
                        <span className="w-2 h-2 rounded-full bg-ink-soft animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="w-2 h-2 rounded-full bg-ink-soft animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="w-2 h-2 rounded-full bg-ink-soft animate-bounce" style={{ animationDelay: "300ms" }} />
                      </div>
                    ) : (
                      <p className="text-[13px] leading-relaxed whitespace-pre-wrap">
                        {msg.text}
                        {msg.streaming && <span className="inline-block w-[2px] h-[13px] align-middle mr-0.5 bg-brand-500 animate-pulse" />}
                      </p>
                    )}
                    {!msg.streaming && (
                      <p className={cx("text-[10px] mt-1", msg.role === "user" ? "text-brand-100" : "text-ink-soft")}>
                        {msg.time.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
            {activeTool && (
              <div className="flex justify-start">
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100 px-2.5 py-1 text-[11.5px] font-medium">
                  <Icon d={I.spark} className="w-3 h-3 animate-pulse" />
                  {TOOL_LABEL_AR[activeTool] || activeTool}
                </span>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-line p-3">
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t("typeMessage")}
                className="flex-1"
                disabled={loading}
              />
              <Button onClick={sendMessage} disabled={loading || !input.trim()}>
                <Icon d={I.arrow} className="w-4 h-4 rotate-180" />
              </Button>
            </div>
          </div>
        </Card>

        {/* Context panel */}
        <Card className="p-4 space-y-4">
          <h3 className="text-[14px] font-semibold text-ink flex items-center gap-2">
            <Icon d={I.spark} className="w-4 h-4 text-brand-600" />
            {t("conversationContext")}
          </h3>

          {!context ? (
            <div className="py-8 text-center">
              <p className="text-[12.5px] text-ink-soft">{t("startConversation")}</p>
            </div>
          ) : (
            <div className="space-y-3">
              <Field label={t("beneficiary")} value={context.name_ar || "—"} />
              <Field label={t("fileNumber")} value={context.file_no || "—"} />
              <Field label={t("fileStatus")} value={
                <Badge tone={STATUS_TONE[context.file_status] || "slate"}>
                  {FILE_STATUS_AR[context.file_status] || context.file_status}
                </Badge>
              } />
              <Field label={t("completion")} value={
                <div className="flex items-center gap-2">
                  <Progress value={context.completion_pct || 0} className="flex-1" />
                  <span className="text-[12px] tabular">{context.completion_pct || 0}%</span>
                </div>
              } />

              {context.missing_documents?.length > 0 && (
                <div>
                  <dt className="text-[11.5px] text-ink-muted mb-1">{t("missingDocs")}</dt>
                  <div className="flex flex-wrap gap-1">
                    {context.missing_documents.map((doc, i) => (
                      <Badge key={i} tone="amber">{doc}</Badge>
                    ))}
                  </div>
                </div>
              )}

              {context.open_requests?.length > 0 && (
                <div>
                  <dt className="text-[11.5px] text-ink-muted mb-1">{t("openRequests")}</dt>
                  {context.open_requests.map((req, i) => (
                    <Badge key={i} tone="sky">{req.id} ({req.stage})</Badge>
                  ))}
                </div>
              )}

              {context.next_disbursement && (
                <Field label={t("nextDisbursement")} value={
                  `${money(context.next_disbursement.amount)} - ${dateAr(context.next_disbursement.due_date)}`
                } />
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}


/* ================================================================ Voice test
   Talk to the same agent that answers the phone, from the browser.

   This exists so the voice channel can be demonstrated and debugged without
   a PBX, a SIP extension or a softphone: the microphone goes straight to the
   voice engine over a WebSocket, and the engine runs the identical
   STT -> agent -> TTS pipeline a real call runs. What you hear here is what
   a caller hears.

   Audio in is 16 kHz mono PCM16; audio out arrives as JSON headers followed
   by raw PCM at whatever rate the synthesizer produced. */
function VoiceTestPage() {
  const [phone, setPhone] = useState("96655000000");
  const [state, setState] = useState("idle");   // idle|connecting|listening|thinking|speaking
  const [turns, setTurns] = useState([]);
  const [tool, setTool] = useState(null);
  const [error, setError] = useState("");
  const endRef = useRef(null);
  const ws = useRef(null);
  const mic = useRef(null);          // {ctx, stream, node, source}
  const out = useRef(null);          // {ctx, playAt, queued}
  const pending = useRef(null);      // {rate, chunks[]} being received
  const { t } = U;

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns, tool]);
  useEffect(() => () => stop(), []);   // always release the microphone

  const say = (role, text) => setTurns(prev => {
    // The engine sends the reply sentence by sentence as it is spoken;
    // append to the open agent turn rather than making a bubble per sentence.
    if (role === "assistant" && prev.length && prev[prev.length - 1].role === "assistant") {
      const copy = prev.slice();
      copy[copy.length - 1] = { ...copy[copy.length - 1], text: copy[copy.length - 1].text + " " + text };
      return copy;
    }
    return [...prev, { role, text }];
  });

  /* ---- playback: queue each chunk after the previous one ends ---- */
  function playPcm(pcm, rate) {
    const ctx = out.current?.ctx;
    if (!ctx) return;
    const view = new DataView(pcm.buffer, pcm.byteOffset, pcm.byteLength);
    const samples = pcm.byteLength / 2;
    const buf = ctx.createBuffer(1, samples, rate);
    const channel = buf.getChannelData(0);
    for (let i = 0; i < samples; i++) channel[i] = view.getInt16(i * 2, true) / 32768;
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    const at = Math.max(ctx.currentTime, out.current.playAt);
    src.start(at);
    out.current.playAt = at + buf.duration;
    // Held so a barge-in can stop them. Chunks are scheduled several
    // seconds ahead, so without this the agent keeps talking over someone
    // who has already interrupted it — and the microphone keeps hearing it.
    out.current.queued.push(src);
  }

  /* Stop everything scheduled but not yet heard. The engine sends `flush`
     when it decides the visitor has interrupted; the phone transport does
     the same thing to its RTP playout buffer. */
  function flushPlayback() {
    if (!out.current) return;
    for (const src of out.current.queued) {
      try { src.stop(); } catch (e) { /* already finished */ }
    }
    out.current.queued = [];
    out.current.playAt = 0;
    pending.current = null;
  }

  async function start() {
    setError(""); setTurns([]); setTool(null); setState("connecting");
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          // Ask for everything the browser has. Its echo canceller is the
          // first line of defence against the microphone hearing the
          // agent's own reply — the engine's level gate is the second,
          // because this one only cancels what the browser knows it is
          // rendering, and never what leaks acoustically from a speaker.
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (e) {
      setError(t("voiceMicDenied")); setState("idle"); return;
    }
    let sessionId;
    try {
      const r = await fetch(A.VOICE_BASE + "/voice/session", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone }),
      });
      if (!r.ok) throw new Error(r.status);
      sessionId = (await r.json()).session_id;
    } catch (e) {
      stream.getTracks().forEach(tr => tr.stop());
      setError(t("voiceEngineDown")); setState("idle"); return;
    }

    // 16 kHz in — the rate the STT server wants, so nothing resamples twice.
    const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    const source = ctx.createMediaStreamSource(stream);
    const node = ctx.createScriptProcessor(2048, 1, 1);
    const playCtx = new (window.AudioContext || window.webkitAudioContext)();
    out.current = { ctx: playCtx, playAt: 0, queued: [] };

    const url = A.VOICE_BASE.replace(/^http/, "ws") + "/voice/ws/" + sessionId;
    const socket = new WebSocket(url);
    socket.binaryType = "arraybuffer";
    ws.current = socket;

    socket.onopen = () => {
      node.onaudioprocess = (ev) => {
        if (socket.readyState !== WebSocket.OPEN) return;
        const input = ev.inputBuffer.getChannelData(0);
        const pcm = new Int16Array(input.length);
        for (let i = 0; i < input.length; i++) {
          const v = Math.max(-1, Math.min(1, input[i]));
          pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
        }
        socket.send(pcm.buffer);
      };
      source.connect(node);
      node.connect(ctx.destination);   // Safari will not run the node otherwise
    };

    socket.onmessage = (ev) => {
      if (typeof ev.data !== "string") {
        if (pending.current) playPcm(new Uint8Array(ev.data), pending.current.rate);
        return;
      }
      let msg; try { msg = JSON.parse(ev.data); } catch { return; }
      if (msg.type === "state") setState(msg.value);
      else if (msg.type === "text") say(msg.role, msg.text);
      else if (msg.type === "tool") setTool(msg.name);
      else if (msg.type === "audio") pending.current = { rate: msg.rate };
      else if (msg.type === "audio_end") pending.current = null;
      else if (msg.type === "flush") flushPlayback();
      else if (msg.type === "reset") setTurns(prev =>
        prev.length && prev[prev.length - 1].role === "assistant" ? prev.slice(0, -1) : prev);
      else if (msg.type === "error") setError(msg.text || "");
    };
    socket.onerror = () => setError(t("voiceEngineDown"));
    socket.onclose = () => { if (mic.current) stop(); };

    mic.current = { ctx, stream, node, source };
    setState("listening");
  }

  function stop() {
    try { ws.current?.readyState === WebSocket.OPEN && ws.current.send(JSON.stringify({ type: "stop" })); } catch (e) { /* closing anyway */ }
    try { ws.current?.close(); } catch (e) { /* already gone */ }
    ws.current = null;
    if (mic.current) {
      const { ctx, stream, node, source } = mic.current;
      try { node.onaudioprocess = null; source.disconnect(); node.disconnect(); } catch (e) { /* torn down */ }
      stream.getTracks().forEach(tr => tr.stop());   // drops the browser's mic indicator
      try { ctx.close(); } catch (e) { /* already closed */ }
      mic.current = null;
    }
    if (out.current) { try { out.current.ctx.close(); } catch (e) { /* already closed */ } out.current = null; }
    pending.current = null;
    setState("idle"); setTool(null);
  }

  /* The agent keys a conversation on the phone number, so a browser test
     inherits whatever that number said on WhatsApp or on a call before —
     across days. That continuity is a real feature on a phone line, and a
     trap on a test page: an exchange that went wrong yesterday keeps
     steering today's, and there was no way to clear it from here. */
  async function resetConversation() {
    setTurns([]); setTool(null); setError("");
    try {
      // The backend proxies /agent/* through to :8002, same as the chat test.
      await A.post(`/agent/session/${encodeURIComponent(phone)}/reset`, {});
    } catch (e) {
      setError(t("voiceResetFailed"));
    }
  }

  const live = state !== "idle";
  const tone = { listening: "green", thinking: "amber", speaking: "sky", connecting: "slate" }[state] || "slate";

  return (
    <div className="space-y-4">
      <PageHead
        title={t("voiceTestTitle")}
        sub={t("voiceTestSub")}
        right={
          <Button variant="outline" onClick={resetConversation} disabled={live}>
            <Icon d={I.x} className="w-4 h-4" /> {t("voiceReset")}
          </Button>
        }
      />

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-[13px] font-medium text-ink whitespace-nowrap">
            {t("callerNumber")}
          </label>
          <Input value={phone} onChange={e => setPhone(e.target.value)}
                 disabled={live} dir="ltr" className="flex-1 max-w-xs" />
          {live ? (
            <Button onClick={stop} variant="danger">{t("voiceHangUp")}</Button>
          ) : (
            <Button onClick={start}>{t("voiceStart")}</Button>
          )}
          <Badge tone={tone} dot>{t("voiceState_" + state) || state}</Badge>
          {tool && <Badge tone="slate">{tool}</Badge>}
        </div>
        {error && <p className="mt-3 text-[12.5px] text-rose-600">{error}</p>}
        <p className="mt-3 text-[12px] text-ink-muted">{t("voiceHint")}</p>
      </Card>

      <Card className="flex flex-col" style={{ height: "460px" }}>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {turns.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="p-3 rounded-xl bg-line-soft text-ink-soft mb-3">
                <Icon d={I.spark} className="w-5 h-5" />
              </div>
              <p className="text-[14px] font-medium text-ink">{t("voiceEmpty")}</p>
              <p className="text-[12.5px] text-ink-muted mt-1">{t("voiceEmptySub")}</p>
            </div>
          )}
          {turns.map((turn, i) => (
            <div key={i} className={cx("flex", turn.role === "user" ? "justify-end" : "justify-start")}>
              <div className={cx("max-w-[80%] rounded-2xl px-4 py-2.5",
                turn.role === "user"
                  ? "bg-brand-600 text-white rounded-br-md"
                  : "bg-white border border-line text-ink rounded-bl-md shadow-card")}>
                <p className="text-[13px] leading-relaxed whitespace-pre-wrap">{turn.text}</p>
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </Card>
    </div>
  );
}

window.PAGES = { Dashboard, KanbanPage, TicketsPage, TicketSheet, BeneficiariesPage,
  BeneficiarySheet, RequestsPage, CommitteePage, FinancePage, ChannelsPage, ProgramsPage,
  AgentTestPage, VoiceTestPage };
