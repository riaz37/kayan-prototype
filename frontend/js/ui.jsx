/* ============================================================
   Kayan console — UI primitives (shadcn-flavoured) + API client
   Exposed on window.UI / window.API for the other bundles.
   ============================================================ */
const { useState, useEffect, useMemo, useRef, useCallback, createElement: h } = React;

/* ---------------------------------------------- utils */
const cx = (...a) => a.filter(Boolean).join(" ");
const nf = new Intl.NumberFormat("en-US");
const money = (v) => (v == null ? "—" : nf.format(Math.round(v)) + " ر.س");
const num = (v) => (v == null ? "—" : nf.format(v));
const dateAr = (s) => {
  if (!s) return "—";
  const d = new Date(String(s).replace("Z", ""));
  if (isNaN(d)) return String(s).slice(0, 10);
  return d.toLocaleDateString("ar-SA-u-nu-latn", { year: "numeric", month: "short", day: "numeric" });
};
const timeAgo = (s) => {
  if (!s) return "—";
  const d = new Date(String(s).replace("Z", ""));
  const mins = Math.floor((Date.now() - d.getTime()) / 60000);
  if (isNaN(mins)) return "—";
  if (mins < 1) return "الآن";
  if (mins < 60) return `قبل ${mins} د`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `قبل ${hrs} س`;
  return `قبل ${Math.floor(hrs / 24)} يوم`;
};

/* ---------------------------------------------- icons (inline, no dep) */
const Icon = ({ d, className = "w-4 h-4", stroke = 1.7, fill = "none" }) => (
  <svg viewBox="0 0 24 24" fill={fill} stroke="currentColor" strokeWidth={stroke}
       strokeLinecap="round" strokeLinejoin="round" className={className}>
    {typeof d === "string" ? <path d={d} /> : d}
  </svg>
);
const I = {
  home: "M3 10.5 12 3l9 7.5M5 9.5V21h14V9.5",
  users: <><circle cx="9" cy="8" r="3.2"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16.5 5.6a3.2 3.2 0 0 1 0 5.4M18 20a6 6 0 0 0-3-4.9"/></>,
  ticket: <><path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h11A2.5 2.5 0 0 1 20 8.5v1a2.5 2.5 0 0 0 0 5v1a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 15.5v-1a2.5 2.5 0 0 0 0-5Z"/><path d="M12 7v10" strokeDasharray="2 2"/></>,
  board: <><rect x="3" y="4" width="5" height="16" rx="1.5"/><rect x="9.5" y="4" width="5" height="10" rx="1.5"/><rect x="16" y="4" width="5" height="13" rx="1.5"/></>,
  inbox: <><path d="M3 13h4l1.5 3h7L17 13h4"/><path d="M4.6 5.5 3 13v5a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5l-1.6-7.5A2 2 0 0 0 17.5 4h-11a2 2 0 0 0-1.9 1.5Z"/></>,
  gift: <><rect x="3" y="9" width="18" height="11" rx="2"/><path d="M3 13h18M12 9v11"/><path d="M12 9S9.5 4 7.2 5.4C5.4 6.5 6.8 9 12 9Zm0 0s2.5-5 4.8-3.6C18.6 6.5 17.2 9 12 9Z"/></>,
  wallet: <><path d="M3 8a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M16.5 12.5h3.5v-3h-3.5a1.5 1.5 0 0 0 0 3Z"/></>,
  scale: <><path d="M12 4v16M7 8h10"/><path d="m5 8-2.5 6a2.8 2.8 0 0 0 5 0Zm14 0-2.5 6a2.8 2.8 0 0 0 5 0Z"/></>,
  chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>,
  phone: <><path d="M6.5 3.5 9 8l-2 2a12 12 0 0 0 5 5l2-2 4.5 2.5v3a2 2 0 0 1-2.2 2A17 17 0 0 1 2.5 5.7 2 2 0 0 1 4.5 3.5Z"/></>,
  chat: <><path d="M20 12a8 8 0 1 1-3.2-6.4"/><path d="M4 20.5 5.4 16"/><path d="M20.5 4.5v4h-4"/></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m20 20-4.5-4.5"/></>,
  bell: <><path d="M18 9a6 6 0 1 0-12 0c0 5-2 6-2 6h16s-2-1-2-6"/><path d="M10.5 20a2 2 0 0 0 3 0"/></>,
  check: "m4.5 12.5 5 5 10-11",
  x: "M6 6l12 12M18 6 6 18",
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5.5l3.5 2"/></>,
  doc: <><path d="M14 3v5h5"/><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/></>,
  chevron: "m14 6-6 6 6 6",
  arrow: "M5 12h14M13 6l6 6-6 6",
  alert: <><path d="M12 8v5M12 17h.01"/><path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></>,
  spark: <><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/><circle cx="12" cy="12" r="3.2"/></>,
  pin: <><path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11Z"/><circle cx="12" cy="10" r="2.6"/></>,
  home2: "M3 10.5 12 3l9 7.5M5 9.5V21h14V9.5",
  bot: <><rect x="4" y="6" width="16" height="12" rx="3"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><path d="M9 17.5c0 0 1.5 1 3 1s3-1 3-1"/></>,
  user: <><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></>,
};

