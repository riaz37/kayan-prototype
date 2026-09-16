import type { KanbanCard, Ticket } from "@/lib/api/types";

/**
 * A ticket is "expired" when its response deadline (SLA) has passed.
 * Kanban cards only carry the backend's Arabic countdown string, so it is parsed here.
 */
export function isCardExpired(card: Pick<KanbanCard, "sla_remaining_ar">): boolean {
  return (card.sla_remaining_ar ?? "").includes("منتهية");
}

export function isTicketExpired(ticket: Pick<Ticket, "sla" | "status">): boolean {
  return ticket.status === "expired" || Boolean(ticket.sla?.breached);
}
