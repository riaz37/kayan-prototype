import { StaffView } from "@/components/views/staff-view";
import { pageMetadata } from "@/lib/i18n/metadata";

export const generateMetadata = pageMetadata("staff");

export default function Page() {
  return <StaffView />;
}
