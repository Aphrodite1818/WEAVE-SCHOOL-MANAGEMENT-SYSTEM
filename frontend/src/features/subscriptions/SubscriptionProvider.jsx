import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { authSession, getErrorMessage } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";
import {
  getSubscriptionStatusMeta,
  isAttentionStatus,
} from "./subscriptionConfig";
import { SubscriptionContext } from "./subscriptionContext";

const normalizeRole = (value) => String(value || "").trim().toLowerCase();

export function SubscriptionProvider({ children }) {
  const location = useLocation();
  const [currentSubscription, setCurrentSubscription] = useState(null);
  const [entitlements, setEntitlements] = useState(null);
  const [errors, setErrors] = useState({
    currentSubscription: null,
    entitlements: null,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const token = authSession.getToken();
  const user = authSession.getUser();
  const role = normalizeRole(user?.role || authSession.getRole());
  const isTenantAdmin = Boolean(token) && role === "admin";

  const refreshSubscriptionState = useCallback(
    async ({ silent = false } = {}) => {
      if (!isTenantAdmin) {
        return null;
      }

      if (silent) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
      }

      const [subscriptionResult, entitlementsResult] = await Promise.allSettled([
        subscriptionService.getCurrentSubscription(),
        subscriptionService.getSubscriptionEntitlements(),
      ]);

      const nextErrors = {
        currentSubscription: null,
        entitlements: null,
      };

      if (subscriptionResult.status === "fulfilled") {
        setCurrentSubscription(subscriptionResult.value || null);
      } else {
        nextErrors.currentSubscription = getErrorMessage(
          subscriptionResult.reason,
          "Failed to load current subscription."
        );
      }

      if (entitlementsResult.status === "fulfilled") {
        setEntitlements(entitlementsResult.value || null);
      } else {
        nextErrors.entitlements = getErrorMessage(
          entitlementsResult.reason,
          "Failed to load subscription entitlements."
        );
      }

      setErrors(nextErrors);

      if (silent) {
        setIsRefreshing(false);
      } else {
        setIsLoading(false);
      }

      return {
        currentSubscription:
          subscriptionResult.status === "fulfilled"
            ? subscriptionResult.value || null
            : null,
        entitlements:
          entitlementsResult.status === "fulfilled"
            ? entitlementsResult.value || null
            : null,
      };
    },
    [isTenantAdmin]
  );

  useEffect(() => {
    if (!isTenantAdmin) return;
    const timerId = window.setTimeout(() => {
      refreshSubscriptionState();
    }, 0);

    return () => {
      window.clearTimeout(timerId);
    };
  }, [isTenantAdmin, location.key, refreshSubscriptionState]);

  const visibleCurrentSubscription = isTenantAdmin ? currentSubscription : null;
  const visibleEntitlements = isTenantAdmin ? entitlements : null;
  const visibleErrors = useMemo(
    () =>
      isTenantAdmin
        ? errors
        : {
            currentSubscription: null,
            entitlements: null,
          },
    [errors, isTenantAdmin]
  );
  const planCode =
    visibleEntitlements?.plan || visibleCurrentSubscription?.plan_code || null;
  const statusCode =
    visibleEntitlements?.subscription_status ||
    visibleCurrentSubscription?.status ||
    null;
  const statusMeta = getSubscriptionStatusMeta(statusCode);

  const getFeatureGuard = useCallback(
    (featureCode) => {
      if (!isTenantAdmin) {
        return { allowed: true, pending: false, reason: null };
      }

      if (isLoading || isRefreshing) {
        return { allowed: true, pending: true, reason: null };
      }

      const features = visibleEntitlements?.features;
      if (!features) {
        return { allowed: true, pending: false, reason: null };
      }

      if (features[featureCode] === false) {
        return {
          allowed: false,
          pending: false,
          reason: null,
        };
      }

      return { allowed: true, pending: false, reason: null };
    },
    [isLoading, isRefreshing, isTenantAdmin, visibleEntitlements]
  );

  const getResourceGuard = useCallback(
    (resourceCode, { featureCode } = {}) => {
      const featureGuard = featureCode
        ? getFeatureGuard(featureCode)
        : { allowed: true, pending: false, reason: null };

      if (!featureGuard.allowed || featureGuard.pending) {
        return {
          allowed: featureGuard.allowed,
          pending: featureGuard.pending,
          reason: featureGuard.reason,
          usage: visibleEntitlements?.usage?.[resourceCode] || null,
        };
      }

      const usage = visibleEntitlements?.usage?.[resourceCode];

      if (usage?.limit_reached) {
        return {
          allowed: false,
          pending: false,
          reason: "You have reached the limit for your current plan.",
          usage,
        };
      }

      return {
        allowed: true,
        pending: false,
        reason: null,
        usage: usage || null,
      };
    },
    [getFeatureGuard, visibleEntitlements]
  );

  const value = useMemo(
    () => ({
      isTenantAdmin,
      currentSubscription: visibleCurrentSubscription,
      entitlements: visibleEntitlements,
      planCode,
      statusCode,
      statusMeta,
      isAttentionRequired: isAttentionStatus(statusCode),
      isLoading: isTenantAdmin ? isLoading : false,
      isRefreshing: isTenantAdmin ? isRefreshing : false,
      errors: visibleErrors,
      refreshSubscriptionState,
      getFeatureGuard,
      getResourceGuard,
    }),
    [
      getFeatureGuard,
      getResourceGuard,
      isLoading,
      isRefreshing,
      isTenantAdmin,
      planCode,
      refreshSubscriptionState,
      statusCode,
      statusMeta,
      visibleCurrentSubscription,
      visibleEntitlements,
      visibleErrors,
    ]
  );

  return (
    <SubscriptionContext.Provider value={value}>
      {children}
    </SubscriptionContext.Provider>
  );
}

export default SubscriptionProvider;
