import { CommitteeView } from "@/components/views/committee-view";
import { pageMetadata } from "@/lib/i18n/metadata";

export const generateMetadata = pageMetadata("committee");

export default function Page() {
  return <CommitteeView />;
}
