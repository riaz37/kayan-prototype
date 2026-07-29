/* ============================================================
   Kayan console — app shell (sidebar, topbar, router)
   ============================================================ */
const { useState, useEffect } = React;
const U2 = window.UI, A2 = window.API, P = window.PAGES;
const { cx, Icon, I, Button, Input, Badge, Avatar, t, useLang, setLang } = U2;

function getNav() {
  return [
    { group: t("home"), items: [
      { id: "dashboard",     label: t("dashboard"), icon: I.home },
      { id: "kanban",        label: t("ticketBoard"),   icon: I.board },
      { id: "tickets",       label: t("tickets"), icon: I.ticket },
    ]},
    { group: t("beneficiariesGroup"), items: [
      { id: "beneficiaries", label: t("beneficiaryFiles"), icon: I.users },
      { id: "requests",      label: t("supportRequests"),     icon: I.doc },
      { id: "committee",     label: t("committee"),  icon: I.scale },
    ]},
    { group: t("operations"), items: [
      { id: "finance",       label: t("finance"), icon: I.wallet },
      { id: "programs",      label: t("programs"),          icon: I.gift },
      { id: "channels",      label: t("channels"),    icon: I.spark },
    ]},
    { group: t("agentGroup"), items: [
      { id: "agent-test",    label: t("agentTest"),    icon: I.spark },
    ]},
  ];
}

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative w-9 h-9 rounded-xl bg-brand-600 grid place-items-center shadow-sm">
        <span className="text-white font-bold text-[15px] leading-none">K</span>
        <span className="absolute -bottom-0.5 -left-0.5 w-2.5 h-2.5 rounded-[4px] bg-brand-300 ring-2 ring-white" />
      </div>
      <div className="leading-tight">
        <p className="text-[14px] font-semibold text-ink">Kayan Association</p>
        <p className="text-[10.5px] text-ink-soft">Beneficiary Management</p>
      </div>
    </div>
  );
}

