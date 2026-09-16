import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { AuthGate } from "@/components/providers/auth-gate";

/** Everything in this group requires a signed-in staff account. */
export default function ConsoleLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <AppShell>{children}</AppShell>
    </AuthGate>
  );
}
