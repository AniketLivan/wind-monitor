import { useEffect, useState } from "react";

export type Async<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ok"; data: T };

/** Runs `load` whenever `key` changes; ignores responses that arrive after a newer request. */
export function useAsync<T>(load: () => Promise<T>, key: string): Async<T> {
  const [state, setState] = useState<Async<T>>({ status: "loading" });
  useEffect(() => {
    let current = true;
    setState({ status: "loading" });
    load().then(
      (data) => current && setState({ status: "ok", data }),
      (e: Error) => current && setState({ status: "error", message: e.message }),
    );
    return () => {
      current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}
