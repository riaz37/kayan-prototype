"use client";

import { useId, useMemo, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/components/providers/i18n-provider";
import { ApiError, api } from "@/lib/api/client";
import { useApi, useRevalidate } from "@/lib/api/hooks";
import type { BeneficiaryHistory } from "@/lib/api/types";
import { FILE_SECTIONS, changedValues, type FormField, type SectionValues } from "@/lib/beneficiary-form";
import { cn } from "@/lib/utils";

const UNSET = "__unset__";

type ReferenceOption = { id: string; name_ar: string; eligible?: boolean };

/** Options that come from the API rather than a fixed list. */
function useReferenceOptions() {
  const categories = useApi<{ categories?: ReferenceOption[]; orphan_categories?: ReferenceOption[] }>(
    "/reference/orphan-categories",
    { revalidateOnFocus: false },
  );
  const proofs = useApi<{ housing_proofs?: ReferenceOption[]; proofs?: ReferenceOption[] }>("/reference/housing-proofs", {
    revalidateOnFocus: false,
  });
  const list = (data: Record<string, unknown> | undefined) =>
    (Object.values(data ?? {}).find(Array.isArray) as ReferenceOption[] | undefined) ?? [];
  return {
    orphanCategory: list(categories.data).filter((c) => c.eligible !== false),
    housingProof: list(proofs.data),
  };
}

function FieldInput({
  field,
  value,
  onChange,
  references,
}: {
  field: FormField;
  value: unknown;
  onChange: (value: unknown) => void;
  references: ReturnType<typeof useReferenceOptions>;
}) {
  const { t, label } = useI18n();
  const id = useId();
  const text = t.fields[field.key];

  const control = () => {
    switch (field.type) {
      case "boolean":
        return (
          <div className="flex h-9 items-center">
            <Switch id={id} checked={value === true} onCheckedChange={(v) => onChange(v)} />
          </div>
        );
      case "select":
      case "reference": {
        const options =
          field.type === "select"
            ? field.options.map((o) => ({ id: o, name_ar: "" }))
            : references[field.source];
        return (
          <Select value={(value as string) || UNSET} onValueChange={(v) => onChange(v === UNSET ? null : v)}>
            <SelectTrigger id={id} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent position="popper">
              <SelectItem value={UNSET}>{t.file.notSet}</SelectItem>
              {options.map((o) => (
                <SelectItem key={o.id} value={o.id}>
                  {label(field.catalog, o.id, o.name_ar || undefined)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      }
      case "number":
        return (
          <Input
            id={id}
            type="number"
            dir="ltr"
            inputMode="decimal"
            value={value === null || value === undefined ? "" : String(value)}
            onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
          />
        );
      default:
        return (
          <Input
            id={id}
            type={field.type === "text" ? "text" : field.type}
            dir={field.type === "text" ? "auto" : "ltr"}
            required={"required" in field && field.required}
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value)}
          />
        );
    }
  };

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-[12px] font-normal text-ink-muted">
        {text}
        {"required" in field && field.required && <span className="text-rose-500"> *</span>}
      </Label>
      {control()}
    </div>
  );
}

/* ------------------------------------------------------------------ create */

export function CreateFileDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (beneficiaryId: string) => void;
}) {
  const { t, format, label } = useI18n();
  const references = useReferenceOptions();
  const revalidate = useRevalidate();
  const ids = { name: useId(), id: useId(), phone: useId(), city: useId(), type: useId(), cat: useId() };
  const [form, setForm] = useState({
    full_name_ar: "",
    national_id: "",
    phone: "",
    city: "",
    case_type: "CT-IND",
    orphan_category_id: "OC-UNK",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ beneficiary_id: string; file_no: string }>("/beneficiary/create-file", {
        full_name_ar: form.full_name_ar.trim(),
        national_id: form.national_id.trim() || null,
        phone: form.phone.trim(),
        city: form.city.trim() || null,
        case_type: form.case_type,
        orphan_category_id: form.orphan_category_id,
      });
      toast.success(format(t.file.created, { fileNo: res.file_no }));
      void revalidate("/beneficiaries", "/reports");
      onOpenChange(false);
      onCreated(res.beneficiary_id);
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      const detail = err instanceof ApiError ? (err.detail ?? "") : "";
      setError(status === 409 ? (detail.includes("Category") ? t.file.ineligible : t.file.phoneExists) : t.file.saveFailed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" closeLabel={t.common.close}>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>{t.file.createTitle}</DialogTitle>
            <DialogDescription>{t.file.createHint}</DialogDescription>
          </DialogHeader>
          <DialogBody className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor={ids.name} className="text-[12px] font-normal text-ink-muted">
                {t.fields.full_name_ar} <span className="text-rose-500">*</span>
              </Label>
              <Input id={ids.name} dir="auto" required minLength={2} value={form.full_name_ar} onChange={(e) => setForm({ ...form, full_name_ar: e.target.value })} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor={ids.phone} className="text-[12px] font-normal text-ink-muted">
                  {t.fields.mobile} <span className="text-rose-500">*</span>
                </Label>
                <Input id={ids.phone} type="tel" dir="ltr" required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={ids.id} className="text-[12px] font-normal text-ink-muted">
                  {t.fields.national_id}
                </Label>
                <Input id={ids.id} dir="ltr" value={form.national_id} onChange={(e) => setForm({ ...form, national_id: e.target.value })} />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor={ids.type} className="text-[12px] font-normal text-ink-muted">
                  {t.fields.case_type}
                </Label>
                <Select value={form.case_type} onValueChange={(v) => setForm({ ...form, case_type: v })}>
                  <SelectTrigger id={ids.type} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent position="popper">
                    <SelectItem value="CT-IND">{label("caseType", "CT-IND")}</SelectItem>
                    <SelectItem value="CT-FOSTER">{label("caseType", "CT-FOSTER")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={ids.cat} className="text-[12px] font-normal text-ink-muted">
                  {t.fields.orphan_category_id}
                </Label>
                <Select value={form.orphan_category_id} onValueChange={(v) => setForm({ ...form, orphan_category_id: v })}>
                  <SelectTrigger id={ids.cat} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent position="popper">
                    {references.orphanCategory.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {label("orphanCategory", c.id, c.name_ar)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={ids.city} className="text-[12px] font-normal text-ink-muted">
                {t.fields.city}
              </Label>
              <Input id={ids.city} dir="auto" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
            </div>
            {error && (
              <p role="alert" className="text-[12px] text-rose-600">
                {error}
              </p>
            )}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
              {t.common.cancel}
            </Button>
            <Button type="submit" disabled={busy || !form.full_name_ar.trim() || !form.phone.trim()}>
              {busy && <LoaderCircle className="animate-spin" />}
              {t.file.create}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ edit */

export function EditFileDialog({
  beneficiary,
  open,
  onOpenChange,
  onSaved,
}: {
  beneficiary: BeneficiaryHistory["beneficiary"] & { sections?: Record<string, SectionValues> };
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const { t, label } = useI18n();
  const references = useReferenceOptions();
  const revalidate = useRevalidate();
  // The history endpoint omits the raw sections, so load the file itself.
  const file = useApi<{ sections: Record<string, SectionValues> }>(open ? `/beneficiary/${encodeURIComponent(beneficiary.id)}` : null);
  const original = useMemo(() => file.data?.sections ?? {}, [file.data]);
  const [draft, setDraft] = useState<Record<string, SectionValues>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const valueOf = (sectionId: string, key: string) =>
    draft[sectionId]?.[key] !== undefined ? draft[sectionId][key] : (original[sectionId]?.[key] ?? null);

  const setValue = (sectionId: string, key: string, value: unknown) =>
    setDraft((d) => ({ ...d, [sectionId]: { ...(d[sectionId] ?? {}), [key]: value } }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const patches = FILE_SECTIONS.map((section) => ({
        id: section.id,
        values: changedValues(original[section.id] ?? {}, draft[section.id] ?? {}),
      })).filter((p) => Object.keys(p.values).length > 0);

      if (!patches.length) {
        toast.info(t.file.noChanges);
        onOpenChange(false);
        return;
      }
      for (const patch of patches) {
        await api.patch(`/beneficiary/${encodeURIComponent(beneficiary.id)}/section/${patch.id}`, { values: patch.values });
      }
      toast.success(t.file.updated);
      void revalidate("/beneficiary/", "/beneficiaries", "/reports");
      onSaved();
      onOpenChange(false);
      setDraft({});
    } catch {
      setError(t.file.saveFailed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl" closeLabel={t.common.close}>
        <form onSubmit={save}>
          <DialogHeader>
            <DialogTitle>{t.file.editTitle}</DialogTitle>
            <DialogDescription>
              <span className="tabular">{beneficiary.file_no}</span> · {beneficiary.name_ar}
            </DialogDescription>
          </DialogHeader>
          <DialogBody className="max-h-[60vh] overflow-y-auto">
            <Tabs defaultValue={FILE_SECTIONS[0].id}>
              <TabsList className="flex-wrap">
                {FILE_SECTIONS.map((section) => (
                  <TabsTrigger key={section.id} value={section.id}>
                    {label("formSection", section.id)}
                  </TabsTrigger>
                ))}
              </TabsList>
              {FILE_SECTIONS.map((section) => (
                <TabsContent key={section.id} value={section.id}>
                  <div className={cn("grid gap-3", section.fields.length > 3 && "sm:grid-cols-2")}>
                    {section.fields.map((field) => (
                      <FieldInput
                        key={field.key}
                        field={field}
                        value={valueOf(section.id, field.key)}
                        onChange={(v) => setValue(section.id, field.key, v)}
                        references={references}
                      />
                    ))}
                  </div>
                </TabsContent>
              ))}
            </Tabs>
            {error && (
              <p role="alert" className="mt-3 text-[12px] text-rose-600">
                {error}
              </p>
            )}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
              {t.common.cancel}
            </Button>
            <Button type="submit" disabled={busy || file.isLoading}>
              {busy && <LoaderCircle className="animate-spin" />}
              {t.file.save}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
