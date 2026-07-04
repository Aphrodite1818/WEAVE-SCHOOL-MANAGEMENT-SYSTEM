import { createContext } from "react";
import { getSubscriptionStatusMeta } from "./subscriptionConfig";

export const SubscriptionContext = createContext({
  isTenantAdmin: false,
  currentSubscription: null,
  entitlements: null,
  planCode: null,
  statusCode: null,
  statusMeta: getSubscriptionStatusMeta(null),
  isAttentionRequired: false,
  isLoading: false,
  isRefreshing: false,
  errors: {
    currentSubscription: null,
    entitlements: null,
  },
  refreshSubscriptionState: async () => null,
  getFeatureGuard: () => ({ allowed: true, pending: false, reason: null }),
  getResourceGuard: () => ({
    allowed: true,
    pending: false,
    reason: null,
    usage: null,
  }),
});
