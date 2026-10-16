import { useEffect, useState } from "react";
import { getJson } from "./api";

export type Loaded<T> =
  | { state: "loading" }
  | { state: "error"; error: unknown }
  | { state: "ok"; data: T };

export function useApi<T>(path: string | null): Loaded<T> {
  const [result, setResult] = useState<Loaded<T>>({ state: "loading" });
  useEffect(() => {
    if (path === null) {
      setResult({ state: "loading" });
      return;
    }
    const ctrl = new AbortController();
    setResult({ state: "loading" });
    getJson<T>(path, ctrl.signal).then(
      (data) => setResult({ state: "ok", data }),
      (error: unknown) => {
        if (!ctrl.signal.aborted) setResult({ state: "error", error });
      },
    );
    return () => ctrl.abort();
  }, [path]);
  return result;
}
