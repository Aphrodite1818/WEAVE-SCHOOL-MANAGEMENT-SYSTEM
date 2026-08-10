
import { API_BASE_URL, api } from "./api";

const PUBLIC_CATALOGUE_ETAG_KEY = "weave:public-pricing-etag";
const PUBLIC_CATALOGUE_VALUE_KEY = "weave:public-pricing-catalogue";

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

const readStoredCatalogue = () => {
  try {
    return JSON.parse(window.sessionStorage.getItem(PUBLIC_CATALOGUE_VALUE_KEY) || "null");
  } catch {
    window.sessionStorage.removeItem(PUBLIC_CATALOGUE_VALUE_KEY);
    return null;
  }
};

const getPublicPlans = async ({ force = false } = {}) => {
  const storedEtag = window.sessionStorage.getItem(PUBLIC_CATALOGUE_ETAG_KEY);
  const headers = {};
  if (!force && storedEtag) headers["If-None-Match"] = storedEtag;

  const response = await fetch(`${API_BASE_URL}/subscriptions/plans`, {
    method: "GET",
    credentials: "include",
    cache: "no-cache",
    headers,
  });

  if (response.status === 304) {
    const cached = readStoredCatalogue();
    if (cached) return cached;
    return getPublicPlans({ force: true });
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data?.detail || data?.message || "Pricing catalogue unavailable.");
    error.response = { status: response.status, data };
    throw error;
  }

  const etag = response.headers.get("etag");
  if (etag) window.sessionStorage.setItem(PUBLIC_CATALOGUE_ETAG_KEY, etag);
  window.sessionStorage.setItem(PUBLIC_CATALOGUE_VALUE_KEY, JSON.stringify(data));
  return data;
};

export const subscriptionService = {
  getPublicPlans,

  getCurrentSubscription: () =>
    api.get("/subscriptions/current", backgroundAuthOptions),

  getSubscriptionEntitlements: () =>
    api.get("/subscriptions/entitlements", backgroundAuthOptions),

  getActorEntitlements: () =>
    api.get("/subscriptions/actor-entitlements", backgroundAuthOptions),

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

  initializeSubscriptionCheckout: async (payload) => {
    await getPublicPlans({ force: true });
    return api.post("/subscriptions/checkout", payload);
  },

  verifySubscriptionPayment: (reference) =>
    api.get(`/subscriptions/verify/${encodeURIComponent(reference)}`),
};

export const getSubscriptionCheckoutErrorMessage = (message) => {
  const normalizedMessage = String(message || "").toLowerCase();

  if (normalizedMessage.includes("selected plan billing is not configured")) {
    return "Checkout for this plan is temporarily unavailable. Please try again later.";
  }
  if (normalizedMessage.includes("provider plan configuration")) {
    return "We couldn't start checkout right now. Please try again in a moment.";
  }
  if (normalizedMessage.includes("payment verification failed")) {
    return "We couldn't confirm this payment. Please try again or contact support if the problem continues.";
  }
  if (normalizedMessage.includes("school exceeds the selected plan limits")) {
    return "Your current school usage is above this plan's limits. Reduce usage before switching to this plan.";
  }
  if (normalizedMessage.includes("schedule this downgrade first")) {
    return "This plan change is not ready for payment yet. Please wait until your current billing period ends.";
  }
  if (
    normalizedMessage.includes("unable to initialize subscription checkout") ||
    normalizedMessage.includes("paystack")
  ) {
    return "We couldn't start checkout right now. Please try again in a moment.";
  }
  return null;
};

export default subscriptionService;
