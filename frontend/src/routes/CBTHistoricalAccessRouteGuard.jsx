import { Navigate } from "react-router-dom";

import LoadingState from "../components/shared/LoadingState";
import useCbtHistoricalAccess from "../features/cbt/useCbtHistoricalAccess";

export default function CBTHistoricalAccessRouteGuard({ children }) {
  const access = useCbtHistoricalAccess();

  if (access.pending) {
    return <LoadingState label="Checking CBT access..." />;
  }

  if (!access.allowed) {
    return <Navigate to="/admin/dashboard" replace />;
  }

  return children;
}
