import { useEffect, useState } from "react";

import LoadingState from "../../../components/shared/LoadingState";
import { getErrorMessage, isAbortError } from "../../../services/api";
import { schoolCalendarService } from "../api/schoolCalendarService";
import TodaySchoolStatusCard from "./TodaySchoolStatusCard";

function DashboardCalendarPanel({ role = "student", admin = false, actorId = "", membershipId = "", tenantId = "" }) {
  const [today, setToday] = useState(null);
  const [upcoming, setUpcoming] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function loadCalendar() {
      setLoading(true);
      setError("");
      try {
        const [todayResponse, upcomingResponse] = await Promise.all([
          schoolCalendarService.getToday({}, { signal: controller.signal }),
          schoolCalendarService.getUpcoming({ days: 45, limit: 6 }, { signal: controller.signal }),
        ]);
        if (!mounted || controller.signal.aborted) return;
        setToday(todayResponse);
        setUpcoming(upcomingResponse);
      } catch (err) {
        if (!mounted || isAbortError(err)) return;
        setError(getErrorMessage(err, "Failed to load school calendar."));
      } finally {
        if (mounted && !controller.signal.aborted) setLoading(false);
      }
    }

    loadCalendar();
    return () => {
      mounted = false;
      controller.abort();
    };
  }, [actorId, membershipId, role, tenantId]);

  if (loading) {
    return <LoadingState label="Loading school calendar..." />;
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-900">
        {error}
      </div>
    );
  }

  return <TodaySchoolStatusCard today={today} upcoming={upcoming} role={role} admin={admin} />;
}

export default DashboardCalendarPanel;
