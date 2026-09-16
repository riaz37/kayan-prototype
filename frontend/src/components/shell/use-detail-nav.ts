"use client";

import { useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";

export const TICKET_PARAM = "ticket";
export const BENEFICIARY_PARAM = "ben";
export const REQUEST_PARAM = "request";

/**
 * Detail panels (ticket, beneficiary) are addressed by search params, so they
 * survive refresh, can be shared as links, and close with the back button.
 * Reads the current query at call time to avoid a Suspense requirement.
 */
export function useDetailNav() {
  const router = useRouter();
  const pathname = usePathname();

  const go = useCallback(
    (set: Record<string, string | null>, mode: "push" | "replace" = "push") => {
      const params = new URLSearchParams(typeof window === "undefined" ? "" : window.location.search);
      for (const [key, value] of Object.entries(set)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      const qs = params.toString();
      router[mode](qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [pathname, router],
  );

  return {
    openTicket: useCallback((id: string) => go({ [TICKET_PARAM]: id, [BENEFICIARY_PARAM]: null, [REQUEST_PARAM]: null }), [go]),
    openBeneficiary: useCallback(
      (id: string) => go({ [BENEFICIARY_PARAM]: id, [TICKET_PARAM]: null, [REQUEST_PARAM]: null }),
      [go],
    ),
    openRequest: useCallback((id: string) => go({ [REQUEST_PARAM]: id, [TICKET_PARAM]: null, [BENEFICIARY_PARAM]: null }), [go]),
    closeDetails: useCallback(
      () => go({ [TICKET_PARAM]: null, [BENEFICIARY_PARAM]: null, [REQUEST_PARAM]: null }, "replace"),
      [go],
    ),
  };
}