/* ---------------------------------------------- primitives */
const Card = ({ className, children, hover, ...p }) => (
  <div {...p} className={cx("bg-white border border-line rounded-xl shadow-card",
    hover && "transition-shadow hover:shadow-pop", className)}>{children}</div>
);
const CardHead = ({ title, sub, action, className }) => (
  <div className={cx("flex items-start justify-between gap-3 px-5 pt-4 pb-3", className)}>
    <div>
      <h3 className="text-[15px] font-semibold text-ink tracking-tight">{title}</h3>
      {sub && <p className="text-[12.5px] text-ink-muted mt-0.5">{sub}</p>}
    </div>
    {action}
  </div>
);

const Button = ({ variant = "default", size = "md", className, children, ...p }) => {
  const v = {
    default: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm",
    soft: "bg-brand-50 text-brand-700 hover:bg-brand-100",
    outline: "bg-white text-ink border border-line hover:bg-line-soft",
    ghost: "text-ink-muted hover:bg-line-soft hover:text-ink",
    danger: "bg-rose-50 text-rose-700 hover:bg-rose-100",
  }[variant];
  const s = { sm: "h-8 px-2.5 text-[12.5px] gap-1.5", md: "h-9 px-3.5 text-[13px] gap-2",
              lg: "h-10 px-4 text-[13.5px] gap-2" }[size];
  return <button {...p} className={cx("inline-flex items-center justify-center rounded-lg font-medium",
    "transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300", v, s, className)}>{children}</button>;
};

const TONE = {
  brand:  "bg-brand-50 text-brand-700 ring-brand-100",
  green:  "bg-emerald-50 text-emerald-700 ring-emerald-100",
  amber:  "bg-amber-50 text-amber-700 ring-amber-100",
  sky:    "bg-sky-50 text-sky-700 ring-sky-100",
  rose:   "bg-rose-50 text-rose-700 ring-rose-100",
  violet: "bg-violet-50 text-violet-700 ring-violet-100",
  slate:  "bg-slate-50 text-slate-600 ring-slate-200/70",
};
const Badge = ({ tone = "slate", className, children, dot }) => (
  <span className={cx("inline-flex items-center gap-1.5 rounded-md px-2 py-[3px]",
    "text-[11.5px] font-medium ring-1 ring-inset whitespace-nowrap", TONE[tone], className)}>
    {dot && <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />}
    {children}
  </span>
);

const STATUS_TONE = {
  open: "green", "مفتوح": "green",
  in_progress: "sky", "جاري العمل": "sky",
  waiting_customer: "amber", "بانتظار العميل": "amber",
  replied: "violet", "تم الرد": "violet",
  expired: "rose", "منتهية المدة": "rose",
  closed: "slate", "مغلق": "slate",
  approved: "green", submitted: "sky", under_review: "amber", draft: "slate", rejected: "rose",
  paid: "green", scheduled: "sky", pending_approval: "amber",
  accepted: "green", declined: "rose", docs_required: "amber",
  decided: "green", committee: "violet", under_study: "sky",
  active: "green", completed: "slate",
};
const FILE_STATUS_AR = { draft:"مسودة", submitted:"مرفوع", under_review:"قيد المراجعة",
  approved:"معتمد", rejected:"مرفوض" };
