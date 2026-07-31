import { Navigate } from "react-router-dom";

import LoadingState from "../components/shared/LoadingState";
import { FEATURE_CODES } from "../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../features/subscriptions/useSubscription";
import BulkImportPage from "../pages/admin/BulkImportPage";

function BulkImportRouteGuard({ children = null }) {
  const { getFeatureGuard, isLoading, isRefreshing, planCode } = useSubscription();
  const bulkImportGuard = getFeatureGuard(FEATURE_CODES.BULK_IMPORT);
  const isTrialPlan = String(planCode || "").trim().toLowerCase() === "free_trial";

  if (isTrialPlan || bulkImportGuard.allowed === false) {
    return <Navigate to="/admin/dashboard" replace />;
  }

  if (bulkImportGuard.pending || isLoading || isRefreshing) {
    return <LoadingState label="Checking plan access..." />;
  }

  return children || <BulkImportPage />;
}

export default BulkImportRouteGuard;
