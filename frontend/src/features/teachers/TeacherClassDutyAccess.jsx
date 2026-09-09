import { useEffect, useMemo, useState } from "react";

import { classService } from "../../services/academicsService";
import { TeacherClassDutyAccessContext } from "./TeacherClassDutyAccessContext";

export function TeacherClassDutyAccessProvider({ enabled, children }) {
  const [state, setState] = useState({
    loading: Boolean(enabled),
    hasClassTeacherDuties: false,
    error: null,
  });

  useEffect(() => {
    if (!enabled) {
      setState({ loading: false, hasClassTeacherDuties: false, error: null });
      return undefined;
    }

    let active = true;
    const controller = new AbortController();
    setState((current) => ({ ...current, loading: true, error: null }));
    classService
      .getClasses({ limit: 1, activeOnly: true, signal: controller.signal })
      .then((response) => {
        if (!active) return;
        setState({
          loading: false,
          hasClassTeacherDuties: Boolean(response?.items?.length),
          error: null,
        });
      })
      .catch((error) => {
        if (!active || controller.signal.aborted) return;
        setState({
          loading: false,
          hasClassTeacherDuties: false,
          error,
        });
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [enabled]);

  const value = useMemo(() => state, [state]);
  return (
    <TeacherClassDutyAccessContext.Provider value={value}>
      {children}
    </TeacherClassDutyAccessContext.Provider>
  );
}
