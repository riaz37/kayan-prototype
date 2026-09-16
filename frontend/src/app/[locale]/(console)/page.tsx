import { DashboardView } from "@/components/views/dashboard-view";
import { pageMetadata } from "@/lib/i18n/metadata";

export const generateMetadata = pageMetadata("dashboard");

export default function Page() {
  return <DashboardView />;
}
