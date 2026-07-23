import { useCallback, useState } from "react";
import { ApiError } from "./api";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/** Wraps an async API call with loading/error/data state so every form
 * doesn't have to hand-roll the same three `useState`s. */
export function useAsyncAction<Args extends unknown[], T>(
  fn: (...args: Args) => Promise<T>
) {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: false, error: null });

  const run = useCallback(
    async (...args: Args) => {
      setState({ data: null, loading: true, error: null });
      try {
        const data = await fn(...args);
        setState({ data, loading: false, error: null });
        return data;
      } catch (e) {
        const message = e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e);
        setState({ data: null, loading: false, error: message });
        return null;
      }
    },
    [fn]
  );

  const reset = useCallback(() => setState({ data: null, loading: false, error: null }), []);

  return { ...state, run, reset };
}
