"use client";

import { useEffect } from "react";
import { TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/components/providers/i18n-provider";

export default function ErrorBoundary({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const { t } = useI18n();
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <Card role="alert" className="mx-auto mt-10 max-w-md p-10 text-center">
      <div className="mb-4 inline-flex rounded-xl bg-rose-50 p-3 text-rose-600">
        <TriangleAlert className="size-6" />
      </div>
      <h1 className="text-[18px] font-semibold text-ink">{t.error.title}</h1>
      <p className="mt-1.5 text-[13px] text-ink-muted">{t.error.body}</p>
      <Button className="mt-6" onClick={reset}>
        {t.error.retry}
      </Button>
    </Card>
  );
}
