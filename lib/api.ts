/** Typed client for the API. All finance logic lives on the server. */
"use client";

import { useEffect, useState } from "react";

export async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      signal,
      ...(body === undefined
        ? {}
        : {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }),
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error("Could not reach the server. Check your connection and try again.");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload === null) {
    throw new Error(payload?.error?.message ?? "The server could not complete the request.");
  }
  return payload as T;
}

export interface Query<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/**
 * GET (body undefined) or POST. Pass path = null to pause. The previous result stays
 * visible while a new one loads, so numbers do not flash on every slider move.
 */
export function useApi<T>(path: string | null, body?: unknown): Query<T> {
  const key = path === null ? null : `${path} ${body === undefined ? "" : JSON.stringify(body)}`;
  const [state, setState] = useState<{ key: string; data: T | null; error: string | null } | null>(
    null,
  );

  useEffect(() => {
    if (key === null) return;
    const split = key.indexOf(" ");
    const target = key.slice(0, split);
    const json = key.slice(split + 1);
    const controller = new AbortController();
    request<T>(target, json ? JSON.parse(json) : undefined, controller.signal)
      .then((data) => setState({ key, data, error: null }))
      .catch((error: Error) => {
        if (!controller.signal.aborted) {
          setState((prev) => ({ key, data: prev?.data ?? null, error: error.message }));
        }
      });
    return () => controller.abort();
  }, [key]);

  const current = state !== null && state.key === key;
  return {
    data: state?.data ?? null,
    error: current ? state.error : null,
    loading: key !== null && !current,
  };
}

/** The value after it has stopped changing for ``ms`` milliseconds (slider debounce). */
export function useDebounced<T>(value: T, ms = 350): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

/** POST and save the returned file (the Excel export). */
export async function download(path: string, body: unknown, fallbackName: string): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.error?.message ?? "The file could not be created.");
  }
  const named = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") ?? "");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = named?.[1] ?? fallbackName;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
