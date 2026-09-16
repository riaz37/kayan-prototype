"use client";

import type { ReactNode } from "react";
import { Lock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import type { Permission } from "@/lib/api/types";

/** Page-level guard: renders the page only if the user holds the permission. */
export function RequirePermission({ permission, children }: { permission: Permission; children: ReactNode }) {
  const { t } = useI18n();
  const { can } = useSession();
  if (can(permission)) return <>{children}</>;
  return (
    <Card className="mx-auto mt-10 max-w-md p-10 text-center">
      <div className="mb-4 inline-flex rounded-xl bg-line-soft p-3 text-ink-soft">
        <Lock className="size-6" />
      </div>
      <h1 className="text-[16px] font-semibold text-ink">{t.auth.noAccess}</h1>
      <p className="mt-1.5 text-[13px] text-ink-muted">{t.auth.noAccessBody}</p>
    </Card>
  );
}
