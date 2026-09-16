import type { CatalogKind } from "@/lib/i18n/catalog";
import type { Dictionary } from "@/lib/i18n/dictionaries";

export type FieldKey = keyof Dictionary["fields"];

export type FormField =
  | { key: FieldKey; type: "text" | "number" | "date" | "tel" | "email"; required?: boolean }
  | { key: FieldKey; type: "boolean" }
  | { key: FieldKey; type: "select"; options: string[]; catalog: CatalogKind }
  /** Options come from the API (orphan categories, housing proofs…). */
  | { key: FieldKey; type: "reference"; source: "orphanCategory" | "housingProof"; catalog: CatalogKind };

export type FormSection = { id: string; fields: FormField[] };

/**
 * The editable parts of the 10-section beneficiary file, mirroring
 * `reference-data/form_sections.json`. Dependents, documents and income sources
 * are managed on their own screens, so they are not repeated here.
 */
export const FILE_SECTIONS: FormSection[] = [
  {
    id: "SEC-BASIC",
    fields: [
      { key: "full_name_ar", type: "text", required: true },
      { key: "national_id", type: "text" },
      { key: "birth_date", type: "date" },
      { key: "gender", type: "select", options: ["M", "F"], catalog: "gender" },
      { key: "marital_status", type: "select", options: ["single", "married", "divorced", "widowed"], catalog: "maritalStatus" },
      { key: "orphan_category_id", type: "reference", source: "orphanCategory", catalog: "orphanCategory" },
      { key: "nationality", type: "text" },
    ],
  },
  {
    id: "SEC-CONTACT",
    fields: [
      { key: "mobile", type: "tel", required: true },
      { key: "whatsapp", type: "tel" },
      { key: "alt_mobile", type: "tel" },
      { key: "email", type: "email" },
    ],
  },
  {
    id: "SEC-HOUSING",
    fields: [
      { key: "city", type: "text" },
      { key: "district", type: "text" },
      { key: "housing_type", type: "select", options: ["owned", "rented", "family", "government"], catalog: "housingType" },
      { key: "ownership_proof_type", type: "reference", source: "housingProof", catalog: "housingProof" },
      { key: "rooms", type: "number" },
      { key: "monthly_rent", type: "number" },
      { key: "monthly_bills", type: "number" },
    ],
  },
  {
    id: "SEC-EDU",
    fields: [
      { key: "education_level", type: "select", options: ["primary", "intermediate", "secondary", "university"], catalog: "education" },
      { key: "employment_status", type: "select", options: ["employed", "self_employed", "unemployed", "retired", "student"], catalog: "employmentStatus" },
      { key: "employer", type: "text" },
      { key: "monthly_salary", type: "number" },
    ],
  },
  {
    id: "SEC-BANK",
    fields: [
      { key: "bank_name", type: "text" },
      { key: "iban", type: "text" },
      { key: "account_holder_name", type: "text" },
    ],
  },
  {
    id: "SEC-EXTRA",
    fields: [
      { key: "dependents_count", type: "number" },
      { key: "has_social_security", type: "boolean" },
      { key: "has_citizen_account", type: "boolean" },
    ],
  },
  {
    id: "SEC-HEALTH",
    fields: [
      { key: "chronic_conditions", type: "text" },
      { key: "disability", type: "text" },
      { key: "has_health_insurance", type: "boolean" },
      { key: "monthly_medication_cost", type: "number" },
    ],
  },
  {
    id: "SEC-JOIN",
    fields: [
      { key: "join_reason", type: "text" },
      { key: "referral_source", type: "select", options: ["self", "social_media", "charity", "government", "other"], catalog: "referralSource" },
      { key: "previous_support", type: "text" },
    ],
  },
];

export type SectionValues = Record<string, unknown>;

/** Only the fields that actually changed, so each section is patched minimally. */
export function changedValues(before: SectionValues, after: SectionValues): SectionValues {
  const out: SectionValues = {};
  for (const [key, value] of Object.entries(after)) {
    const original = before[key] ?? null;
    const next = value === "" ? null : value;
    if (JSON.stringify(original ?? null) !== JSON.stringify(next ?? null)) out[key] = next;
  }
  return out;
}
