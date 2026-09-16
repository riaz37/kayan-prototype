import { Suspense } from "react";
import { BeneficiariesView } from "@/components/views/beneficiaries-view";
import { pageMetadata } from "@/lib/i18n/metadata";

export const generateMetadata = pageMetadata("beneficiaries");

export default function Page() {
  // The view reads `?q=` from the URL (topbar search), which needs a Suspense boundary.
  return (
    <Suspense>
      <BeneficiariesView />
    </Suspense>
  );
}
