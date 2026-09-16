"use client";

import { useCallback, useSyncExternalStore } from "react";

const KEY = "kayan:show-expired";
const listeners = new Set<() => void>();

function read(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  const onStorage = (e: StorageEvent) => e.key === KEY && cb();
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", onStorage);
  };
}

/**
 * Whether expired (past-SLA) tickets are shown. Hidden by default; the choice
 * is remembered per browser and shared by the board, dashboard and ticket list.
 */
export function useShowExpired(): [boolean, (value: boolean) => void] {
  const value = useSyncExternalStore(subscribe, read, () => false);
  const set = useCallback((next: boolean) => {
    try {
      window.localStorage.setItem(KEY, next ? "1" : "0");
    } catch {
      /* storage unavailable (private mode) — preference just won't persist */
    }
    listeners.forEach((l) => l());
  }, []);
  return [value, set];
}
