"use client";

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Bot,
  Check,
  CheckCheck,
  ChevronDown,
  Clock,
  Info,
  LoaderCircle,
  MessageCircle,
  SendHorizontal,
  User,
} from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { DataText, LoadError, NameAvatar, StatusBadge } from "@/components/kayan/primitives";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { useDetailNav } from "@/components/shell/use-detail-nav";
import { api } from "@/lib/api/client";
import { useRevalidate, useTicket } from "@/lib/api/hooks";
import type { TicketMessage } from "@/lib/api/types";
import { parseApiDate } from "@/lib/i18n/format";
import { formatMessage } from "@/lib/rich-text";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 30;

type ReplyResult = { whatsapp_sent?: boolean; warning_ar?: string | null };

export function TicketSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <Sheet open={!!id} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="end" className="max-w-3xl" closeLabel={t.common.close}>
        {id && <TicketConversation key={id} id={id} />}
      </SheetContent>
    </Sheet>
  );
}

function TicketConversation({ id }: { id: string }) {
  const { t, fmt, format, label, personName } = useI18n();
  const { data: d, error, isLoading, mutate } = useTicket(id);
  const revalidate = useRevalidate();
  const { openTicket, openBeneficiary } = useDetailNav();
  const canManage = useSession().can("tickets:manage");

  const [reply, setReply] = useState("");
  const [viaWhatsapp, setViaWhatsapp] = useState(true);
  const [sending, setSending] = useState(false);
  const [showCount, setShowCount] = useState(PAGE_SIZE);
  const [showDetails, setShowDetails] = useState(false);
  const [atBottom, setAtBottom] = useState(true);

  const scroller = useRef<HTMLDivElement>(null);
  const messages = d?.messages ?? [];
  const visible = messages.slice(-showCount);
  const hasMore = messages.length > showCount;

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "auto") => {
    const el = scroller.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior });
  }, []);

  // Follow the conversation, but never yank the view while reading older messages.
  useEffect(() => {
    if (atBottom) scrollToBottom();
  }, [messages.length, atBottom, scrollToBottom]);

  const refresh = () => {
    void mutate();
    void revalidate("/crm", "/beneficiary/");
  };

  const sendReply = async () => {
    const body = reply.trim();
    if (!body || sending) return;
    setSending(true);
    try {
      const res = await api.post<ReplyResult>(`/crm/tickets/${encodeURIComponent(id)}/reply`, {
        body_ar: body,
        sender: "agent",
        send_to_whatsapp: viaWhatsapp,
      });
      setReply("");
      setAtBottom(true);
      const warning = res.warning_ar ?? "";
      if (!viaWhatsapp) toast.success(t.ticket.noteSaved);
      else if (warning.includes("نافذة")) toast.warning(t.ticket.warnWindowClosed);
      else if (warning.includes("رقم")) toast.warning(t.ticket.warnNoPhone);
      else if (warning) toast.warning(t.ticket.warnSendFailed);
      else toast.success(t.ticket.sent);
      refresh();
    } catch {
      toast.error(t.ticket.replyFailed);
    } finally {
      setSending(false);
    }
  };

  const closeTicket = async () => {
    try {
      await api.patch(`/crm/tickets/${encodeURIComponent(id)}/status`, { status: "closed" });
      toast.success(t.ticket.closed);
      refresh();
    } catch {
      toast.error(t.ticket.closeFailed);
    }
  };

  if (error && !d) {
    return (
      <>
        <SheetHeader>
          <div className="min-w-0">
            <SheetTitle>{id}</SheetTitle>
            <SheetDescription>{t.common.loadError}</SheetDescription>
          </div>
        </SheetHeader>
        <LoadError onRetry={() => mutate()} />
      </>
    );
  }

  if (isLoading || !d) {
    return (
      <>
        <SheetHeader>
          <div className="min-w-0 space-y-2">
            <SheetTitle className="sr-only">{id}</SheetTitle>
            <SheetDescription className="sr-only">{id}</SheetDescription>
            <Skeleton className="h-4 w-56" />
            <Skeleton className="h-3 w-32" />
          </div>
        </SheetHeader>
        <div className="flex-1 space-y-3 p-6">
          <Skeleton className="h-12" />
          <Skeleton className="h-20 w-2/3" />
          <Skeleton className="ms-auto h-16 w-1/2" />
          <Skeleton className="h-20 w-2/3" />
        </div>
      </>
    );
  }

  const sla = fmt.sla(d.sla);
  const customer = personName(d.customer_name_ar);

  return (
    <>
      {/* conversation header: who, and the state of this conversation */}
      <SheetHeader className="items-center gap-3 py-3">
        <NameAvatar name={customer} size={38} />
        <div className="min-w-0 flex-1">
          <SheetTitle className="truncate text-[15px]">
            {d.beneficiary_id ? (
              <button type="button" onClick={() => openBeneficiary(d.beneficiary_id!)} className="cursor-pointer hover:underline">
                <DataText>{customer}</DataText>
              </button>
            ) : (
              <DataText>{customer}</DataText>
            )}
          </SheetTitle>
          <SheetDescription className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="tabular" dir="ltr">
              {d.whatsapp_number || d.phone || "—"}
            </span>
            <span aria-hidden>·</span>
            <span>{label("channel", d.channel)}</span>
            <span aria-hidden>·</span>
            <span className="tabular">{d.id}</span>
          </SheetDescription>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <StatusBadge kind="ticketStatus" code={d.status} arabic={d.status_ar} />
          <Button variant="ghost" size="icon-sm" aria-label={t.ticket.info} aria-expanded={showDetails} onClick={() => setShowDetails((v) => !v)}>
            <Info className="size-4" />
          </Button>
        </div>
      </SheetHeader>

      {/* subject + SLA strip, with the details drawer */}
      <div className="border-b border-line bg-white/70 px-6 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="min-w-0 truncate text-[13px] font-medium text-ink">
            <DataText>{d.subject_ar || t.ticket.conversation}</DataText>
          </p>
          <span className={cn("inline-flex items-center gap-1 text-[11.5px] tabular", sla.breached ? "text-rose-600" : "text-ink-muted")}>
            <Clock className="size-3.5" />
            {sla.text}
          </span>
        </div>
        {showDetails && (
          <dl className="mt-3 grid gap-x-6 gap-y-2 border-t border-line-soft pt-3 text-[12px] sm:grid-cols-3">
            <div>
              <dt className="text-ink-muted">{t.ticket.category}</dt>
              <dd className="text-ink">{label("department", d.department_id, d.department_ar)}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">{t.ticket.openedAt}</dt>
              <dd className="text-ink">{fmt.date(d.opened_at)}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">{t.ticket.slaTitle}</dt>
              <dd className={cn(sla.breached && "text-rose-600")}>{sla.text}</dd>
            </div>
            {d.previous_tickets?.length > 0 && (
              <div className="sm:col-span-3">
                <dt className="mb-1 text-ink-muted">{format(t.ticket.previous, { n: d.previous_tickets.length })}</dt>
                <dd className="flex flex-wrap gap-1.5">
                  {d.previous_tickets.slice(0, 8).map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => openTicket(p)}
                      className="cursor-pointer rounded-md bg-line-soft px-1.5 py-0.5 text-[11px] text-ink-muted tabular transition-colors hover:bg-brand-50 hover:text-brand-700"
                    >
                      {p}
                    </button>
                  ))}
                </dd>
              </div>
            )}
            {canManage && d.status !== "closed" && (
              <div className="sm:col-span-3">
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="danger" size="sm">
                      {t.ticket.closeTicket}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{t.ticket.closeConfirmTitle}</AlertDialogTitle>
                      <AlertDialogDescription>{format(t.ticket.closeConfirmBody, { id: d.id })}</AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>{t.common.cancel}</AlertDialogCancel>
                      <AlertDialogAction variant="danger" onClick={closeTicket}>
                        {t.ticket.closeTicket}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            )}
          </dl>
        )}
      </div>

      {/* the conversation itself */}
      <div className="relative min-h-0 flex-1 bg-[#F5F6F8]">
        <div
          ref={scroller}
          onScroll={(e) => {
            const el = e.currentTarget;
            setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
          }}
          className="h-full space-y-1.5 overflow-y-auto px-4 py-4 sm:px-6"
          aria-live="polite"
        >
          {hasMore && (
            <div className="flex justify-center pb-2">
              <Button variant="outline" size="sm" onClick={() => setShowCount((c) => c + PAGE_SIZE)}>
                {t.ticket.loadEarlier}
              </Button>
            </div>
          )}
          {visible.map((m, i) => {
            const prev = visible[i - 1];
            return (
              <Fragment key={m.id ?? i}>
                {isNewDay(m, prev) && <DaySeparator date={m.sent_at} />}
                <MessageBubble message={m} grouped={isGrouped(m, prev)} />
              </Fragment>
            );
          })}
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-brand-50">
                <MessageCircle className="size-5 text-brand-500" />
              </div>
              <p className="text-[13px] font-medium text-ink">{t.ticket.emptyTitle}</p>
              <p className="mt-0.5 text-[11.5px] text-ink-soft">{t.ticket.emptySub}</p>
            </div>
          )}
        </div>
        {!atBottom && messages.length > 0 && (
          <Button
            size="icon-sm"
            variant="outline"
            aria-label={t.ticket.jumpToLatest}
            onClick={() => {
              setAtBottom(true);
              scrollToBottom("smooth");
            }}
            className="absolute end-4 bottom-4 rounded-full shadow-pop"
          >
            <ChevronDown className="size-4" />
          </Button>
        )}
      </div>

      {/* composer */}
      {canManage ? (
        <div className="border-t border-line bg-white p-3 sm:px-6">
          <label className="mb-2 flex w-fit cursor-pointer items-center gap-2">
            <Switch checked={viaWhatsapp} onCheckedChange={setViaWhatsapp} />
            <span className={cn("text-[11.5px]", viaWhatsapp ? "text-ink-muted" : "font-medium text-amber-700")}>
              {viaWhatsapp ? t.ticket.sendViaWhatsapp : t.ticket.internalNote}
            </span>
          </label>
          <form
            className="flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void sendReply();
            }}
          >
            <Textarea
              dir="auto"
              rows={1}
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void sendReply();
                }
              }}
              placeholder={viaWhatsapp ? t.ticket.replyPlaceholder : t.ticket.notePlaceholder}
              aria-label={viaWhatsapp ? t.ticket.replyPlaceholder : t.ticket.notePlaceholder}
              className={cn(
                "max-h-32 min-h-10 flex-1 resize-none rounded-2xl py-2.5",
                !viaWhatsapp && "border-amber-200 bg-amber-50/40",
              )}
            />
            <Button
              type="submit"
              size="icon"
              className="size-10 shrink-0 rounded-full active:scale-95"
              disabled={sending || !reply.trim()}
              aria-label={t.ticket.send}
            >
              {sending ? <LoaderCircle className="animate-spin" /> : <SendHorizontal className="rtl:-scale-x-100" />}
            </Button>
          </form>
          <p className="mt-1.5 text-[10.5px] text-ink-soft">{t.ticket.composerHint}</p>
        </div>
      ) : (
        <div className="border-t border-line bg-white px-6 py-3 text-center text-[12px] text-ink-soft">{t.ticket.readOnly}</div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ pieces */

function DaySeparator({ date }: { date: string }) {
  const { fmt } = useI18n();
  return (
    <div className="flex justify-center py-2">
      <span className="rounded-full bg-white px-3 py-1 text-[10.5px] font-medium text-ink-muted shadow-card">{fmt.date(date)}</span>
    </div>
  );
}

function isNewDay(m: TicketMessage, prev?: TicketMessage) {
  if (!prev) return true;
  const a = parseApiDate(m.sent_at);
  const b = parseApiDate(prev.sent_at);
  return !a || !b || a.toDateString() !== b.toDateString();
}

/** Consecutive messages from the same side within 5 minutes hang together. */
function isGrouped(m: TicketMessage, prev?: TicketMessage) {
  if (!prev || prev.direction !== m.direction || Boolean(prev.is_internal) !== Boolean(m.is_internal)) return false;
  if (isNewDay(m, prev)) return false;
  const a = parseApiDate(m.sent_at)?.getTime() ?? 0;
  const b = parseApiDate(prev.sent_at)?.getTime() ?? 0;
  return a - b < 5 * 60 * 1000;
}

function DeliveryState({ status }: { status?: string | null }) {
  const { t } = useI18n();
  if (status === "failed") {
    return (
      <span title={t.ticket.notDelivered} className="inline-flex items-center text-rose-200">
        <AlertTriangle className="size-3" />
      </span>
    );
  }
  if (status === "sent") {
    return (
      <span title={t.ticket.delivered} className="inline-flex items-center">
        <CheckCheck className="size-3.5" />
      </span>
    );
  }
  return (
    <span title={t.ticket.sentLabel} className="inline-flex items-center">
      <Check className="size-3.5" />
    </span>
  );
}

function MessageBubble({ message: m, grouped }: { message: TicketMessage; grouped: boolean }) {
  const { t, fmt } = useI18n();
  const inbound = m.direction === "inbound";
  const internal = Boolean(m.is_internal);
  const senderLabel = inbound
    ? t.ticket.senderBeneficiary
    : internal
      ? t.ticket.internalNote
      : m.sender === "bot"
        ? t.ticket.senderBot
        : t.ticket.senderStaff;

  return (
    <div className={cn("flex items-end gap-2", inbound ? "justify-start" : "justify-end", grouped ? "mt-0.5" : "mt-3")}>
      {inbound && (
        <span className={cn("mb-4 flex size-6 shrink-0 items-center justify-center rounded-full bg-line-soft", grouped && "invisible")}>
          <User className="size-3 text-ink-muted" />
        </span>
      )}
      <div className={cn("max-w-[78%] min-w-0", inbound ? "items-start" : "items-end")}>
        {!grouped && (
          <p className={cn("mb-1 text-[10.5px]", inbound ? "ms-1 text-ink-soft" : "me-1 text-end", internal ? "text-amber-600" : "text-ink-soft")}>
            {senderLabel}
          </p>
        )}
        <div
          className={cn(
            "w-fit px-3.5 py-2 shadow-[0_1px_1px_rgba(16,24,40,0.06)]",
            inbound
              ? "rounded-2xl border border-line bg-white text-ink"
              : internal
                ? "rounded-2xl border border-amber-200 bg-amber-50 text-amber-900"
                : "rounded-2xl bg-brand-600 text-white",
            !grouped && (inbound ? "rounded-es-md" : "rounded-ee-md"),
            inbound ? "me-auto" : "ms-auto",
          )}
        >
          <p dir="auto" className="text-[13px] leading-[1.65] break-words whitespace-pre-wrap">
            {formatMessage(m.body_ar)}
          </p>
          <p
            className={cn(
              "mt-1 flex items-center justify-end gap-1 text-[10px] tabular",
              inbound ? "text-ink-soft" : internal ? "text-amber-500" : "text-brand-100",
            )}
          >
            {fmt.time(m.sent_at)}
            {!inbound && !internal && <DeliveryState status={m.status} />}
          </p>
        </div>
      </div>
      {!inbound && (
        <span
          className={cn(
            "mb-4 flex size-6 shrink-0 items-center justify-center rounded-full",
            internal ? "bg-amber-100" : "bg-brand-600",
            grouped && "invisible",
          )}
        >
          {m.sender === "bot" ? (
            <Bot className={cn("size-3", internal ? "text-amber-700" : "text-white")} />
          ) : (
            <User className={cn("size-3", internal ? "text-amber-700" : "text-white")} />
          )}
        </span>
      )}
    </div>
  );
}
