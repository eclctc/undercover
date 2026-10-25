import { useCallback, useEffect, useState } from "react";
import { getJson } from "./api";

export interface ApiState<T> {
  data: T | null;
  failed: boolean;
  reload: () => void;
}

/** Load JSON from path once path is set, reloading every pollMs while pollMs is set. */
export function useApi<T>(
  path: string | null,
  pollMs: number | null,
): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (path === null) return;
    let active = true;
    const load = () => {
      getJson<T>(path)
        .then((result) => {
          if (active) setData(result);
        })
        .catch(() => {
          if (active) setFailed(true);
        });
    };
    load();
    const timer = pollMs ? setInterval(load, pollMs) : undefined;
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [path, pollMs, version]);

  const reload = useCallback(() => {
    setVersion((v) => v + 1);
  }, []);

  return { data, failed, reload };
}
