import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";

export function useAdminSetupReadiness() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  const { pathname } = useLocation();
  const refresh = useCallback(async () => {
    const request = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const response = await academicService.getSetupReadiness();
      if (request === generation.current) setData(response);
    } catch (err) {
      if (request === generation.current) {
        setData(null);
        setError(getErrorMessage(err, "Could not check school setup. Refresh to try again."));
      }
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    refresh();
    window.addEventListener("weave:dashboard-cache-clear", refresh);
    return () => {
      generation.current += 1;
      window.removeEventListener("weave:dashboard-cache-clear", refresh);
    };
  }, [refresh, pathname]);
  return { data, error, loading, refresh };
}