const STAGE_AR = { submitted:"تم التقديم", under_study:"قيد الدراسة",
  committee:"لدى اللجنة", decided:"صدر القرار" };

const Input = ({ icon, className, ...p }) => (
  <div className="relative">
    {icon && <span className="absolute inset-y-0 right-3 flex items-center text-ink-soft pointer-events-none">
      <Icon d={icon} className="w-[15px] h-[15px]" /></span>}
    <input {...p} className={cx("w-full h-9 rounded-lg bg-white border border-line",
      "text-[13px] placeholder:text-ink-soft text-ink transition",
      "focus:outline-none focus:ring-2 focus:ring-brand-100 focus:border-brand-300",
      icon ? "pr-9 pl-3" : "px-3", className)} />
  </div>
);

const Select = ({ className, children, ...p }) => (
  <select {...p} className={cx("h-9 rounded-lg bg-white border border-line px-3 text-[13px] text-ink",
    "focus:outline-none focus:ring-2 focus:ring-brand-100 focus:border-brand-300", className)}>{children}</select>
);

const Progress = ({ value = 0, tone = "brand", className }) => {
  const bar = { brand:"bg-brand-500", green:"bg-emerald-500", amber:"bg-amber-500", rose:"bg-rose-500" }[tone];
  return (
    <div className={cx("h-1.5 w-full rounded-full bg-line-soft overflow-hidden", className)}>
      <div className={cx("h-full rounded-full transition-all duration-700", bar)} style={{ width: `${Math.max(0,Math.min(100,value))}%` }} />
    </div>
  );
};

const Ring = ({ value = 0, size = 62, stroke = 5, label }) => {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  const tone = value >= 90 ? "#059669" : value >= 50 ? "#0F8478" : "#D97706";
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#F2F4F7" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={tone} strokeWidth={stroke}
          strokeDasharray={c} strokeDashoffset={c - (c * Math.min(100,value)) / 100} strokeLinecap="round"
          style={{ transition: "stroke-dashoffset .9s cubic-bezier(.16,1,.3,1)" }} />
      </svg>
      <span className="absolute text-[13px] font-semibold tabular text-ink">{Math.round(value)}<span className="text-[9px] text-ink-soft">%</span></span>
      {label && <span className="absolute -bottom-5 text-[11px] text-ink-muted whitespace-nowrap">{label}</span>}
    </div>
  );
};

const Avatar = ({ name = "", size = 34, tone }) => {
  const letters = (name || "؟").trim().split(/\s+/).slice(0, 1).map(w => w[0]).join("");
  const tones = ["bg-brand-50 text-brand-700","bg-violet-50 text-violet-700","bg-amber-50 text-amber-700",
                 "bg-sky-50 text-sky-700","bg-emerald-50 text-emerald-700","bg-rose-50 text-rose-700"];
  const t = tone || tones[(name || "").length % tones.length];
  return <span className={cx("inline-flex items-center justify-center rounded-full font-semibold shrink-0", t)}
    style={{ width: size, height: size, fontSize: size * 0.38 }}>{letters}</span>;
};

const Stat = ({ label, value, hint, tone = "slate", icon, onClick }) => (
  <Card hover={!!onClick} onClick={onClick}
    className={cx("p-4 animate-in", onClick && "cursor-pointer")}>
    <div className="flex items-start justify-between">
      <div className="min-w-0">
        <p className="text-[12px] text-ink-muted font-medium">{label}</p>
        <p className="text-[26px] leading-9 font-semibold tabular text-ink mt-0.5">{value}</p>
        {hint && <p className="text-[11.5px] text-ink-soft mt-0.5 truncate">{hint}</p>}
      </div>
      {icon && <span className={cx("rounded-lg p-2 ring-1 ring-inset", TONE[tone])}>
        <Icon d={icon} className="w-[17px] h-[17px]" /></span>}
    </div>
  </Card>
);

