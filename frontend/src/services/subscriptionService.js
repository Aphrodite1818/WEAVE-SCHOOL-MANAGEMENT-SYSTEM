import { api } from "./api";

export const subscriptionService = {
  getCurrentSubscription: () => api.get("/subscriptions/current"),

  getSubscriptionEntitlements: () => api.get("/subscriptions/entitlements"),

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

  if (
    normalizedMessage.includes("unable to initialize subscription checkout") ||
    normalizedMessage.includes("paystack")
  ) {
    return "We could not start billing right now. Please try again shortly.";
  }

  return null;
};

export default subscriptionService;
