import { useCallback, useEffect, useState } from "react";
import { getErrorMessage, isAbortError } from "../../services/api";
import { getCachedDashboardBundle, getDashboardSessionCacheKey } from "../../services/dashboardSessionCache";
import { parentService } from "../../services/parentService";
import { readSelectedChildId, writeSelectedChildId } from "./parentPageUtils";

export function useParentChildren() {
  const [children, setChildren] = useState([]);
  const [selectedChildId, setSelectedChildIdState] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const setSelectedChildId = useCallback((childId) => {
    setSelectedChildIdState(childId);
    writeSelectedChildId(childId);
  }, []);

  const reloadChildren = useCallback(async (requestOptions = {}) => {
    const cacheKey = getDashboardSessionCacheKey("parent:children");
    const items = await getCachedDashboardBundle(cacheKey, async () => {
      const response = await parentService.getMyStudents(requestOptions);
      return response?.items || [];
    });

    setChildren(items);

    const nextChildId = readSelectedChildId(items);
    setSelectedChildIdState(nextChildId);
    writeSelectedChildId(nextChildId);

    return items;
  }, []);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function loadChildren() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const items = await reloadChildren({ signal: controller.signal });
        if (!mounted || controller.signal.aborted) return;
        if (items.length === 0) {
          setSelectedChildIdState("");
          writeSelectedChildId("");
        }
      } catch (error) {
        if (!mounted || isAbortError(error)) return;
        setLoadError(getErrorMessage(error, "Failed to load linked students."));
      } finally {
        if (mounted && !controller.signal.aborted) setIsLoading(false);
      }
    }

    loadChildren();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [reloadChildren]);

  const selectedChildRecord =
    children.find((item) => item.student?.id === selectedChildId) || null;

  return {
    children,
    selectedChildId,
    selectedChildRecord,
    setSelectedChildId,
    reloadChildren,
    isLoading,
    loadError,
    setLoadError,
  };
}

export default useParentChildren;
