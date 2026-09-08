import { useEffect, useState } from "react";

import { authSession } from "../../services/api";
import { cbtResultLedgerService } from "../../services/cbtResultLedgerService";
import { FEATURE_CODES } from "../subscriptions/subscriptionConfig";
import { useSubscription } from "../subscriptions/useSubscription";

const accessCache = new Map();
const accessRequests = new Map();

const checkHistoricalAccess = async (tenantKey) => {
  if (accessCache.has(tenantKey)) return accessCache.get(tenantKey);
  if (!accessRequests.has(tenantKey)) {
    const request = cbtResultLedgerService
      .listTenantBatches({ skip: 0, limit: 1 })
      .then((response) => Number(response?.total || 0) > 0)
      .catch(() => false)
      .then((allowed) => {
        accessCache.set(tenantKey, allowed);
        accessRequests.delete(tenantKey);
        return allowed;
      });
    accessRequests.set(tenantKey, request);
  }
  return accessRequests.get(tenantKey);
};

export default function useCbtHistoricalAccess({ enabled = true } = {}) {
  const { getFeatureGuard, isLoading, isRefreshing } = useSubscription();
  const featureGuard = getFeatureGuard(FEATURE_CODES.CBT_PAIRING);
  const tenantKey = String(authSession.getUser()?.tenant_id || "current-tenant");
  const [historyState, setHistoryState] = useState(() => ({
    tenantKey,
    checked: accessCache.has(tenantKey),
    allowed: accessCache.get(tenantKey) === true,
  }));
  const currentHistoryState =
    historyState.tenantKey === tenantKey
      ? historyState
      : {
          tenantKey,
          checked: accessCache.has(tenantKey),
          allowed: accessCache.get(tenantKey) === true,
        };

  const featureAllowed = featureGuard.allowed !== false;
  const featurePending = featureGuard.pending || isLoading || isRefreshing;

  useEffect(() => {
    if (!enabled || featurePending || featureAllowed || currentHistoryState.checked) {
      return undefined;
    }

    let active = true;
    const checkHistory = async () => {
      const allowed = await checkHistoricalAccess(tenantKey);
      if (active) {
        setHistoryState({ tenantKey, checked: true, allowed });
      }
    };

    const timeoutId = window.setTimeout(checkHistory, 0);
    return () => {
      active = false;
      window.clearTimeout(timeoutId);
    };
  }, [
    currentHistoryState.checked,
    enabled,
    featureAllowed,
    featurePending,
    tenantKey,
  ]);

  if (!enabled) {
    return { allowed: false, pending: false, source: null };
  }

  if (featurePending) {
    return { allowed: false, pending: true, source: "entitlement" };
  }
  if (featureAllowed) {
    return { allowed: true, pending: false, source: "entitlement" };
  }
  if (!currentHistoryState.checked) {
    return { allowed: false, pending: true, source: "history" };
  }
  return {
    allowed: currentHistoryState.allowed,
    pending: false,
    source: currentHistoryState.allowed ? "history" : null,
  };
}
