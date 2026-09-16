import { Suspense } from "react";
import { LoginView } from "@/components/views/login-view";
import { pageMetadata } from "@/lib/i18n/metadata";

export const generateMetadata = pageMetadata("signIn");

export default function Page() {
  // LoginView reads `?next=` to return the visitor to the page they asked for.
  return (
    <Suspense>
      <LoginView />
    </Suspense>
  );
}
