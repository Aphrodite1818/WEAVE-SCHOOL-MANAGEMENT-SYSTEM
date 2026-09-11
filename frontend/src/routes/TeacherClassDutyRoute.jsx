import { Navigate, Outlet, useLocation } from "react-router-dom";

import LoadingState from "../components/shared/LoadingState";
import { useTeacherClassDutyAccess } from "../features/teachers/TeacherClassDutyAccessContext";

export default function TeacherClassDutyRoute() {
  const location = useLocation();
  const { loading, hasClassTeacherDuties } = useTeacherClassDutyAccess();

  if (loading) return <LoadingState label="Checking class-teacher assignment..." />;
  if (!hasClassTeacherDuties) {
    return (
      <Navigate
        to="/teacher/dashboard"
        replace
        state={{ from: location.pathname, reason: "class-teacher-required" }}
      />
    );
  }
  return <Outlet />;
}
