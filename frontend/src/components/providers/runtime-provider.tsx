"use client";

import { createContext, useContext, type ReactNode } from "react";

type Runtime = { backendUrl: string; isLocal: boolean };

const RuntimeContext = createContext<Runtime>({ backendUrl: "", isLocal: true });

/** Server-provided runtime facts (which backend the console proxies to). */
export function RuntimeProvider({ backendUrl, children }: { backendUrl: string; children: ReactNode }) {
  let isLocal = true;
  try {
    isLocal = ["localhost", "127.0.0.1", "[::1]"].includes(new URL(backendUrl).hostname);
  } catch {
    isLocal = true;
  }
  return <RuntimeContext.Provider value={{ backendUrl, isLocal }}>{children}</RuntimeContext.Provider>;
}

export const useRuntime = () => useContext(RuntimeContext);
