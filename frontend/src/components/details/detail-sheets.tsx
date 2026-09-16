"use client";

import { useSearchParams } from "next/navigation";
import { BENEFICIARY_PARAM, REQUEST_PARAM, TICKET_PARAM, useDetailNav } from "@/components/shell/use-detail-nav";
import { BeneficiarySheet } from "./beneficiary-sheet";
import { RequestSheet } from "./request-sheet";
import { TicketSheet } from "./ticket-sheet";

/** Mounted once in the shell; opens the ticket / beneficiary / support-request panels from the URL. */
export function DetailSheets() {
  const params = useSearchParams();
  const { closeDetails } = useDetailNav();
  return (
    <>
      <TicketSheet id={params.get(TICKET_PARAM)} onClose={closeDetails} />
      <BeneficiarySheet id={params.get(BENEFICIARY_PARAM)} onClose={closeDetails} />
      <RequestSheet id={params.get(REQUEST_PARAM)} onClose={closeDetails} />
    </>
  );
}
