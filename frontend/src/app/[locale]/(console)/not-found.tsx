"use client";

import Link from "next/link";
import { SearchX } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/components/providers/i18n-provider";

export default function NotFound() {
  const { t, locale } = useI18n();
  return (
    <Card className="mx-auto mt-10 max-w-md p-10 text-center">
      <div className="mb-4 inline-flex rounded-xl bg-line-soft p-3 text-ink-soft">
        <SearchX className="size-6" />
      </div>
      <h1 className="text-[18px] font-semibold text-ink">{t.notFound.title}</h1>
      <p className="mt-1.5 text-[13px] text-ink-muted">{t.notFound.body}</p>
      <Link href={`/${locale}`} className={buttonVariants({ className: "mt-6" })}>
        {t.notFound.home}
      </Link>
    </Card>
  );
}
