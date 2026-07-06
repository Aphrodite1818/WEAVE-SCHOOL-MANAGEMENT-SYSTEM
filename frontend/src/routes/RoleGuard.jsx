import { Navigate, Outlet } from "react-router-dom";
import { authSession } from "../services/api";
import { getValidTokenPayload } from "../utils/auth";

const ROLE_DASHBOARD_ROUTES = {
  admin: "/admin/dashboard",
  teacher: "/teacher/dashboard",
  student: "/student/dashboard",
  parent: "/parent/dashboard",
  superadmin: "/superadmin/dashboard",
};

function RoleGuard({ allowedRoles = [] }) {
  const payload = getValidTokenPayload();
  const userRole = payload?.role?.toLowerCase();
  const normalizedRoles = allowedRoles.map((role) => role.toLowerCase());

  if (!payload) {
    return <Navigate to="/login" replace />;
  }

  if (!normalizedRoles.includes(userRole)) {
    const safeRedirect = ROLE_DASHBOARD_ROUTES[userRole];

    if (!safeRedirect) {
      authSession.clear();
      return <Navigate to="/login" replace />;
    }

    return <Navigate to={safeRedirect} replace />;
  }

  return <Outlet />;
}

export default RoleGuard;
