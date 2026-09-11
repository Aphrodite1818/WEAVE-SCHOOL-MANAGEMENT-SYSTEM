import { useEffect, useState } from "react";

import { authSession } from "../../services/api";
import { cbtResultLedgerService } from "../../services/cbtResultLedgerService";
import { FEATURE_CODES } from "../subscriptions/subscriptionConfig";
import { useSubscription } from "../subscriptions/useSubscription";

const accessCache = new Map();
const accessRequests = new Map();

const checkHistoricalAccess = async (tenantKey) => {
  if (accessCache.has(tenantKey)) {
    return { allowed: accessCache.get(tenantKey), error: null };
  }
  if (!accessRequests.has(tenantKey)) {
    const request = cbtResultLedgerService
      .listTenantBatches({ skip: 0, limit: 1 })
      .then((response) => {
        const allowed = Number(response?.total || 0) > 0;
        accessCache.set(tenantKey, allowed);
        return { allowed, error: null };
      })
      .catch((error) => ({ allowed: false, error }))
      .finally(() => {
        accessRequests.delete(tenantKey);
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
    error: null,
  }));
  const currentHistoryState =
    historyState.tenantKey === tenantKey
      ? historyState
      : {
          tenantKey,
          checked: accessCache.has(tenantKey),
          allowed: accessCache.get(tenantKey) === true,
          error: null,
        };

  const featureAllowed = featureGuard.allowed !== false;
  const featurePending = featureGuard.pending || isLoading || isRefreshing;

  useEffect(() => {
    if (!enabled || featurePending || featureAllowed || currentHistoryState.checked) {
      return undefined;
    }

    let active = true;
    const checkHistory = async () => {
      const result = await checkHistoricalAccess(tenantKey);
      if (active) {
        setHistoryState({
          tenantKey,
          checked: result.error == null,
          allowed: result.allowed,
          error: result.error,
        });
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
    return { allowed: false, pending: false, source: null, error: null };
  }
  if (featurePending) {
    return { allowed: false, pending: true, source: "entitlement", error: null };
  }
  if (featureAllowed) {
    return { allowed: true, pending: false, source: "entitlement", error: null };
  }
  if (currentHistoryState.error) {
    return {
      allowed: false,
      pending: false,
      source: "history",
      error: currentHistoryState.error,
    };
  }
  if (!currentHistoryState.checked) {
    return { allowed: false, pending: true, source: "history", error: null };
  }
  return {
    allowed: currentHistoryState.allowed,
    pending: false,
    source: currentHistoryState.allowed ? "history" : null,
    error: null,
  };
}
