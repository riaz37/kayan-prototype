"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { LoaderCircle } from "lucide-react";
import { ChangePasswordDialog } from "@/components/details/change-password-dialog";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";

/**
 * Guards the console: anonymous visitors are sent to the sign-in page (with a
 * `next` parameter so they land where they intended), and a user created with a
 * temporary password must change it before continuing.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const { user, loading } = useSession();
  const { locale } = useI18n();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      const next = typeof window === "undefined" ? pathname : pathname + window.location.search;
      router.replace(`/${locale}/login?next=${encodeURIComponent(next)}`);
    }
  }, [loading, user, locale, pathname, router]);

  if (loading || !user) {
    return (
      <div className="grid min-h-screen place-items-center" role="status" aria-busy="true">
        <LoaderCircle className="size-6 animate-spin text-brand-600" />
      </div>
    );
  }

  return (
    <>
      {children}
      {user.must_change_password && <ChangePasswordDialog forced />}
    </>
  );
}
