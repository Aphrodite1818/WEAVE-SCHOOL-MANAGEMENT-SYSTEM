import { useCallback, useEffect, useState } from "react";
import { getErrorMessage } from "../../services/api";
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

  const reloadChildren = useCallback(async () => {
    const response = await parentService.getMyStudents();
    const items = response?.items || [];
    setChildren(items);

    const nextChildId = readSelectedChildId(items);
    setSelectedChildIdState(nextChildId);
    writeSelectedChildId(nextChildId);

    return items;
  }, []);

  useEffect(() => {
    let mounted = true;

    async function loadChildren() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const items = await reloadChildren();
        if (!mounted) return;
        if (items.length === 0) {
          setSelectedChildIdState("");
          writeSelectedChildId("");
        }
      } catch (error) {
        if (!mounted) return;
        setLoadError(getErrorMessage(error, "Failed to load linked students."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadChildren();

    return () => {
      mounted = false;
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
