import { KanbanView } from "@/components/views/kanban-view";
import { pageMetadata } from "@/lib/i18n/metadata";

export const generateMetadata = pageMetadata("kanban");

export default function Page() {
  return <KanbanView />;
}
