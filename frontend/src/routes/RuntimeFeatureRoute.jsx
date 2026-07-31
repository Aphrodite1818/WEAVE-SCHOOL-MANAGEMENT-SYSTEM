import { Navigate } from "react-router-dom";

import { useRuntimeConfig } from "../hooks/useRuntimeConfig";

const fallbackDashboardByRole = {
  admin: "/admin/dashboard",
  teacher: "/teacher/dashboard",
  student: "/student/dashboard",
  parent: "/parent/dashboard",
  superadmin: "/superadmin/dashboard",
};

function RuntimeFeatureRoute({ feature, role, children }) {
  const runtimeConfig = useRuntimeConfig();
  if (runtimeConfig?.features?.[feature] === false) {
    return <Navigate to={fallbackDashboardByRole[role] || "/"} replace />;
  }
  return children;
}

export default RuntimeFeatureRoute;
