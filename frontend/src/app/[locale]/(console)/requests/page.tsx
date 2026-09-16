import { Suspense } from "react";
import { RequestsView } from "@/components/views/requests-view";
import { pageMetadata } from "@/lib/i18n/metadata";

export const generateMetadata = pageMetadata("requests");

export default function Page() {
  // The view reads `?q=` from the URL (topbar search), which needs a Suspense boundary.
  return (
    <Suspense>
      <RequestsView />
    </Suspense>
  );
}
