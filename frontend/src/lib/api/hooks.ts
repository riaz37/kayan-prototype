"use client";

import useSWR, { useSWRConfig, type SWRConfiguration } from "swr";
import { useCallback, useMemo } from "react";
import { parseApiDate } from "@/lib/i18n/format";
import type {
  BeneficiaryHistory,
  BeneficiaryRow,
  CommitteeItem,
  CrmStats,
  Department,
  DisbursementRun,
  Kanban,
  Notification,
  Overview,
  Program,
  RequestType,
  CaseStepRef,
  Staff,
  SupportRequest,
  SupportRequestDetail,
  Ticket,
  TicketDetail,
} from "./types";

export function useApi<T>(path: string | null, config?: SWRConfiguration<T>) {
  return useSWR<T>(path, config);
}

/** Live CRM views poll so tickets created by the WhatsApp agent appear without a reload. */
const LIVE = { refreshInterval: 15_000 };

const newestFirst = (a?: string | null, b?: string | null) =>
  (parseApiDate(b)?.getTime() ?? 0) - (parseApiDate(a)?.getTime() ?? 0);

export const useStats = () => useApi<CrmStats>("/crm/stats", LIVE);
export const useOverview = () => useApi<Overview>("/reports/overview");
export function useKanban(departmentId?: string) {
  const swr = useApi<Kanban>(
    `/crm/kanban${departmentId ? `?department_id=${encodeURIComponent(departmentId)}` : ""}`,
    LIVE,
  );
  // The API returns cards oldest-first; show the newest activity at the top of each column.
  const data = useMemo<Kanban | undefined>(
    () =>
      swr.data && {
        columns: swr.data.columns.map((c) => ({
          ...c,
          cards: [...c.cards].sort((x, y) => newestFirst(x.last_update, y.last_update)),
        })),
      },
    [swr.data],
  );
  return { data, error: swr.error, isLoading: swr.isLoading, isValidating: swr.isValidating, mutate: swr.mutate };
}
export const useDepartments = () => useApi<{ departments: Department[] }>("/crm/departments");
export const useTickets = () => useApi<{ count: number; tickets: Ticket[] }>("/crm/tickets?limit=100", LIVE);
export const useTicket = (id: string | null) => useApi<TicketDetail>(id ? `/crm/tickets/${encodeURIComponent(id)}` : null);
export const useBeneficiaries = () =>
  useApi<{ count: number; results: BeneficiaryRow[] }>("/beneficiaries/search?q=&limit=500");
export const useBeneficiaryHistory = (id: string | null) =>
  useApi<BeneficiaryHistory>(id ? `/beneficiary/${encodeURIComponent(id)}/history` : null);
export const useSupportRequests = () => useApi<{ count: number; requests: SupportRequest[] }>("/support-requests");
export const useSupportRequest = (id: string | null) =>
  useApi<SupportRequestDetail>(id ? `/support-requests/${encodeURIComponent(id)}` : null);
export const useStaff = () => useApi<{ staff: Staff[] }>("/crm/staff", { revalidateOnFocus: false });
export const useCaseSteps = () => useApi<{ steps: CaseStepRef[] }>("/reference/case-steps", { revalidateOnFocus: false });
export const usePrograms = () => useApi<{ count: number; programs: Program[] }>("/programs", { revalidateOnFocus: false });
export const useRequestTypes = (programId: string | null) =>
  useApi<{ program_id?: string; request_types: RequestType[] }>(
    programId ? `/programs/${encodeURIComponent(programId)}/request-types` : null,
    { revalidateOnFocus: false },
  );
export const useCommitteeQueue = () => useApi<{ count: number; queue: CommitteeItem[] }>("/committee/queue?limit=100");
export const useDisbursementRun = (days = 60) => useApi<DisbursementRun>(`/finance/disbursement-run?days=${days}`);
export const useSponsorships = () => useApi<{ count: number; monthly_total_sar: number }>("/sponsorships");
export const useNotifications = () =>
  useApi<{ count: number; notifications: Notification[] }>("/notifications?limit=30", { refreshInterval: 60_000 });
export const useHealth = () =>
  useSWR<{ status: string }>("/health", { refreshInterval: 30_000, shouldRetryOnError: false });

/**
 * Revalidate every cached API path that starts with one of the prefixes.
 * Used after mutations so every page showing the affected data refreshes.
 */
export function useRevalidate() {
  const { mutate } = useSWRConfig();
  return useCallback(
    (...prefixes: string[]) =>
      mutate((key) => typeof key === "string" && prefixes.some((p) => key.startsWith(p)), undefined, {
        revalidate: true,
      }),
    [mutate],
  );
}
