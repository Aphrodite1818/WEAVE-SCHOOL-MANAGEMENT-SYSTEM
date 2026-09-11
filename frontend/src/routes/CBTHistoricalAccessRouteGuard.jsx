import { Navigate } from "react-router-dom";

import LoadingState from "../components/shared/LoadingState";
import useCbtHistoricalAccess from "../features/cbt/useCbtHistoricalAccess";

export default function CBTHistoricalAccessRouteGuard({ children }) {
  const access = useCbtHistoricalAccess();

  if (access.pending) {
    return <LoadingState label="Checking CBT access..." />;
  }

  if (access.error) {
    return (
      <div className="mx-auto mt-8 max-w-xl rounded-xl border border-warning/30 bg-warning-soft px-5 py-4 text-sm text-warning">
        <p className="font-semibold">CBT access could not be verified.</p>
        <p className="mt-1 text-xs leading-5">
          The historical audit service is temporarily unavailable. Refresh this page after connectivity is restored.
        </p>
      </div>
    );
  }

  if (!access.allowed) {
    return <Navigate to="/admin/dashboard" replace />;
  }

  return children;
}
