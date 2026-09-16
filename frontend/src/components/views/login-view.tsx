"use client";

import { useEffect, useId, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Languages, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { ApiError, api } from "@/lib/api/client";
import { LOCALE_COOKIE, swapLocaleInPath, type Locale } from "@/lib/i18n/config";

export function LoginView() {
  const { t, locale } = useI18n();
  const { user, refresh } = useSession();
  const router = useRouter();
  const params = useSearchParams();
  const ids = { email: useId(), password: useId() };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const other: Locale = locale === "ar" ? "en" : "ar";

  const next = params.get("next");
  const destination = next && next.startsWith(`/${locale}`) ? next : `/${locale}`;

  // Already signed in (or just signed in): leave the login page.
  useEffect(() => {
    if (user) router.replace(destination);
  }, [user, destination, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/login", { email: email.trim(), password });
      refresh();
      router.replace(destination);
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      setError(status === 401 ? t.auth.invalid : status === 403 ? t.auth.deactivated : t.auth.failed);
      setBusy(false);
    }
  };

  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="relative mb-3 grid size-12 place-items-center rounded-2xl bg-brand-600 shadow-sm">
            <span className="text-[19px] leading-none font-bold text-white">{t.brand.mark}</span>
            <span className="absolute -end-1 -bottom-1 size-3 rounded-[5px] bg-brand-300 ring-2 ring-canvas" />
          </div>
          <h1 className="text-[20px] font-semibold text-ink">{t.auth.signInTitle}</h1>
          <p className="mt-1 text-[12.5px] text-ink-muted">{t.auth.signInSub}</p>
        </div>

        <Card className="p-6">
          <form className="space-y-4" onSubmit={submit}>
            <div className="space-y-1.5">
              <Label htmlFor={ids.email} className="text-[12.5px] text-ink-muted">
                {t.auth.email}
              </Label>
              <Input
                id={ids.email}
                type="email"
                dir="ltr"
                autoComplete="username"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-invalid={!!error}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={ids.password} className="text-[12.5px] text-ink-muted">
                {t.auth.password}
              </Label>
              <Input
                id={ids.password}
                type="password"
                dir="ltr"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={!!error}
              />
            </div>
            {error && (
              <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-[12.5px] text-rose-700">
                {error}
              </p>
            )}
            <Button type="submit" size="lg" className="w-full" disabled={busy || !email || !password}>
              {busy && <LoaderCircle className="animate-spin" />}
              {busy ? t.auth.signingIn : t.auth.signIn}
            </Button>
          </form>
        </Card>

        <div className="mt-4 text-center">
          <Button
            variant="ghost"
            size="sm"
            lang={other}
            onClick={() => {
              document.cookie = `${LOCALE_COOKIE}=${other}; path=/; max-age=31536000; samesite=lax`;
              router.push(swapLocaleInPath(window.location.pathname, other) + window.location.search);
            }}
          >
            <Languages className="size-4" />
            {t.topbar.switchLanguage}
          </Button>
        </div>
      </div>
    </main>
  );
}
