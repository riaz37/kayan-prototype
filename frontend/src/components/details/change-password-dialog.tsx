"use client";

import { useId, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { ApiError, api } from "@/lib/api/client";

/**
 * Change your own password. `forced` is used right after sign-in when the account
 * still has the temporary password an admin set — it cannot be dismissed.
 */
export function ChangePasswordDialog({
  forced = false,
  open,
  onOpenChange,
}: {
  forced?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const { t } = useI18n();
  const { refresh } = useSession();
  const ids = { current: useId(), next: useId(), confirm: useId() };
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (next.length < 8) return setError(t.auth.passwordShort);
    if (next !== confirm) return setError(t.auth.passwordMismatch);
    setError(null);
    setBusy(true);
    try {
      await api.post("/auth/change-password", { current_password: current, new_password: next });
      toast.success(t.auth.passwordChanged);
      setCurrent("");
      setNext("");
      setConfirm("");
      refresh();
      onOpenChange?.(false);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t.auth.wrongCurrent : t.staff.saveFailed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={forced ? true : open} onOpenChange={forced ? undefined : onOpenChange}>
      <DialogContent
        closeLabel={t.common.close}
        showCloseButton={!forced}
        onEscapeKeyDown={forced ? (e) => e.preventDefault() : undefined}
        onInteractOutside={forced ? (e) => e.preventDefault() : undefined}
      >
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>{forced ? t.auth.mustChangeTitle : t.auth.changePassword}</DialogTitle>
            <DialogDescription>{forced ? t.auth.mustChangeBody : t.auth.signInSub}</DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor={ids.current} className="text-[12.5px] text-ink-muted">
                {t.auth.currentPassword}
              </Label>
              <Input id={ids.current} type="password" dir="ltr" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={ids.next} className="text-[12.5px] text-ink-muted">
                {t.auth.newPassword}
              </Label>
              <Input id={ids.next} type="password" dir="ltr" autoComplete="new-password" required minLength={8} value={next} onChange={(e) => setNext(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={ids.confirm} className="text-[12.5px] text-ink-muted">
                {t.auth.confirmPassword}
              </Label>
              <Input id={ids.confirm} type="password" dir="ltr" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </div>
            {error && (
              <p role="alert" className="text-[12px] text-rose-600">
                {error}
              </p>
            )}
          </DialogBody>
          <DialogFooter>
            {!forced && (
              <Button variant="outline" onClick={() => onOpenChange?.(false)} disabled={busy}>
                {t.common.cancel}
              </Button>
            )}
            <Button type="submit" disabled={busy}>
              {busy && <LoaderCircle className="animate-spin" />}
              {t.auth.changePassword}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