const Table = ({ head, children, empty }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-[13px]">
      <thead>
        <tr className="border-b border-line">
          {head.map((hd, i) => (
            <th key={i} className="text-right font-medium text-ink-muted text-[12px] px-4 py-2.5 whitespace-nowrap">{hd}</th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-line-soft">{children}</tbody>
    </table>
    {empty && <div className="py-12 text-center text-[13px] text-ink-soft">{empty}</div>}
  </div>
);
const Td = ({ className, children, ...p }) => <td {...p} className={cx("px-4 py-2.5 align-middle", className)}>{children}</td>;

const Tabs = ({ tabs, value, onChange }) => (
  <div className="inline-flex items-center gap-1 p-1 rounded-xl bg-line-soft">
    {tabs.map(t => (
      <button key={t.id} onClick={() => onChange(t.id)}
        className={cx("h-8 px-3 rounded-lg text-[12.5px] font-medium transition-all",
          value === t.id ? "bg-white text-ink shadow-card" : "text-ink-muted hover:text-ink")}>
        {t.label}{t.count != null && <span className="mr-1.5 text-[11px] text-ink-soft tabular">{t.count}</span>}
      </button>
    ))}
  </div>
);

const Sheet = ({ open, onClose, title, sub, children, width = "max-w-2xl" }) => {
  useEffect(() => {
    const k = (e) => e.key === "Escape" && onClose();
    if (open) { document.addEventListener("keydown", k); document.body.style.overflow = "hidden"; }
    return () => { document.removeEventListener("keydown", k); document.body.style.overflow = ""; };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-slate-900/20 backdrop-blur-[2px] animate-in" onClick={onClose} />
      <div className={cx("relative mr-auto h-full w-full bg-canvas shadow-pop overflow-y-auto", width)}
           style={{ animation: "in .3s cubic-bezier(.16,1,.3,1) both" }}>
        <div className="sticky top-0 z-10 bg-white/85 backdrop-blur border-b border-line px-6 py-4 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-[16px] font-semibold text-ink truncate">{title}</h2>
            {sub && <p className="text-[12.5px] text-ink-muted mt-0.5 truncate">{sub}</p>}
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} className="shrink-0">
            <Icon d={I.x} className="w-4 h-4" />
          </Button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
};

const Modal = ({ open, onClose, title, sub, children, footer }) => {
  useEffect(() => {
    const k = (e) => e.key === "Escape" && onClose();
    if (open) { document.addEventListener("keydown", k); document.body.style.overflow = "hidden"; }
    return () => { document.removeEventListener("keydown", k); document.body.style.overflow = ""; };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/30 backdrop-blur-[2px] animate-in" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-pop w-full max-w-md animate-in"
           style={{ animation: "in .2s cubic-bezier(.16,1,.3,1) both" }}>
        <div className="px-6 pt-5 pb-4">
          <h2 className="text-[16px] font-semibold text-ink">{title}</h2>
          {sub && <p className="text-[12.5px] text-ink-muted mt-1">{sub}</p>}
        </div>
        <div className="px-6 pb-4">{children}</div>
        {footer && <div className="px-6 py-3 bg-line-soft/40 border-t border-line rounded-b-2xl flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
};

const Empty = ({ icon = I.inbox, title, sub }) => (
  <div className="py-16 text-center">
    <div className="inline-flex p-3 rounded-xl bg-line-soft text-ink-soft mb-3"><Icon d={icon} className="w-5 h-5" /></div>
    <p className="text-[14px] font-medium text-ink">{title}</p>
    {sub && <p className="text-[12.5px] text-ink-muted mt-1">{sub}</p>}
  </div>
);

const Skeleton = ({ className }) => <div className={cx("animate-pulse rounded-lg bg-line-soft", className)} />;

const Field = ({ label, value, mono }) => (
  <div className="min-w-0">
    <dt className="text-[11.5px] text-ink-muted">{label}</dt>
    <dd className={cx("text-[13px] text-ink mt-0.5 truncate", mono && "tabular")}>{value ?? "—"}</dd>
  </div>
);

/* ---------------------------------------------- API client */
/* Resolution order:
     1. ?api=<url>            — override for one session (persisted)
     2. window.KAYAN_API_BASE — set by a <script> tag or config.js
     3. localhost             — the local backend, so `./run.sh` is self-contained
     4. otherwise             — the deployed backend
   Previously both branches of this were the same hardcoded Railway URL, so a
   developer running the console locally still hit production. */
const DEFAULT_REMOTE_API = "https://kayan-prototype-production.up.railway.app";

function resolveApiBase() {
  const param = new URLSearchParams(window.location.search).get("api");
  if (param) {
    try { localStorage.setItem("kayan-api-base", param); } catch (e) { /* private mode */ }
    return param.replace(/\/$/, "");
  }
  let stored = null;
  try { stored = localStorage.getItem("kayan-api-base"); } catch (e) { /* private mode */ }
  if (stored) return stored.replace(/\/$/, "");
  if (window.KAYAN_API_BASE) return String(window.KAYAN_API_BASE).replace(/\/$/, "");
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1" || host === "[::1]") {
    return "http://localhost:8001";
  }
  return DEFAULT_REMOTE_API;
}

const API_BASE = resolveApiBase();

/* The voice engine is a separate process on :8004 (the browser talks to it
   directly over a WebSocket — audio never goes through the backend).
   Same resolution order as the API base: ?voice= wins and is remembered,
   otherwise it is assumed to sit beside the backend. */
function resolveVoiceBase() {
  const param = new URLSearchParams(window.location.search).get("voice");
  if (param) {
    try { localStorage.setItem("kayan-voice-base", param); } catch (e) { /* private mode */ }
    return param.replace(/\/$/, "");
  }
  let stored = null;
  try { stored = localStorage.getItem("kayan-voice-base"); } catch (e) { /* private mode */ }
  if (stored) return stored.replace(/\/$/, "");
  if (window.KAYAN_VOICE_BASE) return String(window.KAYAN_VOICE_BASE).replace(/\/$/, "");
  return API_BASE.replace(/:8001$/, ":8004");
}

const VOICE_BASE = resolveVoiceBase();
let SNAP = null;

async function loadSnapshot() {
  if (SNAP) return SNAP;
  try { SNAP = await (await fetch("snapshot.json")).json(); } catch { SNAP = {}; }
  return SNAP;
}

/** Try the live API; fall back to the bundled snapshot so the UI always renders. */
async function get(path, fallbackKey) {
  try {
    const r = await fetch(API_BASE + path, { headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error(r.status);
    return { data: await r.json(), live: true };
  } catch (e) {
    const s = await loadSnapshot();
    if (typeof fallbackKey === "function") return { data: fallbackKey(s), live: false };
    return { data: s[fallbackKey] ?? null, live: false };
  }
}

/** Send a request and, on failure, throw an Error carrying the parsed body.
 *  The API explains refusals in `detail.reply_ar` (ceiling exceeded, file not
 *  approved, window closed…). Throwing only the status code discarded all of
 *  that and left the console showing a generic "خطأ". */
async function send(method, path, body) {
  const r = await fetch(API_BASE + path, {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  let payload = null;
  try { payload = await r.json(); } catch (e) { payload = null; }
  if (!r.ok) {
    const detail = payload?.detail;
    const message = (typeof detail === "string" && detail)
      || detail?.reply_ar || detail?.message
      || (Array.isArray(detail) ? detail.map(d => d.msg).join("، ") : null)
      || `HTTP ${r.status}`;
    const err = new Error(message);
    err.status = r.status;
    err.detail = detail;
    throw err;
  }
  return payload;
}

const post = (path, body) => send("POST", path, body);
const patch = (path, body) => send("PATCH", path, body);

/** POST and consume a Server-Sent Events response.
 *  Calls onEvent(payload) for each `data:` line as it arrives.
 *  EventSource cannot POST, so this reads the body stream directly. */
async function postStream(path, body, onEvent, { signal } = {}) {
  const r = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body ?? {}),
    signal,
  });
  if (!r.ok || !r.body) {
    let detail = null;
    try { detail = (await r.json())?.detail; } catch (e) { /* not json */ }
    throw new Error(detail?.reply_ar || detail?.message || detail || `HTTP ${r.status}`);
  }
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // events are separated by a blank line; keep any partial tail in the buffer
    const parts = buffer.split("\n\n");
    buffer = parts.pop();
    for (const part of parts) {
      for (const line of part.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const raw = line.slice(5).trim();
        if (!raw) continue;
        try { onEvent(JSON.parse(raw)); } catch (e) { console.warn("bad SSE payload", raw); }
      }
    }
  }
}

function useApi(path, fallbackKey, deps = []) {
  const [state, setState] = useState({ loading: true, data: null, live: false });
  const refreshKey = useRef(0);
  useEffect(() => {
    let dead = false;
    setState(s => ({ ...s, loading: true }));
    get(path, fallbackKey).then(r => { if (!dead) setState({ loading: false, ...r }); });
    return () => { dead = true; };
  }, [...deps, refreshKey.current]);
  const refresh = useCallback(() => {
    refreshKey.current += 1;
    setState(s => ({ ...s, loading: true }));
    get(path, fallbackKey).then(r => setState({ loading: false, ...r }));
  }, [path, fallbackKey]);
  return { ...state, refresh };
}

/* ---------------------------------------------- translations */
const TRANSLATIONS = {
  ar: {
    // Navigation
    home: "الرئيسية",
    dashboard: "لوحة المعلومات",
    ticketBoard: "لوحة التذاكر",
    tickets: "التذاكر والطلبات",
    beneficiariesGroup: "المستفيدون",
    beneficiaryFiles: "ملفات المستفيدين",
    supportRequests: "طلبات الدعم",
    committee: "اللجنة المختصة",
    operations: "التشغيل",
    finance: "الصرف والكفالات",
    programs: "البرامج",
    channels: "قنوات الوكلاء",
    agentGroup: "الوكيل",
    agentTest: "اختبار الوكيل",
    voiceTest: "اختبار المكالمة",
    voiceTestTitle: "اختبار المكالمة الصوتية",
    voiceTestSub: "تحدث مع نفس الوكيل الذي يرد على الهاتف، من المتصفح مباشرة",
    voiceReset: "محادثة جديدة",
    voiceResetFailed: "تعذر مسح المحادثة السابقة",
    callerNumber: "رقم المتصل",
    voiceStart: "ابدأ المكالمة",
    voiceHangUp: "انه المكالمة",
    voiceHint: "استخدم رقم مستفيد مسجل ليتعرف عليك الوكيل. تحدث بشكل طبيعي، ويمكنك مقاطعته.",
    voiceEmpty: "لا توجد مكالمة نشطة",
    voiceEmptySub: "اضغط ابدأ المكالمة وتحدث بالعربية",
    voiceMicDenied: "تعذر الوصول الى الميكروفون. يرجى السماح بالوصول من اعدادات المتصفح.",
    voiceEngineDown: "تعذر الاتصال بخدمة الصوت. تاكد من تشغيلها على المنفذ 8004.",
    voiceState_idle: "غير متصل",
    voiceState_connecting: "جاري الاتصال",
    voiceState_listening: "يستمع",
    voiceState_thinking: "يفكر",
    voiceState_speaking: "يتحدث",
    // Topbar
    search: "ابحث عن مستفيد، تذكرة، أو طلب…",
    connected: "متصل بالنظام",
    demoMode: "وضع العرض",
    // Agent Test
    agentTestTitle: "اختبار الوكيل الذكي",
    agentTestSub: "محاكاة محادثة واتساب مع وكيل Qwen",
    reset: "إعادة تعيين",
    phoneNumber: "رقم الجوال:",
    registeredBeneficiary: "مستفيد مسجل",
    newUser: "مستخدم جديد",
    startChat: "ابدأ المحادثة",
    startChatSub: "أرسل رسالة لمحاكاة محادثة واتساب",
    typeMessage: "اكتب رسالتك هنا...",
    conversationContext: "سياق المحادثة",
    startConversation: "ابدأ محادثة لعرض السياق",
    beneficiary: "المستفيد",
    fileNumber: "رقم الملف",
    fileStatus: "حالة الملف",
    completion: "نسبة الإكمال",
    missingDocs: "مستندات ناقصة",
    openRequests: "طلبات مفتوحة",
    nextDisbursement: "الدفعة القادمة",
    connectionError: "خطأ في الاتصال بالوكيل",
    // Common
    save: "حفظ",
    cancel: "إلغاء",
    delete: "حذف",
    edit: "تعديل",
    view: "عرض",
    close: "إغلاق",
    loading: "جاري التحميل...",
    noData: "لا توجد بيانات",
    // File statuses
    draft: "مسودة",
    submitted: "مرفوع",
    underReview: "قيد المراجعة",
    approved: "معتمد",
    rejected: "مرفوض",
  },
  en: {
    // Navigation
    home: "Home",
    dashboard: "Dashboard",
    ticketBoard: "Ticket Board",
    tickets: "Tickets & Requests",
    beneficiariesGroup: "Beneficiaries",
    beneficiaryFiles: "Beneficiary Files",
    supportRequests: "Support Requests",
    committee: "Committee",
    operations: "Operations",
    finance: "Finance & Sponsorships",
    programs: "Programs",
    channels: "Channels",
    agentGroup: "Agent",
    agentTest: "Agent Test",
    voiceTest: "Voice Test",
    voiceTestTitle: "Voice call test",
    voiceTestSub: "Talk to the same agent that answers the phone, from the browser",
    voiceReset: "New conversation",
    voiceResetFailed: "Could not clear the previous conversation",
    callerNumber: "Caller number",
    voiceStart: "Start call",
    voiceHangUp: "Hang up",
    voiceHint: "Use a registered beneficiary's number so the agent identifies you. Speak naturally — you can interrupt it.",
    voiceEmpty: "No active call",
    voiceEmptySub: "Press Start call and speak in Arabic",
    voiceMicDenied: "Could not access the microphone. Allow access in your browser settings.",
    voiceEngineDown: "Could not reach the voice engine. Check it is running on port 8004.",
    voiceState_idle: "Idle",
    voiceState_connecting: "Connecting",
    voiceState_listening: "Listening",
    voiceState_thinking: "Thinking",
    voiceState_speaking: "Speaking",
    // Topbar
    search: "Search beneficiary, ticket, or request…",
    connected: "Connected",
    demoMode: "Demo Mode",
    // Agent Test
    agentTestTitle: "AI Agent Test",
    agentTestSub: "Simulate WhatsApp chat with Qwen agent",
    reset: "Reset",
    phoneNumber: "Phone Number:",
    registeredBeneficiary: "Registered",
    newUser: "New User",
    startChat: "Start Chat",
    startChatSub: "Send a message to simulate a WhatsApp conversation",
    typeMessage: "Type your message here...",
    conversationContext: "Conversation Context",
    startConversation: "Start a conversation to see context",
    beneficiary: "Beneficiary",
    fileNumber: "File Number",
    fileStatus: "File Status",
    completion: "Completion",
    missingDocs: "Missing Documents",
    openRequests: "Open Requests",
    nextDisbursement: "Next Disbursement",
    connectionError: "Connection error with agent",
    // Common
    save: "Save",
    cancel: "Cancel",
    delete: "Delete",
    edit: "Edit",
    view: "View",
    close: "Close",
    loading: "Loading...",
    noData: "No data",
    // File statuses
    draft: "Draft",
    submitted: "Submitted",
    underReview: "Under Review",
    approved: "Approved",
    rejected: "Rejected",
  },
};

let _lang = localStorage.getItem("kayan-lang") || "ar";
const _langListeners = new Set();

function setLang(lang) {
  _lang = lang;
  localStorage.setItem("kayan-lang", lang);
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  document.documentElement.lang = lang;
  _langListeners.forEach(fn => fn(lang));
}

function getLang() { return _lang; }

function useLang() {
  const [lang, setLangState] = useState(_lang);
  useEffect(() => {
    _langListeners.add(setLangState);
    return () => _langListeners.delete(setLangState);
  }, []);
  return [lang, setLang];
}

function t(key) {
  return TRANSLATIONS[_lang]?.[key] || TRANSLATIONS.ar[key] || key;
}

window.UI = { cx, nf, money, num, dateAr, timeAgo, Icon, I, Card, CardHead, Button, Badge, TONE,
  STATUS_TONE, FILE_STATUS_AR, STAGE_AR, Input, Select, Progress, Ring, Avatar, Stat, Table, Td,
  Tabs, Sheet, Modal, Empty, Skeleton, Field, t, useLang, setLang, getLang };
window.API = { get, post, patch, postStream, useApi, loadSnapshot, API_BASE, VOICE_BASE };
