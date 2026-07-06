import { useEffect, useState } from "react";

import { getErrorMessage, isAbortError } from "../services/api";
import {
  getCachedDashboardBundle,
  getDashboardSessionCacheKey,
} from "../services/dashboardSessionCache";

export default function useDashboardBundle({
  cacheKey,
  loader,
  enabled = true,
  ttlMs,
  errorMessage = "Failed to load dashboard data.",
}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(Boolean(enabled));
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function loadBundle() {
      if (!enabled) {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const resolvedCacheKey = getDashboardSessionCacheKey(cacheKey);
        const bundle = await getCachedDashboardBundle(
          resolvedCacheKey,
          () => loader({ signal: controller.signal }),
          ttlMs ? { ttlMs } : undefined
        );

        if (!mounted || controller.signal.aborted) return;
        setData(bundle);
      } catch (err) {
        if (!mounted || isAbortError(err)) return;
        setError(getErrorMessage(err, errorMessage));
      } finally {
        if (mounted && !controller.signal.aborted) setIsLoading(false);
      }
    }

    loadBundle();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [cacheKey, enabled, errorMessage, loader, ttlMs]);

  return { data, isLoading, error, setError };
}
