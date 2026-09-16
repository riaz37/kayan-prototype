import { ProgramsView } from "@/components/views/programs-view";
import { pageMetadata } from "@/lib/i18n/metadata";

export const generateMetadata = pageMetadata("programs");

export default function Page() {
  return <ProgramsView />;
}
