import { api } from "./api";

const backgroundAuthOptions = {
  clearAuthOnUnauthorized: false,
};

const queryString = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const value = query.toString();
  return value ? `?${value}` : "";
};

export const subscriptionService = {
  getCurrentSubscription: () =>
    api.get("/subscriptions/current", backgroundAuthOptions),

  getSubscriptionEntitlements: () =>
    api.get("/subscriptions/entitlements", backgroundAuthOptions),

  getPaymentHistory: (params = {}) =>
    api.get(`/subscriptions/payments${queryString(params)}`, backgroundAuthOptions),

  getCurrentPlanChange: () =>
    api.get("/subscriptions/plan-change/current", backgroundAuthOptions),

  previewPlanChange: (targetPlanCode) =>
    api.get(
      `/subscriptions/plan-change/preview${queryString({
        target_plan_code: targetPlanCode,
      })}`,
      backgroundAuthOptions,
    ),

  schedulePlanChange: (targetPlanCode) =>
    api.post("/subscriptions/plan-change", {
      target_plan_code: targetPlanCode,
      confirmation: "CHANGE_SUBSCRIPTION_PLAN",
    }),

  cancelCurrentSubscription: (payload) =>
    api.post("/subscriptions/cancel", payload),

  initializeSubscriptionCheckout: (payload) =>
    api.post("/subscriptions/checkout", payload),

  verifySubscriptionPayment: (reference) =>
    api.get(`/subscriptions/verify/${encodeURIComponent(reference)}`),
};

export const getSubscriptionCheckoutErrorMessage = (message) => {
  const normalizedMessage = String(message || "").toLowerCase();

  if (normalizedMessage.includes("selected plan billing is not configured")) {
    return "Billing for this plan is not configured yet.";
  }

  if (normalizedMessage.includes("school exceeds the selected plan limits")) {
    return "Your current school usage exceeds this plan. Reduce active usage before scheduling the downgrade.";
  }

  if (normalizedMessage.includes("schedule this downgrade first")) {
    return "Schedule this downgrade first. Payment for the lower plan becomes available after the current paid period ends.";
  }

  if (
    normalizedMessage.includes("unable to initialize subscription checkout") ||
    normalizedMessage.includes("paystack")
  ) {
    return "We could not start billing right now. Please try again shortly.";
  }

  return null;
};

export default subscriptionService;
