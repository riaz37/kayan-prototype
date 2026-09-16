import { TicketsView } from "@/components/views/tickets-view";
import { pageMetadata } from "@/lib/i18n/metadata";

export const generateMetadata = pageMetadata("tickets");

export default function Page() {
  return <TicketsView />;
}
