"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import useSWR from "swr";
import type { Permission, SessionUser } from "@/lib/api/types";

type SessionValue = {
  user: SessionUser | null;
  loading: boolean;
  /** True when the signed-in user holds every listed permission. */
  can: (...permissions: Permission[]) => boolean;
  refresh: () => void;
};

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children, initialUser }: { children: ReactNode; initialUser?: SessionUser | null }) {
  const { data, isLoading, mutate } = useSWR<{ user: SessionUser }>("/auth/me", {
    fallbackData: initialUser ? { user: initialUser } : undefined,
    shouldRetryOnError: false,
    revalidateOnFocus: true,
  });

  const value = useMemo<SessionValue>(() => {
    const user = data?.user ?? null;
    const held = new Set(user?.permissions ?? []);
    return {
      user,
      loading: isLoading && !data,
      can: (...permissions) => held.has("admin:all") || permissions.every((p) => held.has(p)),
      refresh: () => void mutate(),
    };
  }, [data, isLoading, mutate]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
