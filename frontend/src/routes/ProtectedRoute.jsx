import { Navigate, Outlet, useLocation } from "react-router-dom";
import { authSession } from "../services/api";
import { getStoredTokenPayload } from "../utils/auth";

function ProtectedRoute() {
  const location = useLocation();
  const payload = getStoredTokenPayload();

  if (!payload) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  const user = authSession.getUser();
  const isStudent = String(payload?.role || "").toLowerCase() === "student";
  const requiresPasswordReset = Boolean(user?.password_reset_required);
  const isPasswordResetRoute = location.pathname === "/student/change-password";

  if (isStudent && requiresPasswordReset && !isPasswordResetRoute) {
    return <Navigate to="/student/change-password" replace />;
  }

  if (isStudent && !requiresPasswordReset && isPasswordResetRoute) {
    return <Navigate to="/student/dashboard" replace />;
  }

  return <Outlet />;
}

export default ProtectedRoute;