function Sidebar({ page, go, open, setOpen }) {
  const NAV = getNav();
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-slate-900/20 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={cx(
        "fixed lg:sticky top-0 z-40 h-screen w-[248px] shrink-0 bg-white border-l border-line",
        "flex flex-col transition-transform duration-300 lg:translate-x-0",
        open ? "translate-x-0" : "translate-x-full lg:translate-x-0")}>
        <div className="h-16 px-5 flex items-center border-b border-line-soft"><Logo /></div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
          {NAV.map(g => (
            <div key={g.group}>
              <p className="px-2.5 mb-1.5 text-[10.5px] font-medium text-ink-soft tracking-wide">{g.group}</p>
              <div className="space-y-0.5">
                {g.items.map(it => {
                  const active = page === it.id;
                  return (
                    <button key={it.id} onClick={() => { go(it.id); setOpen(false); }}
                      className={cx("w-full flex items-center gap-2.5 h-9 px-2.5 rounded-lg text-[13px] font-medium transition-all",
                        active ? "bg-brand-50 text-brand-700" : "text-ink-muted hover:bg-line-soft hover:text-ink")}>
                      <Icon d={it.icon} className={cx("w-[17px] h-[17px] shrink-0", active && "text-brand-600")} />
                      <span className="truncate">{it.label}</span>
                      {active && <span className="mr-auto w-1 h-4 rounded-full bg-brand-500" />}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="p-3 border-t border-line-soft">
          <div className="rounded-xl bg-gradient-to-l from-brand-50 to-white border border-brand-100/70 p-3">
            <div className="flex items-center gap-2 mb-1.5">
              <Icon d={I.spark} className="w-3.5 h-3.5 text-brand-600" />
              <p className="text-[12px] font-medium text-brand-900">Agents Active</p>
            </div>
            <p className="text-[11px] text-brand-800/80 leading-relaxed">
              Voice and WhatsApp are connected and receiving beneficiary requests
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}

function Topbar({ setOpen, live }) {
  const [lang, setLangFn] = useLang();
  const isEn = lang === "en";

  const toggleLang = () => {
    setLangFn(isEn ? "ar" : "en");
  };

  return (
    <header className="sticky top-0 z-20 h-16 bg-canvas/85 backdrop-blur border-b border-line
                       flex items-center gap-3 px-4 sm:px-6">
      <Button variant="ghost" size="sm" className="lg:hidden" onClick={() => setOpen(true)}>
        <Icon d="M4 6h16M4 12h16M4 18h16" className="w-5 h-5" />
      </Button>
      <div className="flex-1 max-w-md hidden sm:block">
        <Input icon={I.search} placeholder={t("search")} />
      </div>
      <div className="mr-auto flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={toggleLang}
          className="text-[12px] font-medium px-2.5">
          {isEn ? "AR" : "EN"}
        </Button>
        <span className={cx("hidden sm:inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11.5px] font-medium ring-1 ring-inset",
          live ? "bg-emerald-50 text-emerald-700 ring-emerald-100" : "bg-amber-50 text-amber-700 ring-amber-100")}>
          <span className={cx("w-1.5 h-1.5 rounded-full", live ? "bg-emerald-500 animate-pulse" : "bg-amber-500")} />
          {live ? t("connected") : t("demoMode")}
        </span>
        <Button variant="ghost" size="sm" className="relative">
          <Icon d={I.bell} className="w-[18px] h-[18px]" />
          <span className="absolute top-1 left-1 w-1.5 h-1.5 rounded-full bg-rose-500 ring-2 ring-canvas" />
        </Button>
        <div className="flex items-center gap-2.5 pr-2 border-r border-line">
          <div className="text-left hidden sm:block leading-tight">
            <p className="text-[12.5px] font-medium text-ink">Shaden Al-Fasaily</p>
            <p className="text-[10.5px] text-ink-soft">System Admin</p>
          </div>
          <Avatar name="Shaden" size={34} />
        </div>
      </div>
    </header>
  );
}

function App() {
  const [page, setPage] = useState("dashboard");
  const [navOpen, setNavOpen] = useState(false);
  const [ticket, setTicket] = useState(null);
  const [ben, setBen] = useState(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    A2.get("/health").then(r => setLive(r.live)).catch(() => setLive(false));
  }, []);
  useEffect(() => { window.scrollTo({ top: 0, behavior: "smooth" }); }, [page]);

  const go = (p) => setPage(p);
  const Page = {
    dashboard: () => <P.Dashboard go={go} />,
    kanban: () => <P.KanbanPage openTicket={setTicket} />,
    tickets: () => <P.TicketsPage openTicket={setTicket} />,
    beneficiaries: () => <P.BeneficiariesPage openBen={setBen} />,
    requests: () => <P.RequestsPage />,
    committee: () => <P.CommitteePage />,
    finance: () => <P.FinancePage />,
    programs: () => <P.ProgramsPage />,
    channels: () => <P.ChannelsPage />,
    "agent-test": () => <P.AgentTestPage />,
  }[page] || (() => <P.Dashboard go={go} />);

  return (
    <div className="flex min-h-screen">
      <Sidebar page={page} go={go} open={navOpen} setOpen={setNavOpen} />
      <div className="flex-1 min-w-0 flex flex-col">
        <Topbar setOpen={setNavOpen} live={live} />
        <main className="flex-1 p-4 sm:p-6 max-w-[1400px] w-full mx-auto">
          <div key={page} className="animate-in"><Page /></div>
        </main>
        <footer className="px-6 py-4 text-center text-[11.5px] text-ink-soft border-t border-line-soft">
          Prototype — All data is synthetic · Kayan Association for Orphans · Beneficiary Services 0506094154
        </footer>
      </div>
      <P.TicketSheet id={ticket} onClose={() => setTicket(null)} />
      <P.BeneficiarySheet id={ben} onClose={() => setBen(null)} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
