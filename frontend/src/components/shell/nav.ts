import {
  Bot,
  ShieldCheck,
  FileText,
  Gift,
  House,
  Scale,
  SquareKanban,
  Ticket,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import type { Dictionary } from "@/lib/i18n/dictionaries";
import type { Permission } from "@/lib/api/types";

/** Every console page has a nav entry; the sign-in page is not one of them. */
export type NavKey = Exclude<keyof Dictionary["meta"]["pages"], "signIn">;
export type NavItem = { key: NavKey; href: string; icon: LucideIcon; permission?: Permission };
export type NavGroup = { key: keyof Dictionary["nav"]["groups"]; items: NavItem[] };

/** Paths are relative to the locale prefix. */
export const NAV: NavGroup[] = [
  {
    key: "home",
    items: [
      { key: "dashboard", href: "", icon: House },
      { key: "kanban", href: "/kanban", icon: SquareKanban, permission: "tickets:view" },
      { key: "tickets", href: "/tickets", icon: Ticket, permission: "tickets:view" },
    ],
  },
  {
    key: "beneficiaries",
    items: [
      { key: "beneficiaries", href: "/beneficiaries", icon: Users, permission: "beneficiaries:view" },
      { key: "requests", href: "/requests", icon: FileText, permission: "requests:view" },
      { key: "committee", href: "/committee", icon: Scale, permission: "requests:view" },
    ],
  },
  {
    key: "operations",
    items: [
      { key: "finance", href: "/finance", icon: Wallet, permission: "finance:view" },
      { key: "programs", href: "/programs", icon: Gift },
    ],
  },
  {
    key: "agent",
    items: [{ key: "agentTest", href: "/agent-test", icon: Bot, permission: "agent:test" }],
  },
  {
    key: "system",
    items: [{ key: "staff", href: "/staff", icon: ShieldCheck, permission: "staff:manage" }],
  },
];
