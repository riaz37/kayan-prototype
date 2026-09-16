import { FinanceView } from "@/components/views/finance-view";
import { pageMetadata } from "@/lib/i18n/metadata";

export const generateMetadata = pageMetadata("finance");

export default function Page() {
  return <FinanceView />;
}
