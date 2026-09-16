"use client";

import { useEffect, useId, useRef, useState } from "react";
import { MessageCircle, RotateCcw, SendHorizontal, Sparkles, Trash2 } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { DataText, Field, PageHead, StatusBadge } from "@/components/kayan/primitives";
import { useI18n } from "@/components/providers/i18n-provider";
import { RequirePermission } from "@/components/providers/require-permission";
import { api } from "@/lib/api/client";
import type { AgentChatResponse, AgentContext } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Message = { role: "user" | "agent" | "error"; text: string; time: Date };

const DEFAULT_PHONE = "966500287602";
const AGENT_TIMEOUT_MS = 120_000;

export function AgentTestView() {
  return (
    <RequirePermission permission="agent:test">
      <AgentTestConsole />
    </RequirePermission>
  );
}

function AgentTestConsole() {
  const { t, fmt, label, format } = useI18n();
  const phoneId = useId();
  const [phone, setPhone] = useState(DEFAULT_PHONE);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [context, setContext] = useState<AgentContext | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text, time: new Date() }]);
    setLoading(true);
    try {
      const res = await api.post<AgentChatResponse>(
        "/agent/chat",
        { from_number: phone.trim(), text_ar: text },
        { timeoutMs: AGENT_TIMEOUT_MS },
      );
      setMessages((m) => [...m, { role: "agent", text: res.reply, time: new Date() }]);
      if (res.context) setContext(res.context);
    } catch {
      setMessages((m) => [...m, { role: "error", text: t.agentTest.connectionError, time: new Date() }]);
    } finally {
      setLoading(false);
    }
  };

  const reset = async () => {
    try {
      await api.post(`/agent/session/${encodeURIComponent(phone.trim())}/reset`);
      setMessages([]);
      setContext(null);
      toast.success(t.agentTest.resetDone);
    } catch {
      toast.error(t.agentTest.actionFailed);
    }
  };

  const clearAll = async () => {
    try {
      await api.post("/agent/sessions/clear-all");
      setMessages([]);
      setContext(null);
      toast.success(t.agentTest.cleared);
    } catch {
      toast.error(t.agentTest.actionFailed);
    }
  };

  return (
    <div className="space-y-4">
      <PageHead
        title={t.agentTest.title}
        sub={t.agentTest.sub}
        right={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={reset}>
              <RotateCcw /> {t.agentTest.reset}
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" className="border-rose-200 text-rose-600 hover:bg-rose-50">
                  <Trash2 /> {t.agentTest.clearAll}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t.agentTest.clearAllTitle}</AlertDialogTitle>
                  <AlertDialogDescription>{t.agentTest.clearAllBody}</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{t.common.cancel}</AlertDialogCancel>
                  <AlertDialogAction variant="danger" onClick={() => void clearAll()}>
                    {t.agentTest.clearAll}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        }
      />

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Label htmlFor={phoneId} className="text-[13px] font-medium whitespace-nowrap text-ink">
            {t.agentTest.phoneLabel}
          </Label>
          <Input
            id={phoneId}
            dir="ltr"
            inputMode="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder={DEFAULT_PHONE}
            className="max-w-xs flex-1 tabular"
          />
          <Badge tone={context?.known ? "green" : "slate"} dot>
            {context?.known ? t.agentTest.registered : t.agentTest.newUser}
          </Badge>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="flex h-[520px] flex-col lg:col-span-2">
          <div className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
            {messages.length === 0 && !loading && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <div className="mb-3 rounded-xl bg-line-soft p-3 text-ink-soft">
                  <MessageCircle className="size-5" />
                </div>
                <p className="text-[14px] font-medium text-ink">{t.agentTest.startTitle}</p>
                <p className="mt-1 text-[12.5px] text-ink-muted">{t.agentTest.startSub}</p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "max-w-[80%] rounded-2xl px-4 py-2.5",
                    m.role === "user" && "rounded-ee-md bg-brand-600 text-white",
                    m.role === "agent" && "rounded-es-md border border-line bg-white text-ink shadow-card",
                    m.role === "error" && "rounded-es-md border border-rose-200 bg-rose-50 text-rose-700",
                  )}
                >
                  <p dir="auto" className="text-[13px] leading-relaxed break-words whitespace-pre-wrap">
                    {m.text}
                  </p>
                  <p className={cn("mt-1 text-end text-[10px] tabular", m.role === "user" ? "text-brand-100" : "text-ink-soft")}>
                    {fmt.time(m.time)}
                  </p>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-es-md border border-line bg-white px-4 py-3 shadow-card" role="status">
                  <span className="sr-only">{t.agentTest.typing}</span>
                  <div className="flex gap-1.5" aria-hidden>
                    {[0, 150, 300].map((delay) => (
                      <span key={delay} className="size-2 animate-bounce rounded-full bg-ink-soft" style={{ animationDelay: `${delay}ms` }} />
                    ))}
                  </div>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
          <form
            className="flex gap-2 border-t border-line p-3"
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
          >
            <Input
              dir="auto"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t.agentTest.placeholder}
              aria-label={t.agentTest.placeholder}
              className="flex-1"
              disabled={loading}
            />
            <Button type="submit" size="icon" disabled={loading || !input.trim()} aria-label={t.agentTest.send}>
              <SendHorizontal className="rtl:-scale-x-100" />
            </Button>
          </form>
        </Card>

        <Card className="space-y-4 p-4">
          <h3 className="flex items-center gap-2 text-[14px] font-semibold text-ink">
            <Sparkles className="size-4 text-brand-600" />
            {t.agentTest.contextTitle}
          </h3>
          {!context ? (
            <p className="py-8 text-center text-[12.5px] text-ink-soft">{t.agentTest.contextEmpty}</p>
          ) : (
            <dl className="space-y-3">
              <Field label={t.agentTest.beneficiary} value={<DataText>{context.name_ar || "—"}</DataText>} />
              <Field label={t.agentTest.fileNo} value={context.file_no || "—"} mono />
              <Field
                label={t.agentTest.fileStatus}
                value={context.file_status ? <StatusBadge kind="fileStatus" code={context.file_status} dot={false} /> : "—"}
              />
              <div>
                <dt className="text-[11.5px] text-ink-muted">{t.agentTest.completion}</dt>
                <dd className="mt-1 flex items-center gap-2">
                  <Progress value={context.completion_pct ?? 0} className="flex-1" />
                  <span className="text-[12px] tabular">{context.completion_pct ?? 0}%</span>
                </dd>
              </div>
              {!!context.missing_documents?.length && (
                <div>
                  <dt className="mb-1 text-[11.5px] text-ink-muted">{t.agentTest.missingDocs}</dt>
                  <dd className="flex flex-wrap gap-1">
                    {context.missing_documents.map((doc) => (
                      <Badge key={doc} tone="amber">
                        {label("documentType", null, doc)}
                      </Badge>
                    ))}
                  </dd>
                </div>
              )}
              {!!context.open_requests?.length && (
                <div>
                  <dt className="mb-1 text-[11.5px] text-ink-muted">{t.agentTest.openRequests}</dt>
                  <dd className="flex flex-wrap gap-1">
                    {context.open_requests.map((req) => (
                      <Badge key={req.id} tone="sky">
                        <span className="tabular">{req.id}</span> · {label("stage", req.stage)}
                      </Badge>
                    ))}
                  </dd>
                </div>
              )}
              {!!context.open_tickets?.length && (
                <div>
                  <dt className="mb-1 text-[11.5px] text-ink-muted">{t.agentTest.openTickets}</dt>
                  <dd className="flex flex-wrap gap-1">
                    {context.open_tickets.map((id) => (
                      <Badge key={id} tone="slate" className="tabular">
                        {id}
                      </Badge>
                    ))}
                  </dd>
                </div>
              )}
              {context.next_disbursement && (
                <Field
                  label={t.agentTest.nextDisbursement}
                  value={format("{amount} · {date}", {
                    amount: fmt.money(context.next_disbursement.amount),
                    date: fmt.date(context.next_disbursement.due_date),
                  })}
                />
              )}
            </dl>
          )}
        </Card>
      </div>
    </div>
  );
}
