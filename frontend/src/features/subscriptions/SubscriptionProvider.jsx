import {
  startTransition,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation } from "react-router-dom";
import { authSession, getErrorMessage } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";
import {
  getSubscriptionStatusMeta,
  isAttentionStatus,
} from "./subscriptionConfig";
import { SubscriptionContext } from "./subscriptionContext";

const normalizeRole = (value) =>
  String(value || "")
    .trim()
    .toLowerCase();

const scheduleDeferredWork = (
  callback,
  { timeout = 1500, fallbackDelay = 750 } = {},
) => {
  if (typeof window === "undefined") return () => {};

  if (typeof window.requestIdleCallback === "function") {
    const handle = window.requestIdleCallback(callback, { timeout });
    return () => window.cancelIdleCallback?.(handle);
  }

  const timerId = window.setTimeout(callback, fallbackDelay);
  return () => window.clearTimeout(timerId);
};

const commitBackgroundState = (callback) => {
  if (typeof startTransition === "function") {
    startTransition(callback);
    return;
  }

  callback();
};

export function SubscriptionProvider({ children }) {
  const location = useLocation();
  const subscriptionLoadRequestedRef = useRef(false);
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

      const [subscriptionResult, entitlementsResult] = await Promise.allSettled(
        [
          subscriptionService.getCurrentSubscription(),
          subscriptionService.getSubscriptionEntitlements(),
        ],
      );

      const nextErrors = {
        currentSubscription: null,
        entitlements: null,
      };

      const nextCurrentSubscription =
        subscriptionResult.status === "fulfilled"
          ? subscriptionResult.value || null
          : null;
      const nextEntitlements =
        entitlementsResult.status === "fulfilled"
          ? entitlementsResult.value || null
          : null;

      if (subscriptionResult.status !== "fulfilled") {
        nextErrors.currentSubscription = getErrorMessage(
          subscriptionResult.reason,
          "Failed to load current subscription.",
        );
      }

      if (entitlementsResult.status !== "fulfilled") {
        nextErrors.entitlements = getErrorMessage(
          entitlementsResult.reason,
          "Failed to load subscription entitlements.",
        );
      }

      commitBackgroundState(() => {
        if (subscriptionResult.status === "fulfilled") {
          setCurrentSubscription(nextCurrentSubscription);
        }

        if (entitlementsResult.status === "fulfilled") {
          setEntitlements(nextEntitlements);
        }

        setErrors(nextErrors);

        if (silent) {
          setIsRefreshing(false);
        } else {
          setIsLoading(false);
        }
      });

      return {
        currentSubscription: nextCurrentSubscription,
        entitlements: nextEntitlements,
      };
    },
    [isTenantAdmin],
  );

  useEffect(() => {
    if (!isTenantAdmin) {
      subscriptionLoadRequestedRef.current = false;
      return;
    }

    const shouldRefreshAfterPaymentRedirect =
      location.pathname === "/billing/subscription/verify";
    const shouldLoadSubscriptionState =
      !subscriptionLoadRequestedRef.current ||
      shouldRefreshAfterPaymentRedirect;

    if (!shouldLoadSubscriptionState) return;

    subscriptionLoadRequestedRef.current = true;

    if (shouldRefreshAfterPaymentRedirect) {
      const timerId = window.setTimeout(() => {
        refreshSubscriptionState();
      }, 0);

      return () => {
        window.clearTimeout(timerId);
      };
    }

    return scheduleDeferredWork(() => {
      refreshSubscriptionState();
    });
  }, [isTenantAdmin, location.pathname, refreshSubscriptionState]);

  useEffect(() => {
    if (!isTenantAdmin) return undefined;
    const handlePullRefresh = () => {
      refreshSubscriptionState({ silent: true });
    };
    window.addEventListener("weave:pull-refresh", handlePullRefresh);
    return () => {
      window.removeEventListener("weave:pull-refresh", handlePullRefresh);
    };
  }, [isTenantAdmin, refreshSubscriptionState]);

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
    [errors, isTenantAdmin],
  );
  const tenantSnapshot = user?.tenant?.tenant || user?.tenant || {};
  const planCode =
    visibleCurrentSubscription?.plan_code ||
    visibleEntitlements?.plan ||
    tenantSnapshot?.plan ||
    user?.plan ||
    null;
  const statusCode =
    visibleCurrentSubscription?.status ||
    visibleEntitlements?.subscription_status ||
    tenantSnapshot?.subscription_status ||
    user?.subscription_status ||
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
        if (visibleErrors.entitlements) {
          return {
            allowed: false,
            pending: false,
            reason:
              "We couldn't confirm access for this feature. Refresh and try again.",
          };
        }
        return { allowed: true, pending: true, reason: null };
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
    [
      isLoading,
      isRefreshing,
      isTenantAdmin,
      visibleEntitlements,
      visibleErrors.entitlements,
    ],
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

      if (isTenantAdmin && !visibleEntitlements) {
        if (visibleErrors.entitlements) {
          return {
            allowed: false,
            pending: false,
            reason:
              "We couldn't confirm your plan limits. Refresh and try again.",
            usage: null,
          };
        }
        return {
          allowed: true,
          pending: true,
          reason: null,
          usage: null,
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
    [
      getFeatureGuard,
      isTenantAdmin,
      visibleEntitlements,
      visibleErrors.entitlements,
    ],
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
    ],
  );

  return (
    <SubscriptionContext.Provider value={value}>
      {children}
    </SubscriptionContext.Provider>
  );
}

export default SubscriptionProvider;
