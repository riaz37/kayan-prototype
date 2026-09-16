"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";

/**
 * Local search state seeded from `?q=` (set by the topbar search). When the
 * URL query changes (a new topbar search), the local value follows it.
 */
export function useUrlQuery(): [string, (v: string) => void] {
  const urlQ = useSearchParams().get("q") ?? "";
  const [state, setState] = useState({ urlQ, value: urlQ });
  if (state.urlQ !== urlQ) {
    // Adjusting state during render (React-recommended over an effect).
    setState({ urlQ, value: urlQ });
  }
  return [state.urlQ !== urlQ ? urlQ : state.value, (value) => setState((s) => ({ ...s, value }))];
}
