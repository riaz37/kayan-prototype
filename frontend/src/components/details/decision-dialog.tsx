"use client";

import { useId, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { DataText } from "@/components/kayan/primitives";
import { useI18n } from "@/components/providers/i18n-provider";
import { ApiError, api } from "@/lib/api/client";
import { useRevalidate } from "@/lib/api/hooks";

export type DecisionType = "accepted" | "declined" | "docs_required";
export type DecisionTarget = {
  requestId: string;
  name: string | null;
  requestedAmount: number | null;
  type: DecisionType;
};

const DEFAULT_AMOUNT = "15000";

/**
 * Decision texts are delivered to the beneficiary (WhatsApp + SMS) and stored in
 * `*_ar` fields, so the defaults are Arabic whatever the console language is.
 */
const AR_DEFAULTS = {
  accepted: "اعتماد الطلب من اللجنة المختصة",
  docs: "تعريف الراتب، عقد الإيجار",
  declined: "لا يوجد احتياج مؤكد حسب التقييم",
  docsReason: "يلزم استكمال المستندات المطلوبة",
};

/** Record a committee decision on a support request. */
export function DecisionDialog({ target, onClose }: { target: DecisionTarget | null; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <Dialog open={!!target} onOpenChange={(open) => !open && onClose()}>
      <DialogContent closeLabel={t.common.close}>
        {target && <DecisionForm key={`${target.requestId}-${target.type}`} target={target} onDone={onClose} />}
      </DialogContent>
    </Dialog>
  );
}

function DecisionForm({ target, onDone }: { target: DecisionTarget; onDone: () => void }) {
  const { t, fmt, format } = useI18n();
  const revalidate = useRevalidate();
  const fieldId = useId();
  const [amount, setAmount] = useState(target.requestedAmount ? String(target.requestedAmount) : DEFAULT_AMOUNT);
  const [docs, setDocs] = useState(AR_DEFAULTS.docs);
  const [reason, setReason] = useState(AR_DEFAULTS.declined);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const title =
    target.type === "accepted" ? t.decision.acceptTitle : target.type === "declined" ? t.decision.declineTitle : t.decision.docsTitle;

  const submit = async () => {
    const body: Record<string, unknown> = { decision: target.type };
    if (target.type === "accepted") {
      const value = Number(amount);
      if (!Number.isFinite(value) || value <= 0) return setError(t.decision.invalidAmount);
      body.approved_amount_sar = value;
      body.reason_ar = AR_DEFAULTS.accepted;
    } else if (target.type === "docs_required") {
      const list = docs.split(/[,،]/).map((s) => s.trim()).filter(Boolean);
      if (!list.length) return setError(t.decision.docsRequired);
      body.required_documents_ar = list;
      body.reason_ar = AR_DEFAULTS.docsReason;
    } else {
      if (!reason.trim()) return setError(t.decision.reasonRequired);
      body.reason_ar = reason.trim();
    }
    setError(null);
    setSubmitting(true);
    try {
      await api.post(`/support-requests/${encodeURIComponent(target.requestId)}/decision`, body);
      toast.success(t.decision.recorded);
      void revalidate("/support-requests", "/committee", "/reports", "/beneficiary/", "/finance");
      onDone();
    } catch (e) {
      const detail = e instanceof ApiError ? (e.detail ?? "") : "";
      const ceiling = /ceiling \((\d+(?:\.\d+)?)/i.exec(detail);
      if (ceiling) setError(format(t.decision.exceedsCeiling, { ceiling: fmt.money(Number(ceiling[1])) }));
      else if (/already exists/i.test(detail)) setError(t.decision.alreadyDecided);
      else toast.error(t.decision.failed);
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>
          <span className="tabular">{target.requestId}</span> — <DataText>{target.name ?? "—"}</DataText>
        </DialogDescription>
      </DialogHeader>
      <DialogBody className="space-y-3">
        {target.type === "accepted" && (
          <>
            <Label htmlFor={fieldId} className="text-[13px] font-normal text-ink-muted">
              {t.decision.amountLabel}
            </Label>
            <Input
              id={fieldId}
              type="number"
              inputMode="decimal"
              min={1}
              dir="ltr"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              aria-invalid={!!error}
              autoFocus
            />
            <div className="flex items-center justify-between text-[12px] text-ink-muted">
              <span>{t.decision.requestedAmount}</span>
              <span className="font-medium tabular">{fmt.money(target.requestedAmount)}</span>
            </div>
          </>
        )}
        {target.type === "docs_required" && (
          <>
            <Label htmlFor={fieldId} className="text-[13px] font-normal text-ink-muted">
              {t.decision.docsLabel}
            </Label>
            <Textarea id={fieldId} dir="auto" rows={3} value={docs} onChange={(e) => setDocs(e.target.value)} aria-invalid={!!error} autoFocus />
          </>
        )}
        {target.type === "declined" && (
          <>
            <Label htmlFor={fieldId} className="text-[13px] font-normal text-ink-muted">
              {t.decision.reasonLabel}
            </Label>
            <Textarea id={fieldId} dir="auto" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} aria-invalid={!!error} autoFocus />
          </>
        )}
        {target.type !== "accepted" && <p className="text-[11.5px] text-ink-soft">{t.decision.beneficiaryHint}</p>}
        {error && (
          <p role="alert" className="text-[12px] text-rose-600">
            {error}
          </p>
        )}
      </DialogBody>
      <DialogFooter>
        <Button variant="outline" onClick={onDone} disabled={submitting}>
          {t.common.cancel}
        </Button>
        <Button type="submit" variant={target.type === "declined" ? "danger" : "default"} disabled={submitting}>
          {submitting && <LoaderCircle className="animate-spin" />}
          {submitting ? t.common.submitting : t.common.confirm}
        </Button>
      </DialogFooter>
    </form>
  );
}
