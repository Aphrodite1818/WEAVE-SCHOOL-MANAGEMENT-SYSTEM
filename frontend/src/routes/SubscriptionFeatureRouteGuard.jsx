import { Navigate } from "react-router-dom";

import LoadingState from "../components/shared/LoadingState";
import { useSubscription } from "../features/subscriptions/useSubscription";

function SubscriptionFeatureRouteGuard({
  featureCode,
  fallback = "/admin/dashboard",
  children,
}) {
  const { getFeatureGuard, isLoading, isRefreshing } = useSubscription();
  const featureGuard = getFeatureGuard(featureCode);

  if (featureGuard.allowed === false) {
    return <Navigate to={fallback} replace />;
  }

  if (featureGuard.pending || isLoading || isRefreshing) {
    return <LoadingState label="Checking plan access..." />;
  }

  return children;
}

export default SubscriptionFeatureRouteGuard;
